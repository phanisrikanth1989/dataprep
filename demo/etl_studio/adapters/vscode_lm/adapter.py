"""vscode.lm adapter: the semantic Python half of the split decided in
ticket 07 Q6. The TS shim is mechanical -- it forwards instanceof-tagged
parts and verbatim vscode errors ({code, name, message}); everything that
MEANS something (error taxonomy, part -> event mapping, usage decoding,
system-role emulation, tool-convention mapping) happens here, so Citi-build
drift is a Python-only fix.

Wire (ticket 07 mechanical defaults): ``lm/listModels``, ``lm/countTokens``
and ``lm/chat`` requests to the shim; per-part ``lm/chatEvent {streamId,
part}`` notifications back; the request resolves at stream end; cancellation
rides JSON-RPC ``$/cancelRequest``.

Semantic mappings owned here (ticket 01 facts):
- ``system`` role -> leading-User-message emulation (stable has no System);
- tool items -> the Assistant(toolCall)-then-User(toolResult) two-message
  convention, serialized as tagged parts the shim instantiates mechanically;
- image items are capability-gated OFF for vscode.lm until a probe confirms
  DataPart image acceptance on the Citi build (adapters degrade: dropped
  with a stderr note, never sent blind).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from core.port import (
    ChatMessage,
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
    ToolCall,
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
                capabilities={
                    "counts_tokens": True,  # stable API since 1.95
                    "image_input": False,  # unprobed on the Citi build
                    "thinking": False,  # proposed-API; 09 saw no parts
                },
            )
            for m in models
        ]

    # ---- count_tokens --------------------------------------------------------

    async def count_tokens(self, model_id: Optional[str], text: str) -> Optional[int]:
        try:
            res = await self._conn.request(
                "lm/countTokens", {"modelId": model_id, "text": text}
            )
        except RpcError as e:
            if e.code == METHOD_NOT_FOUND:
                return None  # older shim: degrade, never fail the caller
            raise self._map_error(e)
        except RpcClosed as e:
            raise ProviderUnavailable(f"connection closed: {e}")
        count = (res or {}).get("count")
        return int(count) if isinstance(count, (int, float)) else None

    # ---- message serialization (semantic; the shim instantiates) --------------

    @staticmethod
    def _serialize_message(m: ChatMessage) -> Dict[str, Any]:
        # System emulation: stable vscode.lm has no System role (ticket 01);
        # the convention is a leading User message carrying the system text.
        role = "user" if m.role == "system" else m.role
        if not m.items:
            return {"role": role, "text": m.text}
        parts: List[Dict[str, Any]] = []
        for item in m.items:
            kind = getattr(item, "kind", "")
            if kind == "text":
                parts.append({"kind": "text", "value": item.text})
            elif kind == "tool_call":
                parts.append(
                    {
                        "kind": "toolCall",
                        "callId": item.call_id,
                        "name": item.name,
                        "input": item.args,
                    }
                )
            elif kind == "tool_result":
                parts.append(
                    {
                        "kind": "toolResult",
                        "callId": item.call_id,
                        "name": item.name,
                        "content": item.content,
                    }
                )
            elif kind == "image":
                # Capability-gated off (list_models says image_input=False);
                # degrade loudly if a caller sends one anyway.
                logger.warning("vscode_lm: dropping image item (image_input unprobed)")
            else:
                logger.warning("vscode_lm: dropping unknown content item kind %r", kind)
        return {"role": role, "parts": parts, "text": m.text}

    # ---- chat ----------------------------------------------------------------

    async def chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        stream_id = request.stream_id or f"s-{uuid.uuid4().hex[:8]}"
        q: asyncio.Queue = asyncio.Queue()
        self._queues[stream_id] = q
        options: Dict[str, Any] = {}
        if request.options.max_output_tokens is not None:
            options["max_output_tokens"] = request.options.max_output_tokens
        params = {
            "streamId": stream_id,
            "modelId": request.model_id,
            "messages": [self._serialize_message(m) for m in request.messages],
            "tools": [
                {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
                for t in request.tools
            ],
            "options": options,
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
        if kind == "toolCall":
            args = part.get("input")
            return ToolCall(
                call_id=str(part.get("callId", "")),
                name=str(part.get("name", "")),
                args=args if isinstance(args, dict) else {},
            )
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
