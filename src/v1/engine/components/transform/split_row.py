"""Engine component for SplitRow (tSplitRow).

Expands each input row into multiple output rows using a column mapping list.
Each mapping group defines one output row: keys are target column names and
values are source expressions that are evaluated against the input row.

Supported expression types:
  - Flow column reference:  ``row1.colname``  ->  input_row["colname"]
  - Quoted string literal:  ``"Jan"``         ->  "Jan"
  - Numeric literal:        ``42``            ->  42  (int)
  - Unresolved expression:  anything else     ->  returned as-is

An empty ``col_mapping`` produces an empty DataFrame.

Config keys consumed (3 total):
    col_mapping         (list[dict]) -- row-expansion group dicts
    tstatcatcher_stats  (bool, default False) -- framework
    label               (str, default "")     -- framework

Each ``col_mapping`` entry:
    A dict where each key is a target column name (str) and each value
    is a source expression string (e.g. ``"row1.id"`` or ``'"Jan"'``).

Example:
    col_mapping = [
        {"id": "row1.id", "Month": '"Jan"', "amount": "row1.Jan"},
        {"id": "row1.id", "Month": '"Feb"', "amount": "row1.Feb"},
    ]
    Input row: {id:1, Jan:100, Feb:200}
    Output rows:
        {id:1, Month:"Jan", amount:100}
        {id:1, Month:"Feb", amount:200}
"""
import logging
import re
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Regex for flow.column reference patterns: e.g. "row1.id", "input.colName"
_FLOW_COL_RE = re.compile(r'^[A-Za-z_]\w*\.([A-Za-z_]\w*)$')


# ------------------------------------------------------------------
# Module-level helper
# ------------------------------------------------------------------

def _resolve_expression(expr: str, row: dict[str, Any], input_cols: set[str]) -> Any:
    """Resolve a Talend source expression against an input row dict.

    Resolution order:
    1. ``flowname.colname`` -- if ``colname`` is a known input column, return
       the column value from ``row``.
    2. Quoted string literal (``"..."`` or ``'...'``) -- return the unquoted
       string content.
    3. Integer literal -- return as ``int``.
    4. Float literal -- return as ``float``.
    5. Fallback -- return the expression string as-is.

    Args:
        expr: Source expression string from config.
        row: Single input row as a plain dict.
        input_cols: Set of known input column names.

    Returns:
        Resolved Python value.
    """
    # 1. flow.column reference
    m = _FLOW_COL_RE.match(expr)
    if m:
        col = m.group(1)
        if col in input_cols:
            return row[col]

    # 2. Quoted string literal (double or single quotes)
    if len(expr) >= 2:
        if (expr[0] == '"' and expr[-1] == '"') or (expr[0] == "'" and expr[-1] == "'"):
            return expr[1:-1]

    # 3 & 4. Numeric literals
    try:
        return int(expr)
    except (ValueError, TypeError):
        pass
    try:
        return float(expr)
    except (ValueError, TypeError):
        pass

    # 5. Fallback
    return expr


@REGISTRY.register("SplitRow", "tSplitRow")
class SplitRow(BaseComponent):
    """tSplitRow engine implementation.

    Expands each input row into multiple output rows.  For each input row,
    one output row is produced per group in ``col_mapping``.  The output
    DataFrame has ``len(input) * len(col_mapping)`` rows.

    An empty ``col_mapping`` produces an empty DataFrame.

    Config keys:
        col_mapping: List of group dicts, each mapping target column names to
            source expressions.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        Validates structural correctness only — expression content is not
        evaluated here (context variables may not yet be resolved).

        Raises:
            ConfigurationError: If ``col_mapping`` is absent, not a list,
                or contains non-dict entries.
        """
        col_mapping = self.config.get("col_mapping")
        if col_mapping is None:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'col_mapping'"
            )
        if not isinstance(col_mapping, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'col_mapping' must be a list, "
                f"got {type(col_mapping).__name__}"
            )
        for i, entry in enumerate(col_mapping):
            if not isinstance(entry, dict):
                raise ConfigurationError(
                    f"[{self.id}] col_mapping[{i}] must be a dict, "
                    f"got {type(entry).__name__}"
                )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Expand each input row into multiple output rows per col_mapping groups.

        For each input row, one output row is produced per group in
        ``col_mapping``.  Expressions in each group are resolved against
        the current input row.

        Args:
            input_data: Input DataFrame from upstream component.

        Returns:
            dict with 'main' (expanded DataFrame) and 'reject' (always None).
        """
        col_mapping: list[dict] = self.config.get("col_mapping", [])

        # Empty mapping → empty DataFrame
        if not col_mapping:
            logger.debug(f"[{self.id}] col_mapping is empty -- returning empty DataFrame")
            self._update_stats(0, 0, 0)
            return {"main": pd.DataFrame(), "reject": None}

        if input_data is None or (isinstance(input_data, pd.DataFrame) and input_data.empty):
            self._update_stats(0, 0, 0)
            return {"main": pd.DataFrame(), "reject": None}

        input_cols: set[str] = set(input_data.columns)
        output_rows: list[dict] = []

        for _, row in input_data.iterrows():
            row_dict = row.to_dict()
            for group in col_mapping:
                new_row: dict[str, Any] = {}
                for target_col, expr in group.items():
                    new_row[target_col] = _resolve_expression(str(expr), row_dict, input_cols)
                output_rows.append(new_row)

        result_df = pd.DataFrame(output_rows) if output_rows else pd.DataFrame()

        self._update_stats(len(input_data), len(result_df), 0)
        return {"main": result_df, "reject": None}
