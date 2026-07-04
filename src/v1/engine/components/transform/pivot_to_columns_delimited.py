"""tPivotToColumnsDelimited engine component.

Groups input rows by 'groupbys' columns, pivots 'pivot_column' distinct values
into new column headers, aggregates 'aggregation_column' using the selected
function, and writes the result to a delimited file. The pivoted DataFrame is
also returned as the 'main' output for downstream components.

Supported aggregation functions: sum, count, min, max, first, last

Config keys (matching converter D-38 output):
  pivot_column          (str, required)  -- column whose distinct values become headers
  aggregation_column    (str, required)  -- column to aggregate
  aggregation_function  (str, default "sum")  -- sum/count/min/max/first/last
  groupbys              (list[str], required)  -- group-by columns (non-empty list)
  filename              (str, required)  -- output file path
  create                (bool, default True)  -- create file and parent dirs if True
  rowseparator          (str, default "\\n")  -- row delimiter (escape sequences decoded)
  fieldseparator        (str, default ";")   -- field delimiter (escape sequences decoded)
  encoding              (str, default "ISO-8859-15")  -- file encoding
  advanced_separator    (bool, default False)  -- locale formatting (not implemented)
  thousands_separator   (str, default ",")  -- thousands grouping (not implemented)
  decimal_separator     (str, default ".")  -- decimal point (not implemented)
  csv_option            (bool, default False)  -- RFC4180 quoting (not implemented)
  escape_char           (str, default '"')  -- escape character (not implemented)
  text_enclosure        (str, default '"')  -- quote character (not implemented)
  delete_emptyfile      (bool, default False)  -- skip file creation when output is empty
  tstatcatcher_stats    (bool, default False)  -- framework only
  label                 (str, default "")  -- framework only

Output GlobalMap variables:
  {id}_NB_LINE      -- input row count
  {id}_NB_LINE_OK   -- output row count (set by BaseComponent)
  {id}_NB_LINE_OUT  -- output row count (Talend file-output convention)
"""
import logging
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent, ExecutionMode
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)

# ---- Valid aggregation functions ----
_VALID_AGG_FUNCTIONS = {"sum", "count", "min", "max", "first", "last"}

# ---- Safe separator escape-sequence map (avoids unicode_escape dangers) ----
_UNESCAPE_MAP = {
    "\\r\\n": "\r\n",
    "\\n": "\n",
    "\\r": "\r",
    "\\t": "\t",
}


def _unescape_separator(sep: str) -> str:
    """Convert escaped separator string to actual character(s).

    Uses an explicit map rather than .encode().decode('unicode_escape') to avoid
    corrupting Windows paths and non-ASCII content.

    Args:
        sep: Separator string, possibly containing Talend escape sequences.

    Returns:
        Unescaped separator string.
    """
    # Try exact match first (handles "\\r\\n" as a unit before "\\r")
    if sep in _UNESCAPE_MAP:
        return _UNESCAPE_MAP[sep]
    result = sep
    for escaped, char in _UNESCAPE_MAP.items():
        result = result.replace(escaped, char)
    return result



