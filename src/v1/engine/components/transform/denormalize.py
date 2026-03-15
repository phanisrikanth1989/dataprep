"""
Denormalize component - Consolidates rows by grouping key columns and concatenating denormalize columns.

Talend equivalent: tDenormalize
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...exceptions import ConfigurationError, DataValidationError, ComponentExecutionError

logger = logging.getLogger(__name__)


class Denormalize(BaseComponent):
    """
    Consolidates rows by grouping key columns and concatenating denormalize columns.
    Equivalent to Talend's tDenormalize component.

    The component works by:
    1. Identifying key columns (columns NOT in denormalize_columns list)
    2. Grouping rows by key columns
    3. Concatenating values of denormalize columns using specified delimiters
    4. Producing one row per unique key combination

    Configuration:
        denormalize_columns (list): List of column configurations with:
            - input_column (str): Column name to denormalize
            - delimiter (str): Delimiter to use for concatenation (resolved from context). Default: ","
            - merge (bool): Whether to merge values (always true for denormalize)
        null_as_empty (bool): Whether to treat null values as empty strings. Default: False
        connection_format (str): Connection format (usually "row"). Default: "row"

    Inputs:
        main: Primary input DataFrame with rows to be denormalized

    Outputs:
        main: Denormalized DataFrame with grouped key columns and concatenated denormalize columns

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully denormalized
        NB_LINE_REJECT: Rows rejected (always 0 for this component)

    Example configuration:
        {
            "denormalize_columns": [
                {
                    "input_column": "product_name",
                    "delimiter": "; "
                },
                {
                    "input_column": "quantity",
                    "delimiter": ", "
                }
            ],
            "null_as_empty": True
        }
    """

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # denormalize_columns is optional - if not provided, pass through data
        denormalize_columns = self.config.get('denormalize_columns', [])

        if denormalize_columns:
            # If provided, validate structure
            if not isinstance(denormalize_columns, list):
                errors.append("Config 'denormalize_columns' must be a list")
            else:
                for i, col_config in enumerate(denormalize_columns):
                    if not isinstance(col_config, dict):
                        errors.append(f"Config 'denormalize_columns[{i}]' must be a dict")
                        continue

                    if 'input_column' not in col_config:
                        errors.append(f"Config 'denormalize_columns[{i}]' missing required 'input_column'")
                    elif not isinstance(col_config['input_column'], str):
                        errors.append(f"Config 'denormalize_columns[{i}].input_column' must be a string")

                    if 'delimiter' in col_config and not isinstance(col_config['delimiter'], str):
                        errors.append(f"Config 'denormalize_columns[{i}].delimiter' must be a string")

        # Validate optional boolean fields
        null_as_empty = self.config.get('null_as_empty', False)
        if not isinstance(null_as_empty, bool):
            errors.append("Config 'null_as_empty' must be a boolean")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Perform the denormalization process.

        Consolidates rows by grouping key columns and concatenating values
        of denormalize columns using specified delimiters.

        Args:
            input_data: Input DataFrame to process. If None or empty, returns empty result.

        Returns:
            Dictionary containing:
                - 'main': Denormalized DataFrame with grouped rows
                - 'stats': Execution statistics

        Raises:
            ConfigurationError: If configuration validation fails
            DataValidationError: If denormalize columns are missing from input
            ComponentExecutionError: If denormalization processing fails

        Example:
            result = self._process(input_df)
            denormalized_df = result['main']
        """
        # Validate configuration first
        config_errors = self._validate_config()
        if config_errors:
            error_msg = f"Configuration validation failed: {'; '.join(config_errors)}"
            logger.error(f"[{self.id}] {error_msg}")
            raise ConfigurationError(error_msg)

        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        # Extract configuration
        denormalize_columns = self.config.get('denormalize_columns', [])
        null_as_empty = self.config.get('null_as_empty', False)

        logger.debug(f"[{self.id}] Denormalize columns config: {denormalize_columns}")

        # Validate configuration - if no columns specified, pass through
        if not denormalize_columns:
            logger.warning(f"[{self.id}] No denormalize_columns configured, passing data through")
            self._update_stats(rows_in, rows_in, 0)
            logger.info(f"[{self.id}] Processing complete: in={rows_in}, out={rows_in}, rejected=0")
            return {'main': input_data.copy()}

        # Extract denormalize column names
        denorm_col_names = [col['input_column'] for col in denormalize_columns]

        # Validate that denormalize columns exist in input
        missing_cols = [col for col in denorm_col_names if col not in input_data.columns]
        if missing_cols:
            error_msg = f"Denormalize columns not found in input: {missing_cols}"
            logger.error(f"[{self.id}] {error_msg}")
            raise DataValidationError(error_msg)

        # Identify key columns (all columns NOT in denormalize list)
        key_columns = [col for col in input_data.columns if col not in denorm_col_names]

        if not key_columns:
            error_msg = "No key columns found. All columns cannot be denormalized."
            logger.error(f"[{self.id}] {error_msg}")
            raise DataValidationError(error_msg)

        logger.debug(f"[{self.id}] Key columns: {key_columns}")
        logger.debug(f"[{self.id}] Denormalize columns: {denorm_col_names}")

        try:
            # Build aggregation dictionary for denormalize columns
            aggregation_dict = {}

            for col_config in denormalize_columns:
                col_name = col_config['input_column']
                delimiter = col_config.get('delimiter', ',')

                # Resolve context variables in delimiter
                if self.context_manager:
                    delimiter = self.context_manager.resolve_string(delimiter)

                logger.debug(f"[{self.id}] Column {col_name} using delimiter '{delimiter}'")

                # Create aggregation function that handles nulls properly
                def make_concat_func(delim):
                    def concat_func(series):
                        if null_as_empty:
                            # Convert nulls to empty strings
                            values = [str(val) if pd.notnull(val) else '' for val in series]
                        else:
                            # Keep nulls as they are, convert others to string
                            values = [str(val) if pd.notnull(val) else None for val in series]
                            # Filter out None values
                            values = [val for val in values if val is not None]

                        # Join non-empty values
                        result = delim.join(values) if values else ''
                        return result
                    return concat_func

                aggregation_dict[col_name] = make_concat_func(delimiter)

            # For key columns, take the first value (they should be the same within each group)
            for key_col in key_columns:
                aggregation_dict[key_col] = 'first'

            # Perform groupby and aggregation
            logger.debug(f"[{self.id}] Grouping by {key_columns}")

            if len(key_columns) == 1:
                # Single key column
                denormalized_df = input_data.groupby(key_columns[0], as_index=False).agg(aggregation_dict)
            else:
                # Multiple key columns
                denormalized_df = input_data.groupby(key_columns, as_index=False).agg(aggregation_dict)

            # Ensure column order matches original input
            output_columns = key_columns + denorm_col_names
            denormalized_df = denormalized_df[output_columns]

            rows_out = len(denormalized_df)
            logger.debug(f"[{self.id}] Produced {rows_out} rows from {rows_in} input rows")

            # Update statistics and log completion
            self._update_stats(rows_in, rows_out, 0)
            logger.info(f"[{self.id}] Processing complete: in={rows_in}, out={rows_out}, rejected=0")

            return {'main': denormalized_df}

        except Exception as e:
            logger.error(f"[{self.id}] Denormalization failed: {e}")
            self._update_stats(rows_in, 0, rows_in)
            raise ComponentExecutionError(self.id, f"Denormalization failed: {e}", e) from e
