"""ETL Studio core app (tickets 10 + 15).

Owns the 08 contract surface: attach/replay, the run/stage/question/stream/
health families, ``command.start_run`` / ``answer`` / ``command.ask`` /
``fetch_artifact``, and per-run journals. Runs are scripted (ticket 15's
demo driver in ``scripted_run.py``) until the conductor lands (ticket 16).

The ``skeleton.*`` handlers from ticket 10 stay as dev/smoke affordances --
ping, LM echo through the live provider resolution, cancel, crash. Their
events land in a "skeleton" session journaled at the work-dir root, exactly
where the walking skeleton kept it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .envelope import PROTOCOL_VERSION, Envelope, now_ts
from .journal import UiJournal
from .port import (
    ChatMessage,
    ChatRequest,
    ModelInfo,
    ModelNotFound,
    ProviderError,
    ProviderPort,
    RequestCanceled,
)
from .rpc import JsonRpcConnection
from .scripted_run import JOB, ScriptedRun

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
    ):
        self._conn = conn
        self._work_dir = work_dir
        self._primary = primary
        self._primary_name = primary_name
        self._fallback = fallback
        # The scripted demo run always plays through the double (ticket 15);
        # live per-stage providers arrive with the real specialists (17/18).
        self._scripted_port = scripted_port or fallback or primary
        self._pace = pace
        self._resolved: Optional[Tuple[ProviderPort, str, List[ModelInfo]]] = None
        self._streams: Dict[str, asyncio.Task] = {}
        self._session: Optional[RunSession] = None
        self._driver: Optional[ScriptedRun] = None

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

        driver = ScriptedRun(emit, self._scripted_port, run_id, door="brd", request={},
                             pace=self._pace)
        driver.restore(events)
        self._driver = driver
        if driver.ended:
            logger.info("resumed finished run %s at seq %d", run_id, session.journal.last_seq)
            return
        await self._emit(session, "conductor", "run.crash_restored",
                         {"note": "The core restarted; the run continues from the journal."})
        driver.resume()
        logger.info("crash-restored run %s at seq %d", run_id, session.journal.last_seq)

    # ---- attach / replay -----------------------------------------------------

    async def _on_attach(self, params: Any) -> Dict[str, Any]:
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

    # ---- scripted run commands (ticket 15) -----------------------------------

    async def _on_start_run(self, params: Any) -> None:
        p = dict(params or {})
        door = str(p.get("door", "typed"))
        if self._driver is not None and self._driver.active:
            if self._session is not None:
                await self._emit(
                    self._session, "conductor", "health.error",
                    {"taxonomy": "RunActive",
                     "message": "a run is already active -- one run per panel"},
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

        self._driver = ScriptedRun(
            emit, self._scripted_port, session.run_id, door=door,
            request=p, pace=self._pace,
        )
        self._driver.start()

    async def _on_answer(self, params: Any) -> None:
        if self._driver is None:
            logger.warning("answer with no active run ignored")
            return
        await self._driver.handle_answer(dict(params or {}))

    async def _on_ask(self, params: Any) -> None:
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

    def close(self) -> None:
        if self._driver is not None:
            self._driver.dispose()
        if self._session is not None:
            self._session.close()
