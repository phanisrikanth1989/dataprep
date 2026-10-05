"""Run a loaded job.

Each subjob is built as one lazy Polars plan, component by component, and
then run in a single pass: every file it writes and everything its
components asked to know about the data are collected together, so a source
is read once however many outputs hang off it. Files are written beside
their target and moved into place only when the whole subjob has succeeded.

Which subjob runs after which follows v1: subjobs nothing triggers run in
job-config order, and what a subjob triggers runs right after it.
"""
from __future__ import annotations

import dataclasses
import logging
import os
import re
import shutil
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Mapping, Optional, Tuple

import polars as pl

from ..components.base import CheckFailed, Component, Sink, Source, Tap, Write
from ..errors import ConfigurationError, JobFailedError
from ..job.graph import subjobs
from ..job.keys import normalize_config
from ..job.model import ComponentSpec, Job, Trigger
from ..types import VIOLATION, conform
from .conditions import evaluate
from .context import RunContext

logger = logging.getLogger(__name__)

DEFAULT_ENGINE = "streaming"
# A failed pass that ran longer than this is not followed by the search for the component at fault.
BLAME_BUDGET_S = 60.0
_STATS = ("NB_LINE", "NB_LINE_OK", "NB_LINE_REJECT")
_NULL_COLUMN = re.compile(r"Column '(.*)': non-nullable column has null")


@dataclass
class JobResult:
    """How a run ended.

    Attributes:
        job_name: The job's name.
        status: ``success``, or ``failed`` when any component failed.
        error: Why the first failure happened; empty on success.
        failed_component: Id of the component the first failure is blamed on.
        failures: Every failure: component id to reason, in the order they
            happened.
        rows: Rows written by each sink, by component id.
        global_map: globalMap entries at the end of the run.
        context: Context values at the end of the run.
        duration_s: Wall-clock seconds the run took.
    """

    job_name: str
    status: str = "success"
    error: str = ""
    failed_component: Optional[str] = None
    failures: Dict[str, str] = field(default_factory=dict)
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


