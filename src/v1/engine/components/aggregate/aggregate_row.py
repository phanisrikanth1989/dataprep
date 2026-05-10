"""Engine component for AggregateRow (tAggregateRow).

Groups input rows by specified columns and applies aggregation functions.

Config keys consumed (8 total):
  groupbys                (list[dict], default [])   -- group-by column mappings [{output_column, input_column}]
  operations              (list[dict], default [])   -- aggregation operations [{output_column, function, input_column, ignore_null}]
  list_delimiter          (str, default ",")          -- delimiter for list/list_object aggregation
  use_financial_precision (bool, default True)        -- use Decimal arithmetic for numeric aggregations
  check_type_overflow     (bool, default False)       -- deferred
  check_ulp               (bool, default False)       -- deferred
  tstatcatcher_stats      (bool, default False)       -- framework
  label                   (str, default "")           -- framework
"""
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import numpy as np
import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Supported aggregation functions (allowlist for config validation)
# ------------------------------------------------------------------
_SUPPORTED_FUNCTIONS = frozenset({
    "count", "min", "max", "avg", "sum", "first", "last",
    "list", "list_object", "count_distinct", "std",
    "population_std_dev", "median", "variance", "union",
})


# ------------------------------------------------------------------
# Decimal precision helpers
# ------------------------------------------------------------------

