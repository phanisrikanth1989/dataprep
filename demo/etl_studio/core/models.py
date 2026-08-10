"""Per-stage model selection (tickets 07 Q7 + 09).

The roster is org-mutable and display names are non-unique, so selection is
always by (vendor, id) against a runtime enumeration -- never by name. Config
shape (optional ``studio_config.json`` beside main.py; absent = adapter
defaults everywhere; per-stage entries tuned at rehearsal):

    {
      "models": {
        "default": {"vendor": "copilot", "id": "claude-opus-4.8"},
        "stages": {
          "interpret": {"vendor": "copilot", "id": "claude-opus-4.6"}
        }
      }
    }
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .port import ModelInfo

logger = logging.getLogger(__name__)


class ModelConfig:
    def __init__(self, raw: Optional[Dict] = None):
        models = (raw or {}).get("models") or {}
        self._default: Optional[Dict] = models.get("default")
        self._stages: Dict[str, Dict] = dict(models.get("stages") or {})

    @classmethod
    def load(cls, path: Optional[Path]) -> "ModelConfig":
        if path is None or not Path(path).is_file():
            return cls()
        try:
            return cls(json.loads(Path(path).read_text(encoding="utf-8")))
        except ValueError as e:
            logger.warning("studio config unreadable (%s); using adapter defaults", e)
            return cls()

    @staticmethod
    def _match(models: List[ModelInfo], selector: Optional[Dict]) -> Optional[ModelInfo]:
        if not selector:
            return None
        vendor = str(selector.get("vendor") or "")
        model_id = str(selector.get("id") or "")
        for m in models:
            if m.vendor == vendor and m.id == model_id:
                return m
        return None

    def pick(self, models: List[ModelInfo], stage: str) -> Optional[ModelInfo]:
        """The model for a stage: stage selector, else default, else the
        adapter's own default (None). A configured selector missing from the
        live roster logs and falls through -- the roster is org-mutable."""
        for selector, scope in ((self._stages.get(stage), stage), (self._default, "default")):
            if selector is None:
                continue
            hit = self._match(models, selector)
            if hit is not None:
                return hit
            logger.warning(
                "model selector for %s (%s/%s) not in the live roster",
                scope, selector.get("vendor"), selector.get("id"),
            )
        return None
