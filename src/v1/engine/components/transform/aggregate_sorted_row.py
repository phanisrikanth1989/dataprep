"""Engine component for AggregateSortedRow (tAggregateSortedRow).

Functionally identical to tAggregateRow -- groups input rows by specified columns and
applies aggregation functions. The difference from Talend's perspective is that
tAggregateSortedRow assumes pre-sorted input for O(1) streaming (Talend JVM).  In
Python/pandas, groupby handles sorted input transparently, so the implementation
delegates to the same helpers used by AggregateRow.

Config keys consumed (5 total):
  groupbys          (list[dict], default [])  -- [{output_column, input_column}]
  operations        (list[dict], default [])  -- [{output_column, function, input_column, ignore_null}]
  list_delimiter    (str, default ",")         -- delimiter for list/list_object/union aggregation
  use_financial_precision (bool, default True) -- Decimal arithmetic for numeric aggregations
  row_count         (str, default "")          -- expression-capable row limit (not yet enforced)
  tstatcatcher_stats (bool, default False)     -- framework
  label             (str, default "")          -- framework
"""
import logging
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError
# Re-use the helpers that AggregateRow uses -- identical semantics.
from ..aggregate.aggregate_row import _SUPPORTED_FUNCTIONS, _build_agg_func

logger = logging.getLogger(__name__)


@REGISTRY.register("AggregateSortedRow", "tAggregateSortedRow")
class AggregateSortedRow(BaseComponent):
    """tAggregateSortedRow engine implementation.

    Delegates to the same aggregation helpers as AggregateRow.  The
    tAggregateSortedRow Talend component is identical in semantics to
    tAggregateRow; the only difference is Talend's JVM-side streaming
    optimisation for pre-sorted input.  pandas groupby handles sorted
    input transparently, so no special code path is needed here.

    Config keys:
        groupbys: Group-by column mappings [{output_column, input_column}].
        operations: Aggregation operations [{output_column, function, input_column, ignore_null}].
        list_delimiter: Delimiter for list/list_object/union aggregation.
        use_financial_precision: Use Decimal arithmetic for numeric aggregations.
        row_count: Expression-capable row limit (not yet enforced by engine).
    """

    # ------------------------------------------------------------------
    # Configuration validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate structural config correctness.

        Checks key presence and container shape only.  Content checks
        (empty operations list, unknown function names, missing columns)
        are deferred to _process() per Rule 12, because any of these
        fields may hold a ${context.X} reference.

        Raises:
            ConfigurationError: If config keys have wrong container types.
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

        groupbys = self.config.get("groupbys", [])
        if not isinstance(groupbys, list):
            raise ConfigurationError(
                f"[{self.id}] 'groupbys' must be a list, got {type(groupbys).__name__}"
            )

    # ------------------------------------------------------------------
    # Core processing
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

        # Read config (fully resolved by BaseComponent before _process runs)
        groupbys = self.config.get("groupbys", [])
        operations = self.config.get("operations", [])
        list_delimiter = self.config.get("list_delimiter", ",")
        use_financial_precision = self.config.get("use_financial_precision", True)

        # Content checks deferred here per Rule 12
        if not isinstance(operations, list) or len(operations) == 0:
            raise ConfigurationError(f"[{self.id}] 'operations' must be a non-empty list")

        for i, op in enumerate(operations):
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

        group_input_cols = [g["input_column"] for g in groupbys]
        group_output_cols = [g["output_column"] for g in groupbys]

        logger.info(
            f"[{self.id}] Aggregating {len(input_data)} rows, "
            f"{len(operations)} operations, {len(groupbys)} group-by columns"
        )

        # Build aggregation specs (output_col -> (input_col, agg_func))
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
            result = self._grouped_aggregation(input_data, group_input_cols, agg_specs)
            rename_map = {
                g["input_column"]: g["output_column"]
                for g in groupbys
                if g["input_column"] != g["output_column"]
            }
            if rename_map:
                result = result.rename(columns=rename_map)
        else:
            result = self._global_aggregation(input_data, agg_specs)

        # Column ordering: group outputs first, then operation outputs
        ordered_cols = []
        for col in group_output_cols:
            if col in result.columns and col not in ordered_cols:
                ordered_cols.append(col)
        for col in op_output_order:
            if col in result.columns and col not in ordered_cols:
                ordered_cols.append(col)
        for col in result.columns:
            if col not in ordered_cols:
                ordered_cols.append(col)
        result = result[ordered_cols]

        rows_in = len(input_data)
        rows_out = len(result)
        self._update_stats(rows_in, rows_out, 0)

        logger.debug(f"[{self.id}] Result: {rows_out} rows, columns: {list(result.columns)}")
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
        """Single-pass grouped aggregation using pd.NamedAgg.

        sort=False preserves first-seen group order, matching Talend's
        LinkedHashMap insertion-order behaviour.

        Args:
            df: Input DataFrame.
            group_cols: Columns to group by (input column names).
            agg_specs: {output_col: (input_col, agg_func)}.

        Returns:
            Aggregated DataFrame with group columns + operation outputs.
        """
        named_aggs = {
            out_col: pd.NamedAgg(column=spec[0], aggfunc=spec[1])
            for out_col, spec in agg_specs.items()
        }
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
            agg_specs: {output_col: (input_col, agg_func)}.

        Returns:
            Single-row DataFrame with aggregation results.
        """
        result_row = {}
        for out_col, (in_col, agg_func) in agg_specs.items():
            if callable(agg_func):
                result_row[out_col] = agg_func(df[in_col])
            else:
                result_row[out_col] = getattr(df[in_col], agg_func)()
        return pd.DataFrame([result_row])
