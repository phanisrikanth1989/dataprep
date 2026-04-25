"""Engine component for Normalize (tNormalize).

Splits a single column on a separator, exploding each delimited value into a
separate output row. All other columns are carried through unchanged.

Config keys consumed (6 total):
  normalize_column           (str, required)      -- column to split
  item_separator             (str, default ",")   -- literal separator (not regex)
  trim                       (bool, default False) -- strip whitespace from each value
  discard_trailing_empty_str (bool, default False) -- remove only TRAILING empties per
                                                      Talend tNormalize semantics
  deduplicate                (bool, default False) -- remove duplicate values per row
  die_on_error               (bool, default True)  -- raise on config/runtime errors

Talend reference:
  tNormalize_main.javajet (Talaxie mirror):
  https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/
  org.talend.designer.components.localprovider/components/tNormalize/
  tNormalize_main.javajet

Talend operation order (per Talaxie source and help.qlik.com docs):
  discard_trailing_empty_str -> trim -> deduplicate
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("Normalize", "tNormalize")
class Normalize(BaseComponent):
    """tNormalize engine implementation.

    Splits values in ``normalize_column`` by ``item_separator``, exploding each
    split value into a separate output row. All other columns are preserved
    with their original dtypes (vectorized via .str.split + .explode).

    Talend reference: tNormalize_main.javajet
    """

    def _validate_config(self) -> None:
        """Validate component configuration.

        Raises:
            ConfigurationError: If normalize_column is missing, not a non-empty
                string, or if any boolean option is not a bool.
        """
        if "normalize_column" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'normalize_column'"
            )
        nc = self.config["normalize_column"]
        if not isinstance(nc, str) or not nc.strip():
            raise ConfigurationError(
                f"[{self.id}] 'normalize_column' must be a non-empty string, "
                f"got {type(nc).__name__!r}: {nc!r}"
            )

        sep = self.config.get("item_separator", ",")
        if not isinstance(sep, str):
            raise ConfigurationError(
                f"[{self.id}] 'item_separator' must be a string, "
                f"got {type(sep).__name__!r}"
            )

        for flag in ("deduplicate", "trim", "discard_trailing_empty_str", "die_on_error"):
            if flag in self.config and not isinstance(self.config[flag], bool):
                raise ConfigurationError(
                    f"[{self.id}] '{flag}' must be a boolean, "
                    f"got {type(self.config[flag]).__name__!r}"
                )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Split ``normalize_column`` values into multiple rows.

        Args:
            input_data: Input DataFrame. If None or empty, returns empty result.

        Returns:
            dict with ``main`` key (exploded DataFrame) and ``reject`` key (None).

        Raises:
            ConfigurationError: If ``normalize_column`` is not present in input columns.
        """
        if input_data is None:
            return {"main": pd.DataFrame(), "reject": None}
        if input_data.empty:
            return {"main": input_data, "reject": None}

        norm_col: str = self.config["normalize_column"]
        sep: str = self.config.get("item_separator", ",")
        trim: bool = self.config.get("trim", False)
        discard_trailing: bool = self.config.get("discard_trailing_empty_str", False)
        dedupe: bool = self.config.get("deduplicate", False)

        rows_in = len(input_data)
        logger.info("[%s] Processing started: %d rows", self.id, rows_in)

        if norm_col not in input_data.columns:
            raise ConfigurationError(
                f"[{self.id}] Column '{norm_col}' not found in input. "
                f"Available columns: {list(input_data.columns)}"
            )

        df = input_data.copy()

        # ---- 1. Vectorized split ----------------------------------------
        # .astype("string") coerces any non-string cell (lists, numbers, NaN)
        # to a StringDtype string before splitting -- this avoids the per-cell
        # pd.isna() array-truthiness crash (ENG-WR-01).
        # regex=False treats sep as a literal string, not a regex pattern.
        splits = (
            df[norm_col]
            .astype("string")
            .fillna("")
            .str.split(sep, regex=False)
        )

        # ---- 2. Talend operation order: discard -> trim -> dedupe ---------
        # Source: Talaxie tNormalize_main.javajet (lastNoEmptyIndex_ loop)
        #         help.qlik.com tNormalize documentation
        if discard_trailing:
            splits = splits.apply(self._strip_trailing_empties)

        if trim:
            splits = splits.apply(lambda lst: [v.strip() for v in lst])

        if dedupe:
            splits = splits.apply(lambda lst: list(dict.fromkeys(lst)))

        df[norm_col] = splits

        # ---- 3. Explode into multiple rows ---------------------------------
        # .explode() on a list column expands each list element to its own row.
        # All other columns are repeated with their original dtypes preserved
        # (vectorized -- fixes ENG-CR-02, no O(n^2) row-by-row rebuild).
        # When a list is empty, explode produces NaN for that row.
        out = df.explode(norm_col, ignore_index=True)

        if discard_trailing:
            # Empty-list rows come from rows where all values were trailing empties.
            # Talend emits 0 rows for those (ENG-WR-02). Drop them.
            out = out.dropna(subset=[norm_col]).reset_index(drop=True)
        else:
            # Replace NaN from empty non-discarding explode with empty string
            out[norm_col] = out[norm_col].fillna("")

        rows_out = len(out)
        logger.info("[%s] Processing complete: in=%d, out=%d, rejected=0",
                    self.id, rows_in, rows_out)

        return {"main": out, "reject": None}

    @staticmethod
    def _strip_trailing_empties(lst: list) -> list:
        """Remove only TRAILING empty strings from a list.

        Mirrors the ``lastNoEmptyIndex_`` loop in Talaxie tNormalize_main.javajet.
        Interior empty strings are preserved; only the trailing run is stripped.

        Args:
            lst: List of split string values.

        Returns:
            List with trailing empty strings removed.

        Examples:
            _strip_trailing_empties(["a", "b", "", ""]) -> ["a", "b"]
            _strip_trailing_empties(["a", "", "b", ""]) -> ["a", "", "b"]
            _strip_trailing_empties(["", "", ""])       -> []
            _strip_trailing_empties([])                  -> []
        """
        if not lst:
            return lst
        last_idx = len(lst)
        while last_idx > 0 and lst[last_idx - 1] == "":
            last_idx -= 1
        return lst[:last_idx]
