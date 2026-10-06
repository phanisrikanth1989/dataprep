"""The v2 engine: load a job config, check it, and run it."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Union

from ..components.registry import REGISTRY, Registry
from ..errors import ConfigurationError, JobRefusedError
from ..job.loader import load_job as read_job
from ..job.model import Job
from ..job.refusal import RefusalReport
from .check import check_job
from .routines import load_routines
from .runner import JobResult, Runner

__all__ = ["JobResult", "Runner", "check_job", "load_job", "run_job"]

Routines = Mapping[str, Mapping[str, Callable[..., Any]]]


def load_job(
    source: Union[Mapping[str, Any], str, Path],
    context: Optional[Mapping[str, Any]] = None,
    *,
    registry: Registry = REGISTRY,
    routines: Optional[Routines] = None,
) -> Job:
    """Load a job config and check that v2 can run it.

    Args:
        source: The job config, as a dict or as the path of a JSON file.
        context: Context values that override the job config's own.
        registry: Where component types are looked up.
        routines: Routine modules available to expressions.

    Returns:
        The loaded job.

    Raises:
        JobRefusedError: When the job config holds anything v2 will not run
            with. Its report lists every problem found. Nothing has run.
    """
    job = read_job(source, context=context, registry=registry)
    report = RefusalReport(job_name=job.name)
    try:
        job.routine_modules = dict(routines) if routines is not None else load_routines(job.routines)
    except ConfigurationError as exc:
        report.add("job", "python_config", str(exc))
    else:
        report = check_job(job)
    if report:
        raise JobRefusedError(report)
    return job


def run_job(
    source: Union[Job, Mapping[str, Any], str, Path],
    context: Optional[Mapping[str, Any]] = None,
    *,
    registry: Registry = REGISTRY,
    engine: Optional[str] = None,
    routines: Optional[Routines] = None,
    row_counts: bool = False,
) -> JobResult:
    """Load a job config, check it, and run it.

    Args:
        source: A job config (dict or path of a JSON file), or a loaded job.
        context: Context values that override the job config's own.
        registry: Where component types are looked up.
        engine: The Polars engine to collect with: ``streaming`` (default),
            ``in-memory`` or ``auto``. The ``V2_ENGINE`` environment variable
            sets it too.
        routines: Routine modules available to expressions.
        row_counts: Whether the rows of every component are counted, logged
            and put in the result's ``counts``. The run then takes about
            three times as long; without it only the counts something in
            the job reads are taken.

    Returns:
        How the run ended. A job that starts and fails is reported in the
        result, not raised; call ``raise_for_status()`` to raise.

    Raises:
        JobRefusedError: When the job config holds anything v2 will not run
            with. Nothing has run.
    """
    if isinstance(source, Job):
        job = source
    else:
        job = load_job(source, context=context, registry=registry, routines=routines)
    return Runner(job, engine=engine, routines=routines, row_counts=row_counts).run()
