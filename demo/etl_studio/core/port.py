"""Provider port: the plain-data interface through which the core requests
model calls (CONTEXT.md: Provider port).

Ticket 07's full surface, completed by ticket 16 (the skeleton shipped
send + stream + cancel only):

- messages carry content items -- text | image (capability-gated) |
  tool_call | tool_result -- with ``text`` kept as sugar for the plain case;
- tool declarations ride the request (``tools``); the model answers with
  ``tool_call`` stream events; the core's tool-use loop runner (core/llm.py)
  feeds ``tool_result`` items back on follow-up messages;
- request options are typed only (temperature / max_output_tokens / stop);
  no open provider-options dict crosses the port;
- ``label`` names the call for observability: it becomes the UI stream label
  and is the key the test double resolves fixtures by;
- ``count_tokens`` is an optional capability (``counts_tokens`` flag on
  ModelInfo.capabilities); the core must degrade when it returns None.

The event kinds and the neutral exception family are ticket 07's verbatim.
Adapters classify and raise -- they never retry; the core owns visible
backoff (health.* events).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional


# ---- Content items (ticket 07 Q1/Q2) ------------------------------------------


@dataclass
class TextItem:
    text: str
    kind: str = "text"


@dataclass
class ImageItem:
    """Base64 image content; send only when the model's ``image_input``
    capability flag is true -- adapters degrade, the core gates."""

    media_type: str  # e.g. "image/png"
    data_base64: str
    kind: str = "image"


@dataclass
class ToolCallItem:
    """A model-issued call echoed back on an assistant message so the
    follow-up round carries the full tool conversation."""

    call_id: str
    name: str
    args: Dict[str, Any] = field(default_factory=dict)
    kind: str = "tool_call"


@dataclass
class ToolResultItem:
    """The core-computed result of one tool call, riding a user message
    (adapters map to their provider's convention)."""

    call_id: str
    name: str
    content: Any = None  # JSON-serializable
    kind: str = "tool_result"


ContentItem = Any  # TextItem | ImageItem | ToolCallItem | ToolResultItem


# ---- Requests ----------------------------------------------------------------


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant" -- adapters own degradation
    text: str = ""  # sugar for items=[TextItem(text)]
    items: List[ContentItem] = field(default_factory=list)


@dataclass
class ToolDecl:
    """One tool offered to the model for this call."""

    name: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatOptions:
    """Typed request options only (ticket 07 Q8). Provider-specific knobs
    are adapter config, never port surface."""

    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None
    stop: Optional[List[str]] = None


@dataclass
class ChatRequest:
    messages: List[ChatMessage]
    model_id: Optional[str] = None  # None = adapter default
    stream_id: str = ""  # core-generated; follows the call port to pixel
    label: str = ""  # call label: UI stream label + the double's fixture key
    tools: List[ToolDecl] = field(default_factory=list)
    options: ChatOptions = field(default_factory=ChatOptions)


@dataclass
class ModelInfo:
    id: str
    vendor: str
    family: str
    name: str
    max_input_tokens: int
    # Known flags: counts_tokens, image_input, thinking (ticket 07 Q12).
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


StreamEvent = Any  # TextDelta | ThinkingDelta | ToolCall | Usage | Done | UnknownEvent


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

    async def count_tokens(self, model_id: Optional[str], text: str) -> Optional[int]:
        """Optional capability (``counts_tokens`` flag). None = unsupported;
        the core's only use is prompt-budget checks -- it must degrade."""
        return None
