"""
FileRowCount component - Count rows in a file

This component counts the number of rows in a specified file, with options to ignore empty rows
and handle different encodings. It's equivalent to Talend's tFileRowCount component.

Configuration Parameters:
    filename (str): Path to the file to count rows in (required)
    row_separator (str): Row separator to use (default: '\n') - currently not implemented
    ignore_empty_row (bool): Whether to ignore empty rows in the count (default: False)
    encoding (str): File encoding to use when reading (default: 'UTF-8')

Returns:
    Dictionary with 'main' key containing 'row_count' value

Example Usage:
    component = FileRowCount(
        id="row_counter_1",
        config={
            "filename": "/path/to/data.csv",
            "ignore_empty_row": True,
            "encoding": "UTF-8"
        }
    )
    result = component.execute()
    row_count = result['main']['row_count']
"""
import logging
import os
from typing import Any, Dict, Optional

from ...base_component import BaseComponent

# Module-level logger
logger = logging.getLogger(__name__)


class FileRowCount(BaseComponent):
    """
    Count rows in a file based on the specified configuration.

    This component reads a file and counts the number of rows, with optional
    filtering for empty rows. The row count is stored in the GlobalMap for
    use by other components in the job flow.

    Attributes:
        Inherits all attributes from BaseComponent

    Configuration:
        filename (str): Path to the input file (required)
        row_separator (str): Row separator character (default: '\n') - for future use
        ignore_empty_row (bool): Skip empty rows in count (default: False)
        encoding (str): File encoding (default: 'UTF-8')

    Inputs:
        None: This component reads directly from files

    Outputs:
        main: Dictionary with 'row_count' key containing the total row count

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Total rows processed (same as NB_LINE for this component)
        NB_LINE_REJECT: Always 0 (no rejection logic)

    Example:
        config = {
            "filename": "/data/input.csv",
            "ignore_empty_row": True,
            "encoding": "UTF-8"
        }
        component = FileRowCount("comp_1", config, global_map, context_manager)
        result = component.execute()
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the FileRowCount component.

        Args:
            *args: Variable length argument list passed to parent class
            **kwargs: Arbitrary keyword arguments passed to parent class
        """
        super().__init__(*args, **kwargs)
        # Initialize component logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _validate_config(self) -> bool:
        """
        Validate the component configuration parameters.

        Checks that all required configuration parameters are present and valid.
        This method is called before component execution to ensure proper setup.

        Returns:
            bool: True if the configuration is valid, False otherwise
        
        validation Rules:
            - filename: Required, must be a string
            - encoding: Optional, if provided must be a valid encoding
            - ignore_empty_row: Optional, if provided must be a boolean
        """
        is_valid = True

        # Check required filename parameter (support both snake_case and legacy UPPER_CASE)
        filename = self.config.get('filename') or self.config.get('FILENAME', '')
        if not filename:
            self.logger.error(f"[{self.id}] filename is required but not provided")
            is_valid = False
        elif not isinstance(filename, str):
            self.logger.error(f"[{self.id}] filename must be a string, got {type(filename)}")
            is_valid = False

        # Validate encoding parameter if provided (support both formats)
        encoding = self.config.get('encoding') or self.config.get('ENCODING', 'UTF-8')
        if encoding:
            try:
                ''.encode(encoding)
            except LookupError:
                self.logger.error(f"[{self.id}] Invalid encoding specified: {encoding}")
                is_valid = False

        # Validate boolean parameters (support both formats)
        ignore_empty_row = self.config.get('ignore_empty_row')
        if ignore_empty_row is None:
            ignore_empty_row = self.config.get('IGNORE_EMPTY_ROW', False)
        if not isinstance(ignore_empty_row, bool):
            self.logger.error(f"[{self.id}] ignore_empty_row must be a boolean, got {type(ignore_empty_row)}")
            is_valid = False

        if is_valid:
            self.logger.debug(f"[{self.id}] Configuration validation passed")
        else:
            self.logger.debug(f"[{self.id}] Configuration validation failed")

        return is_valid

    def _process(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process the component logic to count rows in the specified file.

        This method reads the specified file line by line and counts the total
        number of rows, optionally ignoring empty rows based on configuration.
        The result is stored in GlobalMap and returned.

        Args:
            input_data: Input data (not used for this component)

        Returns:
            Dict[str, Any]: Dictionary containing:
                - main: Dictionary with 'row_count' key containing the total row count

        Raises:
            FileNotFoundError: If the specified file does not exist
            PermissionError: If the file cannot be read due to permissions
            UnicodeDecodeError: If the file cannot be decoded with specified encoding
            IOError: If there are issues reading the file
        """
        try:
            # Get configuration parameters with defaults (support both snake_case and legacy UPPER_CASE)
            filename = self.config.get('filename') or self.config.get('FILENAME', '')
            row_separator = self.config.get('row_separator') or self.config.get('ROWSEPARATOR', '\n')
            ignore_empty_row = self.config.get('ignore_empty_row')
            if ignore_empty_row is None:
                ignore_empty_row = self.config.get('IGNORE_EMPTY_ROW', False)
            encoding = self.config.get('encoding') or self.config.get('ENCODING', 'UTF-8')

            # Validate file existence
            if not filename or not os.path.exists(filename):
                raise FileNotFoundError(f"File not found: {filename}")

            # Log processing start
            self.logger.info(f"[{self.id}] Processing started: file={filename}")

            # Count rows in file
            rows_in = 0
            rows_out = 0
            rows_rejected = 0

            try:
                with open(filename, 'r', encoding=encoding) as file:
                    for line in file:
                        rows_in += 1
                        # Skip empty rows if configured to ignore them
                        if ignore_empty_row and not line.strip():
                            rows_rejected += 1
                            continue
                        rows_out += 1

            except PermissionError as e:
                self.logger.error(f"[{self.id}] Permission denied accessing file: {filename}")
                raise PermissionError(f"Permission denied accessing file: {filename}") from e
            except UnicodeDecodeError as e:
                self.logger.error(f"[{self.id}] Encoding error reading file {filename} with encoding {encoding}")
                raise UnicodeDecodeError(encoding, b'', 0, 1, f"Cannot decode file {filename} with encoding {encoding}") from e
            except IOError as e:
                self.logger.error(f"[{self.id}] I/O error reading file: {filename}")
                raise IOError(f"I/O error reading file: {filename}") from e

            # The actual row count depends on whether we ignore empty rows
            row_count = rows_out

            # Log successful completion
            self.logger.info(f"[{self.id}] Processing complete: in={rows_in}, out={rows_out}, rejected={rows_rejected}")

            # Update component statistics using Talend-compatible values
            self._update_stats(rows_in, rows_out, rows_rejected)

            # Store row count in GlobalMap with Talend-compatible keys
            if self.global_map:
                # Store the main count with both key formats for compatibility
                global_map_key = f"{self.id}_NB_LINE"
                count_key = f"{self.id}_COUNT"  # Legacy key format

                self.global_map.put(global_map_key, rows_out)
                self.global_map.put(count_key, rows_out)  # Store with legacy key too

                # Store additional Talend-compatible statistics
                self.global_map.put(f"{self.id}_NB_LINE_OK", rows_out)
                self.global_map.put(f"{self.id}_NB_LINE_REJECT", rows_rejected)

                # Verify storage in GlobalMap (for debugging purposes)
                stored_value = self.global_map.get(count_key)
                self.logger.debug(f"[{self.id}] Stored row count {stored_value} in GlobalMap with key: {count_key}")

            return {'main': {'row_count': row_count}}

        except Exception as e:
            self.logger.error(f"[{self.id}] Processing failed: {str(e)}")
            raise