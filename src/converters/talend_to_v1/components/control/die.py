"""Converter for Talend tDie component.

Throws an error and kills the job with a priority-rated message.

Config mapping (6 params total):
  MESSAGE            -> message (str, default "the end is near")
  CODE               -> code (str, default "4")
  PRIORITY           -> priority (str, default "5")
  EXIT_JVM           -> exit_jvm (bool, default False)
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tDie")
class DieConverter(ComponentConverter):
    """Convert a Talend tDie node into a v1 Die component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        """Convert a TalendNode into a v1 engine component dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["message"] = self._get_str(node, "MESSAGE", "the end is near")
        config["code"] = self._get_str(node, "CODE", "4")

        # ---- 2. CLOSED_LIST parameters ----
        config["priority"] = self._get_str(node, "PRIORITY", "5")

        # ---- 3. Advanced parameters ----
        config["exit_jvm"] = self._get_bool(node, "EXIT_JVM", False)

        # ---- 4. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 5. Schema ----
        schema = {"input": [], "output": []}

        # ---- 6. Engine gap needs_review entries (per D-24: per-feature) ----
        needs_review.append({
            "issue": "Engine default message 'Job execution stopped' differs from Talend default 'the end is near'",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        needs_review.append({
            "issue": "Engine default code 1 differs from Talend default 4",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        needs_review.append({
            "issue": "EXIT_JVM parameter not read by engine -- JVM exit behavior not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 7. Return ----
        component = self._build_component_dict(
            node=node,
            type_name="Die",
            config=config,
            schema=schema,
        )
        return ComponentResult(
            component=component, warnings=warnings, needs_review=needs_review
        )
