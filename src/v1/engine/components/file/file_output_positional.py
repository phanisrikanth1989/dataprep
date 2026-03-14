
"""
FileOutputPositional component - Write fixed-width (positional) files.

Talend equivalent: tFileOutputPositional
"""
import gzip
import logging
import os
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)

class FileOutputPositional(BaseComponent):
    """
    Write fixed-width (positional) files with configurable column formatting.

    This component creates fixed-width files where each column is written at a
    specific position with defined width, padding, and alignment. Supports
    compression, headers, and various data type formatting.

    Configuration:
        filepath (str): Output file path. Required.
        formats (list): Column format definitions with size, padding, alignment. Required.
        row_separator (str): Row separator string. Default: '\n'
        append (bool): Append to existing file. Default: False
        include_header (bool): Include header row with column names. Default: True
        compress (bool): Use gzip compression. Default: False
        encoding (str): File encoding. Default: 'utf-8'
        create (bool): Create directory if not exists. Default: True
        flush_on_row (bool): Flush after each row group. Default: False
        flush_on_row_num (int): Number of rows per flush. Default: 1
        delete_empty_file (bool): Delete file if no data written. Default: False
        schema (list): Column schema for type formatting. Optional.
        die_on_error (bool): Fail on error. Default: True

    Inputs:
        main: DataFrame with data to write to positional file

    Outputs:
        main: Same DataFrame as input (pass-through)

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully written
        NB_LINE_REJECT: Rows that failed (usually 0)

    Example configuration:
        {
            "filepath": "/data/output.txt",
            "formats": [
                {"schema_column": "id", "size": 10, "align": "R", "padding_char": "0"},
                {"schema_column": "name", "size": 20, "align": "L", "padding_char": " "}
            ],
            "row_separator": "\n",
            "encoding": "utf-8",
            "include_header": true
        }

    Notes:
        - Supports left (L) and right (R) alignment
        - Handles different data types with precision formatting
        - Can compress output using gzip
        - Creates directories automatically if needed
        - Supports escape sequences in row separator
    """

    # Class constants
    DEFAULT_ROW_SEPARATOR = '\n'
    DEFAULT_ENCODING = 'utf-8'
    DEFAULT_APPEND = False
    DEFAULT_INCLUDE_HEADER = True
    DEFAULT_COMPRESS = False
    DEFAULT_CREATE = True
    DEFAULT_FLUSH_ON_ROW = False
    DEFAULT_FLUSH_ON_ROW_NUM = 1
    DEFAULT_DELETE_EMPTY_FILE = False
    DEFAULT_DIE_ON_ERROR = True
    DEFAULT_PADDING_CHAR = ' '
    DEFAULT_ALIGN = 'L'
    DEFAULT_KEEP = 'A'
    DEFAULT_PRECISION = 8

    VALID_ALIGNMENTS = ['L', 'R']
    VALID_KEEP_OPTIONS = ['A', 'C']
    NUMERIC_TYPES = ['float', 'double', 'decimal','id_Float', 'id_Double', 'id_BigDecimal'    ]
    INTEGER_TYPES = [        'int', 'long', 'integer',        'id_Integer', 'id_Long'    ]

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        if not self.config.get('filepath'):
            errors.append("Missing required config: 'filepath'")

        formats = self.config.get('formats')
        if not formats:
            errors.append("Missing required config: 'formats'")
        elif not isinstance(formats, list):
            errors.append("Config 'formats' must be a list")
        elif len(formats) == 0:
            errors.append("Config 'formats' cannot be empty")
        else:
            # Validate each format definition
            for i, fmt in enumerate(formats):
                if not isinstance(fmt, dict):
                    errors.append(f"Format {i}: must be a dictionary")
                    continue

                # Check required format fields
                if not (fmt.get('schema_column') or fmt.get('SCHEMA_COLUMN')):
                    errors.append(f"Format {i}: missing 'schema_column' field")

                size = fmt.get('size') or fmt.get('SIZE')
                if not size:
                    errors.append(f"Format {i}: missing 'size' field")
                else:
                    try:
                        size_int = int(size)
                        if size_int <= 0:
                            errors.append(f"Format {i}: 'size' must be positive, got {size_int}")
                    except (ValueError, TypeError):
                        errors.append(f"Format {i}: 'size' must be a valid integer, got {size}")

                # Validate optional fields
                align = (fmt.get('align') or fmt.get('ALIGN') or self.DEFAULT_ALIGN).upper()
                if align not in self.VALID_ALIGNMENTS:
                    errors.append(f"Format {i}: 'align' must be one of {self.VALID_ALIGNMENTS}, got '{align}'")

                keep = (fmt.get('keep') or fmt.get('KEEP') or self.DEFAULT_KEEP).upper()
                if keep not in self.VALID_KEEP_OPTIONS:
                    errors.append(f"Format {i}: 'keep' must be one of {self.VALID_KEEP_OPTIONS}, got '{keep}'")

        # Optional field validation
        flush_on_row_num = self.config.get('flush_on_row_num', self.DEFAULT_FLUSH_ON_ROW_NUM)
        try:
            num = int(flush_on_row_num)
            if num <= 0:
                errors.append("Config 'flush_on_row_num' must be positive")
        except (ValueError, TypeError):
            errors.append("Config 'flush_on_row_num' must be a valid integer")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process positional file output.

        Args:
            input_data: Input DataFrame to write to positional file

        Returns:
            Dictionary with main output (pass-through of input data)

        Raises:
            ValueError: If required configuration is missing or invalid
            IOError: If file operations fail
        """
        logger.info(f"[{self.id}] Positional file output started")

        try:
            # Get configuration with defaults
            filepath = self.config.get('filepath', '')
            row_separator = self.config.get('row_separator',self.DEFAULT_ROW_SEPARATOR)
            append = self.config.get('append', self.DEFAULT_APPEND)
            include_header = self.config.get('include_header',self.DEFAULT_INCLUDE_HEADER)
            compress = self.config.get('compress', self.DEFAULT_COMPRESS)
            encoding = self.config.get('encoding', self.DEFAULT_ENCODING)
            create = self.config.get('create', self.DEFAULT_CREATE)
            flush_on_row = self.config.get('flush_on_row',self.DEFAULT_FLUSH_ON_ROW)
            flush_on_row_num = int(self.config.get('flush_on_row_num',self.DEFAULT_FLUSH_ON_ROW_NUM))
            delete_empty_file = self.config.get('delete_empty_file',self.DEFAULT_DELETE_EMPTY_FILE)
            formats = self.config.get('formats', [])
            die_on_error = self.config.get('die_on_error',self.DEFAULT_DIE_ON_ERROR)

            # Validate required parameters
            if not filepath:
                error_msg = "filepath is required"
                logger.error(f"[{self.id}] {error_msg}")
                if die_on_error:
                    raise ValueError(error_msg)
                else:
                    logger.warning(f"[{self.id}] Continuing with error, returning input data")
                    self._update_stats(0, 0, 0)
                    return {'main': input_data or pd.DataFrame()}

            if not formats or not isinstance(formats, list):
                error_msg = "formats (column definitions) are required and must be a list"
                logger.error(f"[{self.id}] {error_msg}")
                if die_on_error:
                    raise ValueError(error_msg)
                else:
                    logger.warning(f"[{self.id}] Continuing with error, returning input data")
                    self._update_stats(0, 0, 0)
                    return {'main': input_data or pd.DataFrame()}

            # Handle empty input
            if input_data is None or (hasattr(input_data, 'empty') and input_data.empty):
                logger.info(f"[{self.id}] Empty input received")
                if delete_empty_file and os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        logger.info(f"[{self.id}] Deleted empty file: {filepath}")
                    except Exception as e:
                        logger.warning(f"[{self.id}] Could not delete file {filepath}: {e}")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

            # Prepare data
            data = input_data.fillna('')
            rows_in = len(data)
            logger.debug(f"[{self.id}] Processing {rows_in} rows")

            # Decode escape sequences in row_separator
            if isinstance(row_separator, str):
                row_separator = row_separator.encode('utf-8').decode('unicode_escape')
                logger.debug(f"[{self.id}] Using row separator: {repr(row_separator)}")

            # Write file
            rows_written = self._write_positional_file(
                data, filepath, formats, row_separator, append, include_header,
                compress, encoding, create, flush_on_row, flush_on_row_num
            )

            # Handle empty file deletion
            if delete_empty_file and os.path.exists(filepath):
                if os.path.getsize(filepath) == 0:
                    os.remove(filepath)
                    logger.info(f"[{self.id}] Deleted empty file: {filepath}")

            # Update statistics and log success
            self._update_stats(rows_in, rows_written, 0)
            logger.info(f"[{self.id}] Positional file output complete: {rows_written} rows written to {filepath}")

            return {'main': input_data}

        except Exception as e:
            logger.error(f"[{self.id}] Positional file output failed: {e}")

            #Update stats with failure
            rows_in = len(input_data) if input_data is not None else 0
            self._update_stats(rows_in, 0, rows_in)

            #Re-raise or return input data based on die_on_error
            if self.config.get('die_on_error', self.DEFAULT_DIE_ON_ERROR):
                raise
            else:
                #Return input data on error if not dying, ensuring it's a DataFrame
                return {'main': input_data or pd.DataFrame()}

    def _write_positional_file(self, data: pd.DataFrame, filepath: str, formats: List[Dict],
                                row_separator: str, append: bool, include_header: bool,
                                compress: bool, encoding: str, create: bool,
                                flush_on_row: bool, flush_on_row_num: int) -> int:
        """
        Write data to positional file with specified formatting.

        Args:
            data: DataFrame to write
            filepath: Output file path
            formats: List of column format specifications
            row_separator: Row separator string
            append: Whether to append to existing file
            include_header: Whether to include header row
            compress: Whether to use gzip compression
            encoding: File encoding
            create: Whether to create directories if needed
            flush_on_row: Whether to flush after each row group
            flush_on_row_num: Number of rows per flush
        
        Returns:
            Number of rows written
        """
        #Prepare output mode and file handle
        mode = 'ab' if compress else ('a' if append else 'w')
        file_handle = None

        try:
            # Create directory if needed
            directory = os.path.dirname(filepath)
            if create and directory and not os.path.exists(directory):
                logger.debug(f"[{self.id}] Creating directory: {directory}")
                os.makedirs(directory, exist_ok=True)

            #prepare file handle
            if compress:
                logger.debug(f"[{self.id}] Opening compressed file: {filepath}")
                file_handle = gzip.open(filepath, mode)
            else:
                logger.debug(f"[{self.id}] Opening file: {filepath}")
                file_handle = open(filepath, mode, encoding=encoding)

            #prepare format specifications
            col_formats, col_names, col_types = self._prepare_column_formats(formats)

            #Write header if needed
            if include_header:
                logger.debug(f"[{self.id}] Writing header row")
                header = self._format_header_row(col_names, col_formats, row_separator)
                if compress:
                    file_handle.write(header.encode(encoding))
                else:
                    file_handle.write(header)

            #Write data rows
            row_count = 0
            for idx, row in data.iterrows():
                line = self._format_data_row(row, col_names, col_formats, col_types, row_separator)
                if compress:
                    file_handle.write(line.encode(encoding))
                else:
                    file_handle.write(line)
                row_count += 1

                if flush_on_row and (row_count % flush_on_row_num == 0):
                    logger.debug(f"[{self.id}] Flushing after {row_count} rows")
                    file_handle.flush()

            #   Final flush and close
            file_handle.flush()
            file_handle.close()
            file_handle = None

            return row_count

        except Exception as e:
            if file_handle:
                try:
                    file_handle.close()
                except Exception:
                    pass
            raise

    def _prepare_column_formats(self, formats: List[Dict]) -> tuple:
        """
