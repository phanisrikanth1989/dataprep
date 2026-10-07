"""The v2 engine: load a job config, check it, and run it."""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Mapping, Optional, Tuple, Union

from ..components.registry import REGISTRY, Registry
from ..errors import ConfigurationError, JobRefusedError
from ..job.loader import caller_settings
from ..job.loader import load_job as read_job
from ..job.model import Job, RunSettings
from ..job.refusal import RefusalReport
from .check import check_job
from .routines import load_routines
from .runner import JobResult, Runner

__all__ = ["JobResult", "Runner", "check_job", "load_job", "run_job", "settled"]

logger = logging.getLogger(__name__)

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
    row_counts: Optional[bool] = None,
    run: Optional[Mapping[str, Any]] = None,
) -> JobResult:
    """Load a job config, check it, and run it.

    This is how a service runs a job: the job config as a dict, the context
    values that override its own, and the run settings that override its
    ``run`` block.

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
            the job reads are taken. Wins over ``run`` and over the job
            config.
        run: Run settings, with the keys of a job config's ``run`` block
            (``log_level``, ``row_counts``, ``summary_file``, ``only``,
            ``trace``). Each one given wins over the job config's.

    Returns:
        How the run ended. A job that starts and fails is reported in the
        result, not raised; call ``raise_for_status()`` to raise.
        ``summary()`` gives it as plain values, ready to be sent as JSON.

    Raises:
        JobRefusedError: When the job config or the run settings hold
            anything v2 will not run with. Nothing has run.
        ConfigurationError: When the summary file cannot be opened. Nothing
            has run.
    """
    if isinstance(source, Job):
        job = source
    else:
        job = load_job(source, context=context, registry=registry, routines=routines)
    asked, refusals = caller_settings(run)
    if refusals:
        report = RefusalReport(job_name=job.name)
        report.extend(refusals)
        raise JobRefusedError(report)
    if row_counts is not None:
        asked.row_counts = row_counts
    settings, asked_for = settled(job, asked)

    # Opened before the job runs: a job is not run only to find that its summary has nowhere to go.
    summary_file = None
    if settings.summary_file:
        try:
            summary_file = open(settings.summary_file, "w", encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(f"run.summary_file {settings.summary_file}: {exc}") from None
    with log_level(settings.log_level):
        result = Runner(
            job, engine=engine, routines=routines, settings=settings, asked_for=asked_for, asked_by="asked by the caller"
        ).run()
    if summary_file is not None:
        try:
            with summary_file:
                summary_file.write(json.dumps(result.summary(), indent=2) + "\n")
        except OSError as exc:
            # The job has run, and how it ended stands: this is said, and is not made a failure of the job.
            logger.warning(f"[{job.name}] the summary could not be written to {settings.summary_file}: {exc}")
    return result


def settled(job: Job, asked: RunSettings) -> Tuple[RunSettings, Dict[str, bool]]:
    """The run settings in force: what was asked for laid over the job config's ``run`` block.

    Returns:
        The settings, and for each one that is set whether it was asked for
        (True) or stands in the job config (False).

    Raises:
        JobRefusedError: When the settings do not go together.
    """
    settings, asked_for = asked.over(job.run)
    if settings.trace and settings.only is None:
        report = RefusalReport(job_name=job.name)
        report.add("job", "run.trace", "a trace is of the rows `only` picks; say which rows")
        raise JobRefusedError(report)
    return settings, asked_for


@contextmanager
def log_level(level: Optional[str]) -> Iterator[None]:
    """Have the engine's log lines written from a level up while a job runs; as it was before, after."""
    if level is None:
        yield
        return
    engine_log = logging.getLogger("src.v2")
    before = engine_log.level
    engine_log.setLevel(level)
    try:
        yield
    finally:
        engine_log.setLevel(before)
