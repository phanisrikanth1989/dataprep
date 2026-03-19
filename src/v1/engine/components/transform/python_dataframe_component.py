"""
PythonDataFrame component - Execute Python code on entire DataFrame

This component provides vectorized DataFrame operations:
- Executes custom Python code on the full DataFrame
- Allows transformations that would be tedious with standard operations
- Access to pandas operations, context, globalMap, and Python routines
- Useful for bulk transformations and aggregations
"""

from typing import Any, Dict, Optional
import pandas as pd
import numpy as np
import logging
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class PythonDataFrameComponent(BaseComponent):
    """
    Execute Python code on entire DataFrame (vectorized operations)

    User code operates on the full DataFrame for efficient bulk processing.
    This is the Pythonic way to transform data - much faster than row-by-row operations.

    Config parameters:
    - python_code: Python code to execute on the DataFrame
    - output_columns: List of columns to keep in output (optional, keeps all if not specified)

    Example python_code:
        # Vectorized string operations
        df['full_name'] = df['first_name'] + ' ' + df['last_name']
        df['lengthOfName'] = df['full_name'].str.len()

        # Conditional logic
        df['age_group'] = pd.cut(df['age'], bins=[0, 18, 65, np.inf], labels=['child', 'adult', 'senior'])

        # Complex calculations
        df['discount'] = df['price'].apply(lambda x: x * 0.9 if x > 100 else x)

        # Using routines
        df['formatted_name'] = df['full_name'].apply(routines.StringRoutine.format_name)

        Available in execution context:
        - df: Input DataFrame (must be modified in-place)
        - pd: pandas library
        - np: numpy library
        - context: Context variables as a flat dict
        - globalMap: Global variables dict
        - routines: Python routines defined in the project (also available directly by name)
    """

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Execute Python code on DataFrame"""

        if input_data is None or input_data.empty:
            logger.warning(f"Component {self.id}: No input data")
            return {'main': pd.DataFrame()}

        # Get configuration
        python_code = self.config.get('python_code', '')
        output_columns = self.config.get('output_columns', None)

        if not python_code:
            raise ValueError(f"Component {self.id}: 'python_code' is required")

        # Get Python routines
        python_routines = self.get_python_routines()

        # Get context as flat dict
        context_dict = self._get_context_dict()

        # Copy input DataFrame to avoid modifying original
        df = input_data.copy()

        logger.info(f"Component {self.id}: Processing DataFrame with {len(df)} rows using Python code")

        try:
            # Create execution namespace
            namespace = {
                'df': df,
                'pd': pd,
                'np': np,
                'context': context_dict,
                'globalMap': self.global_map,
                'routines': python_routines,
                # Add routines directly for easier access
                **python_routines,
                # Common functions
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'sum': sum,
                'min': min,
                'max': max,
            }

            # Execute user's Python code
            exec(python_code, namespace)

            # Get the modified DataFrame
            output_df = namespace['df']

            # Filter columns if specified
            if output_columns:
                # Keep only specified columns
                available_cols = [col for col in output_columns if col in output_df.columns]
                if available_cols:
                    output_df = output_df[available_cols]
                else:
                    logger.warning(f"Component {self.id}: None of the specified output_columns exist in DataFrame")

            # Update statistics
            self._update_stats(
                rows_read=len(input_data),
                rows_ok=len(output_df),
                rows_reject=0
            )

            logger.info(f"Component {self.id}: Processed DataFrame successfully: {len(output_df)} rows, {len(output_df.columns)} columns")

            return {'main': output_df}

        except Exception as e:
            logger.error(f"Component {self.id}: Error executing Python code: {e}")
            raise

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
                else:
                    # Simple flat structure: {home_location: "US"}
                    context_dict[context_name] = context_vars
        return context_dict
