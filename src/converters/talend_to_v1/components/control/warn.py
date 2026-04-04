"""Converter for Talend tWarn component.

Logs a priority-rated warning message without stopping the job.

Config mapping (5 params total):
  MESSAGE            -> message (str, default "this is a warning")
  CODE               -> code (str, default "42")
  PRIORITY           -> priority (str, default "4")
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------
_PRIORITY_ITEMS = {"1": "TRACE", "2": "DEBUG", "3": "INFO", "4": "WARNING", "5": "ERROR", "6": "FATAL"}


@REGISTRY.register("tWarn")
class WarnConverter(ComponentConverter):
    """Convert Talend tWarn to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        """Convert a TalendNode into a v1 Warn component config dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["message"] = self._get_str(node, "MESSAGE", "this is a warning")
        config["code"] = self._get_str(node, "CODE", "42")

        # ---- 2. CLOSED_LIST parameters ----
        config["priority"] = self._get_str(node, "PRIORITY", "4")

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Engine gap needs_review entries (per D-24: per-feature) ----
        _engine_gap_keys = {
            "message": "Engine default for 'message' is 'Warning' but Talend default is 'this is a warning'",
            "code": "Engine default for 'code' is 0 but Talend default is 42",
        }
        for key, issue_desc in _engine_gap_keys.items():
            needs_review.append({
                "issue": issue_desc,
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 6. Return ----
        return ComponentResult(
            component=self._build_component_dict(
                node=node,
                type_name="Warn",
                config=config,
                schema={"input": [], "output": []},
            ),
            warnings=warnings,
            needs_review=needs_review,
        )