@dataclass
class _Subjob:
    """What one subjob has built and written so far."""

    writes: List[Tuple[str, Write]] = field(default_factory=list)
    taps: List[Tuple[str, Tap]] = field(default_factory=list)
    produced: List[Tuple[str, pl.LazyFrame]] = field(default_factory=list)
    written: List[Tuple[str, Write, str, Optional[int]]] = field(default_factory=list)


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
        self.run_context = RunContext(job.name, job.context, routines or job.routine_modules, job.context_types)
        self.rows: Dict[str, int] = {}
        self._wanted = _wanted_stats(job)

    def run(self) -> JobResult:
        """Run the job's subjobs and report how it went."""
        started = time.perf_counter()
        result = JobResult(job_name=self.job.name)
        logger.info(f"[{self.job.name}] starting ({len(self.job.components)} components, engine={self.engine})")
        try:
            self._run_subjobs(result)
        finally:
            self.run_context.cleanup()
        if result.failures:
            result.status = "failed"
        result.rows = dict(self.rows)
        result.global_map = dict(self.run_context.global_map)
        result.context = dict(self.run_context.context)
        result.duration_s = time.perf_counter() - started
        logger.info(f"[{self.job.name}] {result.status} in {result.duration_s:.2f}s")
        return result

    # ------------------------------------------------------------------
    # Subjobs and triggers
    # ------------------------------------------------------------------

    def _run_subjobs(self, result: JobResult) -> None:
        plan = subjobs(self.job)
        subjob_of = {component_id: index for index, members in enumerate(plan) for component_id in members}
        leaving: Dict[int, List[Trigger]] = {}
        triggered = set()
        for trigger in sorted(self.job.triggers, key=lambda trigger: trigger.order):
            leaving.setdefault(subjob_of[trigger.source], []).append(trigger)
            triggered.add(subjob_of[trigger.target])

        queue: Deque[int] = deque(index for index in range(len(plan)) if index not in triggered)
        done = set()
        while queue:
            index = queue.popleft()
            if index in done:
                continue
            done.add(index)
            failure = self._run_subjob(plan[index])
            if failure is not None:
                self._record(result, failure.component_id, failure.reason)
            try:
                following = self._fired(leaving.get(index, []), failure, subjob_of)
            except ConfigurationError as exc:
                self._record(result, None, str(exc))
                return
            queue.extendleft(reversed(following))

    def _fired(self, triggers: List[Trigger], failure: Optional[_Failed], subjob_of: Dict[str, int]) -> List[int]:
        """The subjobs a finished subjob sets off, in trigger order."""
        following: List[int] = []
        for trigger in triggers:
            if trigger.kind in ("OnSubjobOk", "OnComponentOk"):
                fires = failure is None
            elif trigger.kind == "OnSubjobError":
                fires = failure is not None
            elif trigger.kind == "OnComponentError":
                fires = failure is not None and failure.component_id == trigger.source
            else:
                fires = evaluate(trigger.condition, self.run_context.context, self.run_context.global_map)
            target = subjob_of[trigger.target]
            if fires and target not in following:
                following.append(target)
        return following

    def _record(self, result: JobResult, component_id: Optional[str], reason: str) -> None:
        logger.error(f"[{self.job.name}] failed at {component_id}: {reason}")
        result.failures.setdefault(component_id or "job", reason)
        if not result.error:
            result.error = reason
            result.failed_component = component_id

    # ------------------------------------------------------------------
    # One subjob
    # ------------------------------------------------------------------

    def _run_subjob(self, component_ids: List[str]) -> Optional[_Failed]:
        """Build and run one subjob. Returns the failure, or None when it finished."""
        state = _Subjob()
        try:
            self._build(component_ids, state)
            self._collect([], state)
            self._place(state)
        except _Failed as failure:
            for _, _, temp, _ in state.written:
                _remove(temp)
            return failure
        return None

    def _build(self, component_ids: List[str], state: _Subjob) -> None:
        frames: Dict[str, pl.LazyFrame] = {}
        for component_id in component_ids:
            spec = self.job.components[component_id]
            try:
                component = self._ready(spec)
                inputs = {flow.name: frames[flow.name] for flow in self.job.incoming(component_id)}
                if isinstance(component, Sink):
                    state.writes.append((component_id, component.write(next(iter(inputs.values())))))
                    outputs: Dict[str, pl.LazyFrame] = {}
                elif isinstance(component, Source):
                    outputs = component.read()
                elif component.needs_rows():
                    collected = self._collect(list(inputs.values()), state)
                    for name, frame in zip(inputs, collected):
                        self._share(name, frame.lazy(), frames)
                    results = component.run(dict(zip(inputs, collected))) or {}
                    outputs = {port: frame.lazy() for port, frame in results.items()}
                else:
                    outputs = component.build(inputs)
                outputs = self._conformed(component, outputs)
                for frame in outputs.values():
                    frame.collect_schema()
                self._count(component, inputs, outputs)
            except _Failed:
                raise
            except Exception as exc:  # noqa: BLE001 -- anything a component raises fails the job
                raise _Failed(component_id, _reason(exc)) from exc

            for flow in self.job.outgoing(component_id):
                if flow.port not in outputs:
                    raise _Failed(component_id, f"produced no '{flow.port}' output for flow '{flow.name}'")
                frames[flow.name] = outputs[flow.port]
            state.produced += [(component_id, frame) for frame in outputs.values()]
            state.taps += [(component_id, tap) for tap in component.taps]

    def _instantiate(self, spec: ComponentSpec) -> Component:
        config, refusals = normalize_config(
            spec.raw_config, spec.cls.all_keys(), spec.where, resolve=self.run_context.resolve
        )
        if refusals:
            raise ConfigurationError("; ".join(f"{refusal.key}: {refusal.reason}" for refusal in refusals))
        return spec.cls(spec, config, self.run_context)

    def _ready(self, spec: ComponentSpec) -> Component:
        """A component about to run: built, and with nothing wrong in its config."""
        component = self._instantiate(spec)
        found = component.problems()
        if found:
            raise ConfigurationError("; ".join(found))
        return component

    def _share(self, flow_name: str, frame: pl.LazyFrame, frames: Dict[str, pl.LazyFrame]) -> None:
        """Hand a collected frame to every flow that carries the same output."""
        origin = next(flow for flow in self.job.flows if flow.name == flow_name)
        for flow in self.job.flows:
            if (flow.source, flow.port) == (origin.source, origin.port) and flow.name in frames:
                frames[flow.name] = frame

    # ------------------------------------------------------------------
    # Declared schemas and row counts
    # ------------------------------------------------------------------

    def _conformed(self, component: Component, outputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        """Make a component's main and reject outputs match its declared schemas."""
        outputs = dict(outputs)
        spec = component.spec
        if "main" in outputs:
            columns = spec.schema if component.conforms else []
            main, violation = conform(outputs["main"], columns, rename_errors=True)
            if violation is not None and component.config.get("die_on_error", True):
                component.check(
                    main.filter(violation.is_not_null()).select(pl.len().alias("rows"), violation.first().alias("why")),
                    _null_problem,
                )
                main = main.drop(VIOLATION)
            elif violation is not None:
                broken = main.filter(violation.is_not_null())
                main = main.filter(violation.is_null()).drop(VIOLATION)
                if "reject" in type(component).outputs:
                    rejected = broken.with_columns(
                        pl.lit("SCHEMA_VIOLATION").alias("errorCode"), violation.alias("errorMessage")
                    ).drop(VIOLATION)
                    own = outputs.get("reject")
                    outputs["reject"] = rejected if own is None else pl.concat([own, rejected], how="diagonal_relaxed")
            outputs["main"] = main
        if "reject" in outputs and spec.reject_schema and component.conforms:
            columns = [dataclasses.replace(column, nullable=True) for column in spec.reject_schema]
            outputs["reject"], _ = conform(outputs["reject"], columns)
        return outputs

    def _count(self, component: Component, inputs: Dict[str, pl.LazyFrame], outputs: Dict[str, pl.LazyFrame]) -> None:
        """Count the rows of a component whose counts something in the job reads."""
        wanted = self._wanted.get(component.id)
        if not wanted or isinstance(component, Sink):
            return
        counted: Dict[str, List[pl.LazyFrame]] = {
            "NB_LINE_OK": [outputs[port] for port in ("main",) if port in outputs],
            "NB_LINE_REJECT": [outputs[port] for port in ("reject",) if port in outputs],
        }
        counted["NB_LINE"] = list(inputs.values()) or counted["NB_LINE_OK"] + counted["NB_LINE_REJECT"]
        global_map = self.run_context.global_map
        for stat in wanted:
            key = f"{component.id}_{stat}"
            global_map[key] = 0
            for frame in counted[stat]:
                component.tap(frame.select(pl.len()), lambda rows, key=key: _add(global_map, key, rows.item()))

    # ------------------------------------------------------------------
    # Collecting and placing files
    # ------------------------------------------------------------------

    def _collect(self, wanted: List[pl.LazyFrame], state: _Subjob) -> List[pl.DataFrame]:
        """Run pending writes and taps and collect wanted frames, all in one pass."""
        writes, taps = state.writes, state.taps
        state.writes, state.taps = [], []
        if not wanted and not writes and not taps:
            return []
        temps = [_temp_path(write.path) for _, write in writes]
        counted = [(component_id, write.rows) for component_id, write in writes if write.rows is not None]
        started = time.perf_counter()
        try:
            plans = [write.sink(temp) for (_, write), temp in zip(writes, temps)]
            plans += [rows for _, rows in counted]
            plans += [tap.frame for _, tap in taps]
            results = pl.collect_all(plans + wanted, engine=self.engine)
        except Exception as exc:  # noqa: BLE001 -- Polars reports data problems in many types
            for temp in temps:
                _remove(temp)
            blamed = None
            if time.perf_counter() - started <= BLAME_BUDGET_S:
                blamed = self._blame(state.produced) or (writes[0][0] if len(writes) == 1 else None)
            raise _Failed(blamed, _reason(exc)) from exc

        first_count, first_tap, first_wanted = len(writes), len(writes) + len(counted), len(plans)
        counts = {
            component_id: int(frame.item())
            for (component_id, _), frame in zip(counted, results[first_count:first_tap])
        }
        state.written += [
            (component_id, write, temp, counts.get(component_id)) for (component_id, write), temp in zip(writes, temps)
        ]
        for (component_id, tap), frame in zip(taps, results[first_tap:first_wanted]):
            try:
                tap.receive(frame)
            except CheckFailed as problem:
                raise _Failed(component_id, str(problem)) from problem
            except Exception as exc:  # noqa: BLE001
                raise _Failed(component_id, _reason(exc)) from exc
        return results[first_wanted:]

    def _place(self, state: _Subjob) -> None:
        """Put every file the subjob wrote in place."""
        while state.written:
            component_id, write, temp, rows = state.written.pop(0)
            try:
                if write.place is not None:
                    write.place(temp, rows)
                else:
                    _put_in_place(temp, write)
                if rows is not None:
                    self.rows[component_id] = self.rows.get(component_id, 0) + rows
                    self.run_context.global_map[f"{component_id}_NB_LINE"] = self.rows[component_id]
                    for stat in self._wanted.get(component_id, ()):
                        self.run_context.global_map[f"{component_id}_{stat}"] = (
                            0 if stat == "NB_LINE_REJECT" else self.rows[component_id]
                        )
                if write.finish is not None:
                    write.finish(rows)
            except Exception as exc:  # noqa: BLE001
                _remove(temp)
                raise _Failed(component_id, _reason(exc)) from exc

    def _blame(self, produced: List[Tuple[str, pl.LazyFrame]]) -> Optional[str]:
        """Find the first component whose own output cannot be computed.

        Polars reports a data problem when the plan runs and names a column,
        not a component. Each component's output is therefore computed on its
        own, in order, holding no rows, until one fails. That reads the data
        again once per component, so it is only done after a short pass.
        """
        for component_id, frame in produced:
            try:
                frame.select(pl.all().count()).collect(engine=self.engine)
            except Exception:  # noqa: BLE001
                return component_id
        return None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _wanted_stats(job: Job) -> Dict[str, List[str]]:
    """The row counts something in the job reads: component id to stat names."""
    texts: List[str] = [trigger.condition or "" for trigger in job.triggers]
    for spec in job.components.values():
        _strings(spec.raw_config, texts)
    everything = "\n".join(texts)
    wanted: Dict[str, List[str]] = {}
    if "_NB_LINE" not in everything:
        return wanted
    for component_id in job.components:
        for stat in _STATS:
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(component_id)}_{stat}(?![A-Za-z0-9_])", everything):
                wanted.setdefault(component_id, []).append(stat)
    return wanted


def _strings(value: Any, found: List[str]) -> None:
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            _strings(item, found)
    elif isinstance(value, list):
        for item in value:
            _strings(item, found)


def _add(global_map: Dict[str, Any], key: str, rows: int) -> None:
    global_map[key] = global_map.get(key, 0) + int(rows)


def _null_problem(found: pl.DataFrame) -> Optional[str]:
    """v1's words for a missing value in a column that may not hold one."""
    if not found["rows"].item():
        return None
    named = _NULL_COLUMN.fullmatch(found["why"].item() or "")
    return f"Column '{named.group(1) if named else '?'}' has NULL values but is not nullable"


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
