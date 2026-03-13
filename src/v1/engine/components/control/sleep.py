"""
SleepComponent - Introduces a delay in the execution of the job.

Talend equivalent: tSleep
"""
import logging
import time
from typing import Dict, Any, Optional, List

import pandas as pd

from ...base_component import BaseComponent
from ...exceptions import ConfigurationError, ComponentExecutionError

logger = logging.getLogger(__name__)


class SleepComponent(BaseComponent):
    """
    Introduce a configurable delay in job execution flow.

    This component pauses job execution for a specified duration, useful for
    timing control, rate limiting, or waiting for external systems. The pause
    duration can be configured statically or dynamically using context variables.

    Configuration:
        pause_duration (float): Duration to sleep in seconds. Default: 0
                               Supports context variables like ${context.delay}

    Inputs:
        main: Optional input DataFrame (passed through unchanged)

    Outputs:
        main: Same as input DataFrame (pass-through component)

    Statistics:
        NB_LINE: Always 1 (represents one sleep operation)
        NB_LINE_OK: Always 1 (sleep operations don't fail)
        NB_LINE_REJECT: Always 0

    Example configuration:
        {
            "pause_duration": 5.5
        }

    # With context variable
        {
            "pause_duration": "${context.sleep_seconds}"
        }

    Notes:
        - Component blocks execution thread during sleep
        - Input data is passed through unchanged
        - Duration supports decimal values for sub-second precision
        - Zero or negative duration results in no sleep operation
        - Context variables are resolved before sleep execution
    """

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # pause_duration is optional with default, but validate if present
        if 'pause_duration' in self.config:
            duration = self.config['pause_duration']

            # Allow string values for context variables
            if isinstance(duration, str):
                # Context variables like ${context.var} are valid
                if not (duration.strip().startswith('${') and duration.strip().endswith('}')):
                    # If it's a string but not a context variable, try to parse as number
                    try:
                        float(duration)
                    except (ValueError, TypeError):
                        errors.append("Config 'pause_duration' must be a number, context variable, or numeric string")
            elif not isinstance(duration, (int, float)):
                errors.append("Config 'pause_duration' must be a number or context variable")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Execute sleep operation for configured duration.

        Args:
            input_data: Input DataFrame (optional, passed through unchanged)

        Returns:
            Dictionary containing 'main' DataFrame (same as input)

        Raises:
            ConfigurationError: If configuration is invalid
            ComponentExecutionError: If sleep operation fails
        """
        logger.info(f"[{self.id}] Processing started: executing sleep operation")

        try:
            # Validate configuration
            config_errors = self._validate_config()
            if config_errors:
                error_msg = f"Invalid configuration: {'; '.join(config_errors)}"
                logger.error(f"[{self.id}] {error_msg}")
                raise ConfigurationError(error_msg)

            # Get pause duration with safe conversion
            pause_duration = self._get_pause_duration()

            # Log sleep start
            logger.info(f"[{self.id}] Sleeping for {pause_duration} seconds")

            # Sleep only if positive (zero functionality preserved)
            if pause_duration > 0:
                time.sleep(pause_duration)
            else:
                logger.debug(f"[{self.id}] Skipping sleep for non-positive duration: {pause_duration}")

            # Log completion
            logger.info(f"[{self.id}] Sleep completed")

            # Update statistics (always count as 1 operation)
            self._update_stats(1, 1, 0)

            # Pass through input data unchanged
            return {'main': input_data if input_data is not None else pd.DataFrame()}

        except ConfigurationError:
            # Re-raise configuration errors as-is
            raise
        except Exception as e:
            logger.error(f"[{self.id}] Processing failed: {e}")
            raise ComponentExecutionError(self.id, f"Sleep operation failed: {e}", e) from e

    def _get_pause_duration(self) -> float:
        """
        Get pause duration with safe conversion and context variable resolution.

        Returns:
            Pause duration in seconds as float
        """
        # Get raw value with default
        duration_value = self.config.get('pause_duration', 0)

        # If it's already a number, use it directly
        if isinstance(duration_value, (int, float)):
            return float(duration_value)

        # If it's a string, it might be a context variable or numeric string
        if isinstance(duration_value, str):
            # Resolve context variables if available
            resolved_value = duration_value
            if self.context_manager:
                resolved_value = self.context_manager.resolve_string(duration_value)

            # Try to convert to float
            try:
                return float(resolved_value)
            except (ValueError, TypeError):
                logger.warning(f"[{self.id}] Could not convert pause_duration '{resolved_value}' to number, using 0")
                return 0.0

        # For any other type, default to 0
        logger.warning(f"[{self.id}] Invalid pause_duration type '{type(duration_value)}', using 0")
        return 0.0
