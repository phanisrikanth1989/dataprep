"""Run a loaded job.

Each subjob is built as one lazy Polars plan, component by component, and
then run in a single pass: every file it writes and every row count it needs
are collected together, so a source is read once however many outputs hang
off it. Files are written beside their target and moved into place only when
the subjob has succeeded.
"""
from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import polars as pl

from ..components.base import Component, Eager, Sink, Source, Transform, Write
from ..errors import ConfigurationError, JobFailedError
from ..job.graph import subjobs
from ..job.keys import normalize_config
from ..job.model import ComponentSpec, Job
from .context import RunContext

logger = logging.getLogger(__name__)

DEFAULT_ENGINE = "streaming"


@dataclass
class JobResult:
    """How a run ended.

    Attributes:
        job_name: The job's name.
        status: ``success`` or ``failed``.
        error: Why it failed; empty on success.
        failed_component: Id of the component the failure is blamed on.
        rows: Rows written by each sink, by component id.
        global_map: globalMap entries at the end of the run.
        context: Context values at the end of the run.
        duration_s: Wall-clock seconds the run took.
    """

    job_name: str
    status: str = "success"
    error: str = ""
    failed_component: Optional[str] = None
    rows: Dict[str, int] = field(default_factory=dict)
    global_map: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0

    def raise_for_status(self) -> None:
        """Raise ``JobFailedError`` unless the job finished."""
        if self.status != "success":
            raise JobFailedError(self)


class _Failed(Exception):
    """A component could not be built or run."""

    def __init__(self, component_id: Optional[str], reason: str) -> None:
        super().__init__(reason)
        self.component_id = component_id
        self.reason = reason


