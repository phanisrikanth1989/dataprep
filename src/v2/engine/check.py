"""Check a loaded job before it runs.

The loader checks a job config key by key. This goes further and builds
every subjob against empty frames shaped like its declared schemas, which
finds what only shows once components meet: an expression naming a column
that is not there, config keys that do not go together, Python that has no
Polars form. Nothing is read and nothing is written.

A component that cannot be built does not hide the faults of what it feeds:
the check carries on down the flow with the columns the component declares.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Mapping, Optional

import polars as pl

from ..components.base import Component, Sink, Source
from ..errors import ExpressionError
from ..job.graph import subjobs
from ..job.keys import normalize_config
from ..job.model import ComponentSpec, Job
from ..job.refusal import RefusalReport
from ..rows import HIDDEN, hidden
from .context import _BARE, _TEMPLATE
from .runner import Runner, _reason


def check_job(
    job: Job,
    routines: Optional[Mapping[str, Mapping[str, Callable[..., Any]]]] = None,
) -> RefusalReport:
    """Build every subjob of a job without data and report what cannot work.

    A component with a fault does not hide the faults of what it feeds. The
    check goes on down the flow with empty frames of the columns the
    component declares, and a fault found that way says what it was judged
    on. Where the component declares no columns, what it feeds is left
    unchecked: its columns would be a guess, and a guess reports faults that
    are not there.

    When the job holds a component that sets context variables while it
    runs, a config value that names a context variable is not judged: the
    variable may not exist yet, or hold a placeholder until it is loaded. A
    component that cannot be built for that reason is left unchecked,
    together with what it feeds. So is one that reads a globalMap entry,
    which is set while the job runs.
    """
    report = RefusalReport(job_name=job.name)
    runner = Runner(job, routines=routines)
    late_context = any(getattr(spec.cls, "sets_context", False) for spec in job.components.values())
    for members in subjobs(job):
        frames: Dict[str, pl.LazyFrame] = {}
        # Flow name to the faulty component whose declared columns the flow's frame stands on.
        stands_on: Dict[str, str] = {}
        for component_id in members:
            spec = job.components[component_id]
            arriving = job.incoming(component_id)
            origin = next((stands_on[flow.name] for flow in arriving if flow.name in stands_on), None)
            reported = len(report)
            component: Optional[Component] = None
            outputs: Dict[str, pl.LazyFrame] = {}
            try:
                component = runner._instantiate(spec)
                found = component.problems()
                for problem in found:
                    key, _, reason = problem.partition(": ")
                    if not (late_context and _names_context(_written(spec, key))):
                        report.add(spec.where, key, reason)
                if not found and all(flow.name in frames for flow in arriving) and not isinstance(component, Sink):
                    inputs = {flow.name: frames[flow.name] for flow in arriving}
                    if isinstance(component, Source) or component.needs_rows():
                        outputs = component.declared_outputs()
                    else:
                        outputs = component.build(inputs)
                    outputs = runner._conformed(component, outputs)
                    made = {name for frame in outputs.values() for name in frame.collect_schema().names()}
                    # Nothing is read here, so no row has a number yet: a hidden column is the job's own.
                    arrived = {name for frame in inputs.values() for name in frame.collect_schema().names()}
                    for name in sorted(set(hidden(made)) - arrived):
                        report.add(
                            spec.where, "columns",
                            f"'{name}': a column's name may not start with '{HIDDEN}', which marks the engine's own",
                        )
            except ExpressionError as exc:
                outputs = {}
                # A globalMap entry is set while the job runs, and so is a context variable when the
                # job loads context: neither can be judged before the run.
                later = "globalMap has no entry" in exc.reason or (
                    late_context and "context has no variable" in exc.reason
                )
                if not later:
                    report.add(spec.where, "expression", _judged_on(str(exc), origin))
            except Exception as exc:  # noqa: BLE001 -- whatever stops a build is worth reporting
                outputs = {}
                reason = _reason(exc)
                if late_context and reason.startswith("context has no variable"):
                    reason = ""
                elif late_context:
                    judged = _judged_now(spec, runner)
                    reason = reason if judged is None else judged
                if reason:
                    report.add(spec.where, "config", _judged_on(reason, origin))
            if len(report) > reported and component is not None:
                outputs, origin = _declared(component), component_id
            for flow in job.outgoing(component_id):
                if flow.port in outputs:
                    frames[flow.name] = outputs[flow.port]
                    if origin is not None:
                        stands_on[flow.name] = origin
    runner.run_context.cleanup()
    return report


# ------------------------------------------------------------------
# Going on past a component with a fault
# ------------------------------------------------------------------

def _declared(component: Component) -> Dict[str, pl.LazyFrame]:
    """Empty frames of the columns a component with a fault declares to hand on.

    A source describes every output it has. Of any other component only the
    main output is its declared schema; what leaves by its other outputs is
    declared nowhere, and is left out.
    """
    outputs = component.declared_outputs()
    if isinstance(component, Source):
        return outputs
    return {port: frame for port, frame in outputs.items() if port == "main"}


def _judged_on(reason: str, origin: Optional[str]) -> str:
    """A fault found past a component with a fault of its own says which columns it was judged on."""
    if origin is None:
        return reason
    return f"{reason} (checked against the columns '{origin}' declares, because '{origin}' has a fault of its own)"


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
