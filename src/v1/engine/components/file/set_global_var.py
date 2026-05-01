"""tSetGlobalVar component - Sets globalMap variables from a KEY/VALUE table.

Talend equivalent: tSetGlobalVar

Config mapping (Talend XML param -> v1 engine config key):
    VARIABLES  -> variables   (list of {key, value} dicts, required)
                  legacy fallback: VARIABLES (uppercase) with {name, value} dicts

Engine-only:
    die_on_error (bool, default True) -- inherited from BaseComponent.
                  When False, a failing variable assignment is skipped with
                  a warning; other variables in the table are still set.

GlobalMap variables:
    {id}_NB_LINE / NB_LINE_OK / NB_LINE_REJECT  via _update_stats()
    (All always 0 -- this component sets variables, not data rows.)

Behaviour:
    Input data is passed through unchanged.  Values are resolved by
    BaseComponent._resolve_expressions() before _process() is called, so
    context variables and {{java}} markers are already replaced.
"""
import logging
from typing import Any, Dict, Optional

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("SetGlobalVar", "tSetGlobalVar")
class SetGlobalVar(BaseComponent):
    """Sets globalMap variables from a KEY/VALUE table.  Input rows pass through."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_variables(self):
        """Return the normalised variable list, supporting both key shapes."""
        # Preferred: converter outputs lowercase ``variables`` with {key, value}
        rows = self.config.get("variables") or self.config.get("VARIABLES") or []
        if not isinstance(rows, list):
            return []
        return rows

    @staticmethod
    def _get_var_name(row: dict) -> str:
        """Extract variable name from a row dict (supports key / name)."""
        return row.get("key") or row.get("name") or ""

    @staticmethod
    def _get_var_value(row: dict) -> Any:
        """Extract variable value from a row dict (supports value / VALUE)."""
        if "value" in row:
            return row["value"]
        if "VALUE" in row:
            return row["VALUE"]
        return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate configuration structure (keys + container shape only).

        Note:
            Content-level validation (e.g. individual variable names) is
            intentionally deferred to _process() after context-variable
            resolution per Rule 12 of MANUAL_COMPONENT_AUTHORING.md.
        """
        if "variables" in self.config:
            rows = self.config["variables"]
        elif "VARIABLES" in self.config:
            rows = self.config["VARIABLES"]
        else:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'variables'"
            )
        if not isinstance(rows, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'variables' must be a list, got {type(rows).__name__}"
            )

    def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        """Set globalMap variables and pass input data through unchanged.

        Args:
            input_data: Any input (DataFrame or None). Passed through unchanged.

        Returns:
            dict with ``main`` key containing the unmodified input.
        """
        variables = self._get_variables()
        logger.info("[%s] Setting %d global variable(s)", self.id, len(variables))

        for i, row in enumerate(variables):
            if not isinstance(row, dict):
                msg = f"[{self.id}] Variable entry at index {i} must be a dict, got {type(row).__name__}"
                if self.die_on_error:
                    raise ConfigurationError(msg)
                logger.warning("%s -- skipping", msg)
                continue

            var_name = self._get_var_name(row)
            if not var_name:
                msg = f"[{self.id}] Variable entry at index {i} has no name (key/name field missing or empty)"
                if self.die_on_error:
                    raise ConfigurationError(msg)
                logger.warning("%s -- skipping", msg)
                continue

            var_value = self._get_var_value(row)

            try:
                if self.global_map is not None:
                    self.global_map.put(var_name, var_value)
                logger.debug("[%s] Set %s = %r", self.id, var_name, var_value)
            except Exception as exc:
                msg = f"[{self.id}] Failed to set global variable '{var_name}': {exc}"
                if self.die_on_error:
                    raise ConfigurationError(msg) from exc
                logger.warning("%s -- skipping", msg)

        # NB_LINE is always 0 -- this component does not process data rows
        self._update_stats(rows_read=0, rows_ok=0, rows_reject=0)
        logger.info("[%s] Global variable assignment complete", self.id)
        return {"main": input_data}
