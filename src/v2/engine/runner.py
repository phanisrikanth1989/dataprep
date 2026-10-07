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
import json
import logging
import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Iterable, List, Mapping, Optional, Set, Tuple

import polars as pl

from ..components.base import CheckFailed, Component, Sink, Source, Tap, Write, ascii_only
from ..errors import ConfigurationError, JobFailedError
from ..files import put_in_place
from ..job.graph import subjobs
from ..job.keys import normalize_config
from ..job.model import ComponentSpec, Job, Trigger
from ..rows import first_of, visible, without
from ..types import VIOLATION, conform
from .conditions import evaluate
from .context import RunContext

logger = logging.getLogger(__name__)

DEFAULT_ENGINE = "streaming"
# A failed pass that ran longer than this is not followed by the search for the component at fault.
BLAME_BUDGET_S = 60.0
_STATS = ("NB_LINE", "NB_LINE_OK", "NB_LINE_REJECT")
_ROW_NUMBER = "__v2_row_number"
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
        counts: The row counts of every component of every subjob that
            finished, when the run was asked for them: component id to
            ``NB_LINE``, ``NB_LINE_OK`` and ``NB_LINE_REJECT``. Empty
            otherwise.
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
    counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    global_map: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0

    def raise_for_status(self) -> None:
        """Raise ``JobFailedError`` unless the job finished."""
        if self.status != "success":
            raise JobFailedError(self)


class _Failed(Exception):
    """A component could not be built or run."""

    def __init__(self, component_id: Optional[str], reason: str, read_again: bool = False) -> None:
        super().__init__(reason)
        self.component_id = component_id
        self.reason = reason
        # The pass failed while a source let Polars parse numbers itself: the tolerant reader may succeed.
        self.read_again = read_again


@dataclass
class _Subjob:
    """What one subjob has built and written so far."""

    writes: List[Tuple[str, Write, List[int]]] = field(default_factory=list)
    taps: List[Tuple[str, Tap]] = field(default_factory=list)
    produced: List[Tuple[str, pl.LazyFrame]] = field(default_factory=list)
    written: List[Tuple[str, Write, str, int]] = field(default_factory=list)
    temps: List[str] = field(default_factory=list)


