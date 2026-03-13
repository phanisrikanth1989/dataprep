"""
UniqueRow - Remove duplicate rows based on key columns.

Talend equivalent: tUniqueRow

This component removes duplicate rows from the input DataFrame based on
specified key columns, with options for case sensitivity and duplicate handling.
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...exceptions import ComponentExecutionError, ConfigurationError

logger = logging.getLogger(__name__)


class UniqueRow(BaseComponent):
    """
    Remove duplicate rows based on key columns.

    This component filters out duplicate rows from the input DataFrame,
    keeping only unique records based on the specified key columns.
    Supports case-sensitive and case-insensitive matching for string columns.

    Configuration:
        key_columns (List[str]): Columns to check for duplicates. If empty, uses all columns. Default: []
        keep (str): Which duplicates to keep - 'first', 'last', or False to drop all duplicates. Default: 'first'
        case_sensitive (bool): Whether string comparison is case sensitive. Default: True
        output_duplicates (bool): Whether to output duplicate rows. Default: True
        is_reject_duplicate (bool): Whether to treat duplicates as rejects vs separate output. Default: True

    Inputs:
        main: Input DataFrame to deduplicate

    Outputs:
        main: DataFrame with unique rows only
        reject: Duplicate rows (always present, empty DataFrame if output_duplicates=False)

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Unique rows output
        NB_LINE_REJECT: Duplicate rows (if is_reject_duplicate=True)
        {component_id}_NB_UNIQUES: Number of unique rows (custom stat)
        {component_id}_NB_DUPLICATES: Number of duplicate rows (custom stat)

    Example:
        config = {
            "key_columns": ["customer_id", "order_date"],
            "keep": "first",
            "case_sensitive": False,
            "output_duplicates": True,
            "is_reject_duplicate": True
        }
        component = UniqueRow("unique_1", config)
        result = component.execute(input_df)

    Notes:
        - When key_columns is empty, all columns are used for duplicate detection
        - Case insensitive comparison creates temporary lowercase columns for processing
        - Always returns both 'main' and 'reject' outputs for consistent flow connections
        - If output_duplicates=False, reject output will be an empty DataFrame
    """

    # Class constants
    VALID_KEEP_OPTIONS = ['first', 'last', False]
    DEFAULT_KEEP = 'first'
    DEFAULT_CASE_SENSITIVE = True
    DEFAULT_OUTPUT_DUPLICATES = True
    DEFAULT_IS_REJECT_DUPLICATE = True

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Validate key_columns if provided
        if 'key_columns' in self.config:
            key_columns = self.config['key_columns']
            if not isinstance(key_columns, list):
                errors.append("Config 'key_columns' must be a list")
            elif any(not isinstance(col, str) for col in key_columns):
                errors.append("All items in 'key_columns' must be strings")

        # Validate keep option
        if 'keep' in self.config:
            keep = self.config['keep']
            if keep not in self.VALID_KEEP_OPTIONS:
                errors.append(f"Config 'keep' must be one of {self.VALID_KEEP_OPTIONS}")

        # Validate boolean flags
        bool_configs = ['case_sensitive', 'output_duplicates', 'is_reject_duplicate']
        for config_key in bool_configs:
            if config_key in self.config:
                value = self.config[config_key]
                if not isinstance(value, bool):
                    errors.append(f"Config '{config_key}' must be a boolean")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Remove duplicate rows based on key columns.

        Args:
            input_data: Input DataFrame to deduplicate. If None or empty, returns empty result.

        Returns:
            Dictionary containing:
                - 'main': DataFrame with unique rows
                - 'reject': Duplicate rows (always present for consistent flow connections)

        Raises:
            ComponentExecutionError: If duplicate removal fails
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {
                'main': pd.DataFrame(),
                'reject': pd.DataFrame()
            }

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        try:
            # Get configuration with defaults
            key_columns = self.config.get('key_columns', [])
            keep = self.config.get('keep', self.DEFAULT_KEEP)
            case_sensitive = self.config.get('case_sensitive', self.DEFAULT_CASE_SENSITIVE)
            output_duplicates = self.config.get('output_duplicates', self.DEFAULT_OUTPUT_DUPLICATES)
            is_reject_duplicate = self.config.get('is_reject_duplicate', self.DEFAULT_IS_REJECT_DUPLICATE)

            # Core processing logic
            result = self._remove_duplicates(
                input_data, key_columns, keep, case_sensitive, output_duplicates, is_reject_duplicate
            )

            unique_df = result['unique']
            duplicate_df = result['duplicate']

            # Calculate statistics
            unique_count = len(unique_df)
            duplicate_count = len(duplicate_df) if output_duplicates else rows_in - unique_count

            # Update statistics
            if is_reject_duplicate:
                self._update_stats(rows_in, unique_count, duplicate_count)
            else:
                self._update_stats(rows_in, unique_count, 0)

            # Store additional stats in global_map
            if self.global_map:
                self.global_map.put(f"{self.id}_NB_UNIQUES", unique_count)
                self.global_map.put(f"{self.id}_NB_DUPLICATES", duplicate_count)

            logger.info(f"[{self.id}] Processing complete: "
                        f"in={rows_in}, unique={unique_count}, duplicates={duplicate_count}")

            # Return consistent output structure with both main and reject outputs
            # Also return outputs by the component's declared output names for flow mapping
            outputs = {
                'main': unique_df,
                'reject': duplicate_df if output_duplicates else pd.DataFrame()
            }

            # Also add outputs by the component's declared output flow names
            # This ensures compatibility with different flow configurations
            if hasattr(self, 'outputs') and self.outputs:
                for i, output_name in enumerate(self.outputs):
                    if i == 0:
                        outputs[output_name] = unique_df
                    elif i == 1:
                        outputs[output_name] = duplicate_df if output_duplicates else pd.DataFrame()

            return outputs

        except Exception as e:
            logger.error(f"[{self.id}] Processing failed: {str(e)}")
            raise ComponentExecutionError(self.id, f"Duplicate removal failed: {str(e)}", e) from e

    def _remove_duplicates(
        self,
        input_data: pd.DataFrame,
        key_columns: List[str],
        keep: str,
        case_sensitive: bool,
        output_duplicates: bool,
        is_reject_duplicate: bool
    ) -> Dict[str, pd.DataFrame]:
        """
        Internal method to remove duplicates from DataFrame.

        Args:
            input_data: Input DataFrame
            key_columns: Columns to check for duplicates
            keep: Which duplicates to keep ('first', 'last', or False)
            case_sensitive: Whether string comparison is case sensitive
            output_duplicates: Whether to output duplicate rows
            is_reject_duplicate: Whether to treat duplicates as rejects

        Returns:
            Dictionary with 'unique' and 'duplicate' DataFrames
        """
        # If no key columns specified, use all columns
        if not key_columns:
            key_columns = list(input_data.columns)
        else:
            # Filter to existing columns
            key_columns = [col for col in key_columns if col in input_data.columns]

        if not key_columns:
            # No valid key columns, return all data as unique
            logger.warning(f"[{self.id}] No valid key columns found: returning all rows as unique")
            return {
                'unique': input_data,
                'duplicate': pd.DataFrame()
            }

        # Create a copy for processing
        df = input_data.copy()

        # Handle case sensitivity for string columns
        temp_cols = {}
        if not case_sensitive:
            for col in key_columns:
                if df[col].dtype == 'object':
                    temp_col = f"_temp_{col}"
                    temp_cols[col] = temp_col
                    df[temp_col] = df[col].str.lower()

            # Use temporary columns for deduplication
            if temp_cols:
                temp_key_columns = [temp_cols.get(col, col) for col in key_columns]
            else:
                temp_key_columns = key_columns
        else:
            temp_key_columns = key_columns

        # Find duplicates
        duplicates_mask = df.duplicated(subset=temp_key_columns, keep=keep)

        # Split into unique and duplicate rows
        unique_df = df[~duplicates_mask].copy()
        duplicate_df = df[duplicates_mask].copy() if output_duplicates else pd.DataFrame()

        # Clean up temporary columns
        if not case_sensitive and temp_cols:
            for temp_col in temp_cols.values():
                if temp_col in unique_df.columns:
                    unique_df = unique_df.drop(columns=[temp_col])
                if temp_col in duplicate_df.columns and not duplicate_df.empty:
                    duplicate_df = duplicate_df.drop(columns=[temp_col])

        return {
            'unique': unique_df,
            'duplicate': duplicate_df
        }

    def execute(self, input_data=None) -> Dict[str, Any]:
        """
        Execute the component with enhanced flow mapping support.

        This override ensures that outputs are properly mapped to flow names
        to prevent execution stalling.
        """
        # Call parent execute method
        result = super().execute(input_data)

        # Enhanced flow mapping to ensure engine can find the data
        if result and hasattr(self, 'outputs') and self.outputs:
            # For each declared output, ensure the data is available under the flow name
            for i, output_flow_name in enumerate(self.outputs):
                if i == 0 and 'main' in result:
                    # First output gets unique data
                    result[output_flow_name] = result['main']
                elif i == 1 and 'reject' in result:
                    # Second output gets duplicate data
                    result[output_flow_name] = result['reject']

        return result
