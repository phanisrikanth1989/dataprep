"""The v2 engine: load a job config, check it, and run it."""
from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Tuple, Union

from ..components.registry import REGISTRY, Registry
from ..errors import ConfigurationError, JobRefusedError
from ..job.loader import caller_settings
from ..job.loader import load_job as read_job
from ..job.model import Job, RunSettings
from ..job.refusal import RefusalReport
from .check import check_job
from .picking import check_only, source_problem
from .routines import load_routines
from .runner import JobResult, Runner

__all__ = ["JobResult", "Runner", "check_job", "load_job", "run_job", "settled"]

logger = logging.getLogger(__name__)

Routines = Mapping[str, Mapping[str, Callable[..., Any]]]

# The levels that the loads and runs under way asked of the engine's logger, and its level before the first.
_LEVELS: List[int] = []
_LEVEL_BEFORE = [logging.NOTSET]
_LEVEL_LOCK = threading.Lock()


def load_job(
    source: Union[Mapping[str, Any], str, Path],
    context: Optional[Mapping[str, Any]] = None,
    *,
    registry: Registry = REGISTRY,
    routines: Optional[Routines] = None,
    log_level: Optional[str] = None,
) -> Job:
    """Load a job config and check that v2 can run it.

    Args:
        source: The job config, as a dict or as the path of a JSON file.
        context: Context values that override the job config's own.
        registry: Where component types are looked up.
        routines: Routine modules available to expressions.
        log_level: The level the engine's log lines are written from while
            the job loads, when whoever loads it asks for one. Otherwise
            the job config's ``run.log_level`` is, when it has one.

    Returns:
        The loaded job.

    Raises:
        JobRefusedError: When the job config holds anything v2 will not run
            with. Its report lists every problem found. Nothing has run.
    """
    job = read_job(source, context=context, registry=registry)
    report = RefusalReport(job_name=job.name)
    with logging_from(log_level or job.run.log_level):
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
    asked, refusals = caller_settings(run)
    if isinstance(source, Job):
        job = source
    else:
        # A level that is refused is said below, with the job's name; the job is loaded without it.
        level = None if refusals else asked.log_level
        job = load_job(source, context=context, registry=registry, routines=routines, log_level=level)
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
    with logging_from(settings.log_level):
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
    report = RefusalReport(job_name=job.name)
    if settings.trace and settings.only is None:
        report.add("job", "run.trace", "a trace is of the rows `only` picks; say which rows")
    if settings.only is not None:
        found = source_problem(job, settings.only)
        if not found:
            try:
                reader = Runner(job)._instantiate(job.components[settings.only.source])
            except ConfigurationError:
                # Its config waits for a value the run sets: what only the built reader can tell is said by the run.
                reader = None
            found = check_only(job, settings.only, reader)
        report.extend(found)
    if report:
        raise JobRefusedError(report)
    return settings, asked_for


@contextmanager
def logging_from(level: Optional[str]) -> Iterator[None]:
    """Have the engine's log lines written from a level up while a job loads or runs; as it was before, after.

    The engine has one logger (``src.v2``) for the whole process. While
    several loads or runs that asked for a level are under way, its lines
    are written from the lowest of their levels up; when the last of them
    ends, the logger is as it was before the first.
    """
    if level is None:
        yield
        return
    engine_log = logging.getLogger("src.v2")
    asked = logging.getLevelNamesMapping().get(level.upper())
    if asked is None:
        raise ConfigurationError(f"{level!r} is not a log level")
    with _LEVEL_LOCK:
        if not _LEVELS:
            _LEVEL_BEFORE[0] = engine_log.level
        _LEVELS.append(asked)
        engine_log.setLevel(min(_LEVELS))
    try:
        yield
    finally:
        with _LEVEL_LOCK:
            _LEVELS.remove(asked)
            engine_log.setLevel(min(_LEVELS) if _LEVELS else _LEVEL_BEFORE[0])
