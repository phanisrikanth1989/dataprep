"""Scripted trade_positions run (ticket 15).

Drives the full 08 event vocabulary over the real wire so the webview can be
built and demoed against the test double before the conductor exists
(tickets 16+ replace this with the real pipeline). Everything emitted is
real run state: streams go through the provider port (the double plays the
fixtures below), questions block until a human answer arrives, and the
journal is the only crash-restore state -- every emission helper consults it
and no-ops when the journal already holds the event, so a restarted core
resumes mid-run by replaying the same script against the same journal.

Provisional contract extensions recorded on ticket 15:
  - ``stage.progress`` {node_id, state} -- per-component configure progress
    (conductor machine truth feeding the canvas choreography).
  - stream part kind ``tool_result`` -- core-authored outcome of a model
    ``tool_call``, for the observed activity window.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from .port import ChatMessage, ChatRequest, ProviderError, ProviderPort, RateLimited

logger = logging.getLogger(__name__)

Emit = Callable[[str, str, Dict[str, Any]], Awaitable[None]]

# ---------------------------------------------------------------------------
# Run content (real-shaped, ported from the ticket 12 design record)
# ---------------------------------------------------------------------------

JOB = "trade_positions"
BRD = "Trade_Positions_BRD.docx"

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

SOURCES = [
    {"file": "trades.csv", "cols": 7},
    {"file": "accounts.csv", "cols": 3},
    {"file": "prices.csv", "cols": 2},
]

RULES = [
    {"id": "R1", "kind": "filter", "label": "Keep settled trades", "detail": "status = SETTLED"},
    {"id": "R2", "kind": "join", "label": "Add account details", "detail": "left join · account_id", "gap": "G1"},
    {"id": "R3", "kind": "join", "label": "Add closing price", "detail": "left join · symbol"},
    {"id": "R4", "kind": "derive", "label": "Compute market value", "detail": "quantity × price", "code": True},
    {"id": "R5", "kind": "validate", "label": "Validate trade_date", "detail": "yyyy-MM-dd"},
    {"id": "R6", "kind": "sort", "label": "Sort by market value", "detail": "high to low", "gap": "G2"},
]

GAPS = [
    {
        "id": "G1",
        "severity": "blocking",
        "rule": "R2",
        "prompt": "Trades with no matching account — drop them, or keep them with blank account fields?",
        "options": [
            {"id": "keep_blanks", "label": "Keep them with blanks", "kind": "choice",
             "recommended": True, "why": "the BRD reads as a full extract"},
            {"id": "drop", "label": "Drop unmatched trades", "kind": "choice"},
        ],
        "free_prompt": "Something else…",
    },
    {
        "id": "G2",
        "severity": "advisory",
        "rule": "R6",
        "prompt": "Equal market values: the BRD gives no tie-breaker. Default to trade_id ascending within ties?",
        "options": [
            {"id": "trade_id_asc", "label": "trade_id ascending", "kind": "choice",
             "recommended": True, "why": "stable and auditable"},
            {"id": "waive", "label": "Waive — proceed with the default", "kind": "waive"},
        ],
        "free_prompt": "A different tie-breaker…",
    },
]

NODES = [
    {"id": "in_trades", "kind": "source", "label": "Read trades", "sub": "trades.csv · 7 cols"},
    {"id": "in_accounts", "kind": "source", "label": "Read accounts", "sub": "accounts.csv · 3 cols"},
    {"id": "in_prices", "kind": "source", "label": "Read prices", "sub": "prices.csv · 2 cols"},
    {"id": "filter_settled", "kind": "filter", "label": "Keep status = SETTLED", "sub": "FilterRows"},
    {"id": "join_accounts", "kind": "join", "label": "Match accounts", "sub": "left join · account_id"},
    {"id": "join_prices", "kind": "join", "label": "Match prices", "sub": "left join · symbol"},
    {"id": "validate_date", "kind": "validate", "label": "Validate trade_date", "sub": "yyyy-MM-dd"},
    {"id": "derive_mv", "kind": "derive", "label": "Compute market_value", "sub": "generated cell", "code": True},
    {"id": "sort_mv", "kind": "sort", "label": "Sort by market_value", "sub": "numeric · desc"},
    {"id": "out_positions", "kind": "output", "label": "Write trade_positions", "sub": "trade_positions.csv"},
]

EDGES = [
    ["in_trades", "filter_settled"],
    ["filter_settled", "join_accounts"],
    ["in_accounts", "join_accounts"],
    ["join_accounts", "join_prices"],
    ["in_prices", "join_prices"],
    ["join_prices", "validate_date"],
    ["validate_date", "derive_mv"],
    ["derive_mv", "sort_mv"],
    ["sort_mv", "out_positions"],
]

CODE_CELL = {
    "id": "derive_market_value",
    "node_id": "derive_mv",
    "component": "tPythonDataFrame",
    "author": "Configurator",
    "code": "df['market_value'] = df['quantity'].astype(float) * df['price'].astype(float)",
    "validator": "validator clean · output schema 6 columns",
}
CODE_CELL_REVISED = dict(
    CODE_CELL,
    code=(
        "df['market_value'] = (df['quantity'].astype('float64')\n"
        "                      * df['price'].astype('float64')).round(2)"
    ),
    validator="validator clean · output schema 6 columns · rounding pinned",
)

VERDICT_TABLE = {
    "headers": ["trade_id", "account_name", "region", "symbol", "market_value", "closing_price"],
    "rows": [
        ["T004", "Gamma Funds", "APAC", "AAPL", "30200.00", "150.80"],
        ["T002", "Beta Partners", "EMEA", "MSFT", "20525.00", "411.00"],
        ["T001", "Alpha Capital", "NA", "AAPL", "15025.00", "150.80"],
        ["T005", "—", "—", "TSLA", "6901.00", "689.00"],
    ],
}

ORCH = {
    "questions": "I’ve read Trade_Positions_BRD.docx — three sources, six rules. Two answers and the spec is complete. They’re pinned to the rules they block, out on the canvas.",
    "signed": "Spec signed off. Your goldens are in place — this run grades against them.",
    "flow": "The flow is designed: a filter, two lookups, one computed column, a date check, a sort. Configuring each step now.",
    "gate": "One step writes code — computing market_value. Nothing runs until you approve the exact cell. The cell is on the canvas, spotlit.",
    "verdict": "Verified. The output matches your golden — all 4 rows, order included. Run 1 mis-sorted; the fix was one setting.",
    "reverdict": "Re-verified after your revision — the output still matches your golden, all 4 rows.",
}

THINK_INTERPRETER = (
    "R4 reads “settled trades only” — that’s a filter on status = SETTLED. "
    "Section 3 never says what happens to trades with no account match — raising it rather than assuming. "
    "Sort is given (value, high to low) but no tie-breaker — advisory, default trade_id."
)
THINK_FLOW = (
    "Filter first — it shrinks both lookups. "
    "Two joins stay separate: different keys, and rejects must be traceable per lookup. "
    "Sort placed last so the output order is the contract."
)
THINK_CONFIG_1 = (
    "join_accounts carries account_name and region; left join per the G1 answer — unmatched trades keep blanks. "
    "prices joins on symbol; single lookup column closing_price, key unique in the sample rows."
)
THINK_CONFIG_2 = (
    "market_value = quantity × price lands as the one generated cell — flagging it for the code gate. "
    "sort_mv compares numerically, descending; ties per the G2 default."
)

TOOL_RESULTS: Dict[str, Dict[str, Any]] = {
    "read_knowledge": {"ok": True,
                       "note": "loaded: join modes, key rules, 2 landmines (lookup dupe fan-out; type-mismatched keys)"},
    "validate_config": {"ok": True, "warn": "attempt 2 of 3",
                        "note": "run 1: sort_type missing → fixed. run 2: clean."},
    "write_artifact": {"ok": True, "note": "config.json · 10 components · 9 flows"},
}


def build_scripts() -> Dict[str, List[List[Dict[str, Any]]]]:
    """Fixture scripts handed to the DoubleAdapter at the main.py wiring point."""
    u = lambda n: {"usage": int(n * 1e9)}  # noqa: E731 -- AIU to nano-AIU
    return {
        "orch.opening.brd": [[
            {"text": "Reading Trade_Positions_BRD.docx — three tables and six rule paragraphs found. I’ll interpret them into a spec; anything unclear becomes a question, never an assumption."},
            u(2.1),
        ]],
        "orch.opening.typed": [[
            {"text": "Reading your request. I’ll interpret it into a spec; anything unclear becomes a question, never an assumption."},
            u(1.7),
        ]],
        "interp.read": [[{"think": THINK_INTERPRETER}, u(3.4)]],
        "interp.revise": [[
            {"think": "Reading your note — folding it into the spec as a revision. Every signed answer carries over; only what you flagged moves."},
            u(2.6),
        ]],
        "orch.questions": [[{"text": ORCH["questions"]}, u(1.8)]],
        "orch.signed": [[{"text": ORCH["signed"]}, u(1.2)]],
        "flow.design": [[{"think": THINK_FLOW}, u(3.1)]],
        "orch.flow": [[{"text": ORCH["flow"]}, u(1.6)]],
        "config.main": [[
            {"think": THINK_CONFIG_1},
            {"tool": {"call_id": "t1", "name": "read_knowledge", "args": {"component": "tJoin"}}},
            {"pause": 0.5},
            {"tool": {"call_id": "t2", "name": "validate_config", "args": {"step": "keep_settled"}}},
            u(12.4),
        ]],
        "config.rate": [[
            {"think": "writing config.json for the configured steps…"},
            {"error": {"kind": "RateLimited", "message": "provider returned 429 on the last call", "retry_after": 1.8}},
        ]],
        "config.retry": [[
            {"think": THINK_CONFIG_2},
            {"tool": {"call_id": "t3", "name": "write_artifact", "args": {"path": "config.json"}}},
            u(9.7),
        ]],
        "config.revise": [[
            {"think": "Rewriting the market_value cell per your note — explicit float64 cast and a pinned 2-decimal round, no drift."},
            u(3.9),
        ]],
        "orch.gate": [[{"text": ORCH["gate"]}, u(1.9)]],
        "diag.run": [[
            {"think": "run 1 output: rows 2 and 3 swapped against the golden. sort_mv compares as text — '15025.00' sorts above '6901.00' only numerically. Owner: Configurator; fix is one setting, sort_type = num."},
            u(5.3),
        ]],
        "orch.verdict": [[{"text": ORCH["verdict"]}, u(2.4)]],
        "orch.reverdict": [[{"text": ORCH["reverdict"]}, u(1.8)]],
        "orch.hold": [[
            {"text": "You’d like me to pause. Confirm and I’ll hold at the next stage boundary — the stage in flight finishes and its artifact lands whole, then the run waits for you."},
            u(1.4),
        ]],
        "orch.stop": [[
            {"text": "You’d like to stop this run. Confirm and I’ll end it plainly at the next boundary — nothing else executes, everything so far stays on the canvas."},
            u(1.3),
        ]],
        "orch.resume": [[{"text": "Resuming — picking the run up exactly where the hold left it."}, u(0.9)]],
        "orch.steer": [[
            {"text": "That’s spec-shaped feedback, so it routes to the Interpreter: the spec revises, you re-sign it, and the stages after it re-run."},
            u(1.2),
        ]],
        "orch.ask": [[{"echo_prompt": True}, u(1.5)]],
    }


# ---------------------------------------------------------------------------
# Control-flow signals
# ---------------------------------------------------------------------------


class _Stopped(Exception):
    def __init__(self, note: str):
        self.note = note


class _SteerToSpec(Exception):
    def __init__(self, feedback: str):
        self.feedback = feedback


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------


class ScriptedRun:
    def __init__(
        self,
        emit: Emit,
        port: ProviderPort,
        run_id: str,
        door: str,
        request: Dict[str, Any],
        pace: float = 1.0,
    ):
        self._emit = emit
        self._port = port
        self.run_id = run_id
        self._door = door
        self._request = request
        self._pace = pace

        self._task: Optional[asyncio.Task] = None
        self._side_tasks: List[asyncio.Task] = []
        self._waiters: Dict[str, asyncio.Future] = {}
        self._questions: Dict[str, Dict[str, Any]] = {}  # qid -> raised payload
        self._resolved: Dict[str, Dict[str, Any]] = {}  # qid -> resolution
        self._artifacts: Dict[str, Dict[str, Any]] = {}
        self._done_stages: set[Tuple[str, int]] = set()
        self._done_artifacts: set[Tuple[str, int]] = set()
        self._closed_streams: Dict[str, int] = {}  # label -> closed count (journal)
        self._stream_calls: Dict[str, int] = {}  # label -> invocations this life
        self._iter: Dict[str, int] = {k: 1 for k in STAGE_ORDER}
        self._draft = 1
        self._code_round = 1
        self._human_round = 1
        self._cells_changed = True  # first pass: the cell is new
        self._pc_count = 0
        self._hold_count = 0
        self._armed: Optional[str] = None  # "hold" | "stop"
        self._stretch_active = False
        self._started = False
        self.ended = False

    # ---- lifecycle -----------------------------------------------------------

    @property
    def active(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        self._task = asyncio.get_running_loop().create_task(self._run())

    def restore(self, events: List[Dict[str, Any]]) -> None:
        """Rebuild resume state from the journal -- the journal IS the state."""
        for env in events:
            t, p = env.get("type", ""), env.get("payload", {}) or {}
            if t == "run.started":
                self._started = True
            elif t == "run.ended":
                self.ended = True
            elif t == "stage.completed":
                self._done_stages.add((p.get("stage", ""), int(p.get("iteration", 1))))
            elif t == "stage.artifact_written":
                self._done_artifacts.add((p.get("name", ""), int(p.get("iteration", 1))))
                if "fields" in p:
                    self._artifacts[p.get("name", "")] = p
            elif t == "question.raised":
                qid = p.get("question_id", "")
                self._questions[qid] = p
                if p.get("kind") == "spec_gate":
                    self._draft = max(self._draft, int(p.get("draft", 1)))
                if p.get("kind") == "code_gate":
                    self._code_round = max(self._code_round, int(p.get("round", 1)))
                if p.get("kind") == "human_gate":
                    self._human_round = max(self._human_round, int(p.get("round", 1)))
                if p.get("kind") == "propose_confirm":
                    self._pc_count = max(self._pc_count, int(p.get("n", 0)))
                if p.get("kind") == "hold":
                    self._hold_count = max(self._hold_count, int(p.get("n", 0)))
            elif t == "question.resolved":
                qid = p.get("question_id", "")
                self._resolved[qid] = p
            elif t == "stream.close":
                label = p.get("label")
                if label:
                    self._closed_streams[label] = self._closed_streams.get(label, 0) + 1
        # A confirmed hold/stop proposal whose hold question never raised re-arms.
        for qid, res in self._resolved.items():
            q = self._questions.get(qid, {})
            if q.get("kind") == "propose_confirm" and res.get("choice") == "confirm":
                later_hold = any(
                    k.startswith("q-hold-") and self._questions[k].get("after_pc") == qid
                    for k in self._questions
                )
                if not later_hold and not self.ended:
                    self._armed = q.get("proposal", "hold")
        # Bump stage iterations past completed directed re-runs so the step
        # loop's skip logic lands on the first unfinished iteration.
        for key in STAGE_ORDER:
            while (key, self._iter[key]) in self._done_stages:
                nxt = (key, self._iter[key] + 1)
                started_next = nxt in self._done_stages or self._journal_stage_started(events, *nxt)
                if started_next:
                    self._iter[key] += 1
                else:
                    break

    @staticmethod
    def _journal_stage_started(events: List[Dict[str, Any]], key: str, iteration: int) -> bool:
        return any(
            e.get("type") == "stage.started"
            and (e.get("payload") or {}).get("stage") == key
            and int((e.get("payload") or {}).get("iteration", 1)) == iteration
            for e in events
        )

    def resume(self) -> None:
        """Continue an un-ended run after crash-restart (crash_restored already emitted)."""
        for qid, q in self._questions.items():
            if qid in self._resolved:
                continue
            if q.get("kind") == "propose_confirm":
                self._spawn_side(self._await_proposal(qid))
        self._task = asyncio.get_running_loop().create_task(self._run())

    def dispose(self) -> None:
        for t in [self._task, *self._side_tasks]:
            if t is not None and not t.done():
                t.cancel()

    # ---- emission helpers (journal-idempotent) -------------------------------

    async def _sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds * self._pace)

    async def _stage_started(self, key: str, **extra: Any) -> None:
        it = self._iter[key]
        payload = {"stage": key, "label": STAGE_LABELS[key], "iteration": it, **extra}
        await self._emit("conductor", "stage.started", payload)

    async def _stage_completed(self, key: str, note: Optional[str] = None) -> None:
        it = self._iter[key]
        payload: Dict[str, Any] = {"stage": key, "label": STAGE_LABELS[key], "iteration": it}
        if note:
            payload["note"] = note
        await self._emit("conductor", "stage.completed", payload)
        self._done_stages.add((key, it))

    def _stage_done(self, key: str) -> bool:
        return (key, self._iter[key]) in self._done_stages

    async def _artifact(
        self, name: str, kind: str, fields: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None, stage: Optional[str] = None,
    ) -> None:
        it = self._iter.get(stage or "", 1) if stage else 1
        if (name, it) in self._done_artifacts:
            return
        payload: Dict[str, Any] = {"name": name, "kind": kind, "iteration": it}
        if stage:
            payload["stage"] = stage
        if note:
            payload["note"] = note
        if fields is not None:
            payload["fields"] = fields
        await self._emit("conductor", "stage.artifact_written", payload)
        self._done_artifacts.add((name, it))
        if fields is not None:
            self._artifacts[name] = payload

    async def _progress(self, node_id: str, state: str) -> None:
        await self._emit(
            "conductor", "stage.progress",
            {"stage": "configure", "node_id": node_id, "state": state},
        )

    async def _stream(
        self,
        source: str,
        who: str,
        script: str,
        prompt: str = "",
        stage_label: Optional[str] = None,
        in_reply_to: Optional[str] = None,
    ) -> str:
        """One model call through the port, forwarded per-part. Returns finish_reason."""
        self._stream_calls[script] = self._stream_calls.get(script, 0) + 1
        if self._closed_streams.get(script, 0) >= self._stream_calls[script]:
            return "stop"  # journal already holds this stream in full
        stream_id = f"s-{script}-{self._stream_calls[script]}-{self.run_id[-4:]}"
        open_payload: Dict[str, Any] = {
            "stream_id": stream_id, "provider": "double", "who": who, "label": script,
        }
        if stage_label:
            open_payload["stage_label"] = stage_label
        if in_reply_to:
            open_payload["in_reply_to"] = in_reply_to
        await self._emit(source, "stream.open", open_payload)
        request = ChatRequest(
            messages=[ChatMessage(role="user", text=prompt or script)],
            stream_id=stream_id,
            options={"script": script},
        )
        agen = self._port.chat(request)
        finish = "unknown"
        try:
            async for ev in agen:
                kind = getattr(ev, "kind", "unknown")
                if kind == "done":
                    finish = ev.finish_reason
                elif kind in ("text_delta", "thinking_delta"):
                    await self._emit(source, "stream.delta",
                                     {"stream_id": stream_id, "part": {"kind": kind, "text": ev.text}})
                elif kind == "tool_call":
                    await self._emit(source, "stream.delta",
                                     {"stream_id": stream_id,
                                      "part": {"kind": kind, "call_id": ev.call_id,
                                               "name": ev.name, "args": ev.args}})
                    result = TOOL_RESULTS.get(ev.name)
                    if result:
                        await self._sleep(0.5)
                        await self._emit(source, "stream.delta",
                                         {"stream_id": stream_id,
                                          "part": {"kind": "tool_result", "call_id": ev.call_id,
                                                   "name": ev.name, **result}})
                elif kind == "usage":
                    await self._emit(source, "stream.delta",
                                     {"stream_id": stream_id,
                                      "part": {"kind": "usage", "raw": ev.raw,
                                               "total_nano_aiu": ev.total_nano_aiu}})
            await self._emit(source, "stream.close",
                             {"stream_id": stream_id, "finish_reason": finish, "label": script})
            return finish
        except RateLimited as e:
            await self._emit(source, "stream.close",
                             {"stream_id": stream_id, "finish_reason": "error", "label": script})
            await self._emit("conductor", "health.retry",
                             {"reason": str(e), "attempt": 2, "of": 3,
                              "backoff_s": e.retry_after or 1.8, "stream_label": script})
            await self._sleep(float(e.retry_after or 1.8))
            return "rate_limited"
        except ProviderError as e:
            await self._emit("conductor", "health.error",
                             {"taxonomy": type(e).__name__, "message": str(e), "stream_id": stream_id})
            await self._emit(source, "stream.close",
                             {"stream_id": stream_id, "finish_reason": "error", "label": script})
            return "error"
        finally:
            try:
                await agen.aclose()
            except Exception:  # noqa: BLE001 -- generator may already be closed
                pass

    # ---- questions -----------------------------------------------------------

    async def _question(
        self, qid: str, kind: str, payload: Dict[str, Any], options: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if qid in self._resolved:
            return self._resolved[qid]
        if qid not in self._questions:
            raised = {"question_id": qid, "kind": kind, "options": options, **payload}
            self._questions[qid] = raised
            await self._emit("conductor", "question.raised", raised)
        fut = asyncio.get_running_loop().create_future()
        self._waiters[qid] = fut
        try:
            return await fut
        finally:
            self._waiters.pop(qid, None)

    async def handle_answer(self, params: Dict[str, Any]) -> None:
        qid = str(params.get("question_id", ""))
        q = self._questions.get(qid)
        if q is None or qid in self._resolved:
            logger.warning("answer for unknown/resolved question %s ignored", qid)
            return
        choice = str(params.get("choice", ""))
        free_text = params.get("free_text")
        resolution = {
            "question_id": qid,
            "kind": q.get("kind"),
            "choice": choice,
            "free_text": free_text,
            "note": self._resolution_note(q, choice, free_text),
        }
        if q.get("kind") == "gap":
            resolution["round_id"] = q.get("round_id")
            resolution["gap_id"] = q.get("gap_id")
        self._resolved[qid] = resolution
        await self._emit("conductor", "question.resolved", resolution)
        fut = self._waiters.get(qid)
        if fut is not None and not fut.done():
            fut.set_result(resolution)

    @staticmethod
    def _option_label(q: Dict[str, Any], choice: str) -> str:
        for o in q.get("options", []):
            if o.get("id") == choice:
                return str(o.get("label", choice))
        return choice

    def _resolution_note(self, q: Dict[str, Any], choice: str, free_text: Any) -> str:
        kind = q.get("kind")
        label = self._option_label(q, choice)
        if kind == "gap":
            gap = q.get("gap_id", "")
            if choice == "waive":
                return f"{gap}: waived — default applies, recorded on the spec"
            if choice == "other" and free_text:
                return f"{gap}: {free_text}"
            return f"{gap}: {label}"
        if kind == "spec_gate":
            draft = q.get("draft", 1)
            return (f"Spec draft {draft} — signed" if choice == "approve"
                    else f"Spec draft {draft} — changes requested")
        if kind == "code_gate":
            n = len(q.get("cells", []))
            return (f"Code gate — {n} cell{'s' if n != 1 else ''} approved" if choice == "approve"
                    else "Code gate — changes requested on derive_market_value")
        if kind == "human_gate":
            return {"approve": "Job approved — verdict and the signed cell recorded",
                    "request_changes": "Verdict — changes requested, spec door",
                    "stop": "Run stopped at the human gate"}.get(choice, label)
        if kind == "hold":
            if choice == "resume":
                return "Hold — resumed"
            if choice == "stop":
                return "Hold — stopped"
            text = str(free_text or "").strip()
            return f"Hold — steered: {text[:80]}" if text else "Hold — steered"
        if kind == "propose_confirm":
            proposal = q.get("proposal", "hold")
            if choice == "confirm":
                return ("Hold armed — takes effect at the next stage boundary"
                        if proposal == "hold" else "Stop confirmed — run ends at the next boundary")
            return "Dismissed — the run continues"
        return label

    # ---- composer asks -------------------------------------------------------

    async def handle_ask(self, params: Dict[str, Any]) -> None:
        ask_id = str(params.get("ask_id", ""))
        text = str(params.get("text", "")).strip()
        if not text:
            return
        self._spawn_side(self._answer_ask(ask_id, text))

    def _spawn_side(self, coro: Awaitable[None]) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._side_tasks.append(task)
        task.add_done_callback(lambda t: self._side_tasks.remove(t) if t in self._side_tasks else None)

    @staticmethod
    def _intent(text: str) -> Optional[str]:
        low = text.lower()
        if any(w in low for w in ("stop", "halt", "abort", "kill the run")):
            return "stop"
        if any(w in low for w in ("hold", "pause", "wait", "hang on", "slow down")):
            return "hold"
        return None

    async def _answer_ask(self, ask_id: str, text: str) -> None:
        intent = self._intent(text)
        if intent and self._stretch_active and not self._armed and not self.ended:
            await self._propose(ask_id, intent)
            return
        reply = self._compose_ask_reply(text)
        await self._stream("orchestrator", "Orchestrator", "orch.ask",
                           prompt=reply, in_reply_to=ask_id)

    def _compose_ask_reply(self, text: str) -> str:
        if self.ended:
            return ("This run has ended — everything on the canvas is final. "
                    "Start a new run from the two doors whenever you’re ready.")
        done = sum(1 for k in STAGE_ORDER if (k, self._iter[k]) in self._done_stages)
        pending = [q for qid, q in self._questions.items() if qid not in self._resolved]
        if pending:
            kinds = {q.get("kind") for q in pending}
            if "hold" in kinds:
                where = "holding at a stage boundary — the run waits on your Resume, Stop or steer"
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

    async def _propose(self, ask_id: str, proposal: str) -> None:
        self._pc_count += 1
        qid = f"q-pc-{self._pc_count}"
        await self._stream("orchestrator", "Orchestrator",
                           "orch.stop" if proposal == "stop" else "orch.hold",
                           in_reply_to=ask_id)
        await self._await_proposal(qid, proposal)

    async def _await_proposal(self, qid: str, proposal: Optional[str] = None) -> None:
        if proposal is None:
            proposal = self._questions.get(qid, {}).get("proposal", "hold")
        n = int(qid.rsplit("-", 1)[-1])
        res = await self._question(
            qid, "propose_confirm",
            {"proposal": proposal, "n": n,
             "voice": ("Stop this run at the next stage boundary?" if proposal == "stop"
                       else "Hold the run at the next stage boundary?")},
            [
                {"id": "confirm", "kind": "confirm",
                 "label": "Stop the run" if proposal == "stop" else "Confirm hold"},
                {"id": "dismiss", "kind": "dismiss", "label": "Dismiss"},
            ],
        )
        if res.get("choice") == "confirm":
            self._armed = proposal

    # ---- boundaries and holds ------------------------------------------------

    async def _boundary(self, after_key: str) -> None:
        if self._armed == "stop":
            raise _Stopped("Stopped by you — confirmed from the composer")
        if self._armed != "hold":
            return
        self._armed = None
        self._hold_count += 1
        qid = f"q-hold-{self._hold_count}"
        self._stretch_active = False
        res = await self._question(
            qid, "hold",
            {"after_stage": after_key, "after_label": STAGE_LABELS.get(after_key, after_key),
             "n": self._hold_count, "after_pc": f"q-pc-{self._pc_count}",
             "voice": f"Holding after {STAGE_LABELS.get(after_key, after_key)} — the artifact landed whole. "
                      f"Resume, stop, or steer with a note; nothing times out."},
            [
                {"id": "resume", "kind": "resume", "label": "Resume"},
                {"id": "stop", "kind": "stop", "label": "Stop the run"},
                {"id": "steer", "kind": "steer", "label": "Steer", "free": "required",
                 "placeholder": "Tell it what to change — routes to the Interpreter…"},
            ],
        )
        choice = res.get("choice")
        if choice == "stop":
            raise _Stopped("Stopped by you — from the hold")
        if choice in ("steer", "other") or (choice not in ("resume",) and res.get("free_text")):
            await self._stream("orchestrator", "Orchestrator", "orch.steer")
            raise _SteerToSpec(str(res.get("free_text") or ""))
        await self._stream("orchestrator", "Orchestrator", "orch.resume")

    # ---- artifacts for fetch_artifact ---------------------------------------

    def get_artifact(self, name: str) -> Optional[Dict[str, Any]]:
        return self._artifacts.get(name)

    # ---- the run -------------------------------------------------------------

    async def _run(self) -> None:
        try:
            await self._run_script()
        except _Stopped as s:
            self.ended = True
            await self._emit("conductor", "run.ended",
                             {"status": "stopped", "by": "you", "note": s.note})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("scripted run crashed")
            self.ended = True
            await self._emit("conductor", "run.ended",
                             {"status": "error", "note": "the scripted driver hit an internal error"})

    async def _run_script(self) -> None:
        steps: List[Callable[[], Awaitable[None]]] = [
            self._s_open, self._s_intake, self._s_interpret, self._s_gaps,
            self._s_spec_gate, self._s_golden, self._s_design, self._s_configure,
            self._s_assemble, self._s_code_gate, self._s_verify, self._s_human_gate,
        ]
        revise_index = steps.index(self._s_interpret)
        i = 0
        while i < len(steps):
            self._stretch_active = True
            try:
                await steps[i]()
            except _SteerToSpec as steer:
                self._begin_spec_revision(steer.feedback)
                i = revise_index
                continue
            i += 1
        self.ended = True
        await self._emit("conductor", "run.ended",
                         {"status": "approved",
                          "note": "Approved — job, verdict and the signed cell recorded."})

    def _begin_spec_revision(self, feedback: str) -> None:
        self._draft += 1
        self._feedback = feedback
        owner_hit = False
        for key in STAGE_ORDER:
            if key == "interpret":
                owner_hit = True
            if owner_hit and (key, self._iter[key]) in self._done_stages:
                self._iter[key] += 1

    def _begin_code_revision(self, feedback: str) -> None:
        self._feedback = feedback
        self._cells_changed = True
        self._code_round += 1
        owner_hit = False
        for key in STAGE_ORDER:
            if key == "configure":
                owner_hit = True
            if owner_hit and (key, self._iter[key]) in self._done_stages:
                self._iter[key] += 1

    # ---- steps ---------------------------------------------------------------

    async def _s_open(self) -> None:
        if not self._started:
            self._started = True
            await self._emit("conductor", "run.started",
                             {"job": JOB, "door": self._door, "tier": "verified",
                              "brd": BRD if self._door == "brd" else None,
                              "request_text": self._request.get("text"),
                              "itinerary": ITINERARY})
            await self._stream("orchestrator", "Orchestrator",
                               "orch.opening.brd" if self._door == "brd" else "orch.opening.typed")

    async def _s_intake(self) -> None:
        if self._stage_done("intake"):
            return
        await self._stage_started("intake")
        await self._sleep(0.9)
        await self._artifact(
            "intake.json", "intake", {"sources": SOURCES, "door": self._door},
            note=f"Explode · {BRD} → 3 tables, 6 rule paragraphs" if self._door == "brd"
            else "Intake · request + attached sample and expected data",
            stage="intake",
        )
        await self._sleep(0.7)
        await self._stage_completed(
            "intake", note="Doc Normalizer · extract proposed — Normalize · validated clean")
        await self._boundary("intake")

    async def _s_interpret(self) -> None:
        if self._stage_done("interpret"):
            return
        revision = self._iter["interpret"] > 1
        await self._stage_started(
            "interpret",
            **({"directed": True, "feedback": getattr(self, "_feedback", "")} if revision else {}))
        await self._stream("specialist:interpret", "Interpreter",
                           "interp.revise" if revision else "interp.read",
                           stage_label="Interpret")
        gap_res = [
            {"gap_id": g["id"], "resolution": self._resolved.get(f"q-{g['id'].lower()}-r1", {}).get("note")}
            for g in GAPS
        ]
        await self._artifact(
            f"requirement_spec.draft{self._draft}.json", "spec",
            {"draft": self._draft, "sources": SOURCES, "rules": RULES,
             "gaps": GAPS if not revision else [],
             "gap_resolutions": gap_res if revision else [],
             "what_changed": (f"Draft {self._draft}: folded in your note — "
                              f"{getattr(self, '_feedback', '')[:120]}" if revision else None)},
            note=f"Interpreter · requirement_spec draft {self._draft}",
            stage="interpret",
        )
        # Interpret completes at spec-gate entry: elicitation belongs to the
        # interpreter (04), so the stage stays active through the gap round.

    async def _s_gaps(self) -> None:
        if self._iter["interpret"] > 1:
            return  # scripted revisions surface no new gaps; 13's minimal re-entry
        await self._stream("orchestrator", "Orchestrator", "orch.questions")
        waits = []
        for g in GAPS:
            qid = f"q-{g['id'].lower()}-r1"
            waits.append(self._question(
                qid, "gap",
                {"gap_id": g["id"], "rule_id": g["rule"], "severity": g["severity"],
                 "prompt": g["prompt"], "free_prompt": g["free_prompt"],
                 "round_id": "r1", "round": {"k": 1, "n": 3}},
                g["options"],
            ))
        await asyncio.gather(*waits)

    async def _s_spec_gate(self) -> None:
        while True:
            if not self._stage_done("interpret"):
                await self._stage_completed("interpret")
            gap_res = [
                {"gap_id": g["id"],
                 "note": self._resolved.get(f"q-{g['id'].lower()}-r1", {}).get("note", "")}
                for g in GAPS
            ]
            spec_artifact = self._artifacts.get(f"requirement_spec.draft{self._draft}.json", {})
            what_changed = (spec_artifact.get("fields") or {}).get("what_changed")
            res = await self._question(
                f"q-spec-d{self._draft}", "spec_gate",
                {"draft": self._draft, "job": JOB,
                 "summary": {"sources": len(SOURCES), "rules": len(RULES)},
                 "gap_resolutions": gap_res, "what_changed": what_changed,
                 "voice": ("The spec is complete: six rules, your two answers recorded. "
                           "Signing it fixes what the job must do — every later stage builds on it."
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
                return
            self._begin_spec_revision(str(res.get("free_text") or ""))
            await self._s_interpret()

    async def _s_golden(self) -> None:
        await self._stream("orchestrator", "Orchestrator", "orch.signed")
        await self._artifact("golden/", "golden", {"outputs": 1, "tier": "verified"},
                             note="Materializer · wrote golden/ — tier verified")
        await self._boundary("interpret")

    async def _s_design(self) -> None:
        if self._stage_done("design"):
            return
        condensed = self._iter["design"] > 1
        await self._stage_started("design")
        if not condensed:
            await self._stream("specialist:design", "Flow Designer", "flow.design",
                               stage_label="Design")
        await self._artifact(
            "flow.json", "flow", {"nodes": NODES, "edges": EDGES},
            note="Flow Designer · 10 components, 9 flows", stage="design")
        await self._stage_completed("design")
        if not condensed:
            await self._stream("orchestrator", "Orchestrator", "orch.flow")
        await self._boundary("design")

    async def _s_configure(self) -> None:
        if self._stage_done("configure"):
            return
        condensed = self._iter["configure"] > 1
        await self._stage_started("configure",
                                  **({"directed": True, "feedback": getattr(self, "_feedback", "")}
                                     if condensed and self._cells_changed else {}))
        node_ids = [n["id"] for n in NODES]
        if condensed:
            await self._stream("specialist:configure", "Configurator", "config.revise",
                               stage_label="Configure")
            for nid in node_ids:
                await self._progress(nid, "configured")
            await self._stage_completed(
                "configure", note="Configurator · revision applied — validate loop clean")
            await self._boundary("configure")
            return
        for nid in node_ids[:4]:
            await self._progress(nid, "active")
            await self._sleep(0.55)
            await self._progress(nid, "configured")
        await self._progress("join_accounts", "active")
        await self._stream("specialist:configure", "Configurator", "config.main",
                           stage_label="Configure")
        await self._progress("join_accounts", "configured")
        await self._progress("join_prices", "active")
        finish = await self._stream("specialist:configure", "Configurator", "config.rate",
                                    stage_label="Configure")
        if finish == "rate_limited":
            await self._stream("specialist:configure", "Configurator", "config.retry",
                               stage_label="Configure")
        await self._progress("join_prices", "configured")
        for nid in ("validate_date", "derive_mv", "sort_mv", "out_positions"):
            await self._progress(nid, "active")
            await self._sleep(0.5)
            await self._progress(nid, "configured")
        await self._emit("conductor", "stage.loop_attempt",
                         {"stage": "configure", "k": 2, "n": 3,
                          "note": "validate loop · run 1: sort_type missing → fixed · run 2: clean"})
        await self._stage_completed(
            "configure", note="Configurator · 10/10 configured — validate loop clean on attempt 2")
        await self._boundary("configure")

    async def _s_assemble(self) -> None:
        if self._stage_done("assemble"):
            return
        await self._stage_started("assemble")
        await self._sleep(0.8)
        await self._artifact(
            "job.json", "job", {"components": 10, "flows": 9},
            note="Assembler · job assembled — 10 components, 9 flows", stage="assemble")
        await self._stage_completed("assemble")
        await self._boundary("assemble")

    async def _s_code_gate(self) -> None:
        if not self._cells_changed:
            return  # 04's re-pause rule: only new or changed cells re-raise the gate
        await self._stream("orchestrator", "Orchestrator", "orch.gate")
        while True:
            cell = CODE_CELL_REVISED if self._code_round > 1 else CODE_CELL
            res = await self._question(
                f"q-code-r{self._code_round}", "code_gate",
                {"round": self._code_round,
                 "cells": [dict(cell, changed=self._code_round > 1, new=self._code_round == 1)],
                 "note": "Re-raising changed cells only" if self._code_round > 1 else None,
                 "voice": (ORCH["gate"] if self._code_round == 1 else
                           "The cell is rewritten to your note — same one step, new exact code. "
                           "Approve it to run.")},
                [
                    {"id": "approve", "kind": "approve", "label": "Approve and run"},
                    {"id": "request_changes", "kind": "reject", "label": "Request changes",
                     "free": "required", "placeholder": "What should change in this cell…"},
                ],
            )
            if res.get("choice") == "approve":
                self._cells_changed = False
                return
            self._begin_code_revision(str(res.get("free_text") or ""))
            await self._s_configure()
            await self._s_assemble()

    async def _s_verify(self) -> None:
        if self._stage_done("verify"):
            return
        first_pass = self._iter["verify"] == 1
        await self._stage_started("verify")
        if first_pass:
            await self._sleep(1.1)
            await self._artifact("runs/run-1", "test_run",
                                 note="Test Runner · run 1 — 2 rows out of order", stage="verify")
            await self._stream("specialist:verify", "Diagnostician", "diag.run",
                               stage_label="Verify")
            await self._artifact("diagnosis.json", "diagnosis",
                                 {"owner": "Configurator", "fix": "sort_type = num"},
                                 note="Diagnostician · owner: Configurator — sort compares as text",
                                 stage="verify")
            await self._emit("conductor", "stage.loop_attempt",
                             {"stage": "verify", "k": 2, "n": 3,
                              "note": "repair 2 of 3 · Configurator re-ran · sort_type = num"})
            await self._sleep(1.0)
            await self._artifact("runs/run-2", "test_run",
                                 note="Test Runner · run 2 — clean", stage="verify")
        else:
            await self._sleep(1.0)
            await self._artifact(f"runs/rerun-{self._iter['verify']}", "test_run",
                                 note="Test Runner · run 1 — clean · output re-graded 4/4",
                                 stage="verify")
        await self._stage_completed("verify")
        await self._boundary("verify")

    async def _s_human_gate(self) -> None:
        first = self._human_round == 1
        await self._stream("orchestrator", "Orchestrator",
                           "orch.verdict" if first else "orch.reverdict")
        while True:
            res = await self._question(
                f"q-human-r{self._human_round}", "human_gate",
                {"round": self._human_round, "verdict": "verified", "matched": "4/4",
                 "runs": {"k": 2 if first else 1, "n": 3}, "tier": "verified",
                 "table": VERDICT_TABLE,
                 "diagnosis": ("run 1 mis-sorted — Diagnostician: owner Configurator · "
                               "fix: sort_type = num · 1/1 outputs graded" if first else
                               "revision re-verified — clean · 1/1 outputs graded"),
                 "voice": "Job, verdict, and the one signed cell — ready for your approval. "
                          "Nothing auto-approves."},
                [
                    {"id": "approve", "kind": "approve", "label": "Approve job"},
                    {"id": "request_changes", "kind": "reject", "label": "Request changes",
                     "free": "required", "placeholder": "What’s wrong with the output…"},
                    {"id": "stop", "kind": "stop", "label": "Stop"},
                ],
            )
            choice = res.get("choice")
            if choice == "approve":
                return
            if choice == "stop":
                raise _Stopped("Stopped by you — at the human gate")
            self._human_round += 1
            raise _SteerToSpec(str(res.get("free_text") or ""))
