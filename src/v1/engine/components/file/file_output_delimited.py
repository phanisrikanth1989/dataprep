"""
FileOutputDelimited - Write delimited files (CSV, TSV, etc.).

Talend equivalent: tFileOutputDelimited

This component writes DataFrame data to delimited text files with configurable
formatting options. Supports various delimiters, encodings, and output modes.
Handles empty data according to Talend behavior (creates header-only files).
"""
import logging
import os
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


class FileOutputDelimited(BaseComponent):
    """
    Write DataFrame data to delimited text files with configurable formatting.

    This component outputs data in various delimited formats (CSV, TSV, pipe-separated, etc.)
    with support for custom delimiters, encodings, and text enclosures. Handles streaming
    data and provides Talend-compatible empty file behavior.

        Configuration:
            filepath (str): Output file path. Required. Supports context variables.
            delimiter (str): Field delimiter character. Default: ','
            encoding (str): File encoding. Default: 'UTF-8'
            include_header (bool): Include column headers. Default: True
            append (bool): Append to existing file. Default: False
            text_enclosure (str): Quote character for text fields. Default: None (no quoting)
            create_directory (bool): Create parent directories if needed. Default: True
            delete_empty_file (bool): Delete file if no data rows written. Default: False
            die_on_error (bool): Fail on errors vs. continue. Default: True
            row_separator (str): Row separator. Default: '\n'
            output_schema (List[str]): Column names to output in order. Optional.

        Inputs:
            main: DataFrame to write to file

        Outputs:
            main: Pass-through of input DataFrame (for flow continuation)

        Statistics:
            NB_LINE: Total rows written
            NB_LINE_OK: Successfully written rows
            NB_LINE_REJECT: Failed rows (0 for this component)

        Example:
            config = {
                "filepath": "/data/output.csv",
                "delimiter": ",",
                "encoding": "UTF-8",
                "include_header": True
            }

        Notes:
            - Empty input creates header-only file when include_header=True
            - Special handling for single-column output without delimiter (AT17854)
            - Supports streaming mode for large datasets
            - Text enclosure None disables all quoting (csv.QUOTE_NONE)
    """

        # Class constants for default values
    DEFAULT_DELIMITER = ','
    DEFAULT_ENCODING = 'UTF-8'
    DEFAULT_ROW_SEPARATOR = '\n'
    DEFAULT_ESCAPE_CHAR = '\\'
    QUOTE_NONE = 3      # csv.QUOTE_NONE
    QUOTE_MINIMAL = 1   # csv.QUOTE_MINIMAL

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

        if 'include_header' in self.config:
            if not isinstance(self.config['include_header'], bool):
                errors.append("Config 'include_header' must be boolean")

        if 'append' in self.config:
            if not isinstance(self.config['append'], bool):
                errors.append("Config 'append' must be boolean")

        if 'create_directory' in self.config:
            if not isinstance(self.config['create_directory'], bool):
                errors.append("Config 'create_directory' must be boolean")

        if 'die_on_error' in self.config:
            if not isinstance(self.config['die_on_error'], bool):
                errors.append("Config 'die_on_error' must be boolean")

        if 'output_schema' in self.config:
            schema = self.config['output_schema']
            if not isinstance(schema, list):
                errors.append("Config 'output_schema' must be a list")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
            Write DataFrame to delimited file.

        Args:
            input_data: Input DataFrame to write. May be None or empty.

        Returns:
            Dictionary containing:
                - 'main': Pass-through of input DataFrame

        Raises:
            ConfigurationError: If required configuration is missing
            FileOperationError: If file write operation fails
        """
        # Get configuration with defaults
        filepath = self.config.get('filepath', '')
        delimiter = self.config.get('delimiter', self.DEFAULT_DELIMITER)
        encoding = self.config.get('encoding', self.DEFAULT_ENCODING)
        include_header = self.config.get('include_header', True)
        append = self.config.get('append', False)
        text_enclosure = self.config.get('text_enclosure', None)
        create_directory = self.config.get('create_directory', True)
        delete_empty_file = self.config.get('delete_empty_file', False)
        die_on_error = self.config.get('die_on_error', True)

        if not filepath:
            error_msg = "filepath is required"
            logger.error(f"[{self.id}] Configuration error: {error_msg}")
            if die_on_error:
                raise ConfigurationError(f"[{self.id}] {error_msg}")
            else:
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

        logger.info(f"[{self.id}] Writing started: target file '{filepath}'")
        logger.debug(f"[{self.id}] Configuration: delimiter='{delimiter}', "
                f"encoding='{encoding}', include_header={include_header}, "
                f"text_enclosure='{text_enclosure}'")

        # Handle streaming input
        if isinstance(input_data, Iterator):
            logger.debug(f"[{self.id}] Processing streaming input")
            return self._write_streaming(input_data,filepath,delimiter,encoding,
                include_header,append,text_enclosure,
                create_directory,delete_empty_file,die_on_error)

        # Convert list input to DataFrame if needed
        if isinstance(input_data, list):
            try:
                input_data = pd.DataFrame(input_data)
                logger.debug(f"[{self.id}] Converted list input to DataFrame: {len(input_data)} rows")
            except Exception as e:
                error_msg = f"Failed to convert list to DataFrame: {str(e)}"
                logger.error(f"[{self.id}] Data conversion error: {error_msg}")
            if die_on_error:
                raise FileOperationError(f"[{self.id}] {error_msg}") from e
            else:
                self._update_stats(0, 0, len(input_data) if input_data else 0)
                return {'main': pd.DataFrame()}
            
        # Log input data details for debugging
        if input_data is not None and not input_data.empty:
            logger.debug(f"[{self.id}] Input data shape: {input_data.shape}")
            logger.debug(f"[{self.id}] Input columns: {list(input_data.columns)}")
            if len(input_data) <= 5:
                logger.debug(f"[{self.id}] Input sample:\n{input_data.head()}")

        # Handle empty data - Talend behavior: create header-only file when configured
        if input_data is None or (hasattr(input_data, 'empty') and input_data.empty):
            logger.info(f"[{self.id}] Empty input received: applying Talend empty data behavior")
            return self._handle_empty_data(filepath, encoding, delimiter, include_header,
                                        delete_empty_file, append)
        
        # Create directory if needed
        if create_directory:
            self._ensure_directory_exists(filepath)

        # Normalize delimiter for pandas
        delimiter= self. normalize_delimiter(delimiter)

        # Apply output schema filtering if configured
        input_data = self ._apply_output_schema(input_data)

        try:
            rows_in = len(input_data)

            # Determine file write mode and header behavior
            mode = 'a' if append else 'w'
            write_header = include_header
            if append and os.path.exists(filepath):
                write_header = False
                logger.debug(f"[{self.id}] Appending to existing file: header disabled")

            # Configure quoting behavior based on text_enclosure
            quoting, quotechar = self._configure_quoting(text_enclosure)

            logger.info(f"[{self.id}] Writing file: mode='{mode}', quoting={quoting}, "
                f"header={write_header}")

            # Special case: empty delimiter for single-column output (AT17854 logic)
            if delimiter == "":
                logger.debug(f"[{self.id}] Using manual write for empty delimiter (single column)")
                self._write_single_column(input_data,filepath,mode,encoding)
            else:
            # Standard pandas CSV write
                input_data.to_csv(
                    filepath,
                    sep=delimiter,
                    encoding=encoding,
                    header=write_header,
                    index=False,
                    mode=mode,
                    quotechar=quotechar,
                    quoting=quoting,
                    escapechar=self.DEFAULT_ESCAPE_CHAR
                )

            # Update statistics and log completion
            self._update_stats(rows_in, rows_in, 0)
            logger.info(f"[{self.id}] Writing complete: {rows_in} rows written to '{filepath}'")

            return {'main': input_data}

        except Exception as e:
            error_msg = f"Error writing file '{filepath}': {str(e)}"
            logger.error(f"[{self.id}] File operation failed: {error_msg}")

            if die_on_error:
                raise FileOperationError(f"[{self.id}] {error_msg}") from e
            else:
                rows_in = len(input_data) if input_data is not None else 0
                self._update_stats(rows_in, 0, rows_in)
                return {'main': pd.DataFrame()}

    def _handle_empty_data(self, filepath: str, encoding: str, delimiter: str,
                          include_header: bool, delete_empty_file: bool,
                          append: bool ) -> Dict[str, Any]:
        """
        Handle empty data according to Talend behavior.
        Talend creates empty file with header when include_header=True.
        This logic preserves that behavior (AT17854).
        """

        logger.debug(f"[{self.id}] Handling empty data: include_header={include_header}, "
            f"delete_empty_file={delete_empty_file}")

        # Normalize delimiter and row separator
        if delimiter == '\\t':
            delimiter = '\t'

        row_separator = self.config.get('row_separator',self.DEFAULT_ROW_SEPARATOR)
        if row_separator == '\\n':
            row_separator = '\n'
        elif row_separator == '\\r\\n':
            row_separator = '\r\n'
        elif row_separator == '\\t':
            row_separator = '\t'

        mode = 'a' if append else 'w'

        # Determine header columns from various sources
        output_schema = self._get_output_schema_columns()

        # Write header only if required and schema available
        if include_header and output_schema:
            logger.info(f"[{self.id}] Writing header-only file: {len(output_schema)} columns")
            try:
                with open(filepath, mode, encoding=encoding) as f:
                    f.write(delimiter.join(output_schema) + row_separator)
            except Exception as e:
                logger.error(f"[{self.id}] Failed to write header: {str(e)}")
                raise FileOperationError(f"[{self.id}] Failed to write header: {str(e)}") from e

        # Delete file only if configured AND no header was written
        elif delete_empty_file and (not include_header or not output_schema) and os.path.exists(filepath):
            try:
                os.remove(filepath)
                logger.info(f"[{self.id}] Deleted empty file: '{filepath}'")
            except Exception as e:
                logger.warning(f"[{self.id}] Could not delete empty file '{filepath}': {str(e)}")

        self._update_stats(0, 0, 0)
        return {'main': pd.DataFrame()}
    
    def _write_streaming(self, data_iterator: Iterator[pd.DataFrame], filepath: str,
                         delimiter: str, encoding: str, include_header: bool, 
                         append: bool, text_enclosure: Optional[str], create_directory: bool,
                         delete_empty_file: bool, die_on_error: bool) -> Dict[str, Any]:
        """
        Write data in streaming mode for large datasets.
        
        Args:
            data_iterator: Iterator yielding DataFrame chunks
            filepath: Target file path
            delimiter: Field delimiter
            encoding: File encoding
            include_header: Whether to include header
            append: Whether to append to existing file
            text_enclosure: Quote character
            create_directory: Whether to create parent directories
            delete_empty_file: Whether to delete empty files
            die_on_error: Whether to fail on errors

        Returns:
            Dictionary with empty main DataFrame (streaming mode)
        """
        logger.info(f"[{self.id}] Writing in streaming mode: target '{filepath}'")

        # Create directory if needed
        if create_directory:
            self._ensure_directory_exists(filepath)

        # Normalize delimiter
        delimiter = self._normalize_delimiter(delimiter)

        total_rows = 0
        first_chunk = True

        try:
            for chunk_num, chunk in enumerate(data_iterator, 1):
                if chunk.empty:
                    logger.debug(f"[{self.id}] Skipping empty chunk #{chunk_num}")
                    continue

                # Determine write mode and header for this chunk
                if first_chunk:
                    mode = 'a' if append else 'w'
                    write_header = include_header and not (append and os.path.exists(filepath))
                    first_chunk = False
                    logger.debug(f"[{self.id}] First chunk: mode='{mode}', header={write_header}")
                else:
                    mode = 'a'
                    write_header = False

                # Configure quoting
                quoting, quotechar = self._configure_quoting(text_enclosure)

                # Write chunk
                chunk.to_csv(
                    filepath,
                    sep=delimiter,
                    encoding=encoding,
                    header=write_header,
                    index=False,
                    mode=mode,
                    quotechar=quotechar,
                    quoting=quoting,
                    escapechar=self.DEFAULT_ESCAPE_CHAR
                )

                # Update statistics
                chunk_rows = len(chunk)
                total_rows += chunk_rows
                self._update_stats(chunk_rows, chunk_rows, 0)

                logger.debug(f"[{self.id}] Chunk {chunk_num} written: {chunk_rows} rows")

            # Handle empty result
            if total_rows == 0 and delete_empty_file and os.path.exists(filepath):
                logger.info(f"[{self.id}] No data written: considering file deletion")
                # Note: Keeping original logic - commented out deletion
                # os.remove(filepath)
                logger.info(f"[{self.id}] Empty file deletion skipped: '{filepath}'")
            else:
                logger.info(f"[{self.id}] Streaming write complete: {total_rows} total rows")

            return {'main': pd.DataFrame()}  # Return empty DataFrame for streaming

        except Exception as e:
            error_msg = f"Error in streaming write to '{filepath}': {str(e)}"
            logger.error(f"[{self.id}] Streaming operation failed: {error_msg}")

            if die_on_error:
                raise FileOperationError(f"[{self.id}] {error_msg}") from e
            else:
                return {'main': pd.DataFrame()}
            
    def _ensure_directory_exists(self, filepath: str) -> None:
        """Create parent directories if they don't exist."""
        directory = os.path.dirname(filepath)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                logger.debug(f"[{self.id}] Created directory: '{directory}'")
            except Exception as e:
                logger.error(f"[{self.id}] Failed to create directory '{directory}': {str(e)}")
                raise FileOperationError(f"[{self.id}] Cannot create directory '{directory}': {str(e)}") from e

    def _normalize_delimiter(self, delimiter: str) -> str:
        """Convert delimiter shortcuts to actual characters for pandas."""
        if delimiter == "\\t" or delimiter == "\t":
            return "\t"
        elif len(delimiter) > 1:
            return rf"{delimiter}"
        return delimiter

    def _configure_quoting(self,text_enclosure: Optional[str]) -> tuple:
        """Configure pandas CSV quoting behavior based on text_enclosure setting."""
        if text_enclosure is None:
            # No quoting - disable entirely
            quoting = self.QUOTE_NONE
            quotechar = None
            logger.debug(f"[{self.id}] Quoting disabled: text_enclosure=None")
        else:
            # Quote when needed
            quoting = self.QUOTE_MINIMAL
            quotechar = text_enclosure
            logger.debug(f"[{self.id}] Quoting enabled: text_enclosure='{text_enclosure}'")

        return quoting, quotechar

    def _apply_output_schema(self,df: pd.DataFrame) -> pd.DataFrame:
        """Apply output schema filtering if configured."""
        output_schema = self.config.get('output_schema')

        if not output_schema:
            # Try alternative schema sources
            if hasattr(self, 'output_schema') and self.output_schema:
                output_schema = [col['name'] for col in self.output_schema]
            elif hasattr(self, 'schema') and self.schema and 'output' in self.schema:
                output_schema = [col['name'] for col in self.schema['output']]

        if output_schema and isinstance(df, pd.DataFrame):
            # Filter and reorder columns according to schema
            available_cols = [col for col in output_schema if col in df.columns]
            if available_cols != list(df.columns):
                logger.debug(f"[{self.id}] Applying output schema: "f"{len(available_cols)} of "
                             f"{len(output_schema)} columns available")
                df = df[available_cols]

        return df
    
    def _get_output_schema_columns(self) -> List[str]:
        """Get output column names from various schema sources."""
        # Try config first
        output_schema = self.config.get('output_schema')
        if output_schema:
            return output_schema

        # Try component schema attributes
        if hasattr(self, 'output_schema') and self.output_schema:
            return [col['name'] for col in self.output_schema]
        elif hasattr(self, 'schema') and self.schema and 'output' in self.schema:
            return [col['name'] for col in self.schema['output']]

        # No schema available
        return []

    def _write_single_column(self,df: pd.DataFrame,filepath: str,mode: str,encoding: str) -> None:
        """
        Handle special case of single-column output without delimiter (AT17854 logic).

        When delimiter is empty, write each row as a single string, one per line.
        This preserves the original AT17854 functionality.
        """
        row_separator = self.config.get('row_separator',self.DEFAULT_ROW_SEPARATOR)
        logger.debug(f"[{self.id}] Single column write: {len(df)} rows, "f"row_separator='{row_separator}'")

        try:
            with open(filepath, mode, encoding=encoding) as f:
                for value in df.iloc[:, 0]:  # First column only
                    f.write(f"{value}{row_separator}")
        except Exception as e:
            raise FileOperationError(f"[{self.id}] Failed single column write: {str(e)}") from e
        