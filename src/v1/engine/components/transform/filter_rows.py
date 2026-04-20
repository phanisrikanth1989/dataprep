"""Engine component for FilterRows (tFilterRow / tFilterRows).

Filters rows based on structured conditions or advanced Java expressions.
Matching rows go to main output; non-matching rows go to reject output.

Config keys consumed (6 total):
  conditions    (list[dict], default [])  -- filter conditions [{column, function, operator, value}]
  logical_op    (str, default "&&")       -- combine conditions: "&&" (AND) or "||" (OR)
  use_advanced  (bool, default False)     -- use advanced_cond Java expression instead of conditions
  advanced_cond (str, default "")         -- Java expression (must contain {{java}} marker)
  tstatcatcher_stats (bool, default False) -- framework
  label         (str, default "")          -- framework
"""
import logging
import re
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, ExpressionError

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Operator Map (D-05, D-06, FROW-01, FROW-02)
# ------------------------------------------------------------------
# All 15 Talend operators -- operator-function map, no AST, pure vectorized pandas.

_OPERATOR_MAP = {
    "==":           lambda col, val: col == val,
    "!=":           lambda col, val: col != val,
    ">":            lambda col, val: col > val,
    "<":            lambda col, val: col < val,
    ">=":           lambda col, val: col >= val,
    "<=":           lambda col, val: col <= val,
    "MATCHES":      lambda col, val: col.astype(str).str.fullmatch(str(val), na=False),
    "CONTAINS":     lambda col, val: col.astype(str).str.contains(str(val), regex=False, na=False),
    "NOT_CONTAINS": lambda col, val: ~col.astype(str).str.contains(str(val), regex=False, na=False),
    "STARTS_WITH":  lambda col, val: col.astype(str).str.startswith(str(val), na=False),
    "ENDS_WITH":    lambda col, val: col.astype(str).str.endswith(str(val), na=False),
    "IS_NULL":      lambda col, val: col.isna(),
    "IS_NOT_NULL":  lambda col, val: col.notna(),
    "LENGTH_LT":    lambda col, val: col.astype(str).str.len() < int(val),
    "LENGTH_GT":    lambda col, val: col.astype(str).str.len() > int(val),
}

# ------------------------------------------------------------------
# FUNCTION Pre-transform Map (D-07, FROW-03)
# ------------------------------------------------------------------

_FUNCTION_MAP = {
    "":            lambda col: col,
    "LOWER":       lambda col: col.astype(str).str.lower(),
    "UPPER":       lambda col: col.astype(str).str.upper(),
    "LOWER_FIRST": lambda col: col.astype(str).str[0].str.lower(),
    "UPPER_FIRST": lambda col: col.astype(str).str[0].str.upper(),
    "LENGTH":      lambda col: col.astype(str).str.len(),
    "TRIM":        lambda col: col.astype(str).str.strip(),
    "LTRIM":       lambda col: col.astype(str).str.lstrip(),
    "RTRIM":       lambda col: col.astype(str).str.rstrip(),
    "ABS":         lambda col: pd.to_numeric(col, errors="coerce").abs(),
}

# ------------------------------------------------------------------
# Logical Operator Normalization (Pitfall 6)
# ------------------------------------------------------------------

_LOGICAL_OP_MAP = {"&&": "AND", "||": "OR", "AND": "AND", "OR": "OR"}


# ------------------------------------------------------------------
# Module-level Helpers
# ------------------------------------------------------------------

def _apply_function(col: pd.Series, func_str: str) -> pd.Series:
    """Apply FUNCTION pre-transform to column values before operator comparison."""
    if not func_str:
        return col
    func_upper = func_str.upper().strip()
    if func_upper in _FUNCTION_MAP:
        return _FUNCTION_MAP[func_upper](col)
    # Handle LEFT(n) and RIGHT(n) with argument parsing
    left_match = re.match(r"LEFT\((\d+)\)", func_upper)
    if left_match:
        n = int(left_match.group(1))
        return col.astype(str).str[:n]
    right_match = re.match(r"RIGHT\((\d+)\)", func_upper)
    if right_match:
        n = int(right_match.group(1))
        return col.astype(str).str[-n:]
    logger.warning("Unknown FUNCTION pre-transform: %r, returning column as-is", func_str)
    return col


