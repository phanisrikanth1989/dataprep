"""
tPython Component - Execute one-time Python code

This component mimics Talend's tJava functionality:
- Executes custom Python code once (not per-row)
- Useful for initialization and one-time operations
- Access to context, globalMap, and Python routines
"""

from typing import Any, Dict, Optional
import pandas as pd
import logging
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class PythonComponent(BaseComponent):
    """
    Execute one-time Python code (not row-based)

    Similar to Talend's tJava component - executes code once per job execution,
    not per row. Useful for:
    - initializing resources
    - One-time calculations
    - Setting global variables
    - Setup operations

    Config parameters:
    - python_code: Python code to execute once

    Example python_code:
        from datetime import datetime

        # Set global variables
        globalMap.put('start_time', datetime.now())
        globalMap.put('record_count', 0)

        # Access context
        output_dir = context.get('output_dir')
        print(f"Output directory: {output_dir}")

        # Perform calculations
        expected_records = 1000
        globalMap.put('expected_records', expected_records)

        Available in execution context:
        - context: Context variables from ContextManager
        - globalMap: Global storage from GlobalMap
        - routines: Python routines from PythonRoutineManager
        - Common imports: datetime, os, sys, etc.
    """

    def process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Execute one-time Python code"""

        # Get configuration
        python_code = self.config.get('python_code', '')

        if not python_code:
            raise ValueError(f"Component {self.id}: 'python_code' is required")

        # Get Python routines
        python_routines = self.get_python_routines()

        # Get context as flat dict
        context_dict = self._get_context_dict()

        try:
            logger.info(f"Component {self.id}: Executing one-time Python code")

            # Create execution namespace
            namespace = {
                'context': context_dict,
                'globalMap': self.global_map,
                'routines': python_routines,
                # Add routines directly for easier access
                **python_routines,
                # Common imports available
                'pd': pd,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'print': print,
                'sum': sum,
                'min': min,
                'max': max,
            }

            # Make common modules available
            import datetime
            import os
            import sys
            namespace['datetime'] = datetime
            namespace['os'] = os
            namespace['sys'] = sys

            # Execute user's Python code
            exec(python_code, namespace)

            logger.info(f"Component {self.id}: Python code executed successfully")

        except Exception as e:
            logger.error(f"Component {self.id}: Python code execution failed: {e}")
            raise

    def _get_context_dict(self) -> Dict[str, Any]:
        """Get context variables as a flat dictionary"""
        context_dict = {}
        if self.context_manager:
            context_all = self.context_manager.get_all()
            # Flatten context structure
            for context_name, context_vars in context_all.items():
                if isinstance(context_vars, dict):
                    # Nested structure (Default: {home_Location: {value: "US", type: "str"}})
                    for var_name, var_info in context_vars.items():
                        if isinstance(var_info, dict) and 'value' in var_info:
                            context_dict[var_name] = var_info['value']
                        else:
                            context_dict[var_name] = var_info
                elif context_vars is not None:
                    # Simple flat structure: {home_Location: "US"}
                    context_dict[context_name] = context_vars
        return context_dict
