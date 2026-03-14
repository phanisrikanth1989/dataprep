"""
SetGlobalVar - Sets global variables in the globalMap.

Talend equivalent: tSetGlobalVar

This component sets global variables that can be accessed by other components
through the globalMap. Variables are set based on the configuration and the
input data is passed through unchanged.
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class SetGlobalVar(BaseComponent):
    """
    Sets global variables in the globalMap for access by other components.

    This component allows you to set global variables that can be accessed
    by other components in the job through the globalMap. The input data
    is passed through unchanged.

    Configuration:
        VARIABLES (list): List of variable definitions. Required.
            Each variable should have:
                - name (str): Variable name
                - value (str): Variable value

    Inputs:
        main: Any data (passed through unchanged)

    Outputs:
        main: Same data as input (pass-through)

    Statistics:
        NB_LINE: Total rows processed (0 for this component)
        NB_LINE_OK: Successful rows (0 for this component)
        NB_LINE_REJECT: Rejected rows (0 for this component)

    Example configuration:
        {
            "VARIABLES": [
                {"name": "batch_id", "value": "BATCH_001"},
                {"name": "process_date", "value": "2024-01-15"}
            ]
        }

    Notes:
        - This component does not process data rows, it only sets variables
        - Variables are accessible via globalMap in other components
        - Input data is passed through without modification
    """

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check required VARIABLES parameter
        if "VARIABLES" not in self.config:
            errors.append("Missing required config: 'VARIABLES'")
        else:
            variables = self.config["VARIABLES"]
            if not isinstance(variables, list):
                errors.append("Config 'VARIABLES' must be a list")
            else:
                for i, variable in enumerate(variables):
                    if not isinstance(variable, dict):
                        errors.append(f"Variable at index {i} must be a dictionary")
                        continue

                    if "name" not in variable or not variable["name"]:
                        errors.append(f"Variable at index {i} missing required 'name' field")

                    if "value" not in variable:
                        errors.append(f"Variable at index {i} missing required 'value' field")

        return errors

    def _process(self, data: Any = None) -> Dict[str, Any]:
        """
        Process the component logic to set global variables.

        Args:
            data: Input data (any type, passed through unchanged)

        Returns:
            Dictionary with the same input data passed through

        Raises:
            ComponentExecutionError: If variable setting fails
        """
        logger.info(f"[{self.id}] Setting global variables")

        try:

            variables = self.config.get("VARIABLES", [])
            variables_set = 0

            for variable in variables:
                var_name = variable.get("name")
                var_value = variable.get("value")

                if var_name:
                    # Check if value looks like Java code that needs to be evaluated
                    if (isinstance(var_value, str) and 
                        var_value.strip().startswith("new ") and self.context_manager and 
                        hasattr(self.context_manager, "get_java_bridge")):

                        # Get Java bridge to evaluate the expression
                        java_bridge = self.context_manager.get_java_bridge()
                        if java_bridge:
                            try:
                                # Evaluate the Java expression
                                evaluated_value = java_bridge.execute_one_time_expression(var_value)
                                self.global_map.put(var_name, evaluated_value)
                                logger.debug(f"[{self.id}] Set global variable (evaluated): {var_name} = {type(evaluated_value)}")
                            except Exception as e:
                                logger.warning(f"[{self.id}] Failed to evaluate Java expression for {var_name}: {e}")
                                # Fallback to string value
                                self.global_map.put(var_name, var_value)
                                logger.debug(f"[{self.id}] Set global variable (string fallback): {var_name} = {var_value}")
                        else:
                            # No Java bridge available
                            self.global_map.put(var_name, var_value)
                            logger.debug(f"[{self.id}] Set global variable (no Java bridge): {var_name} = {var_value}")
                    else:
                        # Regular string value
                        self.global_map.put(var_name, var_value)
                        logger.debug(f"[{self.id}] Set global variable: {var_name} = {var_value}")

                    variables_set += 1

            # Update stats (this component doesn't process data rows)
            self._update_stats(0, 0, 0)

            logger.info(f"[{self.id}] Global variables set: {variables_set} variables")

            return {"main": data}

        except Exception as e:
            logger.error(f"[{self.id}] Failed to set global variables: {e}")
            raise
