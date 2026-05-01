"""Engine component for Denormalize (tDenormalize).

Groups rows by key columns (all columns NOT in the denormalize list) and
concatenates values of specified columns using per-column delimiters.
This is the inverse of the Normalize (tNormalize) component.

Config keys consumed (2 total):
  denormalize_columns (list of dicts, default [])  -- columns to concatenate.
    Each dict has:
      input_column (str, required)  -- column name to concatenate
      delimiter    (str, default ";") -- delimiter for concatenation
      merge        (bool, default False) -- deduplicate values before concatenation
  null_as_empty    (bool, default False) -- treat null values as empty strings
                                           (engine-only; not a _java.xml param)

Key column detection:
  Any column NOT listed in denormalize_columns is treated as a grouping key.
  Rows are grouped by these key columns; one output row per unique key combination.
  Null-key rows are preserved as their own group (dropna=False, Talend-compatible).

Talend reference:
  tDenormalize_main.javajet (Talaxie mirror):
  https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/
  org.talend.designer.components.localprovider/components/tDenormalize/
  tDenormalize_main.javajet

Note: null_as_empty has no Talend _java.xml equivalent. It is an engine-only
enhancement. The delimiter default in Talend _java.xml is ";" per column.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, DataValidationError

logger = logging.getLogger(__name__)


@REGISTRY.register("Denormalize", "tDenormalize")
class Denormalize(BaseComponent):
    """tDenormalize engine implementation.

    Groups rows by key columns (those NOT in ``denormalize_columns``) and
    concatenates the values of each configured column within each group,
    separated by the per-column delimiter. Supports optional deduplication
    (merge flag) and null handling (null_as_empty flag).

    Talend reference: tDenormalize_main.javajet
    """

    def _validate_config(self) -> None:
        """Validate component configuration.

        Only checks key presence and container shape per Rule 12. Content checks
        (bool isinstance for null_as_empty, delimiter content) are deferred to
        _process() after context variable resolution.

        Raises:
            ConfigurationError: If denormalize_columns is present but not a list,
                or if any entry is not a dict, or if input_column is missing from
                an entry.
        """
        denormalize_columns = self.config.get("denormalize_columns", [])
        if not isinstance(denormalize_columns, list):
            raise ConfigurationError(
                f"[{self.id}] 'denormalize_columns' must be a list, "
                f"got {type(denormalize_columns).__name__!r}"
            )
        for i, col_config in enumerate(denormalize_columns):
            if not isinstance(col_config, dict):
                raise ConfigurationError(
                    f"[{self.id}] 'denormalize_columns[{i}]' must be a dict, "
                    f"got {type(col_config).__name__!r}"
                )
            if "input_column" not in col_config:
                raise ConfigurationError(
                    f"[{self.id}] 'denormalize_columns[{i}]' missing required key 'input_column'"
                )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Group rows by key columns and concatenate denormalize column values.

        Args:
            input_data: Input DataFrame. If None or empty, returns empty result.

        Returns:
            Dict with ``main`` key (denormalized DataFrame) and ``reject`` key (None).

        Raises:
            DataValidationError: If configured denormalize columns are missing from
                input, or if no key columns can be determined.
        """
        if input_data is None or input_data.empty:
            logger.warning("[%s] Empty input received, returning empty result", self.id)
            return {"main": pd.DataFrame(), "reject": None}

        rows_in = len(input_data)
        logger.info("[%s] Processing started: %d rows", self.id, rows_in)

        denormalize_columns: List[Dict[str, Any]] = self.config.get("denormalize_columns", [])
        null_as_empty: bool = bool(self.config.get("null_as_empty", False))

        # ---- 1. Pass-through when no denormalize columns configured --------
        if not denormalize_columns:
            logger.warning("[%s] No denormalize_columns configured, passing data through", self.id)
            return {"main": input_data.copy(), "reject": None}

        # ---- 2. Validate columns exist in input ----------------------------
        denorm_col_names: List[str] = [col["input_column"] for col in denormalize_columns]
        missing_cols = [c for c in denorm_col_names if c not in input_data.columns]
        if missing_cols:
            raise DataValidationError(
                f"[{self.id}] Denormalize columns not found in input: {missing_cols}"
            )

        # ---- 3. Identify key columns (all non-denormalize columns) ---------
        key_columns: List[str] = [c for c in input_data.columns if c not in denorm_col_names]
        if not key_columns:
            raise DataValidationError(
                f"[{self.id}] No key columns found -- all columns are in "
                f"denormalize_columns list. At least one non-denormalize column is required."
            )

        logger.debug("[%s] Key columns: %s", self.id, key_columns)
        logger.debug("[%s] Denormalize columns: %s", self.id, denorm_col_names)

        # ---- 4. Build per-column aggregation functions ---------------------
        # dropna=False preserves rows with null values in key columns as a
        # separate group, matching Talend tDenormalize behavior (ENG-DNR-003).
        aggregation_dict: Dict[str, Any] = {}

        for col_config in denormalize_columns:
            col_name: str = col_config["input_column"]
            # Base class has already resolved context vars before _process() runs.
            delimiter: str = col_config.get("delimiter", ";")
            do_merge: bool = bool(col_config.get("merge", False))

            def make_concat_func(delim: str, merge: bool) -> Any:
                def concat_func(series: pd.Series) -> str:
                    if null_as_empty:
                        values = [str(val) if pd.notnull(val) else "" for val in series]
                    else:
                        values = [str(val) for val in series if pd.notnull(val)]
                    if merge:
                        # Deduplicate while preserving first-seen order (Talend merge=True)
                        seen: Dict[str, None] = {}
                        values = [v for v in values if not (v in seen or seen.update({v: None}))]  # type: ignore[func-returns-value]
                    return delim.join(values) if values else ""
                return concat_func

            aggregation_dict[col_name] = make_concat_func(delimiter, do_merge)

        # Key columns: take the first value per group (identical within group)
        for key_col in key_columns:
            aggregation_dict[key_col] = "first"

        # ---- 5. Perform groupby (dropna=False preserves null-key rows) -----
        denormalized_df: pd.DataFrame = input_data.groupby(
            key_columns if len(key_columns) > 1 else key_columns[0],
            as_index=False,
            dropna=False,
            sort=False,
        ).agg(aggregation_dict)

        # Restore original column order: key columns first, then denorm columns
        output_columns = key_columns + denorm_col_names
        denormalized_df = denormalized_df[output_columns]

        rows_out = len(denormalized_df)
        logger.info(
            "[%s] Processing complete: in=%d, out=%d, rejected=0",
            self.id, rows_in, rows_out,
        )

        return {"main": denormalized_df, "reject": None}
