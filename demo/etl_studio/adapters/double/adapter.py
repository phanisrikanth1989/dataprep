"""Test double: the adapter that plays back scripted responses instead of
calling a real model (CONTEXT.md: Test double).

Skeleton form of ticket 07 Q10: responses consumed in order from an optional
playlist, streamed with fake cadence; with no playlist it synthesizes an echo
of the prompt. The full fixture format (tool calls, thinking, error
injection) lands with the implementation slices.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, List, Optional

from core.port import (
    ChatRequest,
    Done,
    ModelInfo,
    ProviderPort,
    StreamEvent,
    TextDelta,
    Usage,
)


class DoubleAdapter(ProviderPort):
    def __init__(self, playlist: Optional[List[str]] = None, chunk_delay: float = 0.03):
        self._playlist = list(playlist or [])
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

    async def chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        self._calls += 1
        prompt = request.messages[-1].text if request.messages else ""
        if self._playlist:
            # Consumed in order; the last entry repeats once exhausted.
            text = (
                self._playlist.pop(0) if len(self._playlist) > 1 else self._playlist[0]
            )
        else:
            text = f"[double] you said: {prompt} -- scripted reply #{self._calls}"
        approx_tokens = max(1, len(text) // 4)
        for word in text.split(" "):
            await asyncio.sleep(self._chunk_delay)
            yield TextDelta(word + " ")
        yield Usage(raw={"scripted": True, "call": self._calls, "approx_tokens": approx_tokens})
        yield Done("stop")
