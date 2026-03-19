"""
ExtractPositionalFields - Extracts fields from positional data based on fixed-width patterns.

Talend equivalent: tExtractPositionalFields

This component processes fixed-width positional data by extracting fields according to
specified width patterns. Supports trimming and advanced separator handling.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...exceptions import ComponentExecutionError, ConfigurationError, DataValidationError

logger = logging.getLogger(__name__)


class ExtractPositionalFields(BaseComponent):
    """
    Extracts fields from a positional file based on fixed-width columns.

    This component processes positional data by splitting each row into fields based on
    specified field widths. Each field can be optionally trimmed and the component
    supports advanced separator handling for numeric formatting.

    Configuration:
        pattern (str): Comma-separated string defining field widths (e.g. "5,4,5"). Required.
        die_on_error (bool): Whether to stop processing on error. Default: False
        trim (bool): Whether to trim whitespace from extracted fields. Default: False
        advanced_separator (bool): Whether to use advanced separators. Default: False
        thousands_separator (str): Character for thousands separator. Default: ','
        decimal_separator (str): Character for decimal separator. Default: '.'

    Inputs:
        main: Positional file data as a DataFrame with first column containing the raw data.

    Outputs:
        main: Extracted fields as a DataFrame with columns named field_1, field_2, etc.
        reject: Rows that failed processing (empty DataFrame if no failures).

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully processed
        NB_LINE_REJECT: Rows that failed processing

    Example:
        config = {
            "pattern": "5,4,5",
            "die_on_error": False,
            "trim": True
        }
        component = ExtractPositionalFields("comp_1", config)
        result = component.execute(input_df)

    Notes:
        - Assumes the first column of input DataFrame contains the positional data
        - Creates output columns with names field_1, field_2, etc. based on pattern
        - If a row is shorter than expected, remaining fields will contain partial data
    """

    def __init__(self, component_id: str, config: Dict[str, Any], global_map, context_manager):
        """Initialize the ExtractPositionalFields component with enhanced logging."""
        super().__init__(component_id, config, global_map, context_manager)
        logger.info(f"[{self.id}] ExtractPositionalFields component initialized")
        logger.info(f"[{self.id}] Configuration: {self.config}")

        # Validate configuration during initialization
        config_errors = self._validate_config()
        if config_errors:
            error_msg = f"Configuration validation failed: {'; '.join(config_errors)}"
            logger.error(f"[{self.id}] {error_msg}")
            raise ConfigurationError(error_msg)
        else:
            logger.info(f"[{self.id}] Configuration validation passed")

    def execute(self, input_data=None):
        """Execute the component with enhanced logging."""
        logger.info(f"[{self.id}] ===== EXECUTE CALLED =====")
        logger.info(f"[{self.id}] Input data type: {type(input_data)}")
        if hasattr(input_data, 'shape'):
            logger.info(f"[{self.id}] Input data shape: {input_data.shape}")
        if hasattr(input_data, 'columns'):
            logger.info(f"[{self.id}] Input data columns: {list(input_data.columns)}")

        try:
            result = super().execute(input_data)
            logger.info(f"[{self.id}] ===== EXECUTE COMPLETED =====")
            logger.info(f"[{self.id}] Result keys: {list(result.keys()) if result else 'None'}")
            return result
        except Exception as e:
            logger.error(f"[{self.id}] ===== EXECUTE FAILED =====")
            logger.error(f"[{self.id}] Error: {e}")
            raise

    def _validate_config(self) -> List[str]:
        """Validate component configuration."""
        errors = []

        # Check required pattern field
        if 'pattern' not in self.config:
            errors.append("Missing required config: 'pattern'")
        elif not isinstance(self.config['pattern'], str) or not self.config['pattern'].strip():
            errors.append("Config 'pattern' must be a non-empty string")
        else:
            # Validate pattern format
            try:
                pattern_parts = self.config['pattern'].split(',')
                for part in pattern_parts:
                    width = int(part.strip())
                    if width <= 0:
                        errors.append(f"Invalid field width in pattern: {part}. Must be positive integer")
            except ValueError as e:
                errors.append(f"Invalid pattern format: {self.config['pattern']}. Must be comma-separated integers")

        # Validate optional boolean fields
        for bool_field in ['die_on_error', 'trim', 'advanced_separator']:
            if bool_field in self.config and not isinstance(self.config[bool_field], bool):
                errors.append(f"Config '{bool_field}' must be boolean")

        # Validate separator fields
        for sep_field in ['thousands_separator', 'decimal_separator']:
            if sep_field in self.config:
                value = self.config[sep_field]
                if not isinstance(value, str):
                    errors.append(f"Config '{sep_field}' must be string")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Process input data by extracting positional fields."""
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}

        # Ensure input_data is a DataFrame
        if not isinstance(input_data, pd.DataFrame):
            try:
                input_data = pd.DataFrame(input_data)
                logger.debug(f"[{self.id}] Converted input to DataFrame")
            except Exception as e:
                logger.error(f"[{self.id}] Failed to convert input to DataFrame: {e}")
                raise DataValidationError(f"Cannot convert input to DataFrame: {e}") from e

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        # Get configuration with defaults
        pattern = self.config.get('pattern', '')
        die_on_error = self.config.get('die_on_error', False)
        trim = self.config.get('trim', False)

        try:
            # Parse the pattern into field widths
            field_widths = [int(width) for width in pattern.split(',')]
            logger.debug(f"[{self.id}] Using strict field widths: {field_widths}")

            # Extract fields based on the exact pattern specified
            extracted_data = []
            for _, row in input_data.iterrows():
                # Get the line data
                if 'line' in input_data.columns:
                    line = row['line']
                elif len(input_data.columns) > 0:
                    line = row.iloc[0]
                else:
                    logger.error(f"[{self.id}] No data columns found in input DataFrame")
                    continue

                # Ensure line is a string and clean any BOM
                if not isinstance(line, str):
                    line = str(line)

                # Clean BOM characters
                if line.startswith('\ufeff'):  # UTF-8 BOM
                    line = line[1:]
                if line.startswith('\xff\xfe'):  # UTF-16 LE BOM
                    line = line[2:]

                logger.debug(f"[{self.id}] Processing line: '{line}' (length: {len(line)})")

                # Extract fields dynamically based on the pattern
                extracted_row = []
                current_pos = 0

                for idx, width in enumerate(field_widths):
                    start_pos = current_pos
                    end_pos = current_pos + width
                    
                    # Extract the field, handling lines shorter than expected
                    field_value = line[start_pos:end_pos] if len(line) > start_pos else ''
                    
                    # Apply trimming if configured
                    if trim:
                        field_value = field_value.strip()
                    
                    extracted_row.append(field_value)
                    logger.debug(f"[{self.id}] Field {idx+1}: extracted '{field_value}' from positions {start_pos}-{end_pos}")
                    
                    current_pos = end_pos

                logger.debug(f"[{self.id}] Extracted row: {extracted_row}")

                extracted_data.append(extracted_row)

            # Create DataFrame with proper column names from schema
            output_schema = getattr(self, 'output_schema', None) or []

            if output_schema and len(output_schema) >= len(field_widths):
                column_names = [field['name'] for field in output_schema[:len(field_widths)]]
                logger.debug(f"[{self.id}] Using schema column names: {column_names}")
            else:
                column_names = [f"field_{i+1}" for i in range(len(field_widths))]
                logger.debug(f"[{self.id}] Using generic column names: {column_names}")

            output_df = pd.DataFrame(extracted_data, columns=column_names)

            # Calculate statistics
            rows_out = len(output_df)
            rows_rejected = 0

            # Update statistics
            self._update_stats(rows_in, rows_out, rows_rejected)
            logger.info(f"[{self.id}] Processing complete: in={rows_in}, out={rows_out}, rejected={rows_rejected}")

            return {'main': output_df, 'reject': pd.DataFrame()}

        except Exception as e:
            logger.error(f"[{self.id}] Processing failed: {e}")
            if die_on_error:
                raise ComponentExecutionError(self.id, f"Error processing data: {e}", e) from e
            else:
                self._update_stats(rows_in, 0, rows_in)
                logger.warning(f"[{self.id}] Returning empty result due to error (die_on_error=False)")
                return {'main': pd.DataFrame(), 'reject': input_data}
