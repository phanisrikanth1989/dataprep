"""Engine component for tJavaRow (per-row Java/Groovy execution).

Executes user-supplied Java code ONCE per input row. Java side compiles the
code once at the start of the call and reuses the compiled script across rows
(Phase 5.1 pattern, JavaBridge.java:200-204).

Error semantics (Talend parity, revision 2):
    Talend's tJavaRow has NO native REJECT connector and NO try/catch around
    the row body in the generated code (verified Talaxie tJavaRow_java.xml +
    tJavaRow_main.javajet at planning time). Uncaught row-level exceptions
    propagate up the call stack and the parent DIE_ON_ERROR (on tFlowToIterate
    or similar) decides job termination.

    This component matches that contract exactly:
    - On bridge exception, log via [{component_id}] prefix and re-raise the
      original exception (wrapped as ComponentExecutionError carrying the cause).
    - Do NOT build a reject DataFrame; do NOT swallow the error.
    - BaseComponent's die_on_error semantics (configured at the parent flow)
      handle fatal-vs-continue at the engine level.

    This is also zero behavior change vs the legacy java_row_component.py:96-98
    which already re-raises on bridge errors.

Note (Phase 8 D-26 supersession):
    java_code/imports are NEVER ${context.X}-resolved
    (ContextManager.SKIP_RESOLUTION_KEYS at
    src/v1/engine/context_manager.py:37-41). User code reads context
    programmatically via globalMap -- NOT via string substitution into
    the source.

Config keys consumed:
    java_code     (str, required) -- Java/Groovy source executed per row.
    imports       (str, default "") -- Java import block prepended to
                                       java_code with a newline separator
                                       before bridge call (D-07/D-08).
    output_schema (dict|list, optional) -- output column types
                                           (BaseComponent step 7c).
    tstatcatcher_stats (bool, default False) -- BaseComponent stats hook (passthrough).
    label              (str, optional) -- BaseComponent display label (passthrough).

Anti-patterns avoided (Phase 8 PATTERNS.md table -- consult that file for
the bare-string patterns the negative-grep gates look for):
- AP-1: built-in generic exceptions are forbidden -- only custom engine
        exceptions (ConfigurationError / ComponentExecutionError /
        ExpressionError) appear below.
- AP-3: BaseComponent step 8 (``_update_stats_from_result``) auto-counts
        from the result dict; no manual stats update is performed here.
- AP-4: ``_get_context_dict`` is inherited from CodeComponentMixin (D-09);
        no per-component re-implementation here.
- AP-8: the bridge's ``_call_java_with_sync`` internal wrapper owns
        bidirectional sync; this component does not invoke the sync
        machinery directly.
- AP-9: bridge accessed via ``self.java_bridge`` (set by engine), NOT via
        the legacy ContextManager-based lookup.
- AP-12: the registry decorator wires both the V1 and Talend names into
         the central REGISTRY (Rule 9).
"""
import logging
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError, ExpressionError  # noqa: F401  -- ExpressionError kept for symmetry with java_component.py and may surface from bridge wrapping
from ._code_component_mixin import CodeComponentMixin

logger = logging.getLogger(__name__)


