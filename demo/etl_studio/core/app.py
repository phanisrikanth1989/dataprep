"""ETL Studio core app (tickets 10 + 15 + 16).

Owns the 08 contract surface: attach/replay, the run/stage/question/stream/
health families, ``command.start_run`` / ``answer`` / ``command.ask`` /
``fetch_artifact``, and per-run journals. Runs are driven by the real
conductor (ticket 16) over the real stages (tickets 17 + 19 -- doors,
specialists, and the verification spine); ``fetch_artifact`` serves full
artifacts from the run's bus.

The ``skeleton.*`` handlers from ticket 10 stay as dev/smoke affordances --
ping, LM echo through the live provider resolution, cancel, crash. Their
events land in a "skeleton" session journaled at the work-dir root, exactly
where the walking skeleton kept it.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .conductor import Conductor
from .envelope import PROTOCOL_VERSION, Envelope, now_ts
from .journal import UiJournal
from .models import ModelConfig
from .port import (
    ChatMessage,
    ChatRequest,
    ModelInfo,
    ModelNotFound,
    ProviderError,
    ProviderPort,
    RequestCanceled,
)
from .real_stages import JOB, build_stages
from .rpc import JsonRpcConnection

logger = logging.getLogger(__name__)

SKELETON_RUN_ID = "skeleton"


class RunSession:
    """One run's identity + journal (fresh journal per run, ticket 08)."""

    def __init__(self, run_id: str, journal_path: Path, job: Optional[str] = None):
        self.run_id = run_id
        self.job = job
        self.journal = UiJournal(journal_path)

    def close(self) -> None:
        self.journal.close()


