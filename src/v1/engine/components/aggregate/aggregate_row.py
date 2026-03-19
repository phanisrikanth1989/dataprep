"""
AggregateRow - Aggregate data rows with group by and various functions.

Talend equivalent: tAggregateRow
"""
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class AggregateRow(BaseComponent):
    """
    Aggregate rows with group by and various aggregation functions.

    Supports grouping by multiple columns and applying various aggregation
    functions like sum, count, average, min, max, etc. Handles Decimal
    precision for financial calculations and supports custom aggregations.

    Configuration:
        group_by (List[str]): Columns to group by. Default: []
        operations (List[Dict]): Aggregation operations to perform. Default: []
            Each operation dict contains:
                - input_column (str): Source column name
                - output_column (str): Target column name (defaults to input_column)
                - function (str): Aggregation function (sum, count, avg, min, max, etc.)
                - delimiter (str): For concat operations. Default: ","

    Inputs:
        main: Input DataFrame to aggregate

    Outputs:
        main: Aggregated DataFrame with grouped results

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully aggregated
        NB_LINE_REJECT: Rejected rows (always 0)

Example configuration:
        {
            "group_by": ["department", "region"],
            "operations": [
                {
                    "input_column": "amount",
                    "output_column": "total_amount",
                    "function": "sum"
                },
                {
                    "input_column": "employee_id",
                    "output_column": "employee_count",
                    "function": "count_distinct"
                }
            ]
        }

    Notes:
        - Preserves Decimal precision for financial calculations
        - Supports custom concatenation with configurable delimiters
        - Missing group_by columns are filtered out automatically
        - Returns single row aggregate if no group_by specified
    """

    # Class constants
    DEFAULT_OPERATIONS = []
    DEFAULT_GROUP_BY = []
    DEFAULT_DELIMITER = ","

    SUPPORTED_FUNCTIONS = [
        'sum', 'count', 'count_distinct', 'avg', 'mean', 'min', 'max',
        'first', 'last', 'std', 'stddev', 'var', 'variance', 'median',
        'list', 'concat', 'concatenate'
    ]

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Validate group_by
        group_by = self.config.get('group_by', self.DEFAULT_GROUP_BY)
        if not isinstance(group_by, list):
            errors.append("Config 'group_by' must be a list")

        # Validate operations
        operations = self.config.get('operations', self.DEFAULT_OPERATIONS)
        if not isinstance(operations, list):
            errors.append("Config 'operations' must be a list")
        else:
            for i, op in enumerate(operations):
                if not isinstance(op, dict):
                    errors.append(f"Operation {i} must be a dictionary")
                    continue

                function = op.get('function', 'sum').lower()
                if function not in self.SUPPORTED_FUNCTIONS:
                    errors.append(f"Operation {i}: Unknown function '{function}'. "
                                f"Supported: {', '.join(self.SUPPORTED_FUNCTIONS)}")

                # Warn about missing input_column for non-count operations
                if function != 'count' and not op.get('input_column'):
                    errors.append(f"Operation {i}: Missing 'input_column' for function '{function}'")

        return errors

    def _process(self,input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Perform aggregation operations on input data.

        Args:
            input_data: Input DataFrame to aggregate

        Returns:
            Dictionary containing:
                - 'main': Aggregated DataFrame
                - 'stats': Execution statistics
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        # Log input details
        logger.info(f"[{self.id}] Input shape: {input_data.shape}")
        logger.info(f"[{self.id}] Input columns: {input_data.columns.tolist()}")

        # Add diagnostic logging for sum operations
        operations = self.config.get('operations', self.DEFAULT_OPERATIONS)
        sum_operations = [op for op in operations if op.get('function', '').lower() == 'sum']
        if sum_operations:
            logger.info(f"[{self.id}] Found {len(sum_operations)} sum operations. Diagnosing...")
            for i, op in enumerate(sum_operations):
                input_col = op.get('input_column')
                if input_col and input_col in input_data.columns:
                    logger.info(f"[{self.id}] Sum operation {i+1}: column '{input_col}'")
                    logger.info(f"[{self.id}] Data type: {input_data[input_col].dtype}")
                    logger.info(f"[{self.id}] Sample values: {input_data[input_col].head(5).tolist()}")
                    logger.info(f"[{self.id}] Non-null values: {input_data[input_col].count()}")

                    # Test if values can be summed directly
                    try:
                        test_sum = input_data[input_col].sum()
                        logger.info(f"[{self.id}] Direct sum test: {test_sum}")
                    except Exception as e:
                        logger.error(f"[{self.id}] Direct sum test failed: {str(e)}")

        try:
            # Get configuration with defaults
            group_by = self.config.get('group_by', self.DEFAULT_GROUP_BY)

            # Log configuration
            logger.info(f"[{self.id}] Group by columns: {group_by}")
            logger.info(f"[{self.id}] Operations: {operations}")

            # Perform aggregation
            if not group_by:
                result_df = self._aggregate_all(input_data, operations)
            else:
                result_df = self._aggregate_grouped(input_data, group_by, operations)

            # Final verification for sum columns
            if sum_operations:
                logger.info(f"[{self.id}] ===== SUM OPERATIONS FINAL VERIFICATION =====")
                for op in sum_operations:
                    output_col = op.get('output_column', op.get('input_column'))
                    if output_col in result_df.columns:
                        values = result_df[output_col].tolist()
                        logger.info(f"[{self.id}] Sum column '{output_col}': {values}")
                        logger.info(f"[{self.id}] Sum column '{output_col}' non-null count: {result_df[output_col].count()}")
                    else:
                        logger.error(f"[{self.id}] Sum column '{output_col}' MISSING from final result!")

            # Ensure all columns present in output (Talend-like behavior)
            result_df = self._ensure_output_columns(result_df, input_data, group_by)

            # Calculate statistics
            rows_out = len(result_df)
            self._update_stats(rows_in, rows_out, 0)

            # Log completion
            logger.info(f"[{self.id}] Processing complete: "
                f"in={rows_in}, out={rows_out}, rejected=0")
            logger.info(f"[{self.id}] Output shape: {result_df.shape}")
            logger.info(f"[{self.id}] Output columns: {result_df.columns.tolist()}")

            return {'main': result_df}

        except Exception as e:
            logger.error(f"[{self.id}] Aggregation failed: {str(e)}")
            from ...base_component import ComponentExecutionError
            raise ComponentExecutionError(self.id,f"Aggregation failed: {str(e)}", e) from e

    def _aggregate_all(self,df: pd.DataFrame,operations: List[Dict]) -> pd.DataFrame:
        """
        Aggregate all rows without grouping.

        Args:
            df: Input DataFrame
            operations: List of aggregation operations

        Returns:
            Single-row DataFrame with aggregated results
        """
        result = {}

        for op in operations:
            input_col = op.get('input_column')
            output_col = op.get('output_column', input_col)
            function = op.get('function', 'sum').lower()

            if input_col and input_col in df.columns:
                result[output_col] = self._apply_agg_function(df[input_col],function,op)
            elif function == 'count':
                # Count all rows
                result[output_col] = len(df)

        return pd.DataFrame([result])

    def _ensure_output_columns(self,result_df: pd.DataFrame,input_df: pd.DataFrame,
                               group_by: List[str]) -> pd.DataFrame:
        """
        Ensure all operation columns are present in output and all input columns are included.
        Columns not in operations or group_by will have empty/null data.

        Args:
            result_df: Current result DataFrame with aggregation results
            input_df: Original input DataFrame
            group_by: Group by columns

        Returns:
            DataFrame with all operation columns populated and all input columns present
        """
        operations = self.config.get('operations', self.DEFAULT_OPERATIONS)
        valid_group_by = [col for col in group_by if col in input_df.columns]

        logger.info(f"[{self.id}] Ensuring output columns - "
                    f"Current result columns: {result_df.columns.tolist()}")

        # Track all operation output columns that should have computed values
        operation_output_columns = set()
        operation_input_columns = set()
        for op in operations:
            output_col = op.get('output_column', op.get('input_column'))
            input_col = op.get('input_column')
            if output_col:
                operation_output_columns.add(output_col)
            if input_col:
                operation_input_columns.add(input_col)

        logger.info(f"[{self.id}] Expected operation output columns: {list(operation_output_columns)}")

        # Determine which columns should have meaningful data vs empty data
        meaningful_columns = (set(valid_group_by) | operation_output_columns| operation_input_columns)

        # Verify all operation columns exist and have data
        for col in operation_output_columns:
            if col not in result_df.columns:
                logger.error(f"[{self.id}] MISSING operation column '{col}' from aggregation result!")
                result_df[col] = None
            else:
                non_null_count = result_df[col].count()
                if non_null_count == 0:
                    logger.error(f"[{self.id}] Operation column '{col}' exists but has no values!")
                else:
                    logger.info(f"[{self.id}] ✓ Operation column '{col}' has {non_null_count} values")

        # Add missing input columns with appropriate data handling
        for col in input_df.columns:
            if col not in result_df.columns:
                if col in meaningful_columns:
                    # This column is used in operations or grouping - add representative values
                    if valid_group_by and col in operation_input_columns:
                        try:
                            first_values = (input_df.groupby(valid_group_by)[col].first().reset_index())
                            result_df = result_df.merge(first_values,on=valid_group_by,how='left')
                            logger.info(f"[{self.id}] Added operation input column '{col}' with representative values")
                        except Exception as e:
                            logger.warning(f"[{self.id}] Could not add column '{col}': {str(e)}")
                            result_df[col] = None
                else:
                    # Group by column should already be present, but add if missing
                    if col in valid_group_by:
                        logger.warning(f"[{self.id}] Group by column '{col}' missing - "
                                       f"this should not happen")
                        result_df[col] = None
            else:
                # This column is NOT used in operations or grouping - set to empty/null
                result_df[col] = None
                logger.info(f"[{self.id}] Added non-operation column '{col}' with empty data (not in operations or group_by)")

        # Reorder columns: group by columns first, then input columns, then operation columns
        final_columns = []

        # Add group by columns first
        for col in valid_group_by:
            if col in result_df.columns:
                final_columns.append(col)

        # Add other input columns (maintain original order)
        for col in input_df.columns:
            if col in result_df.columns and col not in final_columns:
                final_columns.append(col)

        # Add operation columns that aren't in input
        for col in operation_output_columns:
            if col in result_df.columns and col not in final_columns:
                final_columns.append(col)

        # Add any remaining columns
        for col in result_df.columns:
            if col not in final_columns:
                final_columns.append(col)

        result_df = result_df[final_columns]

        logger.info(f"[{self.id}] Final output columns: {final_columns}")
        logger.info(f"[{self.id}] Final result shape: {result_df.shape}")

        # Final verification of all operations
        for i, op in enumerate(operations):
            output_col = op.get('output_column', op.get('input_column'))
            function = op.get('function', '').lower()

            if output_col and output_col in result_df.columns:
                values = result_df[output_col].tolist()
                non_null_count = result_df[output_col].count()
                logger.info(f"[{self.id}] FINAL CHECK - Operation {i+1} ({function}): '{output_col}' = {values} ({non_null_count} values)")
            else:
                logger.error(f"[{self.id}] FINAL CHECK - Operation {i+1} ({function}): '{output_col}' MISSING!")

        return result_df

    def _is_decimal_column(self, series: pd.Series) -> bool:
        """
        Check if a series contains Decimal objects.

        Args:
            series: Pandas Series to check

        Returns:
            True if series contains Decimal objects
        """
        if len(series) == 0:
            return False
        # Check first non-null value
        for val in series:
            if pd.notna(val):
                return isinstance(val, Decimal)
        return False

    def _apply_agg_function(self, series: pd.Series, function: str, op: Dict) -> Any:
        """
        Apply aggregation function to a series.

        Args:
            series: Pandas Series to aggregate
            function: Aggregation function name
            op: Operation configuration dictionary

        Returns:
            Aggregated value
        """
        if function == 'sum':
            # Special handling for Decimal columns to preserve precision
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
            delimiter = op.get('delimiter', self.DEFAULT_DELIMITER)
            return delimiter.join(series.astype(str))
        else:
            return series.sum()  # Default to sum

    def _aggregate_grouped(self, df: pd.DataFrame, group_by: List[str],
                           operations: List[Dict]) -> pd.DataFrame:
        """
        Aggregate rows with grouping - operation results populate input columns directly.

        Args:
            df: Input DataFrame
            group_by: List of columns to group by
            operations: List of aggregation operations

        Returns:
            Aggregated DataFrame with grouped results in original columns
        """
        # Filter group_by columns that exist
        valid_group_by = [col for col in group_by if col in df.columns]

        if not valid_group_by:
            logger.warning(f"[{self.id}] No valid group by columns found")
            return self._aggregate_all(df, operations)

        logger.info(f"[{self.id}] Starting aggregation with {len(operations)} operations")
        logger.info(f"[{self.id}] Group by columns: {valid_group_by}")

        # Start with grouped data (just the groups)
        result_df = df[valid_group_by].drop_duplicates().reset_index(drop=True)
        logger.info(f"[{self.id}] Base result shape: {result_df.shape}, columns: {result_df.columns.tolist()}")

        # Process each operation individually - populate results into input columns
        for i, op in enumerate(operations):
            input_col = op.get('input_column')
            # Use input_column as output_column unless specifically overridden
            output_col = op.get('output_column', input_col)
            function = op.get('function', 'sum').lower()

            logger.info(f"[{self.id}] Processing operation {i+1}: '{input_col}' -> '{output_col}' ({function})")

            # Skip if no input column for non-count operations
            if not input_col and function != 'count':
                logger.warning(f"[{self.id}] Skipping operation {i}: no input column for {function}")
                continue

        # Skip if input column doesn't exist (except for count)
            if input_col and input_col not in df.columns:
                logger.warning(f"[{self.id}] Skipping operation {i}: column '{input_col}' not found")
                continue

            try:
                # Process each operation type
                if function == 'sum':
                    agg_result = df.groupby(valid_group_by)[input_col].sum().reset_index()
                    # Keep original column name for the aggregated values
                    target_col = input_col

                elif function == 'count':
                    if input_col:
                        agg_result = df.groupby(valid_group_by)[input_col].count().reset_index()
                        target_col = input_col
                    else:
                        # Count rows in each group - use output_col if specified
                        agg_result = df.groupby(valid_group_by).size().reset_index(name=output_col)
                        target_col = output_col

                elif function == 'count_distinct':
                    agg_result = df.groupby(valid_group_by)[input_col].nunique().reset_index()
                    target_col = input_col

                elif function in ['avg', 'mean']:
                    agg_result = df.groupby(valid_group_by)[input_col].mean().reset_index()
                    target_col = input_col

                elif function == 'min':
                    agg_result = df.groupby(valid_group_by)[input_col].min().reset_index()
                    target_col = input_col

                elif function == 'max':
                    agg_result = df.groupby(valid_group_by)[input_col].max().reset_index()
                    target_col = input_col

                elif function in ['std', 'stddev']:
                    agg_result = df.groupby(valid_group_by)[input_col].std().reset_index()
                    target_col = input_col

                elif function in ['var', 'variance']:
                    agg_result = df.groupby(valid_group_by)[input_col].var().reset_index()
                    target_col = input_col
                
                elif function == 'median':
                    agg_result = df.groupby(valid_group_by)[input_col].median().reset_index()
                    target_col = input_col

                elif function == 'first':
                    agg_result = df.groupby(valid_group_by)[input_col].first().reset_index()
                    target_col = input_col

                elif function == 'last':
                    agg_result = df.groupby(valid_group_by)[input_col].last().reset_index()
                    target_col = input_col

                elif function == 'list':
                    agg_result = df.groupby(valid_group_by)[input_col].apply(list).reset_index()
                    target_col = input_col

                elif function in ['concat', 'concatenate']:
                    delimiter = op.get('delimiter', self.DEFAULT_DELIMITER)
                    agg_result = df.groupby(valid_group_by)[input_col].apply(
                        lambda x: delimiter.join(x.astype(str))
                    ).reset_index()
                    target_col = input_col

                else:
                    # Default to sum for unknown functions
                    logger.warning(f"[{self.id}] Unknown function '{function}', defaulting to sum")
                    agg_result = df.groupby(valid_group_by)[input_col].sum().reset_index()
                    target_col = input_col

                # Merge the aggregation result into the main result
                result_df = result_df.merge(agg_result, on=valid_group_by, how='left')

                # Verify the column was added
                if target_col in result_df.columns:
                    values = result_df[target_col].tolist()
                    logger.info(f"[{self.id}] ✓ Added operation column '{target_col}': {values}")
                else:
                    logger.error(f"[{self.id}] ✗ Failed to add operation column '{target_col}'")

            except Exception as e:
                logger.error(f"[{self.id}] Error processing operation {i+1}: {str(e)}")
                # Add empty column to ensure it exists
                target_col = input_col if input_col else output_col
                result_df[target_col] = None

        logger.info(f"[{self.id}] Completed all operations. Final result shape: {result_df.shape}")
        logger.info(f"[{self.id}] Final result columns: {result_df.columns.tolist()}")

        return result_df
        