@REGISTRY.register("JavaRowComponent", "tJavaRow")
class JavaRowComponent(CodeComponentMixin, BaseComponent):
    """tJavaRow engine implementation -- per-row Java/Groovy execution.

    Executes user-supplied Java code ONCE per input row. Per the revision-2
    Talaxie verification (tJavaRow_java.xml + tJavaRow_main.javajet), Talend's
    tJavaRow has NO native REJECT and NO try/catch around the row body. This
    component matches that contract: per-row failures propagate up via
    ``_process`` raise (wrapped as ``ComponentExecutionError`` carrying the
    original cause). The parent flow's ``die_on_error`` decides termination.
    See module docstring for the parity-source citation.

    Config keys:
        java_code     (str, required): Java/Groovy source executed per row.
        imports       (str, default ""): Java import block prepended once with a
            newline separator before being sent to the bridge (D-07/D-08).
            Bridge surfaces compile errors with full diagnostics; no
            client-side syntax check.
        output_schema (dict|list, optional): output column types
            (BaseComponent step 7c).
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration (Rule 12 -- presence + container shape only).

        Raises:
            ConfigurationError: If ``java_code`` is missing/empty, if
                ``imports`` is provided but not a string, or if
                ``output_schema`` is provided but not a ``dict`` or ``list``.

        Note:
            Java syntax validity, imports content shape, and schema column
            types are intentionally deferred to ``_process`` / step 7c. The
            Java bridge surfaces compile errors with full diagnostics.
            ``${context.X}`` literals in ``imports`` arrive verbatim because
            ``ContextManager.SKIP_RESOLUTION_KEYS`` excludes the ``imports``
            field from resolution.
        """
        if not self.config.get("java_code"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'java_code'"
            )
        imports = self.config.get("imports", "")
        if imports and not isinstance(imports, str):
            raise ConfigurationError(
                f"[{self.id}] 'imports' must be a string"
            )
        output_schema = self.config.get("output_schema")
        if output_schema is not None and not isinstance(output_schema, (dict, list)):
            raise ConfigurationError(
                f"[{self.id}] 'output_schema' must be a dict or list"
            )
        
        # chunk_size: optional override of the bridge's default Py4J-safe
        # row batch. Accepts int or numeric str (e.g. "50000") so JSON
        # configs that store numbers as strings still validate.
        chunk_size = self.config.get("chunk_size")
        if chunk_size is not None:
            try:
                cs_int = int(chunk_size)
            except (TypeError, ValueError) as e:
                raise ConfigurationError(
                    f"[{self.id}] 'chunk_size' must be a positive int, got {chunk_size!r}"
                ) from e

            if cs_int <= 0:
                raise ConfigurationError(
                    f"[{self.id}] 'chunk_size' must be a positive int, got {chunk_size!r}"
                )
    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict[str, Any]:
        """Execute the per-row Java code; propagate errors (NO REJECT).

        Steps:
            1. Short-circuit when ``input_data`` is ``None`` or empty -- return
               ``{"main": input_data, "reject": None}`` without invoking the
               bridge (matches legacy line 40-42 short-circuit, AP-3-safe
               because no rows means nothing to count).
            2. Pull ``java_code``, ``imports``, ``output_schema`` from
               ``self.config`` (already free of ``${context.X}`` substitution
               per ``SKIP_RESOLUTION_KEYS``).
            3. Prepend ``imports`` to ``java_code`` with a newline separator
               when ``imports`` is non-empty (D-07/D-08).
            4. Verify ``self.java_bridge`` was wired by the engine
               (raises ``ComponentExecutionError`` otherwise -- AP-9 fix).
            5. Hand the resulting source to ``java_bridge.execute_java_row``
               which compiles once on the Java side and loops across rows
               (Phase 5.1 compiled-script pattern). Bridge wraps the call
               in ``_call_java_with_sync`` (D-20). The bridge owns
               bidirectional sync; this component must not invoke the
               sync machinery directly (AP-8). BaseComponent step 8 owns
               the stats update; this component must not invoke the stats
               helper directly (AP-3).
            6. On bridge exception, log via ``[{self.id}]`` prefix and
               re-raise wrapped as ``ComponentExecutionError`` with the
               original exception as ``cause`` (Talend parity, revision 2 --
               see module docstring).
            7. Return ``{"main": main_df, "reject": None}``. ``reject`` is
               always ``None`` because tJavaRow has no reject flow.

        Args:
            input_data: Upstream DataFrame, or ``None`` / empty when no
                upstream rows are available.

        Returns:
            Dict with ``main`` (transformed DataFrame; or the input/None for
            empty input) and ``reject`` (always ``None``; tJavaRow has no
            reject flow per Talend parity).

        Raises:
            ComponentExecutionError: If the engine never wired a Java bridge,
                or if the bridge raises while compiling/executing the user's
                Java code. The original exception is preserved as ``cause``.
        """
        if input_data is None or input_data.empty:
            return {"main": input_data, "reject": None}

        java_code: str = self.config.get("java_code", "")
        imports: str = self.config.get("imports", "") or ""
        output_schema = self.config.get("output_schema")

        # Bridge contract: output_schema must be dict[str, str] (col -> python type).
        # Converter emits list[{"name": ..., "type": ...}]; normalize here.
        if isinstance(output_schema, list):
            output_schema = {
                col["name"]: col.get("type", "str")
                for col in output_schema
                if isinstance(col, dict) and "name" in col
            }
        elif output_schema is None:
            output_schema = {}

        # Build input_schema dict from the upstream flow's declared schema.
        # The engine populates self.schema_inputs_map from comp_config.schema.inputs
        # (engine.py:162) and self.input_schema as a flat list (engine.py:156).
        # We feed this to the bridge so input columns NOT echoed to output
        # (e.g. Talend-style ``incremental_value`` int read by the row body
        # but absent from the output schema) keep their declared type during
        # Arrow serialization. Without this hint the bridge dtype-infers,
        # which silently demotes object/float64 NaN-promoted columns to
        # String/Double on the Java side and breaks ``int x = input_row.col``
        # primitive coercion (e.g. wrong VALUEDATE in calendar-arithmetic
        # tJavaRow bodies).
        input_schema_dict: dict[str, str] = {}
        # Prefer schema_inputs_map (per-flow) when present -- a tJavaRow has
        # exactly one input flow, so we merge any/all entries.
        schema_inputs_map = getattr(self, "schema_inputs_map", None) or {}
        for _flow_name, flow_cols in schema_inputs_map.items():
            if isinstance(flow_cols, list):
                for col in flow_cols:
                    if isinstance(col, dict) and "name" in col:
                        input_schema_dict[col["name"]] = col.get("type", "str")
        # Fall back to flat input_schema list if schema_inputs_map was empty.
        if not input_schema_dict:
            for col in getattr(self, "input_schema", []) or []:
                if isinstance(col, dict) and "name" in col:
                    input_schema_dict[col["name"]] = col.get("type", "str")

        # D-07/D-08: prepend imports with newline separator (one-time, before
        # the bridge compiles the script for the row loop).
        if imports:
            java_code = imports + "\n" + java_code

        # AP-9 fix: read bridge from self.java_bridge (set by engine), not via
        # the legacy ContextManager-based bridge accessor used in pre-Phase-7.1
        # code components.
        if not self.java_bridge:
            raise ComponentExecutionError(
                self.id,
                "Java execution requested but no Java bridge available",
            )

        # Sync engine's GlobalMap into bridge's global_map dict so the Java
        # globalMap binding receives values set by upstream Python components
        # (e.g. tSetGlobalVar, tFileRowCount). The bridge's self.global_map is
        # a plain dict tracking Java-side state; it is never automatically
        # populated from the engine's GlobalMap object. Same pattern as
        # java_component.py:169.
        if self.global_map:
            self.java_bridge.global_map.update(self.global_map._map)

        # Push engine ContextManager state into the bridge so user code reads
        # current context.* values. java_code lives in SKIP_RESOLUTION_KEYS so
        # BaseComponent's _resolve_java_expressions() does not push context
        # for us when the only Java payload is the row body.
        if self.context_manager:
            for key, value in self.context_manager.get_all().items():
                self.java_bridge.context[key] = value

        # Logging policy (RESEARCH.md): DEBUG only, never INFO with body.
        logger.debug(
            f"[{self.id}] Executing per-row Java code on {len(input_data)} rows "
            f"(code size={len(java_code)} chars)"
        )

        try:
            # D-08 + Phase 5.1 compiled-script reuse: the Java side compiles
            # ``java_code`` ONCE and reuses it across rows. D-20: bridge wraps
            # the call in _call_java_with_sync, which owns bidirectional
            # context/globalMap sync (AP-8; do not duplicate sync here).

            # chunk_size: forwarded to the bridge so wide DataFrames (e.g.
            # 330K+ rows) do not overflow Py4J's signed-int Base64 length
            # field (~2.14 GB) -- see execute_java_row docstring. Default
            # 50_000 mirrors execute_compiled_map_chunked. The bridge
            # auto-halves any chunk that still overflows at runtime, so
            # tuning this is rarely needed.
            chunk_size = int(self.config.get("chunk_size") or 50_000)
            main_df = self.java_bridge.execute_java_row(
                df=input_data,
                java_code=java_code,
                output_schema=output_schema,
                input_schema=input_schema_dict or None,
                chunk_size=chunk_size,
            )
        except Exception as e:
            # Talend parity (revision 2): tJavaRow has no REJECT and no
            # try/catch around the row body. We re-raise so the engine's
            # error handling (and the parent flow's die_on_error) decides
            # termination. Matches legacy java_row_component.py:96-98.
            logger.error(
                f"[{self.id}] Java per-row execution failed: "
                f"{e.__class__.__name__}: {e}"
            )
            raise ComponentExecutionError(
                self.id,
                f"Java per-row execution failed: {e}",
                cause=e,
            ) from e

        # Bridge's _sync_from_java() (run inside _call_java_with_sync) refreshed
        # self.java_bridge.context / global_map from the JVM. Propagate those
        # changes back to the engine's ContextManager / GlobalMap so downstream
        # components see context.* / globalMap mutations performed by the
        # per-row Java body.
        if self.context_manager:
            for key, value in self.java_bridge.context.items():
                value_type = self.context_manager.get_type(key)
                self.context_manager.set(key, value, value_type)
        if self.global_map:
            for key, value in self.java_bridge.global_map.items():
                self.global_map.put(key, value)

        # Passthrough-style return: NB_LINE / NB_LINE_OK are computed by
        # BaseComponent step 8 from result['main'] -- no manual _update_stats()
        # call here (AP-3 / S8). reject is always None per Talend parity.
        return {"main": main_df, "reject": None}
