"""Engine component for tJava (one-shot Java/Groovy code block).

Executes user-supplied Java code ONCE per job invocation (not per row).
Bidirectional ``context`` and ``globalMap`` sync is handled by the existing
JavaBridge wrapper (``_call_java_with_sync`` -- D-19, D-20). This component
is the consumer; it MUST NOT duplicate sync logic.

Config keys consumed:
  java_code (str, required) -- Java/Groovy source executed once at component activation.
  imports   (str, default "") -- Java import block prepended to ``java_code`` with
                                  a newline separator before bridge call (D-07).
  tstatcatcher_stats (bool, default False) -- BaseComponent stats hook (passthrough).
  label              (str, optional) -- BaseComponent display label (passthrough).

Note (Phase 8 D-26 supersession):
    ``java_code``/``imports`` are NEVER ``${context.X}``-resolved
    (``ContextManager.SKIP_RESOLUTION_KEYS`` at
    ``src/v1/engine/context_manager.py:37-41``). User code reads context
    programmatically via ``globalMap`` and (in Python variants) the
    ``context`` dict -- NOT via string substitution into the source.

Note (passthrough behavior, D-29 / revision 2):
    When ``input_data`` is provided, this component returns it unchanged
    as ``result["main"]``; when ``input_data`` is ``None``, it returns
    ``None`` for ``main``. NO toggle, NO opt-out. This is DataPrep's
    data-flow equivalent of Talend's tJava begin-block (verified via
    Talaxie ``tJava_begin.javajet`` which is just ``<%=CODE%>`` with no
    row iteration). DataPrep's flow-graph model places the component in
    a chain where input/output FLOW connectors exist, so the natural
    semantic is: "user code runs once; any input rows pass through
    because the component is not a row transformer." Documented as a
    DataPrep data-flow semantic, not a Talend feature.

Anti-patterns avoided (Phase 8 PATTERNS.md table -- consult that file for
the bare-string patterns the negative-grep gates look for):
- AP-1: built-in generic exceptions are forbidden -- only custom engine
        exceptions (ConfigurationError / ComponentExecutionError /
        ExpressionError) appear below.
- AP-3: BaseComponent step 8 (``_update_stats_from_result``) auto-counts
        from the result dict; no manual stats update is performed here.
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
from ...exceptions import ComponentExecutionError, ConfigurationError, ExpressionError
from ._code_component_mixin import CodeComponentMixin
from .map.map_compiled_script import groovy_escape_expression

logger = logging.getLogger(__name__)


@REGISTRY.register("JavaComponent", "tJava")
class JavaComponent(CodeComponentMixin, BaseComponent):
    """tJava engine implementation -- one-shot Java/Groovy code execution.

    Executes user-supplied Java code ONCE per job invocation. Code has access
    to ``context`` and ``globalMap`` proxies via the JavaBridge subprocess.
    Bidirectional sync is handled by ``JavaBridge._call_java_with_sync``
    (D-19, D-20). Per Phase 8 D-09, mixin precedes BaseComponent in the MRO.

    Config keys:
        java_code (str, required): Java/Groovy source executed once.
        imports   (str, default ""): Java import block prepended with a newline
            separator before being sent to the bridge (D-07). Bridge surfaces
            compile errors with full diagnostics; no client-side syntax check.

    Data flow:
        ``input_data`` is returned unchanged as ``main`` when supplied, or
        ``None`` when no upstream is connected (D-29 / revision 2).
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration (Rule 12 -- presence + container shape only).

        Raises:
            ConfigurationError: If ``java_code`` is missing/empty, or if
                ``imports`` is provided but is not a string.

        Note:
            Java syntax validity and ``imports`` content shape are intentionally
            deferred to ``_process``; the Java bridge surfaces compile errors
            with full diagnostics. ``${context.X}`` literals in ``imports``
            arrive verbatim because ``ContextManager.SKIP_RESOLUTION_KEYS``
            excludes the ``imports`` field from resolution.
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

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Execute the one-shot Java code block, then return passthrough.

        Steps:
            1. Pull ``java_code`` and ``imports`` from ``self.config``
               (already free of ``${context.X}`` substitution per
               ``SKIP_RESOLUTION_KEYS``).
            2. Prepend ``imports`` to ``java_code`` with a newline separator
               when ``imports`` is non-empty (D-07).
            3. Verify ``self.java_bridge`` was wired by the engine
               (raises ``ComponentExecutionError`` otherwise -- AP-9 fix).
            4. Hand the resulting source to
               ``java_bridge.execute_one_time_expression`` which internally
               wraps the call in ``_call_java_with_sync`` (D-20). The bridge
               owns bidirectional sync; this component must not invoke the
               sync machinery directly (AP-8). BaseComponent step 8 owns
               the stats update; this component must not invoke the stats
               helper directly (AP-3).
            5. Return ``{"main": input_data, "reject": None}`` -- passthrough
               per D-29 (revision 2).

        Args:
            input_data: Upstream DataFrame, or ``None`` for begin-block-style
                placement.

        Returns:
            Dict with ``main`` (input_data passthrough or ``None``) and
            ``reject`` (always ``None``; tJava has no reject flow).

        Raises:
            ComponentExecutionError: If the engine never wired a Java bridge.
            ExpressionError: If the bridge raises while compiling/executing
                the user's Java code (compile errors surface here).
        """
        java_code: str = self.config.get("java_code", "")
        imports: str = self.config.get("imports", "") or ""

        # D-07: prepend imports with newline separator.
        if imports:
            java_code = imports + "\n" + java_code
        #Groovy escaping (D-24) -- the bridge's compile-time checks are not
        # sufficient to prevent syntax errors from unescaped user code. The
        # escape function is designed to be idempotent, so it won't double-escape if the
        # user pre-escapes their code (e.g. to work around a known issue in their code editor).
        # The escape function handles backslashes, quotes, and newlines, which are common sources of syntax errors in Groovy code blocks. This is a proactive measure to improve the user experience by reducing the likelihood of syntax errors due to unescaped characters.
        # Note that this escaping is applied to the entire code block, including imports. If users need to include raw Groovy code in their imports, they should pre-escape it before placing it in the config.
        # The escape function is designed to be safe for Java code as well, since Java syntax is a subset of Groovy syntax. However, users should be aware that certain characters in their Java code may be escaped, which could affect how the code is interpreted by the Java compiler. If users want to include raw Java code without escaping, they should pre-escape it before placing it in the config.
        # The decision to apply Groovy escaping at the component level (instead of relying on the bridge's compile-time checks) is based on the desire to provide immediate feedback to users about potential syntax issues in their code, rather than allowing them to submit code that will fail at runtime. This proactive approach helps users identify and fix syntax issues early in the development process, improving the overall user experience.
        # The escape function is designed to be idempotent, so it won't double-escape if the user pre-escapes their code (e.g. to work around a known issue in their code editor). This allows users to have control over the escaping process if they need to include raw Groovy or Java code in their config.
        
        java_code = groovy_escape_expression(java_code)
        # AP-9 fix: read bridge from self.java_bridge (set by engine), not from
        # self.context_manager.get_java_bridge() (legacy path).
        if self.java_bridge is None:
            raise ComponentExecutionError(
                self.id,
                "Java execution requested but no Java bridge available",
            )

        # Sync engine's GlobalMap into bridge's global_map dict so the Java
        # globalMap binding receives values set by upstream Python components
        # (e.g. tFileRowCount_1_COUNT from FileRowCount). The bridge's
        # self.global_map is a plain dict tracking Java-side state; it is
        # never automatically populated from the engine's GlobalMap object.
        if self.global_map:
            self.java_bridge.global_map.update(self.global_map._map)

        # Push engine ContextManager state into the bridge so user code reads
        # the current context.* values. SKIP_RESOLUTION_KEYS prevents config
        # substitution from doing this for us, and BaseComponent's
        # _resolve_java_expressions() only fires when {{java}} markers exist
        # in config -- tJava has none.
        if self.context_manager:
            for key, value in self.context_manager.get_all().items():
                self.java_bridge.context[key] = value

        # Logging policy (RESEARCH.md): DEBUG only, never INFO with body.
        logger.debug(
            f"[{self.id}] Executing one-shot Java block (size={len(java_code)} chars)"
        )

        try:
            # D-20: bridge wraps this call in _call_java_with_sync, which owns
            # bidirectional context/globalMap sync. Do not invoke the sync
            # machinery directly here (AP-8).
            self.java_bridge.execute_one_time_expression(java_code)
        except Exception as e:
            raise ExpressionError(
                f"[{self.id}] Java execution failed: {e}"
            ) from e

        # Bridge's _sync_from_java() has refreshed self.java_bridge.context and
        # self.java_bridge.global_map from the JVM. Propagate those changes
        # back to the engine's ContextManager / GlobalMap so downstream
        # components (tMap filters, etc.) observe context.* assignments made
        # by the user's Java code.
        if self.context_manager:
            for key, value in self.java_bridge.context.items():
                value_type = self.context_manager.get_type(key)
                self.context_manager.set(key, value, value_type)
        if self.global_map:
            for key, value in self.java_bridge.global_map.items():
                self.global_map.put(key, value)

        # Passthrough per D-29 (revision 2). Stats lifecycle (NB_LINE etc.)
        # is computed by BaseComponent step 8 from result['main'] -- no manual
        # _update_stats() call here (AP-3 / S8).
        return {"main": input_data, "reject": None}
