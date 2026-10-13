"""Model-call runner: one logical call, forwarded per-part to the UI, with
the tool-use loop and core-owned visible backoff (tickets 07 + 16).

Semantics reconciled into the contract (see envelope.py):

- One logical call presents as ONE UI stream per attempt. A tool-use loop's
  follow-up rounds reuse the attempt's stream_id -- every round's port call
  carries it, so the port-to-pixel id law holds while the observed window
  stays a single stream. ``tool_result`` parts between rounds are
  core-authored (the model never speaks them).
- Adapters never retry (07). On RateLimited the runner closes the errored
  stream (finish_reason "error"), emits ``health.retry`` with the visible
  backoff, sleeps, and re-issues as a NEW stream. Bounded attempts; the
  final failure surfaces as ``health.error`` and raises LlmCallError for
  the conductor to escalate (05: propose-confirm, never a silent death).
- Journal idempotence: a restarted core skips calls whose streams the
  journal already holds in full (per-label completed-close counting), so a
  crash-restored run never replays model traffic it already showed.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .port import (
    ChatMessage,
    ChatOptions,
    ChatRequest,
    ModelInfo,
    ProviderError,
    ProviderPort,
    RateLimited,
    RequestCanceled,
    ToolCallItem,
    ToolDecl,
    ToolResultItem,
)

logger = logging.getLogger(__name__)

Emit = Callable[[str, str, Dict[str, Any]], Awaitable[None]]
ToolHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]

MAX_ATTEMPTS = 3  # visible backoff budget per logical call
MAX_TOOL_ROUNDS = 8  # runaway guard; real loops are 2-3 rounds
DEFAULT_BACKOFF_S = 1.8


class LlmCallError(Exception):
    """A logical call failed for good (retries exhausted / non-retryable).
    The conductor escalates; nothing here is silent."""

    def __init__(self, taxonomy: str, message: str):
        super().__init__(f"{taxonomy}: {message}")
        self.taxonomy = taxonomy
        self.message = message


@dataclass
class LlmCall:
    source: str  # envelope source: "specialist:<stage>" | "orchestrator"
    who: str  # display name for the observed window / bubble
    label: str  # call label: UI stream label + the double's fixture key
    prompt: str = ""  # single-user-message convenience
    messages: Optional[List[ChatMessage]] = None  # overrides prompt when set
    stage_label: Optional[str] = None
    in_reply_to: Optional[str] = None
    tools: Dict[str, ToolHandler] = field(default_factory=dict)
    tool_decls: List[ToolDecl] = field(default_factory=list)
    model: Optional[ModelInfo] = None
    options: ChatOptions = field(default_factory=ChatOptions)
    # Ticket 17: real specialists set live=True -- the runner routes them to
    # the live provider when one resolved (else the scripted double plays the
    # fixture); orchestrator placeholders (18's) and stub stages stay scripted.
    live: bool = False
    # When set, every text_delta of the winning attempt accumulates here --
    # the real stages parse their JSON artifact from it. Cleared per attempt.
    capture: Optional[List[str]] = None
    # Ticket 18: conversation turns (composer asks, proposals) are NOT part
    # of the deterministic walk -- a crash-restored core must never skip a
    # NEW ask because the journal holds an older stream under the same label.
    journal_guarded: bool = True


class StreamRunner:
    def __init__(
        self,
        emit: Emit,
        port: ProviderPort,
        provider_name: str,
        run_id: str,
        pace: float = 1.0,
        closed_streams: Optional[Dict[str, int]] = None,
        live_port: Optional[ProviderPort] = None,
        live_provider: str = "",
    ):
        self._emit = emit
        self._port = port
        self._provider = provider_name
        self._run_id = run_id
        self._pace = pace
        # Live routing (ticket 17): calls flagged live go to the live port
        # when one resolved; everything else plays through the scripted port.
        self._live_port = live_port
        self._live_provider = live_provider or provider_name
        # label -> completed (non-error) closes already in the journal;
        # populated by the conductor's restore pass.
        self._closed = dict(closed_streams or {})
        self._calls: Dict[str, int] = {}  # label -> logical calls this life
        # Stream ids must stay unique across crash-restarts: unguarded calls
        # (ticket 18's conversation turns) restart their per-label count each
        # life, so the id carries a per-process epoch instead of the run id.
        self._epoch = uuid.uuid4().hex[:4]

    def _port_for(self, call: LlmCall):
        if call.live and self._live_port is not None:
            return self._live_port, self._live_provider
        return self._port, self._provider

    async def count_tokens(self, call_or_model, text: str) -> Optional[int]:
        """Prompt-budget probe on the port that would serve the call; None
        when the capability is absent (the core degrades)."""
        if isinstance(call_or_model, LlmCall):
            port, _ = self._port_for(call_or_model)
            model = call_or_model.model
        else:
            port = self._live_port or self._port
            model = call_or_model
        try:
            return await port.count_tokens(model.id if model else None, text)
        except ProviderError:
            return None

    async def _sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds * self._pace)

    # ---- the one entrypoint ----------------------------------------------------

    async def run(self, call: LlmCall) -> str:
        """Run one logical call (attempts + tool rounds); returns finish_reason.

        Journal-idempotent: when the journal already holds this label's
        completed stream, the call no-ops (the stub stages' bus writes are
        separately idempotent, so skipping the stream skips no state)."""
        self._calls[call.label] = self._calls.get(call.label, 0) + 1
        if call.journal_guarded and self._closed.get(call.label, 0) >= self._calls[call.label]:
            return "stop"  # journal already holds this call in full

        messages = list(call.messages) if call.messages is not None else [
            ChatMessage(role="user", text=call.prompt or call.label)
        ]
        last_error: Optional[ProviderError] = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            stream_id = f"s-{call.label}-{self._calls[call.label]}.{attempt}-{self._epoch}"
            try:
                return await self._attempt(call, messages, stream_id)
            except RateLimited as e:
                last_error = e
                if attempt >= MAX_ATTEMPTS:
                    break
                backoff = float(e.retry_after or DEFAULT_BACKOFF_S)
                await self._emit(
                    "conductor", "health.retry",
                    {"reason": str(e), "attempt": attempt + 1, "of": MAX_ATTEMPTS,
                     "backoff_s": backoff, "stream_label": call.label},
                )
                await self._sleep(backoff)
            except RequestCanceled:
                return "canceled"
            except ProviderError as e:
                await self._emit(
                    "conductor", "health.error",
                    {"taxonomy": type(e).__name__, "message": str(e),
                     "stream_label": call.label},
                )
                raise LlmCallError(type(e).__name__, str(e))
        await self._emit(
            "conductor", "health.error",
            {"taxonomy": type(last_error).__name__, "message": str(last_error),
             "stream_label": call.label, "note": "retry budget exhausted"},
        )
        raise LlmCallError(type(last_error).__name__, str(last_error))

    # ---- one attempt: open .. rounds .. close ------------------------------------

    async def _attempt(
        self, call: LlmCall, messages: List[ChatMessage], stream_id: str
    ) -> str:
        if call.capture is not None:
            call.capture.clear()  # a retry attempt starts a fresh transcript
        _, provider_name = self._port_for(call)
        open_payload: Dict[str, Any] = {
            "stream_id": stream_id,
            "provider": provider_name,
            "who": call.who,
            "label": call.label,
        }
        if call.model is not None:
            open_payload["model"] = {"vendor": call.model.vendor, "id": call.model.id}
        if call.stage_label:
            open_payload["stage_label"] = call.stage_label
        if call.in_reply_to:
            open_payload["in_reply_to"] = call.in_reply_to
        await self._emit(call.source, "stream.open", open_payload)

        try:
            for _round in range(MAX_TOOL_ROUNDS):
                finish, tool_calls = await self._one_round(call, messages, stream_id)
                if not tool_calls:
                    await self._emit(
                        call.source, "stream.close",
                        {"stream_id": stream_id, "finish_reason": finish,
                         "label": call.label},
                    )
                    return finish
                # Core-authored tool outcomes, then feed results back and loop.
                result_items: List[ToolResultItem] = []
                call_items: List[ToolCallItem] = []
                for tc in tool_calls:
                    handler = call.tools.get(tc["name"])
                    if handler is None:
                        result: Dict[str, Any] = {
                            "ok": False, "note": f"no tool named {tc['name']}"}
                    else:
                        result = await handler(tc["args"])
                    await self._sleep(0.5)
                    await self._emit(
                        call.source, "stream.delta",
                        {"stream_id": stream_id,
                         "part": {"kind": "tool_result", "call_id": tc["call_id"],
                                  "name": tc["name"], **result}},
                    )
                    call_items.append(ToolCallItem(tc["call_id"], tc["name"], tc["args"]))
                    result_items.append(ToolResultItem(tc["call_id"], tc["name"], result))
                messages.append(ChatMessage(role="assistant", items=list(call_items)))
                messages.append(ChatMessage(role="user", items=list(result_items)))
            # Tool-round runaway: close honestly and fail the call.
            await self._emit(
                call.source, "stream.close",
                {"stream_id": stream_id, "finish_reason": "error", "label": call.label},
            )
            raise LlmCallError("ToolLoopRunaway",
                               f"{call.label} exceeded {MAX_TOOL_ROUNDS} tool rounds")
        except (RateLimited, RequestCanceled) as e:
            reason = "error" if isinstance(e, RateLimited) else "canceled"
            await self._emit(
                call.source, "stream.close",
                {"stream_id": stream_id, "finish_reason": reason, "label": call.label},
            )
            raise
        except ProviderError:
            await self._emit(
                call.source, "stream.close",
                {"stream_id": stream_id, "finish_reason": "error", "label": call.label},
            )
            raise
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await asyncio.shield(self._emit(
                    call.source, "stream.close",
                    {"stream_id": stream_id, "finish_reason": "canceled",
                     "label": call.label},
                ))
            raise

    async def _one_round(
        self, call: LlmCall, messages: List[ChatMessage], stream_id: str
    ) -> tuple:
        """One port call: forward parts, collect tool calls; returns
        (finish_reason, tool_calls)."""
        request = ChatRequest(
            messages=list(messages),
            model_id=call.model.id if call.model else None,
            stream_id=stream_id,
            label=call.label,
            tools=list(call.tool_decls),
            options=call.options,
        )
        port, _ = self._port_for(call)
        agen = port.chat(request)
        finish = "unknown"
        tool_calls: List[Dict[str, Any]] = []
        try:
            async for ev in agen:
                kind = getattr(ev, "kind", "unknown")
                if kind == "done":
                    finish = ev.finish_reason
                elif kind in ("text_delta", "thinking_delta"):
                    if kind == "text_delta" and call.capture is not None:
                        call.capture.append(ev.text)
                    await self._emit(
                        call.source, "stream.delta",
                        {"stream_id": stream_id, "part": {"kind": kind, "text": ev.text}},
                    )
                elif kind == "tool_call":
                    await self._emit(
                        call.source, "stream.delta",
                        {"stream_id": stream_id,
                         "part": {"kind": kind, "call_id": ev.call_id,
                                  "name": ev.name, "args": ev.args}},
                    )
                    tool_calls.append(
                        {"call_id": ev.call_id, "name": ev.name, "args": ev.args})
                elif kind == "usage":
                    await self._emit(
                        call.source, "stream.delta",
                        {"stream_id": stream_id,
                         "part": {"kind": "usage", "raw": ev.raw,
                                  "total_nano_aiu": ev.total_nano_aiu}},
                    )
                else:
                    await self._emit(
                        call.source, "stream.delta",
                        {"stream_id": stream_id,
                         "part": {"kind": "unknown",
                                  "detail": getattr(ev, "detail", {})}},
                    )
            return finish, tool_calls
        finally:
            with contextlib.suppress(Exception):
                await agen.aclose()
