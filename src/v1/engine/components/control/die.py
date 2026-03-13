"""
Die - Stop job execution with error message and optional exit code.

Talend equivalent: tDie
"""
import logging
import re
import sys
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...exceptions import ComponentExecutionError, ConfigurationError

logger = logging.getLogger(__name__)


class Die(BaseComponent):
    """
    Stop job execution with an error message and optional exit code.

    This component terminates the job execution with a specified error message,
    exit code, and priority level. It's used for controlled error handling
    and job termination based on specific conditions.

    Configuration:
        message (str): Error message to display. Supports context variable resolution. Default: "Job execution stopped"
        code (int): Error code for logging purposes. Default: 1
        priority (int): Log priority level (1=trace, 2=debug, 3=info, 4=warn, 5=error, 6=fatal). Default: 5
        exit_code (int): Job exit code. Default: 1

    Inputs:
        main: Optional input DataFrame (rows will be counted as rejected)

    Outputs:
        None: This component terminates job execution

    Statistics:
        NB_LINE: Number of input rows (or 1 if no input)
        NB_LINE_OK: Always 0 (no successful processing)
        NB_LINE_REJECT: Equal to NB_LINE (all rows rejected when job dies)

    Example configuration:
        {
            "message": "Critical error in job: ${context.error_details}",
            "code": 500,
            "priority": 5,
            "exit_code": 1
        }

    Notes:
        - Message supports context variable resolution with ${context.var} syntax
        - Message supports globalMap variable resolution with ((Integer)globalMap.get("key")) syntax
        - Component always raises ComponentExecutionError to terminate job
        - Exit code is attached to exception for engine handling
    """

    # Priority level constants
    PRIORITY_TRACE = 1
    PRIORITY_DEBUG = 2
    PRIORITY_INFO = 3
    PRIORITY_WARN = 4
    PRIORITY_ERROR = 5
    PRIORITY_FATAL = 6

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Optional field validation with more robust type checking
        if 'code' in self.config:
            code = self.config['code']
            if not isinstance(code, int):
                try:
                    # Allow string representation of integers
                    int(code)
                except (ValueError, TypeError):
                    errors.append("Config 'code' must be an integer or integer string")

        if 'priority' in self.config:
            priority = self.config['priority']
            if isinstance(priority, str) and priority.isdigit():
                priority = int(priority)
            if not isinstance(priority, int) or priority < 1 or priority > 6:
                errors.append("Config 'priority' must be an integer between 1 and 6")

        if 'exit_code' in self.config:
            exit_code = self.config['exit_code']
            if not isinstance(exit_code, int):
                try:
                    # Allow string representation of integers
                    int(exit_code)
                except (ValueError, TypeError):
                    errors.append("Config 'exit_code' must be an integer or integer string")

        if 'message' in self.config:
            message = self.config['message']
            if message is not None and not isinstance(message, str):
                errors.append("Config 'message' must be a string or None")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process input and terminate job execution with error.

        Args:
            input_data: Optional input DataFrame (rows counted as rejected)

        Returns:
            Does not return - raises ComponentExecutionError

        Raises:
            ComponentExecutionError: Always raised to terminate job execution
        """
        logger.info(f"[{self.id}] Processing started: terminating job execution")

        try:
            # Get configuration with defaults
            message = self.config.get('message', 'Job execution stopped')
            code = self.config.get('code', 1)
            priority = self.config.get('priority', self.PRIORITY_ERROR)
            exit_code = self.config.get('exit_code', 1)

            # Resolve context variables in message
            if self.context_manager and isinstance(message, str):
                message = self.context_manager.resolve_string(message)

            # Resolve globalMap variables in message
            if self.global_map and isinstance(message, str):
                message = self._resolve_global_map_variables(message)

            # Log based on priority level
            log_message = f"[{self.id}] Code {code}: {message}"

            if priority <= self.PRIORITY_INFO:
                logger.info(log_message)
            elif priority == self.PRIORITY_WARN:
                logger.warning(log_message)
            elif priority == self.PRIORITY_ERROR:
                logger.error(log_message)
            else:  # PRIORITY_FATAL or higher
                logger.critical(log_message)

            # Store information in global map for error handling
            if self.global_map:
                self.global_map.put(f"{self.id}_MESSAGE", message)
                self.global_map.put(f"{self.id}_CODE", code)
                self.global_map.put(f"{self.id}_PRIORITY", priority)
                self.global_map.put(f"{self.id}_EXIT_CODE", exit_code)
                self.global_map.put("JOB_ERROR_MESSAGE", message)
                self.global_map.put("JOB_EXIT_CODE", exit_code)

            # Update statistics before terminating
            if input_data is not None and not input_data.empty:
                rows = len(input_data)
                self._update_stats(rows, 0, rows)  # All rows are "rejected"
                logger.info(f"[{self.id}] Processed {rows} rows before termination")
            else:
                self._update_stats(1, 0, 1)  # Count as 1 execution with rejection
                logger.info(f"[{self.id}] No input data - terminating job")

            # Raise exception to terminate job execution
            error = ComponentExecutionError(
                self.id,
                f"Job terminated: {message} (exit code: {exit_code})"
            )
            error.exit_code = exit_code  # Attach exit code for engine handling
            raise error

        except ComponentExecutionError:
            # Re-raise our termination exception
            raise
        except Exception as e:
            logger.error(f"[{self.id}] Unexpected error during termination: {e}")
            raise ComponentExecutionError(self.id, f"Die component failed: {e}", e) from e

    def _resolve_global_map_variables(self, message: str) -> str:
        """
        Resolve globalMap variable references in message.

        Args:
            message: Message string potentially containing globalMap references

        Returns:
            Message with globalMap variables resolved
        """
        if not self.global_map:
            return message

        # Pattern for globalMap.get() calls
        pattern = r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'

        def replace_func(match):
            key = match.group(1)
            value = self.global_map.get(key, 0)
            return str(value)

        return re.sub(pattern, replace_func, message)
