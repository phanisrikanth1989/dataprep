"""Engine component for UniqueRow (tUniqRow).

Separates input rows into UNIQUE (first-seen) and DUPLICATE outputs.

Config keys consumed:
  key_columns       (list[dict | str], default []) -- per-converter format:
                      [{"column": "col_name", "case_sensitive": True}, ...]
                      also accepts plain list[str] for backward compat.
  keep              (str | False, default "first") -- "first", "last", or False
  case_sensitive    (bool, default True) -- global fallback if per-column not set
  output_duplicates (bool, default True) -- emit duplicate rows to reject output
  is_reject_duplicate (bool, default True) -- count duplicates as NB_LINE_REJECT

Talend tUniqRow connector types: UNIQUE (→ main), DUPLICATE (→ reject).
Output routing: output_router maps flow type "unique" → result["main"],
"duplicate" → result["reject"].
"""
import logging
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)

def _safe_lower(series):
    """Lowercase a series safely; non-string values are returned unchanged.
    
    Avoids issues with non-string types (e.g. numbers, NaN) that would raise errors
    when calling .str.lower() directly. This is used for case-insensitive key handling.
    """
    return series.map(lambda v: v.lower() if isinstance(v, str) else v)




@REGISTRY.register("UniqueRow", "tUniqRow", "tUniqueRow", "tUnqRow")
class UniqueRow(BaseComponent):
    """tUniqRow engine implementation.

    Splits input DataFrame into unique rows (UNIQUE/main output) and
    duplicate rows (DUPLICATE/reject output).

    Per-column case sensitivity is supported via the list-of-dicts format
    emitted by the converter::

        key_columns = [{"column": "id", "case_sensitive": False}, ...]

    A plain list[str] is also accepted and uses the global ``case_sensitive``
    flag for every column.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate config container shape only (Rule 12).

        Raises:
            ConfigurationError: If ``key_columns`` is present but not a list.
        """
        key_columns = self.config.get("key_columns")
        if key_columns is not None and not isinstance(key_columns, list):
            raise ConfigurationError(
                self.id,
                f"'key_columns' must be a list, got {type(key_columns).__name__}",
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict[str, Any]:
        """Split input into unique and duplicate rows.

        Args:
            input_data: Input DataFrame (single-flow component).

        Returns:
            dict with ``'main'`` (unique rows) and ``'reject'`` (duplicate rows).
        """
        if input_data is None or (
            isinstance(input_data, pd.DataFrame) and input_data.empty
        ):
            return {"main": pd.DataFrame(), "reject": pd.DataFrame()}

        raw_keys = self.config.get("key_columns", [])
        keep = self.config.get("keep", "first")
        global_case = self.config.get("case_sensitive", True)
        output_duplicates = self.config.get("output_duplicates", True)
        is_reject_duplicate = self.config.get("is_reject_duplicate", True)
        only_once_each_dup = self.config.get("only_once_each_duplicated_key", False)

        # Normalise key_columns: converter emits list[dict]; manual config may use list[str]
        col_names: list[str] = []
        col_case: dict[str, bool] = {}
        for entry in raw_keys:
            if isinstance(entry, dict):
                col = entry.get("column", "")
                if col:
                    col_names.append(col)
                    col_case[col] = entry.get("case_sensitive", global_case)
            elif isinstance(entry, str) and entry:
                col_names.append(entry)
                col_case[entry] = global_case

        # Resolve to columns that actually exist in the DataFrame
        key_cols = [c for c in col_names if c in input_data.columns]
        if not key_cols:
            if col_names:
                logger.warning(
                    "[%s] None of key_columns %s found in DataFrame; "
                    "falling back to all columns",
                    self.id,
                    col_names,
                )
            key_cols = list(input_data.columns)
            for c in key_cols:
                col_case.setdefault(c, global_case)

        # Build case-insensitive temp columns (single copy only when required)
        work = input_data
        temp_map: dict[str, str] = {}
        for col in key_cols:
            if not col_case.get(col, True) and (
                pd.api.types.is_object_dtype(work[col]) or pd.api.types.is_string_dtype(work[col])
            ):
                if work is input_data:
                    work = input_data.copy()
                temp_col = f"__uniq_ci_{col}__"
                work[temp_col] = _safe_lower(work[col])
                temp_map[col] = temp_col

        dedup_cols = [temp_map.get(c, c) for c in key_cols]
        dup_mask = work.duplicated(subset=dedup_cols, keep=keep)

        # Use mask indexing against the original (temp-free) DataFrame
        unique_df = input_data.loc[~dup_mask].reset_index(drop=True)
        duplicate_df = (
            input_data.loc[dup_mask].reset_index(drop=True)
            if output_duplicates
            else pd.DataFrame(columns=input_data.columns)
        )

        # When only_once_each_duplicated_key=True, keep only the first duplicate
        # per key group in the reject output (suppress subsequent duplicates).
        if output_duplicates and only_once_each_dup and not duplicate_df.empty:
            if temp_map:
                dup_ci = duplicate_df.copy()
                for col, tc in temp_map.items():
                    dup_ci[tc] = _safe_lower(dup_ci[col])
                once_mask = ~dup_ci.duplicated(subset=dedup_cols, keep="first")
            else:
                once_mask = ~duplicate_df.duplicated(subset=dedup_cols, keep="first")
            duplicate_df = duplicate_df.loc[once_mask].reset_index(drop=True)

        unique_count = len(unique_df)
        dup_count = len(input_data) - unique_count

        self._update_stats(
            len(input_data),
            unique_count,
            dup_count if is_reject_duplicate else 0,
        )

        if self.global_map is not None:
            self.global_map.put(f"{self.id}_NB_UNIQUES", unique_count)
            self.global_map.put(f"{self.id}_NB_DUPLICATES", dup_count)

        logger.info("[%s] unique=%d duplicate=%d", self.id, unique_count, dup_count)
        return {"main": unique_df, "reject": duplicate_df}

