"""UI journal: append-only per-run record of every webview-bound event
(CONTEXT.md: UI journal). The journal, not the process, owns the event
sequence -- a restarted core continues where the file ends (ticket 08).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class UiJournal:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._last_seq = self._scan_last_seq()
        # Line-buffered append handle; every append is flushed so a crash
        # loses at most the event being written.
        self._fh = open(self.path, "a", encoding="utf-8")
        if self._last_seq:
            logger.info("journal continues at seq %d (%s)", self._last_seq, self.path)

    def _scan_last_seq(self) -> int:
        if not self.path.exists():
            return 0
        last = 0
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = int(json.loads(line).get("seq", last))
                except (ValueError, KeyError):
                    logger.warning("journal: skipping unparsable line")
        return last

    def next_seq(self) -> int:
        self._last_seq += 1
        return self._last_seq

    @property
    def last_seq(self) -> int:
        return self._last_seq

    def append(self, envelope: Dict[str, Any]) -> None:
        self._fh.write(json.dumps(envelope, separators=(",", ":")) + "\n")
        self._fh.flush()

    def replay_since(self, since_seq: int) -> List[Dict[str, Any]]:
        """All journaled envelopes with seq > since_seq, in order."""
        out: List[Dict[str, Any]] = []
        if not self.path.exists():
            return out
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    env = json.loads(line)
                except ValueError:
                    continue
                if env.get("seq", 0) > since_seq:
                    out.append(env)
        return out

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass
