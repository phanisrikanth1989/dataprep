"""
tFileInputPositional component - Read fixed-width (positional) files.

Talend equivalent: tFileInputPositional
"""
import logging
import os
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent, ExecutionMode
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError, ComponentExecutionError

logger = logging.getLogger(__name__)

# Non-printable byte scrubber.
# Positional files may contain raw bytes (e.g. 0x00-0x1F, 0x7F-0x9F) or
# unmappable codepoints that decode to U+FFFD when the file's declared
# encoding (default ISO-8859-15) cannot represent the byte. Such characters
# survive into string columns and later cause ``Wrapping � failed`` /
# ``Wrapping <bad-row> failed`` errors when the row is marshalled across
# the Py4J bridge to the Java engine (e.g. by tMap's globalMap / context
# payload).
#
# We replace each offending codepoint with a single space -- this preserves
# row count and column count, never alters positional field alignment, and is
# the same scrub pattern used by ``file_input_delimited.py``.
_NON_PRINTABLE_RE = re.compile(r'[^\x20-\x7E\t\n\r]')

# Decode error policy for all file reads.
# Talend reads through java.io.InputStreamReader, which defaults to
# CodingErrorAction.REPLACE: bytes that are malformed or unmappable in the
# declared charset become U+FFFD instead of raising. Python's open()/read_fwf
# default to "strict" and raise UnicodeDecodeError, so a job that ran cleanly
# in Talend (e.g. a file with extended bytes declared as US-ASCII) would hard
# crash here. Using "replace" matches Talend byte-for-byte: one replacement
# char per bad byte, so positional field alignment is preserved (unlike
# "ignore", which drops bytes and shifts columns). The resulting U+FFFD is
# then scrubbed to a space by _NON_PRINTABLE_RE before the row crosses the
# Py4J bridge.
_DECODE_ERRORS = "replace"


@REGISTRY.register("FileInputPositional", "tFileInputPositional")
class FileInputPositional(BaseComponent):
    """
    Read fixed-width (positional) files.
    Equivalent to Talend's tFileInputPositional component.

    Configuration:
        filepath (str): Path to the input file. Required.
        pattern (str): Comma-separated field widths (e.g., "5,4,5"). Required.
        row_separator (str): Row separator. Default: '\n'
        pattern_units (str): Pattern units. Default: 'SYMBOLS'
        remove_empty_row (bool): Skip empty rows. Default: False
        trim_all (bool): Trim all fields. Default: False
        encoding (str): File encoding. Default: 'UTF-8'
        header_rows (int): Number of header rows to skip. Default: 0
        footer_rows (int): Number of footer rows to skip. Default: 0
        limit (int): Max rows to read. Default: None
        die_on_error (bool): Stop on error. Default: True
        advanced_separator (bool): Use advanced separators. Default: False
        thousands_separator (str): Thousands separator. Default: ','
        decimal_separator (str): Decimal separator. Default: '.'
        check_date (bool): Check date format. Default: False
        uncompress (bool): Uncompress file (not implemented). Default: False
    Inputs:
        None

    Outputs:
        main: Primary output DataFrame with parsed positional data

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully processed
        NB_LINE_REJECT: Rows rejected (always 0 for this component)

    Example:
        config = {
            "filepath": "input.txt",
            "pattern": "5,4,5",
            "encoding": "ISO-8859-15"
        }
        component = FileInputPositional("comp_1", config)
        result = component.execute()

    Notes:
        - File must exist and be readable
        - Pattern defines fixed column widths in characters
        - Schema validation is performed if output_schema is provided
    """

    # Class constants
    DEFAULT_ENCODING = 'ISO-8859-15'
    DEFAULT_ROW_SEPARATOR = '\n'
    DEFAULT_PATTERN_UNITS = 'SYMBOLS'
    DEFAULT_THOUSANDS_SEPARATOR = ','
    DEFAULT_DECIMAL_SEPARATOR = '.'
    DEFAULT_HEADER_ROWS = 0
    DEFAULT_FOOTER_ROWS = 0
    DEFAULT_REMOVE_EMPTY_ROW = True
    DEFAULT_TRIM_ALL = True
    DEFAULT_DIE_ON_ERROR = False
    DEFAULT_ADVANCED_SEPARATOR = False
    DEFAULT_CHECK_DATE = False
    DEFAULT_UNCOMPRESS = False

    def _validate_config(self) -> None:
        """Validate component configuration.

        Raises:
            ConfigurationError: If required config keys are absent or empty.

        Note:
            Pattern parsing and header_rows / footer_rows / limit numeric
            validation are intentionally deferred to _process() after
            context variable resolution. Validating here would crash with
            ValueError on legitimate ${context.WIDTHS}, ${context.ROWS},
            or ${context.LIMIT} references. See file_output_delimited.py
            (CR-06 / quick task 260429-hc2) for the same pattern.
        """
        # Required fields -- key-presence and shape only
        if 'filepath' not in self.config or not self.config.get('filepath', '').strip():
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'filepath'"
            )

        if 'pattern' not in self.config or not self.config.get('pattern', '').strip():
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'pattern'"
            )

    def _build_dtype_dict(self) -> Optional[Dict[str, str]]:
        """
        Build dtype dictionary from output schema for pd.read_fwf()

        Returns:
            Dict mapping column names to pandas dtypes, or None if no schema
        """
        if not self.output_schema:
            return None

        # Type mapping from Talend to pandas dtype strings
        type_mapping = {
            'id_String': 'object',
            'id_Integer': 'Int64',  # Nullable integer
            'id_Long': 'Int64',
            'id_Float': 'float64',
            'id_Double': 'float64',
            'id_Boolean': 'object',  # Read as object, convert later
            'id_Date': 'object',     # Read as object, convert later
            'id_BigDecimal': 'object',  # Read as string, convert to Decimal later
            # Simple type names
            'str': 'object',
            'int': 'Int64',
            'long': 'Int64',
            'float': 'float64',
            'double': 'float64',
            'bool': 'object',
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
        Process fixed-width file input.

        Args:
            input_data: Input DataFrame (not used for input components)

        Returns:
            Dictionary containing:
                - 'main': Processed DataFrame with positional data

        Raises:
            ConfigurationError: If required configuration is missing
            FileOperationError: If file cannot be read
            ComponentExecutionError: If processing fails
        """
        # Handle empty input (not applicable for input components)
        if input_data is not None:
            logger.debug(f"[{self.id}] Input data provided but not used for file input component")

        # Get configuration with defaults using class constants
        filepath = self.config.get('filepath', '')
        row_separator = self.config.get('row_separator', self.DEFAULT_ROW_SEPARATOR)
        pattern = self.config.get('pattern', '')
        pattern_units = self.config.get('pattern_units', self.DEFAULT_PATTERN_UNITS)
        remove_empty_row = self.config.get('remove_empty_row', self.DEFAULT_REMOVE_EMPTY_ROW)
        trim_all = self.config.get('trim_all', self.DEFAULT_TRIM_ALL)
        encoding = self.config.get('encoding', self.DEFAULT_ENCODING)
        # Numeric / pattern fields validated post-resolution -- see _validate_config note.
        header_rows_raw = self.config.get('header_rows', self.DEFAULT_HEADER_ROWS)
        try:
            header_rows = int(header_rows_raw)
        except (ValueError, TypeError) as e:
            raise ConfigurationError(
                f"[{self.id}] Config 'header_rows' must be an integer"
            ) from e
        if header_rows < 0:
            raise ConfigurationError(
                f"[{self.id}] Config 'header_rows' must be non-negative"
            )

        footer_rows_raw = self.config.get('footer_rows', self.DEFAULT_FOOTER_ROWS)
        try:
            footer_rows = int(footer_rows_raw)
        except (ValueError, TypeError) as e:
            raise ConfigurationError(
                f"[{self.id}] Config 'footer_rows' must be an integer"
            ) from e
        if footer_rows < 0:
            raise ConfigurationError(
                f"[{self.id}] Config 'footer_rows' must be non-negative"
            )

        limit = self.config.get('limit', '')
        die_on_error = self.config.get('die_on_error', self.DEFAULT_DIE_ON_ERROR)
        advanced_separator = self.config.get('advanced_separator', self.DEFAULT_ADVANCED_SEPARATOR)
        thousands_separator = self.config.get('thousands_separator', self.DEFAULT_THOUSANDS_SEPARATOR)
        decimal_separator = self.config.get('decimal_separator', self.DEFAULT_DECIMAL_SEPARATOR)
        check_date = self.config.get('check_date', self.DEFAULT_CHECK_DATE)
        uncompress = self.config.get('uncompress', self.DEFAULT_UNCOMPRESS)

        logger.info("[%s] Processing started: reading file %s", self.id, filepath)

        # Parse limit (deferred from _validate_config -- may resolve from ${context.LIMIT})
        nrows = None
        if limit and str(limit).strip():
            try:
                nrows = int(limit)
            except (ValueError, TypeError) as e:
                raise ConfigurationError(
                    f"[{self.id}] Config 'limit' must be an integer"
                ) from e
            if nrows <= 0:
                raise ConfigurationError(
                    f"[{self.id}] Config 'limit' must be positive"
                )
            logger.debug("[%s] Row limit set: %d", self.id, nrows)

        # Validate required parameters
        if not filepath:
            raise ConfigurationError("Missing required config: 'filepath'")
        if not pattern:
            raise ConfigurationError("Missing required config: 'pattern'")

        # Check file existence
        if not os.path.exists(filepath):
            error_msg = f"Input file not found: {filepath}"
            if die_on_error:
                logger.error("[%s] File not found: %s", self.id, filepath)
                raise FileOperationError(error_msg)
            else:
                logger.warning("[%s] File not found: %s, returning empty result", self.id, filepath)
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

        # Parse pattern to list of widths (deferred from _validate_config --
        # may resolve from ${context.WIDTHS})
        try:
            widths = [int(x.strip()) for x in pattern.split(',') if x.strip()]
        except ValueError as e:
            raise ConfigurationError(
                f"[{self.id}] Config 'pattern' must be comma-separated integers, got: {pattern}"
            ) from e
        if not widths:
            raise ConfigurationError(
                f"[{self.id}] Config 'pattern' cannot be empty"
            )
        if any(w <= 0 for w in widths):
            raise ConfigurationError(
                f"[{self.id}] Config 'pattern' must contain positive integers"
            )
        logger.debug("[%s] Parsed column widths: %s", self.id, widths)

        # Extract column names from schema if available
        names = None
        if self.output_schema:
            names = [col['name'] for col in self.output_schema]

        # Build dtype dictionary from schema to enforce column types during read
        dtype_dict = self._build_dtype_dict()

        try:
            logger.debug("[%s] Reading fixed-width file with pandas read_fwf", self.id)

            # Read file as fixed-width
            df = pd.read_fwf(
                filepath,
                widths=widths,
                encoding=encoding,
                encoding_errors=_DECODE_ERRORS,
                header=None,
                names=names,
                skiprows=header_rows,
                nrows=nrows,
                skipfooter=footer_rows,
                engine='python' if footer_rows > 0 else None,
                dtype=dtype_dict
            )

            rows_in = len(df)
            logger.debug("[%s] Read %d raw rows from file", self.id, rows_in)

            # Sanitize non-printable characters in string columns.
            # Positional files may contain raw bytes (e.g. 0x00-0x1F, 0x7F-0x9F)
            # that decode to U+FFFD or other non-printable chars, causing Java
            # bridge failures ("Wrapping \ufffd failed").
            # Replace them with spaces to preserve positional alignment.
            # See module-level _NON_PRINTABLE_RE / _DECODE_ERRORS for details.
            string_cols = df.select_dtypes(include=['object']).columns
            for col in string_cols:
                df[col] = df[col].apply(
                    lambda x: _NON_PRINTABLE_RE.sub(' ', x) if isinstance(x, str) else x
                )
            # Trim all string columns if requested
            if trim_all:
                logger.debug("[%s] Trimming all string columns", self.id)
                string_columns = df.select_dtypes(include=['object']).columns
                for col in string_columns:
                    df[col] = df[col].str.strip()

            # Remove empty rows if requested.
            # Must check both NaN (pre-trim) and empty-string (post-trim) -- BUG-FIP-004.
            if remove_empty_row:
                initial_count = len(df)
                # Replace empty strings with NaN so dropna covers both cases
                string_columns_for_drop = df.select_dtypes(include=['object']).columns
                df[string_columns_for_drop] = df[string_columns_for_drop].replace('', pd.NA)
                df = df.dropna(how='all')
                # Restore empty string (NaN fill happens below)
                removed_count = initial_count - len(df)
                if removed_count > 0:
                    logger.debug("[%s] Removed %d empty rows", self.id, removed_count)
            # Replace NaN in string columns with empty string
            string_columns = df.select_dtypes(include=['object']).columns
            df[string_columns] = df[string_columns].fillna('')
            # Advanced separator: apply only to numeric-typed schema columns -- BUG-FIP-002.
            # Applying to all object columns would corrupt string data.
            if advanced_separator:
                logger.debug("[%s] Applying advanced separators to numeric columns", self.id)
                numeric_col_names: set[str] = set()
                if self.output_schema:
                    _NUMERIC_TYPES = {
                        'id_Float', 'id_Double', 'id_BigDecimal',
                        'float', 'double', 'decimal', 'Decimal',
                    }
                    numeric_col_names = {
                        c['name'] for c in self.output_schema
                        if c.get('type', '') in _NUMERIC_TYPES
                    }
                for col in df.select_dtypes(include=['object']).columns:
                    if col in numeric_col_names:
                        df[col] = df[col].str.replace(thousands_separator, '', regex=False)
                        df[col] = df[col].str.replace(decimal_separator, '.', regex=False)

            # Check date columns if requested
            if check_date and self.output_schema:
                logger.debug("[%s] Converting date columns", self.id)
                for col in self.output_schema:
                    if col.get('type', '').lower() in ('id_date', 'date'):
                        pattern = col.get('date_pattern') or col.get('pattern')
                        fmt = pattern if pattern else None
                        try:
                            df[col['name']] = pd.to_datetime(
                                df[col['name']], format=fmt, errors='coerce'
                            )
                        except Exception:
                            pass

            # Convert BigDecimal columns from string to Decimal
            if self.output_schema:
                for col_def in self.output_schema:
                    col_name = col_def['name']
                    col_type = col_def.get('type', 'id_String')
                    if col_type in ('id_BigDecimal', 'Decimal') and col_name in df.columns:
                        logger.debug("[%s] Converting column %s to Decimal", self.id, col_name)
                        df[col_name] = df[col_name].apply(
                            lambda x: Decimal(str(x)) if pd.notna(x) and str(x).strip() else None
                        )

            # Calculate final statistics
            rows_out = len(df)
            rows_rejected = 0  # This component doesn't reject rows

            # Update statistics
            self._update_stats(rows_in, rows_out, rows_rejected)

            logger.info(
                "[%s] Processing complete: in=%d, out=%d, rejected=%d",
                self.id, rows_in, rows_out, rows_rejected,
            )
            logger.debug("[%s] Output columns: %s", self.id, df.columns.tolist())

            # Log data types for debugging
            if logger.isEnabledFor(logging.DEBUG):
                dtypes_info = {col: str(dtype) for col, dtype in df.dtypes.items()}
                logger.debug("[%s] Column dtypes: %s", self.id, dtypes_info)

            return {'main': df}

        except FileOperationError:
            # Re-raise file operation errors
            raise
        except ConfigurationError:
            # Re-raise configuration errors
            raise
        except Exception as e:
            error_msg = f"Error reading positional file {filepath}: {str(e)}"
            logger.error("[%s] Processing failed: %s", self.id, e)

            if die_on_error:
                raise ComponentExecutionError(self.id, error_msg, e)
            else:
                logger.warning(f"[{self.id}] Returning empty result due to error with die_on_error=False")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}