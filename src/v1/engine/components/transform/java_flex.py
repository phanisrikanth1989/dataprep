"""Engine component for tJavaFlex (single-scope Java/Groovy execution).

Executes user-supplied Java/Groovy code as a single bridge call in three
sections: START (once before the row loop), MAIN (per row, inside the loop),
END (once after the loop). All three sections share one Groovy scope, so a
variable declared in START is visible in MAIN and END (Talend tJavaFlex parity).

Unlike tJavaRow, this component:
- NEVER short-circuits on empty/None input: START and END must always run
  exactly once even when there are zero rows. The bridge handles the empty case
  and returns a zero-row DataFrame with the declared output_schema columns.
- Has no REJECT flow (same as tJavaRow -- tJavaFlex has no native reject
  connector in Talend).
- Delegates row iteration to the Groovy script assembled by
  ``java_flex_script.build_script``; the bridge executes the whole script in
  one call (no chunking -- cross-row START state must not be split).

Error semantics (Talend parity):
    No try/catch around the row body. Uncaught bridge exceptions propagate as
    ``ComponentExecutionError`` carrying the original cause. The engine's
    ``die_on_error`` at the parent flow decides termination.

Note:
    ``code_start``, ``code_main``, ``code_end``, and ``imports`` live in
    ``ContextManager.SKIP_RESOLUTION_KEYS`` -- they are never
    ``${context.X}``-resolved. User code reads context at runtime via the
    Java-side ``globalMap`` / ``context`` bindings populated by the pre-call
    sync.

Config keys consumed:
    code_start      (str, optional) -- Groovy executed once before the row loop.
    code_main       (str, optional) -- Groovy executed once per row (inside loop).
    code_end        (str, optional) -- Groovy executed once after the row loop.
    imports         (str, optional) -- Java import block prepended before script.
    auto_propagate  (bool, default False) -- copy matching input cols to output
                    before/after MAIN (controlled by ``propagate_timing``).
    propagate_timing (str, default "before") -- "before" or "after".
    input_row_name  (str, default "row1") -- Groovy loop variable for input row.
    output_row_name (str, default "row2") -- Groovy loop variable for output row.
    output_schema   (dict|list, optional) -- output column types.
    tstatcatcher_stats (bool, default False) -- BaseComponent stats hook (passthrough).
    label           (str, optional) -- display label (passthrough).
"""
import logging
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError
from ._code_component_mixin import CodeComponentMixin
from .java_flex_script import build_script
from .map.map_compiled_script import groovy_escape_expression

logger = logging.getLogger(__name__)

_VALID_PROPAGATE_TIMINGS = frozenset({"before", "after"})