class Runner:
    """Runs one loaded job.

    Args:
        job: The loaded job.
        engine: The Polars engine to collect with.
        routines: Routine modules available to expressions.
        row_counts: Whether the rows of every component are counted and
            logged. Without it only the counts something in the job reads
            are taken, because every count is one more plan Polars works
            through.
    """

    def __init__(
        self,
        job: Job,
        engine: Optional[str] = None,
        routines: Optional[Mapping[str, Mapping[str, Callable[..., Any]]]] = None,
        row_counts: bool = False,
    ) -> None:
        self.job = job
        self.engine = engine or os.environ.get("V2_ENGINE") or DEFAULT_ENGINE
        self.run_context = RunContext(job.name, job.context, routines or job.routine_modules, job.context_types)
        self.rows: Dict[str, int] = {}
        self.row_counts = row_counts
        self.counts: Dict[str, Dict[str, int]] = {}
        self.run_context.job_text = _job_text(job)
        self._wanted = _wanted_stats(job, self.run_context.job_text)
        if row_counts:
            self._wanted = {component_id: list(_STATS) for component_id in job.components}

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
        result.counts = dict(self.counts)
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
        for trigger in self.job.triggers:
            leaving.setdefault(subjob_of[trigger.source], []).append(trigger)
            triggered.add(subjob_of[trigger.target])

        queue: Deque[int] = deque(index for index in range(len(plan)) if index not in triggered)
        done: Set[int] = set()
        set_off: Set[int] = set()
        while queue:
            index = queue.popleft()
            if index in done:
                continue
            done.add(index)
            failure = self._run_subjob(plan[index])
            if failure is not None:
                self._record(result, failure.component_id, failure.reason)
            try:
                following = self._fired(plan[index], leaving.get(index, []), failure, subjob_of, done, set_off)
            except ConfigurationError as exc:
                self._record(result, None, str(exc))
                return
            queue.extendleft(reversed(following))

    def _fired(
        self,
        members: List[str],
        triggers: List[Trigger],
        failure: Optional[_Failed],
        subjob_of: Dict[str, int],
        done: Set[int],
        set_off: Set[int],
    ) -> List[int]:
        """The subjobs a finished subjob sets off, in the order v1 sets them off.

        v1 runs a subjob one component at a time. A component's own triggers
        (OnComponentOk, OnComponentError, RunIf) fire when it is done, and
        the subjob's (OnSubjobOk, OnSubjobError) with its last component, or
        with the one that failed; what fires together goes by ``order``. A
        RunIf is judged there on what globalMap held at that moment. A
        subjob is set off this way only once in a job.

        When the subjob is done, v1 goes through its subjob triggers and its
        RunIf triggers once more, in the order the job lists them, and sets
        off every subjob that has not run yet. That is where a condition on
        a count of a later component of the same subjob fires.

        Args:
            members: The subjob's components, in the order they run.
            triggers: The triggers leaving the subjob, as the job lists them.
            failure: What failed in the subjob, if anything did.
            subjob_of: Component id to the index of its subjob.
            done: The subjobs that have run.
            set_off: The subjobs a component's turn has set off, in the whole job.
        """
        context, global_map = self.run_context.context, self.run_context.global_map
        by_order = sorted(triggers, key=lambda trigger: trigger.order)
        closing = members[-1]
        if failure is not None and failure.component_id in members:
            closing = failure.component_id
        following: List[int] = []
        for position, component_id in enumerate(members):
            seen: Optional[Mapping[str, Any]] = None
            for trigger in by_order:
                target = subjob_of[trigger.target]
                if target in set_off:
                    continue
                judged = None
                if trigger.kind == "OnSubjobOk":
                    fires = failure is None and component_id == closing
                elif trigger.kind == "OnSubjobError":
                    fires = failure is not None and component_id == closing
                elif trigger.source != component_id:
                    fires = False
                elif trigger.kind == "OnComponentOk":
                    fires = failure is None
                elif trigger.kind == "OnComponentError":
                    fires = failure is not None and failure.component_id == component_id
                else:
                    if seen is None:
                        seen = _before(global_map, members[position + 1:], self.job.components)
                    fires = evaluate(trigger.condition, context, seen)
                    judged = f"{component_id} was done"
                self._say(trigger, fires, judged)
                if fires:
                    set_off.add(target)
                    following.append(target)

        for trigger in triggers:
            target = subjob_of[trigger.target]
            if target in done or target in following:
                continue
            judged = None
            if trigger.kind == "OnSubjobOk":
                fires = failure is None
            elif trigger.kind == "OnSubjobError":
                fires = failure is not None
            elif trigger.kind == "RunIf":
                fires = evaluate(trigger.condition, context, global_map)
                judged = "the subjob was done"
            else:
                fires = False
            self._say(trigger, fires, judged)
            if fires:
                following.append(target)
        return following

    def _say(self, trigger: Trigger, fires: bool, judged: Optional[str]) -> None:
        """Log a trigger that fired, and a RunIf every time it was judged, whatever it came to.

        Args:
            trigger: The trigger.
            fires: Whether it sets its subjob off.
            judged: For a RunIf, the moment its condition was looked at; None for any other trigger.
        """
        ends = f"[{self.job.name}] trigger {trigger.kind} from {trigger.source} to {trigger.target}"
        sets_off = f"the subjob of {trigger.target} is set off"
        if judged is not None:
            came_to = f"{ends}, judged when {judged}: {trigger.condition or ''} is {str(fires).lower()}"
            logger.info(_one_line(f"{came_to}: {sets_off}" if fires else came_to))
        elif fires:
            logger.info(_one_line(f"{ends} fired: {sets_off}"))

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
        """Build and run one subjob. Returns the failure, or None when it finished.

        Sources first let Polars parse numbers itself, which is the fast
        way and fails on a value only the tolerant reader takes. The subjob
        is then run once more with the tolerant reader. That is safe as long
        as nothing in the subjob has acted on rows yet, so a subjob holding
        a component that needs rows in hand starts with the tolerant reader.
        """
        holding = [component_id for component_id in component_ids if self.job.components[component_id].cls.may_need_rows]
        self.run_context.fast_read = not holding and not os.environ.get("V2_SAFE_READ")
        if logger.isEnabledFor(logging.DEBUG):
            how = (
                "sources may let Polars parse numbers itself in this subjob: "
                "nothing in it needs rows in hand, so it can be read a second time"
            )
            if holding:
                how = (
                    f"sources read every column as text in this subjob: {', '.join(holding)} may need rows "
                    "in hand, so the subjob cannot be read a second time"
                )
            elif not self.run_context.fast_read:
                how = "sources read every column as text in this subjob: V2_SAFE_READ is set"
            logger.debug(ascii_only(f"[{self.job.name}] {how}"))
        try:
            failure = self._attempt(component_ids)
            if failure is not None and failure.read_again:
                logger.info(
                    f"[{self.job.name}] a file holds values the fast reader does not take ({failure.reason}); "
                    "reading again with the tolerant reader"
                )
                if logger.isEnabledFor(logging.DEBUG):
                    said = f"[{self.job.name}] what the fast reader said, in full:\n{failure.__cause__}"
                    logger.debug(ascii_only(said))
                self.run_context.fast_read = False
                failure = self._attempt(component_ids)
        finally:
            # No plan outlives its subjob, so neither do the scratch files it read through.
            self.run_context.cleanup()
        return failure

    def _attempt(self, component_ids: List[str]) -> Optional[_Failed]:
        """Build and run one subjob once."""
        state = _Subjob()
        self.run_context.used_fast_read = False
        self.run_context.dropped.clear()
        started = time.perf_counter()
        logger.info(f"[{self.job.name}] subjob starting: {', '.join(component_ids)}")
        try:
            self._build(component_ids, state)
            self._collect([], state)
            self._place(state)
        except _Failed as failure:
            _discard(state)
            return failure
        except BaseException:
            # A run that is stopped (Ctrl-C) leaves no file half written either.
            _discard(state)
            raise
        self._say_dropped()
        if self.row_counts:
            self._say_counts(component_ids)
        logger.info(f"[{self.job.name}] subjob finished in {time.perf_counter() - started:.2f}s")
        return None

    def _say_dropped(self) -> None:
        """Warn of the rows that components dropped for a fault in a subjob that finished.

        Said only now: a subjob that fails writes nothing, and so has dropped nothing.
        """
        for component_id, said in self.run_context.dropped:
            logger.warning(ascii_only(f"[{component_id}] {said}"))
        self.run_context.dropped.clear()

    def _say_counts(self, component_ids: List[str]) -> None:
        """Keep and log the row counts of a subjob that finished, component by component, as v1 words them."""
        global_map = self.run_context.global_map
        for component_id in component_ids:
            counted = {stat: global_map[f"{component_id}_{stat}"] for stat in _STATS}
            self.counts[component_id] = counted
            logger.info(ascii_only(
                f"[{component_id}] NB_LINE:{counted['NB_LINE']} OK:{counted['NB_LINE_OK']} "
                f"REJECT:{counted['NB_LINE_REJECT']}"
            ))

    def _build(self, component_ids: List[str], state: _Subjob) -> None:
        frames: Dict[str, pl.LazyFrame] = {}
        for component_id in component_ids:
            spec = self.job.components[component_id]
            try:
                component = self._ready(spec)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(ascii_only(f"[{component_id}] config: {json.dumps(component.config, default=str)}"))
                inputs = {flow.name: frames[flow.name] for flow in self.job.incoming(component_id)}
                if isinstance(component, Sink):
                    heights: List[int] = []
                    # A file holds the job's own columns and nothing of the engine's.
                    handed = _counted(without(next(iter(inputs.values()))), heights)
                    state.writes.append((component_id, component.write(handed), heights))
                    outputs: Dict[str, pl.LazyFrame] = {}
                elif isinstance(component, Source):
                    outputs = component.read()
                    self.run_context.sources[component_id] = component
                elif component.needs_rows():
                    collected = self._collect(list(inputs.values()), state, component_id)
                    for name, frame in zip(inputs, collected):
                        self._share(name, frame.lazy(), frames)
                    if not component.sees_hidden_columns:
                        collected = [frame.select(visible(frame.columns)) for frame in collected]
                    results = component.run(dict(zip(inputs, collected))) or {}
                    # Counted from the rows in hand: the plans that made them are not run again for it.
                    inputs = {name: frame.lazy() for name, frame in zip(inputs, collected)}
                    outputs = {port: frame.lazy() for port, frame in results.items()}
                else:
                    if not component.sees_hidden_columns:
                        inputs = {name: without(frame) for name, frame in inputs.items()}
                    outputs = component.build(inputs)
                left = component.unchecked()
                if left:
                    raise RuntimeError(
                        f"conversions were translated and never checked (check_conversions): {'; '.join(left)}"
                    )
                outputs = self._conformed(component, outputs)
                for port, frame in outputs.items():
                    columns = frame.collect_schema()
                    if logger.isEnabledFor(logging.DEBUG):
                        shown = ", ".join(f"{name} {columns[name]}" for name in visible(columns))
                        logger.debug(ascii_only(f"[{component_id}] output {port}: {shown}"))
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
        component = spec.cls(spec, config, self.run_context)
        component.wired = {flow.port for flow in self.job.outgoing(spec.id)}
        return component

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
                broken = main.filter(violation.is_not_null())
                component.check(
                    broken.select(pl.len().alias("rows"), violation.first().alias("why"), *first_of(broken)),
                    lambda found: _null_problem(found, component),
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
                component.tell_dropped(broken, violation)
            outputs["main"] = main
        if "reject" in outputs and spec.reject_schema and component.conforms:
            columns = [dataclasses.replace(column, nullable=True) for column in spec.reject_schema]
            outputs["reject"], _ = conform(outputs["reject"], columns)
        return outputs

    def _count(self, component: Component, inputs: Dict[str, pl.LazyFrame], outputs: Dict[str, pl.LazyFrame]) -> None:
        """Count the rows of a component whose counts something in the job reads, or the run asked for."""
        wanted = self._wanted.get(component.id)
        if not wanted or isinstance(component, Sink):
            return
        counted = component.line_counts(inputs, outputs)
        global_map = self.run_context.global_map
        for stat in wanted:
            key = f"{component.id}_{stat}"
            global_map[key] = 0
            for frame in counted.get(stat, []):
                component.tap(_row_count(frame), lambda rows, key=key: _add(global_map, key, rows.item()))

    # ------------------------------------------------------------------
    # Collecting and placing files
    # ------------------------------------------------------------------

    def _collect(
        self, wanted: List[pl.LazyFrame], state: _Subjob, handed_to: Optional[str] = None
    ) -> List[pl.DataFrame]:
        """Run pending writes and taps and collect wanted frames, all in one pass.

        Args:
            wanted: Frames to collect and return.
            state: What the subjob has built so far.
            handed_to: Id of the component the wanted frames are collected for.
        """
        writes, taps = state.writes, state.taps
        state.writes, state.taps = [], []
        if not wanted and not writes and not taps:
            return []
        temps = [_temp_path(write.path, component_id) for component_id, write, _ in writes]
        state.temps += temps
        started = time.perf_counter()
        try:
            plans = [write.sink(temp) for (_, write, _), temp in zip(writes, temps)]
            plans += [tap.frame for _, tap in taps]
            if logger.isEnabledFor(logging.DEBUG):
                for (component_id, _, _), temp in zip(writes, temps):
                    logger.debug(ascii_only(f"[{component_id}] writing to the temporary file {temp}"))
                named = [f"output {component_id}" for component_id, _, _ in writes]
                named += [f"what {component_id} asked to know" for component_id, _ in taps]
                named += [f"the rows {handed_to} is handed"] * len(wanted)
                for name, plan in zip(named, plans + wanted):
                    logger.debug(ascii_only(f"[{self.job.name}] plan of {name}:{_given(plan)}"))
            results = pl.collect_all(plans + wanted, engine=self.engine)
        except Exception as exc:  # noqa: BLE001 -- Polars reports data problems in many types
            if self.run_context.fast_read and self.run_context.used_fast_read:
                raise _Failed(None, _reason(exc), read_again=True) from exc
            blamed = None
            if time.perf_counter() - started <= BLAME_BUDGET_S:
                blamed = self._blame(state.produced) or (writes[0][0] if len(writes) == 1 else None)
            raise _Failed(blamed, _reason(exc)) from exc

        first_tap, first_wanted = len(writes), len(plans)
        for (component_id, write, heights), temp in zip(writes, temps):
            state.written.append((component_id, write, temp, sum(heights)))
        for (component_id, tap), frame in zip(taps, results[first_tap:first_wanted]):
            try:
                tap.receive(frame)
            except CheckFailed as problem:
                raise _Failed(component_id, str(problem)) from problem
            except Exception as exc:  # noqa: BLE001
                raise _Failed(component_id, _reason(exc)) from exc
        return results[first_wanted:]

    def _place(self, state: _Subjob) -> None:
        """Put every file the subjob wrote in place.

        Each file is first made ready where it was written. That is the
        last thing the rows can fail (a character the file's encoding cannot
        write), and it is done for every file before any is put in place:
        a subjob that fails leaves every file as it was. Then the files are
        moved, in the order their components run.
        """
        left: Set[str] = set()
        for component_id, write, temp, rows in state.written:
            try:
                where = os.path.realpath(write.path)
                if write.refuses_existing is not None and where in left:
                    raise ConfigurationError(write.refuses_existing)
                if write.ready is not None:
                    write.ready(temp, rows)
                if rows or not write.empty_leaves_none:
                    left.add(where)
            except Exception as exc:  # noqa: BLE001
                raise _Failed(component_id, _reason(exc)) from exc

        while state.written:
            component_id, write, temp, rows = state.written.pop(0)
            try:
                if write.place is not None:
                    write.place(temp, rows)
                else:
                    put_in_place(temp, write.path, write.append)
                self.rows[component_id] = self.rows.get(component_id, 0) + rows
                self.run_context.global_map[f"{component_id}_NB_LINE"] = self.rows[component_id]
                for stat in self._wanted.get(component_id, ()):
                    self.run_context.global_map[f"{component_id}_{stat}"] = (
                        0 if stat == "NB_LINE_REJECT" else self.rows[component_id]
                    )
                if write.finish is not None:
                    write.finish(rows)
                logger.info(f"[{component_id}] wrote {rows} row(s) to {write.path}")
            except Exception as exc:  # noqa: BLE001
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

def _job_text(job: Job) -> str:
    """Every text of a job config that could name a globalMap entry: config values and trigger conditions."""
    texts: List[str] = [trigger.condition or "" for trigger in job.triggers]
    for spec in job.components.values():
        _strings(spec.raw_config, texts)
    return "\n".join(texts)


def _wanted_stats(job: Job, everything: str) -> Dict[str, List[str]]:
    """The row counts something in the job reads: component id to stat names."""
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


def _before(global_map: Mapping[str, Any], later: List[str], everyone: Iterable[str]) -> Mapping[str, Any]:
    """globalMap as v1 has it before some components of a subjob have run: without what is theirs.

    An entry is a component's when its key starts with the component's id
    and an underscore; of two ids that fit, the longer one owns it.
    """
    if not later:
        return global_map
    ids = sorted(everyone, key=len, reverse=True)
    hidden = set(later)
    kept: Dict[str, Any] = {}
    for key, value in global_map.items():
        owner = next((component_id for component_id in ids if key.startswith(component_id + "_")), None)
        if owner not in hidden:
            kept[key] = value
    return kept


def _row_count(frame: pl.LazyFrame) -> pl.LazyFrame:
    """A frame of one value: how many rows a frame holds.

    The rows are numbered and the highest number is taken. Asking Polars for
    the number outright (``select(pl.len())``) is wrong on Polars 1.44 for
    frames put one after another and then cut (``concat`` under ``slice`` or
    ``head``): it counts each frame on its own and cuts the list of counts,
    not the rows.
    """
    highest = frame.with_row_index(_ROW_NUMBER).select(pl.col(_ROW_NUMBER).max().cast(pl.Int64))
    return highest.select((pl.col(_ROW_NUMBER) + 1).fill_null(0))


def _add(global_map: Dict[str, Any], key: str, rows: int) -> None:
    global_map[key] = global_map.get(key, 0) + int(rows)


def _null_problem(found: pl.DataFrame, component: Component) -> Optional[str]:
    """v1's words for a missing value in a column that may not hold one, and the row it was."""
    if not found["rows"].item():
        return None
    named = _NULL_COLUMN.fullmatch(found["why"].item() or "")
    column = named.group(1) if named else "?"
    return f"Column '{column}' has NULL values but is not nullable{component.where(found)}"


def _temp_path(path: str, component_id: str) -> str:
    """Where a component's file is written before it is put in place: beside its target.

    The component's id is part of the name, so two components writing to one
    file in the same subjob do not write over each other.
    """
    folder, name = os.path.split(path)
    safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in component_id)
    return os.path.join(folder, f".{name}.{safe}.v2tmp{os.getpid()}")


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _counted(frame: pl.LazyFrame, heights: List[int]) -> pl.LazyFrame:
    """A frame that notes the height of every batch of rows that passes through it.

    That is how the rows handed to a sink are counted: in the pass that
    writes them, at no cost. A second frame over the same rows can make
    Polars read the source twice, and the lines of the written file are not
    its rows when a value holds a line break.
    """
    def note(batch: pl.DataFrame) -> pl.DataFrame:
        # Batches arrive from several threads; adding to a list is safe from all of them.
        heights.append(batch.height)
        return batch

    return frame.map_batches(note, streamable=True, validate_output_schema=False)


