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


def main(argv=None) -> int:
    """CLI: append one audit entry to <job-dir>/audit.jsonl."""
    import argparse
    import json
    import sys
    parser = argparse.ArgumentParser(description="Append one audit entry to <job-dir>/audit.jsonl.")
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--detail", default=None, help="optional JSON object string")
    args = parser.parse_args(argv)
    detail = None
    if args.detail:
        try:
            detail = json.loads(args.detail)
        except ValueError as exc:
            sys.stderr.write(f"--detail must be a JSON object: {exc}\n")
            return 2
    AuditLog(args.job_dir).record(args.iteration, args.role, args.event, detail)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
