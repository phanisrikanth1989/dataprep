"""Engine component for Warn (tWarn).

Logs a priority-rated warning message and passes input data through unchanged.

Config keys consumed (5 total):
  message             (str, default "this is a warning") -- message text
  code                (int | str, default "42")          -- warning code
  priority            (int | str, default "4")           -- log level 1-6
  tstatcatcher_stats  (bool, default False)              -- framework param
  label               (str, default "")                  -- framework param
"""
import logging
import re
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)

_GLOBALMAP_PATTERN = re.compile(r'\(\(\w+\)globalMap\.get\("(\w+)"\)\)')


@REGISTRY.register("Warn", "tWarn")
class Warn(BaseComponent):
    """tWarn engine implementation.

    Logs a configurable warning message at the specified priority level,
    stores it in GlobalMap, and passes input data through unchanged.

    Config keys:
        message: Warning message text (context vars resolved by base).
        code: Numeric warning code stored in GlobalMap (default 42).
        priority: Log level 1=TRACE…6=FATAL (default 4=WARN).
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Raise ConfigurationError for invalid message, code, or priority.

        Called on unresolved config. All values may be strings from converter.
        """
        if "message" in self.config and not isinstance(self.config["message"], str):
            raise ConfigurationError(
                f"[{self.id}] Config 'message' must be a string"
            )

        if "code" in self.config:
            try:
                int(self.config["code"])
            except (ValueError, TypeError):
                raise ConfigurationError(
                    f"[{self.id}] Config 'code' must be an integer; got '{self.config['code']}'"
                )

        if "priority" in self.config:
            try:
                p = int(self.config["priority"])
            except (ValueError, TypeError):
                raise ConfigurationError(
                    f"[{self.id}] Config 'priority' must be an integer 1-6; "
                    f"got '{self.config['priority']}'"
                )
            if p not in range(1, 7):
                raise ConfigurationError(
                    f"[{self.id}] Config 'priority' must be between 1 and 6; got {p}"
                )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Log warning message and pass input data through unchanged."""
        message = self.config.get("message", "this is a warning")
        code = int(self.config.get("code", 42))
        priority = int(self.config.get("priority", 4))

        # Resolve globalMap variable references (context already resolved by base)
        resolved_message = _resolve_globalmap_vars(message, self.global_map)

        # Log at configured priority level
        _log_at_priority(self.id, code, resolved_message, priority)

        # Store warning details in GlobalMap
        if self.global_map:
            self.global_map.put(f"{self.id}_MESSAGE", resolved_message)
            self.global_map.put(f"{self.id}_CODE", code)
            self.global_map.put(f"{self.id}_PRIORITY", priority)

        return {
            "main": input_data if input_data is not None else pd.DataFrame(),
            "reject": None,
        }


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _resolve_globalmap_vars(message: str, global_map) -> str:
    """Replace ``((Type)globalMap.get("key"))`` patterns with GlobalMap values."""
    if not isinstance(message, str) or global_map is None:
        return str(message) if message is not None else ""

    def _replace(match: re.Match) -> str:
        return str(global_map.get(match.group(1), 0))

    return _GLOBALMAP_PATTERN.sub(_replace, message)


def _log_at_priority(component_id: str, code: int, message: str, priority: int) -> None:
    """Log message at the Python log level matching Talend priority 1-6."""
    log_message = f"[{component_id}] Code {code}: {message}"
    if priority <= 2:
        logger.debug(log_message)
    elif priority == 3:
        logger.info(log_message)
    elif priority == 4:
        logger.warning(log_message)
    elif priority == 5:
        logger.error(log_message)
    else:  # 6 = FATAL
        logger.critical(log_message)
