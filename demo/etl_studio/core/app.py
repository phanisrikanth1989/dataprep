"""Walking-skeleton app logic (ticket 10).

Proves, end to end: the 08 envelope + journal attach/replay, one stream
family fed through the provider port, cancellation crossing the wire, and
crash-restart seq continuity. No real pipeline lives here yet -- the
``skeleton.*`` command names are throwaway by design (the webview's
skip-unknown rule makes that safe); ``attach``, the envelope, the journal and
the ``stream.*`` family are the real contract.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import uuid
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

logger = logging.getLogger(__name__)

RUN_ID = "skeleton"  # provisional pseudo-run; the conductor owns real run ids later


class SkeletonApp:
    def __init__(
        self,
        conn: JsonRpcConnection,
        journal: UiJournal,
        primary: ProviderPort,
        primary_name: str,
        fallback: Optional[ProviderPort] = None,
    ):
        self._conn = conn
        self._journal = journal
        self._primary = primary
        self._primary_name = primary_name
        self._fallback = fallback
        self._resolved: Optional[Tuple[ProviderPort, str, List[ModelInfo]]] = None
        self._streams: Dict[str, asyncio.Task] = {}

        conn.on_request("attach", self._on_attach)
        conn.on_notification("skeleton.ping", self._on_ping)
        conn.on_notification("skeleton.echo", self._on_echo)
        conn.on_notification("skeleton.cancel", self._on_cancel)
        conn.on_notification("skeleton.crash", self._on_crash)

    # ---- event emission ------------------------------------------------------

    async def _emit(self, source: str, type_: str, payload: Dict[str, Any]) -> None:
        env = Envelope(
            seq=self._journal.next_seq(),
            ts=now_ts(),
            run_id=RUN_ID,
            source=source,
            type=type_,
            payload=payload,
        ).to_dict()
        self._journal.append(env)
        await self._conn.notify("ui/event", env)

    # ---- attach / replay -----------------------------------------------------

    async def _on_attach(self, params: Any) -> Dict[str, Any]:
        since = int((params or {}).get("since_seq", 0) or 0)
        events = self._journal.replay_since(since)
        logger.info("attach since_seq=%d -> replaying %d events", since, len(events))
        # The response frame is written before this task first suspends, so
        # replay notifications always land after `attached` on the wire; the
        # webview reducer is seq-idempotent regardless.
        asyncio.get_running_loop().create_task(self._replay(events))
        return {
            "v": PROTOCOL_VERSION,
            "run": {"run_id": RUN_ID, "last_seq": self._journal.last_seq},
        }

    async def _replay(self, events: List[Dict[str, Any]]) -> None:
        for env in events:
            await self._conn.notify("ui/event", env)

    # ---- ping ----------------------------------------------------------------

    async def _on_ping(self, params: Any) -> None:
        await self._emit(
            "conductor",
            "skeleton.pong",
            {
                "nonce": (params or {}).get("nonce"),
                "python": sys.version.split()[0],
                "pid": os.getpid(),
            },
        )

    # ---- provider resolution (visible fallback, never silent) ----------------

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
            "conductor",
            "health.provider_fallback",
            {"from": self._primary_name, "to": "double", "reason": reason},
        )
        logger.warning("provider fallback: %s -> double (%s)", self._primary_name, reason)
        return self._resolved

    @staticmethod
    def _pick_model(models: List[ModelInfo]) -> Optional[ModelInfo]:
        # Skeleton selector: first copilot-vendor model, else first anything.
        # Ticket 07's per-stage config selectors replace this in the slices.
        for m in models:
            if m.vendor == "copilot":
                return m
        return models[0] if models else None

    # ---- echo stream ---------------------------------------------------------

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
        try:
            port, provider_name, models = await self._resolve_port()
        except ProviderError as e:
            await self._emit(
                "conductor",
                "health.error",
                {"taxonomy": type(e).__name__, "message": str(e), "stream_id": stream_id},
            )
            return
        model = self._pick_model(models)
        await self._emit(
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
                        src,
                        "stream.delta",
                        {"stream_id": stream_id, "part": {"kind": kind, "text": ev.text}},
                    )
                elif kind == "usage":
                    await self._emit(
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
                        src,
                        "stream.delta",
                        {
                            "stream_id": stream_id,
                            "part": {"kind": "unknown", "detail": getattr(ev, "detail", {})},
                        },
                    )
            await self._emit(
                src, "stream.close", {"stream_id": stream_id, "finish_reason": finish}
            )
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await asyncio.shield(agen.aclose())
            await asyncio.shield(
                self._emit(
                    src,
                    "stream.close",
                    {"stream_id": stream_id, "finish_reason": "canceled"},
                )
            )
        except RequestCanceled:
            await self._emit(
                src, "stream.close", {"stream_id": stream_id, "finish_reason": "canceled"}
            )
        except ProviderError as e:
            await self._emit(
                "conductor",
                "health.error",
                {"taxonomy": type(e).__name__, "message": str(e), "stream_id": stream_id},
            )
            # 'error' extends 07's stop|canceled|unknown -- an errored stream
            # never yields done, but the webview still needs the close edge.
            await self._emit(
                src, "stream.close", {"stream_id": stream_id, "finish_reason": "error"}
            )
        finally:
            with contextlib.suppress(Exception):
                await agen.aclose()

    # ---- crash (dev affordance for the restart proof) ------------------------

    async def _on_crash(self, params: Any) -> None:
        logger.warning("skeleton.crash received -- hard-exiting for restart proof")
        os._exit(13)
