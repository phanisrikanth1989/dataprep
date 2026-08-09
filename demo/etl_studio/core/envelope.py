"""Event envelope, per ticket 08: every core-originated event is
``{seq, ts, run_id, source, type, payload}``; Python dataclasses are canonical
and the webview imports a hand-mirrored types.ts.
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
