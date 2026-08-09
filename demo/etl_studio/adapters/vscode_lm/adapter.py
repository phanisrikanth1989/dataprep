"""vscode.lm adapter: the semantic Python half of the split decided in
ticket 07 Q6. The TS shim is mechanical -- it forwards instanceof-tagged
parts and verbatim vscode errors ({code, name, message}); everything that
MEANS something (error taxonomy, part -> event mapping, usage decoding)
happens here, so Citi-build drift is a Python-only fix.

Wire (ticket 07 mechanical defaults): ``lm/listModels`` and ``lm/chat``
requests to the shim; per-part ``lm/chatEvent {streamId, part}``
notifications back; the request resolves at stream end; cancellation rides
JSON-RPC ``$/cancelRequest``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from core.port import (
    ChatRequest,
    ConsentDenied,
    Done,
    ModelInfo,
    ModelNotFound,
    ProviderError,
    ProviderPort,
    ProviderUnavailable,
    RequestCanceled,
    StreamEvent,
    TextDelta,
    ThinkingDelta,
    UnknownEvent,
    Usage,
)
from core.rpc import (
    METHOD_NOT_FOUND,
    REQUEST_CANCELLED,
    JsonRpcConnection,
    OutgoingRequest,
    RpcClosed,
    RpcError,
)

logger = logging.getLogger(__name__)


class VscodeLmAdapter(ProviderPort):
    def __init__(self, conn: JsonRpcConnection):
        self._conn = conn
        self._queues: Dict[str, asyncio.Queue] = {}
        conn.on_notification("lm/chatEvent", self._on_chat_event)

    async def _on_chat_event(self, params: Any) -> None:
        stream_id = (params or {}).get("streamId")
        q = self._queues.get(stream_id)
        if q is not None:
            q.put_nowait(("part", (params or {}).get("part") or {}))

    # ---- list_models ---------------------------------------------------------

    async def list_models(self) -> List[ModelInfo]:
        try:
            res = await self._conn.request("lm/listModels", {})
        except RpcError as e:
            if e.code == METHOD_NOT_FOUND:
                raise ProviderUnavailable("lm bridge not present (lm/listModels unhandled)")
            raise self._map_error(e)
        except RpcClosed as e:
            raise ProviderUnavailable(f"connection closed: {e}")
        models = (res or {}).get("models") or []
        return [
            ModelInfo(
                id=str(m.get("id", "")),
                vendor=str(m.get("vendor", "")),
                family=str(m.get("family", "")),
                name=str(m.get("name", "")),
                max_input_tokens=int(m.get("maxInputTokens") or 0),
            )
            for m in models
        ]

    # ---- chat ----------------------------------------------------------------

    async def chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        stream_id = request.stream_id or f"s-{uuid.uuid4().hex[:8]}"
        q: asyncio.Queue = asyncio.Queue()
        self._queues[stream_id] = q
        params = {
            "streamId": stream_id,
            "modelId": request.model_id,
            "messages": [{"role": m.role, "text": m.text} for m in request.messages],
            "options": request.options or {},
        }
        try:
            handle = await self._conn.start_request("lm/chat", params)
        except RpcClosed as e:
            self._queues.pop(stream_id, None)
            raise ProviderUnavailable(f"connection closed: {e}")
        finisher = asyncio.create_task(self._watch_end(handle, q))
        finished_clean = False
        try:
            while True:
                kind, item = await q.get()
                if kind == "part":
                    ev = self._map_part(item)
                    if ev is not None:
                        yield ev
                elif kind == "error":
                    raise item
                else:  # "end"
                    yield Done(str((item or {}).get("finishReason") or "unknown"))
                    finished_clean = True
                    return
        finally:
            self._queues.pop(stream_id, None)
            finisher.cancel()
            if not finished_clean and not handle.done():
                # Iterator closed early (core-side cancel): propagate outward
                # so the shim cancels the vscode token. Never retry.
                with contextlib.suppress(Exception):
                    await asyncio.shield(handle.cancel())

    async def _watch_end(self, handle: OutgoingRequest, q: asyncio.Queue) -> None:
        try:
            result = await handle.wait()
            q.put_nowait(("end", result or {}))
        except RpcError as e:
            if e.code == REQUEST_CANCELLED:
                q.put_nowait(("error", RequestCanceled("request canceled")))
            else:
                q.put_nowait(("error", self._map_error(e)))
        except RpcClosed as e:
            q.put_nowait(("error", ProviderUnavailable(f"connection closed: {e}")))

    # ---- semantic mapping ----------------------------------------------------

    @staticmethod
    def _map_error(e: RpcError) -> ProviderError:
        """Shim forwards vscode LanguageModelError verbatim in error.data:
        {code, name, message}. Classification happens here, nowhere else.
        Known code strings come from the ticket 09 on-machine probe."""
        data: Dict[str, Any] = e.data if isinstance(e.data, dict) else {}
        code = str(data.get("code") or "")
        message = str(data.get("message") or e.message)
        if code == "NoPermissions":
            return ConsentDenied(message)
        if code == "NotFound":
            return ModelNotFound(message)
        return ProviderError(message)

    @staticmethod
    def _map_part(part: Dict[str, Any]) -> Optional[StreamEvent]:
        kind = part.get("kind")
        if kind == "text":
            return TextDelta(str(part.get("value", "")))
        if kind == "thinking":
            return ThinkingDelta(str(part.get("value", "")))
        if kind == "data":
            payload = part.get("json")
            if part.get("mime") == "usage" and isinstance(payload, dict):
                nano = (payload.get("copilot_usage") or {}).get("total_nano_aiu")
                return Usage(
                    raw=payload,
                    total_nano_aiu=nano if isinstance(nano, int) else None,
                )
            return UnknownEvent({"kind": "data", "mime": part.get("mime")})
        # Unknown ctor / future part kinds: forward, never drop silently.
        return UnknownEvent({k: v for k, v in part.items() if k != "json"})
