"""The v2 engine: load a job config and run it."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Union

from ..components.registry import REGISTRY, Registry
from ..job.loader import load_job
from ..job.model import Job
from .runner import JobResult, Runner

__all__ = ["JobResult", "Runner", "run_job"]


def run_job(
    source: Union[Job, Mapping[str, Any], str, Path],
    context: Optional[Mapping[str, Any]] = None,
    *,
    registry: Registry = REGISTRY,
    engine: Optional[str] = None,
    routines: Optional[Mapping[str, Mapping[str, Callable[..., Any]]]] = None,
) -> JobResult:
    """Load a job config and run it.

    Args:
        source: A job config (dict or path of a JSON file), or a loaded job.
        context: Context values that override the job config's own.
        registry: Where component types are looked up.
        engine: The Polars engine to collect with: ``streaming`` (default),
            ``in-memory`` or ``auto``. The ``V2_ENGINE`` environment variable
            sets it too.
        routines: Routine modules available to expressions.

    Returns:
        How the run ended. A job that starts and fails is reported in the
        result, not raised; call ``raise_for_status()`` to raise.

    Raises:
        JobRefusedError: When the job config holds anything v2 will not run
            with. Nothing has run.
    """
    job = source if isinstance(source, Job) else load_job(source, context=context, registry=registry)
    return Runner(job, engine=engine, routines=routines).run()
