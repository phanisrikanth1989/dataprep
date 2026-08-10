"""Specialist harness riding ticket 16's loop runner (ticket 17).

One entrypoint: ``run_specialist`` streams a specialist call through the
stage context (stage-tagged at call-issue time, per ticket 06), captures the
text, and parses the JSON artifact out of it -- the prompted opening line
precedes the fenced JSON and feeds the live line on the way through.

Malformed output gets a bounded corrective retry (the model's reply plus a
pointed correction go back as messages, same label -- the double scripts the
retry as the label's next call); exhaustion raises LlmCallError, which the
conductor escalates (propose-confirm today; ticket 18's orchestrator later).

Prompt-budget check: when the serving model carries the counts_tokens
capability, the assembled prompt is measured against the model's input window
BEFORE the call (ticket 09: the provider raises no overflow error, so the
core must budget proactively); an over-budget prompt fails loudly.

Journal idempotence: on a crash-restore re-walk the runner skips streams the
journal already holds, so the capture comes back empty -- the caller then
reads its artifact back from the bus (the bus, not process memory, owns run
state).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .llm import LlmCallError
from .port import ChatMessage, ToolDecl
from .stages import StageContext

logger = logging.getLogger(__name__)

MALFORMED_RETRIES = 2  # corrective re-issues per logical artifact call
BUDGET_HEADROOM = 0.9  # fraction of the model input window a prompt may fill

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class MalformedOutput(ValueError):
    """The captured text held no parseable JSON artifact."""


def parse_json_reply(text: str) -> Dict[str, Any]:
    """Parse the artifact object out of a specialist reply: the LAST fenced
    JSON block, else the outermost brace span. Raises MalformedOutput."""
    candidates: List[str] = [m.group(1) for m in _FENCE_RE.finditer(text)]
    if not candidates:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            candidates = [text[start:end + 1]]
    last_error: Optional[Exception] = None
    for raw in reversed(candidates):
        try:
            obj = json.loads(raw)
        except ValueError as e:
            last_error = e
            continue
        if isinstance(obj, dict):
            return obj
        last_error = ValueError(f"artifact is {type(obj).__name__}, not an object")
    raise MalformedOutput(str(last_error) if last_error else "no JSON object in the reply")


def _to_chat_messages(messages: List[Dict[str, str]]) -> List[ChatMessage]:
    return [ChatMessage(role=m["role"], text=m["text"]) for m in messages]


async def run_specialist(
    ctx: StageContext,
    *,
    who: str,
    label: str,
    messages: List[Dict[str, str]],
    stage_label: Optional[str] = None,
    tools: Optional[Dict[str, Any]] = None,
    tool_decls: Optional[List[ToolDecl]] = None,
) -> Optional[Dict[str, Any]]:
    """One specialist artifact call. Returns the parsed artifact object, or
    None when the journal already held the stream (crash-restore re-walk;
    read the artifact back from the bus). Raises LlmCallError when the
    bounded malformed-output retries are spent."""
    chat = _to_chat_messages(messages)

    # Prompt budget (ticket 17 scope): proactive, capability-gated, loud.
    prompt_text = "\n".join(m.text for m in chat)
    tokens = await ctx.count_tokens(prompt_text)
    if tokens is not None and ctx.model is not None and ctx.model.max_input_tokens:
        ceiling = int(ctx.model.max_input_tokens * BUDGET_HEADROOM)
        if tokens > ceiling:
            raise LlmCallError(
                "InputTooLarge",
                f"{label} prompt is {tokens} tokens against a {ceiling}-token "
                f"budget ({ctx.model.id}); shrink the slice or pick a larger model",
            )

    last_error = ""
    for attempt in range(1 + MALFORMED_RETRIES):
        capture: List[str] = []
        await ctx.stream(
            who, label,
            stage_label=stage_label,
            messages=chat,
            capture=capture,
            tools=tools,
            tool_decls=tool_decls,
        )
        text = "".join(capture)
        if not text.strip():
            # The runner skipped a journal-held stream: state is on the bus.
            return None
        try:
            return parse_json_reply(text)
        except MalformedOutput as e:
            last_error = str(e)
            logger.warning("[%s] %s: malformed artifact (%s); corrective retry %d/%d",
                           ctx.stage, label, e, attempt + 1, MALFORMED_RETRIES)
            chat = chat + [
                ChatMessage(role="assistant", text=text),
                ChatMessage(role="user", text=(
                    "Your reply did not contain a valid JSON artifact "
                    f"({e}). Re-emit it now: one short present-tense line, then "
                    "the complete artifact in a single fenced ```json block, "
                    "nothing after the fence.")),
            ]
    raise LlmCallError(
        "MalformedOutput",
        f"{label} produced no parseable JSON artifact after "
        f"{MALFORMED_RETRIES} corrective retries ({last_error})",
    )
