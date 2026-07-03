"""Per-run structured audit trail for the ETL orchestration (one JSON line per step)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AuditLog:
    """Append-only JSONL audit trail under a job's work dir."""

    def __init__(self, job_dir: str):
        self._path = Path(job_dir) / "audit.jsonl"

    def record(self, iteration: int, role: str, event: str, detail: dict | None = None) -> None:
        """Append one audit entry: {iteration, role, event, detail}."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"iteration": iteration, "role": role, "event": event, "detail": detail or {}}
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    def read(self) -> list:
        """Return all audit entries (empty list if the log does not exist)."""
        if not self._path.exists():
            return []
        entries = []
        with self._path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("[audit_log] skipping malformed line")
                    continue
        return entries
