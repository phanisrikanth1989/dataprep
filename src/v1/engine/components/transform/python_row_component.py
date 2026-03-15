"""
tPythonRow component - Execute Python code row-by-row

This component mimics Talend's tJavaRow functionality but uses Python:
- Executes custom Python code for each input row
- Access to input_row and output_row dictionaries
- Access to context, globalMap, and Python routines
- Useful for row-level transformations with custom logic
"""

from typing import Any, Dict, Optional
import pandas as pd
import logging
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class PythonRowComponent(BaseComponent):
    """
    Execute Python code for each row (row-by-row processing)

    Similar to Talend's tJavaRow component - executes code once per row.
    User code operates on input_row and output_row dictionaries.

    Config parameters:
    - python_code: Python code to execute for each row
    - output_schema: Dict defining output columns and types (optional)

    Example python_code:
        output_row['full_name'] = input_row['first_name'] + " " + input_row['last_name']
        output_row['age'] = input_row['age']
        output_row['lengthOfName'] = len(output_row['full_name'])

    Available in execution context:
    - input_row: Dictionary with current row values
    - output_row: Dictionary to populate with output values
    - context: Context variables from ContextManager
    - globalMap: Global storage from GlobalMap
    - routines: Python routines from PythonRoutineManager
    """

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Execute Python code for each row"""

        if input_data is None or input_data.empty:
            logger.warning(f"Component {self.id}: No input data")
            return {'main': pd.DataFrame()}

        # Get configuration
        python_code = self.config.get('python_code', '')
        output_schema = self.config.get('output_schema', {})

        if not python_code:
            raise ValueError(f"Component {self.id}: 'python_code' is required")

        # Get Python routines
        python_routines = self.get_python_routines()

        # Get context as flat dict
        context_dict = self._get_context_dict()

        # Prepare output rows list
        output_rows = []
        reject_rows = []

        logger.info(f"Component {self.id}: Processing {len(input_data)} rows with Python code")

        # Process each row
        for idx, row in input_data.iterrows():
            try:
                # Convert row to dictionary
                input_row = row.to_dict()
                output_row = {}

                # Create execution namespace
                namespace = {
                    'input_row': input_row,
                    'output_row': output_row,
                    'context': context_dict,
                    'globalMap': self.global_map,
                    'routines': python_routines,
                    # Add routines directly for easier access
                    **python_routines,
                    # Common imports available
                    'len': len,
                    'str': str,
                    'int': int,
                    'float': float,
                    'bool': bool,
                }

                # Execute user's Python code
                exec(python_code, namespace)

                # Get the modified output_row
                output_row = namespace['output_row']

                # Validate output schema if provided
                if output_schema:
                    output_row = self._validate_output_row(output_row, output_schema, idx)

                output_rows.append(output_row)

            except Exception as e:
                logger.error(f"Component {self.id}: Error processing row {idx}: {e}")
                # Add to reject with error info
                reject_row = row.to_dict()
                reject_row['errorCode'] = 'PYTHON_ERROR'
                reject_row['errorMessage'] = str(e)
                reject_rows.append(reject_row)

        # Convert to DataFrames
        main_df = pd.DataFrame(output_rows) if output_rows else pd.DataFrame()
        reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame()

        # Update statistics
        self._update_stats(
            rows_read=len(input_data),
            rows_ok=len(output_rows),
            rows_reject=len(reject_rows)
        )

        logger.info(f"Component {self.id}: Processed {len(output_rows)} rows successfully, {len(reject_rows)} rejected")

        result = {'main': main_df}
        if not reject_df.empty:
            result['reject'] = reject_df

        return result

    def _get_context_dict(self) -> Dict[str, Any]:
        """Get context variables as a flat dictionary"""
        context_dict = {}
        if self.context_manager:
            context_all = self.context_manager.get_all()
            # Flatten context structure
            for context_name, context_vars in context_all.items():
                if isinstance(context_vars, dict):
                    # Nested structure: {Default: {home_location: {value: "US", type: "str"}}}
                    for var_name, var_info in context_vars.items():
                        if isinstance(var_info, dict) and 'value' in var_info:
                            context_dict[var_name] = var_info['value']
                        else:
                            context_dict[var_name] = var_info
                elif context_vars is not None:
                    # Simple flat structure: {home_location: "US"}
                    context_dict[context_name] = context_vars
        return context_dict

    def _validate_output_row(self, output_row: Dict[str, Any], output_schema: Dict[str, str], row_idx: int) -> Dict[str, Any]:
        """
        Validate and convert output row according to schema

        Args:
            output_row: Output row dictionary
            output_schema: Schema definition (column_name -> type_name)
            row_idx: Row index for error reporting

        Returns:
            Validated output row
        """
        validated_row = {}

        # Type mapping
        type_mapping = {
            'str': str,
            'String': str,
            'int': int,
            'Integer': int,
            'float': float,
            'Float': float,
            'Double': float,
            'double': float,
            'bool': bool,
            'Boolean': bool,
        }

        for col_name, col_type in output_schema.items():
            if col_name in output_row:
                value = output_row[col_name]

                # Type conversion
                if value is not None and col_type in type_mapping:
                    try:
                        converter = type_mapping[col_type]
                        validated_row[col_name] = converter(value)
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            f"Component {self.id}: Row {row_idx}, column '{col_name}': "
                            f"Cannot convert '{value}' to {col_type}, using original value"
                        )
                        validated_row[col_name] = value
                else:
                    validated_row[col_name] = value
            else:
                # Column not in output_row, set to None
                validated_row[col_name] = None

        return validated_row
