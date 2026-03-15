"""
Replicate - Replicate input data to multiple outputs.

Talend equivalent: tReplicate
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class Replicate(BaseComponent):
    """
    Replicate input data to multiple outputs.

    Configuration:
        output_count (int): Number of outputs to create. Default: 2
        die_on_error (bool): Stop execution on error. Default: True

    Inputs:
        main: Input DataFrame to replicate

    Outputs:
        main: Primary replicated output
        output_1, output_2, etc.: Additional outputs based on output_count

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully replicated
        NB_LINE_REJECT: Rows rejected (always 0 for replicate)

    Example configuration:
        {
            "output_count": 3,
            "die_on_error": True
        }
    """

    def _validate_config(self) -> List[str]:
        """Validate component configuration."""
        errors = []

        # Validate output_count
        output_count = self.config.get('output_count', 2)
        if not isinstance(output_count, int):
            errors.append("Config 'output_count' must be an integer")
        elif output_count < 1:
            errors.append("Config 'output_count' must be at least 1")
        elif output_count > 10:  # Reasonable limit
            errors.append("Config 'output_count' cannot exceed 10")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process input data to replicate it to multiple outputs.

        Args:
            input_data: Input DataFrame to replicate

        Returns:
            Dictionary with replicated outputs

        Raises:
            RuntimeError: If processing fails and die_on_error is True
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        try:
            # Get configuration with defaults
            output_count = self.config.get('output_count', 2)
            die_on_error = self.config.get('die_on_error', True)

            # For Replicate, we return the same data as 'main' output
            # The engine will handle mapping this to multiple output flows
            # based on the job configuration flows section
            result = {'main': input_data.copy()}

            # If multiple outputs are configured, add them as well
            if output_count > 1:
                logger.debug(f"[{self.id}] Creating {output_count} outputs")
                for i in range(1, output_count + 1):
                    result[f'output_{i}'] = input_data.copy()

            # Update statistics
            self._update_stats(rows_in, rows_in, 0)
            logger.info(f"[{self.id}] Processing complete: "
                        f"replicated {rows_in} rows to {len(result)} outputs")

            return result

        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            logger.error(f"[{self.id}] {error_msg}")

            if die_on_error:
                raise RuntimeError(f"[{self.id}] {error_msg}") from e
            else:
                logger.warning(f"[{self.id}] Continuing after error, returning empty")
                self._update_stats(0, 0, rows_in if 'rows_in' in locals() else 0)
                return {'main': pd.DataFrame()}
