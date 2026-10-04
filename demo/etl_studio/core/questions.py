"""Question channel: all nine question kinds on one raised -> resolved
lifecycle (tickets 02/04/05/08/13, built in ticket 16).

Kinds: gap, needs_human, spec_gate, code_gate, exhaustion, owner_human,
human_gate, propose_confirm, hold. Every question is conductor-authored
structured options; NO timeout exists anywhere; a pending question is state
(it replays on attach and survives crash-restarts). The resolution is one
generic shape -- {question_id, choice, free_text?} -- recorded untouched:
no model ever sits in the return path (ticket 05's reword boundary).

The resolution *note* is deterministic presentation the feed chips render;
ticket 18's orchestrator may later restyle prose around it but never the
choice itself.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

Emit = Callable[[str, str, Dict[str, Any]], Awaitable[None]]

QUESTION_KINDS = (
    "gap", "needs_human", "spec_gate", "code_gate", "exhaustion",
    "owner_human", "human_gate", "propose_confirm", "hold",
)


class QuestionChannel:
    def __init__(self, emit: Emit, audit: Optional[Callable[..., None]] = None,
                 feed: Optional[Callable[[str, str], None]] = None):
        self._emit = emit
        self._audit = audit or (lambda *a, **k: None)
        # Ticket 18: the orchestrator's live context feed -- lines match the
        # conductor's audit-rebuilt feed exactly, so a crash-restored
        # conversation sees the same history a live one accumulated.
        self._feed = feed or (lambda *a: None)
        self.raised: Dict[str, Dict[str, Any]] = {}  # qid -> raised payload
        self.resolved: Dict[str, Dict[str, Any]] = {}  # qid -> resolution
        self._waiters: Dict[str, asyncio.Future] = {}

    # ---- ask / resolve ---------------------------------------------------------

    async def ask(
        self,
        qid: str,
        kind: str,
        payload: Dict[str, Any],
        options: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Raise a question (journal-idempotent) and block until its answer."""
        if qid in self.resolved:
            return self.resolved[qid]
        if qid not in self.raised:
            raised = {"question_id": qid, "kind": kind, "options": options, **payload}
            self.raised[qid] = raised
            await self._emit("conductor", "question.raised", raised)
            self._audit("conductor", "question_raised", {"question_id": qid, "kind": kind})
            self._feed("question_raised", f"question raised: {kind} {qid}")
        fut = asyncio.get_running_loop().create_future()
        self._waiters[qid] = fut
        try:
            return await fut
        finally:
            self._waiters.pop(qid, None)

    async def resolve(self, params: Dict[str, Any]) -> None:
        """Record a human answer untouched and release the waiter."""
        qid = str(params.get("question_id", ""))
        q = self.raised.get(qid)
        if q is None or qid in self.resolved:
            logger.warning("answer for unknown/resolved question %s ignored", qid)
            return
        choice = str(params.get("choice", ""))
        # Options are conductor-authored: a choice outside them is out of
        # contract (e.g. approve on a red verdict, where Approve was never
        # offered). The question stays pending -- nothing times out.
        allowed = {str(o.get("id")) for o in q.get("options", [])} | {"other"}
        if choice not in allowed:
            logger.warning("answer %r not among question %s options; ignored",
                           choice, qid)
            return
        free_text = params.get("free_text")
        resolution: Dict[str, Any] = {
            "question_id": qid,
            "kind": q.get("kind"),
            "choice": choice,
            "free_text": free_text,
            "note": self._resolution_note(q, choice, free_text),
        }
        if q.get("kind") == "gap":
            resolution["round_id"] = q.get("round_id")
            resolution["gap_id"] = q.get("gap_id")
        self.resolved[qid] = resolution
        await self._emit("conductor", "question.resolved", resolution)
        self._audit(
            "human", "question_resolved",
            {"question_id": qid, "kind": q.get("kind"), "choice": choice,
             "free_text": free_text},
        )
        self._feed("question_resolved", f"human resolved {qid}: {choice}")
        fut = self._waiters.get(qid)
        if fut is not None and not fut.done():
            fut.set_result(resolution)

    # ---- state views -------------------------------------------------------------

    def pending(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        out = []
        for qid, q in self.raised.items():
            if qid in self.resolved:
                continue
            if kind is None or q.get("kind") == kind:
                out.append(q)
        return out

    def is_pending(self, qid: str) -> bool:
        return qid in self.raised and qid not in self.resolved

    # ---- restore (journal is the state) --------------------------------------------

    def restore_raised(self, payload: Dict[str, Any]) -> None:
        qid = str(payload.get("question_id", ""))
        if qid:
            self.raised[qid] = payload

    def restore_resolved(self, payload: Dict[str, Any]) -> None:
        qid = str(payload.get("question_id", ""))
        if qid:
            self.resolved[qid] = payload

    # ---- deterministic resolution notes ----------------------------------------------

    @staticmethod
    def _option_label(q: Dict[str, Any], choice: str) -> str:
        for o in q.get("options", []):
            if o.get("id") == choice:
                return str(o.get("label", choice))
        return choice

    def _resolution_note(self, q: Dict[str, Any], choice: str, free_text: Any) -> str:
        kind = q.get("kind")
        label = self._option_label(q, choice)
        text = str(free_text or "").strip()
        if kind == "gap":
            gap = q.get("gap_id", "")
            if choice == "waive":
                return f"{gap}: waived — default applies, recorded on the spec"
            if choice == "other" and text:
                return f"{gap}: {text}"
            if text and choice not in ("", "other"):
                return f"{gap}: {label} — {text[:80]}"
            return f"{gap}: {label}"
        if kind == "needs_human":
            src = q.get("source", "extraction")
            return f"{src}: {text[:80] if choice == 'other' and text else label}"
        if kind == "spec_gate":
            draft = q.get("draft", 1)
            return (f"Spec draft {draft} — signed" if choice == "approve"
                    else f"Spec draft {draft} — changes requested")
        if kind == "code_gate":
            cells = q.get("cells", [])
            n = len(cells)
            if choice == "approve":
                return f"Code gate — {n} cell{'s' if n != 1 else ''} approved"
            first = str(cells[0].get("id", "the cell")) if cells else "the cell"
            return f"Code gate — changes requested on {first}"
        if kind == "exhaustion":
            loop = q.get("loop", "repair")
            if choice == "grant":
                return f"Granted — {q.get('grant_size', 3)} more {loop} passes"
            if choice == "stop_to_gate":
                return "Stopped to the gate — the verdict stands as-is"
            return f"Steered — routes to the Interpreter: {text[:80]}" if text else "Steered — routes to the Interpreter"
        if kind == "owner_human":
            return f"Owner: you — {text[:80] if text else label}"
        if kind == "human_gate":
            return {"approve": "Job approved — verdict and the signed cell recorded",
                    "request_changes": "Verdict — changes requested, spec door",
                    "stop": "Build stopped at the human gate"}.get(choice, label)
        if kind == "hold":
            if choice == "resume":
                return "Hold — resumed"
            if choice == "stop":
                return "Hold — stopped"
            return f"Hold — steered: {text[:80]}" if text else "Hold — steered"
        if kind == "propose_confirm":
            proposal = q.get("proposal", "hold")
            if choice == "confirm":
                return ("Hold armed — takes effect at the next stage boundary"
                        if proposal == "hold"
                        else "Stop confirmed — the build ends at the next boundary")
            return "Dismissed — the build continues"
        return label
