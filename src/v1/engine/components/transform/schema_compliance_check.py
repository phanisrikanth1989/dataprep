"""
TSchemaComplianceCheck - Validate data against predefined schema rules.

Talend equivalent: tSchemaComplianceCheck

This component validates input data against a predefined schema, checking for
type compliance and nullability constraints. Rows that fail validation are
separated into a reject output with error details.
"""
import logging
import pandas as pd
from typing import Dict, Any, Optional, List
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class SchemaComplianceCheck(BaseComponent):
    """
    Validates data against a predefined schema with type and nullability checks.
    Equivalent to Talend's tSchemaComplianceCheck component.

    Configuration:
        schema (List[Dict]): Schema definition with column specifications. Required.
            Each column must have:
            - name (str): Column name. Required.
            - type (str): Talend data type (e.g., 'id_String', 'id_Integer'). Required.
            - nullable (bool): Whether null values are allowed. Default: True
            - length (int): Column length constraint (for future use). Optional.

    Inputs:
        main: Input DataFrame to validate against schema

    Outputs:
        main: Valid rows that pass all schema checks
        reject: Rejected rows with errorCode and errorMessage columns

    Statistics:
        NB_LINE: Total rows processed (input rows)
        NB_LINE_OK: Valid rows that passed schema validation
        NB_LINE_REJECT: Rejected rows that failed schema validation

    Example:
        config = {
            "schema": [
                {"name": "id", "type": "id_Integer", "nullable": False},
                {"name": "name", "type": "id_String", "nullable": True},
                {"name": "amount", "type": "id_Float", "nullable": False}
            ]
        }

    Notes:
        - Supports Talend data types: id_String, id_Integer, id_Float, id_Date
        - Rejected rows include errorCode (8) and errorMessage with details
        - Type validation uses Python type checking against mapped Talend types
        - Null validation respects the nullable flag for each column
        - Length constraints are supported in schema but not currently enforced
    """

    # Class constants
    DEFAULT_ERROR_CODE = 8
    DEFAULT_NULLABLE = True
    TALEND_TYPE_MAPPING = {
        'id_Integer': int,
        'id_String': str,
        'id_Float': float,
        'id_Date': str,  # Dates can be validated further if needed
    }

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Validate schema presence
        if 'schema' not in self.config:
            errors.append("Missing required config: 'schema'")
            return errors

        schema = self.config['schema']
        if not isinstance(schema, list):
            errors.append("Config 'schema' must be a list")
            return errors

        if len(schema) == 0:
            errors.append("Config 'schema' cannot be empty")
            return errors

        # Validate each schema column
        for i, col in enumerate(schema):
            if not isinstance(col, dict):
                errors.append(f"Schema column {i} must be a dictionary")
                continue

            # Required fields
            if 'name' not in col:
                errors.append(f"Schema column {i}: missing required field 'name'")
            elif not isinstance(col['name'], str):
                errors.append(f"Schema column {i}: 'name' must be a string")

            if 'type' not in col:
                errors.append(f"Schema column {i}: missing required field 'type'")
            elif not isinstance(col['type'], str):
                errors.append(f"Schema column {i}: 'type' must be a string")
            elif col['type'] not in self.TALEND_TYPE_MAPPING:
                valid_types = list(self.TALEND_TYPE_MAPPING.keys())
                errors.append(f"Schema column {i}: unsupported type '{col['type']}'. "
                              f"Valid types: {valid_types}")

            # Optional fields validation
            if 'nullable' in col and not isinstance(col['nullable'], bool):
                errors.append(f"Schema column {i}: 'nullable' must be boolean")

            if 'length' in col and not isinstance(col['length'], int):
                errors.append(f"Schema column {i}: 'length' must be an integer")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Validate input data against the schema, interpreting Talend data types.

        Args:
            input_data: Input DataFrame to validate (may be None or empty)

        Returns:
            Dictionary containing:
                - 'main': Valid rows that passed schema validation
                - 'reject': Rejected rows with errorCode and errorMessage

        Raises:
            No exceptions raised - all validation errors are captured in reject output
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        # Get schema configuration
        schema = self.config.get('schema', [])
        logger.debug(f"[{self.id}] Schema validation with {len(schema)} column definitions")

        reject_rows = []
        valid_rows = []

        # Use class constant for type mapping
        talend_type_mapping = self.TALEND_TYPE_MAPPING

        logger.debug(f"[{self.id}] Starting row-by-row schema validation")

        # Validate each row against schema
        for row_idx, (_, row) in enumerate(input_data.iterrows()):
            errors = []
            row_name = f"Row({row_idx + 1})"  # Talend uses 1-based row numbering

            # Check each column in schema
            for col in schema:
                col_name = col['name']
                col_type = col['type']
                col_nullable = col.get('nullable', self.DEFAULT_NULLABLE)
                col_length = col.get('length', None)

                value = row.get(col_name)

                # Check for empty values (Talend-specific handling)
                if pd.isnull(value) or (isinstance(value, str) and value.strip() == ''):
                    if not col_nullable:
                        error_msg = f"Value is empty for column : '{col_name}' in '{row_name}' connection, value is invalid or this column should be nullable or have a default value."
                        print(error_msg)  # Print to console like Talend
                        logger.info(error_msg)  # Also log it
                        errors.append(f"{col_name}:cannot be null")
                    continue  # Skip further validation for empty values

                # Check for length constraints 
                if col_length is not None and isinstance(value, str):
                    if len(value) > col_length:
                        error_msg = f"Value length exceeds maximum for column : '{col_name}' in '{row_name}' connection, max length is {col_length}, actual length is {len(value)}"
                        print(error_msg)  # Print to console like Talend
                        logger.info(error_msg)  # Also log it
                        errors.append(f"{col_name}:exceed max length")

                # Check for type compliance based on Talend types
                expected_type = talend_type_mapping.get(col_type, None)
                if expected_type and not isinstance(value, expected_type):
                    # Try to convert the value if possible
                    try:
                        if col_type == 'id_Integer':
                            converted_value = int(float(str(value)))  # Handle string numbers
                            row[col_name] = converted_value  # Update the row with converted value
                        elif col_type == 'id_Float':
                            converted_value = float(str(value))
                            row[col_name] = converted_value
                        # String types don't need conversion
                    except (ValueError, TypeError):
                        error_msg = f"Type mismatch for column : '{col_name}' in '{row_name}' connection, expected {col_type}, got {type(value).__name__}."
                        print(error_msg)  # Print to console like Talend
                        logger.info(error_msg)  # Also log it
                        errors.append(f"{col_name}:invalid type")

            # Categorize row as valid or rejected
            if errors:
                reject_rows.append({
                    **row,
                    'errorCode': self.DEFAULT_ERROR_CODE,
                    'errorMessage': ';'.join(errors),  # No space after semicolon to match Talend
                })
                logger.debug(f"[{self.id}] Row {row_idx + 1}: rejected with {len(errors)} errors")
            else:
                valid_rows.append(row)

        # Create output DataFrames
        valid_df = pd.DataFrame(valid_rows)
        reject_df = pd.DataFrame(reject_rows)

        # Calculate statistics
        rows_out = len(valid_df)
        rows_rejected = len(reject_df)
        self._update_stats(rows_in, rows_out, rows_rejected)

        logger.info(f"[{self.id}] Schema validation complete: "
                     f"in={rows_in}, valid={rows_out}, rejected={rows_rejected}")

        if rows_rejected > 0:
            logger.info(f"[{self.id}] Rejected {rows_rejected} rows due to schema violations")

        return {'main': valid_df, 'reject': reject_df}

    def validate_config(self) -> bool:
        """
        Validate the component configuration.

        Returns:
            bool: True if configuration is valid, False otherwise

        Note:
            This method maintains backward compatibility. The preferred method
            is _validate_config() which returns detailed error messages.
        """
        errors = self._validate_config()

        if errors:
            for error in errors:
                logger.error(f"[{self.id}] Configuration error: {error}")
            return False

        logger.debug(f"[{self.id}] Configuration validation passed")
        return True
