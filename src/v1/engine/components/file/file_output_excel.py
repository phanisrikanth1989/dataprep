"""
FileOutputExcelComponent - Writes data to an Excel file with advanced formatting and structure options.

Talend equivalent: tFileOutputExcel
"""
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import openpyxl
import os
import logging

from ...base_component import BaseComponent
from ...exceptions import FileOperationError, ComponentExecutionError, ConfigurationError

logger = logging.getLogger(__name__)


class FileOutputExcel(BaseComponent):
    """
    Writes DataFrame data to an Excel file with support for multiple sheets and formatting options.

    Configuration:
        filename (str): Path to the Excel file to create/write to. Required.
        sheetname (str): Name of the Excel sheet to write to. Default: 'Sheet1'
        includeheader (bool): Whether to include column headers in output. Default: False
        append_file (bool): Whether to append to existing file or create new. Default: False
        create (bool): Whether to create output directory if it doesn't exist. Default: True
        encoding (str): File encoding (for compatibility, not used in Excel). Default: 'UTF-8'
        die_on_error (bool): Whether to fail job on error. Default: True

    Inputs:
        main: Primary input DataFrame containing data to write

    Outputs:
        None: This component does not produce output data

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully written
        NB_LINE_REJECT: Rows rejected/skipped

    Example configuration:
        {
            "filename": "/path/to/output.xlsx",
            "sheetname": "DataSheet",
            "includeheader": true,
            "append_file": false,
            "create": true,
            "die_on_error": true
        }

    Notes:
        - Supports both DataFrame and list-of-dict input formats
        - Automatically filters out empty rows (all null/empty values)
        - Preserves column order from output schema if defined
        - Creates output directory if it doesn't exist
    """

    # Class constants
    DEFAULT_SHEET_NAME = 'Sheet1'
    DEFAULT_ENCODING = 'UTF-8'

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        if 'filename' not in self.config:
            errors.append("Missing required config: 'filename'")
        elif not isinstance(self.config['filename'], str) or not self.config['filename'].strip():
            errors.append("Config 'filename' must be a non-empty string")

        # Optional field validation
        if 'sheetname' in self.config:
            sheetname = self.config['sheetname']
            if not isinstance(sheetname, str):
                errors.append("Config 'sheetname' must be a string")

        if 'includeheader' in self.config:
            include_header = self.config['includeheader']
            if not isinstance(include_header, bool):
                errors.append("Config 'includeheader' must be a boolean")

        if 'append_file' in self.config:
            append_file = self.config['append_file']
            if not isinstance(append_file, bool):
                errors.append("Config 'append_file' must be a boolean")

        return errors

    def _process(self, input_data: Union[Dict[str, Any], pd.DataFrame, None] = None) -> Dict[str, Any]:
        """
        Write data to Excel file based on configuration.

        Args:
            input_data: Input data - can be DataFrame, dict containing DataFrames, or None

        Returns:
            Dictionary with execution statistics

        Raises:
            FileOperationError: If file operations fail
            ComponentExecutionError: If processing fails
        """
        # Handle empty input
        if input_data is None:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': None, 'stats': self.stats}

        rows_in = 0
        rows_out = 0
        rows_rejected = 0

        logger.info(f"[{self.id}] Processing started")

        try:
            # Extract configuration with defaults
            filename = self.config['filename']
            sheet_name = self.config.get('sheetname', self.DEFAULT_SHEET_NAME)

            # Clean sheet name - remove quotes if present
            if sheet_name.startswith("'") and sheet_name.endswith("'"):
                sheet_name = sheet_name[1:-1]
            elif sheet_name.startswith('"') and sheet_name.endswith('"'):
                sheet_name = sheet_name[1:-1]

            include_header = self.config.get('includeheader', False)
            append_file = self.config.get('append_file', False)
            create_file = self.config.get('create', True)
            die_on_error = self.config.get('die_on_error', True)

            logger.info(f"[{self.id}] Writing to file: {filename}, sheet: {sheet_name}")

            # Ensure the output directory exists
            output_dir = os.path.dirname(filename)
            if create_file and output_dir and not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir)
                    logger.info(f"[{self.id}] Created output directory: {output_dir}")
                except OSError as e:
                    error_msg = f"Failed to create output directory: {output_dir}"
                    logger.error(f"[{self.id}] {error_msg}: {e}")
                    if die_on_error:
                        raise FileOperationError(f"[{self.id}] {error_msg}") from e
                    else:
                        self._update_stats(0, 0, 0)
                        return {'main': None, 'stats': self.stats}

            # Load or create workbook
            try:
                if append_file and os.path.exists(filename):
                    workbook = openpyxl.load_workbook(filename)
                    logger.info(f"[{self.id}] Loaded existing workbook: {filename}")
                else:
                    workbook = openpyxl.Workbook()
                    # Remove default sheet if it exists and we're creating a custom named sheet
                    if 'Sheet' in workbook.sheetnames and sheet_name != 'Sheet':
                        default_sheet = workbook['Sheet']
                        workbook.remove(default_sheet)
                        logger.info(f"[{self.id}] Removed default 'Sheet' to avoid multiple sheets")
            except Exception as e:
                error_msg = f"Failed to load/create workbook: {filename}"
                logger.error(f"[{self.id}] {error_msg}: {e}")
                if die_on_error:
                    raise FileOperationError(f"[{self.id}] {error_msg}") from e
                else:
                    self._update_stats(0, 0, 0)
                    return {'main': None, 'stats': self.stats}

            # Get or create sheet
            try:
                if sheet_name in workbook.sheetnames:
                    sheet = workbook[sheet_name]
                    logger.info(f"[{self.id}] Using existing sheet: {sheet_name}")
                else:
                    sheet = workbook.create_sheet(sheet_name)
                    logger.info(f"[{self.id}] Created new sheet: {sheet_name}")
            except Exception as e:
                error_msg = f"Failed to create/access sheet: {sheet_name}"
                logger.error(f"[{self.id}] {error_msg}: {e}")
                if die_on_error:
                    raise ComponentExecutionError(self.id, error_msg, e) from e
                else:
                    self._update_stats(0, 0, 0)
                    return {'main': None, 'stats': self.stats}

            # Handle DataFrame input properly - Auto-detect from tMap outputs
            main_data = None

            # Check if input_data is a DataFrame directly
            if isinstance(input_data, pd.DataFrame):
                main_data = input_data
                logger.info(f"[{self.id}] Using input DataFrame directly with {len(input_data)} rows")
            elif isinstance(input_data, dict):
                # Look for 'main' key first
                main_data = input_data.get('main')

                # If 'main' not found, try to get the first non-stats DataFrame
                if main_data is None:
                    logger.info(f"[{self.id}] 'main' key not found, searching for first DataFrame in input_data")
                    logger.debug(f"[{self.id}] Available keys: {list(input_data.keys())}")

                    # Look for first DataFrame (skip 'stats' and other metadata)
                    for key, value in input_data.items():
                        if key != 'stats' and hasattr(value, 'iterrows'):  # It's a DataFrame
                            main_data = value
                            logger.info(f"[{self.id}] Using DataFrame from key '{key}' with {len(value)} rows")
                            break

            # Convert DataFrame to list of dictionaries if needed
            rows = []
            column_names = []

            if hasattr(main_data, 'iterrows'):  # It's a pandas DataFrame
                rows_in = len(main_data)
                logger.info(f"[{self.id}] Converting DataFrame with {rows_in} rows to records")

                # PRIORITY 1: Use output schema column order if defined
                if self.output_schema:
                    column_names = [col_def['name'] for col_def in self.output_schema]
                    logger.debug(f"[{self.id}] Using output schema column order: {column_names}")
                else:
                    # PRIORITY 2: Fall back to DataFrame column order
                    column_names = list(main_data.columns)
                    logger.debug(f"[{self.id}] Using DataFrame column order: {column_names}")

                # Convert to records while preserving column order
                for _, pandas_row in main_data.iterrows():
                    # Create ordered dictionary using the defined column order
                    row_dict = {}
                    for col in column_names:
                        # Handle case where schema column might not exist in DataFrame
                        if col in main_data.columns:
                            row_dict[col] = pandas_row[col]
                        else:
                            row_dict[col] = ''  # Default empty value for missing columns
                            logger.warning(f"[{self.id}] Column '{col}' from schema not found in DataFrame, using empty value")
                    rows.append(row_dict)

            elif isinstance(main_data, list):
                rows = main_data
                rows_in = len(rows)
                # Use schema if available, otherwise use first row keys
                if self.output_schema:
                    column_names = [col_def['name'] for col_def in self.output_schema]
                    logger.debug(f"[{self.id}] Using output schema column order for list data: {column_names}")
                else:
                    column_names = list(rows[0].keys()) if rows else []
                    logger.debug(f"[{self.id}] Using first row keys for column order: {column_names}")
            else:
                logger.warning(f"[{self.id}] No data to write or unsupported data format")
                rows = []
                column_names = []
                rows_in = 0

            # Filter out empty rows (rows where all values are empty/null)
            def is_non_empty_row(row):
                return any(
                    value is not None and
                    str(value).strip() != '' and
                    str(value).strip().lower() != 'nan'
                    for value in row.values()
                )

            non_empty_rows = [row for row in rows if is_non_empty_row(row)]
            rows_rejected = len(rows) - len(non_empty_rows)

            logger.info(f"[{self.id}] Processing {len(non_empty_rows)} non-empty rows out of {rows_in} total rows")

            # Write header if requested and we have data
            # Only write header if:
            # 1. Header is requested (include_header is True)
            # 2. We have column names
            # 3. Either we're not appending, or the sheet is empty/has no existing matching header
            should_write_header = False
            if include_header and column_names:
                if not append_file:
                    # Always write header for new files
                    should_write_header = True
                    logger.debug(f"[{self.id}] Writing header for new file")
                else:
                    # For append mode, check if we need to write header
                    if sheet.max_row == 0:
                        # Sheet is completely empty
                        should_write_header = True
                        logger.debug(f"[{self.id}] Writing header for empty sheet in append mode")
                    elif sheet.max_row >= 1:
                        # Sheet has content, check if first row is a matching header
                        try:
                            first_row_values = [cell.value for cell in sheet[1]]
                            # Remove any None values and convert to strings for comparison
                            first_row_cleaned = [str(val).strip() if val is not None else '' for val in first_row_values]
                            column_names_cleaned = [str(col).strip() for col in column_names]

                            if first_row_cleaned == column_names_cleaned:
                                # Headers match, don't write header
                                should_write_header = False
                                logger.debug(f"[{self.id}] Skipping header write - sheet already has matching headers")
                            else:
                                # Headers don't match or first row is data
                                # Check if this looks like a header row or data row
                                if all(val == '' for val in first_row_cleaned):
                                    # First row is empty, write header
                                    should_write_header = True
                                    logger.debug(f"[{self.id}] First row is empty, writing header")
                                else:
                                    # First row has data but doesn't match expected headers
                                    # This could be data from a previous run without headers
                                    should_write_header = False
                                    logger.debug(f"[{self.id}] First row appears to be data, not writing header. "
                                        f"Existing: {first_row_cleaned[:3]}..., Expected headers: {column_names_cleaned[:3]}...")
                        except Exception as e:
                            # If we can't read the first row, assume we need to write header
                            logger.warning(f"[{self.id}] Could not read first row: {e}. Writing header to be safe.")
                            should_write_header = True

            if should_write_header:
                sheet.append(column_names)
                logger.debug(f"[{self.id}] Added header row with columns: {column_names}")

            # Write data rows
            rows_written = 0
            for row in non_empty_rows:
                # Convert row values to list, preserving order of columns
                if column_names:
                    # Use column order from header
                    row_values = [row.get(col, '') for col in column_names]
                else:
                    # Use original order
                    row_values = list(row.values())

                sheet.append(row_values)
                rows_written += 1

            rows_out = rows_written

            # Save workbook
            try:
                workbook.save(filename)
                logger.info(f"[{self.id}] Excel file written successfully: {filename}")
            except Exception as e:
                error_msg = f"Failed to save Excel file: {filename}"
                logger.error(f"[{self.id}] {error_msg}: {e}")
                if die_on_error:
                    raise FileOperationError(f"[{self.id}] {error_msg}") from e
                else:
                    self._update_stats(rows_in, 0, rows_rejected)
                    return {'main': None, 'stats': self.stats}

            # Update statistics
            self._update_stats(rows_in, rows_out, rows_rejected)
            logger.info(f"[{self.id}] Processing complete: in={rows_in}, out={rows_out}, rejected={rows_rejected}")

            return {'main': None, 'stats': self.stats}

        except (FileOperationError, ComponentExecutionError):
            # Re-raise custom exceptions
            raise
        except Exception as e:
            logger.error(f"[{self.id}] Processing failed: {e}")
            raise ComponentExecutionError(self.id, f"Excel output processing failed: {e}", e) from e

    # Legacy method for backward compatibility
    def validate_config(self) -> bool:
        """
        Legacy configuration validation method.

        Returns:
            True if configuration is valid, False otherwise
        """
        errors = self._validate_config()
        if errors:
            for error in errors:
                logger.error(f"[{self.id}] Configuration error: {error}")
            return False
        return True
