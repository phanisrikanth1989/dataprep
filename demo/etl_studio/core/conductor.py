"""Conductor: the deterministic control layer -- the hub (ticket 05's code
conductor, built by ticket 16 on the ticket 10/15 skeleton).

The conductor computes every transition: ticket 04's fixed itinerary for
both doors, the loop counters and 3-caps (shape-repair, main repair with
uncapped human grants, the elicitation round budget; the configurator's
inner validate loop is its own counter reported through the stage context),
the diagnostician's owner-plus-forward rule, tier routing (only ``verified``
loops; ``smoke`` runs exactly once; ``build`` never runs), gate raising, and
artifact moves on the bus. It records the human's resolutions untouched --
no model in the return path -- and cannot improvise: on anything unplanned
it stops and asks (propose-confirm), never silently acts.

It is code, never a speaker. The speaking layer is ticket 18's LLM
orchestrator (core/orchestrator.py): the conductor enqueues narration at
fixed moments (non-blocking -- the walk never waits on prose), routes
composer messages to it, and hands it unplanned failures to explain; the
machine-truth events (run/stage/question/health) are conductor-authored
forever, and the return path (answers, approvals) never passes through the
model.

Crash-restore: the bus owns the artifacts, ``audit.jsonl`` owns the
decisions, and the UI journal owns the event sequence. On boot the
conductor re-walks its deterministic itinerary with every emission
journal-guarded (count-based ledgers for artifacts, streams and loop
attempts; key-based for stages and questions), so a restarted core
continues mid-run without replaying traffic the webview already saw,
and seq continuity comes from the journal itself (ticket 08).

Ticket 13 verbs, all conductor-owned: directed iteration (owner interpret =
spec door, owner configure = code door -- the raising surface fixes the
door, the conductor never routes by reading text); hold armed at the next
stage boundary (in-flight artifacts land whole; no mid-stream cancel);
steer always routes to the interpreter; stop ends the run plainly; every
human-initiated act is uncapped and burns no loop budget.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .bus import ArtifactBus
from .llm import LlmCallError, StreamRunner
from .models import ModelConfig
from .orchestrator import Orchestrator
from .port import ModelInfo, ProviderPort
from .questions import QuestionChannel
from .real_stages import LIVE_SLOTS
from .stages import RunInfo, StageAdapter, StageContext, StageResult
from .vendored.surface_code_cells import surface_code_cells

logger = logging.getLogger(__name__)

Emit = Callable[[str, str, Dict[str, Any]], Awaitable[None]]

# The UI itinerary (ticket 04's spine at webview resolution -- the BRD
# door's explode/normalize chain lives inside "intake", the test-runner/
# diagnostician repair loop inside "verify").
ITINERARY: List[Dict[str, str]] = [
    {"kind": "stage", "key": "intake", "label": "Intake"},
    {"kind": "stage", "key": "interpret", "label": "Interpret"},
    {"kind": "gate", "key": "spec", "label": "Spec sign-off"},
    {"kind": "stage", "key": "design", "label": "Design"},
    {"kind": "stage", "key": "configure", "label": "Configure"},
    {"kind": "stage", "key": "assemble", "label": "Assemble"},
    {"kind": "gate", "key": "code", "label": "Code gate"},
    {"kind": "stage", "key": "verify", "label": "Verify"},
    {"kind": "gate", "key": "human", "label": "Human gate"},
]
STAGE_LABELS = {e["key"]: e["label"] for e in ITINERARY}
STAGE_ORDER = [e["key"] for e in ITINERARY if e["kind"] == "stage"]

SHAPE_REPAIR_CAP = 3
REPAIR_CAP = 3  # total run attempts in the verified loop before exhaustion
GRANT_SIZE = 3
ELICITATION_ROUNDS = 3

# feedback.json owner enum (04). Anything outside it routes to the human,
# never to a guessed stage (fail-closed: "anything you cannot confidently
# classify -> human" is enforced here, not just prompted).
_OWNER_ENUM = frozenset(
    {"interpreter", "flow-designer", "configurator", "assembler", "human"})
# Owner -> stage-adapter slot; the design-side chain order drives the
# owner+forward rule (04: the owner re-runs reading feedback.json first,
# then every forward stage, as quiet repair passes).
_OWNER_SLOT = {
    "configurator": "configure",
    "flow-designer": "design",
    "assembler": "assemble",
}
_REPAIR_CHAIN = ["design", "configure", "assemble"]


# ---------------------------------------------------------------------------
# Control-flow signals
# ---------------------------------------------------------------------------


class _Stopped(Exception):
    def __init__(self, note: str):
        self.note = note


class _StopToGate(Exception):
    """Exhaustion's 'stop to the gate': dispose of the red verdict at the
    human gate (distinct from stopping the run)."""


class _DirectedIteration(Exception):
    """One primitive under every human-driven revision (ticket 13):
    the owner stage re-runs reading the feedback first, then every
    completed forward stage."""

    def __init__(self, owner: str, feedback: str):
        self.owner = owner  # "interpret" | "configure"
        self.feedback = feedback


# ---------------------------------------------------------------------------
# The conductor
# ---------------------------------------------------------------------------


class Conductor:
    def __init__(
        self,
        emit: Emit,
        port: ProviderPort,
        provider_name: str,
        run_id: str,
        job: str,
        door: str,
        request: Dict[str, Any],
        run_dir: Path,
        stages: Dict[str, StageAdapter],
        model_config: Optional[ModelConfig] = None,
        pace: float = 1.0,
        live_port: Optional[ProviderPort] = None,
        live_provider: str = "",
    ):
        self._emit = emit
        self._port = port
        self._provider = provider_name
        # Tickets 17/18/19: every LLM slot's stream routes here when a live
        # provider resolved (LIVE_SLOTS), except slots the rig's
        # scripted_slots pins to the double (the live-probe affordance).
        self._live_port = live_port
        self._live_provider = live_provider
        self.run_id = run_id
        self._stages_impl = stages
        self._models = model_config or ModelConfig()
        self._pace = pace

        rig = dict(request.get("rig") or {})
        self.run = RunInfo(run_id=run_id, job=job, door=door, request=dict(request), rig=rig)
        self.run.data_present = bool(request.get("attachments"))

        self.bus = ArtifactBus(run_dir)
        self.questions = QuestionChannel(emit, audit=self.bus.audit, feed=self._feed)
        self._runner = StreamRunner(emit, port, provider_name, run_id, pace=pace,
                                    live_port=live_port, live_provider=live_provider)
        self._roster: List[ModelInfo] = []
        self._live_roster: List[ModelInfo] = []
        self._model_map: Optional[Dict[str, Optional[ModelInfo]]] = None

        self._task: Optional[asyncio.Task] = None
        self._side_tasks: List[asyncio.Task] = []

        # Journal-guarded emission ledgers (restore fills the *_journal side;
        # the deterministic re-walk consumes them count-wise).
        self._artifact_journal: Dict[str, int] = {}
        self._artifact_calls: Dict[str, int] = {}
        self._loop_journal: Dict[str, int] = {}
        self._loop_calls: Dict[str, int] = {}
        self._closed_streams: Dict[str, int] = {}

        self._iter: Dict[str, int] = {k: 1 for k in STAGE_ORDER}
        self._done_stages: set = set()  # (key, iteration)
        self._started = False
        self.ended = False

        # Counters and verbs.
        self._draft = 1
        self._code_round = 1
        self._human_round = 1
        self._pc_count = 0
        self._hold_count = 0
        self._nh_count = 0
        self._oh_count = 0
        self._x_count = 0
        self._armed: Optional[str] = None  # "hold" | "stop"
        self._stretch_active = False
        self._directed_owner: Optional[str] = None
        self._pending_gaps: List[Dict[str, Any]] = []
        self._approved_cells: set = set()  # sha1(component|field|code)
        self._raised_cells: set = set()  # (component, field) ever gated
        self._signed_spec_sig: Optional[str] = None
        self._grants = 0
        self._verdict: Dict[str, Any] = {}

        # The orchestrator context feed (ticket 05): one compact line per
        # machine event, rebuilt from bus + audit after a crash. The
        # orchestrator agent (ticket 18) consumes it turn by turn.
        self._orch_feed: List[Dict[str, str]] = []
        self.orch = Orchestrator(self)

    # ---- lifecycle -----------------------------------------------------------

    @property
    def active(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        self._task = asyncio.get_running_loop().create_task(self._run())

    def dispose(self) -> None:
        self.orch.dispose()
        for t in [self._task, *self._side_tasks]:
            if t is not None and not t.done():
                t.cancel()

    def resume(self) -> None:
        """Continue an un-ended run after crash-restart (run.crash_restored
        already emitted by the app)."""
        for qid, q in self.questions.raised.items():
            if self.questions.is_pending(qid) and q.get("kind") == "propose_confirm":
                self._spawn_side(self._await_proposal(qid))
        self._task = asyncio.get_running_loop().create_task(self._run())

    # ---- restore (bus + audit own the state; the journal owns the seq) --------

    def restore(self, events: List[Dict[str, Any]]) -> None:
        # The audited run_started entry is the request of record: the door
        # and rig knobs must re-walk exactly as they first ran.
        for entry in self.bus.audit_entries():
            if entry.get("event") != "run_started":
                continue
            detail = entry.get("detail") or {}
            if detail.get("door"):
                self.run.door = str(detail["door"])
            if isinstance(detail.get("request"), dict):
                self.run.request = dict(detail["request"])
                self.run.rig = dict(self.run.request.get("rig") or {})
                self.run.data_present = bool(self.run.request.get("attachments"))
            break
        for env in events:
            t, p = env.get("type", ""), env.get("payload", {}) or {}
            if t == "run.started":
                self._started = True
            elif t == "run.ended":
                self.ended = True
            elif t == "stage.completed":
                self._done_stages.add((p.get("stage", ""), int(p.get("iteration", 1))))
            elif t == "stage.artifact_written":
                name = str(p.get("name", ""))
                self._artifact_journal[name] = self._artifact_journal.get(name, 0) + 1
            elif t == "stage.loop_attempt":
                stage = str(p.get("stage", ""))
                self._loop_journal[stage] = self._loop_journal.get(stage, 0) + 1
            elif t == "question.raised":
                self.questions.restore_raised(p)
                kind = p.get("kind")
                if kind == "spec_gate":
                    self._draft = max(self._draft, int(p.get("draft", 1)))
                elif kind == "code_gate":
                    self._code_round = max(self._code_round, int(p.get("round", 1)))
                elif kind == "human_gate":
                    self._human_round = max(self._human_round, int(p.get("round", 1)))
                elif kind == "propose_confirm":
                    self._pc_count = max(self._pc_count, int(p.get("n", 0)))
                elif kind == "hold":
                    self._hold_count = max(self._hold_count, int(p.get("n", 0)))
                elif kind == "needs_human":
                    self._nh_count = max(self._nh_count, int(p.get("n", 0)))
                elif kind == "owner_human":
                    self._oh_count = max(self._oh_count, int(p.get("n", 0)))
                elif kind == "exhaustion":
                    self._x_count = max(self._x_count, int(p.get("x_n", 0)))
            elif t == "question.resolved":
                self.questions.restore_resolved(p)
            elif t == "stream.close":
                label = p.get("label")
                if label and p.get("finish_reason") in ("stop", "unknown", "canceled"):
                    self._closed_streams[label] = self._closed_streams.get(label, 0) + 1
        self._runner = StreamRunner(
            self._emit, self._port, self._provider, self.run_id,
            pace=self._pace, closed_streams=self._closed_streams,
            live_port=self._live_port, live_provider=self._live_provider,
        )
        # A confirmed hold/stop proposal whose hold question never raised re-arms.
        for qid, res in self.questions.resolved.items():
            q = self.questions.raised.get(qid, {})
            if q.get("kind") == "propose_confirm" and res.get("choice") == "confirm":
                later_hold = any(
                    k.startswith("q-hold-")
                    and self.questions.raised[k].get("after_pc") == qid
                    for k in self.questions.raised
                )
                if not later_hold and not self.ended:
                    self._armed = q.get("proposal", "hold")
        # Grants are human acts: re-derive from resolutions, never counted twice.
        self._grants = sum(
            1 for qid, res in self.questions.resolved.items()
            if self.questions.raised.get(qid, {}).get("kind") == "exhaustion"
            and res.get("choice") == "grant"
        )
        # Data presence: the request, the intake artifact, or a G0 attach answer.
        intake = self.bus.read_json("intake.json") or {}
        if intake.get("attachments") or intake.get("tables"):
            self.run.data_present = True
        for qid, res in self.questions.resolved.items():
            q = self.questions.raised.get(qid, {})
            if q.get("kind") == "gap" and q.get("gap_id") == "G0" \
                    and res.get("choice") in ("attach", "other"):
                self.run.data_present = True
                paths = [s.strip() for s in str(res.get("free_text") or "").split(",")
                         if s.strip()]
                self.run.request.setdefault("attachments", []).extend(paths)
        # Conductor decisions from the audit trail (05: restore from bus+audit).
        for entry in self.bus.audit_entries():
            event = entry.get("event")
            detail = entry.get("detail") or {}
            if event == "cells_approved":
                for h in detail.get("hashes", []):
                    self._approved_cells.add(str(h))
            elif event == "cells_raised":
                for cf in detail.get("cells", []):
                    if isinstance(cf, list) and len(cf) == 2:
                        self._raised_cells.add((cf[0], cf[1]))
            elif event == "tier_frozen":
                self.run.tier = detail.get("tier")
            elif event == "spec_signed":
                self._signed_spec_sig = detail.get("signature")
        self.bus.restore_index()
        self._rebuild_orch_feed()
        # Bump stage iterations past completed directed re-runs so the step
        # loop's skip logic lands on the first unfinished iteration.
        for key in STAGE_ORDER:
            while (key, self._iter[key]) in self._done_stages:
                nxt = (key, self._iter[key] + 1)
                started_next = nxt in self._done_stages or self._journal_stage_started(
                    events, *nxt
                )
                if started_next:
                    self._iter[key] += 1
                else:
                    break
        self.run.draft = self._draft
        self.run.gap_resolutions = self._gap_resolutions()
        # needs_human answers re-derive from the resolved questions (17): the
        # re-walked normalizer passes get the same fold-in prompt they had.
        for qid in sorted(self.questions.resolved):
            q = self.questions.raised.get(qid, {})
            if q.get("kind") != "needs_human":
                continue
            res = self.questions.resolved[qid]
            self.run.nh_resolutions.append({
                "source": q.get("source", "normalize_validate"),
                "prompt": q.get("prompt", ""),
                "choice": res.get("choice"),
                "free_text": res.get("free_text"),
            })
        if self._code_round > 1:
            self.run.rig["_cell_revised"] = True

    @staticmethod
    def _journal_stage_started(events: List[Dict[str, Any]], key: str, iteration: int) -> bool:
        return any(
            e.get("type") == "stage.started"
            and (e.get("payload") or {}).get("stage") == key
            and int((e.get("payload") or {}).get("iteration", 1)) == iteration
            for e in events
        )

    def _rebuild_orch_feed(self) -> None:
        """The orchestrator's context feed rebuilt from audit + bus
        (ticket 05: after a crash the conductor rebuilds the orchestrator's
        context; ticket 18 consumes this)."""
        self._orch_feed = []
        for entry in self.bus.audit_entries():
            event = str(entry.get("event", ""))
            detail = entry.get("detail") or {}
            if event == "artifact_written":
                text = f"artifact {detail.get('name')} ({detail.get('kind')})"
                if detail.get("note"):
                    text += f" -- {detail['note']}"
            elif event == "question_raised":
                text = f"question raised: {detail.get('kind')} {detail.get('question_id')}"
            elif event == "question_resolved":
                text = f"human resolved {detail.get('question_id')}: {detail.get('choice')}"
            elif event in ("run_started", "run_ended", "stage_started", "stage_completed",
                           "tier_frozen", "grant", "loop_attempt", "hold_armed",
                           "directed_iteration", "data_attached", "spec_signed",
                           "verdict"):
                text = f"{event}: {json.dumps(detail, ensure_ascii=True)}"
            else:
                continue
            self._orch_feed.append({"kind": event, "text": text})

    def orchestrator_context(self) -> List[Dict[str, str]]:
        return list(self._orch_feed)

    def _feed(self, kind: str, text: str) -> None:
        self._orch_feed.append({"kind": kind, "text": text})

    # ---- emission helpers (journal-guarded) ------------------------------------

    async def _sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds * self._pace)

    async def _stage_started(self, key: str, **extra: Any) -> None:
        it = self._iter[key]
        payload = {"stage": key, "label": STAGE_LABELS[key], "iteration": it, **extra}
        await self._emit("conductor", "stage.started", payload)
        self.bus.audit("conductor", "stage_started", {"stage": key}, iteration=it)
        self._feed("stage_started", f"{STAGE_LABELS[key]} started (iteration {it})")

    async def _stage_completed(self, key: str, note: Optional[str] = None) -> None:
        it = self._iter[key]
        payload: Dict[str, Any] = {"stage": key, "label": STAGE_LABELS[key], "iteration": it}
        if note:
            payload["note"] = note
        await self._emit("conductor", "stage.completed", payload)
        self._done_stages.add((key, it))
        self.bus.audit("conductor", "stage_completed",
                       {"stage": key, "note": note}, iteration=it)
        self._feed("stage_completed",
                   f"{STAGE_LABELS[key]} completed" + (f" -- {note}" if note else ""))

    def _stage_done(self, key: str) -> bool:
        return (key, self._iter[key]) in self._done_stages

    async def _emit_artifact(
        self,
        name: str,
        payload: Any,
        *,
        kind: str,
        fields: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None,
        text: Optional[str] = None,
        stage: Optional[str] = None,
        iteration: int = 1,
    ) -> None:
        """Bus write + stage.artifact_written as one journal-guarded unit
        (count-based: the Nth write of a name this walk matches the Nth
        journaled event, because the walk is deterministic)."""
        self._artifact_calls[name] = self._artifact_calls.get(name, 0) + 1
        if self._artifact_journal.get(name, 0) >= self._artifact_calls[name]:
            return  # journal already holds this write (crash re-walk)
        context = {"stage": stage, "iteration": iteration, "draft": self._draft}
        if text is not None:
            self.bus.write_text(name, text, kind=kind, stage=stage,
                                iteration=iteration, note=note, context=context)
        elif payload is not None:
            self.bus.write_json(name, payload, kind=kind, stage=stage,
                                iteration=iteration, note=note, context=context)
        event: Dict[str, Any] = {"name": name, "kind": kind, "iteration": iteration}
        if stage:
            event["stage"] = stage
        if note:
            event["note"] = note
        if fields is not None:
            event["fields"] = fields
        await self._emit("conductor", "stage.artifact_written", event)
        self._feed("artifact", f"{name} written" + (f" -- {note}" if note else ""))

    async def _progress(self, node_id: str, state: str) -> None:
        await self._emit("conductor", "stage.progress",
                         {"stage": "configure", "node_id": node_id, "state": state})

    async def _loop_attempt(self, stage: str, k: int, n: int, note: str) -> None:
        self._loop_calls[stage] = self._loop_calls.get(stage, 0) + 1
        if self._loop_journal.get(stage, 0) >= self._loop_calls[stage]:
            return
        await self._emit("conductor", "stage.loop_attempt",
                         {"stage": stage, "k": k, "n": n, "note": note})
        self.bus.audit("conductor", "loop_attempt",
                       {"stage": stage, "k": k, "n": n, "note": note})
        self._feed("loop_attempt", f"{stage}: {note}")

    # ---- stage invocation --------------------------------------------------------

    def _slot_live(self, slot: str) -> bool:
        # scripted_slots (rig, dev-only -- the live-probe affordance): force
        # named slots onto the scripted port so one stage can be probed live
        # against deterministic neighbors. Never set by the webview.
        if slot in set(self.run.rig.get("scripted_slots") or []):
            return False
        return slot in LIVE_SLOTS and self._live_port is not None

    async def _models_for(self, slot: str) -> Optional[ModelInfo]:
        live = self._slot_live(slot)
        if self._model_map is None:
            try:
                self._roster = await self._port.list_models()
            except Exception as e:  # noqa: BLE001 -- selection degrades; calls surface errors
                logger.warning("list_models failed (%s); adapter defaults apply", e)
                self._roster = []
            if self._live_port is not None:
                try:
                    self._live_roster = await self._live_port.list_models()
                except Exception as e:  # noqa: BLE001
                    logger.warning("live list_models failed (%s); adapter defaults apply", e)
                    self._live_roster = []
            self._model_map = {}
        key = f"{slot}:{'live' if live else 'scripted'}"
        if key not in self._model_map:
            roster = self._live_roster if live else self._roster
            self._model_map[key] = self._models.pick(roster, slot)
        return self._model_map[key]

    async def _run_stage(
        self, slot: str, ui_stage: str, repair: Optional[Dict[str, Any]] = None
    ) -> StageResult:
        adapter = self._stages_impl.get(slot)
        if adapter is None:
            raise LlmCallError("MissingStage", f"no adapter for slot {slot}")
        ctx = StageContext(
            run=self.run,
            bus=self.bus,
            runner=self._runner,
            stage=ui_stage,
            iteration=self._iter.get(ui_stage, 1),
            model=await self._models_for(slot),
            emit_artifact=self._emit_artifact,
            emit_progress=self._progress,
            emit_loop_attempt=self._loop_attempt,
            sleep=self._sleep,
            repair=repair,
            live=self._slot_live(slot),
        )
        try:
            return await adapter.run(ctx)
        except LlmCallError as e:
            # 05: anything unplanned -> stop and ask, never silently act.
            await self._escalate_failure(slot, e)
            return await adapter.run(ctx)  # human said continue: one more try

    async def _escalate_failure(self, slot: str, e: LlmCallError) -> None:
        # 18: the orchestrator explains what it sees (awaited -- the walk is
        # already stopped on the failure); its words become the card's voice.
        # Options stay conductor-authored; the fallback line covers a
        # journal-skipped turn on a crash re-walk.
        text = await self.orch.escalate(slot, e.taxonomy, e.message)
        self._pc_count += 1
        qid = f"q-pc-{self._pc_count}"
        voice = text or (f"The {slot} call failed ({e.taxonomy}: {e.message}). "
                         f"I can stop the build here, or you dismiss this and I try once more.")
        res = await self.questions.ask(
            qid, "propose_confirm",
            {"proposal": "stop", "n": self._pc_count, "voice": voice,
             "slot": slot, "taxonomy": e.taxonomy},
            [
                {"id": "confirm", "kind": "confirm", "label": "Stop the build"},
                {"id": "dismiss", "kind": "dismiss", "label": "Try again"},
            ],
        )
        if res.get("choice") == "confirm":
            raise _Stopped(f"Stopped by you — {slot} failed ({e.taxonomy})")

    # ---- the orchestrator's read surface (ticket 18) -----------------------------

    def orchestrator_live(self) -> bool:
        return self._slot_live("orchestrator")

    async def orchestrator_model(self) -> Optional[ModelInfo]:
        return await self._models_for("orchestrator")

    def runner(self) -> StreamRunner:
        """Always the CURRENT runner -- restore() rebuilds it with the
        journal's closed-stream ledger."""
        return self._runner

    async def handle_propose_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """propose_control: the orchestrator proposes, the human confirms,
        the conductor executes (05: free to pull the cord, never to grab
        the wheel). Raises the card as a side task -- the model's turn never
        blocks on the human."""
        action = str(args.get("action", ""))
        if action not in ("hold", "stop"):
            return {"ok": False, "note": "action must be hold or stop"}
        if self.ended:
            return {"ok": False, "note": "the build already ended; nothing to " + action}
        if self._armed:
            return {"ok": False,
                    "note": f"a {self._armed} is already armed at the next boundary"}
        if not self._stretch_active:
            return {"ok": False, "note": "nothing is in flight; the build is waiting on the human"}
        self._pc_count += 1
        qid = f"q-pc-{self._pc_count}"
        voice = str(args.get("note") or "").strip() or (
            "Stop this build at the next stage boundary?" if action == "stop"
            else "Hold the build at the next stage boundary?")
        self._spawn_side(self._raise_proposal(qid, action, voice))
        return {"ok": True, "question_id": qid,
                "note": "proposal card raised -- nothing happens until the human confirms"}

    # ---- gap resolutions view ------------------------------------------------------

    def _gap_resolutions(self) -> List[Dict[str, Any]]:
        out = []
        for qid, q in self.questions.raised.items():
            if q.get("kind") != "gap":
                continue
            res = self.questions.resolved.get(qid, {})
            out.append({"gap_id": q.get("gap_id"), "note": res.get("note", "")})
        out.sort(key=lambda g: str(g.get("gap_id")))
        return out

    # ---- wire handlers ---------------------------------------------------------------

    async def handle_answer(self, params: Dict[str, Any]) -> None:
        await self.questions.resolve(params)

    async def handle_ask(self, params: Dict[str, Any]) -> None:
        ask_id = str(params.get("ask_id", ""))
        text = str(params.get("text", "")).strip()
        if not text:
            return
        # 18: conversation, never a gate -- the orchestrator's worker runs
        # the turn; a hold/stop instruction becomes its propose_control call.
        self.orch.ask(ask_id, text)

    def _spawn_side(self, coro: Awaitable[None]) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._side_tasks.append(task)
        task.add_done_callback(
            lambda t: self._side_tasks.remove(t) if t in self._side_tasks else None)

    @staticmethod
    def intent_hint(text: str) -> Optional[str]:
        """Keyword LABEL hint for a composer message (stream label + the
        double's fixture key). Whether a proposal card actually rises is the
        model's call -- live, its judgment; scripted, the label's fixture."""
        low = text.lower()
        if any(w in low for w in ("stop", "halt", "abort", "kill the run")):
            return "stop"
        if any(w in low for w in ("hold", "pause", "wait", "hang on", "slow down")):
            return "hold"
        return None

    def compose_ask_reply(self, text: str) -> str:
        """The scripted-path answer: what the scripted model says on an
        echo_prompt fixture -- deterministic and grounded in real run state
        (a live turn answers from its conversation + bus reads instead)."""
        if self.ended:
            return ("This build has ended — everything on the canvas is final. "
                    "Start a new build from the two doors whenever you’re ready.")
        done = sum(1 for k in STAGE_ORDER if (k, self._iter[k]) in self._done_stages)
        pending = self.questions.pending()
        if pending:
            kinds = {q.get("kind") for q in pending}
            if "hold" in kinds:
                where = "holding at a stage boundary — the build waits on your Resume, Stop or steer"
            elif "code_gate" in kinds:
                where = "holding at the code gate — nothing runs until you approve the cell"
            elif "human_gate" in kinds:
                where = "at the human gate — the verdict is in and the approval is yours"
            elif "spec_gate" in kinds:
                where = "at the spec sign-off — the spec is drafted and waiting for your signature"
            else:
                where = "waiting on your answers in the open question round"
            return (f"We’re {where}. {done} of {len(STAGE_ORDER)} stages are complete "
                    f"on spec draft {self._draft}. Every card on the canvas is the artifact itself.")
        label = next(
            (STAGE_LABELS[k] for k in STAGE_ORDER if (k, self._iter[k]) not in self._done_stages),
            "wrap-up",
        )
        return (f"Right now: {label}, spec draft {self._draft}, {done} of {len(STAGE_ORDER)} stages "
                f"complete. Ask about any step on the canvas — what you see there is the artifact, "
                f"not a summary.")

    async def _await_proposal(self, qid: str) -> None:
        """Re-await a pending proposal after crash-restart (payload and
        voice already journaled; ask() short-circuits on the raised qid)."""
        q = self.questions.raised.get(qid, {})
        await self._raise_proposal(qid, str(q.get("proposal", "hold")),
                                   str(q.get("voice") or ""))

    async def _raise_proposal(self, qid: str, proposal: str, voice: str) -> None:
        n = int(qid.rsplit("-", 1)[-1])
        res = await self.questions.ask(
            qid, "propose_confirm",
            {"proposal": proposal, "n": n, "voice": voice},
            [
                {"id": "confirm", "kind": "confirm",
                 "label": "Stop the build" if proposal == "stop" else "Confirm hold"},
                {"id": "dismiss", "kind": "dismiss", "label": "Dismiss"},
            ],
        )
        if res.get("choice") == "confirm":
            self._armed = proposal
            self.bus.audit("human", "hold_armed", {"proposal": proposal})

    # ---- boundaries and holds -----------------------------------------------------

    async def _boundary(self, after_key: str) -> None:
        if self._armed == "stop":
            raise _Stopped("Stopped by you — confirmed from the composer")
        if self._armed != "hold":
            return
        self._armed = None
        self._hold_count += 1
        qid = f"q-hold-{self._hold_count}"
        self._stretch_active = False
        res = await self.questions.ask(
            qid, "hold",
            {"after_stage": after_key, "after_label": STAGE_LABELS.get(after_key, after_key),
             "n": self._hold_count, "after_pc": f"q-pc-{self._pc_count}",
             "voice": f"Holding after {STAGE_LABELS.get(after_key, after_key)} — the artifact "
                      f"landed whole. Resume, stop, or steer with a note; nothing times out."},
            [
                {"id": "resume", "kind": "resume", "label": "Resume"},
                {"id": "stop", "kind": "stop", "label": "Stop the build"},
                {"id": "steer", "kind": "steer", "label": "Steer", "free": "required",
                 "placeholder": "Tell it what to change — routes to the Interpreter…"},
            ],
        )
        choice = res.get("choice")
        if choice == "stop":
            raise _Stopped("Stopped by you — from the hold")
        if choice in ("steer", "other") or (choice not in ("resume",) and res.get("free_text")):
            self.orch.narrate("steer")
            raise _DirectedIteration("interpret", str(res.get("free_text") or ""))
        self.orch.narrate("resume")

    # ---- artifacts for fetch_artifact ----------------------------------------------

    def get_artifact(self, name: str) -> Optional[Dict[str, Any]]:
        """Serve the full artifact from the bus (ticket 16 scope)."""
        meta = self.bus.meta(name)
        if meta is None and not self.bus.exists(name):
            return None
        fields = self.bus.read_json(name) if name.endswith(".json") else None
        out = dict(meta or {"name": name, "kind": "artifact", "iteration": 1})
        if fields is not None:
            out["fields"] = fields
        return out

    # ---- the run ---------------------------------------------------------------------

    async def _run(self) -> None:
        try:
            await self._walk()
        except _Stopped as s:
            self.ended = True
            self.bus.audit("conductor", "run_ended", {"status": "stopped", "note": s.note})
            await self._emit("conductor", "run.ended",
                             {"status": "stopped", "by": "you", "note": s.note})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("conductor crashed")
            self.ended = True
            self.bus.audit("conductor", "run_ended", {"status": "error"})
            await self._emit("conductor", "run.ended",
                             {"status": "error",
                              "note": "the conductor hit an internal error"})

    async def _walk(self) -> None:
        steps: List[Callable[[], Awaitable[None]]] = [
            self._s_open, self._s_intake, self._s_interpret, self._s_gaps,
            self._s_spec_gate, self._s_golden, self._s_design, self._s_configure,
            self._s_assemble, self._s_code_gate, self._s_verify, self._s_human_gate,
        ]
        rewind = {
            "interpret": steps.index(self._s_interpret),
            "configure": steps.index(self._s_configure),
        }
        i = 0
        while i < len(steps):
            self._stretch_active = True
            try:
                await steps[i]()
            except _DirectedIteration as d:
                self._begin_directed(d.owner, d.feedback)
                i = rewind[d.owner]
                continue
            i += 1
        self.ended = True
        self.bus.audit("conductor", "run_ended", {"status": "approved"})
        await self._emit("conductor", "run.ended",
                         {"status": "approved",
                          "note": "Approved — job, verdict and the signed cell recorded."})

    def _begin_directed(self, owner: str, feedback: str) -> None:
        """The owner+forward rule (13): bump iterations for the owner stage
        and every completed forward stage; human acts burn no loop budget."""
        self.run.feedback = feedback
        self._directed_owner = owner
        if owner == "interpret":
            self._draft += 1
            self.run.draft = self._draft
        else:  # configure: the code door
            self.run.rig["_cell_revised"] = True
        owner_hit = False
        for key in STAGE_ORDER:
            if key == owner:
                owner_hit = True
            if owner_hit and (key, self._iter[key]) in self._done_stages:
                self._iter[key] += 1
        self.bus.audit("human", "directed_iteration",
                       {"owner": owner, "feedback": feedback[:200]})
        self._feed("directed_iteration", f"directed iteration -> {owner}: {feedback[:120]}")

    # ---- steps -------------------------------------------------------------------------

    async def _s_open(self) -> None:
        if not self._started:
            self._started = True
            brd = self.run.request.get("brd_name") if self.run.door == "brd" else None
            await self._emit("conductor", "run.started",
                             {"job": self.run.job, "door": self.run.door,
                              "tier": self.run.tier, "brd": brd,
                              "request_text": self.run.request.get("text"),
                              "itinerary": ITINERARY})
            # The full request rides the audit so a crash-restored conductor
            # re-walks the same door with the same knobs (05: restore from
            # bus + audit).
            self.bus.audit("conductor", "run_started",
                           {"job": self.run.job, "door": self.run.door,
                            "request": self.run.request})
            self._feed("run_started", f"run {self.run.run_id} started ({self.run.door} door)")
        # Non-blocking (05): intake starts now; the opening streams alongside.
        self.orch.narrate("opening.brd" if self.run.door == "brd" else "opening.typed")

    async def _s_intake(self) -> None:
        if self._stage_done("intake"):
            return
        await self._stage_started("intake")
        if self.run.door == "brd":
            await self._run_stage("explode", "intake")
            shape_repairs = 0
            budget = SHAPE_REPAIR_CAP
            shape_feedback: Optional[Dict[str, Any]] = None
            while True:
                await self._run_stage("doc_normalize", "intake", repair=shape_feedback)
                shape_feedback = None
                nv = await self._run_stage("normalize_validate", "intake")
                if nv.status == "shape_error":
                    shape_repairs += 1
                    # The validator's structural errors[] route to the next
                    # normalizer pass in-prompt (ticket 17).
                    shape_feedback = {"errors": nv.data.get("errors") or []}
                    if shape_repairs > budget:
                        try:
                            budget = await self._exhaustion("shape_repair", "intake",
                                                            shape_repairs - 1, budget)
                        except _StopToGate:
                            raise _Stopped(
                                "Stopped by you — extraction never validated clean")
                        continue
                    await self._loop_attempt(
                        "intake", shape_repairs, budget,
                        f"shape repair {shape_repairs} of {budget} · "
                        f"{nv.data.get('note', 'validator fed back — re-normalizing')}")
                    continue
                if nv.status == "needs_human":
                    q = nv.data.get("question") or {}
                    # A crash-restore re-walk re-validates the same proposal;
                    # re-await the still-pending extraction question instead of
                    # minting a phantom duplicate (first live session: one
                    # unresolved source raised three ids across two restarts).
                    pending_nh = self.questions.pending("needs_human")
                    if pending_nh:
                        nh_qid = str(pending_nh[-1]["question_id"])
                    else:
                        self._nh_count += 1
                        nh_qid = f"q-nh-{self._nh_count}"
                    res = await self.questions.ask(
                        nh_qid, "needs_human",
                        {"source": q.get("source", "normalize_validate"),
                         "prompt": q.get("prompt", ""),
                         "free_prompt": q.get("free_prompt", "Something else…"),
                         "n": self._nh_count,
                         "voice": "Extraction needs one answer before the envelope closes."},
                        list(q.get("options") or []),
                    )
                    # Recorded untouched, then folded into the next normalizer
                    # pass in-prompt (ticket 17).
                    self.run.nh_resolutions.append({
                        "source": q.get("source", "normalize_validate"),
                        "prompt": q.get("prompt", ""),
                        "choice": res.get("choice"),
                        "free_text": res.get("free_text"),
                    })
                    continue
                self.run.data_present = self.run.data_present or bool(
                    nv.data.get("data_present"))
                break
            note = nv.data.get("note") or "Doc Normalizer · extract validated clean"
        else:
            result = await self._run_stage("intake_build", "intake")
            self.run.data_present = self.run.data_present or bool(
                result.data.get("data_present"))
            note = result.data.get("note") or "Intake builder · envelope validated clean"
        await self._sleep(0.7)
        await self._stage_completed("intake", note=note)
        await self._boundary("intake")

    async def _s_interpret(self) -> None:
        if self._stage_done("interpret"):
            return
        revision = self._iter["interpret"] > 1
        extra = ({"directed": True, "feedback": self.run.feedback} if revision else {})
        await self._stage_started("interpret", **extra)
        self.run.gap_resolutions = self._gap_resolutions()
        self.run.interpret_mode = "revise" if revision else "read"
        result = await self._run_stage("interpret", "interpret")
        self._pending_gaps = list(result.data.get("gaps") or [])
        # Interpret completes at spec-gate entry: elicitation belongs to the
        # interpreter (04), so the stage stays active through the gap round.

    async def _s_gaps(self) -> None:
        if self._iter["interpret"] > 1:
            return  # revisions fold signed answers in; new gaps arrive as a normal round
        gaps = list(self._pending_gaps)
        # Standing injection rule (grilled 2026-08-10): code, not the model,
        # guarantees the missing-data advisory fires every dataless run.
        if not self.run.data_present:
            gaps.insert(0, {
                "id": "G0", "severity": "advisory", "rule": "verification",
                "prompt": ("No sample or expected data came with this request — "
                           "verification needs data to grade against. Attach file "
                           "paths below, or proceed without a verified tier."),
                "options": [
                    {"id": "attach", "label": "Attach data (paths below)", "kind": "choice",
                     "recommended": True, "why": "a verified build grades against your golden"},
                    {"id": "waive", "label": "Proceed without verification", "kind": "waive"},
                ],
                "free_prompt": "Paths to sample / expected files…",
            })
        round_k = 0
        while gaps:
            round_k += 1
            batch = round_k > ELICITATION_ROUNDS
            round_id = "batch" if batch else f"r{round_k}"
            self.orch.narrate("questions")
            waits = []
            for g in gaps:
                qid = f"q-{g['id'].lower()}-{round_id}"
                payload = {
                    "gap_id": g["id"], "rule_id": g.get("rule"),
                    "severity": g["severity"], "prompt": g["prompt"],
                    "free_prompt": g.get("free_prompt", "Something else…"),
                    "round_id": round_id,
                    "round": {"k": min(round_k, ELICITATION_ROUNDS),
                              "n": ELICITATION_ROUNDS},
                }
                if batch:
                    # 02: the soft budget ran out -- everything left lands as
                    # one answer-or-waive batch, never a silent drop.
                    payload["batch"] = True
                waits.append(self.questions.ask(qid, "gap", payload, g["options"]))
            await asyncio.gather(*waits)
            self._apply_gap_effects(round_id, gaps)
            self.run.gap_resolutions = self._gap_resolutions()
            # Dependency-first re-find (tickets 02/17): the interpreter folds
            # the round's answers in and re-finds downstream gaps; the loop
            # drains when it emits none. After the batch round everything
            # left was answer-or-waive, so one fold-in pass closes the loop
            # (any gap it still finds lands on the spec as an open item the
            # human sees at sign-off -- never a silent drop, never round 5).
            self.run.interpret_mode = "refind"
            result = await self._run_stage("interpret", "interpret")
            gaps = list(result.data.get("gaps") or [])
            self._pending_gaps = gaps
            if batch:
                break
        self.run.gap_resolutions = self._gap_resolutions()

    def _apply_gap_effects(self, round_id: str, gaps: List[Dict[str, Any]]) -> None:
        for g in gaps:
            if g["id"] != "G0":
                continue
            res = self.questions.resolved.get(f"q-g0-{round_id}") or {}
            if res.get("choice") in ("attach", "other"):
                self.run.data_present = True
                paths = [p.strip() for p in str(res.get("free_text") or "").split(",")
                         if p.strip()]
                self.run.request.setdefault("attachments", []).extend(paths)
                self.bus.audit("human", "data_attached", {"paths": paths})

    @staticmethod
    def _spec_signature(spec: Dict[str, Any]) -> str:
        core = {k: v for k, v in (spec or {}).items()
                if k not in ("draft", "what_changed")}
        return hashlib.sha1(
            json.dumps(core, sort_keys=True).encode("utf-8")).hexdigest()

    async def _s_spec_gate(self) -> None:
        while True:
            if not self._stage_done("interpret"):
                await self._stage_completed("interpret")
            spec = self.bus.read_json("requirement_spec.json") or {}
            sig = self._spec_signature(spec)
            # Re-raise only when the spec changed (16 scope): an unchanged
            # directed revision keeps the standing signature.
            if self._draft > 1 and sig == self._signed_spec_sig:
                return
            res = await self.questions.ask(
                f"q-spec-d{self._draft}", "spec_gate",
                {"draft": self._draft, "job": self.run.job,
                 "summary": {"sources": len(spec.get("sources") or []),
                             "rules": len(spec.get("rules") or [])},
                 "gap_resolutions": self._gap_resolutions(),
                 "what_changed": spec.get("what_changed"),
                 "voice": ("The spec is complete: %d rules, your answers recorded. "
                           "Signing it fixes what the job must do — every later stage "
                           "stands on it." % len(spec.get("rules") or [])
                           if self._draft == 1 else
                           "The revision is in. Same signed answers, your note folded in — "
                           "sign draft %d to continue." % self._draft)},
                [
                    {"id": "approve", "kind": "approve", "label": "Approve and sign"},
                    {"id": "request_changes", "kind": "reject", "label": "Request changes",
                     "free": "required", "placeholder": "What should change in the spec…"},
                ],
            )
            if res.get("choice") == "approve":
                if sig != self._signed_spec_sig:
                    self._signed_spec_sig = sig
                    self.bus.audit("human", "spec_signed",
                                   {"draft": self._draft, "signature": sig})
                return
            self._begin_directed("interpret", str(res.get("free_text") or ""))
            await self._s_interpret()

    async def _s_golden(self) -> None:
        self.orch.narrate("signed")
        result = await self._run_stage("materialize", "interpret")
        # The materializer's rung-aware computation is the tier truth (19);
        # an empty result reads as build, never as an optimistic verified.
        tier = result.data.get("tier") or "build"
        if self.run.tier != tier:
            self.run.tier = tier
            self.bus.audit("conductor", "tier_frozen", {"tier": tier})
            self._feed("tier_frozen", f"tier frozen: {tier}")
        await self._boundary("interpret")

    async def _s_design(self) -> None:
        if self._stage_done("design"):
            return
        condensed = self._iter["design"] > 1
        await self._stage_started("design")
        await self._run_stage("design", "design")
        await self._stage_completed("design")
        if not condensed:
            self.orch.narrate("flow")
        await self._boundary("design")

    async def _s_configure(self) -> None:
        if self._stage_done("configure"):
            return
        condensed = self._iter["configure"] > 1
        directed = condensed and self._directed_owner == "configure"
        await self._stage_started(
            "configure",
            **({"directed": True, "feedback": self.run.feedback} if directed else {}))
        result = await self._run_stage("configure", "configure")
        await self._stage_completed(
            "configure",
            note=(result.data.get("note")
                  or ("Configurator · revision applied — validate loop clean" if condensed
                      else "Configurator · configured — validate loop clean")))
        await self._boundary("configure")

    async def _s_assemble(self) -> None:
        if self._stage_done("assemble"):
            return
        await self._stage_started("assemble")
        await self._run_stage("assemble", "assemble")
        await self._stage_completed("assemble")
        await self._boundary("assemble")

    # ---- the pre-execution code gate ------------------------------------------------

    @staticmethod
    def _cell_hash(cell: Dict[str, Any]) -> str:
        raw = f"{cell.get('component')}|{cell.get('field')}|{cell.get('code')}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _gate_cells(self) -> List[Dict[str, Any]]:
        """Walk job.json with the vendored surfacer; merge display metadata
        from the configurator's cell_meta sidecar (config.json)."""
        job = self.bus.read_json("job.json") or {}
        meta = (self.bus.read_json("config.json") or {}).get("cell_meta", {})
        out = []
        for cell in surface_code_cells(job):
            m = meta.get(str(cell.get("component"))) or {}
            key = (str(cell.get("component")), str(cell.get("field")))
            h = self._cell_hash(cell)
            out.append({
                "id": m.get("id") or f"{cell.get('component')}.{cell.get('field')}",
                "node_id": m.get("node_id") or cell.get("component"),
                "component": m.get("component") or cell.get("type"),
                "author": m.get("author", "Configurator"),
                "code": cell.get("code"),
                "validator": m.get("validator"),
                "unsandboxed": cell.get("unsandboxed"),
                "new": key not in self._raised_cells,
                "changed": key in self._raised_cells and h not in self._approved_cells,
                "_hash": h, "_key": key,
            })
        return out

    async def _s_code_gate(self) -> None:
        cells = self._gate_cells()
        pending = [c for c in cells if c["_hash"] not in self._approved_cells]
        if not pending:
            return  # 04's re-pause rule: only new or changed cells re-raise
        if self._code_round == 1:
            self.orch.narrate("gate")
        new_keys = [c["_key"] for c in pending if c["new"]]
        if new_keys:
            self.bus.audit("conductor", "cells_raised",
                           {"cells": [list(k) for k in new_keys]})
            self._raised_cells.update(new_keys)
        display = [{k: v for k, v in c.items() if not k.startswith("_")} for c in pending]
        res = await self.questions.ask(
            f"q-code-r{self._code_round}", "code_gate",
            {"round": self._code_round, "cells": display,
             "note": ("Re-raising changed cells only" if self._code_round > 1 else None),
             "voice": (("One step writes code — computing market_value. Nothing runs "
                        "until you approve the exact cell. The cell is on the canvas, "
                        "spotlit.")
                       if self._code_round == 1 else
                       "The cell is rewritten to your note — same one step, new exact "
                       "code. Approve it to run.")},
            [
                {"id": "approve", "kind": "approve", "label": "Approve and run"},
                {"id": "request_changes", "kind": "reject", "label": "Request changes",
                 "free": "required", "placeholder": "What should change in this cell…"},
            ],
        )
        if res.get("choice") == "approve":
            hashes = [c["_hash"] for c in pending]
            fresh = [h for h in hashes if h not in self._approved_cells]
            self._approved_cells.update(hashes)
            if fresh:
                self.bus.audit("human", "cells_approved", {"hashes": fresh})
            return
        self._code_round += 1
        raise _DirectedIteration("configure", str(res.get("free_text") or ""))

    # ---- verify: tier routing + the main repair loop -----------------------------------

    async def _exhaustion(self, loop: str, stage: str, used: int, budget: int) -> int:
        """A loop budget ran dry: grant / stop / steer -- never a silent
        stop (04). Returns the grown budget on grant; raises otherwise."""
        self._x_count += 1
        stop_option = (
            {"id": "stop_to_gate", "kind": "stop", "label": "Stop to the gate"}
            if loop == "repair" else
            {"id": "stop", "kind": "stop", "label": "Stop the build"}
        )
        res = await self.questions.ask(
            f"q-x-{self._x_count}", "exhaustion",
            {"loop": loop, "stage": stage, "k": used, "n": budget,
             "x_n": self._x_count, "grant_size": GRANT_SIZE,
             "voice": (f"The {loop.replace('_', ' ')} budget is spent — {used} passes "
                       f"against a cap of {budget}. Grant {GRANT_SIZE} more, "
                       + ("stop to the gate with the verdict as it stands, "
                          if loop == "repair" else "stop the build, ")
                       + "or steer the spec.")},
            [
                {"id": "grant", "kind": "grant",
                 "label": f"Grant {GRANT_SIZE} more", "recommended": True,
                 "why": "each grant is an explicit act — spend cannot run away silently"},
                stop_option,
                {"id": "steer", "kind": "steer", "label": "Steer", "free": "required",
                 "placeholder": "What should change — routes to the Interpreter…"},
            ],
        )
        choice = res.get("choice")
        if choice == "grant":
            self._grants += 1
            self.bus.audit("human", "grant",
                           {"loop": loop, "new_budget": budget + GRANT_SIZE})
            return budget + GRANT_SIZE
        if choice == "steer" or (choice == "other" and res.get("free_text")):
            self.orch.narrate("steer")
            raise _DirectedIteration("interpret", str(res.get("free_text") or ""))
        if choice == "stop":
            raise _Stopped("Stopped by you — from the exhausted "
                           + loop.replace("_", " ") + " loop")
        raise _StopToGate()

    @staticmethod
    def _matched_of(report: Dict[str, Any]) -> str:
        """"m/n" rows matching the golden across graded outputs, from the
        real report's diff counts; "—" when nothing was graded."""
        matched = total = 0
        seen = False
        for diff in (report.get("outputs") or {}).values():
            expected = diff.get("expected_rows")
            if expected is None:
                continue
            seen = True
            total += int(expected)
            bad = int(diff.get("missing") or 0) + int(diff.get("value_mismatch") or 0)
            matched += max(0, int(expected) - bad)
        return f"{matched}/{total}" if seen else "—"

    def _diagnosis_line(self, clean: bool, runs: int, tier: str,
                        stopped_to_gate: bool, report: Dict[str, Any],
                        feedback: Dict[str, Any]) -> str:
        """The verdict's one-line story, assembled from the run's real
        artifacts -- the report's counts and the diagnostician's actual
        owner/fix (ticket 06: every shown string traceable to this run)."""
        graded = report.get("graded")
        graded_bit = (f" · {graded}/{report.get('total', graded)} outputs graded"
                      if graded is not None else "")
        if tier == "smoke":
            if clean:
                return "smoke tier — the job ran clean; nothing was graded"
            problems = report.get("dropped_or_errored_components") or []
            return ("smoke tier — the run failed"
                    + (f" ({', '.join(str(p) for p in problems[:3])})" if problems
                       else ""))
        if clean and runs == 1:
            return "clean on the first run" + graded_bit
        if clean:
            owner = str(feedback.get("owner") or "").capitalize()
            fix = str(feedback.get("fix") or "").strip()
            line = f"went green on run {runs}"
            if owner:
                line += f" — Diagnostician: owner {owner}"
            if fix:
                line += f" · fix: {fix[:90]}"
            return line + graded_bit
        if stopped_to_gate:
            return "repairs stopped at your call — the verdict stands as it is"
        return (f"not verified — run {runs} still mismatched the golden"
                + graded_bit)

    async def _s_verify(self) -> None:
        if self._stage_done("verify"):
            return
        await self._stage_started("verify")
        tier = self.run.tier or "build"
        if tier == "build":
            self._verdict = {
                "verdict": "unverified", "matched": "—", "runs": {"k": 0, "n": 0},
                "diagnosis": "build tier — no data to grade against, nothing ran"}
            self.bus.audit("conductor", "verdict", dict(self._verdict))
            self._feed("verdict", "verdict: " + json.dumps(self._verdict, ensure_ascii=True))
            await self._stage_completed("verify")
            await self._boundary("verify")
            return
        # Attempt frame: run 1 plus up to (budget - 1) repair re-runs;
        # grants stretch the budget, each an explicit human act.
        budget = REPAIR_CAP + self._grants * GRANT_SIZE
        runs = 0
        clean = False
        stopped_to_gate = False
        last_report: Dict[str, Any] = {}
        last_feedback: Dict[str, Any] = {}
        while True:
            result = await self._run_stage("test_run", "verify")
            runs += 1
            last_report = result.data.get("report") or {}
            if result.data.get("clean"):
                clean = True
                break
            if tier == "smoke":
                break  # smoke runs exactly once; only verified loops
            diag = await self._run_stage("diagnose", "verify")
            feedback = diag.data.get("feedback") or {}
            owner = str(feedback.get("owner") or "")
            if owner not in _OWNER_ENUM:
                # Fail-closed (04): an unclassifiable diagnosis is the
                # human's call, never a guessed re-run.
                owner = "human"
            last_feedback = dict(feedback, owner=owner)
            if owner == "human":
                self._oh_count += 1
                res = await self.questions.ask(
                    f"q-oh-{self._oh_count}", "owner_human",
                    {"n": self._oh_count,
                     "prompt": feedback.get("question")
                     or "The diagnosis lands on your side of the fence.",
                     "evidence": feedback.get("evidence"),
                     "voice": "The diagnostician says the fix is yours to make — "
                              "steer the spec, run again as-is, or stop to the gate."},
                    [
                        {"id": "retry", "kind": "choice", "label": "Run again as-is"},
                        {"id": "stop_to_gate", "kind": "stop", "label": "Stop to the gate"},
                        {"id": "steer", "kind": "steer", "label": "Steer",
                         "free": "required",
                         "placeholder": "What should change — routes to the Interpreter…"},
                    ],
                )
                choice = res.get("choice")
                if choice == "steer" or (choice == "other" and res.get("free_text")):
                    self.orch.narrate("steer")
                    raise _DirectedIteration("interpret", str(res.get("free_text") or ""))
                if choice == "stop_to_gate":
                    stopped_to_gate = True
                    break
                continue  # run again as-is: a human act, burns no repair budget
            if owner == "interpreter":
                # 04's mid-loop rule: a spec-owned failure re-presents the
                # spec for re-sign-off — the spec door, uncapped.
                raise _DirectedIteration(
                    "interpret", str(feedback.get("fix") or feedback.get("why") or ""))
            if runs + 1 > budget:
                try:
                    budget = await self._exhaustion("repair", "verify", runs, budget)
                except _StopToGate:
                    stopped_to_gate = True
                    break
            # Owner+forward (04): the owner re-runs reading feedback.json
            # first, then every forward design-side stage, quietly.
            slot = _OWNER_SLOT.get(owner, "configure")
            for step in _REPAIR_CHAIN[_REPAIR_CHAIN.index(slot):]:
                await self._run_stage(step, "verify", repair=feedback)
            await self._loop_attempt(
                "verify", runs + 1, budget,
                f"repair {runs + 1} of {budget} · {owner.capitalize()} re-ran · "
                f"{feedback.get('fix') or 'fix applied'}")
        if clean:
            verdict = "verified" if tier == "verified" else "smoke_clean"
        else:
            verdict = "failed" if tier == "verified" else "smoke_failed"
        self._verdict = {
            "verdict": verdict,
            "matched": self._matched_of(last_report),
            "runs": {"k": runs, "n": budget if tier == "verified" else 1},
            "diagnosis": self._diagnosis_line(
                clean, runs, tier, stopped_to_gate, last_report, last_feedback),
        }
        # The verdict is a conductor decision: audit it (restore parity) and
        # feed it, so the orchestrator narrates the real result (ticket 18).
        self.bus.audit("conductor", "verdict", dict(self._verdict))
        self._feed("verdict", "verdict: " + json.dumps(self._verdict, ensure_ascii=True))
        await self._stage_completed("verify")
        await self._boundary("verify")

    async def _s_human_gate(self) -> None:
        first = self._human_round == 1
        self.orch.narrate("verdict" if first else "reverdict")
        verdict = dict(self._verdict or {})
        red = verdict.get("verdict") in ("failed", "smoke_failed")
        options = []
        if not red:
            options.append({"id": "approve", "kind": "approve", "label": "Approve job"})
        options.append({"id": "request_changes", "kind": "reject",
                        "label": "Request changes", "free": "required",
                        "placeholder": "What’s wrong with the output…"})
        options.append({"id": "stop", "kind": "stop", "label": "Stop"})
        res = await self.questions.ask(
            f"q-human-r{self._human_round}", "human_gate",
            {"round": self._human_round, **verdict, "tier": self.run.tier,
             "table": self._verdict_table(),
             "files": self._verdict_files(),
             "voice": ("Job, verdict, and the one signed cell — ready for your approval. "
                       "Nothing auto-approves." if not red else
                       "The verdict is red — approve is off the table. Revise the spec "
                       "or stop the build.")},
            options,
        )
        choice = res.get("choice")
        if choice == "approve":
            return
        if choice == "stop":
            raise _Stopped("Stopped by you — at the human gate")
        self._human_round += 1
        raise _DirectedIteration("interpret", str(res.get("free_text") or ""))

    def _verdict_table(self) -> Dict[str, Any]:
        """The human gate's graded table: the first graded output's golden,
        read through the materializer's manifest (name + delimiter)."""
        manifest = self.bus.read_json("golden/manifest.json") or {}
        for name, spec in (manifest.get("outputs") or {}).items():
            if not spec.get("graded"):
                continue
            golden = self.bus.path(f"golden/{name}_expected.csv")
            if not golden.is_file():
                continue
            reader = csv.reader(io.StringIO(golden.read_text(encoding="utf-8")),
                                delimiter=str(spec.get("sep") or ";"))
            rows = [row for row in reader if row]
            if not rows:
                continue
            return {"headers": rows[0], "rows": rows[1:]}
        return {"headers": [], "rows": []}

    def _verdict_files(self) -> List[Dict[str, str]]:
        """Open-in-editor chips for the gate (ticket 20): the whole files
        behind the graded sample -- each actual output beside its golden --
        open in the real editor, never the feed (ticket 06). Real bus paths;
        a missing file simply grows no chip."""
        files: List[Dict[str, str]] = []
        manifest = self.bus.read_json("golden/manifest.json") or {}
        for name, spec in (manifest.get("outputs") or {}).items():
            if not spec.get("graded"):
                continue
            for label, rel in ((f"{name}.csv", f"{name}.csv"),
                               (f"{name}_expected.csv", f"golden/{name}_expected.csv")):
                target = self.bus.path(rel)
                if target.is_file():
                    files.append({"label": label, "path": str(target)})
        return files
