"""Deterministic parity harness: run a job through the real engine, harvest
signals, and (Task 5) diff actual output against golden expected data.

This module runs a job config IN-PROCESS through ``ETLEngine`` (no subprocess)
and harvests the run's signals into a ``RunResult``. The engine's ``execute()``
returns two different dict shapes -- a success shape (with ``global_map`` and
``job_aborted``) and an exception shape (which has neither) -- so every field is
read with ``.get()``. The ACTUAL output is read back from the produced FILES,
not from in-memory flows (which the engine clears per subjob). Dropped
components are the config ids whose component ``type`` is not registered -- the
exact rule the fail-open engine uses to silently skip a component
(engine.py:192-194). This is NOT "absent from ``component_stats``": a known-type
component that simply never ran (e.g. one in an untriggered conditional subjob)
is legitimately missing from ``component_stats`` yet is NOT dropped.
"""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# FileOutput component type aliases (engine registers both the camelCase and the
# Talend t-prefixed name for the same class).
_FILE_OUTPUT_TYPES = {"FileOutputDelimited", "tFileOutputDelimited"}


@dataclass
class RunResult:
    """Signals harvested from one engine run of a job.

    Attributes:
        status: Engine run status ("success" or "error").
        job_aborted: True when a tDie/abort short-circuited the job. Absent from
            the engine's exception shape, so defaults to False.
        error: Error string from the engine, or None on success.
        global_map: Talend-compatible globalMap stats (NB_LINE, etc.). Absent
            from the engine's exception shape, so defaults to empty.
        component_stats: Per-component execution stats keyed by component id.
        dropped_components: Component ids whose type is unregistered
            (engine-skipped).
        outputs: Actual output DataFrames read back from each FileOutput
            component's file, keyed by output-component id.
        raw_stats: The unmodified stats dict returned by ``ETLEngine.execute()``.
    """
    status: str
    job_aborted: bool = False
    error: str | None = None
    global_map: dict = field(default_factory=dict)
    component_stats: dict = field(default_factory=dict)
    dropped_components: list = field(default_factory=list)
    outputs: dict = field(default_factory=dict)
    raw_stats: dict = field(default_factory=dict)


def _read_output(component: dict):
    """Read a FileOutput component's produced file back into a DataFrame.

    Reads every field as a string (``dtype=str``, ``keep_default_na=False``) so
    the captured output is compared textually against golden data in Task 5,
    with no pandas type inference. A missing or unreadable file yields None --
    that absence is itself a signal, not a crash.

    Args:
        component: A component config dict with a ``config.filepath`` and an
            optional ``config.fieldseparator`` (defaults to ";").

    Returns:
        A DataFrame of the file's contents, or None if the file is missing or
        cannot be parsed.
    """
    cfg = component.get("config", {})
    path = cfg.get("filepath")
    if not path or not Path(path).exists():
        return None
    sep = cfg.get("fieldseparator", ";")
    try:
        return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False)
    except Exception as exc:  # a malformed/empty output file is a signal, not a crash
        logger.warning("[run_and_validate] could not read output %s: %s", path, exc)
        return None


def _dropped_components(components: list) -> list:
    """Config ids whose component TYPE is not registered -- the engine silently
    skips these (engine.py:192-194). A known-type component that simply did not
    run (e.g. an untriggered conditional subjob) has a registered type and is
    NOT dropped."""
    from src.v1.engine.component_registry import REGISTRY
    return [c.get("id") for c in components if REGISTRY.get(c.get("type")) is None]


def run_job_capture(job_config: dict, work_dir) -> RunResult:
    """Run a job through ETLEngine and harvest its run signals into a RunResult.

    The job config is deep-copied before running so the caller's dict is never
    mutated by the engine. Any exception raised while constructing or executing
    the engine is tolerated and converted into a uniform ``status="error"``
    result rather than propagating.

    Args:
        job_config: The engine job configuration dict.
        work_dir: The working directory for the run. Reserved for Task 5
            (resolving relative output paths / golden-data location); the
            current capture reads the absolute ``filepath`` recorded on each
            FileOutput component.

    Returns:
        A ``RunResult`` capturing status, globalMap, per-component stats,
        component ids whose type is unregistered (engine-skipped), and the
        actual output DataFrames.
    """
    from src.v1.engine.engine import ETLEngine

    job = copy.deepcopy(job_config)
    try:
        engine = ETLEngine(job)
        stats = engine.execute()
    except Exception as exc:  # constructor/other hard failure -> uniform error result
        logger.warning("[run_and_validate] engine raised: %s", exc)
        return RunResult(status="error", error=str(exc))

    component_stats = stats.get("component_stats", {})
    dropped = _dropped_components(job.get("components", []))

    outputs = {}
    for comp in job.get("components", []):
        if comp.get("type") in _FILE_OUTPUT_TYPES:
            df = _read_output(comp)
            if df is not None:
                outputs[comp["id"]] = df

    return RunResult(
        status=stats.get("status", "error"),
        job_aborted=bool(stats.get("job_aborted", False)),
        error=stats.get("error"),
        global_map=stats.get("global_map", {}),
        component_stats=component_stats,
        dropped_components=dropped,
        outputs=outputs,
        raw_stats=stats,
    )
