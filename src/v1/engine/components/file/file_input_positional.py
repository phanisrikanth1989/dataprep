"""
tFileInputPositional component - Read fixed-width (positional) files.

Talend equivalent: tFileInputPositional
"""
import logging
import os
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent, ExecutionMode
from ...exceptions import ConfigurationError, FileOperationError, ComponentExecutionError

logger = logging.getLogger(__name__)

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
    DEFAULT_ENCODING = 'UTF-8'
    DEFAULT_ROW_SEPARATOR = '\n'
    DEFAULT_PATTERN_UNITS = 'SYMBOLS'
    DEFAULT_THOUSANDS_SEPARATOR = ','
    DEFAULT_DECIMAL_SEPARATOR = '.'
    DEFAULT_HEADER_ROWS = 0
    DEFAULT_FOOTER_ROWS = 0
    DEFAULT_REMOVE_EMPTY_ROWS = False
    DEFAULT_TRIM_ALL = False
    DEFAULT_DIE_ON_ERROR = True
    DEFAULT_ADVANCED_SEPARATOR = False
    DEFAULT_CHECK_DATE = False
    DEFAULT_UNCOMPRESS = False

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        if 'filepath' not in self.config or not self.config.get('filepath', '').strip():
            errors.append("Missing required config: 'filepath'")

        if 'pattern' not in self.config or not self.config.get('pattern', '').strip():
            errors.append("Missing required config: 'pattern'")
        else:
            # Validate pattern format
            pattern = self.config['pattern']
            try:
                widths = [int(x.strip()) for x in pattern.split(',') if x.strip()]
                if not widths:
                    errors.append("Config 'pattern' cannot be empty")
                elif any(w <= 0 for w in widths):
                    errors.append("Config 'pattern' must contain positive integers")
            except ValueError:
                errors.append(f"Config 'pattern' must be comma-separated integers, got: {pattern}")

        # Optional field validation
        if 'header_rows' in self.config:
            try:
                header_rows = int(self.config['header_rows'])
                if header_rows < 0:
                    errors.append("Config 'header_rows' must be non-negative")
            except (ValueError, TypeError):
                errors.append("Config 'header_rows' must be an integer")

        if 'footer_rows' in self.config:
            try:
                footer_rows = int(self.config['footer_rows'])
                if footer_rows < 0:
                    errors.append("Config 'footer_rows' must be non-negative")
            except (ValueError, TypeError):
                errors.append("Config 'footer_rows' must be an integer")

        if 'limit' in self.config:
            limit = self.config['limit']
            if limit and str(limit).strip():
                try:
                    limit_val = int(limit)
                    if limit_val <= 0:
                        errors.append("Config 'limit' must be positive")
                except ValueError:
                    errors.append("Config 'limit' must be an integer")

        return errors

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
        remove_empty_row = self.config.get('remove_empty_row', self.DEFAULT_REMOVE_EMPTY_ROWS)
        trim_all = self.config.get('trim_all', self.DEFAULT_TRIM_ALL)
        encoding = self.config.get('encoding', self.DEFAULT_ENCODING)
        header_rows = int(self.config.get('header_rows', self.DEFAULT_HEADER_ROWS))
        footer_rows = int(self.config.get('footer_rows', self.DEFAULT_FOOTER_ROWS))
        limit = self.config.get('limit', '')
        die_on_error = self.config.get('die_on_error', self.DEFAULT_DIE_ON_ERROR)
        advanced_separator = self.config.get('advanced_separator', self.DEFAULT_ADVANCED_SEPARATOR)
        thousands_separator = self.config.get('thousands_separator', self.DEFAULT_THOUSANDS_SEPARATOR)
        decimal_separator = self.config.get('decimal_separator', self.DEFAULT_DECIMAL_SEPARATOR)
        check_date = self.config.get('check_date', self.DEFAULT_CHECK_DATE)
        uncompress = self.config.get('uncompress', self.DEFAULT_UNCOMPRESS)

        logger.info(f"[{self.id}] Processing started: reading file {filepath}")

        # Parse limit
        nrows = None
        if limit and str(limit).strip():
            try:
                nrows = int(limit)
                logger.debug(f"[{self.id}] Row limit set: {nrows}")
            except ValueError:
                logger.warning(f"[{self.id}] Invalid limit value: {limit}, ignoring")

        # Validate required parameters
        if not filepath:
            raise ConfigurationError("Missing required config: 'filepath'")
        if not pattern:
            raise ConfigurationError("Missing required config: 'pattern'")

        # Check file existence
        if not os.path.exists(filepath):
            error_msg = f"Input file not found: {filepath}"
            if die_on_error:
                logger.error(f"[{self.id}] File not found: {filepath}")
                raise FileOperationError(error_msg)
            else:
                logger.warning(f"[{self.id}] File not found: {filepath}, returning empty result")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

        # Parse pattern to list of widths
        try:
            widths = [int(x.strip()) for x in pattern.split(',') if x.strip()]
            if not widths:
                raise ConfigurationError(f"Pattern cannot be empty: {pattern}")
            logger.debug(f"[{self.id}] Parsed column widths: {widths}")
        except ValueError as e:
            raise ConfigurationError(f"Invalid pattern format: {pattern} - {str(e)}")

        # Extract column names from schema if available
        names = None
        if self.output_schema:
            names = [col['name'] for col in self.output_schema]

        # Build dtype dictionary from schema to enforce column types during read
        dtype_dict = self._build_dtype_dict()

        try:
            logger.debug(f"[{self.id}] Reading fixed-width file with pandas read_fwf")

            # Read file as fixed-width
            df = pd.read_fwf(
                filepath,
                widths=widths,
                encoding=encoding,
                header=None,
                names=names,
                skiprows=header_rows,
                nrows=nrows,
                skipfooter=footer_rows,
                engine='python' if footer_rows > 0 else None,
                dtype=dtype_dict
            )

            rows_in = len(df)
            logger.debug(f"[{self.id}] Read {rows_in} raw rows from file")

            # Trim all string columns if requested
            if trim_all:
                logger.debug(f"[{self.id}] Trimming all string columns")
                string_columns = df.select_dtypes(include=['object']).columns
                for col in string_columns:
                    df[col] = df[col].str.strip()

            # Remove empty rows if requested
            if remove_empty_row:
                initial_count = len(df)
                df = df.dropna(how='all')
                removed_count = initial_count - len(df)
                if removed_count > 0:
                    logger.debug(f"[{self.id}] Removed {removed_count} empty rows")
            # Replace NaN in string columns with empty string
            string_columns = df.select_dtypes(include=['object']).columns
            df[string_columns] = df[string_columns].fillna('')
            # Validate schema
            if self.output_schema:
                logger.debug(f"[{self.id}] Validating schema")
                df = self.validate_schema(df, self.output_schema)

            # Advanced separator: convert thousands/decimal if needed
            if advanced_separator:
                logger.debug(f"[{self.id}] Applying advanced separators")
                for col in df.select_dtypes(include=['object']).columns:
                    df[col] = df[col].str.replace(thousands_separator, '', regex=False)
                    df[col] = df[col].str.replace(decimal_separator, '.', regex=False)

            # Check date columns if requested
            if check_date and self.output_schema:
                logger.debug(f"[{self.id}] Converting date columns")
                for col in self.output_schema:
                    if col.get('type', '').lower() == 'date':
                        try:
                            df[col['name']] = pd.to_datetime(df[col['name']], errors='coerce')
                        except Exception:
                            pass

            # Convert BigDecimal columns from string to Decimal
            if self.output_schema:
                for col_def in self.output_schema:
                    col_name = col_def['name']
                    col_type = col_def.get('type', 'id_String')
                    if col_type in ('id_BigDecimal', 'Decimal') and col_name in df.columns:
                        logger.debug(f"[{self.id}] Converting column {col_name} to Decimal")
                        df[col_name] = df[col_name].apply(lambda x: Decimal(str(x)) if pd.notna(x) and str(x).strip() else None)

            # Calculate final statistics
            rows_out = len(df)
            rows_rejected = 0  # This component doesn't reject rows

            # Update statistics
            self._update_stats(rows_in, rows_out, rows_rejected)

            logger.info(f"[{self.id}] Processing complete: in={rows_in}, out={rows_out}, rejected={rows_rejected}")
            logger.debug(f"[{self.id}] Output columns: {df.columns.tolist()}")

            # Log data types for debugging
            if logger.isEnabledFor(logging.DEBUG):
                dtypes_info = {col: str(dtype) for col, dtype in df.dtypes.items()}
                logger.debug(f"[{self.id}] Column dtypes: {dtypes_info}")

            return {'main': df}

        except FileOperationError:
            # Re-raise file operation errors
            raise
        except ConfigurationError:
            # Re-raise configuration errors
            raise
        except Exception as e:
            error_msg = f"Error reading positional file {filepath}: {str(e)}"
            logger.error(f"[{self.id}] Processing failed: {str(e)}")

            if die_on_error:
                raise ComponentExecutionError(self.id, error_msg, e)
            else:
                logger.warning(f"[{self.id}] Returning empty result due to error with die_on_error=False")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}