class StudioApp:
    def __init__(
        self,
        conn: JsonRpcConnection,
        work_dir: Path,
        primary: ProviderPort,
        primary_name: str,
        fallback: Optional[ProviderPort] = None,
        scripted_port: Optional[ProviderPort] = None,
        pace: float = 1.0,
        model_config: Optional[ModelConfig] = None,
    ):
        self._conn = conn
        self._work_dir = work_dir
        self._primary = primary
        self._primary_name = primary_name
        self._fallback = fallback
        # Stub-specialist runs play through the double (tickets 15/16); the
        # live per-stage providers arrive with the real specialists (17/18).
        self._scripted_port = scripted_port or fallback or primary
        self._pace = pace
        self._model_config = model_config or ModelConfig()
        self._resolved: Optional[Tuple[ProviderPort, str, List[ModelInfo]]] = None
        self._streams: Dict[str, asyncio.Task] = {}
        self._session: Optional[RunSession] = None
        self._driver: Optional[Conductor] = None
        # Boot restore may suspend on the live-provider round trip (17); the
        # wire handlers hold until it settles so a racing command can never
        # swap the session out from under it.
        self._ready = asyncio.Event()

        conn.on_request("attach", self._on_attach)
        conn.on_request("fetch_artifact", self._on_fetch_artifact)
        conn.on_notification("command.start_run", self._on_start_run)
        conn.on_notification("command.ask", self._on_ask)
        conn.on_notification("answer", self._on_answer)
        conn.on_notification("skeleton.ping", self._on_ping)
        conn.on_notification("skeleton.echo", self._on_echo)
        conn.on_notification("skeleton.cancel", self._on_cancel)
        conn.on_notification("skeleton.crash", self._on_crash)

    # ---- event emission ------------------------------------------------------

    async def _emit(
        self, session: RunSession, source: str, type_: str, payload: Dict[str, Any]
    ) -> None:
        env = Envelope(
            seq=session.journal.next_seq(),
            ts=now_ts(),
            run_id=session.run_id,
            source=source,
            type=type_,
            payload=payload,
        ).to_dict()
        session.journal.append(env)
        await self._conn.notify("ui/event", env)

    # ---- sessions ------------------------------------------------------------

    def _skeleton_session(self) -> RunSession:
        if self._session is None or self._session.run_id != SKELETON_RUN_ID:
            if self._session is None:
                self._session = RunSession(
                    SKELETON_RUN_ID, self._work_dir / "ui_journal.jsonl"
                )
        return self._session

    def _new_run_session(self) -> RunSession:
        existing = [
            p.name
            for p in self._work_dir.glob(f"{JOB}-r*")
            if p.is_dir() and re.fullmatch(rf"{re.escape(JOB)}-r\d+", p.name)
        ]
        k = 1 + max(
            (int(name.rsplit("r", 1)[-1]) for name in existing), default=0
        )
        run_id = f"{JOB}-r{k}"
        return RunSession(run_id, self._work_dir / run_id / "ui_journal.jsonl", job=JOB)

    # ---- boot restore (ticket 08: the journal owns the run) ------------------

    async def restore_at_boot(self) -> None:
        try:
            await self._restore_at_boot()
        finally:
            self._ready.set()

    async def _restore_at_boot(self) -> None:
        candidates: List[Path] = []
        root = self._work_dir / "ui_journal.jsonl"
        if root.exists():
            candidates.append(root)
        candidates.extend(sorted(self._work_dir.glob("*/ui_journal.jsonl")))
        if not candidates:
            return
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        if latest == root:
            self._session = RunSession(SKELETON_RUN_ID, root)
            logger.info("resumed skeleton session at seq %d", self._session.journal.last_seq)
            return
        run_id = latest.parent.name
        self._session = RunSession(run_id, latest, job=JOB)
        events = self._session.journal.replay_since(0)
        started = any(e.get("type") == "run.started" for e in events)
        if not started:
            return
        session = self._session

        async def emit(source: str, type_: str, payload: Dict[str, Any]) -> None:
            await self._emit(session, source, type_, payload)

        # A finished run never issues live calls, so it skips the provider
        # round trip entirely (it only serves attach/fetch from the journal).
        ended = any(e.get("type") == "run.ended" for e in events)
        live = None if ended else await self._resolve_live(session)
        # Door and request are recovered inside restore() from the run's own
        # audit trail (the bus + audit own the run; the journal owns the seq).
        driver = self._new_conductor(emit, run_id, door="typed", request={}, live=live)
        driver.restore(events)
        self._driver = driver
        if driver.ended:
            logger.info("resumed finished run %s at seq %d", run_id, session.journal.last_seq)
            return
        await self._emit(session, "conductor", "run.crash_restored",
                         {"note": "The core restarted; the build continues from the journal."})
        driver.resume()
        logger.info("crash-restored run %s at seq %d", run_id, session.journal.last_seq)

    async def _resolve_live(
        self, session: RunSession
    ) -> Optional[Tuple[ProviderPort, str]]:
        """The run's live provider (ticket 17): the primary adapter when it
        answers with models; the announced double fallback otherwise. With
        --provider double there is no live leg at all.

        Hard-bounded: on a cold editor start the lm/listModels round trip can
        stall while the provider extension is still activating -- an unbounded
        await here froze the whole wire (attach and start_run both gate on
        it), which read as dead clicks on a clickable idle screen (first live
        session). A stall now falls back, announced, and the run proceeds."""
        if self._primary is self._scripted_port:
            return None
        reason: Optional[str] = None
        try:
            models = await asyncio.wait_for(self._primary.list_models(), timeout=8.0)
            if models:
                return (self._primary, self._primary_name)
            reason = "provider returned no models"
        except asyncio.TimeoutError:
            reason = "live provider did not answer within 8s (still activating?)"
        except ProviderError as e:
            reason = f"{type(e).__name__}: {e}"
        await self._emit(
            session, "conductor", "health.provider_fallback",
            {"from": self._primary_name, "to": "double", "reason": reason},
        )
        logger.warning("run provider fallback: %s -> double (%s)",
                       self._primary_name, reason)
        return None

    def _new_conductor(
        self, emit: Any, run_id: str, door: str, request: Dict[str, Any],
        live: Optional[Tuple[ProviderPort, str]] = None,
    ) -> Conductor:
        return Conductor(
            emit,
            self._scripted_port,
            "double",
            run_id,
            JOB,
            door,
            request,
            run_dir=self._work_dir / run_id,
            stages=build_stages(),
            model_config=self._model_config,
            pace=self._pace,
            live_port=live[0] if live else None,
            live_provider=live[1] if live else "",
        )

    # ---- attach / replay -----------------------------------------------------

    async def _on_attach(self, params: Any) -> Dict[str, Any]:
        await self._ready.wait()
        since = int((params or {}).get("since_seq", 0) or 0)
        if self._session is None:
            logger.info("attach with no session -> idle")
            return {"v": PROTOCOL_VERSION}
        events = self._session.journal.replay_since(since)
        logger.info("attach since_seq=%d -> replaying %d events", since, len(events))
        # The response frame is written before this task first suspends, so
        # replay notifications always land after `attached` on the wire; the
        # webview reducer is seq-idempotent regardless.
        asyncio.get_running_loop().create_task(self._replay(events))
        return {
            "v": PROTOCOL_VERSION,
            "run": {
                "run_id": self._session.run_id,
                "last_seq": self._session.journal.last_seq,
                "job": self._session.job,
            },
        }

    async def _replay(self, events: List[Dict[str, Any]]) -> None:
        for env in events:
            await self._conn.notify("ui/event", env)

    # ---- run commands (tickets 15/16) ----------------------------------------

    async def _on_start_run(self, params: Any) -> None:
        await self._ready.wait()
        p = dict(params or {})
        door = str(p.get("door", "typed"))
        if self._driver is not None and self._driver.active:
            if self._session is not None:
                await self._emit(
                    self._session, "conductor", "health.error",
                    {"taxonomy": "RunActive",
                     "message": "a build is already active -- one build per panel"},
                )
            return
        if self._driver is not None:
            self._driver.dispose()
        old = self._session
        self._session = self._new_run_session()
        if old is not None:
            old.close()
        session = self._session
        logger.info("start_run door=%s -> %s", door, session.run_id)

        async def emit(source: str, type_: str, payload: Dict[str, Any]) -> None:
            await self._emit(session, source, type_, payload)

        live = await self._resolve_live(session)
        self._driver = self._new_conductor(emit, session.run_id, door, p, live=live)
        self._driver.start()

    async def _on_answer(self, params: Any) -> None:
        await self._ready.wait()
        if self._driver is None:
            logger.warning("answer with no active run ignored")
            return
        await self._driver.handle_answer(dict(params or {}))

    async def _on_ask(self, params: Any) -> None:
        await self._ready.wait()
        if self._driver is None:
            logger.warning("ask with no active run ignored")
            return
        await self._driver.handle_ask(dict(params or {}))

    async def _on_fetch_artifact(self, params: Any) -> Dict[str, Any]:
        name = str((params or {}).get("name", ""))
        artifact = self._driver.get_artifact(name) if self._driver else None
        if artifact is None:
            return {"found": False, "name": name}
        return {"found": True, "name": name, "artifact": artifact}

    # ---- skeleton dev/smoke affordances (ticket 10) --------------------------

    async def _on_ping(self, params: Any) -> None:
        await self._emit(
            self._skeleton_session(),
            "conductor",
            "skeleton.pong",
            {
                "nonce": (params or {}).get("nonce"),
                "python": sys.version.split()[0],
                "pid": os.getpid(),
            },
        )

    async def _resolve_port(self) -> Tuple[ProviderPort, str, List[ModelInfo]]:
        if self._resolved is not None:
            return self._resolved
        reason: Optional[str] = None
        try:
            models = await self._primary.list_models()
            if models:
                self._resolved = (self._primary, self._primary_name, models)
                return self._resolved
            reason = "provider returned no models"
        except ProviderError as e:
            reason = f"{type(e).__name__}: {e}"
        if self._fallback is None:
            raise ModelNotFound(reason or "no models available")
        models = await self._fallback.list_models()
        self._resolved = (self._fallback, "double", models)
        await self._emit(
            self._skeleton_session(),
            "conductor",
            "health.provider_fallback",
            {"from": self._primary_name, "to": "double", "reason": reason},
        )
        logger.warning("provider fallback: %s -> double (%s)", self._primary_name, reason)
        return self._resolved

    @staticmethod
    def _pick_model(models: List[ModelInfo]) -> Optional[ModelInfo]:
        for m in models:
            if m.vendor == "copilot":
                return m
        return models[0] if models else None

    async def _on_echo(self, params: Any) -> None:
        prompt = str((params or {}).get("prompt", "")).strip() or "ping"
        stream_id = f"s-{uuid.uuid4().hex[:8]}"
        task = asyncio.create_task(self._run_echo(stream_id, prompt))
        self._streams[stream_id] = task
        task.add_done_callback(lambda _t: self._streams.pop(stream_id, None))

    async def _on_cancel(self, params: Any) -> None:
        stream_id = (params or {}).get("stream_id")
        task = self._streams.get(stream_id)
        if task is not None and not task.done():
            logger.info("cancelling stream %s", stream_id)
            task.cancel()

    async def _run_echo(self, stream_id: str, prompt: str) -> None:
        src = "specialist:echo"
        session = self._skeleton_session()
        try:
            port, provider_name, models = await self._resolve_port()
        except ProviderError as e:
            await self._emit(
                session,
                "conductor",
                "health.error",
                {"taxonomy": type(e).__name__, "message": str(e), "stream_id": stream_id},
            )
            return
        model = self._pick_model(models)
        await self._emit(
            session,
            src,
            "stream.open",
            {
                "stream_id": stream_id,
                "provider": provider_name,
                "model": {"vendor": model.vendor, "id": model.id, "name": model.name}
                if model
                else None,
                "prompt": prompt,
            },
        )
        request = ChatRequest(
            messages=[ChatMessage(role="user", text=prompt)],
            model_id=model.id if model else None,
            stream_id=stream_id,
        )
        agen = port.chat(request)
        finish = "unknown"
        try:
            async for ev in agen:
                kind = getattr(ev, "kind", "unknown")
                if kind == "done":
                    finish = ev.finish_reason
                elif kind in ("text_delta", "thinking_delta"):
                    await self._emit(
                        session,
                        src,
                        "stream.delta",
                        {"stream_id": stream_id, "part": {"kind": kind, "text": ev.text}},
                    )
                elif kind == "usage":
                    await self._emit(
                        session,
                        src,
                        "stream.delta",
                        {
                            "stream_id": stream_id,
                            "part": {
                                "kind": "usage",
                                "raw": ev.raw,
                                "total_nano_aiu": ev.total_nano_aiu,
                            },
                        },
                    )
                else:
                    await self._emit(
                        session,
                        src,
                        "stream.delta",
                        {
                            "stream_id": stream_id,
                            "part": {"kind": "unknown", "detail": getattr(ev, "detail", {})},
                        },
                    )
            await self._emit(
                session, src, "stream.close", {"stream_id": stream_id, "finish_reason": finish}
            )
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await asyncio.shield(agen.aclose())
            await asyncio.shield(
                self._emit(
                    session,
                    src,
                    "stream.close",
                    {"stream_id": stream_id, "finish_reason": "canceled"},
                )
            )
        except RequestCanceled:
            await self._emit(
                session, src, "stream.close", {"stream_id": stream_id, "finish_reason": "canceled"}
            )
        except ProviderError as e:
            await self._emit(
                session,
                "conductor",
                "health.error",
                {"taxonomy": type(e).__name__, "message": str(e), "stream_id": stream_id},
            )
            # 'error' extends 07's stop|canceled|unknown -- an errored stream
            # never yields done, but the webview still needs the close edge.
            await self._emit(
                session, src, "stream.close", {"stream_id": stream_id, "finish_reason": "error"}
            )
        finally:
            with contextlib.suppress(Exception):
                await agen.aclose()

    async def _on_crash(self, params: Any) -> None:
        logger.warning("skeleton.crash received -- hard-exiting for restart proof")
        os._exit(13)

    # ---- autorun (ticket 17's live-probe rig; a dev affordance, never the
    # demo path -- the F5 demo stays human-driven per ticket 20) --------------

    @staticmethod
    def _autorun_answer(q: Dict[str, Any], state: Dict[str, int]) -> Tuple[str, Optional[str]]:
        """Deterministic kind-policy answers for a probe run: recommended
        option where one exists, approve at gates, keep the run moving. One
        exhaustion grant only -- a live loop that cannot converge stops
        instead of burning budget unattended."""
        kind = q.get("kind")
        opts = list(q.get("options") or [])
        ids = [str(o.get("id")) for o in opts]

        def recommended() -> str:
            for o in opts:
                if o.get("recommended"):
                    return str(o.get("id"))
            return ids[0] if ids else "other"

        if kind == "gap":
            if q.get("gap_id") == "G0":
                return ("waive" if "waive" in ids else recommended()), None
            return recommended(), None
        if kind == "needs_human":
            choice = recommended()
            if choice == "guide":
                # The question's prompt carries the validator's exact reason;
                # the probe's answer points the normalizer straight at it.
                return choice, ("Do exactly what the validator's reason says: "
                                "align the declared schema and locations with "
                                "the actual data (a schema must list every "
                                "column the file's header has, in its order).")
            return choice, None
        if kind in ("spec_gate", "code_gate", "human_gate"):
            return ("approve" if "approve" in ids else ids[0]), None
        if kind == "exhaustion":
            if state.get("grants", 0) < 1 and "grant" in ids:
                state["grants"] = state.get("grants", 0) + 1
                return "grant", None
            for fallback in ("stop_to_gate", "stop"):
                if fallback in ids:
                    return fallback, None
            return ids[0], None
        if kind == "owner_human":
            # One unattended retry only: owner_human is uncapped for a real
            # human, but a probe bot re-answering retry forever would spin a
            # live diagnosis loop with nobody watching.
            if state.get("oh_retries", 0) < 1 and "retry" in ids:
                state["oh_retries"] = state.get("oh_retries", 0) + 1
                return "retry", None
            return ("stop_to_gate" if "stop_to_gate" in ids else ids[0]), None
        if kind == "propose_confirm":
            # A hold the probe itself asked for gets confirmed (ticket 18's
            # composer-intent beat); anything else -- notably an escalation's
            # stop proposal -- is dismissed so the run stays alive.
            if q.get("proposal") == "hold" and "confirm" in ids:
                return "confirm", None
            return ("dismiss" if "dismiss" in ids else ids[0]), None
        if kind == "hold":
            return ("resume" if "resume" in ids else ids[0]), None
        return (ids[0] if ids else "other"), None

    async def _autorun_bot(self, probe_asks: Optional[Dict[str, str]] = None) -> None:
        """``probe_asks`` (ticket 18): {question_kind: composer_text} -- when
        a kind first shows up pending, the bot types the text into the
        composer (through the normal ``command.ask`` path) one tick before
        answering the question, so the orchestrator's live turns -- threaded
        answers and propose_control -- get exercised without a human."""
        answered: set = set()
        asked: set = set()
        ask_n = 0
        state: Dict[str, int] = {}
        probe_asks = dict(probe_asks or {})
        while True:
            await asyncio.sleep(1.0)
            driver = self._driver
            if driver is None:
                continue
            fired_ask = False
            for q in driver.questions.pending():
                qid = str(q.get("question_id"))
                kind = str(q.get("kind"))
                if kind in probe_asks and kind not in asked:
                    asked.add(kind)
                    ask_n += 1
                    text = probe_asks[kind]
                    logger.info("[autorun] probe ask at %s: %r", kind, text)
                    await driver.handle_ask({"ask_id": f"probe-{ask_n}", "text": text})
                    fired_ask = True
                    break  # answer this question on the next tick
                if qid in answered:
                    continue
                choice, free_text = self._autorun_answer(q, state)
                answered.add(qid)
                logger.info("[autorun] answering %s (%s) -> %s",
                            qid, q.get("kind"), choice)
                await driver.handle_answer(
                    {"question_id": qid, "choice": choice, "free_text": free_text})
            if fired_ask:
                # Give the orchestrator's turn a beat to land (and any
                # proposal card to rise) before the gates get answered.
                await asyncio.sleep(4.0)
            if driver.ended:
                logger.info("[autorun] run ended; probe bot done")
                return

    async def maybe_autorun(self) -> None:
        """Consume ``<work-dir>/autorun.json`` (written by the live-probe
        driver): self-start the run it describes and answer its questions by
        the kind policy. Answers land through the normal ``handle_answer``
        path and journal as ordinary resolutions."""
        marker = self._work_dir / "autorun.json"
        if not marker.is_file():
            return
        try:
            params = json.loads(marker.read_text(encoding="utf-8"))
        except ValueError as e:
            logger.warning("[autorun] autorun.json unreadable (%s); ignored", e)
            marker.rename(self._work_dir / "autorun.bad.json")
            return
        consumed = self._work_dir / "autorun.consumed.json"
        if consumed.exists():
            consumed.unlink()
        marker.rename(consumed)
        # probe_asks is the bot's, never part of the start_run request.
        probe_asks = params.pop("probe_asks", None)
        logger.info("[autorun] starting %s-door probe run", params.get("door"))
        await self._on_start_run(params)
        asyncio.get_running_loop().create_task(self._autorun_bot(probe_asks))

    def close(self) -> None:
        if self._driver is not None:
            self._driver.dispose()
        if self._session is not None:
            self._session.close()
