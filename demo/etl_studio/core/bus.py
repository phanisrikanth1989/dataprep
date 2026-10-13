"""Artifact bus: file-based, produce-don't-mutate artifact store for one run
(CONTEXT.md: Artifact bus; decided in ticket 04, built in ticket 16).

One flat per-run work dir -- ``demo/etl_studio/work/<job>-r<k>/`` -- holds
every stage's artifact under a fixed canonical name, plus ``golden/`` and
the run's two append-only logs (``audit.jsonl``, ``ui_journal.jsonl``).
Nothing in a pass is overwritten: on any write where the canonical file
already exists, the superseded version moves to ``history/<artifact>.<k>``
(k monotonic per artifact, one dumb rule covering every rewrite cadence)
and ``audit.jsonl`` maps each k to its context. The nested
``demo/etl_studio/.gitignore`` keeps the containment invariant (work/ is
never committed).

The bus, not process memory, owns the artifacts: after a crash the conductor
restores its picture of the run from the files here plus the audit trail
(ticket 05), with the UI journal supplying seq continuity (ticket 08).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .vendored.audit_log import AuditLog

logger = logging.getLogger(__name__)


class ArtifactBus:
    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._audit = AuditLog(str(self.run_dir))
        self._history_k: Dict[str, int] = {}
        # name -> {kind, stage, iteration, note}; rebuilt on restore.
        self._index: Dict[str, Dict[str, Any]] = {}
        self._scan_history()

    # ---- paths ----------------------------------------------------------------

    def path(self, name: str) -> Path:
        return self.run_dir / name

    def exists(self, name: str) -> bool:
        return self.path(name).exists()

    def _scan_history(self) -> None:
        hist = self.run_dir / "history"
        if not hist.is_dir():
            return
        for p in hist.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(hist).as_posix()
            name, dot, k = rel.rpartition(".")
            if not dot or not k.isdigit():
                continue
            self._history_k[name] = max(self._history_k.get(name, 0), int(k))

    # ---- writes (produce-don't-mutate) -----------------------------------------

    def _supersede(self, name: str, context: Optional[Dict[str, Any]]) -> Optional[int]:
        """Move an existing canonical file aside as history/<name>.<k>."""
        target = self.path(name)
        if not target.exists() or target.is_dir():
            return None
        k = self._history_k.get(name, 0) + 1
        self._history_k[name] = k
        hist_path = self.run_dir / "history" / f"{name}.{k}"
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        target.rename(hist_path)
        self._audit.record(
            0, "bus", "artifact_superseded",
            {"name": name, "k": k, "context": context or {}},
        )
        return k

    def write_json(
        self,
        name: str,
        payload: Any,
        *,
        kind: str,
        stage: Optional[str] = None,
        iteration: int = 1,
        note: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write a canonical JSON artifact; supersede any prior version."""
        self._supersede(name, context)
        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        meta = {"name": name, "kind": kind, "stage": stage, "iteration": iteration, "note": note}
        self._index[name] = meta
        self._audit.record(
            iteration, stage or "conductor", "artifact_written",
            {"name": name, "kind": kind, "note": note},
        )
        return meta

    def write_text(
        self,
        name: str,
        text: str,
        *,
        kind: str = "data",
        stage: Optional[str] = None,
        iteration: int = 1,
        note: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write a data/text artifact (golden files, run outputs)."""
        self._supersede(name, context)
        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        meta = {"name": name, "kind": kind, "stage": stage, "iteration": iteration, "note": note}
        self._index[name] = meta
        self._audit.record(
            iteration, stage or "conductor", "artifact_written",
            {"name": name, "kind": kind, "note": note},
        )
        return meta

    # ---- reads ------------------------------------------------------------------

    def read_json(self, name: str) -> Optional[Any]:
        target = self.path(name)
        if not target.is_file():
            return None
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except ValueError:
            logger.warning("bus: %s is not valid JSON", name)
            return None

    def meta(self, name: str) -> Optional[Dict[str, Any]]:
        return self._index.get(name)

    def artifacts(self) -> List[Dict[str, Any]]:
        return list(self._index.values())

    # ---- audit ------------------------------------------------------------------

    def audit(self, role: str, event: str, detail: Optional[Dict[str, Any]] = None,
              iteration: int = 0) -> None:
        """Append one non-artifact audit entry (conductor decisions, grants,
        loop attempts, question lifecycle, tier freeze...)."""
        self._audit.record(iteration, role, event, detail or {})

    def audit_entries(self) -> List[Dict[str, Any]]:
        return self._audit.read()

    # ---- restore ------------------------------------------------------------------

    def restore_index(self) -> None:
        """Rebuild the artifact index from the audit trail + files on disk.

        The audit trail supplies each artifact's latest recorded metadata;
        disk presence is the existence truth (a crash between rename and
        write can lose at most the artifact being written -- its audit entry
        then points at a missing file, which is dropped here)."""
        for entry in self._audit.read():
            if entry.get("event") != "artifact_written":
                continue
            detail = entry.get("detail") or {}
            name = str(detail.get("name") or "")
            if not name:
                continue
            self._index[name] = {
                "name": name,
                "kind": detail.get("kind"),
                "stage": entry.get("role") if entry.get("role") != "conductor" else None,
                "iteration": int(entry.get("iteration") or 1),
                "note": detail.get("note"),
            }
        for name in list(self._index):
            if not self.exists(name):
                del self._index[name]