def _one_line(text: str) -> str:
    """A text as one line of plain ASCII, for the log."""
    return ascii_only(" ".join(text.split()))


def _given(plan: pl.LazyFrame) -> str:
    """A plan as Polars is given it, on lines of its own, for the log.

    Printing a plan is for the reader of the log only: where Polars cannot
    print one, the log says so and the job goes on.
    """
    try:
        return "\n" + plan.explain(optimized=False)
    except Exception as exc:  # noqa: BLE001 -- whatever stops the printing must not stop the job
        return f" Polars could not print it ({_reason(exc)})"


def _discard(state: _Subjob) -> None:
    """Remove what a subjob that did not finish wrote and has not put in place."""
    for temp in state.temps:
        _remove(temp)


def _reason(error: BaseException) -> str:
    """One line of plain ASCII saying what went wrong."""
    text = " ".join(str(error).split())
    for marker in (" Resolved plan until failure", " You might want to try:"):
        text = text.split(marker)[0]
    # Polars spells microseconds with a Greek letter; logs must stay ASCII.
    text = text.replace("\u03bc", "u").replace("\u00b5", "u")
    text = text.encode("ascii", "replace").decode("ascii")
    if "CSV malformed" in text or ("could not parse" in text and "as dtype `str`" in text):
        # Text always reads as text: what Polars could not read here is an enclosure.
        text += " (with csv_option, an enclosure character must open and close a field; this file has one that does not)"
    return text or type(error).__name__