@REGISTRY.register("PivotToColumnsDelimited", "tPivotToColumnsDelimited")
class PivotToColumnsDelimited(BaseComponent):
    """tPivotToColumnsDelimited engine implementation.

    Groups input rows by 'groupbys', pivots 'pivot_column' distinct values into
    new column headers, aggregates 'aggregation_column' using the selected
    function, and writes the result to a delimited file. The pivoted DataFrame is
    also returned as 'main' for downstream components.
    """

    # ------------------------------------------------------------------
    # Mode override -- pivot always needs the full dataset
    # ------------------------------------------------------------------

    def _select_mode(self, input_data: Optional[pd.DataFrame]) -> ExecutionMode:
        """Always use BATCH mode.

        Pivot operations require the full dataset to compute correct aggregations.
        Streaming / chunk-based execution would produce wrong per-chunk results.
        """
        return ExecutionMode.BATCH

    # ------------------------------------------------------------------
    # Configuration Validation (Rule 2: raise; Rule 12: structure only)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate structural config key presence and types.

        Raises:
            ConfigurationError: On missing or structurally invalid config.

        Note:
            Content-sensitive checks (non-empty strings, single-char delimiters,
            valid aggregation function enum) are intentionally deferred to
            _process() after context variable resolution per Rule 12.
        """
        if "pivot_column" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'pivot_column'"
            )
        if "aggregation_column" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'aggregation_column'"
            )
        groupbys = self.config.get("groupbys")
        if groupbys is None:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'groupbys'"
            )
        if not isinstance(groupbys, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'groupbys' must be a list, "
                f"got {type(groupbys).__name__}"
            )
        if "filename" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'filename'"
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Pivot input data and write to a delimited file.

        Args:
            input_data: Input DataFrame from upstream component, or None.

        Returns:
            dict with 'main' (pivoted DataFrame) and 'reject' (None).

        Raises:
            ConfigurationError: On invalid or empty resolved config values.
            FileOperationError: On file write failure.
        """
        # ---- Handle empty / None input ----
        if input_data is None or input_data.empty:
            logger.debug(f"[{self.id}] Empty input -- returning empty DataFrame")
            self._update_stats(0, 0, 0)
            if self.global_map:
                self.global_map.put_component_stat(self.id, "NB_LINE_OUT", 0)
            return {"main": pd.DataFrame(), "reject": None}

        rows_in = len(input_data)

        # ---- Read config ----
        pivot_column = self.config.get("pivot_column", "")
        aggregation_column = self.config.get("aggregation_column", "")
        aggregation_function = self.config.get("aggregation_function", "sum")
        groupbys = self.config.get("groupbys", [])
        filename = self.config.get("filename", "")
        create = self.config.get("create", True)
        fieldseparator = self.config.get("fieldseparator", ";")
        rowseparator = self.config.get("rowseparator", "\\n")
        encoding = self.config.get("encoding", "ISO-8859-15")
        delete_emptyfile = self.config.get("delete_emptyfile", False)

        # ---- Content validation (deferred from _validate_config per Rule 12) ----
        if not pivot_column:
            raise ConfigurationError(f"[{self.id}] Config 'pivot_column' is empty")
        if not aggregation_column:
            raise ConfigurationError(f"[{self.id}] Config 'aggregation_column' is empty")
        if not groupbys:
            raise ConfigurationError(f"[{self.id}] Config 'groupbys' must be a non-empty list")
        if not filename:
            raise ConfigurationError(f"[{self.id}] Config 'filename' is empty")

        # ---- Normalize separators: unescape escape sequences ----
        field_sep = _unescape_separator(fieldseparator)
        row_sep = _unescape_separator(rowseparator)

        # ---- Validate field separator length (deferred: context vars arrive here) ----
        if len(field_sep) != 1:
            raise ConfigurationError(
                f"[{self.id}] Config 'fieldseparator' must resolve to a single character, "
                f"got {len(field_sep)} chars: {field_sep!r}"
            )

        # ---- Validate aggregation function enum ----
        if aggregation_function not in _VALID_AGG_FUNCTIONS:
            raise ConfigurationError(
                f"[{self.id}] Config 'aggregation_function' must be one of "
                f"{sorted(_VALID_AGG_FUNCTIONS)}, got {aggregation_function!r}"
            )

        # ---- Capture first-appearance order of pivot column values ----
        # pd.pivot_table() sorts column headers alphabetically; Talend preserves
        # the order of first occurrence in the input data.  Capture that order
        # before pivoting so we can restore it afterwards.
        seen: dict = {}
        for v in input_data[pivot_column]:
            if v not in seen:
                seen[v] = None
        pivot_value_order = list(seen.keys())

        # ---- Perform pivot ----
        logger.info(
            f"[{self.id}] Pivoting {rows_in} rows: "
            f"pivot={pivot_column!r}, agg={aggregation_column!r}/{aggregation_function}, "
            f"groupby={groupbys}"
        )
        try:
            pivoted = input_data.pivot_table(
                index=groupbys,
                columns=pivot_column,
                values=aggregation_column,
                aggfunc=aggregation_function,
                sort=False,
            ).reset_index()
        except Exception as exc:
            raise ConfigurationError(
                f"[{self.id}] Pivot operation failed: {exc}"
            ) from exc

        # ---- Flatten MultiIndex columns (pivot_table may produce one) ----
        if isinstance(pivoted.columns, pd.MultiIndex):
            pivoted.columns = [
                str(c[-1]) if c[0] == aggregation_column else str(c[0])
                for c in pivoted.columns
            ]
        pivoted.columns.name = None

        # ---- Restore first-appearance column order (Talend compatibility) ----
        # pivot_table() sorts columns alphabetically; reorder to match the
        # order pivot values were first seen in the input data.
        gb_cols_ordered = [c for c in groupbys if c in pivoted.columns]
        val_cols_ordered = [
            str(v) for v in pivot_value_order if str(v) in pivoted.columns
        ]
        # Any pivot values not in pivot_value_order (shouldn't happen, safety net)
        extra_cols = [
            c for c in pivoted.columns
            if c not in gb_cols_ordered and c not in val_cols_ordered
        ]
        pivoted = pivoted[gb_cols_ordered + val_cols_ordered + extra_cols]

        # ---- Replace NaN with empty string for sparse pivot cells ----
        # Operate only on the value columns (not group-by columns) to avoid
        # corrupting string group-by values.
        gb_cols = set(groupbys) & set(pivoted.columns)
        value_cols = [c for c in pivoted.columns if c not in gb_cols]
        for col in value_cols:
            series = pivoted[col]
            if pd.api.types.is_float_dtype(series):
                # Use int representation for whole-number cells (Talend convention)
                non_null = series.dropna()
                if len(non_null) > 0 and (non_null % 1 == 0).all():
                    pivoted[col] = series.apply(
                        lambda x: int(x) if pd.notna(x) else ""
                    )
                else:
                    pivoted[col] = series.fillna("")
            else:
                pivoted[col] = series.fillna("")

        rows_out = len(pivoted)

        # ---- Write to file ----
        if create:
            out_path = Path(filename)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            if delete_emptyfile and rows_out == 0:
                logger.info(
                    f"[{self.id}] delete_emptyfile=True with no output rows -- skipping write"
                )
            else:
                logger.info(f"[{self.id}] Writing {rows_out} rows to '{filename}'")
                try:
                    pivoted.to_csv(
                        filename,
                        sep=field_sep,
                        lineterminator=row_sep,
                        encoding=encoding,
                        index=False,
                    )
                except Exception as exc:
                    raise FileOperationError(
                        f"[{self.id}] Failed to write '{filename}': {exc}"
                    ) from exc

        # ---- Stats ----
        self._update_stats(rows_in, rows_out, 0)
        if self.global_map:
            self.global_map.put_component_stat(self.id, "NB_LINE_OUT", rows_out)

        logger.info(f"[{self.id}] Complete: in={rows_in}, out={rows_out}")
        return {"main": pivoted, "reject": None}
