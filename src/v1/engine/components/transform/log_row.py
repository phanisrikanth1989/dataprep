"""
LogRow - Logs rows to standard output in table format.

Talend equivalent: tLogRow

This component prints incoming data to standard output in various formats
including table style, basic delimited, and vertical key-value display.
Used for debugging and monitoring data flow in ETL jobs.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class LogRow(BaseComponent):
    """
    Logs rows to standard output in table format, similar to Talend's tLogRow.

    This component prints incoming data to the console for debugging and monitoring
    purposes. Supports multiple output formats including table style with headers,
    basic delimited output, and vertical key-value display.

    Configuration:
        basic_mode (bool): Use basic delimited output instead of table style. Default: False
        table_print (bool): Use table style output with proper formatting. Default: True
        vertical (bool): Use vertical output (each row as key-value pairs). Default: False
        field_separator (str): Field separator for delimited output. Default: '|'
        print_header (bool): Print column headers. Default: True
        max_rows (int): Maximum number of rows to print. Default: 100
        print_column_names (bool): Print column names (alias for print_header). Default: True

    Inputs:
        main: DataFrame to log to console

    Outputs:
        main: Pass-through of input DataFrame (unchanged)

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully logged
        NB_LINE_REJECT: Always 0 (no rejection logic)

    Example configuration:
        {
            "table_print": true,
            "field_separator": "|",
            "print_header": true,
            "max_rows": 50
        }

    Notes:
        - Always passes through input data unchanged
        - Headers are printed by default for better readability
        - Supports both Talend-style and simplified configuration parameters
        - Output goes to standard output (console)
    """

    # Class constants for default values
    DEFAULT_FIELD_SEPARATOR = '|'
    DEFAULT_MAX_ROWS = 100

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Validate max_rows if provided
        max_rows_param = self.config.get('max_rows') or self.config.get('SCHEMA_OPT_NUM')
        if max_rows_param is not None:
            try:
                max_rows_val = int(max_rows_param)
                if max_rows_val < 0:
                    errors.append("Config 'max_rows' must be non-negative")
            except (ValueError, TypeError):
                errors.append("Config 'max_rows' must be an integer")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Process input data and log to console."""
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': input_data}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Logging started: {rows_in} rows")

        # Get configuration with support for both new and Talend-style parameter names
        basic_mode = self._get_boolean_config(['basic_mode', 'BASIC_MODE'], False)
        table_print = self._get_boolean_config(['table_print', 'TABLE_PRINT'], True)
        vertical = self._get_boolean_config(['vertical', 'VERTICAL'], False)
        print_header = self._get_boolean_config(['print_header', 'PRINT_HEADER', 'print_column_names', 'PRINT_COLUMN_NAMES'], True)

        field_separator = self.config.get('field_separator') or self.config.get('FIELDSEPARATOR', self.DEFAULT_FIELD_SEPARATOR)
        max_rows_param = self.config.get('max_rows') or self.config.get('SCHEMA_OPT_NUM', self.DEFAULT_MAX_ROWS)
        max_rows = int(max_rows_param)

        # Limit rows to print
        df_to_print = input_data.head(max_rows)
        rows_logged = len(df_to_print)

        try:
            # Choose output format
            if vertical:
                self._print_vertical_format(df_to_print)
            elif basic_mode:
                self._print_basic_format(df_to_print, field_separator, print_header)
            else:
                # Default table format with beautiful borders
                self._print_table_format(df_to_print, field_separator, print_header)

        except Exception as e:
            logger.error(f"[{self.id}] Error during logging: {e}")
            print(f"[{self.id}] Error logging data: {e}")

        # Update statistics
        self._update_stats(rows_in, rows_logged, 0)
        logger.info(f"[{self.id}] Logging complete: {rows_logged} rows displayed")

        # Pass through input data unchanged
        return {'main': input_data}

    def _get_boolean_config(self, param_names: List[str], default: bool) -> bool:
        """Resolve boolean configuration value with support for multiple parameter names."""
        for param_name in param_names:
            value = self.config.get(param_name)
            if value is not None:
                if isinstance(value, bool):
                    return value
                elif isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
        return default

    def _print_table_format(self, df: pd.DataFrame, separator: str, print_header: bool) -> None:
        """Print DataFrame in formatted table with borders and proper alignment."""
        if df.empty:
            return

        # Calculate column widths based on actual DataFrame columns
        col_widths = {}
        for col in df.columns:
            # Width is max of column name length and max value length in that column
            max_value_len = df[col].fillna('').astype(str).str.len().max() if not df.empty else 0
            col_widths[col] = max(len(str(col)), max_value_len, 1)

        # Calculate total table width based on actual columns
        total_content_width = sum(col_widths.values()) + len(df.columns) - 1  # because we have n-1 separators

        # Component title
        title = f"tLogRow_{self.id}" if not self.id.startswith('tLogRow') else self.id
        title_width = len(title)

        # Make sure table is wide enough for title
        min_table_width = title_width + 4  # +4 for padding
        table_width = max(total_content_width, min_table_width)

        # Top border with calculated width
        top_border = '.' + '-' * (table_width + 2) + '.'
        print(top_border)

        # Component title centered
        title_padding = table_width - title_width
        left_pad = title_padding // 2
        right_pad = title_padding - left_pad
        print(f"|{' ' * left_pad}{title}{' ' * right_pad} |")

        # Header separator with = characters - based on actual DataFrame columns
        header_sep_parts = []
        for col in df.columns:
            header_sep_parts.append('=' * col_widths[col])
        header_separator = '|=' + '|'.join(header_sep_parts) + '=|'
        print(header_separator)

        # Always print column headers for table format
        header_parts = []
        for col in df.columns:
            header_parts.append(str(col).ljust(col_widths[col]))
        print(f"|{'|'.join(header_parts)}|")

        # Header bottom separator
        print(header_separator)

        # Data rows - process actual DataFrame columns
        for idx, row in df.iterrows():
            row_parts = []
            for col in df.columns:
                value = str(row[col]) if pd.notna(row[col]) and str(row[col]) != 'nan' else ''
                row_parts.append(value.ljust(col_widths[col]))
            print(f"|{'|'.join(row_parts)}|")

        # Bottom border
        bottom_border = "'" + '-' * (table_width + 2) + "'"
        print(bottom_border)

    def _print_basic_format(self, df: pd.DataFrame, separator: str, print_header: bool) -> None:
        """Print DataFrame in basic delimited format."""
        if print_header and len(df.columns) > 0:
            print(separator.join(str(col) for col in df.columns))

        for idx, row in df.iterrows():
            print(separator.join(str(row[col]) if pd.notna(row[col]) else '' for col in df.columns))

    def _print_vertical_format(self, df: pd.DataFrame) -> None:
        """Print DataFrame in vertical key-value format."""
        for idx, row in df.iterrows():
            print(f"\nRow {idx + 1}:")
            for col in df.columns:
                value = row[col] if pd.notna(row[col]) else ''
                print(f"  {col}: {value}")
            print("-" * 30)

    # Legacy method name for compatibility
    def validate_config(self) -> bool:
        """Legacy validation method for compatibility."""
        errors = self._validate_config()
        if errors:
            for error in errors:
                logger.error(f"Component {self.id}: {error}")
            return False
        return True
