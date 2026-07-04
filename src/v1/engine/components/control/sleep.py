"""Engine component for Sleep (tSleep).

Pauses job execution for a configurable duration then passes data through unchanged.

Config keys consumed (3 total):
  pause_duration      (str | int | float, default "1") -- sleep duration in seconds
  tstatcatcher_stats  (bool, default False)            -- framework param
  label               (str, default "")                -- framework param
"""
import logging
import math
import time
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("Sleep", "SleepComponent", "tSleep")
class Sleep(BaseComponent):
    """tSleep engine implementation.

    Pauses execution for the configured duration then passes input data
    through unchanged to the next component.

    Config keys:
        pause_duration: Seconds to sleep (int, float, or numeric string).
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Raise ConfigurationError if pause_duration is an unsupported type.

        Called on unresolved config. Accepts int, float, and string (which
        may be a numeric string or a context variable resolved later).
        """
        duration = self.config.get("pause_duration", 0)
        if not isinstance(duration, (int, float, str)):
            raise ConfigurationError(
                f"[{self.id}] Config 'pause_duration' must be a number or string; "
                f"got {type(duration).__name__}"
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Sleep for configured duration then pass input through unchanged."""
        duration_raw = self.config.get("pause_duration", 0)
        try:
            pause_duration = float(duration_raw)
        except (ValueError, TypeError):
            logger.warning(
                f"[{self.id}] Cannot parse pause_duration '{duration_raw}'; skipping sleep"
            )
            pause_duration = 0.0

        if not math.isfinite(pause_duration):
            logger.warning(
                f"[{self.id}] pause_duration is not finite ({pause_duration}); skipping sleep"
            )
            pause_duration = 0.0

        if pause_duration > 0:
            logger.info(f"[{self.id}] Sleeping for {pause_duration} seconds")
            time.sleep(pause_duration)
            logger.info(f"[{self.id}] Sleep completed")
        else:
            logger.debug(f"[{self.id}] Skipping sleep: non-positive duration ({pause_duration})")

        return {
            "main": input_data if input_data is not None else pd.DataFrame(),
            "reject": None,
        }
