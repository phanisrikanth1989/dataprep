"""Test double: the adapter that plays back scripted responses instead of
calling a real model (CONTEXT.md: Test double).

Full fixture format per ticket 07 Q10, grown through tickets 15/16: keyed
scripts with thinking, tool calls, usage and error injection, resolved by
``request.label`` (the core-generated call label that also names the UI
stream -- no request-matching DSL).

``scripts`` maps a label to a list of *calls*; each call is a list of part
dicts consumed in order:

    {"think": str}          -> ThinkingDelta, streamed in small chunks
    {"text": str}           -> TextDelta, streamed word by word
    {"echo_prompt": True}   -> TextDelta stream of the last user message
                               (the core composes the reply, the double plays it)
    {"tool": {"call_id", "name", "args"}} -> ToolCall
    {"usage": int}          -> Usage with total_nano_aiu = int
    {"pause": float}        -> dead air, seconds (scaled by chunk cadence)
    {"error": {"kind", "message", "retry_after"?}} -> raise mid-stream

A label's calls are consumed in order; the last call repeats once exhausted.
The core's tool-use loop and backoff re-issue requests under the SAME label,
so multi-round loops and retry-after-rate-limit are scripted as successive
calls of one label. Requests with no/unknown label fall back to the legacy
string playlist, else a synthesized echo of the prompt.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional

from core.port import (
    ChatRequest,
    Done,
    ModelInfo,
    ProviderError,
    ProviderPort,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
    StreamEvent,
    TextDelta,
    ThinkingDelta,
    ToolCall,
    Usage,
)

_ERROR_KINDS = {
    "ProviderError": ProviderError,
    "RateLimited": RateLimited,
    "QuotaExhausted": QuotaExhausted,
    "ProviderUnavailable": ProviderUnavailable,
}


class DoubleAdapter(ProviderPort):
    def __init__(
        self,
        playlist: Optional[List[str]] = None,
        scripts: Optional[Dict[str, List[List[Dict[str, Any]]]]] = None,
        chunk_delay: float = 0.03,
    ):
        self._playlist = list(playlist or [])
        self._scripts = {k: list(calls) for k, calls in (scripts or {}).items()}
        self._chunk_delay = chunk_delay
        self._calls = 0

    async def list_models(self) -> List[ModelInfo]:
        return [
            ModelInfo(
                id="double-1",
                vendor="double",
                family="double",
                name="Scripted Test Double",
                max_input_tokens=100_000,
                capabilities={
                    "counts_tokens": True,
                    "image_input": True,
                    "thinking": True,
                },
            )
        ]

    async def count_tokens(self, model_id: Optional[str], text: str) -> Optional[int]:
        return max(1, len(text) // 4)

    # ---- fixture resolution --------------------------------------------------

    def _next_fixture(self, label: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        if not label or label not in self._scripts:
            return None
        calls = self._scripts[label]
        if not calls:
            return None
        # Consumed in order; the last call repeats once exhausted.
        return calls.pop(0) if len(calls) > 1 else calls[0]

    @staticmethod
    def _last_user_text(request: ChatRequest) -> str:
        for m in reversed(request.messages):
            if m.role != "user":
                continue
            if m.text:
                return m.text
            texts = [i.text for i in m.items if getattr(i, "kind", "") == "text"]
            if texts:
                return " ".join(texts)
        return ""

    # ---- chat ----------------------------------------------------------------

    async def chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        self._calls += 1
        prompt = self._last_user_text(request)
        fixture = self._next_fixture(request.label)
        if fixture is None:
            async for ev in self._legacy_echo(prompt):
                yield ev
            return
        for part in fixture:
            if "pause" in part:
                await asyncio.sleep(float(part["pause"]))
            elif "think" in part:
                async for ev in self._chunked(str(part["think"]), thinking=True):
                    yield ev
            elif "text" in part:
                async for ev in self._chunked(str(part["text"])):
                    yield ev
            elif part.get("echo_prompt"):
                async for ev in self._chunked(prompt):
                    yield ev
            elif "tool" in part:
                t = part["tool"]
                await asyncio.sleep(self._chunk_delay * 3)
                yield ToolCall(
                    call_id=str(t.get("call_id", f"t{self._calls}")),
                    name=str(t.get("name", "tool")),
                    args=dict(t.get("args", {})),
                )
            elif "usage" in part:
                yield Usage(
                    raw={"scripted": True, "call": self._calls},
                    total_nano_aiu=int(part["usage"]),
                )
            elif "error" in part:
                spec = part["error"]
                exc_cls = _ERROR_KINDS.get(str(spec.get("kind")), ProviderError)
                message = str(spec.get("message", "scripted failure"))
                if exc_cls is RateLimited:
                    raise RateLimited(message, retry_after=spec.get("retry_after"))
                raise exc_cls(message)
        yield Done("stop")

    # ---- streaming helpers ---------------------------------------------------

    async def _chunked(self, text: str, thinking: bool = False) -> AsyncIterator[StreamEvent]:
        words = text.split(" ")
        buf: List[str] = []
        # Thinking reads in small phrase chunks; text streams word by word.
        group = 3 if thinking else 1
        for i, word in enumerate(words):
            buf.append(word)
            if len(buf) >= group or i == len(words) - 1:
                await asyncio.sleep(self._chunk_delay * len(buf))
                chunk = " ".join(buf) + (" " if i < len(words) - 1 else "")
                yield ThinkingDelta(chunk) if thinking else TextDelta(chunk)
                buf = []

    async def _legacy_echo(self, prompt: str) -> AsyncIterator[StreamEvent]:
        if self._playlist:
            text = self._playlist.pop(0) if len(self._playlist) > 1 else self._playlist[0]
        else:
            text = f"[double] you said: {prompt} -- scripted reply #{self._calls}"
        approx_tokens = max(1, len(text) // 4)
        for word in text.split(" "):
            await asyncio.sleep(self._chunk_delay)
            yield TextDelta(word + " ")
        yield Usage(raw={"scripted": True, "call": self._calls, "approx_tokens": approx_tokens})
        yield Done("stop")
