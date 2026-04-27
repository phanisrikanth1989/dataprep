"""Engine component for Die (tDie).

Terminates job execution with a priority-rated error message and exit code.

Config keys consumed (6 total):
  message             (str, default "the end is near")   -- termination message
  code                (int | str, default "4")            -- error code
  priority            (int | str, default "5")            -- log level 1-6
  exit_jvm            (bool, default False)               -- accepted; not supported
  tstatcatcher_stats  (bool, default False)               -- framework param
  label               (str, default "")                   -- framework param
"""
import logging
import re
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError

logger = logging.getLogger(__name__)

_GLOBALMAP_PATTERN = re.compile(r'\(\(\w+\)globalMap\.get\("(\w+)"\)\)')


@REGISTRY.register("Die", "tDie")
class Die(BaseComponent):
    """tDie engine implementation.

    Always raises ComponentExecutionError (with exit_code attribute) to
    terminate the job. Statistics count all input rows as rejected.

    Config keys:
        message: Error message (context vars resolved by base; globalMap refs
                 resolved here).
        code: Error code logged before termination (default 4).
        priority: Log level 1=TRACE…6=FATAL (default 5=ERROR).
        exit_jvm: Accepted from converter but not actionable (JVM exit not
                  supported in Python engine).
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Raise ConfigurationError for invalid message, code, priority, or exit_code.

        Called on unresolved config. All numeric values may arrive as strings
        from the converter.
        """
        if "message" in self.config and self.config["message"] is not None:
            if not isinstance(self.config["message"], str):
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

        if "exit_code" in self.config:
            try:
                int(self.config["exit_code"])
            except (ValueError, TypeError):
                raise ConfigurationError(
                    f"[{self.id}] Config 'exit_code' must be an integer; "
                    f"got '{self.config['exit_code']}'"
                )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Count rows, log message, then raise ComponentExecutionError.

        This component never returns -- it always raises. _update_stats() is
        called manually because auto-counting requires a return value.
        """
        message = self.config.get("message", "the end is near")
        code = int(self.config.get("code", 4))
        priority = int(self.config.get("priority", 5))
        exit_code = int(self.config.get("exit_code", 1))

        # Resolve globalMap variable references (context already resolved by base)
        resolved_message = _resolve_globalmap_vars(message, self.global_map)

        # Log at configured priority level
        _log_at_priority(self.id, code, resolved_message, priority)

        # Record error state in GlobalMap
        if self.global_map:
            self.global_map.put(f"{self.id}_MESSAGE", resolved_message)
            self.global_map.put(f"{self.id}_CODE", code)
            self.global_map.put(f"{self.id}_PRIORITY", priority)
            self.global_map.put(f"{self.id}_EXIT_CODE", exit_code)
            self.global_map.put("JOB_ERROR_MESSAGE", resolved_message)
            self.global_map.put("JOB_EXIT_CODE", exit_code)

        # Count stats manually -- Die raises before base can auto-count
        rows = len(input_data) if input_data is not None and not input_data.empty else 1
        self._update_stats(rows, 0, rows)
        # Push stats to GlobalMap now -- base class _update_global_map() runs
        # only after _process() returns, but Die always raises, so we do it here.
        self._update_global_map()

        error = ComponentExecutionError(
            self.id,
            f"Job terminated by tDie: {resolved_message} (exit code: {exit_code})",
        )
        error.exit_code = exit_code
        raise error


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
