"""Converter for Talend tPostjob component.

Marks the end of post-execution logic. Guaranteed to execute after the main job.

Config mapping (2 params total):
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tPostjob")
class PostjobConverter(ComponentConverter):
    """Convert Talend tPostjob to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Config parameters ----
        config: Dict[str, Any] = {}

        # (No unique parameters -- tPostjob has 0 params in _java.xml)

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Engine gap needs_review entries ----
        needs_review.append({
            "issue": (
                "No concrete engine implementation for tPostjob. "
                "All config keys are extracted for future engine support."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 4. Build component dict and return ----
        component = self._build_component_dict(
            node=node,
            type_name="tPostjob",
            config=config,
            schema={"input": [], "output": []},
        )
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
