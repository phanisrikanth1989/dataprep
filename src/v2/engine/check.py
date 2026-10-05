"""Check a loaded job before it runs.

The loader checks a job config key by key. This goes further and builds
every subjob against empty frames shaped like its declared schemas, which
finds what only shows once components meet: an expression naming a column
that is not there, config keys that do not go together, Python that has no
Polars form. Nothing is read and nothing is written.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional

import polars as pl

from ..components.base import Sink, Source
from ..errors import ExpressionError
from ..job.graph import subjobs
from ..job.model import Job
from ..job.refusal import RefusalReport
from .runner import Runner, _reason


def check_job(
    job: Job,
    routines: Optional[Mapping[str, Mapping[str, Callable[..., Any]]]] = None,
) -> RefusalReport:
    """Build every subjob of a job without data and report what cannot work.

    A component whose config names a context variable that does not exist
    yet is left unchecked, together with what it feeds, when the job holds a
    component that sets context variables while it runs.
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
                report.add(spec.where, "config", reason)
                continue
            for flow in job.outgoing(component_id):
                if flow.port in outputs:
                    frames[flow.name] = outputs[flow.port]
    runner.run_context.cleanup()
    return report
