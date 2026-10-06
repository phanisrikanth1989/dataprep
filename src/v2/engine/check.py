"""Check a loaded job before it runs.

The loader checks a job config key by key. This goes further and builds
every subjob against empty frames shaped like its declared schemas, which
finds what only shows once components meet: an expression naming a column
that is not there, config keys that do not go together, Python that has no
Polars form. Nothing is read and nothing is written.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Mapping, Optional

import polars as pl

from ..components.base import Sink, Source
from ..errors import ExpressionError
from ..job.graph import subjobs
from ..job.keys import normalize_config
from ..job.model import ComponentSpec, Job
from ..job.refusal import RefusalReport
from .context import _BARE, _TEMPLATE
from .runner import Runner, _reason


def check_job(
    job: Job,
    routines: Optional[Mapping[str, Mapping[str, Callable[..., Any]]]] = None,
) -> RefusalReport:
    """Build every subjob of a job without data and report what cannot work.

    When the job holds a component that sets context variables while it
    runs, a config value that names a context variable is not judged: the
    variable may not exist yet, or hold a placeholder until it is loaded. A
    component that cannot be built for that reason is left unchecked,
    together with what it feeds.
    """
    report = RefusalReport(job_name=job.name)
    runner = Runner(job, routines=routines)
    late_context = any(getattr(spec.cls, "sets_context", False) for spec in job.components.values())
    for members in subjobs(job):
        frames: Dict[str, pl.LazyFrame] = {}
        for component_id in members:
            spec = job.components[component_id]
            arriving = job.incoming(component_id)
            try:
                component = runner._instantiate(spec)
                found = component.problems()
                for problem in found:
                    key, _, reason = problem.partition(": ")
                    if not (late_context and _names_context(_written(spec, key))):
                        report.add(spec.where, key, reason)
                if found or any(flow.name not in frames for flow in arriving):
                    continue
                inputs = {flow.name: frames[flow.name] for flow in arriving}
                if isinstance(component, Sink):
                    continue
                if isinstance(component, Source) or component.needs_rows():
                    outputs = component.declared_outputs()
                else:
                    outputs = component.build(inputs)
                outputs = runner._conformed(component, outputs)
                for frame in outputs.values():
                    frame.collect_schema()
            except ExpressionError as exc:
                # A globalMap entry is set while the job runs, and so is a context variable when the
                # job loads context: neither can be judged before the run.
                later = "globalMap has no entry" in exc.reason or (
                    late_context and "context has no variable" in exc.reason
                )
                if not later:
                    report.add(spec.where, "expression", str(exc))
                continue
            except Exception as exc:  # noqa: BLE001 -- whatever stops a build is worth reporting
                reason = _reason(exc)
                if late_context and reason.startswith("context has no variable"):
                    continue
                if late_context:
                    judged = _judged_now(spec, runner)
                    reason = reason if judged is None else judged
                if reason:
                    report.add(spec.where, "config", reason)
                continue
            for flow in job.outgoing(component_id):
                if flow.port in outputs:
                    frames[flow.name] = outputs[flow.port]
    runner.run_context.cleanup()
    return report


# ------------------------------------------------------------------
# Values a component of the job may still set
# ------------------------------------------------------------------

def _judged_now(spec: ComponentSpec, runner: Runner) -> Optional[str]:
    """What is wrong with a component's config, leaving out the values that name a context variable.

    Returns:
        The problems to report, empty when every one of them waits for the
        context; None when the config is not what stopped the build.
    """
    _, refusals = normalize_config(spec.raw_config, spec.cls.all_keys(), spec.where, resolve=runner.run_context.resolve)
    if not refusals:
        return None
    wrong: List[str] = [
        f"{refusal.key}: {refusal.reason}" for refusal in refusals
        if not _names_context(_raw_at(spec.raw_config, refusal.key))
    ]
    return "; ".join(wrong)


def _names_context(value: Any) -> bool:
    return isinstance(value, str) and bool(_TEMPLATE.search(value) or _BARE.search(value))


def _raw_at(raw: Any, path: str) -> Any:
    """The value at a place in a raw config, named the way a refusal names it: ``lookups[0].name``."""
    value = raw
    for part in re.findall(r"[^.\[\]]+", path):
        if isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _written(spec: ComponentSpec, name: str) -> Any:
    """The value a config key was given in the job config, under whichever of its spellings."""
    raw = spec.raw_config or {}
    for key in spec.cls.all_keys():
        if key.name == name:
            return next((raw[spelling] for spelling in key.spellings if spelling in raw), None)
    return _raw_at(raw, name)
