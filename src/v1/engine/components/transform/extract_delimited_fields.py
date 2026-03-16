"""
ExtractDelimitedFields - Extracts fields from a delimited string based on configuration.

Talend equivalent: tExtractDelimitedFields

This component splits a delimited string field into multiple output columns
based on the specified field separator. Supports advanced number formatting,
field validation, and flexible schema mapping.
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class ExtractDelimitedFields(BaseComponent):
    """
    Extracts fields from a delimited string based on the specified configuration.

    This component takes a source field containing delimited values and splits
    it into multiple output columns based on positional mapping. Supports
    advanced number formatting, field trimming, and validation options.

    Configuration:
        field (str): The source field to extract from. Required.
        field_separator (str): The delimiter used to split the field. Default: ','
        ignore_source_null (bool): Whether to ignore null values in the source field. Default: True
        die_on_error (bool): Whether to stop execution on error. Default: False
        advanced_separator (bool): Whether to use advanced separators for numbers. Default: False
        thousands_separator (str): The thousands separator for numbers. Default: ','
        decimal_separator (str): The decimal separator for numbers. Default: '.'
        trim (bool): Whether to trim whitespace from extracted fields. Default: False
        check_fields_num (bool): Whether to validate the number of fields. Default: False
        check_data (bool): Whether to validate data fields. Default: False
        schema (list): Output schema (list of dicts with column names/types).

    Inputs:
        main: A DataFrame containing the input data.

    Outputs:
        main: A DataFrame with extracted fields expanded into columns.
        reject: A DataFrame with rejected rows (if applicable).

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully processed
        NB_LINE_REJECT: Rows rejected due to errors

    Example configuration:
        {
            "field": "product",
            "field_separator": ",",
            "ignore_source_null": true,
            "die_on_error": false,
            "advanced_separator": false,
            "thousands_separator": ",",
            "decimal_separator": ".",
            "trim": false,
            "check_fields_num": false,
            "check_data": false,
            "schema": [
                {"name": "id", "type": "id_String"},
                {"name": "name", "type": "id_String"},
                {"name": "product", "type": "id_String"},
                {"name": "product1", "type": "id_String"},
                {"name": "product2", "type": "id_String"},
                {"name": "product3", "type": "id_String"}
            ]
        }

    Notes:
        - Field names are matched case-insensitively
        - Output columns are determined by schema configuration
        - Extracted fields are mapped by position (field1, field2, etc.)
        - Original source field is preserved in output
    """

    # Class constants for default values
    DEFAULT_FIELD_SEPARATOR = ','
    DEFAULT_THOUSANDS_SEPARATOR = ','
    DEFAULT_DECIMAL_SEPARATOR = '.'

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required field validation
        if 'field' not in self.config:
            errors.append("Missing required config: 'field'")
        elif not self.config.get('field'):
            errors.append("Config 'field' cannot be empty")

        # Optional field validation (type checks only)
        if 'field_separator' in self.config:
            field_sep = self.config['field_separator']
            if not isinstance(field_sep, str):
                errors.append("Config 'field_separator' must be a string")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process input data and extract delimited fields.

        Splits the configured source field using the specified delimiter and maps
        the resulting values to output columns based on positional indexing.

        Args:
            input_data: Input DataFrame. If None or empty, returns empty result.

        Returns:
            Dictionary containing:
                - 'main': Processed DataFrame with extracted fields
                - 'reject': Rejected rows DataFrame (if errors occurred)

        Raises:
            ValueError: If source field is null and ignore_source_null is False
            Exception: Re-raised if die_on_error is True
        """
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        field = self.config.get('field', '')
        field_separator = self.config.get('field_separator', self.DEFAULT_FIELD_SEPARATOR)
        ignore_source_null = self.config.get('ignore_source_null', True)
        die_on_error = self.config.get('die_on_error', False)
        advanced_separator = self.config.get('advanced_separator', False)
        thousands_separator = self.config.get('thousands_separator', self.DEFAULT_THOUSANDS_SEPARATOR)
        decimal_separator = self.config.get('decimal_separator', self.DEFAULT_DECIMAL_SEPARATOR)
        trim = self.config.get('trim', False)
        check_fields_num = self.config.get('check_fields_num', False)
        check_data = self.config.get('check_data', False)
        # Use output_schema as the primary schema source, fallback to config
        schema = self.output_schema or self.config.get('schema', [])

        # Debug: Print schema and config at the start
        logger.debug(f"[ExtractDelimitedFields] schema: {schema}")
        logger.debug(f"[ExtractDelimitedFields] config field: {field}, field_separator: {field_separator}")
        # Remove quotes from field_separator if present (e.g. "," -> ,)
        if field_separator.startswith("'") and field_separator.endswith("'"):
            field_separator = field_separator[1:-1]
        # Make output_columns and extracted_columns case-insensitive
        output_columns = [col['name'] for col in schema if col['name'].lower() != field.lower()]
        extracted_columns = [col for col in output_columns if col.lower().startswith(field.lower())]
        logger.debug(f"[ExtractDelimitedFields] output_columns: {output_columns}")
        logger.debug(f"[ExtractDelimitedFields] extracted_columns: {extracted_columns}")

        main_rows = []
        reject_rows = []

        for idx, row in input_data.iterrows():
            try:
                # Case-insensitive field lookup
                field_lookup = {str(k).lower(): k for k in row.index}
                actual_field = field_lookup.get(field.lower(), field)
                value = row.get(actual_field, None)
                if value is None:
                    if ignore_source_null:
                        continue
                    else:
                        raise ValueError("Source field is null")

                # Split using the field separator
                fields = str(value).split(field_separator)
                if trim:
                    fields = [f.strip() for f in fields]

                # Advanced separator handling (for numbers)
                if advanced_separator:
                    fields = [f.replace(thousands_separator, '').replace(decimal_separator, '.') for f in fields]

                # Check number of fields
                if check_fields_num and len(fields) != len(extracted_columns):
                    raise ValueError(f"Field count mismatch: expected {len(extracted_columns)}, got {len(fields)}")

                # Optionally check date fields (not implemented in detail)
                if check_date:
                    pass

                # Build output row with all schema columns
                output_row = {}
                for col in [col['name'] for col in schema]:
                    if col.lower() == field.lower():
                        # Original field - preserve as is
                        output_row[col] = value
                    elif col.lower().startswith(field.lower()):
                        # Direct match: e.g. skills -> skills1, skills2, skills3
                        idx_split = col[len(field):]
                        idx_val = None
                        try:
                            idx_val = int(idx_split) - 1 if idx_split.isdigit() else None
                        except Exception:
                            pass
                        if idx_val is not None and idx_val >= 0 and idx_val < len(fields):
                            output_row[col] = fields[idx_val]
                        else:
                            output_row[col] = None
                    elif field.lower().startswith(col.lower().rstrip('0123456789')):
                        # Flexible match: e.g. skills -> skill1, skill2, skill3 (handles singular/plural)
                        base_col = col.lower().rstrip('0123456789')
                        if len(col) > len(base_col):
                            try:
                                idx_val = int(col[len(base_col):]) - 1
                                if idx_val >= 0 and idx_val < len(fields):
                                    output_row[col] = fields[idx_val]
                                else:
                                    output_row[col] = None
                            except (ValueError, IndexError):
                                output_row[col] = None
                        else:
                            output_row[col] = None
                    else:
                        # Other columns: copy from input if present (case-insensitive)
                        col_lookup = {str(k).lower(): k for k in row.index}
                        output_row[col] = row.get(col_lookup.get(col.lower(), col), None)
                main_rows.append(output_row)
            except Exception as e:
                logger.error(f"[{self.id}] Error processing row {idx}: {e}")
                reject_rows.append(row)
                if die_on_error:
                    raise

        # Always use output schema columns if available
        if schema:
            schema_cols = [col['name'] for col in schema]
            main_df = pd.DataFrame(main_rows, columns=schema_cols)
        else:
            main_df = pd.DataFrame(main_rows)
        reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame(columns=input_data.columns)

        # Debug: Print the main DataFrame shape, columns, and head
        logger.debug(f"[ExtractDelimitedFields] main_df shape: {main_df.shape}")
        logger.debug(f"[ExtractDelimitedFields] main_df columns: {list(main_df.columns)}")
        logger.debug(f"[ExtractDelimitedFields] main_df head:\n{main_df.head()}\nValues:\n{main_df.values}")

        # Calculate final statistics
        rows_out = len(main_df)
        rows_rejected = len(reject_df)

        # Update stats
        self._update_stats(rows_in, rows_out, rows_rejected)

        # Log completion with statistics
        logger.info(f"[{self.id}] Processing complete: "
                     f"in={rows_in}, out={rows_out}, rejected={rows_rejected}")

        # Validate schema for output
        if schema:
            main_df = self.validate_schema(main_df, schema)
            # Ensure column order and presence matches output schema exactly
            schema_cols = [col['name'] for col in schema]
            for col in schema_cols:
                if col not in main_df.columns:
                    main_df[col] = None
            main_df = main_df[schema_cols]

        return {'main': main_df, 'reject': reject_df}