def _to_decimal(val: Any) -> Optional[Decimal]:
    """Convert a value to Decimal, returning None for NaN/None."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError):
        return None


def _decimal_sum(series: pd.Series) -> Decimal:
    """Sum a series using Decimal arithmetic, skipping NaN."""
    total = Decimal("0")
    for val in series:
        d = _to_decimal(val)
        if d is not None:
            total += d
    return total


def _decimal_mean(series: pd.Series) -> Optional[Decimal]:
    """Mean of a series using Decimal arithmetic, skipping NaN."""
    total = Decimal("0")
    count = 0
    for val in series:
        d = _to_decimal(val)
        if d is not None:
            total += d
            count += 1
    if count == 0:
        return None
    return total / Decimal(str(count))


def _decimal_std(series: pd.Series, ddof: int = 1) -> Optional[Decimal]:
    """Standard deviation using Decimal arithmetic.

    Args:
        series: Input series.
        ddof: Delta degrees of freedom. 1 for sample std, 0 for population std.

    Returns:
        Decimal std or None if insufficient data.
    """
    mean = _decimal_mean(series)
    if mean is None:
        return None
    sq_diffs = []
    for val in series:
        d = _to_decimal(val)
        if d is not None:
            sq_diffs.append((d - mean) ** 2)
    n = len(sq_diffs)
    if n <= ddof:
        return None
    variance = sum(sq_diffs, Decimal("0")) / Decimal(str(n - ddof))
    # Decimal sqrt via float conversion (sufficient precision for ETL)
    return Decimal(str(float(variance) ** 0.5))


# ------------------------------------------------------------------
# Aggregation function builder
# ------------------------------------------------------------------

def _build_agg_func(
    func_name: str,
    ignore_null: bool,
    list_delimiter: str,
    use_financial_precision: bool,
) -> Any:
    """Return a callable (or string) for pandas groupby aggregation.

    Args:
        func_name: Canonical aggregation function name.
        ignore_null: When True, skip NaN in aggregation. When False, propagate NaN.
        list_delimiter: Delimiter for list/list_object/union functions.
        use_financial_precision: When True, use Decimal arithmetic for numeric ops.

    Returns:
        A callable suitable for pd.NamedAgg aggfunc parameter.
    """
    skipna = ignore_null

    if func_name == "count":
        # WR-10 verified WRONG per RESEARCH.md: count = non-null count regardless of
        # ignore_null. Matches SQL convention and Talend docs ("calculates the
        # number of rows" -- no null-inclusion clause). DO NOT change to "size".
        return "count"

    if func_name == "count_distinct":
        return lambda x: x.nunique()

    if func_name == "first":
        return "first"

    if func_name == "last":
        return "last"

    # BUG-AGG-001 (Phase 14-02): pandas Series.astype(str) does NOT coerce
    # NaN/None to a string -- it leaves them as floats, so str.join() crashes
    # ("sequence item N: expected str instance, float found"). The
    # ignore_null=False branches of list / list_object / union were therefore
    # broken for any null-bearing input. Fix at source: fillna("null") before
    # astype(str), matching Java's String.valueOf(null) == "null" semantics
    # (Talend ArrayList.toString() over a list with a null element writes
    # "null" in that position).
    if func_name == "list":
        # list: collect all values (preserving duplicates) and join with delimiter
        if ignore_null:
            return lambda x: list_delimiter.join(x.dropna().astype(str))
        return lambda x: list_delimiter.join(x.fillna("null").astype(str))

    if func_name == "list_object":
        # Talend list(object) calls ArrayList.toString() which produces:
        #   [elem1, elem2, elem3]  -- no quotes around elements, comma-space separated.
        # Returning a Python list serialises as ['elem1', 'elem2'] with quotes,
        # which does not match Talend output. We replicate ArrayList.toString() directly.
        # list_delimiter does NOT apply per Talaxie tAggregateRow_messages.properties:
        #   LIST_DELIMITER.NAME=Delimiter (only for list operation)
        if ignore_null:
            return lambda x: "[" + ", ".join(x.dropna().astype(str)) + "]"
        return lambda x: "[" + ", ".join(x.fillna("null").astype(str)) + "]"

    if func_name == "union":
        # CR-05-bis: distinct + sorted + joined. Talend union aggregator collects
        # unique values; Python equivalent: sorted(set(...)).
        # WR-10 verified WRONG per RESEARCH.md: count = non-null count regardless of
        # ignore_null. Matches SQL convention and Talend docs ("calculates the
        # number of rows" -- no null-inclusion clause). DO NOT change to "size".
        if ignore_null:
            return lambda x: list_delimiter.join(sorted(set(x.dropna().astype(str))))
        return lambda x: list_delimiter.join(sorted(set(x.fillna("null").astype(str))))

    if func_name == "median":
        if use_financial_precision:
            # WR-09 fix: Decimal median is genuinely complex; fall back to float median
            # but warn once per execute() so operators are aware of precision loss.
            # A mutable sentinel list is used so the closure can suppress duplicates
            # even when pandas calls the lambda multiple times (once per group).
            _warned = [False]

            def _median_warn(x, _w=_warned):
                if not _w[0]:
                    logger.warning(
                        "median with use_financial_precision: Decimal median not directly "
                        "supported; falling back to float median (precision loss may occur "
                        "for very large or very precise Decimal values)"
                    )
                    _w[0] = True
                return x.dropna().astype(float).median() if skipna else x.astype(float).median()

            return _median_warn
        return lambda x: x.median(skipna=skipna)

    # Numeric aggregation functions
    if use_financial_precision:
        if func_name == "sum":
            return lambda x: _decimal_sum(x) if skipna else (
                None if x.isna().any() else _decimal_sum(x)
            )
        if func_name == "avg":
            return lambda x: _decimal_mean(x) if skipna else (
                None if x.isna().any() else _decimal_mean(x)
            )
        if func_name == "std":
            return lambda x: _decimal_std(x, ddof=1) if skipna else (
                None if x.isna().any() else _decimal_std(x, ddof=1)
            )
        if func_name == "population_std_dev":
            return lambda x: _decimal_std(x, ddof=0) if skipna else (
                None if x.isna().any() else _decimal_std(x, ddof=0)
            )
        if func_name == "variance":
            # Decimal variance
            def _dec_var(x):
                mean = _decimal_mean(x)
                if mean is None:
                    return None
                sq_diffs = []
                for val in x:
                    d = _to_decimal(val)
                    if d is not None:
                        sq_diffs.append((d - mean) ** 2)
                n = len(sq_diffs)
                if n <= 1:
                    return None
                return sum(sq_diffs, Decimal("0")) / Decimal(str(n - 1))
            return lambda x: _dec_var(x) if skipna else (
                None if x.isna().any() else _dec_var(x)
            )
        if func_name == "min":
            def _dec_min(x):
                vals = [_to_decimal(v) for v in x]
                vals = [v for v in vals if v is not None]
                return min(vals) if vals else None
            return lambda x: _dec_min(x) if skipna else (
                None if x.isna().any() else _dec_min(x)
            )
        if func_name == "max":
            def _dec_max(x):
                vals = [_to_decimal(v) for v in x]
                vals = [v for v in vals if v is not None]
                return max(vals) if vals else None
            return lambda x: _dec_max(x) if skipna else (
                None if x.isna().any() else _dec_max(x)
            )

    # Non-financial-precision numeric functions
    if func_name == "sum":
        return lambda x: x.sum(skipna=skipna)
    if func_name == "avg":
        return lambda x: x.mean(skipna=skipna)
    if func_name == "min":
        return lambda x: x.min(skipna=skipna)
    if func_name == "max":
        return lambda x: x.max(skipna=skipna)
    if func_name == "std":
        return lambda x: x.std(ddof=1, skipna=skipna)
    if func_name == "population_std_dev":
        return lambda x: x.std(ddof=0, skipna=skipna)
    if func_name == "variance":
        return lambda x: x.var(ddof=1, skipna=skipna)

    # Fallback -- unknown function, default to sum
    logger.warning("Unknown aggregation function '%s', defaulting to sum", func_name)
    return lambda x: x.sum(skipna=skipna)


# ------------------------------------------------------------------
# Component
# ------------------------------------------------------------------

@REGISTRY.register("AggregateRow", "tAggregateRow")
class AggregateRow(BaseComponent):
    """tAggregateRow engine implementation.

    Groups input rows by specified columns and applies aggregation
    functions (count, sum, avg, min, max, first, last, list, std,
    population_std_dev, median, variance, count_distinct, union).

    Config keys:
        groupbys: Group-by column mappings [{output_column, input_column}].
        operations: Aggregation operations [{output_column, function, input_column, ignore_null}].
        list_delimiter: Delimiter for list/list_object aggregation.
        use_financial_precision: Use Decimal arithmetic for numeric aggregations.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        Raises:
            ConfigurationError: If configuration is invalid.
        """
        operations = self.config.get("operations", [])
        if not isinstance(operations, list):
            raise ConfigurationError(
                f"[{self.id}] 'operations' must be a list, got {type(operations).__name__}"
            )

        for i, op in enumerate(operations):
            if not isinstance(op, dict):
                raise ConfigurationError(
                    f"[{self.id}] Operation {i} must be a dict, got {type(op).__name__}"
                )
            if "function" not in op:
                raise ConfigurationError(
                    f"[{self.id}] Operation {i} missing required key 'function'"
                )
            if "input_column" not in op:
                raise ConfigurationError(
                    f"[{self.id}] Operation {i} missing required key 'input_column'"
                )
            func = op["function"].lower() if isinstance(op["function"], str) else op["function"]
            if func not in _SUPPORTED_FUNCTIONS:
                raise ConfigurationError(
                    f"[{self.id}] Operation {i} has unsupported function '{func}'. "
                    f"Supported: {sorted(_SUPPORTED_FUNCTIONS)}"
                )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Aggregate input data by group columns and operations.

        Args:
            input_data: Input DataFrame from upstream component.

        Returns:
            dict with 'main' (aggregated DataFrame) and 'reject' (None).
        """
        if input_data is None or input_data.empty:
            return {"main": pd.DataFrame(), "reject": None}

        # Read config (resolved by BaseComponent)
        groupbys = self.config.get("groupbys", [])
        operations = self.config.get("operations", [])
        list_delimiter = self.config.get("list_delimiter", ",")
        use_financial_precision = self.config.get("use_financial_precision", True)

        group_input_cols = [g["input_column"] for g in groupbys]
        group_output_cols = [g["output_column"] for g in groupbys]

        logger.info(
            f"[{self.id}] Aggregating {len(input_data)} rows with "
            f"{len(operations)} operations, {len(groupbys)} group-by columns"
        )

        # Build aggregation specs
        agg_specs = {}
        op_output_order = []
        for op in operations:
            output_col = op.get("output_column", op["input_column"])
            input_col = op["input_column"]
            func = op["function"].lower() if isinstance(op["function"], str) else op["function"]
            ignore_null = op.get("ignore_null", True)

            agg_func = _build_agg_func(func, ignore_null, list_delimiter, use_financial_precision)
            agg_specs[output_col] = (input_col, agg_func)
            op_output_order.append(output_col)

        # Perform aggregation
        if group_input_cols:
            result = self._grouped_aggregation(
                input_data, group_input_cols, agg_specs
            )
            # Rename groupby columns from input_column to output_column
            rename_map = {
                g["input_column"]: g["output_column"]
                for g in groupbys
                if g["input_column"] != g["output_column"]
            }
            if rename_map:
                result = result.rename(columns=rename_map)
        else:
            result = self._global_aggregation(input_data, agg_specs)

        # Ensure column ordering: group outputs first, then operation outputs
        ordered_cols = []
        for col in group_output_cols:
            if col in result.columns and col not in ordered_cols:
                ordered_cols.append(col)
        for col in op_output_order:
            if col in result.columns and col not in ordered_cols:
                ordered_cols.append(col)
        # Add any remaining columns (shouldn't happen, but safety)
        for col in result.columns:
            if col not in ordered_cols:
                ordered_cols.append(col)
        result = result[ordered_cols]

        # NOTE: Do NOT call self.validate_schema() here.
        # BaseComponent.execute() runs _apply_output_schema_validation (step 7c)
        # automatically after _process() returns. Calling it here violates the
        # lifecycle contract and causes double-validation (CR-02 fix).

        # Stats
        rows_in = len(input_data)
        rows_out = len(result)
        self._update_stats(rows_in, rows_out, 0)

        logger.debug(
            f"[{self.id}] Result: {rows_out} rows, columns: {list(result.columns)}"
        )

        return {"main": result, "reject": None}

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _grouped_aggregation(
        df: pd.DataFrame,
        group_cols: list[str],
        agg_specs: dict[str, tuple],
    ) -> pd.DataFrame:
        """Perform single-pass grouped aggregation.

        Args:
            df: Input DataFrame.
            group_cols: Columns to group by.
            agg_specs: Mapping of output_col -> (input_col, agg_func).

        Returns:
            Aggregated DataFrame with group columns and operation results.
        """
        named_aggs = {
            out_col: pd.NamedAgg(column=spec[0], aggfunc=spec[1])
            for out_col, spec in agg_specs.items()
        }
        # WR-11 fix: sort=False preserves first-seen group order (Talend LinkedHashMap
        # insertion order behavior). sort=True was alphabetizing output by group key.
        return (
            df.groupby(group_cols, sort=False)
            .agg(**named_aggs)
            .reset_index()
        )

    @staticmethod
    def _global_aggregation(
        df: pd.DataFrame,
        agg_specs: dict[str, tuple],
    ) -> pd.DataFrame:
        """Aggregate entire DataFrame without grouping (single result row).

        Args:
            df: Input DataFrame.
            agg_specs: Mapping of output_col -> (input_col, agg_func).

        Returns:
            Single-row DataFrame with aggregation results.
        """
        result_row = {}
        for out_col, (in_col, agg_func) in agg_specs.items():
            if callable(agg_func):
                result_row[out_col] = agg_func(df[in_col])
            else:
                # String agg func name (e.g. "count", "first", "last")
                result_row[out_col] = getattr(df[in_col], agg_func)()
        return pd.DataFrame([result_row])