Prepare column format specifications from configuration.

        Args:
            formats: List of column format definitions from config  

        Returns:
            Tuple of (col_formats, col_names, col_types)
        """
        col_formats = []
        col_names = []
        col_types = []

        #Get schema from config for type information
        schema = self.config.get('schema', [])
        schema_map = {col['name']: col for col in schema} if schema else {}

        for fmt in formats:
            col = fmt.get('schema_column') or fmt.get('SCHEMA_COLUMN')
            size = int(fmt.get('size') or fmt.get('SIZE'))
            pad = (fmt.get('padding_char') or fmt.get('PADDING_CHAR') or self.DEFAULT_PADDING_CHAR)

            #Strip single quotes if present (e.g. "' '")
            if isinstance(pad, str) and pad.startswith("'") and pad.endswith("'") and len(pad) == 3:
                pad = pad[1:-1]
            pad = pad or self.DEFAULT_PADDING_CHAR

            align = (fmt.get('align') or fmt.get('ALIGN') or self.DEFAULT_ALIGN).upper()
            keep = (fmt.get('keep') or fmt.get('KEEP') or self.DEFAULT_KEEP).upper()

            col_names.append(col)
            col_formats.append({'size': size, 'pad': pad, 'align': align, 'keep': keep})

            #Get column type from schema
            col_type = schema_map.get(col, {}).get('type', 'str')
            col_types.append(col_type)

        return col_formats, col_names, col_types

    def _format_header_row(self, col_names: List[str], col_formats: List[Dict], row_separator: str) -> str:
        """
            Format header row based on column names and formats.
            
        Args:
            col_names: List of column names
            col_formats: List of column format specifications
            row_separator: Row separator string

        Returns:
            Formatted header row string
        """
        header = ''
        for i, col in enumerate(col_names):
            fmt = col_formats[i]
            val = str(col)

            #Truncate if too long
            if len(val) > fmt['size']:
                val = val[:fmt['size']]

            #Apply alignment and padding
            if fmt['align'] == 'L':
                val = val.ljust(fmt['size'], fmt['pad'])
            else:
                val = val.rjust(fmt['size'], fmt['pad'])

            header += val

        header += row_separator
        return header

    def _format_data_row(self, row: pd.Series, col_names: List[str],col_formats: List[Dict], 
                         col_types: List[str],row_separator: str) -> str:
        """
        Format a single data row
        
        Args:
            row: Pandas Series representing the data row
            col_names: List of column names in order
            col_formats: List of column format specifications
            col_types: List of column data types
            row_separator: Row separator string 
            
        Returns:
            Formatted data row string
        """
        line = ''
        schema = self.config.get('schema', [])
        schema_map = {col['name']: col for col in schema} if schema else {}

        for i, col in enumerate(col_names):
            fmt = col_formats[i]
            col_type = col_types[i] if i < len(col_types) else 'str'
            val = row.get(col, '')

            #Format value based on type
            if col_type in self.NUMERIC_TYPES:
                try:
                    precision = schema_map.get(col, {}).get('precision', self.DEFAULT_PRECISION)
                    val = f"{float(val):.{precision}f}" if val != '' else ''
                except Exception:
                    val = str(val)
            elif col_type in self.INTEGER_TYPES:
                try:
                    val = f"{int(float(val))}" if val != '' else ''
                except Exception:
                    val = str(val)
            else:
                val = str(val)

            #Truncate if too long and keep option is 'C'
            if len(val) > fmt['size']:
                if fmt['keep'] == 'C':
                    val = val[:fmt['size']]

            #Apply alignment and padding
            if fmt['align'] == 'L':
                val = val.ljust(fmt['size'], fmt['pad'])
            else:
                val = val.rjust(fmt['size'], fmt['pad'])

            line += val

        line += row_separator
        return line