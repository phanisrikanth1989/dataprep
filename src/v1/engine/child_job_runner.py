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
