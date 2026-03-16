"""
FileInputDelimited - Read delimited files (CSV, TSV, etc.)

Talend equivalent: tFileInputDelimited

This component reads data from delimited text files with configurable parsing options.
Supports various delimiters, encodings, and schema enforcement. Handles large files
through streaming mode and provides sophisticated type conversion capabilities.
Special handling for single-string file reading when both delimiter and row_separator
are empty.
"""

import csv
import logging
import os
from decimal import Decimal
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd

from ...base_component import BaseComponent, ExecutionMode
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


class FileInputDelimited(BaseComponent):
    """
    Read data from delimited text files with configurable parsing and type conversion.

    This component reads various delimited formats (CSV, TSV, pipe-separated, etc.)
    with support for custom delimiters, encodings, schema enforcement, and automatic type
    conversion.
    Provides streaming mode for large files and sophisticated handling of edge cases.

    Configuration:
        filepath (str): Input file path. Required. Supports context variables.
        delimiter (str): Field delimiter character. Default: ','
        encoding (str): File encoding. Default: 'UTF-8'
        header_rows (int): Number of header rows to skip. Default: 0
        footer_rows (int): Number of footer rows to skip. Default: 0
        limit (str): Maximum rows to read. Empty or no limit. Default: ''
        remove_empty_rows (bool): Remove completely empty rows. Default: False
        text_enclosure (str): Quote character for text fields. Default: '"'
        escape_char (str): Escape character. Default:'\\'
        trim_all (bool): Trim whitespace from all string fields. Default: False
        die_on_error (bool): Fail on errors vs. continue. Default: True
        row_separator (str): Row separator (special case handling). Default: None

    Inputs:
        None (file input component)

    Outputs:
        main: DataFrame containing parsed file data

    Statistics:
        NB_LINE: Total rows read
        NB_LINE_OK: Successfully processed rows
        NB_LINE_REJECT: Failed rows (0 for this component)

    Example:
        config = {
            "filepath": "/data/input.csv",
            "delimiter": ",",
            "encoding": "UTF-8",
            "header_rows": "1",
            "limit": "1000"
        }

    Notes:
        - Empty delimiter and row_separator reads file as single string
        - Automatically switches to streaming mode for large files (>3GB)
        - Schema enforcement with sophisticated type conversion
        - BigDecimal support for financial data
        - Java expression support for dynamic configuration
    """

    # Class constants for default values
    DEFAULT_DELIMITER = ','
    DEFAULT_ENCODING = 'UTF-8'
    DEFAULT_HEADER_ROWS = 0
    DEFAULT_FOOTER_ROWS = 0
    DEFAULT_TEXT_ENCLOSURE = '"'
    DEFAULT_ESCAPE_CHAR = '\\'

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        if 'filepath' not in self.config or not self.config['filepath']:
            errors.append("Missing required config: 'filepath'")

        # Optional field validation
        if 'delimiter' in self.config:
            delimiter = self.config['delimiter']
            if not isinstance(delimiter, str):
                errors.append("Config 'delimiter' must be a string")

        if 'encoding' in self.config:
            encoding = self.config['encoding']
            if not isinstance(encoding, str):
                errors.append("Config 'encoding' must be a string")

        if 'header_rows' in self.config:
            try:
                header_rows = int(self.config['header_rows'])
                if header_rows < 0:
                    errors.append("Config 'header_rows' must be non-negative")
            except (ValueError, TypeError):
                errors.append("Config 'header_rows' must be a valid integer")

        if 'footer_rows' in self.config:
            try:
                footer_rows = int(self.config['footer_rows'])
                if footer_rows < 0:
                    errors.append("Config 'footer_rows' must be non-negative")
            except (ValueError, TypeError):
                errors.append("Config 'footer_rows' must be a valid integer")

        if 'limit' in self.config and self.config['limit']:
            try:
                limit = int(self.config['limit'])
                if limit <= 0:
                    errors.append("Config 'limit' must be positive")
            except (ValueError, TypeError):
                errors.append("Config 'limit' must be a valid integer")

        if 'remove_empty_rows' in self.config:
            if not isinstance(self.config['remove_empty_rows'], bool):
                errors.append("Config 'remove_empty_rows' must be boolean")

        if 'trim_all' in self.config:
            if not isinstance(self.config['trim_all'], bool):
                errors.append("Config 'trim_all' must be boolean")

        if 'die_on_error' in self.config:
            if not isinstance(self.config['die_on_error'], bool):
                errors.append("Config 'die_on_error' must be boolean")

        return errors

    def _build_dtype_dict(self) -> Optional[Dict[str, str]]:
        """
        Build dtype dictionary from output schema for pd.read_csv().

        Maps Talend types to pandas dtype strings for efficient type enforcement
        during file reading. Supports nullable integers and proper object types.

        Returns:
            Dict mapping column names to pandas dtypes, or None if no schema
        """
        if not self.output_schema:
            return None

        # Type mapping from Talend to pandas dtype strings
        type_mapping = {
            'id_String': 'object',
            'id_Integer': 'Int64',   # Nullable integer
            'id_Long': 'Int64',
            'id_Float': 'float64',
            'id_Double': 'float64',
            'id_Boolean': 'bool',   # Read as object, convert later
            'id_Date': 'object',    # Read as object, convert later
            'id_BigDecimal': 'object',
            # Simple type names
            'str': 'object',
            'int': 'Int64',
            'long': 'Int64',
            'float': 'float64',
            'double': 'float64',
            'bool': 'bool',
            'date': 'object',
            'Decimal': 'object'
        }

        dtype_dict = {}
        for col_def in self.output_schema:
            col_name = col_def['name']
            col_type = col_def.get('type', 'id_String')
            pandas_type = type_mapping.get(col_type, 'object')
            dtype_dict[col_name] = pandas_type

        logger.debug(f"[{self.id}] Built dtype mapping: {len(dtype_dict)} columns")
        return dtype_dict

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Read delimited file and return as DataFrame.

        Handles various file formats and special cases including single-string
        reading,
        streaming mode for large files, and comprehensive type conversion.

        Args:
            input_data: Not used for file input components

        Returns:
            Dictionary containing:
                'main': DataFrame with parsed file data
                'is_streaming': True if using streaming mode (optional)

        Raises:
            ConfigurationError: If required configuration is missing or invalid
            FileOperationError: If file read operation fails
        """
        # Get configuration with proper type conversion
        filepath = self.config.get('filepath', '')
        delimiter = self.config.get('delimiter', self.DEFAULT_DELIMITER)
        row_separator = self.config.get('row_separator', None)
        encoding = self.config.get('encoding', self.DEFAULT_ENCODING)
        die_on_error = self.config.get('die_on_error', True)

        # Convert numeric parameters to int to avoid string/int comparison errors
        try:
            header_rows = int(self.config.get('header_rows', self.DEFAULT_HEADER_ROWS))
        except (ValueError, TypeError):
            header_rows = self.DEFAULT_HEADER_ROWS
            logger.warning(f"[{self.id}] Invalid header_rows, using default: {header_rows}")

        try:
            footer_rows = int(self.config.get('footer_rows', self.DEFAULT_FOOTER_ROWS))
        except (ValueError, TypeError):
            footer_rows = self.DEFAULT_FOOTER_ROWS
            logger.warning(f"[{self.id}] Invalid footer_rows, using default: {footer_rows}")

        limit = self.config.get('limit', '')
        remove_empty_rows = self.config.get('remove_empty_rows', False)
        text_enclosure = self.config.get('text_enclosure', self.DEFAULT_TEXT_ENCLOSURE)

        escape_char = self.config.get('escape_char', self.DEFAULT_ESCAPE_CHAR)
        trim_all = self.config.get('trim_all', False)

        if not filepath:
            error_msg = "'filepath' is required"
            logger.error(f"[{self.id}] Configuration error: {error_msg}")
            if die_on_error:
                raise ConfigurationError(f"[{self.id}] {error_msg}")
            else:
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

        logger.info(f"[{self.id}] Reading started: Input file '{filepath}'")
        logger.debug(f"[{self.id}] Configuration: delimiter='{delimiter}', encoding={encoding}, "
                     f"header_rows={header_rows}, footer_rows={footer_rows}")

        # Check if file exists
        if not os.path.exists(filepath):
            error_msg = f"Input file not found: '{filepath}'"
            logger.error(f"[{self.id}] File access error: {error_msg}")
            if die_on_error:
                raise FileOperationError(f"[{self.id}] {error_msg}")
            else:
                logger.warning(f"[{self.id}] Continuing with empty DataFrame due to missing file")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

        # Special case: If both delimiter and row_separator are empty, read file as
        # single string
        # This handles XML or other single-document files that need to be read as one
        if delimiter in [None, '', '  '] and row_separator in [None, '', '  ', '\r\n']:
            logger.info(f"[{self.id}] Special mode: reading as single string (empty delimiter/separator)")
            return self._read_as_single_string(filepath, encoding, die_on_error)

        # Determine execution mode based on file size
        try:
            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
            logger.debug(f"[{self.id}] File size: {file_size_mb:.2f} MB")
        except:
            pass

        # Convert limit to int or None
        nrows = self._parse_limit(limit)

        # Handle multi-character delimiter (regex) and tab shortcut
        use_regex = False
        if delimiter == "\\t" or delimiter == "\t":
            delimiter = "\t"
            logger.debug(f"[{self.id}] Using tab delimiter")
        elif len(delimiter) > 1:
            delimiter = r'{delimiter}'
            use_regex = True
            logger.debug(f"[{self.id}] Using regex delimiter: '{delimiter}'")

        # Determine execution mode
        if (self.execution_mode == ExecutionMode.HYBRID and file_size_mb > self.execution_mode_threshold_mb):
            logger.info(f"[{self.id}] Large file detected: switching to streaming")
            return self._read_streaming(filepath, delimiter, encoding, header_rows, footer_rows, nrows, text_enclosure, escape_char, remove_empty_rows, trim_all, use_regex)
        else:
            logger.debug(f"[{self.id}] Using batch mode for file reading")
            return self._read_batch(filepath, delimiter, encoding, header_rows, footer_rows, nrows, text_enclosure, escape_char, remove_empty_rows, trim_all, use_regex)

        except Exception as e:
            error_msg = f"Error reading file '{filepath}': {str(e)}"
            logger.error(f"[{self.id}] File operation failed: {error_msg}")
            if die_on_error:
                raise FileOperationError(f"[{self.id}] {error_msg}") from e
            else:
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

    def _read_as_single_string(self, filepath: str, encoding: str, die_on_error: bool) -> Dict[str, Any]:
        """
        Read entire file as single string (special case for XML/document files).

        Used when both delimiter and row_separator are empty, indicating the file
        should be treated as a single document rather than structured data.
        """
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                file_content = f.read()

            # Use first column name from output_schema or default to 'doc'
            if self.output_schema and len(self.output_schema) > 0:
                column_name = self.output_schema[0]['name']
            else:
                column_name = 'doc'

            df = pd.DataFrame({column_name: file_content})
            self._update_stats(1, 1, 0)

            logger.info(f"[{self.id}] Read complete: file as single string, column: '{column_name}'")
            logger.debug(f"[{self.id}] Result shape: {df.shape}, content length: {len(file_content)} chars")

            return {'main': df}

        except Exception as e:
            error_msg = f"Error reading file '{filepath}' as single string: {str(e)}"
            logger.error(f"[{self.id}] Single string read failed: {error_msg}")
            if die_on_error:
                raise FileOperationError(f"[{self.id}] {error_msg}") from e
            else:
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

    def _parse_limit(self, limit: Any) -> Optional[int]:
        """Parse limit parameter to integer or None."""
        if not limit or str(limit).strip() == '':
            return None
        try:
            parsed_limit = int(limit)
            logger.debug(f"[{self.id}] Row limit set: {parsed_limit}")
            return parsed_limit
        except (ValueError, TypeError):
            logger.warning(f"[{self.id}] Invalid limit value '{limit}', ignoring")
            return None

    def _read_batch(self, filepath: str, delimiter: str, encoding: str,
                    header_rows: int, footer_rows: int, nrows: Optional[int],
                    text_enclosure: str, escape_char: str, remove_empty_rows: bool,
                    trim_all: bool, use_regex: bool = False) -> Dict[str, Any]:
        """Read entire file at once using pandas.read_csv()."""
        logger.debug(f"[{self.id}] Batch read: delimiter='{delimiter}', header_rows={header_rows}, "
                     f"footer_rows={footer_rows}, nrows={nrows}")

        # ...existing code...
        if self.output_schema:
            skiprows = list(range(header_rows)) if header_rows > 0 else None
            header = None
            column_names = [col['name'] for col in self.output_schema]
            names = column_names
            logger.debug(f"[{self.id}] Using schema column names: {len(column_names)}")
        else:
            skiprows = None
            header = None if header_rows == 0 else list(range(header_rows))
            names = None
            logger.debug(f"[{self.id}] Using file headers")

        dtype_dict = self._build_dtype_dict()
        columns_to_keep = list(dtype_dict.keys()) if dtype_dict else None
        engine = 'python' if (footer_rows > 0 or use_regex or skiprows is not None) else 'c'

        logger.debug(f"[{self.id}] Using pandas engine: '{engine}'")

        quote_params = self._configure_csv_params(text_enclosure, escape_char)

        try:
            read_params = {
                'filepath_or_buffer': filepath,
                'sep': delimiter,
                'encoding': encoding,
                'header': header,
                'names': names,
                'skiprows': skiprows,
                'nrows': nrows,
                'skipfooter': footer_rows,
                'engine': engine,
                'keep_default_na': False,
                **quote_params
            }

            if use_regex:
                read_params['regex'] = True

            if columns_to_keep:
                read_params['usecols'] = columns_to_keep
            if dtype_dict:
                read_params['dtype'] = dtype_dict

            logger.debug(f"[{self.id}] Reading file with pandas: engine='{engine}', " f"usecols={len(columns_to_keep) if columns_to_keep else 'all'}")

            df = pd.read_csv(**read_params)

            # ...existing code...
            df = self._post_process_dataframe(df, trim_all, remove_empty_rows)

            if self.output_schema:
                expected_cols = len(self.output_schema)
                actual_cols = len(df.columns)
                if expected_cols != actual_cols:
                    logger.warning(f"[{self.id}] Schema mismatch: expected {expected_cols} columns, " f"got {actual_cols}. Data may be misaligned.")

                df = self.validate_schema(df, self.output_schema)

            rows_read = len(df)
            self._update_stats(rows_read, rows_read, 0)

            logger.info(f"[{self.id}] Read complete: {rows_read} rows from '{filepath}'")

            if logger.isEnabledFor(logging.DEBUG):
                dtypes_info = {col: str(dtype) for col, dtype in df.dtypes.items()}
                logger.debug(f"[{self.id}] Final column dtypes: {dtypes_info}")

            return {'main': df}

        except Exception as e:
            error_msg = f"Batch read failed for '{filepath}': {str(e)}"
            logger.error(f"[{self.id}] {error_msg}")
            raise FileOperationError(f"[{self.id}] {error_msg}") from e

    def _read_streaming(self, filepath: str, delimiter: str, encoding: str,
                        header_rows: int, footer_rows: int, nrows: Optional[int],
                        text_enclosure: str, escape_char: str, remove_empty_rows: bool,
                        trim_all: bool, use_regex: bool = False) -> Dict[str, Any]:
        """Read file in chunks for memory-efficient processing of large files."""
        logger.info(f"[{self.id}] Streaming read: chunks of {self.chunk_size} rows")

        dtype_dict = self._build_dtype_dict()

        def chunk_generator() -> Iterator[pd.DataFrame]:
            """Generator function that yields processed DataFrame chunks."""

            if self.output_schema:
                skiprows = list(range(header_rows)) if header_rows > 0 else None
                header = None
                column_names = [col['name'] for col in self.output_schema]
                names = column_names
                logger.debug(f"[{self.id}] Streaming with schema: {len(column_names)} columns")
            else:
                skiprows = None
                header = None if header_rows == 0 else list(range(header_rows))
                names = None
                logger.debug(f"[{self.id}] Streaming with file headers")

            engine = 'python' if (footer_rows > 0 or use_regex or skiprows is not None) else 'c'
            quote_params = self._configure_csv_params(text_enclosure, escape_char)

            try:
                read_params = {
                    'filepath_or_buffer': filepath,
                    'sep': delimiter,
                    'encoding': encoding,
                    'header': header,
                    'names': names,
                    'skiprows': skiprows,
                    'nrows': nrows,
                    'skipfooter': footer_rows,
                    'engine': engine,
                    'chunksize': self.chunk_size,
                    'iterator': True,
                    **quote_params
                }

                if use_regex:
                    read_params['regex'] = True

                if dtype_dict:
                    read_params['dtype'] = dtype_dict

                chunk_reader = pd.read_csv(**read_params)

                total_rows = 0
                chunk_num = 0

                for chunk in chunk_reader:
                    chunk_num += 1

                    if self.output_schema and names:
                        if len(names) == len(chunk.columns):
                            chunk.columns = names
                        else:
                            logger.warning(f"[{self.id}] Chunk {chunk_num}: column count mismatch")

                    chunk = self._post_process_dataframe(chunk, trim_all, remove_empty_rows)

                    if self.output_schema:
                        chunk = self.validate_schema(chunk, self.output_schema)

                    chunk_rows = len(chunk)
                    total_rows += chunk_rows
                    self._update_stats(chunk_rows, chunk_rows, 0)

                    logger.debug(f"[{self.id}] Chunk {chunk_num}: {chunk_rows} rows processed")
                    yield chunk

                logger.info(f"[{self.id}] Streaming complete: {total_rows} total rows from '{filepath}'")

            except Exception as e:
                error_msg = f"Streaming read failed for '{filepath}': {str(e)}"
                logger.error(f"[{self.id}] {error_msg}")
                raise FileOperationError(f"[{self.id}] {error_msg}") from e

        return {
            'main': chunk_generator(),
            'is_streaming': True
        }

    def _configure_csv_params(self, text_enclosure: str, escape_char: str) -> Dict[str, Any]:
        """Configure pandas CSV parsing parameters for quoting and escaping."""
        if not text_enclosure or len(text_enclosure) != 1:
            logger.warning(f"[{self.id}] Invalid text_enclosure '{text_enclosure}': disabling quoting")
            return {'quoting': csv.QUOTE_NONE}

        if escape_char and escape_char == text_enclosure:
            quote_params = {
                'quotechar': text_enclosure,
                'doublequote': True
            }
            logger.debug(f"[{self.id}] CSV config: double-quote mode with '{text_enclosure}'")
        else:
            quote_params = {
                'quotechar': text_enclosure,
                'escapechar': escape_char if escape_char else None
            }
            logger.debug(f"[{self.id}] CSV config: escape mode, quote='{text_enclosure}', " f"escape='{escape_char}'")

        return quote_params

    def _post_process_dataframe(self, df: pd.DataFrame, trim_all: bool,
                                remove_empty_rows: bool) -> pd.DataFrame:
        """Apply post-processing operations to DataFrame."""
        if trim_all:
            string_columns = df.select_dtypes(include=['object']).columns
            if len(string_columns) > 0:
                for col in string_columns:
                    df[col] = df[col].str.strip()
                logger.debug(f"[{self.id}] Trimmed {len(string_columns)} string columns")

        if remove_empty_rows:
            rows_before = len(df)
            df = df.dropna(how='all')
            rows_removed = rows_before - len(df)
            if rows_removed > 0:
                logger.debug(f"[{self.id}] Removed {rows_removed} empty rows")

        string_columns = df.select_dtypes(include=['object']).columns
        if len(string_columns) > 0:
            for col in string_columns:
                df[col] = df[col].fillna("")

        if self.output_schema:
            for col_def in self.output_schema:
                col_name = col_def['name']
                col_type = col_def.get('type', 'id_String')
                if col_type in ('id_BigDecimal', 'Decimal') and col_name in df.columns:
                    df[col_name] = df[col_name].apply(
                        lambda x: Decimal(str(x)) if pd.notna(x) and str(x).strip() else None
                    )
                    logger.debug(f"[{self.id}] Converted column '{col_name}' to Decimal type")

        return df
