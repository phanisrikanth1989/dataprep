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

    Talend row-field references (``flowname.columnname`` syntax, e.g.
    ``row2.rowid``) in VALUE expressions are resolved against each input
    row.  When multiple rows are present the component executes once per
    row and the last row's value wins -- matching Talend's per-row model.
"""
import logging
import re
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Row-field reference pattern
# ---------------------------------------------------------------------------
# Matches Talend ``flowname.columnname`` dot syntax ONLY.
# Bare words (e.g. the string literal ``ok``) are NOT treated as row
# references to avoid colliding with plain string values stripped of quotes
# by the converter.
_ROW_REF_RE = re.compile(r"^[A-Za-z_]\w*\.([A-Za-z_]\w*)$")


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

    @staticmethod
    def _resolve_row_ref(value: Any, data_row: "pd.Series") -> Any:
        """Resolve a Talend row-field reference against the current data row.

        Talend uses ``flowname.columnname`` syntax (e.g. ``row2.rowid``) inside
        tSetGlobalVar VALUE expressions to reference the current row's column
        value.  If *value* matches this pattern and the column exists in
        *data_row*, the actual column value is returned.  Otherwise *value* is
        returned unchanged (pass-through for literals and pre-resolved expressions).

        Args:
            value: The raw VALUE string from the variable definition.
            data_row: The current pd.Series representing one input row.

        Returns:
            The resolved column value, or *value* unchanged if no match.
        """
        if not isinstance(value, str):
            return value
        # Java/context markers already resolved by BaseComponent before _process()
        if value.startswith("{{") or value.startswith("${"):
            return value
        m = _ROW_REF_RE.match(value.strip())
        if m:
            col = m.group(1)
            if col in data_row.index:
                raw = data_row[col]
                # Normalize numpy/pandas scalars to native Python types so that
                # Py4J can marshal the value into the Java globalMap without
                # raising "'numpy.int64' object has no attribute '_get_object_id'".
                if hasattr(raw, "item"):
                    try:
                        return raw.item()
                    except (AttributeError, ValueError):
                        pass
                return raw
            logger.warning(
                "Row-field reference '%s' found but column '%s' not in input row "
                "-- keeping literal value",
                value,
                col,
            )
        return value

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
        """Set globalMap variables per input row and pass input data through unchanged.

        Talend processes tSetGlobalVar once per input row: for every row arriving
        from the upstream flow, each entry in the VARIABLES table is evaluated and
        ``globalMap.put(key, value)`` is called.  The last row therefore wins for
        each variable -- this matches Talend semantics exactly.

        Row-field references in VALUE (e.g. ``row2.rowid``) are resolved from the
        current data row.  When no input data is present the raw config value
        (a literal or already-resolved expression) is used directly.

        Args:
            input_data: Any input (DataFrame or None). Passed through unchanged.

        Returns:
            dict with ``main`` key containing the unmodified input.
        """
        variables = self._get_variables()
        logger.info("[%s] Setting %d global variable(s)", self.id, len(variables))

        # Build iteration list -- sentinel [None] is the no-data path so the
        # inner logic runs once with row-ref resolution disabled.
        if isinstance(input_data, pd.DataFrame) and not input_data.empty:
            data_rows = [row for _, row in input_data.iterrows()]
        else:
            data_rows = [None]

        for data_row in data_rows:
            for i, var_def in enumerate(variables):
                if not isinstance(var_def, dict):
                    msg = (
                        f"[{self.id}] Variable entry at index {i} must be a dict, "
                        f"got {type(var_def).__name__}"
                    )
                    if self.die_on_error:
                        raise ConfigurationError(msg)
                    logger.warning("%s -- skipping", msg)
                    continue

                var_name = self._get_var_name(var_def)
                if not var_name:
                    msg = (
                        f"[{self.id}] Variable entry at index {i} has no name "
                        f"(key/name field missing or empty)"
                    )
                    if self.die_on_error:
                        raise ConfigurationError(msg)
                    logger.warning("%s -- skipping", msg)
                    continue

                var_value = self._get_var_value(var_def)

                # Resolve Talend row-field references (e.g. ``row2.rowid``)
                # against the current data row when input data is present.
                if data_row is not None:
                    var_value = self._resolve_row_ref(var_value, data_row)

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
