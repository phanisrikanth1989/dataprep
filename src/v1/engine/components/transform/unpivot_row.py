"""Engine component for UnpivotRow (tUnpivotRow).

Transforms wide-format data into long-format (tall) data by unpivoting columns
into rows. Columns listed in row_keys are preserved as identifier columns; all
remaining columns are melted into key-value pairs.

Config keys consumed (4 unique + 2 framework):
  row_keys             (list[str], required)       -- columns to preserve as identifiers
  pivot_key            (str, default "pivot_key")  -- output column name for original column names
  pivot_value          (str, default "pivot_value") -- output column name for cell values
  include_empty_values (bool, default True)         -- keep null/empty value rows
  die_on_error         (bool, default True)         -- raise on error vs return empty output
  --- framework ---
  tstatcatcher_stats   (bool)
  label                (str)

Community component (michimau/talend_components). _java.xml 404. MEDIUM confidence.

Talend behavioral contract (from community source + .item file exports):
  - Output columns = row_keys + [pivot_key, pivot_value] ONLY (no pollution)
  - pivot_value is always coerced to String
  - INCLUDE_EMPTY_VALUES=false drops rows where pivot_value is null/empty
  - Row order: each input row produces len(columns_to_unpivot) output rows
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("UnpivotRow", "tUnpivotRow")
class UnpivotRow(BaseComponent):
    """tUnpivotRow engine implementation.

    Melts non-key columns into key-value row pairs. Identifier columns
    (row_keys) are replicated for every output row. The pivot_value column
    is always coerced to String to match Talend behavior.

    Community component reference: michimau/talend_components
    """

    _DEFAULT_PIVOT_KEY = "pivot_key"
    _DEFAULT_PIVOT_VALUE = "pivot_value"

    def _validate_config(self) -> None:
        """Validate component configuration.

        Checks key presence and container shape only (Rule 12). Content checks
        (empty list, column presence in data) are deferred to _process() after
        context variable resolution.

        Raises:
            ConfigurationError: If row_keys is missing or not a list.
        """
        if "row_keys" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'row_keys'"
            )
        if not isinstance(self.config["row_keys"], list):
            raise ConfigurationError(
                f"[{self.id}] Config 'row_keys' must be a list, "
                f"got {type(self.config['row_keys']).__name__!r}"
            )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Unpivot input columns into key-value rows.

        Args:
            input_data: Input DataFrame to unpivot. If None or empty, returns
                empty result with stats zeroed.

        Returns:
            dict with 'main' key (unpivoted DataFrame) and 'reject' key (None).

        Raises:
            ConfigurationError: If row_keys is empty or contains columns absent
                from input, and die_on_error is True (default).
        """
        if input_data is None or input_data.empty:
            logger.warning("[%s] Empty input received", self.id)
            self._update_stats(0, 0, 0)
            return {"main": pd.DataFrame(), "reject": None}

        rows_in = len(input_data)
        logger.info("[%s] Processing started: %d rows", self.id, rows_in)

        # ---- 1. Read resolved config ----------------------------------------
        row_keys: list[str] = self.config.get("row_keys", [])
        pivot_key_col: str = self.config.get("pivot_key", self._DEFAULT_PIVOT_KEY)
        pivot_value_col: str = self.config.get("pivot_value", self._DEFAULT_PIVOT_VALUE)
        include_empty: bool = self.config.get("include_empty_values", True)
        die_on_error: bool = self.config.get("die_on_error", True)

        logger.debug(
            "[%s] Config: row_keys=%s pivot_key=%r pivot_value=%r include_empty=%s",
            self.id, row_keys, pivot_key_col, pivot_value_col, include_empty,
        )

        # ---- 2. Deferred content validation (Rule 12) ----------------------
        if not row_keys:
            msg = f"[{self.id}] 'row_keys' cannot be empty"
            if die_on_error:
                raise ConfigurationError(msg)
            logger.error(msg)
            self._update_stats(rows_in, 0, 0)
            return {"main": pd.DataFrame(), "reject": None}

        missing_keys = [k for k in row_keys if k not in input_data.columns]
        if missing_keys:
            msg = f"[{self.id}] row_keys columns not found in input: {missing_keys}"
            if die_on_error:
                raise ConfigurationError(msg)
            logger.error(msg)
            self._update_stats(rows_in, 0, 0)
            return {"main": pd.DataFrame(), "reject": None}

        # ---- 3. Identify value columns to unpivot --------------------------
        columns_to_unpivot = [c for c in input_data.columns if c not in row_keys]
        logger.debug("[%s] Columns to unpivot: %s", self.id, columns_to_unpivot)

        if not columns_to_unpivot:
            # All columns are row_keys — nothing to melt
            logger.info("[%s] No columns to unpivot (all are row_keys)", self.id)
            empty = pd.DataFrame(columns=row_keys + [pivot_key_col, pivot_value_col])
            self._update_stats(rows_in, 0, 0)
            return {"main": empty, "reject": None}

        # ---- 4. Melt (unpivot) — no copy needed, melt creates new DataFrame --
        out = input_data.melt(
            id_vars=row_keys,
            value_vars=columns_to_unpivot,
            var_name=pivot_key_col,
            value_name=pivot_value_col,
        )

        # ---- 5. String coercion for pivot_value (Talend always outputs String) --
        # Use .map() to avoid FutureWarning on dtype-incompatible .loc assignment
        # when the column is typed int64/float64 and we assign str values.
        out[pivot_value_col] = out[pivot_value_col].map(
            lambda x: str(x) if pd.notna(x) else x
        )

        # ---- 6. Optionally drop null pivot_value rows ----------------------
        if not include_empty:
            before = len(out)
            out = out.dropna(subset=[pivot_value_col]).reset_index(drop=True)
            logger.info(
                "[%s] include_empty_values=False: filtered %d null-value rows",
                self.id, before - len(out),
            )

        # ---- 7. Final column order: row_keys + pivot_key + pivot_value -----
        # Output contains ONLY these columns — no pollution from value cols
        out = out[row_keys + [pivot_key_col, pivot_value_col]].reset_index(drop=True)

        rows_out = len(out)
        self._update_stats(rows_in, rows_out, 0)
        logger.info("[%s] Complete: in=%d out=%d", self.id, rows_in, rows_out)
        return {"main": out, "reject": None}