class Runner:
    """Runs one loaded job."""

    def __init__(
        self,
        job: Job,
        engine: Optional[str] = None,
        routines: Optional[Mapping[str, Mapping[str, Callable[..., Any]]]] = None,
    ) -> None:
        self.job = job
        self.engine = engine or os.environ.get("V2_ENGINE") or DEFAULT_ENGINE
        self.run_context = RunContext(job.name, job.context, routines)
        self.rows: Dict[str, int] = {}

    def run(self) -> JobResult:
        """Run every subjob in order and report how it went."""
        started = time.perf_counter()
        result = JobResult(job_name=self.job.name)
        logger.info(f"[{self.job.name}] starting ({len(self.job.components)} components, engine={self.engine})")
        try:
            for component_ids in subjobs(self.job):
                self._run_subjob(component_ids)
        except _Failed as failure:
            result.status = "failed"
            result.error = failure.reason
            result.failed_component = failure.component_id
            logger.error(f"[{self.job.name}] failed at {failure.component_id}: {failure.reason}")
        result.rows = dict(self.rows)
        result.global_map = dict(self.run_context.global_map)
        result.context = dict(self.run_context.context)
        result.duration_s = time.perf_counter() - started
        logger.info(f"[{self.job.name}] {result.status} in {result.duration_s:.2f}s")
        return result

    # ------------------------------------------------------------------
    # One subjob
    # ------------------------------------------------------------------

    def _run_subjob(self, component_ids: List[str]) -> None:
        frames: Dict[str, pl.LazyFrame] = {}
        produced: List[Tuple[str, pl.LazyFrame]] = []
        pending: List[Tuple[str, Write]] = []

        for component_id in component_ids:
            spec = self.job.components[component_id]
            try:
                component = self._instantiate(spec)
                inputs = {flow.name: frames[flow.name] for flow in self.job.incoming(component_id)}
                if isinstance(component, Source):
                    outputs = component.read()
                elif isinstance(component, Sink):
                    pending.append((component_id, component.write(next(iter(inputs.values())))))
                    outputs = {}
                elif isinstance(component, Eager):
                    collected = self._collect(list(inputs.values()), pending, produced)
                    for name, frame in zip(inputs, collected):
                        self._share(name, frame.lazy(), frames)
                    outputs = component.run(dict(zip(inputs, collected))) or {}
                    outputs = {port: frame.lazy() for port, frame in outputs.items()}
                elif isinstance(component, Transform):
                    outputs = component.build(inputs)
                else:
                    raise TypeError(f"{type(component).__name__} is not a Source, Transform, Sink or Eager")
                for frame in outputs.values():
                    frame.collect_schema()
            except _Failed:
                raise
            except Exception as exc:  # noqa: BLE001 -- anything a component raises fails the job
                raise _Failed(component_id, _reason(exc)) from exc

            for flow in self.job.outgoing(component_id):
                if flow.port not in outputs:
                    raise _Failed(component_id, f"produced no '{flow.port}' output for flow '{flow.name}'")
                frames[flow.name] = outputs[flow.port]
            produced += [(component_id, frame) for frame in outputs.values()]

        self._collect([], pending, produced)

    def _instantiate(self, spec: ComponentSpec) -> Component:
        config, refusals = normalize_config(
            spec.raw_config, spec.cls.all_keys(), spec.where, resolve=self.run_context.resolve
        )
        if refusals:
            raise ConfigurationError("; ".join(f"{refusal.key}: {refusal.reason}" for refusal in refusals))
        return spec.cls(spec, config, self.run_context)

    def _share(self, flow_name: str, frame: pl.LazyFrame, frames: Dict[str, pl.LazyFrame]) -> None:
        """Hand a collected frame to every flow that carries the same output."""
        origin = next(flow for flow in self.job.flows if flow.name == flow_name)
        for flow in self.job.flows:
            if (flow.source, flow.port) == (origin.source, origin.port) and flow.name in frames:
                frames[flow.name] = frame

    # ------------------------------------------------------------------
    # Collecting
    # ------------------------------------------------------------------

    def _collect(
        self,
        wanted: List[pl.LazyFrame],
        pending: List[Tuple[str, Write]],
        produced: List[Tuple[str, pl.LazyFrame]],
    ) -> List[pl.DataFrame]:
        """Run pending writes and collect wanted frames, all in one pass."""
        writes = list(pending)
        pending.clear()
        if not wanted and not writes:
            return []
        temps = [_temp_path(write.path) for _, write in writes]
        counted = [(component_id, write.rows) for component_id, write in writes if write.rows is not None]
        try:
            plans = [write.sink(temp) for (_, write), temp in zip(writes, temps)]
            plans += [rows for _, rows in counted]
            results = pl.collect_all(plans + wanted, engine=self.engine)
        except Exception as exc:  # noqa: BLE001 -- Polars reports data problems in many types
            for temp in temps:
                _remove(temp)
            blamed = self._blame(produced, exc) or (writes[0][0] if len(writes) == 1 else None)
            raise _Failed(blamed, _reason(exc)) from exc

        counts = {
            component_id: int(frame.item())
            for (component_id, _), frame in zip(counted, results[len(writes):len(writes) + len(counted)])
        }
        for (component_id, write), temp in zip(writes, temps):
            try:
                _put_in_place(temp, write)
                rows = counts.get(component_id)
                if rows is not None:
                    self.rows[component_id] = self.rows.get(component_id, 0) + rows
                    self.run_context.global_map[f"{component_id}_NB_LINE"] = self.rows[component_id]
                if write.finish is not None:
                    write.finish(rows)
            except Exception as exc:  # noqa: BLE001
                _remove(temp)
                raise _Failed(component_id, _reason(exc)) from exc
        return results[len(writes) + len(counted):]

    def _blame(self, produced: List[Tuple[str, pl.LazyFrame]], error: Exception) -> Optional[str]:
        """Find the first component whose own output cannot be computed.

        Polars reports a data problem when the plan runs and names a column,
        not a component. Each component's output is therefore computed on its
        own, in order, holding no rows, until one fails.
        """
        for component_id, frame in produced:
            try:
                frame.select(pl.all().count()).collect(engine=self.engine)
            except Exception:  # noqa: BLE001
                return component_id
        return None


# ------------------------------------------------------------------
# Files
# ------------------------------------------------------------------

def _temp_path(path: str) -> str:
    folder, name = os.path.split(path)
    return os.path.join(folder, f".{name}.v2tmp{os.getpid()}")


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _put_in_place(temp: str, write: Write) -> None:
    if write.append and os.path.exists(write.path):
        with open(temp, "rb") as source, open(write.path, "ab") as target:
            shutil.copyfileobj(source, target)
        os.remove(temp)
    else:
        os.replace(temp, write.path)


def _reason(error: BaseException) -> str:
    """One line saying what went wrong."""
    text = " ".join(str(error).split())
    for marker in (" Resolved plan until failure", " You might want to try:"):
        text = text.split(marker)[0]
    return text or type(error).__name__
