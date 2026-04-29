"""Engine component for python_row_component (tPythonRow) -- per-row Python
execution with REJECT flow (DataPrep extension; documented as such).

Compile-once contract (PERF-02 / D-17/D-18): user ``python_code`` is compiled
ONCE at the start of ``_process`` via
``compile(source, '<python_row_component:{id}>', 'exec')``. The compiled code
object is reused across every input row; the exec namespace dict is rebuilt
cheaply per row to swap in fresh ``input_row`` / ``output_row`` bindings. This
amortizes the parser's cost across N rows (typical 5-30x speedup for 10K+
rows). The pattern matches Talend's javac-once approach on the Java side and
mirrors the compiled-tMap-script work landed in Phase 5.1.

REJECT semantics (revision 2 D-14/D-16): per-row exception with
``die_on_error=False`` routes the offending input row to ``result["reject"]``
with a SINGLE appended column:

    ``errorMessage`` (str, the exception message).

Original input columns are preserved BEFORE the appended column.

NO secondary error-classification column. Talend's tFilterRow reject schema is
``errorMessage``-only (verified ``tFilterRow_java.xml`` lines 43-47). The
legacy DataPrep-specific error-code string in the prior partial implementation
had no Talend basis; revision 2 drops the entire field. Per project memory
``feedback_fix_source_no_fallbacks`` there is no compatibility shim.

``die_on_error=True`` raises ``ComponentExecutionError`` on the first per-row
failure (D-15/D-28). The error message includes the offending row index.

Note: this REJECT flow itself is a DataPrep extension -- Talend's tPythonRow
has no native REJECT either (verified Talaxie tdi-studio-se templates). Legacy
DataPrep users may depend on the per-row continue behavior, so we preserve it
(with a Talend-aligned single-column schema).

D-11/D-12 namespace: see ``python_component.py`` module docstring. Same
whitelist of safe builtins, stdlib modules, ``pd``, ``np``, ``Decimal``. ``os``,
``sys``, ``subprocess``, ``__import__``, ``open``, ``exec``, ``eval``,
``compile`` are NOT exposed; user code referencing them raises ``NameError``
at exec time. With ``die_on_error=False`` that ``NameError`` routes to reject;
with ``die_on_error=True`` it propagates wrapped as
``ComponentExecutionError``. The whitelist constants and helper
(``_SAFE_NAMESPACE_GLOBALS``, ``_build_safe_builtins``) are imported from
``_code_component_mixin`` -- they are NOT redefined here (Phase 8 revision-1
Warning 7 fix; ditto for Plan 02 / PythonComponent).

Note (Phase 8 D-26 supersession):
    ``python_code`` is NEVER ``${context.X}``-resolved
    (``ContextManager.SKIP_RESOLUTION_KEYS`` at
    ``src/v1/engine/context_manager.py:37-41``). User code reads context
    via the ``context['VAR_NAME']`` dict in the per-row exec namespace.

Note (sandbox honesty, RESEARCH.md Pitfall #3):
    The namespace whitelist is HYGIENIC -- it guards against accidental
    misuse by job authors who reach for ``os.system`` out of habit. It is
    NOT a security sandbox; pure-Python namespace restrictions are
    bypassable via ``__subclasses__`` / ``__mro__`` introspection. Trust
    boundary: ``python_code`` is owned by internal Citi job authors. Real
    isolation (subprocess+seccomp/container) is deferred per CONTEXT.md.

Config keys consumed:
  python_code        (str, required)        -- Python source executed per row.
  output_schema      (dict|list, optional)  -- output column types (handed to
                                              BaseComponent step 7c; the legacy
                                              per-row coercion helper is gone
                                              per Rule 11 / AP-7).
  tstatcatcher_stats (bool, default False)  -- BaseComponent stats hook.
  label              (str, optional)        -- BaseComponent display label.

Anti-patterns avoided (Phase 8 PATTERNS.md table):
- AP-1: built-in generic exceptions are forbidden -- only custom engine
        exceptions (``ConfigurationError`` / ``ComponentExecutionError``)
        appear below. The legacy bare-builtin error path in the deleted
        file is gone.
- AP-2: no top-level imports of ``os`` / ``sys``; D-11 namespace is built
        from the whitelist constants imported from ``_code_component_mixin``.
- AP-3: BaseComponent step 8 (``_update_stats_from_result``) auto-counts
        from the result dict; no manual stats update is performed here.
- AP-4: ``_get_context_dict`` is INHERITED from ``CodeComponentMixin`` (D-09);
        it is NOT redefined in this module.
- AP-5: NO secondary classification column in the reject DataFrame
        (revision 2 D-16). The legacy DataPrep-specific error-code string
        had no Talend basis; revision 2 drops the entire field. Test 15
        deterministically asserts the schema is single-appended-column.
- AP-6: per-row ``exec(python_code, ...)`` is FORBIDDEN; we compile ONCE
        before the loop and ``exec(compiled_code, ...)`` per row. Test 12
        deterministically asserts ``compile`` is invoked exactly once
        across an N-row run via a ``builtins.compile`` monkeypatch.
- AP-7: NO ``_validate_output_row`` helper. Output schema validation is
        BaseComponent step 7c (Rule 11). The legacy 50-line helper is gone.
- AP-12: the registry decorator wires both the V1 name and the Talend
         alias (``tPythonRow``) into the central REGISTRY (Rule 9).

Phase 8 revision-1 Warning 7:
    The whitelist constants and helper are imported from
    ``_code_component_mixin`` -- they are NOT redefined here.

ASCII-only per project memory ``feedback_ascii_logging``.
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


@REGISTRY.register("PythonRowComponent", "tPythonRow")
class PythonRowComponent(CodeComponentMixin, BaseComponent):
    """tPythonRow engine implementation -- per-row Python with REJECT flow.

    See module docstring for the compile-once (D-17/D-18 / PERF-02), REJECT
    (revision 2 D-14/D-16, errorMessage-only), and D-11 / D-12 namespace
    semantics. Mixin precedes BaseComponent in the MRO per Phase 8 D-09 so
    MRO chains naturally to ``BaseComponent.__init__`` (the mixin defines no
    ``__init__``).

    Config keys:
        python_code (str, required): Python source executed per row.
        output_schema (dict|list, optional): forwarded to BaseComponent
            step 7c for output validation -- this component does NOT do
            its own output coercion (Rule 11 / AP-7).

    Data flow:
        Per-row exec mutates ``output_row`` in place; the post-loop
        ``output_row`` snapshot becomes a row in ``result["main"]``.
        Per-row exception with ``die_on_error=False`` appends the input row
        plus an ``errorMessage`` column to ``result["reject"]``; with
        ``die_on_error=True`` the first failure raises
        ``ComponentExecutionError`` carrying the row index.
    """

    # ----------------------------------------------------------------
    # Configuration Validation (Rule 12 -- presence + container shape only)
    # ----------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration (Rule 12 -- presence + shape).

        Checks:
            - ``python_code`` is present (truthy).
            - If ``output_schema`` is present, it is a ``dict`` or ``list``
              (container-shape only -- contents are validated by
              BaseComponent step 7c).

        Raises:
            ConfigurationError: If ``python_code`` is missing/empty or
                ``output_schema`` is the wrong container shape.

        Note:
            Type-of (must-be-string), emptiness-after-resolution, syntax
            validity, and namespace-whitelist enforcement are all
            INTENTIONALLY deferred to ``_process`` per D-13 / D-27.
            ``${context.X}`` literals in ``python_code`` are benign here
            because ``ContextManager.SKIP_RESOLUTION_KEYS`` excludes the
            field from substitution.
        """
        if not self.config.get("python_code"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'python_code'"
            )
        output_schema = self.config.get("output_schema")
        if output_schema is not None and not isinstance(
            output_schema, (dict, list)
        ):
            raise ConfigurationError(
                f"[{self.id}] 'output_schema' must be a dict or list, "
                f"got {type(output_schema).__name__}"
            )

    # ----------------------------------------------------------------
    # Per-row Namespace Construction (D-11 -- whitelist applied at exec time)
    # ----------------------------------------------------------------

    def _build_row_namespace(
        self,
        input_row: dict,
        output_row: dict,
        context_dict: dict,
        routines: dict,
    ) -> dict[str, Any]:
        """Build a per-row namespace dict for ``exec()`` per Phase 8 D-11.

        ``__builtins__`` is a TIGHT dict containing ONLY the names listed in
        :data:`_code_component_mixin._SAFE_BUILTIN_NAMES`. ``os``, ``sys``,
        ``subprocess``, ``__import__``, ``open``, ``exec``, ``eval`` and
        ``compile`` are intentionally absent.

        The dict is REBUILT per row (cheap construction) so ``input_row`` /
        ``output_row`` reflect the current row -- the COMPILED CODE OBJECT,
        in contrast, is shared across the loop (D-17/D-18).

        Args:
            input_row: Per-row input dict (from ``DataFrame.iterrows()``).
            output_row: Per-row mutable output dict; user code populates it.
            context_dict: Flat ``{var_name: value}`` view of context
                variables (already computed once outside the loop).
            routines: Loaded Python routines mapping (computed once).

        Returns:
            Dict ready to pass as the ``globals`` argument of ``exec()``.
        """
        ns: dict[str, Any] = {
            "__builtins__": _build_safe_builtins(),
            **_SAFE_NAMESPACE_GLOBALS,
            "context": context_dict,
            "globalMap": self.global_map,
            "input_row": input_row,
            "output_row": output_row,
        }
        if routines:
            # Per RESEARCH.md Open Question 3: keep the flat spread for
            # backward compatibility with converted Talend jobs that
            # reference routines by bare name. The nested ``routines`` dict
            # is also exposed so future code can prefer namespaced access.
            ns["routines"] = routines
            ns.update(routines)
        return ns

    # ----------------------------------------------------------------
    # Core Processing -- compile-once + per-row exec + REJECT flow
    # ----------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict[str, Any]:
        """Execute user Python code for every input row.

        Steps:
            1. Short-circuit on ``None`` / empty input (compile NOT invoked).
            2. Run deferred content checks on ``python_code`` (D-13 / D-27)
               BEFORE any broad try/except -- ``ConfigurationError`` must
               reach the engine's failure path unmodified.
            3. Compile ``python_code`` ONCE via ``compile(source, filename,
               'exec')`` (D-17 / PERF-02). Wrap ``SyntaxError`` as
               ``ConfigurationError`` because syntax is a config-time
               failure (D-27).
            4. Hoist context dict + routines mapping out of the loop.
            5. For each input row, build a fresh exec namespace and run
               ``exec(compiled_code, namespace)``. On per-row exception:
                 - ``die_on_error=True``: raise ``ComponentExecutionError``
                   with the row index in the message (D-15 / D-28).
                 - ``die_on_error=False``: append ``dict(input_row)`` plus
                   one ``errorMessage`` column to the reject list and
                   continue (revision 2 D-14 / D-16).
            6. Return ``{"main": main_df, "reject": reject_df_or_None}``.

        Args:
            input_data: Upstream DataFrame, or ``None`` / empty for an
                early no-op.

        Returns:
            Dict with ``main`` (DataFrame of accumulated output rows; empty
            DataFrame if all rows rejected) and ``reject`` (DataFrame of
            input columns + ``errorMessage`` for failed rows; ``None`` when
            no rows failed).

        Raises:
            ConfigurationError: If ``python_code`` is not a string, empty
                after resolution, or contains a SyntaxError (raised before
                any try/except wrapping).
            ComponentExecutionError: If a per-row exec fails AND
                ``die_on_error=True``. Message includes the offending row
                index; ``cause`` is the original exception.
        """
        if input_data is None or input_data.empty:
            # Compile is intentionally NOT invoked -- empty input is a no-op
            # and the deferred content checks below are skipped because
            # there is no work to do (Tests 6 / 7).
            return {"main": input_data, "reject": None}

        # Step 2: D-13 / D-27 deferred content checks BEFORE any try/except.
        python_code = self.config.get("python_code", "")
        if not isinstance(python_code, str):
            raise ConfigurationError(
                f"[{self.id}] 'python_code' must be a string"
            )
        if not python_code.strip():
            raise ConfigurationError(
                f"[{self.id}] 'python_code' must be non-empty after resolution"
            )

        # Step 3: D-17 -- compile ONCE. The filename includes the component
        # id so traces from the row-loop point at the right component.
        filename = f"<python_row_component:{self.id}>"
        try:
            compiled_code = compile(python_code, filename, "exec")
        except SyntaxError as e:
            raise ConfigurationError(
                f"[{self.id}] Syntax error in python_code: {e}"
            ) from e

        # Step 4: hoist invariants out of the loop. The namespace itself is
        # rebuilt per row (D-18) but these two lookups are stable for the
        # whole call.
        context_dict = self._get_context_dict()
        routines = self.get_python_routines()

        output_rows: list[dict[str, Any]] = []
        reject_rows: list[dict[str, Any]] = []

        # Logging policy (RESEARCH.md): DEBUG only, never INFO with body.
        logger.debug(
            f"[{self.id}] Per-row Python execution on {len(input_data)} rows "
            f"(compile-once filename={filename})"
        )

        # Step 5: per-row exec loop. The compiled code object is shared;
        # the namespace is rebuilt cheaply each iteration.
        for idx, row in input_data.iterrows():
            input_row = row.to_dict()
            output_row: dict[str, Any] = {}
            namespace = self._build_row_namespace(
                input_row=input_row,
                output_row=output_row,
                context_dict=context_dict,
                routines=routines,
            )
            try:
                # noqa: S102 -- D-11 namespace controls (no __import__, etc.)
                exec(compiled_code, namespace)
            except Exception as e:
                if self.die_on_error:
                    raise ComponentExecutionError(
                        self.id,
                        f"Python error at row index {idx}: "
                        f"{e.__class__.__name__}: {e}",
                        cause=e,
                    ) from e
                # die_on_error=False: append reject row (revision 2 D-14/D-16).
                reject_row = dict(input_row)
                # SINGLE appended column -- Talend's tFilterRow reject schema
                # is errorMessage-only (verified tFilterRow_java.xml
                # lines 43-47); no secondary classification field.
                reject_row["errorMessage"] = (
                    f"{e.__class__.__name__}: {e}"
                )
                reject_rows.append(reject_row)
                continue
            # User code may have rebound ``output_row`` in the namespace.
            # Pull from the namespace to preserve the assignment if so.
            output_rows.append(namespace.get("output_row", output_row))

        # Step 6: build the result dict. Empty main is valid (e.g. all rows
        # rejected); ``reject`` is None when nothing failed (so downstream
        # reject consumers see an explicit no-rows signal).
        main_df = pd.DataFrame(output_rows) if output_rows else pd.DataFrame()
        reject_df = pd.DataFrame(reject_rows) if reject_rows else None
        return {"main": main_df, "reject": reject_df}
