"""
Warn - Log warning message and continue execution.

Talend equivalent: tWarn
"""
import pandas as pd
from typing import Dict, Any, Optional, List
import logging
import re

from ...base_component import BaseComponent
from ...exceptions import ConfigurationError, ComponentExecutionError

logger = logging.getLogger(__name__)


class Warn(BaseComponent):
    """
    Log a warning message and continue execution without stopping the job.

    This component logs a configurable message at the specified priority level
    and passes through any input data unchanged. Useful for debugging,
    monitoring, and conditional warnings in ETL flows.

    Configuration:
        message (str): Warning message to log. Supports context variables. Default: "Warning"
        code (int): Warning code number. Default: 0
        priority (int): Log priority level (1=trace, 2=debug, 3=info, 4=warn, 5=error, 6=fatal). Default: 4

    Inputs:
        main: Input DataFrame (optional, will be passed through unchanged)

    Outputs:
        main: Same as input DataFrame (pass-through)

    Statistics:
        NB_LINE: Number of rows processed (or 1 if no input)
        NB_LINE_OK: Equal to NB_LINE (no rejection logic)
        NB_LINE_REJECT: Always 0

    Example configuration:
        {
            "message": "Processing ${context.filename} - found ${((Integer)globalMap.get(\"row_count\"))} rows",
            "code": 100,
            "priority": 4
        }

    Notes:
        - Message supports context variables (${context.var}) and globalMap references
        - Component stores message details in globalMap for other components to access
        - Input data is passed through unchanged - this is a monitoring/logging component
        - Priority levels map to standard logging levels (warn=4, error=5, etc.)
    """

    # Valid priority levels
    VALID_PRIORITIES = [1, 2, 3, 4, 5, 6]
    PRIORITY_NAMES = {1: 'trace', 2: 'debug', 3: 'info', 4: 'warn', 5: 'error', 6: 'fatal'}

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Optional field validation
        if 'message' in self.config:
            message = self.config['message']
            if not isinstance(message, str):
                errors.append("Config 'message' must be a string")

        if 'code' in self.config:
            code = self.config['code']
            if isinstance(code, str):
                if not code.isdigit():
                    errors.append("Config 'code' must be an integer or integer string")
            elif not isinstance(code, int):
                errors.append("Config 'code' must be an integer")

        if 'priority' in self.config:
            priority = self.config['priority']
            if isinstance(priority, str):
                if not priority.isdigit():
                    errors.append("Config 'priority' must be an integer or integer string")
                else:
                    priority = int(priority)
            elif not isinstance(priority, int):
                errors.append("Config 'priority' must be an integer")

            if isinstance(priority, int) and priority not in self.VALID_PRIORITIES:
                errors.append(f"Config 'priority' must be one of {self.VALID_PRIORITIES} "
                              f"(1=trace, 2=debug, 3=info, 4=warn, 5=error, 6=fatal)")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Log warning message and pass through input data.

        Args:
            input_data: Input DataFrame (optional, passed through unchanged)

        Returns:
            Dictionary containing 'main' DataFrame (same as input)

        Raises:
            ConfigurationError: If configuration is invalid
            ComponentExecutionError: If message processing fails
        """
        logger.info(f"[{self.id}] Processing started: logging warning message")

        try:
            # Get configuration with defaults
            message = self.config.get('message', 'Warning')
            code = self.config.get('code', 0)
            priority = self.config.get('priority', 4)

            # Convert code and priority to integers safely
            try:
                code = int(code)
            except (ValueError, TypeError):
                code = 0
                logger.warning(f"[{self.id}] Invalid code value, using default: 0")

            try:
                priority = int(priority)
                if priority not in self.VALID_PRIORITIES:
                    priority = 4
                    logger.warning(f"[{self.id}] Invalid priority value, using default: 4 (warn)")
            except (ValueError, TypeError):
                priority = 4
                logger.warning(f"[{self.id}] Invalid priority value, using default: 4 (warn)")

            # Resolve context variables in message
            resolved_message = self._resolve_message_variables(message)

            # Log the warning message at appropriate level
            self._log_warning_message(resolved_message, code, priority)

            # Store details in global map for other components
            self._store_warning_in_globalmap(resolved_message, code, priority)

            # Update statistics using standard variable names
            if input_data is not None and not input_data.empty:
                rows_in = len(input_data)
                rows_out = rows_in  # Pass-through component, no rejection
                self._update_stats(rows_in, rows_out, 0)
                logger.info(f"[{self.id}] Processing complete: logged warning, passed through {rows_out} rows")
            else:
                rows_in = 1  # Count the warning operation itself
                rows_out = 1
                self._update_stats(rows_in, rows_out, 0)
                logger.info(f"[{self.id}] Processing complete: logged warning (no input data)")

            # Pass through input data unchanged
            return {'main': input_data if input_data is not None else pd.DataFrame()}

        except Exception as e:
            logger.error(f"[{self.id}] Processing failed: {e}")
            raise ComponentExecutionError(self.id, f"Failed to process warning: {e}", e) from e

    def _resolve_message_variables(self, message: str) -> str:
        """Resolve context and globalMap variables in the message."""
        if not isinstance(message, str):
            return str(message)

        resolved_message = message

        # Resolve context variables (${context.var})
        if self.context_manager:
            resolved_message = self.context_manager.resolve_string(resolved_message)

        # Resolve globalMap variables (((Integer)globalMap.get("key")))
        if self.global_map:
            pattern = r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'

            def replace_globalmap(match):
                key = match.group(1)
                value = self.global_map.get(key, 0)
                return str(value)

            resolved_message = re.sub(pattern, replace_globalmap, resolved_message)

        return resolved_message

    def _log_warning_message(self, message: str, code: int, priority: int) -> None:
        """Log the warning message at the appropriate level."""
        log_message = f"[{self.id}] Code {code}: {message}"
        priority_name = self.PRIORITY_NAMES.get(priority, 'unknown')

        if priority <= 1:
            logger.debug(f"TRACE: {log_message}")
        elif priority == 2:
            logger.debug(log_message)
        elif priority == 3:
            logger.info(log_message)
        elif priority == 4:
            logger.warning(log_message)
        elif priority == 5:
            logger.error(log_message)
        else:  # 6 or higher
            logger.critical(log_message)

        logger.debug(f"[{self.id}] Warning logged at priority {priority} ({priority_name})")

    def _store_warning_in_globalmap(self, message: str, code: int, priority: int) -> None:
        """Store warning details in globalMap for other components to access."""
        if self.global_map:
            self.global_map.put(f"{self.id}_MESSAGE", message)
            self.global_map.put(f"{self.id}_CODE", code)
            self.global_map.put(f"{self.id}_PRIORITY", priority)
            logger.debug(f"[{self.id}] Warning details stored in globalMap")
