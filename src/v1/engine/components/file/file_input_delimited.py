"""
tFileInputDelimited component - Read delimited files
"""
import pandas as pd
import os
from typing import Dict, Any, Optional, Iterator
from decimal import Decimal
import logging
import csv  # Add this import at the top of the file
from ...base_component import BaseComponent, ExecutionMode

logger = logging.getLogger(__name__)


class FileInputDelimited(BaseComponent):
    """
    Read delimited files (CSV, TSV, etc.).
    Equivalent to Talend's tFileInputDelimited component.
    """

    def _build_dtype_dict(self) -> Optional[Dict[str, str]]:
        """
        Build dtype dictionary from output schema for pd.read_csv()

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
            'id_Boolean': 'bool',    # Read as object, convert later
            'id_Date': 'object',     # Read as object, convert later
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

        return dtype_dict

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Read delimited file and return a DataFrame
        """
        # Get configuration with proper type conversion
        filepath = self.config.get('filepath', '')
        delimiter = self.config.get('delimiter', ',')
        row_separator = self.config.get('row_separator', None)
        encoding = self.config.get('encoding', 'UTF-8')

        # Convert numeric parameters to int to avoid string/int comparison errors
        try:
            header_rows = int(self.config.get('header_rows', 0))
        except (ValueError, TypeError):
            header_rows = 0

        try:
            footer_rows = int(self.config.get('footer_rows', 0))
        except (ValueError, TypeError):
            footer_rows = 0

        limit = self.config.get('limit', '')
        remove_empty_rows = self.config.get('remove_empty_rows', False)
        text_enclosure = self.config.get('text_enclosure', '"')
        escape_char = self.config.get('escape_char', '\\')
        trim_all = self.config.get('trim_all', False)
        die_on_error = self.config.get('die_on_error', True)

        # Special case: If both delimiter and row_separator are empty, read file as a single string
        if (delimiter in [None, '', '""']) and (row_separator in [None, '', '""']):
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    file_content = f.read()
                # Use first column name from output schema or default to 'doc'
                if self.output_schema and len(self.output_schema) > 0:
                    column_name = self.output_schema[0]['name']
                else:
                    column_name = 'doc'
                df = pd.DataFrame([{column_name: file_content}])
                self._update_stats(1, 1, 0)
                logger.info(f"Component {self.id}: Read XML as single string from {filepath}")
                logger.debug(f"Component {self.id}: XML as string, DataFrame shape: {df.shape} columns: {df.columns}")
                return {'main': df}
            except Exception as e:
                error_msg = f"Error reading file {filepath} as single string: {str(e)}"
                if die_on_error:
                    raise RuntimeError(error_msg)
                else:
                    logger.error(f"Component {self.id}: {error_msg}")
                    self._update_stats(0, 0, 0)
                    return {'main': pd.DataFrame()}

        # Handle multi-character delimiter (regex) and tab shortcut
        use_regex = False
        if delimiter == "\\t" or delimiter == "\t":
            delimiter = "\t"  # pandas supports tab as '\t'
        elif len(delimiter) > 1:
            delimiter = rf"{delimiter}"
            use_regex = True

        # Convert limit to int or None
        nrows = None
        if limit and str(limit).strip():
            try:
                nrows = int(limit)
            except ValueError:
                pass

        if not filepath:
            raise ValueError(f"Component {self.id}: filepath is required")

        # Check if file exists
        if not os.path.exists(filepath):
            error_msg = f"Input file not found: {filepath}"
            if die_on_error:
                raise FileNotFoundError(error_msg)
            else:
                logger.warning(f"Component {self.id}: {error_msg}")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

        try:
            # Check file size for execution mode
            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)

            # If file is large and we're in hybrid mode, switch to streaming
            if (self.execution_mode == ExecutionMode.HYBRID and 
                file_size_mb > self.MEMORY_THRESHOLD_MB):
                return self._read_streaming(filepath, delimiter, encoding, header_rows, 
                                            footer_rows, nrows, text_enclosure, escape_char,
                                            remove_empty_rows, trim_all, use_regex)
            else:
                return self._read_batch(filepath, delimiter, encoding, header_rows, 
                                            footer_rows, nrows, text_enclosure, escape_char,
                                            remove_empty_rows, trim_all, use_regex)

        except Exception as e:
            error_msg = f"Error reading file {filepath}: {str(e)}"
            if die_on_error:
                raise RuntimeError(error_msg)
            else:
                logger.error(f"Component {self.id}: {error_msg}")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

    def _read_batch(self,filepath: str,delimiter: str,encoding: str,
                    header_rows: int,footer_rows: int,nrows: Optional[int],
                    text_enclosure: str, escape_char: str, remove_empty_rows: bool,
                    trim_all: bool, use_regex: bool = False) -> Dict[str, Any]:
        """Read entire file at once"""

        # Determine header parameter for pandas
        # If schema is provided, skip header rows and set names from schema
        # Otherwise, use header from file
        if self.output_schema:
            skiprows = list(range(header_rows)) if header_rows > 0 else None
            header = None
            # Set column names during read so dtype parameter works correctly
            column_names = [col['name'] for col in self.output_schema]
            names = column_names
        else:
            skiprows = None
            header = None if header_rows == 0 else list(range(header_rows))
            names = None

        # Build dtype dictionary from schema to enforce column types during read
        # Must be built AFTER names are determined so keys match
        dtype_dict = self._build_dtype_dict()
        columns_to_keep = list(dtype_dict.keys())
        # Determine engine
        engine = 'python' if (footer_rows > 0 or use_regex or skiprows is not None) else 'c'

        # Validate text_enclosure and escape_char
        if not text_enclosure or len(text_enclosure) != 1:
            logger.warning(f"Component {self.id}: Invalid text_enclosure '{text_enclosure}'")
            quote_params = {
                'quoting': csv.QUOTE_NONE  # Use the correct csv module
            }
        else:
            if escape_char and escape_char == text_enclosure:
                quote_params = {
                    'quotechar': text_enclosure,
                    'doublequote': True
                }
            else:
                quote_params = {
                    'quotechar': text_enclosure,
                    'escapechar': escape_char if escape_char else None
                }

        # Read the file
        df = pd.read_csv(
            filepath,
            sep=delimiter,
            encoding=encoding,
            header=header,
            names=names,
            skiprows=skiprows,
            nrows=nrows,
            skipfooter=footer_rows,
            engine=engine,
            keep_default_na=False,
            **quote_params,
            # Only pass regex param if using regex
            **({'regex': True} if use_regex else {}),
            usecols=columns_to_keep,
            dtype=dtype_dict  # Enforce types from schema during read
        )
        pd.set_option('display.max_rows', None)
        logger.debug(f"{df.head(1).T}")
        pd.reset_option('display.max_rows')
        # Validate column count matches schema
        if self.output_schema:
            expected_cols = len(self.output_schema)
            actual_cols = len(df.columns)
            if expected_cols != actual_cols:
                logger.warning(
                    f"Component {self.id}: Schema defines {expected_cols} columns "
                    f"but file has {actual_cols} columns. Data may be misaligned."
                )

        # Trim all string columns if requested
        if trim_all:
            string_columns = df.select_dtypes(include=['object']).columns
            for col in string_columns:
                df[col] = df[col].str.strip()

        # Remove empty rows if requested
        if remove_empty_rows:
            df = df.dropna(how='all')

        # Replace NaN values in string columns with empty strings
        string_columns = df.select_dtypes(include=['object']).columns
        for col in string_columns:
            df[col] = df[col].fillna("")

        # Convert BigDecimal columns from string to Decimal
        if self.output_schema:
            for col_def in self.output_schema:
                col_name = col_def['name']
                col_type = col_def.get('type', 'id_String')
                if col_type in ('id_BigDecimal', 'Decimal') and col_name in df.columns:
                    df[col_name] = df[col_name].apply(lambda x: Decimal(str(x)) if pd.notna(x) else x)

        # Validate schema
        if self.output_schema:
            df = self.validate_schema(df, self.output_schema)

        # Update statistics
        rows_read = len(df)
        self._update_stats(rows_read, rows_read, 0)

        logger.info(f"Component {self.id}: Read {rows_read} rows from {filepath}")
        # logger.info(f"Component {self.id}: schema {df.columns.tolist()}")

        # Log data types for all columns
        dtypes_info = {col: str(dtype) for col, dtype in df.dtypes.items()}
        logger.debug(f"Component {self.id}: column dtypes: {dtypes_info}")

        return {'main': df}

    def _read_streaming(self, filepath: str, delimiter: str, encoding: str,
                        header_rows: int, footer_rows: int, nrows: Optional[int],
                        text_enclosure: str, escape_char: str, remove_empty_rows: bool,
                        trim_all: bool, use_regex: bool = False) -> Dict[str, Any]:
        """Read file in chunks"""

        logger.info(f"Component {self.id}: Reading file in streaming mode (chunks of {self.CHUNK_SIZE})")

        # Build dtype dictionary from schema to enforce column types during read
        dtype_dict = self._build_dtype_dict()

        # Create chunk iterator
        def chunk_generator() -> Iterator[pd.DataFrame]:
            # Determine header parameter
            # If schema is provided, skip header rows and set names from schema
            if self.output_schema:
                skiprows = list(range(header_rows)) if header_rows > 0 else None
                header = None
            else:
                skiprows = None
                header = None if header_rows == 0 else list(range(header_rows))

            # Determine engine
            engine = 'python' if (footer_rows > 0 or use_regex or skiprows is not None) else 'c'

            # Read in chunks
            chunk_reader = pd.read_csv(
                filepath,
                sep=delimiter,
                encoding=encoding,
                header=header,
                skiprows=skiprows,
                nrows=nrows,
                skipfooter=footer_rows,
                engine=engine,
                quotechar=text_enclosure,
                escapechar=escape_char if escape_char else None,
                chunksize=self.chunk_size,
                iterator=True,
                **({'regex': True} if use_regex else {}),
                dtype=dtype_dict  # Enforce types from schema during read
            )

            total_rows = 0
            for chunk in chunk_reader:
                # Set column names from schema
                if self.output_schema:
                    column_names = [col['name'] for col in self.output_schema]
                    if len(column_names) == len(chunk.columns):
                        chunk.columns = column_names

                # Trim all string columns if requested
                if trim_all:
                    string_columns = chunk.select_dtypes(include=['object']).columns
                    for col in string_columns:
                        chunk[col] = chunk[col].str.strip()

                # Remove empty rows if requested
                if remove_empty_rows:
                    chunk = chunk.dropna(how='all')

                # Validate schema
                if self.output_schema:
                    chunk = self.validate_schema(chunk, self.output_schema)

                # Update statistics
                chunk_rows = len(chunk)
                total_rows += chunk_rows
                self._update_stats(chunk_rows, chunk_rows, 0)

                yield chunk

            logger.info(f"Component {self.id}: Read {total_rows} total rows from {filepath}")

        # Return generator for streaming
        return {
            'main': chunk_generator(),
            'is_streaming': True
            }
