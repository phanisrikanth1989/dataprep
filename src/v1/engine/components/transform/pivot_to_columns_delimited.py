"""
tPivotToColumnsDelimited - Pivot rows into columns and write to a delimited file.

Talend equivalent: tPivotToColumnsDelimited

This component performs pivot operations on input data, transforming rows into columns
based on a pivot column and aggregation column. The result can be written to a delimited
file while also returning the pivoted DataFrame.
"""
import logging
import pandas as pd
from typing import Dict, Any, Optional, List
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class PivotToColumnsDelimited(BaseComponent):
    """
    Pivot rows into columns based on a pivot column and aggregation column.
    Equivalent to Talend's tPivotToColumnsDelimited component.

    Configuration:
        pivot_column (str): Column to pivot on (becomes new column headers). Required.
        aggregation_column (str): Column to aggregate values from. Required.
        aggregation_function (str): Aggregation function to apply. Default: 'sum'
        group_by_columns (List[str]): Columns to group by (preserved as index). Required.
        filename (str): Output file path. Default: 'output.csv'
        field_separator (str): Field delimiter for output file. Default: ','
        row_separator (str): Row separator for output file. Default: '\n'
        encoding (str): File encoding for output. Default: 'UTF-8'
        create (bool): Whether to create the output file. Default: True
        schema (Dict[str, str]): Optional column type casting schema

    Inputs:
        main: Input DataFrame containing data to pivot

    Outputs:
        main: Pivoted DataFrame with rows transformed to columns
        output_file: Path to the created output file (if create=True)

    Statistics:
        NB_LINE: Total rows processed (input rows)
        NB_LINE_OK: Output rows produced after pivoting
        NB_LINE_REJECT: Always 0 (no rows are rejected)

    Example:
        config = {
            "pivot_column": "category",
            "aggregation_column": "amount",
            "aggregation_function": "sum",
            "group_by_columns": ["region", "date"],
            "filename": "pivot_output.csv",
            "field_separator": "|",
            "create": True
        }

    Notes:
        - Pivot operation uses pandas pivot_table functionality
        - NaN values are replaced with empty strings in output
        - Numeric columns are cast to integers when applicable
        - Schema-based type casting is applied if schema is provided
        - Output file is written only if create=True
        - Field and row separators support quote removal and escape sequences
    """

    # Class constants
    DEFAULT_AGGREGATION_FUNCTION = 'sum'
    DEFAULT_FIELD_SEPARATOR = ','
    DEFAULT_ROW_SEPARATOR = '\n'
    DEFAULT_ENCODING = 'UTF-8'
    DEFAULT_FILENAME = 'output.csv'
    DEFAULT_CREATE = True

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Validate required fields
        if 'pivot_column' not in self.config or not self.config['pivot_column']:
            errors.append("Missing required config: 'pivot_column'")

        if 'aggregation_column' not in self.config or not self.config['aggregation_column']:
            errors.append("Missing required config: 'aggregation_column'")

        if 'group_by_columns' not in self.config:
            errors.append("Missing required config: 'group_by_columns'")
        elif not isinstance(self.config['group_by_columns'], list):
            errors.append("Config 'group_by_columns' must be a list")
        elif len(self.config['group_by_columns']) == 0:
            errors.append("Config 'group_by_columns' cannot be empty")

        if 'filename' not in self.config or not self.config['filename']:
            errors.append("Missing required config: 'filename'")

        # Validate field_separator
        if 'field_separator' in self.config:
            field_separator = self.config['field_separator']
            # Remove quotes for validation if present
            if field_separator.startswith('"') and field_separator.endswith('"'):
                field_separator = field_separator[1:-1]

            if not isinstance(field_separator, str) or len(field_separator) != 1:
                errors.append("Config 'field_separator' must be a single-character string")

        # Validate optional fields if present
        if 'aggregation_function' in self.config:
            if not isinstance(self.config['aggregation_function'], str):
                errors.append("Config 'aggregation_function' must be a string")

        if 'encoding' in self.config:
            if not isinstance(self.config['encoding'], str):
                errors.append("Config 'encoding' must be a string")

        if 'create' in self.config:
            if not isinstance(self.config['create'], bool):
                errors.append("Config 'create' must be boolean")

        if 'schema' in self.config:
            if not isinstance(self.config['schema'], dict):
                errors.append("Config 'schema' must be a dictionary")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process input data to pivot rows into columns and write to a delimited file.

        Args:
            input_data: Input DataFrame containing rows to pivot (may be None or empty)

        Returns:
            Dictionary containing:
                - 'main': Pivoted DataFrame with rows transformed to columns
                - 'output_file': Path to the created output file

        Raises:
            ValueError: If required configuration is missing or pivot operation fails
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        # Get configuration with defaults
        pivot_column = self.config.get('pivot_column', '')
        aggregation_column = self.config.get('aggregation_column', '')
        aggregation_function = self.config.get('aggregation_function', self.DEFAULT_AGGREGATION_FUNCTION)
        group_by_columns = self.config.get('group_by_columns', [])
        output_file = self.config.get('filename', self.DEFAULT_FILENAME)
        row_separator = self.config.get('row_separator', self.DEFAULT_ROW_SEPARATOR)
        field_separator = self.config.get('field_separator', self.DEFAULT_FIELD_SEPARATOR)
        encoding = self.config.get('encoding', self.DEFAULT_ENCODING)
        create_file = self.config.get('create', self.DEFAULT_CREATE)

        logger.debug(f"[{self.id}] Configuration: pivot_column='{pivot_column}', "
                     f"aggregation_column='{aggregation_column}', aggregation_function='{aggregation_function}', "
                     f"group_by_columns={group_by_columns}, output_file='{output_file}', create_file={create_file}")

        # Interpret escape sequences in row_separator
        row_separator = row_separator.encode().decode('unicode_escape')
        logger.debug(f"[{self.id}] Row separator after escape processing: {repr(row_separator)}")

        # Remove enclosing double quotes from field_separator and row_separator if present
        if field_separator.startswith('"') and field_separator.endswith('"'):
            field_separator = field_separator[1:-1]
            logger.debug(f"[{self.id}] Removed quotes from field separator: {field_separator}")

        if row_separator.startswith('"') and row_separator.endswith('"'):
            row_separator = row_separator[1:-1]
            logger.debug(f"[{self.id}] Removed quotes from row separator: {repr(row_separator)}")

        # Log the field_separator for debugging
        logger.info(f"[{self.id}] Field separator used: '{field_separator}'")

        # Validate configuration
        if not pivot_column or not aggregation_column or not group_by_columns:
            error_msg = "Missing required configuration: pivot_column, aggregation_column, or group_by_columns"
            logger.error(f"[{self.id}] {error_msg}")
            raise ValueError(error_msg)

        if not isinstance(field_separator, str) or len(field_separator) != 1:
            error_msg = "Invalid field_separator: must be a single-character string"
            logger.error(f"[{self.id}] {error_msg}")
            raise ValueError(error_msg)

        # Perform pivot operation
        try:
            logger.debug(f"[{self.id}] Performing pivot operation")
            logger.debug(f"[{self.id}] Input data shape: {input_data.shape}")

            pivoted_data = input_data.pivot_table(
                index=group_by_columns,
                columns=pivot_column,
                values=aggregation_column,
                aggfunc=aggregation_function
            ).reset_index()

            logger.debug(f"[{self.id}] After pivot operation: {pivoted_data.shape}")
            logger.debug(f"[{self.id}] Pivoted columns: {list(pivoted_data.columns)}")

            # Ensure data type consistency
            logger.debug(f"[{self.id}] Processing data type consistency")
            for col in pivoted_data.columns:
                if pivoted_data[col].dtype == 'float64':
                    pivoted_data[col] = pivoted_data[col].apply(lambda x: int(x) if pd.notnull(x) and x.is_integer() else x)

            # Replace NaN with empty strings
            logger.debug(f"[{self.id}] Replacing NaN values with empty strings")
            pivoted_data = pivoted_data.fillna('')

            # Ensure numeric columns are cast to integers where applicable
            logger.debug(f"[{self.id}] Casting numeric columns to integers where applicable")
            for col in pivoted_data.columns:
                if pd.api.types.is_numeric_dtype(pivoted_data[col]):
                    pivoted_data[col] = pivoted_data[col].apply(
                        lambda x: int(x) if x != '' and float(x) == int(float(x)) else x
                    )

            # Explicitly cast columns to their original types if schema is provided
            schema = self.config.get('schema', {})
            if schema:
                logger.debug(f"[{self.id}] Applying schema-based type casting: {schema}")
                for col, col_type in schema.items():
                    if col in pivoted_data.columns:
                        if col_type == 'int':
                            pivoted_data[col] = pivoted_data[col].apply(
                                lambda x: int(x) if x != '' else None
                            )
                        elif col_type == 'float':
                            pivoted_data[col] = pivoted_data[col].apply(
                                lambda x: float(x) if x != '' else None
                            )
                        logger.debug(f"[{self.id}] Applied {col_type} casting to column '{col}'")

        except Exception as e:
            error_msg = f"Pivot operation failed: {e}"
            logger.error(f"[{self.id}] {error_msg}")
            raise ValueError(error_msg)

        # Write to file if required
        if create_file:
            try:
                logger.info(f"[{self.id}] Writing output file: '{output_file}'")
                logger.debug(f"[{self.id}] File settings: separator='{field_separator}', "
                             f"line_terminator='{repr(row_separator)}', encoding='{encoding}'")

                pivoted_data.to_csv(
                    output_file,
                    sep=field_separator,
                    line_terminator=row_separator,
                    encoding=encoding,
                    index=False
                )
                logger.info(f"[{self.id}] Successfully wrote {len(pivoted_data)} rows to '{output_file}'")

            except Exception as e:
                error_msg = f"Failed to write output file: {e}"
                logger.error(f"[{self.id}] {error_msg}")
                raise ValueError(error_msg)
        else:
            logger.debug(f"[{self.id}] File creation disabled (create=False)")

        # Calculate statistics
        rows_out = len(pivoted_data)
        self._update_stats(rows_in, rows_out, 0)

        logger.info(f"[{self.id}] Processing complete: "
                    f"in={rows_in}, out={rows_out}, aggregation='{aggregation_function}'")

        return {'main': pivoted_data, 'output_file': output_file}

    def validate_config(self) -> bool:
        """
        Validate component configuration.

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
