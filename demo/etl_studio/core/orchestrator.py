"""LLM orchestrator: the agent that fronts the run (ticket 05's second
layer, built by ticket 18 on ticket 16's chassis and ticket 17's knowledge
machinery).

One persistent per-run conversation, one voice. The conductor feeds it the
run's event lines (its context feed, rebuilt from audit + bus after a
crash) and enqueues turns at fixed moments; a single worker task runs them
strictly in order, so prose stays sequential while the walk never waits --
``narrate`` returns immediately and the next stage starts while the words
stream (05: non-blocking narration, ~12 turns per run).

Turn kinds:

- Narration (``narrate``): journal-guarded, walk-anchored -- a crash-restore
  re-walk skips turns the journal already holds.
- Composer (``ask``): the human typed into the composer. The turn answers
  grounded in the run (bus read tools), or -- when the text is an
  instruction to pause/stop the BUILD -- calls ``propose_control``: the
  conductor raises the propose-confirm card, the human confirms, the
  conductor executes (13: composer-only interruption; the orchestrator has
  zero authority to act silently). Never journal-guarded: conversation is
  not part of the deterministic walk.
- Escalation (``escalate``): awaited -- the walk is already stopped on the
  unplanned failure; the streamed explanation becomes the card's voice.

Reword boundary (05): the model restyles prose only; options, ids, field
names, code and data values render verbatim from conductor-authored cards
and artifacts, and the return path (answers, approvals) never passes
through the model.

Provider routing: live when the run resolved a live provider (the
orchestrator joined LIVE_SLOTS on this ticket); otherwise the scripted
double plays the ``orch.*`` fixture labels -- same labels, same wire, the
webview unchanged.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from . import knowledge
from .llm import LlmCall
from .port import ChatMessage, ToolDecl

if TYPE_CHECKING:  # pragma: no cover -- typing only, no runtime cycle
    from .conductor import Conductor

logger = logging.getLogger(__name__)

HISTORY_CAP = 60  # messages kept verbatim; the event digest carries the rest
_READ_CAP_CHARS = 8000  # bounded artifact reads (tool_result rides the wire)

SYSTEM_PROMPT = """You are the Orchestrator of ETL Studio -- the one voice that speaks to the human \
while a build runs. Under you a deterministic conductor sequences code stages and LLM specialists \
(Interpreter, Flow Designer, Configurator, Assembler, Diagnostician); their work reaches the human \
as observed windows and canvas artifacts, never as speech. You front the run: you narrate its real \
transitions, answer the human's questions, and propose -- never execute -- control moves.

GROUND RULES (non-negotiable):
- Everything you say must be traceable to THIS run: the event lines you receive, the artifacts you
  read through your tools, and the knowledge below. Never invent progress, results, values or
  reasons. If you do not know, read the artifact; if you still do not know, say so plainly.
- Reword boundary: restyle prose freely, but option labels, ids, field names, file names, code and
  data values are quoted VERBATIM when you mention them -- never paraphrase an identifier or value.
- You never sequence the pipeline. The conductor decides what runs next; nothing you say changes
  the itinerary, and you never speak for a specialist.
- You have zero authority to act. Hold and stop are PROPOSALS through the propose_control tool: a
  card asks the human to confirm and the conductor executes. You may always propose a stop. Never
  claim a move happened because you proposed it.
- The machine records the human's answers, approvals and rejections -- not you. Do not restate
  their choices back as if recording them.

STYLE: calm, concrete, present tense; one to three short sentences unless the human asks for
depth. A colleague at the table, not an announcer. State failures as calmly as successes. No
markdown headings; no bullet lists unless listing is genuinely clearer. VARY your wording:
never reuse a sentence shape you already used this run (your prior turns are in this
conversation -- check them), and anchor each line in a concrete particular of the moment
when one exists (a count, a component name, a rule id, a value) rather than a generic
status line. Template-sounding narration reads as canned even when it is not.

WHEN THE HUMAN TYPES TO YOU (a composer message):
- A question: answer it from the run's real state -- use read_artifact / list_artifacts when the
  answer lives in an artifact; keep the answer specific to this run.
- An instruction to pause, hold or stop the BUILD: call propose_control with the action and a
  one-line note, then tell them the confirm card is up and what confirming does (it takes effect
  at the next stage boundary; in-flight work lands whole).
