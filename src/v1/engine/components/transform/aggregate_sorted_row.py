"""
tAggregateSortedRow - Aggregates sorted rows using various functions.

Talend equivalent: tAggregateSortedRow
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from decimal import Decimal

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)

class AggregateSortedRow(BaseComponent):
    """
    Aggregates sorted rows using various aggregation functions.

    Performs grouping and aggregation operations on input data similar to SQL GROUP BY
    with support for multiple aggregation functions including sum, count, min, max,
    avg, count_distinct, first, last, list, and concatenate.

    Configuration:
        group_bys (list): List of column names to group by. Also supports GROUPBYS key.
        operations (list): List of aggregation operation dictionaries. Also supports OPERATIONS key.
        Each operation dict contains:
            - input_column (str): Source column name
            - output_column (str): Target column name
            - function (str): Aggregation function (sum, count, min, max, avg, etc).
            - delimiter (str): Delimiter for concatenate function. Default: ','
        die_on_error (bool): Whether to fail on errors. Default: False
        row_count (str): Number of rows to process (optional)
        connection_format (str): Connection format. Default: 'row'

    Inputs:
        main: Primary input DataFrame to aggregate

    Outputs:
        main: Aggregated DataFrame with grouped results

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully aggregated
        NB_LINE_REJECT: Rows rejected (always 0)

    Example configuration:
        {
            "group_bys": ["customer_id", "product_category"],
            "operations": [
                {
                    "input_column": "amount",
                    "output_column": "total_amount",
                    "function": "sum"
                },
                {
                    "input_column": "order_id",
                    "output_column": "order_count",
                    "function": "count"
                }
            ]
        }

    Notes:
        - Supports Decimal columns for precise financial calculations
        - Maintains all original columns in output by joining back missing columns
        - Empty group_bys aggregates entire dataset into single row
        - Supports both 'column' and 'input_column' keys for backward compatibility
    """

    def _validate_config(self) -> List[str]:
        """Validate component configuration."""
        errors = []

        # Check for required configuration - support both formats
        group_bys = self.config.get('group_bys') or self.config.get('GROUPBYS')
        operations = self.config.get('operations') or self.config.get('OPERATIONS')

        if group_bys is None:
            errors.append("Missing required config: 'group_bys' or 'GROUPBYS'")
        elif not isinstance(group_bys, list):
            errors.append("Config 'group_bys' must be a list")

        if operations is None:
            errors.append("Missing required config: 'operations' or 'OPERATIONS'")
        elif not isinstance(operations, list):
            errors.append("Config 'operations' must be a list")
        elif len(operations) == 0:
            errors.append("Config 'operations' cannot be empty")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process input data and perform aggregation.

        Args:
            input_data: Input DataFrame to aggregate. If None or empty, returns empty result.

        Returns:
            Dictionary containing:
                - 'main': Aggregated DataFrame with grouped results
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        try:
            # Get configuration
            group_bys = self.config.get('group_bys', [])
            operations = self.config.get('operations', [])

            # Validate configuration
            if not group_bys:
                raise ValueError("GROUPBYS configuration is required.")
            if not operations:
                raise ValueError("OPERATIONS configuration is required.")

            # Validate group_bys are all strings (column names)
            if not all(isinstance(col, str) for col in group_bys):
                logger.error(f"[{self.id}] group_bys must be a list of column names (strings). Got: {group_bys}")
                if self.config.get('die_on_error', False):
                    raise ValueError(f"group_bys must be a list of column names (strings). Got: {group_bys}")
                return {'main': input_data}

            # Normalize operations to support both 'column' and 'input_column' keys
            norm_ops = []
            for op in operations:
                if not isinstance(op, dict):
                    logger.error(f"[{self.id}] Invalid operation: {op}")
                    if self.config.get('die_on_error', False):
                        raise ValueError(f"Invalid operation configuration: {op}")
                    return {'main': input_data}
                # Support both key styles
                input_col = op.get('input_column') or op.get('column')
                output_col = op.get('output_column') or op.get('column')
                function = op.get('function', 'sum').lower()
                norm_ops.append({'input_column': input_col, 'output_column': output_col, 'function': function, 'delimiter': op.get('delimiter', ',')})

            # Perform aggregation
            if not group_bys:
                result_df = self._aggregate_all(input_data, norm_ops)
            else:
                result_df = self._aggregate_grouped(input_data, group_bys, norm_ops)

            # NEW BEHAVIOR: Only output group by columns and operation output columns
            # All other columns should be empty/null
            operation_output_columns = {op['output_column'] for op in norm_ops}

            # Identify required columns (group + operations)
            required_columns = set(group_bys) | operation_output_columns

            # Add all original columns but set non-required ones to None
            expected_columns = list(input_data.columns)
            for col in expected_columns:
                if col not in result_df.columns:
                    if col in required_columns:
                        # This shouldn't happen, but handle gracefully
                        logger.warning(f"[{self.id}] Required column '{col}' missing from result")
                        result_df[col] = None
                    else:
                        # Non-required column - set to empty/null
                        result_df[col] = None

            # Reorder columns to match original input order
            result_df = result_df[[col for col in expected_columns if col in result_df.columns] +
                                  [col for col in result_df.columns if col not in expected_columns]]

            rows_out = len(result_df)
            self._update_stats(rows_in, rows_out, 0)
            logger.info(f"[{self.id}] Processing complete: in={rows_in}, out={rows_out}, rejected=0, "
                         f"populated_columns={list(required_columns)}")

            return {'main': result_df}

        except Exception as e:
            logger.error(f"[{self.id}] Processing failed: {e}")
            if self.config.get('die_on_error', False):
                raise
            return {'main': input_data}

    def _is_decimal_column(self, series: pd.Series) -> bool:
        """Check if pandas Series contains Decimal values."""
        if len(series) == 0:
            return False
        for val in series:
            if pd.notna(val):
                return isinstance(val, Decimal)
        return False

    def _aggregate_all(self, df: pd.DataFrame, operations: List[Dict]) -> pd.DataFrame:
        """
        Aggregate entire DataFrame into single row.

        Args:
            df: Input DataFrame
            operations: List of aggregation operations

        Returns:
            Single-row DataFrame with aggregated values
        """
        result = {}
        for op in operations:
            input_col = op['input_column']
            output_col = op['output_column']
            function = op['function']
            if input_col and input_col in df.columns:
                result[output_col] = self._apply_agg_function(df[input_col], function, op)
            elif function == 'count':
                result[output_col] = len(df)
        return pd.DataFrame([result])

    def _aggregate_grouped(self, df: pd.DataFrame, group_bys: List[str], operations: List[Dict]) -> pd.DataFrame:
        """
        Aggregate DataFrame by groups.

        Args:
            df: Input DataFrame
            group_bys: List of column names to group by
            operations: List of aggregation operations

        Returns:
            Grouped and aggregated DataFrame
        """
        valid_group_by = [col for col in group_bys if col in df.columns]
        if not valid_group_by:
            logger.warning(f"[{self.id}] No valid group by columns found")
            return self._aggregate_all(df, operations)

        agg_dict = {}
        rename_dict = {}
        custom_aggs = []
        for op in operations:
            input_col = op['input_column']
            output_col = op['output_column']
            function = op['function']
            if not input_col and function == 'count':
                custom_aggs.append(('count', output_col, None, op))
                continue
            if not input_col or input_col not in df.columns:
                logger.warning(f"[{self.id}] Column '{input_col}' not found in DataFrame")
                continue

            if function == 'sum':
                if self._is_decimal_column(df[input_col]):
                    custom_aggs.append(('decimal_sum', output_col, input_col, op))
                else:
                    if input_col not in agg_dict:
                        agg_dict[input_col] = []
                    agg_dict[input_col].append('sum')
                    # FIX: Handle same input/output column names
                    if input_col == output_col:
                        # When input and output names are same, use the column directly
                        rename_dict[input_col] = output_col
                    else:
                        # When different, use the generated column name
                        rename_dict[f"{input_col}_sum"] = output_col
            elif function in ['mean', 'min', 'max', 'std', 'var', 'median']:
                if input_col not in agg_dict:
                    agg_dict[input_col] = []
                agg_dict[input_col].append(function)
                # FIX: Handle same input/output column names
                if input_col == output_col:
                    # When input and output names are same, use the column directly
                    rename_dict[input_col] = output_col
                else:
                    # When different, use the generated column name
                    rename_dict[f"{input_col}_{function}"] = output_col
            elif function == 'avg':
                if input_col not in agg_dict:
                    agg_dict[input_col] = []
                agg_dict[input_col].append('mean')
                if input_col == output_col:
                    rename_dict[input_col] = output_col
                else:
                    rename_dict[f"{input_col}_mean"] = output_col
            elif function == 'count':
                if input_col not in agg_dict:
                    agg_dict[input_col] = []
                agg_dict[input_col].append('count')
                if input_col == output_col:
                    rename_dict[input_col] = output_col
                else:
                    rename_dict[f"{input_col}_count"] = output_col
            elif function == 'count_distinct':
                if input_col not in agg_dict:
                    agg_dict[input_col] = []
                agg_dict[input_col].append('nunique')
                if input_col == output_col:
                    rename_dict[input_col] = output_col
                else:
                    rename_dict[f"{input_col}_nunique"] = output_col
            elif function in ['first', 'last']:
                if input_col not in agg_dict:
                    agg_dict[input_col] = []
                agg_dict[input_col].append(function)
                if input_col == output_col:
                    rename_dict[input_col] = output_col
                else:
                    rename_dict[f"{input_col}_{function}"] = output_col
            elif function == 'list':
                custom_aggs.append(('list', output_col, input_col, op))
            elif function in ['concat', 'concatenate']:
                custom_aggs.append(('concat', output_col, input_col, op))
            else:
                logger.warning(f"[{self.id}] Unknown aggregation function: {function}")

        # Perform groupby aggregation
        if agg_dict:
            grouped = df.groupby(valid_group_by, as_index=False).agg(agg_dict)

            # COMPLETE FIX: Handle MultiIndex columns correctly for same input/output names
            if any(isinstance(col, tuple) for col in grouped.columns):
                new_columns = []
                for col in grouped.columns:
                    if isinstance(col, tuple):
                        col_name = col[0]
                        func_name = col[1]

                        # Find the corresponding operation for this column/function combination
                        target_output_col = None
                        for op in operations:
                            if op['input_column'] == col_name and op['function'] == func_name:
                                target_output_col = op['output_column']
                                break

                        # Use the target output column name
                        if target_output_col:
                            new_columns.append(target_output_col)
                        else:
                            # Fallback to generated name
                            new_columns.append('_'.join(str(c) for c in col if c))
                    else:
                        # Keep group by columns as is
                        new_columns.append(col)

                # Apply the new column names directly (no renaming needed)
                grouped.columns = new_columns
            else:
                # No MultiIndex, apply standard renaming
                grouped = grouped.rename(columns=rename_dict)
        else:
            grouped = df[valid_group_by].drop_duplicates()

        # Handle custom aggregations
        if custom_aggs:
            for agg_type, output_col, input_col, op in custom_aggs:
                if agg_type == 'decimal_sum':
                    sum_series = df.groupby(valid_group_by)[input_col].apply(lambda x: sum(x.dropna(), Decimal('0')))
                    sum_df = sum_series.reset_index()
                    sum_df.columns = list(valid_group_by) + [output_col]
                    grouped = grouped.merge(sum_df, on=valid_group_by, how='left')
                elif agg_type == 'count':
                    count_df = df.groupby(valid_group_by).size().reset_index(name=output_col)
                    grouped = grouped.merge(count_df, on=valid_group_by, how='left')
                elif agg_type == 'list':
                    grouped = grouped.merge(df.groupby(valid_group_by)[input_col].apply(list).reset_index(name=output_col),
                                            on=valid_group_by, how='left')
                elif agg_type == 'concat':
                    delimiter = op.get('delimiter', ',')
                    concat_df = df.groupby(valid_group_by)[input_col].apply(lambda x: delimiter.join(x.astype(str))).reset_index(name=output_col)
                    grouped = grouped.merge(concat_df, on=valid_group_by, how='left')
        return grouped

    def _apply_agg_function(self, series: pd.Series, function: str, op: Dict) -> Any:
        """
        Apply aggregation function to pandas Series.

        Args:
            series: Input pandas Series
            function: Aggregation function name
            op: Operation configuration dict

        Returns:
            Aggregated value
        """
        if function == 'sum':
            if len(series) > 0 and isinstance(series.iloc[0], Decimal):
                return sum(series.dropna(), Decimal('0'))
            return series.sum()
        elif function in ['avg', 'mean']:
            return series.mean()
        elif function == 'min':
            return series.min()
        elif function == 'max':
            return series.max()
        elif function == 'count':
            return series.count()
        elif function == 'count_distinct':
            return series.nunique()
        elif function == 'first':
            return series.iloc[0] if len(series) > 0 else None
        elif function == 'last':
            return series.iloc[-1] if len(series) > 0 else None
        elif function in ['std', 'stddev']:
            return series.std()
        elif function in ['var', 'variance']:
            return series.var()
        elif function == 'median':
            return series.median()
        elif function == 'list':
            return series.tolist()
        elif function in ['concat', 'concatenate']:
            delimiter = op.get('delimiter', ',')
            return delimiter.join(series.astype(str))
        else:
            return series.sum()  # Default to sum
