"""Event envelope, per ticket 08: every core-originated event is
``{seq, ts, run_id, source, type, payload}``; Python dataclasses are canonical
and the webview imports a hand-mirrored types.ts.

The contract of record (ticket 08, plus the tickets 10/15 provisional
extensions reconciled here by ticket 16). Consumers skip unknown event
types and unknown payload fields -- vocabulary grows without lockstep.

Core -> webview families:
- ``run.*``       started {job, door, tier?, brd?, request_text?, itinerary} /
                  ended {status: approved|stopped|error, by?, note} /
                  crash_restored {note}. Run ids are real (``<job>-r<k>``);
                  the skeleton's fixed id survives only for skeleton.* dev
                  affordances.
- ``stage.*``     started {stage, label, iteration, directed?, feedback?} /
                  completed {stage, label, iteration, note?} /
                  artifact_written {name, kind, iteration, stage?, note?,
                  fields?} (the canvas event; ``fetch_artifact`` serves the
                  full artifact from the bus) /
                  loop_attempt {stage, k, n, note} /
                  progress {stage, node_id, state: active|configured}
                  (per-component configure progress; ticket 15 extension).
- ``question.*``  raised {question_id, kind, options, ...} / resolved
                  {question_id, kind, choice, free_text?, note, ...}. All
                  nine kinds share the one lifecycle: gap, needs_human,
                  spec_gate, code_gate, exhaustion, owner_human, human_gate,
                  propose_confirm, hold. No timeouts anywhere; resolutions
                  are recorded untouched.
- ``stream.*``    open {stream_id, provider, who, label, model?,
                  stage_label?, in_reply_to?} / delta {stream_id, part} /
                  close {stream_id, finish_reason, label}. Part kinds are
                  the port vocabulary (text_delta, thinking_delta,
                  tool_call, usage) plus core-authored ``tool_result``
                  (ticket 15 extension). One logical call = one stream per
                  attempt; a tool-use loop's follow-up rounds reuse the
                  attempt's stream_id, so the port-to-pixel id law holds.
                  finish_reason: stop | canceled | unknown | error (an
                  errored stream never yields done but still closes; the
                  core's visible backoff then opens a fresh stream).
- ``health.*``    retry {reason, attempt, of, backoff_s, stream_label} /
                  error {taxonomy, message, ...} / provider_fallback
                  {from, to, reason}.

Webview -> core: ``attach {v, since_seq}`` -> ``{v, run?}`` (runless attach
returns just {v}: the idle two-door state), ``answer {question_id, choice,
free_text?}``, ``command.start_run {door, text?|brd_path?, brd_name?,
note?, attachments?, rig?}``, ``command.ask {ask_id, text}``,
``fetch_artifact {name}``.

Shim-owned (never reach the core): ``shim.lifecycle`` (spawned | crashed |
restarting | dead | stopped), ``shim.restart``, ``shim.close_panel``,
``editor.pick_file`` (webviews cannot open native dialogs) and the rest of
``editor.*``. The ``lm/*`` family (listModels, countTokens, chat/chatEvent)
is shim<->core only and never crosses the webview boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict


PROTOCOL_VERSION = 1  # rides the attach handshake once, never per message


@dataclass
class Envelope:
    seq: int
    ts: str  # ISO 8601 UTC
    run_id: str
    source: str  # "conductor" | "orchestrator" | "specialist:<stage>" | "shim"
    type: str  # dotted family, e.g. "stream.delta"
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "run_id": self.run_id,
            "source": self.source,
            "type": self.type,
            "payload": self.payload,
        }


def now_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