- Steering content (what the JOB should do differently) is not yours to route: point them at the
  steer / Request-changes affordances on the cards -- steer text revises the spec through the
  Interpreter."""

# Per-moment narration instructions (the live path's turn tail; the scripted
# double plays the orch.* fixture for the same label instead).
_MOMENTS: Dict[str, str] = {
    "opening.brd": (
        "The build just started through the BRD door. In one or two sentences tell the human "
        "what happens now: the document is exploded and read, you interpret it into a spec, and "
        "anything unclear becomes a question to them -- never an assumption."),
    "opening.typed": (
        "The build just started from the human's typed request. In one or two sentences: the "
        "request is interpreted into a spec, and anything unclear becomes a question to them -- "
        "never an assumption."),
    "questions": (
        "A round of clarifying questions is going up to the human as cards. Briefly frame it: "
        "their answers complete the spec, and each card is pinned to the rule it blocks. Do not "
        "restate the questions themselves."),
    "signed": (
        "The spec was just signed. Say what that fixes and what happens next in one or two "
        "sentences (golden data is materialized where the run has data, then the flow is "
        "designed)."),
    "flow": (
        "The flow design just landed as an artifact. Describe its shape in one breath from the "
        "real facts (read flow.json if you need detail). Configuration of each step comes next."),
    "gate": (
        "The code gate is rising: generated code needs the human's approval before anything "
        "runs. Say so plainly -- the exact cell is on the canvas."),
    "verdict": (
        "The verification verdict just landed (the event lines carry it; read feedback.json or "
        "the run reports if needed). Give the honest one-breath summary -- what was graded, what "
        "happened, what stands open."),
    "reverdict": (
        "Verification ran again after the human's revision. Give the honest one-breath summary "
        "of the re-run."),
    "steer": (
        "The human just steered with a note. Explain the route in one sentence: the note revises "
        "the spec through the Interpreter, they re-sign it, and the stages after it re-run."),
    "resume": (
        "The hold was just resumed. One short sentence -- the build picks up exactly where it "
        "held."),
}


def _sections(slices: Dict[str, str]) -> str:
    return "\n\n".join(f"<knowledge name=\"{name}\">\n{body}\n</knowledge>"
                       for name, body in slices.items())


@dataclass
class _Turn:
    label: str  # stream label + the double's fixture key ("orch.*")
    instruction: str  # live-path turn tail
    scripted_prompt: str = ""  # scripted-path prompt (echo composition)
    in_reply_to: Optional[str] = None
    offer_propose: bool = False
    journal_guarded: bool = True
    done: Optional[asyncio.Future] = None  # resolves with the streamed text


class Orchestrator:
    """The conductor's speaking layer. It reads the run through the
    conductor (feed, bus, models, runner) and owns nothing but its
    conversation -- the bus and the journal stay the state of record."""

    def __init__(self, conductor: "Conductor"):
        self._c = conductor
        self._queue: "asyncio.Queue[_Turn]" = asyncio.Queue()
        self._worker: Optional[asyncio.Task] = None
        self._history: List[ChatMessage] = []
        self._feed_pos = 0
        self._pending = 0  # queued + speaking turns (the boundary dwell waits on this)
        self._slices = knowledge.slices_for("orchestrator")

    async def drained(self, timeout: float) -> None:
        """Boundary dwell (ticket 21): wait until every queued turn has
        spoken, capped -- the walk pauses for the voice to land, never
        blocks on prose for long. Journal-skipped turns drain instantly."""
        deadline = asyncio.get_running_loop().time() + timeout
        while self._pending > 0 and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.05)

    # ---- the conductor's surface ---------------------------------------------

    def narrate(self, moment: str) -> None:
        """Enqueue one narration turn and return immediately (05: the next
        stage starts now; prose streams alongside)."""
        self._enqueue(_Turn(label=f"orch.{moment}", instruction=_MOMENTS[moment]))

    def ask(self, ask_id: str, text: str) -> None:
        """One composer message. The keyword hint picks the stream/fixture
        LABEL only -- whether a proposal card rises is the model's call (it
        does or does not invoke propose_control; the scripted double scripts
        that decision in the label's fixture)."""
        hint = self._c.intent_hint(text)
        label = {"hold": "orch.hold", "stop": "orch.stop"}.get(hint or "", "orch.ask")
        self._enqueue(_Turn(
            label=label,
            instruction=(
                "The human typed this into the composer:\n---\n" + text + "\n---\n"
                "Reply to them directly (your reply threads under their message). Answer from "
                "the run's real state -- read artifacts when the answer lives in one. If this "
                "is an instruction to hold/pause or stop the BUILD, call propose_control "
                "instead of promising anything."),
            scripted_prompt=self._c.compose_ask_reply(text),
            in_reply_to=ask_id,
            offer_propose=True,
            journal_guarded=False,
        ))

    async def escalate(self, slot: str, taxonomy: str, message: str) -> str:
        """An unplanned failure (05: stop and ask, never silently act).
        Streams the explanation and returns its text for the card's voice;
        empty when the journal already held the stream (crash re-walk)."""
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._enqueue(_Turn(
            label="orch.escalate",
            instruction=(
                f"Unplanned failure: the {slot} stage failed for good this walk "
                f"({taxonomy}: {message}) -- its bounded retries are spent. In one or two "
                "sentences tell the human what you see and propose the move: they can stop the "
                "build here, or dismiss and let it try once more. A confirm card with exactly "
                "those options follows your words -- do not invent other options, and do not "
                "call propose_control (the card is already coming)."),
            done=fut,
        ))
        return await fut

    def dispose(self) -> None:
        if self._worker is not None and not self._worker.done():
            self._worker.cancel()

    # ---- the worker (one voice: turns run strictly in order) -----------------

    def _enqueue(self, turn: _Turn) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.get_running_loop().create_task(self._run_worker())
        self._pending += 1
        self._queue.put_nowait(turn)

    async def _run_worker(self) -> None:
        while True:
            turn = await self._queue.get()
            try:
                await self._run_turn(turn)
            except asyncio.CancelledError:
                if turn.done is not None and not turn.done.done():
                    turn.done.set_result("")
                raise
            except Exception as e:  # noqa: BLE001 -- prose must never kill the walk
                logger.warning("[orchestrator] %s turn failed: %s", turn.label, e)
                if turn.done is not None and not turn.done.done():
                    turn.done.set_result("")
            finally:
                self._pending -= 1

    async def _run_turn(self, turn: _Turn) -> None:
        live = self._c.orchestrator_live()
        events = self._consume_feed()
        user = self._compose_user(events, turn)
        capture: List[str] = []
        tools, decls = self._tools(turn)
        call = LlmCall(
            source="orchestrator",
            who="Orchestrator",
            label=turn.label,
            in_reply_to=turn.in_reply_to,
            tools=tools,
            tool_decls=decls,
            model=await self._c.orchestrator_model(),
            live=live,
            capture=capture,
            journal_guarded=turn.journal_guarded,
        )
        if live:
            call.messages = (
                [ChatMessage(role="system", text=self._system())]
                + list(self._history)
                + [ChatMessage(role="user", text=user)]
            )
        else:
            # The double plays the label's fixture; echo_prompt fixtures
            # stream this composed, state-grounded reply.
            call.prompt = turn.scripted_prompt
        await self._c.runner().run(call)
        text = "".join(capture).strip()
        # The conversation stays real in both paths: what streamed is what
        # was said. A journal-skipped turn captures nothing -- its events
        # stay in history so the next live turn still knows them.
        self._history.append(ChatMessage(role="user", text=user))
        if text:
            self._history.append(ChatMessage(role="assistant", text=text))
        if len(self._history) > HISTORY_CAP:
            del self._history[: len(self._history) - HISTORY_CAP]
        if turn.done is not None and not turn.done.done():
            turn.done.set_result(text)

    # ---- context assembly ----------------------------------------------------

    def _system(self) -> str:
        return SYSTEM_PROMPT + "\n\n" + _sections(self._slices)

    def _consume_feed(self) -> List[Dict[str, str]]:
        feed = self._c.orchestrator_context()
        events = feed[self._feed_pos:]
        self._feed_pos = len(feed)
        return events

    @staticmethod
    def _compose_user(events: List[Dict[str, str]], turn: _Turn) -> str:
        parts = []
        if events:
            parts.append("Run events since your last turn:\n"
                         + "\n".join(f"- {e['text']}" for e in events))
        parts.append(turn.instruction)
        return "\n\n".join(parts)

    # ---- tools (11's matrix row: run artifacts; 13: propose_control) ---------

    def _tools(self, turn: _Turn):
        tools: Dict[str, Any] = {
            "list_artifacts": self._list_artifacts,
            "read_artifact": self._read_artifact,
        }
        decls = [
            ToolDecl(
                "list_artifacts",
                "List this run's artifacts on the bus (name, kind, stage, note)",
                {"type": "object", "properties": {}},
            ),
            ToolDecl(
                "read_artifact",
                "Read one run artifact by its canonical name (bounded; read-only)",
                {"type": "object", "properties": {"name": {"type": "string"}},
                 "required": ["name"]},
            ),
        ]
        if turn.offer_propose:
            tools["propose_control"] = self._c.handle_propose_tool
            decls.append(ToolDecl(
                "propose_control",
                "Propose holding or stopping the build. Raises a confirm card; the human "
                "confirms and the conductor executes at the next stage boundary. Never "
                "acts by itself.",
                {"type": "object", "properties": {
                    "action": {"type": "string", "enum": ["hold", "stop"]},
                    "note": {"type": "string",
                             "description": "One-line proposal shown on the card"},
                }, "required": ["action"]},
            ))
        return tools, decls

    async def _list_artifacts(self, _args: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "artifacts": self._c.bus.artifacts()}

    async def _read_artifact(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = str(args.get("name", ""))
        artifact = self._c.get_artifact(name)
        if artifact is None:
            return {"ok": False, "note": f"no artifact named {name!r} on the bus"}
        raw = json.dumps(artifact, ensure_ascii=True)
        if len(raw) > _READ_CAP_CHARS:
            return {"ok": True, "artifact_text": raw[:_READ_CAP_CHARS], "truncated": True}
        return {"ok": True, "artifact": artifact}