def _compare(col: pd.Series, operator: str, value: str) -> pd.Series:
    """Apply operator to column with type-aware coercion.

    For comparison operators (==, !=, >, <, >=, <=):
    - Attempt numeric coercion on both column and value
    - If both are numeric, compare as numbers
    - Otherwise fall back to string comparison

    For string operators (MATCHES, CONTAINS, etc.):
    - Always use string comparison

    For null operators (IS_NULL, IS_NOT_NULL):
    - No coercion needed

    Args:
        col: Column data (possibly pre-transformed by _apply_function).
        operator: One of the 15 supported operators.
        value: Comparison value from condition config.

    Returns:
        Boolean Series mask.

    Raises:
        ExpressionError: If operator is not in _OPERATOR_MAP.
    """
    if operator not in _OPERATOR_MAP:
        raise ExpressionError(f"Unsupported operator: {operator!r}")

    # Null operators -- no value needed
    if operator in ("IS_NULL", "IS_NOT_NULL"):
        return _OPERATOR_MAP[operator](col, value)

    # Comparison operators -- try numeric first (FROW-04)
    if operator in ("==", "!=", ">", "<", ">=", "<="):
        numeric_col = pd.to_numeric(col, errors="coerce")
        try:
            numeric_val = float(value)
        except (ValueError, TypeError):
            numeric_val = None
        if numeric_val is not None and numeric_col.notna().any():
            return _OPERATOR_MAP[operator](numeric_col, numeric_val)
        # Fall back to string comparison
        return _OPERATOR_MAP[operator](col.astype(str), str(value))

    # String operators -- use string values
    return _OPERATOR_MAP[operator](col, value)


# ------------------------------------------------------------------
# Component
# ------------------------------------------------------------------

