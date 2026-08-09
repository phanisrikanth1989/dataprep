"""Test double: the adapter that plays back scripted responses instead of
calling a real model (CONTEXT.md: Test double).

Full fixture format per ticket 07 Q10, grown for ticket 15's scripted demo
run: keyed scripts with thinking, tool calls, usage and error injection.

``scripts`` maps a script key (read from ``request.options["script"]``) to a
list of *calls*; each call is a list of part dicts consumed in order:

    {"think": str}          -> ThinkingDelta, streamed in small chunks
    {"text": str}           -> TextDelta, streamed word by word
    {"echo_prompt": True}   -> TextDelta stream of the last user message
                               (the core composes the reply, the double plays it)
    {"tool": {"call_id", "name", "args"}} -> ToolCall
    {"usage": int}          -> Usage with total_nano_aiu = int
    {"pause": float}        -> dead air, seconds (scaled by chunk cadence)
    {"error": {"kind", "message", "retry_after"?}} -> raise mid-stream

A key's calls are consumed in order; the last call repeats once exhausted.
Requests with no/unknown key fall back to the legacy string playlist, else a
synthesized echo of the prompt.
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
            )
        ]

    # ---- fixture resolution --------------------------------------------------

    def _next_fixture(self, key: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        if not key or key not in self._scripts:
            return None
        calls = self._scripts[key]
        if not calls:
            return None
        # Consumed in order; the last call repeats once exhausted.
        return calls.pop(0) if len(calls) > 1 else calls[0]

    # ---- chat ----------------------------------------------------------------

    async def chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        self._calls += 1
        prompt = request.messages[-1].text if request.messages else ""
        fixture = self._next_fixture(request.options.get("script"))
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