@REGISTRY.register("JavaFlexComponent", "JavaFlex", "tJavaFlex")
class JavaFlexComponent(CodeComponentMixin, BaseComponent):
    """tJavaFlex engine implementation -- single-scope Groovy execution.

    Assembles a Groovy script with START/MAIN/END sections (via
    ``java_flex_script.build_script``) and executes it as a SINGLE bridge call
    (no chunking -- cross-row START state must not be split). All three
    sections share one Groovy scope.

    Config keys: see module docstring.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration (Rule 12 -- structural checks only).

        Raises:
            ConfigurationError: If ``code_start``, ``code_main``, or
                ``code_end`` is provided but not a string; if ``imports`` is
                provided but not a string; if ``auto_propagate`` is provided
                but not a bool; if ``propagate_timing`` is provided but not
                "before" or "after"; if ``output_schema`` is provided but not
                a dict or list.

        Note:
            Groovy syntax validity is intentionally deferred to the bridge,
            which surfaces compile errors with full diagnostics.
        """
        for key in ("code_start", "code_main", "code_end"):
            val = self.config.get(key)
            if val is not None and not isinstance(val, str):
                raise ConfigurationError(
                    f"[{self.id}] '{key}' must be a string, got {type(val).__name__}"
                )

        imports = self.config.get("imports", "")
        if imports and not isinstance(imports, str):
            raise ConfigurationError(
                f"[{self.id}] 'imports' must be a string"
            )

        auto_propagate = self.config.get("auto_propagate")
        if auto_propagate is not None and not isinstance(auto_propagate, bool):
            raise ConfigurationError(
                f"[{self.id}] 'auto_propagate' must be a bool"
            )

        propagate_timing = self.config.get("propagate_timing")
        if propagate_timing is not None and propagate_timing not in _VALID_PROPAGATE_TIMINGS:
            raise ConfigurationError(
                f"[{self.id}] 'propagate_timing' must be 'before' or 'after', "
                f"got {propagate_timing!r}"
            )

        output_schema = self.config.get("output_schema")
        if output_schema is not None and not isinstance(output_schema, (dict, list)):
            raise ConfigurationError(
                f"[{self.id}] 'output_schema' must be a dict or list"
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict[str, Any]:
        """Assemble and execute the tJavaFlex Groovy script once over all rows.

        Key differences from tJavaRow._process:
        - NEVER short-circuits on empty input: START/END must always execute.
          If ``input_data`` is None, an empty DataFrame is passed to the bridge.
        - Delegates row iteration to the assembled Groovy script (via
          ``build_script``); the bridge runs one call covering all rows.

        Steps:
            1. Normalise ``input_data`` (None -> empty DataFrame).
            2. Derive ``output_cols`` from ``config['output_schema']``; build
               ``output_schema`` dict[str, str] for the bridge.
            3. Derive ``input_cols`` and ``input_schema`` dict from
               ``schema_inputs_map`` / ``input_schema`` (same precedence as
               java_row_component.py:222-235).
            4. Assemble the Groovy script via ``build_script``; prepend
               ``imports`` when present; apply ``groovy_escape_expression``.
            5. Verify ``self.java_bridge`` is set.
            6. Push engine GlobalMap -> ``self.java_bridge.global_map`` and
               ContextManager -> ``self.java_bridge.context`` BEFORE the call.
            7. Call ``self.java_bridge.execute_java_flex``.
            8. Read bridge context/global_map BACK into the engine AFTER call.
            9. Return ``{"main": out_df, "reject": None}``.

        Args:
            input_data: Upstream DataFrame, or None when no upstream rows exist.

        Returns:
            Dict with ``main`` (output DataFrame) and ``reject`` (always None).

        Raises:
            ComponentExecutionError: If no Java bridge is wired, or if the
                bridge raises during script execution. Original exception
                preserved as ``cause``.
        """
        # ---- 1. Normalise input (NEVER short-circuit -- START/END must run) ----
        if input_data is None:
            input_data = pd.DataFrame()

        # ---- 2. Derive output_cols and output_schema dict ----
        raw_output_schema = self.config.get("output_schema")
        if isinstance(raw_output_schema, list):
            output_cols: list[str] = [
                col["name"]
                for col in raw_output_schema
                if isinstance(col, dict) and "name" in col
            ]
            output_schema_dict: dict[str, str] = {
                col["name"]: col.get("type", "str")
                for col in raw_output_schema
                if isinstance(col, dict) and "name" in col
            }
        elif isinstance(raw_output_schema, dict):
            output_cols = list(raw_output_schema.keys())
            output_schema_dict = dict(raw_output_schema)
        else:
            output_cols = []
            output_schema_dict = {}

        # ---- 3. Derive input_cols and input_schema dict ----
        # Mirror java_row_component.py:222-235: prefer schema_inputs_map
        # (per-flow) then fall back to flat input_schema list.
        input_schema_dict: dict[str, str] = {}
        schema_inputs_map = getattr(self, "schema_inputs_map", None) or {}
        for _flow_name, flow_cols in schema_inputs_map.items():
            if isinstance(flow_cols, list):
                for col in flow_cols:
                    if isinstance(col, dict) and "name" in col:
                        input_schema_dict[col["name"]] = col.get("type", "str")
        if not input_schema_dict:
            for col in getattr(self, "input_schema", []) or []:
                if isinstance(col, dict) and "name" in col:
                    input_schema_dict[col["name"]] = col.get("type", "str")

        input_cols: list[str] = list(input_schema_dict.keys())

        # ---- 4. Assemble Groovy script ----
        code_start: str = self.config.get("code_start", "") or ""
        code_main: str = self.config.get("code_main", "") or ""
        code_end: str = self.config.get("code_end", "") or ""
        imports: str = self.config.get("imports", "") or ""
        auto_propagate: bool = bool(self.config.get("auto_propagate", False))
        propagate_timing: str = self.config.get("propagate_timing", "before") or "before"
        input_row_name: str = self.config.get("input_row_name", "row1") or "row1"
        output_row_name: str = self.config.get("output_row_name", "row2") or "row2"

        script = build_script(
            code_start=code_start,
            code_main=code_main,
            code_end=code_end,
            input_cols=input_cols,
            output_cols=output_cols,
            input_row_name=input_row_name,
            output_row_name=output_row_name,
            auto_propagate=auto_propagate,
            propagate_timing=propagate_timing,
        )

        if imports:
            script = imports + "\n" + script

        script = groovy_escape_expression(script)

        logger.debug(
            "[%s] tJavaFlex script assembled: %d rows, script_len=%d chars",
            self.id, len(input_data), len(script),
        )

        # ---- 5. Verify bridge ----
        if not self.java_bridge:
            raise ComponentExecutionError(
                self.id,
                "Java execution requested but no Java bridge available",
            )

        # ---- 6. Push engine state into bridge BEFORE call ----
        if self.global_map:
            self.java_bridge.global_map.update(self.global_map._map)
        if self.context_manager:
            for key, value in self.context_manager.get_all().items():
                self.java_bridge.context[key] = value

        # ---- 7. Execute ----
        try:
            out_df = self.java_bridge.execute_java_flex(
                df=input_data,
                script=script,
                output_schema=output_schema_dict,
                input_schema=input_schema_dict or None,
            )
        except Exception as e:
            logger.error(
                "[%s] tJavaFlex execution failed: %s: %s",
                self.id, e.__class__.__name__, e,
            )
            raise ComponentExecutionError(
                self.id,
                f"tJavaFlex execution failed: {e}",
                cause=e,
            ) from e

        # ---- 8. Read bridge state BACK into engine AFTER call ----
        if self.context_manager:
            for key, value in self.java_bridge.context.items():
                value_type = self.context_manager.get_type(key)
                self.context_manager.set(key, value, value_type)
        if self.global_map:
            for key, value in self.java_bridge.global_map.items():
                self.global_map.put(key, value)

        # ---- 9. Return ----
        return {"main": out_df, "reject": None}
