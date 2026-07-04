"""Engine component for python_component (tPython, tPythonComponent) -- one-shot
Python code execution.

Executes user-supplied Python code ONCE per job invocation. Namespace is
constructed per Phase 8 D-11 (curated whitelist of safe builtins +
stdlib modules + pandas/numpy + Decimal + context dict + globalMap +
loaded routines).

D-11/D-12 BREAKING CHANGE: ``os``, ``sys``, ``subprocess``, ``__import__``,
``open``, ``exec``, ``eval``, ``compile`` are NOT exposed in the user
namespace. User code that references them raises ``NameError`` at exec
time. Per project memory ``feedback_fix_source_no_fallbacks`` there is no
compatibility shim. Migrate to ``pandas`` (file I/O), ``datetime`` (time),
and ``globalMap`` (cross-component state).

Note (Phase 8 D-26 supersession):
    ``python_code`` is NEVER ``${context.X}``-resolved
    (``ContextManager.SKIP_RESOLUTION_KEYS`` at
    ``src/v1/engine/context_manager.py:37-41``). User code reads context
    via the ``context['VAR_NAME']`` dict in the exec namespace.

Note (sandbox honesty, RESEARCH.md Pitfall #3):
    The namespace whitelist is HYGIENIC -- it guards against accidental
    misuse by job authors who reach for ``os.system`` out of habit. It is
    NOT a security sandbox; pure-Python namespace restrictions are
    bypassable via ``__subclasses__`` / ``__mro__`` introspection. Trust
    boundary: ``python_code`` is owned by internal Citi job authors. Real
    isolation (subprocess+seccomp/container) is deferred per CONTEXT.md.

Note (passthrough behavior, D-29 / revision 2):
    When ``input_data`` is provided, this component returns it unchanged
    as ``result["main"]``; when ``input_data`` is ``None``, it returns
    ``None`` for ``main``. NO toggle, NO opt-out. This is DataPrep's
    data-flow equivalent of Talend's tJava begin-block (verified via
    Talaxie ``tJava_begin.javajet`` which is just ``<%=CODE%>`` with no
    row iteration).

Config keys consumed:
  python_code        (str, required)        -- Python source executed once.
  tstatcatcher_stats (bool, default False)  -- BaseComponent stats hook.
  label              (str, optional)        -- BaseComponent display label.

Anti-patterns avoided (Phase 8 PATTERNS.md table -- consult that file for
the bare-string patterns the negative-grep gates look for):
- AP-1: built-in generic exceptions are forbidden -- only custom engine
        exceptions (ConfigurationError / ComponentExecutionError) appear
        below.
- AP-2: no top-level imports of os / sys; no direct injection of those
        modules into the user namespace under their bare names. D-11
        namespace is built from the whitelist constants imported from
        ``_code_component_mixin``.
- AP-3: BaseComponent step 8 (``_update_stats_from_result``) auto-counts
        from the result dict; no manual stats update is performed here.
- AP-4: ``_get_context_dict`` is INHERITED from ``CodeComponentMixin``
        (D-09); it is NOT redefined in this module.
- AP-12: the registry decorator wires both the V1 name and the Talend
         aliases (``tPython``, ``tPythonComponent``) into the central
         REGISTRY (Rule 9).

Phase 8 revision-1 Warning 7:
    The whitelist constants and helper (``_SAFE_NAMESPACE_GLOBALS``,
    ``_build_safe_builtins``) are imported from ``_code_component_mixin``
    -- they are NOT redefined here. This avoids the near-duplicate
    footgun the prior revision flagged.
"""
import logging
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError
from ._code_component_mixin import (
    CodeComponentMixin,
    _SAFE_NAMESPACE_GLOBALS,
    _build_safe_builtins,
)

logger = logging.getLogger(__name__)


