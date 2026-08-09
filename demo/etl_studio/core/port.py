"""Provider port: the plain-data interface through which the core requests
model calls (CONTEXT.md: Provider port).

Walking-skeleton surface per ticket 10: send + stream + cancel (the ticket 07
chat call minus tools), plus list_models. Ticket 07's full surface
(count_tokens, typed options, capability flags) lands with the implementation
slices; the event kinds and the exception family below are already 07's.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional


# ---- Requests ----------------------------------------------------------------


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant" -- adapters own degradation
    text: str


@dataclass
class ChatRequest:
    messages: List[ChatMessage]
    model_id: Optional[str] = None  # None = adapter default
    stream_id: str = ""  # core-generated; follows the call port to pixel
    options: Dict[str, Any] = field(default_factory=dict)  # provisional


@dataclass
class ModelInfo:
    id: str
    vendor: str
    family: str
    name: str
    max_input_tokens: int
    capabilities: Dict[str, Any] = field(default_factory=dict)


# ---- Stream events (kinds are ticket 07's vocabulary, verbatim) --------------


@dataclass
class TextDelta:
    text: str
    kind: str = "text_delta"


@dataclass
class ThinkingDelta:
    text: str
    kind: str = "thinking_delta"


@dataclass
class ToolCall:
    """Model-issued tool invocation (ticket 07: first-class tool_call items)."""

    call_id: str
    name: str
    args: Dict[str, Any] = field(default_factory=dict)
    kind: str = "tool_call"


@dataclass
class Usage:
    raw: Dict[str, Any]
    total_nano_aiu: Optional[int] = None  # normalized only where confident
    kind: str = "usage"


@dataclass
class Done:
    finish_reason: str  # "stop" | "canceled" | "unknown"
    kind: str = "done"


@dataclass
class UnknownEvent:
    """Forward-compat carrier: consumers must skip kinds they don't know."""

    detail: Dict[str, Any]
    kind: str = "unknown"


StreamEvent = Any  # TextDelta | ThinkingDelta | Usage | Done | UnknownEvent


# ---- Neutral exception family (ticket 07 Q5; adapters classify, never retry) -


class ProviderError(Exception):
    """Base + fallback: something provider-side failed, unclassified."""

    def __init__(self, message: str, cause: Optional[Any] = None):
        super().__init__(message)
        self.cause = cause


class ConsentDenied(ProviderError):
    pass


class ModelNotFound(ProviderError):
    pass


class RateLimited(ProviderError):
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class QuotaExhausted(ProviderError):
    pass


class InputTooLarge(ProviderError):
    pass


class ProviderUnavailable(ProviderError):
    """Bridge down / crashed / method missing."""


class RequestCanceled(ProviderError):
    pass


# ---- The port ----------------------------------------------------------------


class ProviderPort(ABC):
    """One adapter per model source; the core never reaches around this."""

    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        raise NotImplementedError

    @abstractmethod
    def chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """One call, an async iterator of stream events out.

        Cancellation is cancelling the consuming task / closing the iterator;
        adapters propagate cleanup outward (ticket 07 Q3) and never retry.
        """
        raise NotImplementedError
