"""
FilterColumns - Select or remove specific columns from the data flow.

Talend equivalent: tFilterColumns

This component filters columns from the input DataFrame based on include/exclude mode.
Supports column selection by name with flexible include or exclude operations.
Preserves row data while modifying the column structure of the flow.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...exceptions import ConfigurationError, ComponentExecutionError

logger = logging.getLogger(__name__)


class FilterColumns(BaseComponent):
    """
    Select or remove specific columns from the data flow.

    This component provides column filtering capabilities equivalent to Talend's tFilterColumns.
    It can operate in two modes: include mode (keep only specified columns) or exclude mode
    (remove specified columns). The component preserves all row data while modifying the
    column structure of the DataFrame.

    Configuration:
        mode (str): Filter mode - 'include' or 'exclude'. Default: 'include'
        columns (List[str]): List of column names to include or exclude. Default: []
        keep_row_order (bool): Preserve row order (currently not used). Default: True

    Inputs:
        main: Input DataFrame to filter columns from

    Outputs:
        main: Filtered DataFrame with selected/remaining columns

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Successfully processed rows
        NB_LINE_REJECT: Rejected rows (0 for this component)
        NB_COLUMNS_IN: Number of input columns (custom statistic)
        NB_COLUMNS_OUT: Number of output columns (custom statistic)

    Example:
        # Include mode - keep only specified columns
        config = {
            "mode": "include",
            "columns": ["name", "age", "email"]
        }

        # Exclude mode - remove specified columns
        config = {
            "mode": "exclude",
            "columns": ["temp_col", "debug_info"]
        }

    Notes:
        - Missing columns in include mode are logged as warnings but don't cause failure
        - If no valid columns remain after filtering, returns empty DataFrame
        - Custom statistics track column count changes in global map
        - Preserves column order as specified in include mode
    """

    # Class constants for default values
    DEFAULT_MODE = 'include'
    DEFAULT_COLUMNS = []
    DEFAULT_KEEP_ROW_ORDER = True
    VALID_MODES = ['include', 'exclude']

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Validate mode parameter
        if 'mode' in self.config:
            mode = self.config['mode']
            if not isinstance(mode, str):
                errors.append("Config 'mode' must be a string")
            elif mode not in self.VALID_MODES:
                errors.append(f"Config 'mode' must be one of {self.VALID_MODES}, got '{mode}'")

        # Validate columns parameter
        if 'columns' in self.config:
            columns = self.config['columns']
            if not isinstance(columns, list):
                errors.append("Config 'columns' must be a list")
            else:
                for i, col in enumerate(columns):
                    if not isinstance(col, str):
                        errors.append(f"Config 'columns[{i}]' must be a string, got {type(col).__name__}")

        # Validate keep_row_order parameter
        if 'keep_row_order' in self.config:
            keep_row_order = self.config['keep_row_order']
            if not isinstance(keep_row_order, bool):
                errors.append("Config 'keep_row_order' must be boolean")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Filter columns based on configuration.

        Processes the input DataFrame to include or exclude specified columns based on
        the configured mode. Handles missing columns gracefully and provides detailed
        logging of the filtering operation.

        Args:
            input_data: Input DataFrame to filter columns from. If None or empty,
                        returns empty DataFrame.

        Returns:
            Dictionary containing:
                'main': Filtered DataFrame with selected columns

        Raises:
            ComponentExecutionError: If column filtering operation fails
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        # Get configuration with defaults
        mode = self.config.get('mode', self.DEFAULT_MODE)
        columns = self.config.get('columns', self.DEFAULT_COLUMNS)
        keep_row_order = self.config.get('keep_row_order', self.DEFAULT_KEEP_ROW_ORDER)

        total_rows = len(input_data)
        logger.info(f"[{self.id}] Processing started: {total_rows} rows, mode='{mode}'")
        logger.debug(f"[{self.id}] Configuration: columns={columns}, keep_row_order={keep_row_order}")

        try:
            # Validate columns exist
            available_columns = list(input_data.columns)
            logger.debug(f"[{self.id}] Available columns: {available_columns}")

            if mode == 'include':
                # Keep only specified columns
                columns_to_keep = []
                missing_columns = []

                for col in columns:
                    if col in available_columns:
                        columns_to_keep.append(col)
                    else:
                        missing_columns.append(col)

                if missing_columns:
                    logger.warning(f"[{self.id}] Columns not found: {missing_columns}")

                if not columns_to_keep:
                    logger.warning(f"[{self.id}] No valid columns to keep, returning empty DataFrame")
                    self._update_stats(total_rows, 0, total_rows)
                    return {'main': pd.DataFrame()}

                logger.debug(f"[{self.id}] Include mode: keeping columns {columns_to_keep}")
                # Select columns in specified order
                result_df = input_data[columns_to_keep].copy()

            else:  # exclude mode
                # Remove specified columns
                columns_to_remove = [col for col in columns if col in available_columns]
                columns_to_keep = [col for col in available_columns if col not in columns]

                if not columns_to_keep:
                    logger.warning(f"[{self.id}] All columns excluded, returning empty DataFrame")
                    self._update_stats(total_rows, 0, total_rows)
                    return {'main': pd.DataFrame()}

                logger.debug(f"[{self.id}] Exclude mode: removing columns {columns_to_remove}, keeping {columns_to_keep}")
                result_df = input_data[columns_to_keep].copy()

            # Log column filtering results
            logger.info(f"[{self.id}] Column filtering complete: "
                        f"input={len(available_columns)} columns, "
                        f"output={len(result_df.columns)} columns")

            # Update statistics
            self._update_stats(total_rows, total_rows, 0)

            # Store column info in global map (preserve existing custom behavior)
            if self.global_map:
                self.global_map.put(f"{self.id}_NB_COLUMNS_IN", len(available_columns))
                self.global_map.put(f"{self.id}_NB_COLUMNS_OUT", len(result_df.columns))
                logger.debug(f"[{self.id}] Updated global map with column statistics")

            logger.info(f"[{self.id}] Processing complete: {total_rows} rows processed")
            return {'main': result_df}

        except Exception as e:
            error_msg = f"Error filtering columns: {str(e)}"
            logger.error(f"[{self.id}] {error_msg}")
            raise ComponentExecutionError(self.id, error_msg, e) from e