@REGISTRY.register("PythonComponent", "tPython", "tPythonComponent")
class PythonComponent(CodeComponentMixin, BaseComponent):
    """tPython engine implementation -- one-shot Python code execution.

    See module docstring for the D-11 / D-12 namespace contract and the
    breaking-change notes vs the legacy partial implementation. Mixin
    precedes BaseComponent in the MRO per Phase 8 D-09 so MRO chains
    naturally to ``BaseComponent.__init__`` (the mixin defines no
    ``__init__``).

    Config keys:
        python_code (str, required): Python source executed once.

    Data flow:
        ``input_data`` is returned unchanged as ``main`` when supplied,
        or ``None`` when no upstream is connected (D-29 / revision 2).
        ``reject`` is always ``None`` (one-shot variants have no reject
        flow).
    """

    # ----------------------------------------------------------------
    # Configuration Validation (Rule 12 -- presence + container shape only)
    # ----------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration (Rule 12 -- presence only).

        Raises:
            ConfigurationError: If ``python_code`` is missing/empty.

        Note:
            Type-of (must-be-string), emptiness-after-resolution, syntax
            validity, and namespace-whitelist enforcement are all
            INTENTIONALLY deferred to ``_process`` per D-13 / D-27. A
            ``${context.X}`` literal in ``python_code`` is benign here
            because ``ContextManager.SKIP_RESOLUTION_KEYS`` excludes the
            field from substitution -- the literal will reach exec
            verbatim and raise ``NameError`` at exec time, which is the
            desired semantic.
        """
        if not self.config.get("python_code"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'python_code'"
            )

    # ----------------------------------------------------------------
    # Namespace Construction (D-11 -- whitelist applied at exec time)
    # ----------------------------------------------------------------

    def _build_exec_namespace(
        self,
        input_row: Optional[dict] = None,
        output_row: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Build a namespace dict for ``exec()`` per Phase 8 D-11.

        ``__builtins__`` is a TIGHT dict containing ONLY the names listed
        in :data:`_code_component_mixin._SAFE_BUILTIN_NAMES`. ``os``,
        ``sys``, ``subprocess``, ``__import__``, ``open``, ``exec``,
        ``eval`` and ``compile`` are intentionally absent; user code
        referencing them raises ``NameError`` at exec time.

        Args:
            input_row: Per-row input dict (Phase 8 PythonRowComponent
                will pass this; PythonComponent never does -- one-shot
                variants do not iterate rows). Defaults to ``None`` so
                the no-row variant simply omits the binding.
            output_row: Per-row output dict (Phase 8 PythonRowComponent
                will pass this; PythonComponent never does). Defaults to
                ``None``.

        Returns:
            Dict ready to pass as the ``globals`` argument of ``exec()``.
        """
        ns: dict[str, Any] = {
            "__builtins__": _build_safe_builtins(),
            **_SAFE_NAMESPACE_GLOBALS,
            "context": self._get_context_dict(),
            "globalMap": self.global_map,
        }
        routines = self.get_python_routines()
        if routines:
            # Per RESEARCH.md Open Question 3: keep the flat spread for
            # backward compatibility with converted Talend jobs that
            # reference routines by bare name. The nested ``routines``
            # dict is also exposed so future code can prefer the namespaced
            # access; if the routines mechanism is later locked to
            # nested-only, drop the spread.
            ns["routines"] = routines
            ns.update(routines)
        if input_row is not None:
            ns["input_row"] = input_row
        if output_row is not None:
            ns["output_row"] = output_row
        return ns

    # ----------------------------------------------------------------
    # Core Processing
    # ----------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Execute the one-shot Python block, then return passthrough.

        Steps:
            1. Pull ``python_code`` from ``self.config`` (already free of
               ``${context.X}`` substitution per ``SKIP_RESOLUTION_KEYS``).
            2. Run the deferred content checks (D-13 / D-27) BEFORE any
               broad try/except -- otherwise ``ConfigurationError`` would
               be re-wrapped as ``ComponentExecutionError`` per the
               Phase 7.2 send_mail lesson.
            3. Build the D-11 whitelist exec namespace.
            4. Run ``exec(python_code, namespace)``. Any exception from
               user code is wrapped as ``ComponentExecutionError`` so
               the engine's failure path captures ``component_id`` and
               the original cause.
            5. Return ``{"main": input_data, "reject": None}`` -- the
               D-29 passthrough shape. BaseComponent step 8 owns stats.

        Args:
            input_data: Upstream DataFrame, or ``None`` for begin-block-style
                placement.

        Returns:
            Dict with ``main`` (input_data passthrough or ``None``) and
            ``reject`` (always ``None``; tPython has no reject flow).

        Raises:
            ConfigurationError: If ``python_code`` is not a string or is
                empty after stripping (D-27 -- raised before try/except).
            ComponentExecutionError: If user code raises during ``exec``.
                The original exception class and message are preserved in
                the wrapper message and via the ``cause`` attribute.
        """
        # D-13 / D-27: deferred content checks BEFORE any broad try/except.
        python_code = self.config.get("python_code", "")
        if not isinstance(python_code, str):
            raise ConfigurationError(
                f"[{self.id}] 'python_code' must be a string"
            )
        if not python_code.strip():
            raise ConfigurationError(
                f"[{self.id}] 'python_code' must be non-empty after resolution"
            )

        namespace = self._build_exec_namespace()

        # Logging policy (RESEARCH.md): DEBUG only, never INFO with body.
        logger.debug(
            f"[{self.id}] Executing one-shot Python block (size={len(python_code)} chars)"
        )

        try:
            # noqa: S102 -- D-11 namespace controls (no __import__, no os/sys, etc.)
            exec(python_code, namespace)
        except Exception as e:
            raise ComponentExecutionError(
                self.id,
                f"Python code execution failed: {e.__class__.__name__}: {e}",
                cause=e,
            ) from e

        # Passthrough per D-29 (revision 2). Stats lifecycle (NB_LINE etc.)
        # is computed by BaseComponent step 8 from result['main'] -- no
        # manual _update_stats() call here (AP-3 / S8).
        return {"main": input_data, "reject": None}
