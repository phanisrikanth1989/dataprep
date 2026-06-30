"""ChildJobRunner -- runs a child job (tRunJob) in-process as a nested ETLEngine.

See docs/superpowers/specs/2026-06-30-trunjob-component-design.md.
"""
from __future__ import annotations

import logging
import os
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class RunContext:
    """Recursion/resolution state threaded through nested tRunJob calls."""
    base_dir: Optional[str]
    jobs_dir: Optional[str]
    call_stack: List[str]
    depth: int
    max_depth: int = 2


@dataclass
class ChildResult:
    """Outcome of one child-job run."""
    status: str
    return_code: int
    stacktrace: Optional[str] = None


class ChildJobRunner:
    """Resolves and runs a child job (tRunJob) in-process as a nested ETLEngine."""

    def __init__(self, run_context: RunContext) -> None:
        self.run_context = run_context

    def _resolve_path(self, process: str) -> str:
        """Return the absolute path to the child job JSON config.

        Args:
            process: The job process name (filename without extension).

        Returns:
            Absolute path string of the form ``<base>/<process>.json``.

        Raises:
            ConfigurationError: If neither ``base_dir`` nor ``jobs_dir`` is set.
        """
        base = self.run_context.base_dir or self.run_context.jobs_dir
        if not base:
            raise ConfigurationError(
                f"cannot resolve child job '{process}': engine started from an "
                f"in-memory config with no engine_config.jobs_dir"
            )
        return os.path.join(os.path.abspath(base), f"{process}.json")

    def _check_cycle_and_depth(self, child_path: str) -> None:
        """Raise ConfigurationError if the child path creates a cycle or exceeds max depth.

        Args:
            child_path: Absolute path of the child job config being invoked.

        Raises:
            ConfigurationError: On cycle detection or depth overflow.
        """
        if child_path in self.run_context.call_stack:
            chain = " -> ".join(self.run_context.call_stack + [child_path])
            raise ConfigurationError(f"tRunJob cycle detected: {chain}")
        if self.run_context.depth + 1 > self.run_context.max_depth:
            raise ConfigurationError(
                f"tRunJob nesting depth {self.run_context.depth + 1} exceeds "
                f"max_run_job_depth={self.run_context.max_depth}"
            )

    def _child_run_context(self, child_path: str) -> RunContext:
        """Build a RunContext for the child job, incrementing depth and extending the call stack.

        Args:
            child_path: Absolute path to the child job config.

        Returns:
            A new RunContext with depth+1 and child_path appended to the call stack.
        """
        return RunContext(
            base_dir=os.path.dirname(child_path),
            jobs_dir=self.run_context.jobs_dir,
            call_stack=self.run_context.call_stack + [child_path],
            depth=self.run_context.depth + 1,
            max_depth=self.run_context.max_depth,
        )

    def _seed_context(self, child: Any, whole_context: Dict[str, Any],
                      param_overrides: Dict[str, Any], context_name: str = "Default") -> None:
        """Apply parent context overrides onto the child engine's ContextManager.

        Iterates over ALL context groups the child defines (not only the group
        named by ``context_name``) to build the set of declared variable names.
        This is the B1 fix: a child whose only group is e.g. "PROD" (no "Default")
        must still receive its seeded overrides even when ``context_name="Default"``.

        Type tokens are resolved per-variable: the selected/default group wins when
        a name appears in multiple groups.  ``param_overrides`` are applied last so
        they win over ``whole_context`` values.

        Variables that are not declared in any child group trigger a WARNING and are
        silently dropped (never applied) -- never silently skipped without a log line.

        Args:
            child: Object exposing ``.job_config`` (dict) and ``.context_manager``
                (a ``ContextManager`` instance).
            whole_context: Flat dict of parent context values to propagate.
            param_overrides: Flat dict of explicit ``context_params`` from the
                tRunJob component config (highest priority).
            context_name: The context group name from the tRunJob config (used only
                to determine which group's type token wins on a name collision).
        """
        ctx_block = child.job_config.get("context", {}) or {}

        # Determine the "selected" group whose type token takes precedence on collision.
        selected: Dict[str, Any] = (
            ctx_block.get(context_name)
            or ctx_block.get(child.job_config.get("default_context", "Default"), {})
            or {}
        )

        # Build union of all declared names with their type tokens (all groups first,
        # then selected group overwrites to let selected type win on collision).
        declared_types: Dict[str, Any] = {}
        for group in ctx_block.values():
            if isinstance(group, dict):
                for name, meta in group.items():
                    declared_types.setdefault(name, (meta or {}).get("type"))
        for name, meta in selected.items():
            declared_types[name] = (meta or {}).get("type")

        # Overlay the selected group's default VALUES onto the child before explicit overrides.
        # Precedence: child-default < context_name-selected-group < whole_context < param_overrides.
        # This is a no-op when context_name resolves to the child's own default_context.
        for name, meta in selected.items():
            child.context_manager.set(name, (meta or {}).get("value"), declared_types.get(name))

        # Apply whole_context first, then param_overrides (so overrides win).
        for source in (whole_context, param_overrides):
            for name, value in source.items():
                if name in declared_types:
                    child.context_manager.set(name, value, declared_types[name])
                else:
                    logger.warning(
                        "[ChildJobRunner] context override '%s' not defined in child job; skipped",
                        name,
                    )

    def run(self, process: str, whole_context: Dict[str, Any],
            param_overrides: Dict[str, Any], context_name: str = "Default") -> ChildResult:
        """Run a child job in-process as a nested ETLEngine.

        Cycle/depth errors always propagate (fatal). All other failures
        (bad path, construction error, runtime error) are caught and returned
        as a ChildResult with return_code=-1 so the parent component's
        die_on_error model governs uniformly.

        Args:
            process: Child job process name (filename without .json extension).
            whole_context: Flat dict of parent context values to propagate.
            param_overrides: Flat dict of explicit context_params from the
                tRunJob component config (highest priority).
            context_name: The context group name from the tRunJob config.

        Returns:
            ChildResult with status, return_code, and optional stacktrace.

        Raises:
            ConfigurationError: On cycle detection or depth overflow (always fatal).
        """
        from .engine import ETLEngine  # local import breaks the engine <-> runner cycle
        child_path = self._resolve_path(process)
        self._check_cycle_and_depth(child_path)            # cycle/depth: always-fatal, propagate
        child_ctx = self._child_run_context(child_path)
        try:
            if not os.path.isfile(child_path):
                raise ConfigurationError(f"child job file not found: {child_path}")
            with ETLEngine(child_path, _run_context=child_ctx) as child:
                self._seed_context(child, whole_context, param_overrides, context_name)
                stats = child.execute()
            return self._map_result(stats)
        except Exception as exc:                           # construction / seeding / run failures
            logger.error("[ChildJobRunner] child job '%s' failed: %s", process, exc)
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            return ChildResult(status="error", return_code=-1, stacktrace=tb)

    @staticmethod
    def _map_result(stats: Dict[str, Any]) -> ChildResult:
        """Map an ETLEngine stats dict to a ChildResult.

        Args:
            stats: The dict returned by ``ETLEngine.execute()``.

        Returns:
            ChildResult reflecting success, abort, tolerated-failure, or error.
        """
        if "error" in stats:                               # engine raised inside execute()
            return ChildResult("error", -1, str(stats.get("error")))
        if stats.get("status") == "success":
            return ChildResult("success", 0, None)
        if stats.get("job_aborted"):                       # tDie/exit OR die_on_error=true failure
            return ChildResult("error", -1, None)
        return ChildResult("completed_with_tolerated_errors", 0, None)
