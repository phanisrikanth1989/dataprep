"""
TUnpivotRow - Convert columns into rows by unpivoting.

Talend equivalent: tUnpivotRow

This component transforms columns into rows by unpivoting specified columns
while keeping identifier columns intact. Creates key-value pairs from the
unpivoted columns.
"""

import logging
import pandas as pd
from typing import Dict, Any, Optional, List
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class UnpivotRow(BaseComponent):
    """
    Unpivot columns into rows, creating key-value pairs.
    Equivalent to Talend's tUnpivotRow component.

    Configuration:
        row_keys (List[str]): List of columns to keep as identifiers. Required.
        pivot_key (str): Name for the new column containing original column names. Default: 'pivot_key'
        pivot_value (str): Name for the new column containing the values. Default: 'pivot_value'
        include_empty_values (bool): Whether to include rows with null/empty values. Default: True

    Inputs:
        main: Input DataFrame to unpivot

    Outputs:
        main: Unpivoted DataFrame with columns converted to rows

    Statistics:
        NB_LINE: Total rows processed (input rows)
        NB_LINE_OK: Output rows produced after unpivoting
        NB_LINE_REJECT: Always 0 (no rows are rejected)

    Example:
        config = {
            "row_keys": ["id", "name"],
            "pivot_key": "attribute",
            "pivot_value": "value",
            "include_empty_values": False
        }

    Notes:
        - Columns specified in row_keys are preserved as identifier columns
        - All other columns are unpivoted into key-value pairs
        - Output columns are reordered with pivot columns first
        - Missing columns are added with None values
    """

    # Class constants
    DEFAULT_PIVOT_KEY = 'pivot_key'
    DEFAULT_PIVOT_VALUE = 'pivot_value'
    DEFAULT_INCLUDE_EMPTY_VALUES = True

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Validate row_keys
        if 'row_keys' not in self.config:
            errors.append("Missing required config: 'row_keys'")
        else:
            row_keys = self.config['row_keys']
            if not isinstance(row_keys, list):
                errors.append("Config 'row_keys' must be a list")
            elif len(row_keys) == 0:
                errors.append("Config 'row_keys' cannot be empty")
            else:
                # Check if all row_keys are strings
                for i, key in enumerate(row_keys):
                    if not isinstance(key, str):
                        errors.append(f"Config 'row_keys[{i}]' must be a string")

        # Validate optional fields if present
        if 'pivot_key' in self.config:
            if not isinstance(self.config['pivot_key'], str):
                errors.append("Config 'pivot_key' must be a string")

        if 'pivot_value' in self.config:
            if not isinstance(self.config['pivot_value'], str):
                errors.append("Config 'pivot_value' must be a string")

        if 'include_empty_values' in self.config:
            if not isinstance(self.config['include_empty_values'], bool):
                errors.append("Config 'include_empty_values' must be boolean")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Unpivot input data based on configuration.

        Args:
            input_data: Input DataFrame to unpivot (may be None or empty)

        Returns:
            Dictionary containing:
                - 'main': Unpivoted DataFrame with columns converted to rows

        Raises:
            ValueError: If row_keys are not specified or missing from input data
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        # Get configuration with defaults
        row_keys = self.config.get('row_keys', [])
        pivot_key_column = self.config.get('pivot_key', self.DEFAULT_PIVOT_KEY)
        pivot_value_column = self.config.get('pivot_value', self.DEFAULT_PIVOT_VALUE)
        include_empty_values = self.config.get('include_empty_values', self.DEFAULT_INCLUDE_EMPTY_VALUES)

        logger.debug(f"[{self.id}] Configuration: row_keys={row_keys}, "
                     f"pivot_key='{pivot_key_column}', pivot_value='{pivot_value_column}', "
                     f"include_empty_values={include_empty_values}")

        # Validate configuration
        if not row_keys:
            error_msg = "Row keys must be specified for TUnpivotRow."
            logger.error(f"[{self.id}] {error_msg}")
            raise ValueError(error_msg)

        # Ensure row_keys are present in the input data
        missing_keys = [key for key in row_keys if key not in input_data.columns]
        if missing_keys:
            error_msg = f"Missing row keys in input data: {missing_keys}"
            logger.error(f"[{self.id}] {error_msg}")
            raise ValueError(error_msg)

        # Identify columns to unpivot
        columns_to_unpivot = [col for col in input_data.columns if col not in row_keys]
        logger.debug(f"[{self.id}] Row key columns: {row_keys}")
        logger.debug(f"[{self.id}] Columns to unpivot: {columns_to_unpivot}")

        # Perform unpivoting
        try:
            logger.debug(f"[{self.id}] Performing unpivot operation using pandas melt")

            # Create a temporary index to preserve original row order
            input_data_with_index = input_data.copy()
            input_data_with_index['_original_order'] = range(len(input_data))

            unpivoted_df = input_data_with_index.melt(
                id_vars=row_keys + ['_original_order'],
                value_vars=columns_to_unpivot,
                var_name=pivot_key_column,
                value_name=pivot_value_column,
            )

            # Sort by original row order first, then by column name to maintain input structure
            unpivoted_df = unpivoted_df.sort_values(['_original_order', pivot_key_column], ignore_index=True)

            # Remove the temporary index column
            unpivoted_df = unpivoted_df.drop('_original_order', axis=1)

            logger.debug(f"[{self.id}] After melt operation: {len(unpivoted_df)} rows")

            # Filter rows to include only those part of row_keys
            unpivoted_df = unpivoted_df[unpivoted_df[pivot_key_column].isin(columns_to_unpivot)]
            logger.debug(f"[{self.id}] After filtering: {len(unpivoted_df)} rows")

            # Reorder columns to have pivot_key and pivot_value as the first columns
            column_order = [pivot_key_column, pivot_value_column] + [col for col in unpivoted_df.columns if col not in [pivot_key_column, pivot_value_column]]
            unpivoted_df = unpivoted_df[column_order]
            logger.debug(f"[{self.id}] Reordered columns: {list(unpivoted_df.columns)}")

            # Add other columns without data population
            for col in column_order:
                if col not in unpivoted_df.columns:
                    unpivoted_df[col] = None
                    logger.debug(f"[{self.id}] Added missing column '{col}' with None values")

            # Ensure all columns from the original data are present in the output
            for col in input_data.columns:
                if col not in unpivoted_df.columns:
                    unpivoted_df[col] = None
                    logger.debug(f"[{self.id}] Added original column '{col}' with None values")

            # Handle empty values if required
            if not include_empty_values:
                before_filter = len(unpivoted_df)
                unpivoted_df = unpivoted_df.dropna(subset=[pivot_value_column])
                rows_filtered = before_filter - len(unpivoted_df)
                logger.info(f"[{self.id}] Filtered out {rows_filtered} rows with empty values")

            # Calculate statistics
            rows_out = len(unpivoted_df)
            self._update_stats(rows_in, rows_out, 0)

            logger.info(f"[{self.id}] Processing complete: "
                        f"in={rows_in}, out={rows_out}, unpivoted {len(columns_to_unpivot)} columns")

            return {'main': unpivoted_df}

        except Exception as e:
            logger.error(f"[{self.id}] Error in TUnpivotRow: {e}")
            raise

    def validate_config(self) -> bool:
        """
        Validate component configuration.

        Returns:
            bool: True if configuration is valid, False otherwise

        Note:
            This method maintains backward compatibility. The preferred method
            is _validate_config() which returns detailed error messages.
        """
        errors = self._validate_config()

        if errors:
            for error in errors:
                logger.error(f"[{self.id}] Configuration error: {error}")
            return False

        logger.debug(f"[{self.id}] Configuration validation passed")
        return True