@REGISTRY.register("FilterRows", "FilterRow", "tFilterRow", "tFilterRows")
class FilterRows(BaseComponent):
    """tFilterRow / tFilterRows engine implementation.

    Filters rows based on structured conditions or advanced Java expressions.
    Matching rows go to main output; non-matching rows go to reject output.

    Config keys:
        conditions: List of filter conditions [{column, function, operator, value}]
        logical_op: Combine conditions with "&&" (AND) or "||" (OR)
        use_advanced: Use advanced_cond Java expression instead of conditions
        advanced_cond: Java expression for advanced filtering
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        Raises:
            ConfigurationError: If configuration is invalid.
        """
        use_advanced = self.config.get("use_advanced", False)

        if use_advanced:
            advanced_cond = self.config.get("advanced_cond", "")
            if not advanced_cond:
                raise ConfigurationError(
                    f"[{self.id}] Missing 'advanced_cond' when use_advanced is True"
                )
        else:
            conditions = self.config.get("conditions", [])
            if not isinstance(conditions, list):
                raise ConfigurationError(
                    f"[{self.id}] 'conditions' must be a list"
                )
            for i, cond in enumerate(conditions):
                if not isinstance(cond, dict):
                    raise ConfigurationError(
                        f"[{self.id}] Condition {i} must be a dictionary"
                    )
                if "column" not in cond:
                    raise ConfigurationError(
                        f"[{self.id}] Condition {i} missing required key 'column'"
                    )
                if "operator" not in cond:
                    raise ConfigurationError(
                        f"[{self.id}] Condition {i} missing required key 'operator'"
                    )
                op = cond["operator"]
                if op not in _OPERATOR_MAP:
                    raise ConfigurationError(
                        f"[{self.id}] Condition {i} has unsupported operator: {op!r}. "
                        f"Supported: {sorted(_OPERATOR_MAP.keys())}"
                    )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Filter rows based on conditions or advanced expression.

        Args:
            input_data: Input DataFrame from upstream component.

        Returns:
            dict with 'main' (matching rows) and 'reject' (non-matching rows).
        """
        # Early return for empty input
        if input_data is None or input_data.empty:
            return {"main": input_data, "reject": None}

        use_advanced = self.config.get("use_advanced", False)

        if use_advanced:
            # Both advanced condition AND simple conditions are applied (ANDed)
            advanced_mask = self._handle_advanced(input_data)
            simple_mask = self._handle_simple(input_data)
            mask = advanced_mask & simple_mask
        else:
            mask = self._handle_simple(input_data)

        # Split into main and reject
        main_df = input_data[mask].copy()
        reject_df = input_data[~mask].copy()

        self._update_stats(len(input_data), len(main_df), len(reject_df))
        logger.info(
            f"[{self.id}] Filtered {len(input_data)} rows: "
            f"{len(main_df)} passed, {len(reject_df)} rejected"
        )

        # Schema validation on output
        output_schema = getattr(self, "output_schema", None)
        if output_schema:
            main_df = self.validate_schema(main_df, output_schema)

        return {
            "main": main_df,
            "reject": reject_df if not reject_df.empty else None,
        }

    # ------------------------------------------------------------------
    # Simple Conditions
    # ------------------------------------------------------------------

    def _handle_simple(self, df: pd.DataFrame) -> pd.Series:
        """Evaluate structured conditions and return boolean mask.

        Args:
            df: Input DataFrame.

        Returns:
            Boolean Series mask (True = row passes filter).
        """
        conditions = self.config.get("conditions", [])
        logical_op_raw = self.config.get("logical_op", "&&")
        logical_op = _LOGICAL_OP_MAP.get(logical_op_raw, "AND")

        if not conditions:
            logger.warning(f"[{self.id}] No conditions specified, passing all rows")
            return pd.Series(True, index=df.index)

        masks = []
        for cond in conditions:
            col_name = cond.get("column", "")
            func_str = cond.get("function", "")
            operator = cond.get("operator", "==")
            value = cond.get("value", "")

            if col_name not in df.columns:
                logger.warning(
                    f"[{self.id}] Column {col_name!r} not found in input, "
                    f"condition evaluates to False"
                )
                masks.append(pd.Series(False, index=df.index))
                continue

            # Apply FUNCTION pre-transform (D-07, FROW-03)
            col = _apply_function(df[col_name], func_str)

            # Apply operator with type-aware comparison (D-05, FROW-04)
            cond_mask = _compare(col, operator, value)
            masks.append(cond_mask)

        # Combine masks with logical operator
        if logical_op == "AND":
            combined = masks[0]
            for m in masks[1:]:
                combined = combined & m
        else:  # OR
            combined = masks[0]
            for m in masks[1:]:
                combined = combined | m

        return combined

    # ------------------------------------------------------------------
    # Advanced Condition (Java Bridge Delegation)
    # ------------------------------------------------------------------

    def _resolve_java_expressions(self) -> None:
        """Override to skip advanced_cond from one-time batch resolution.

        advanced_cond needs per-row evaluation via execute_tmap_preprocessing,
        not one-time resolution via execute_batch_one_time_expressions (which
        has no row binding). All other config {{java}} markers are handled by
        the parent.
        """
        advanced_cond = self.config.get("advanced_cond", "")
        # Temporarily clear so base class skips it
        if advanced_cond:
            self.config["advanced_cond"] = ""
        try:
            super()._resolve_java_expressions()
        finally:
            # Restore original value regardless
            if advanced_cond:
                self.config["advanced_cond"] = advanced_cond

    def _handle_advanced(self, df: pd.DataFrame) -> pd.Series:
        """Evaluate advanced Java expression per-row and return boolean mask.

        Uses execute_tmap_preprocessing which binds each row as
        `<input_flow_name>` (e.g. row1) so expressions like `row1.age > 10`
        work natively. Falls back to passing all rows if bridge unavailable.

        Args:
            df: Input DataFrame.

        Returns:
            Boolean Series mask (True = row passes filter).
        """
        import numpy as np

        advanced_cond = self.config.get("advanced_cond", "")
        if not advanced_cond:
            logger.warning(
                f"[{self.id}] use_advanced=True but advanced_cond is empty, "
                f"passing all rows"
            )
            return pd.Series(True, index=df.index)

        # Strip {{java}} marker if present
        expression = advanced_cond[8:] if advanced_cond.startswith("{{java}}") else advanced_cond

        if not self.java_bridge:
            logger.warning(
                f"[{self.id}] Advanced condition requires Java bridge but none "
                f"available. Passing all rows."
            )
            return pd.Series(True, index=df.index)

        # Determine main table name from input flow (e.g. "row1")
        main_table_name = self.inputs[0] if self.inputs else "row1"

        # Normalize "input_row." -> actual flow name so both styles work.
        # Talend uses the flow name (row1); users may also write input_row.
        if "input_row." in expression:
            expression = expression.replace("input_row.", f"{main_table_name}.")
            logger.debug(
                f"[{self.id}] Rewrote 'input_row' -> '{main_table_name}' in advanced_cond"
            )

        try:
            # Map pandas dtypes to engine type strings expected by bridge
            _DTYPE_MAP = {
                "int64": "int", "int32": "int", "int16": "int", "int8": "int",
                "float64": "float", "float32": "float",
                "bool": "bool",
                "datetime64[ns]": "datetime",
                "object": "str",
            }
            schema = {
                col: _DTYPE_MAP.get(str(df[col].dtype), "str")
                for col in df.columns
            }
            results = self.java_bridge.execute_tmap_preprocessing(
                df,
                {"_filter": expression},
                main_table_name=main_table_name,
                schema=schema,
            )
            per_row = results.get("_filter", np.array([]))
            if len(per_row) != len(df):
                logger.warning(
                    f"[{self.id}] Advanced condition result length mismatch "
                    f"({len(per_row)} vs {len(df)}). Passing all rows."
                )
                return pd.Series(True, index=df.index)
            # Convert to boolean: treat None/null as False
            bool_mask = pd.array(
                [bool(v) if v is not None else False for v in per_row],
                dtype="boolean",
            ).fillna(False)
            return pd.Series(bool_mask.to_numpy(dtype=bool), index=df.index)
        except Exception as e:
            raise ExpressionError(
                f"[{self.id}] Error in Java expression at advanced_cond: {e}"
            ) from e
