"""Converter for Talend tParallelize component.

Manages parallel execution of multiple subjobs with configurable
wait conditions and failure handling.

Config mapping (5 params total):
  WAIT_FOR           -> wait_for (str, default "All")
  SLEEPTIME          -> sleeptime (str, default "")
  DIE_ON_ERROR       -> die_on_error (bool, default False)
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label (str, default "")

Note: _java.xml not available on Talaxie GitHub. Parameter names
based on official Talend documentation and existing converter analysis.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tParallelize")
class ParallelizeConverter(ComponentConverter):
    """Convert Talend tParallelize to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        """Convert a TalendNode into a v1 Parallelize config dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["wait_for"] = self._get_str(node, "WAIT_FOR", "All")
        config["sleeptime"] = self._get_str(node, "SLEEPTIME", "")
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Engine gap needs_review entries ----
        needs_review.append({
            "issue": "No concrete engine implementation for tParallelize. "
                     "All config keys are extracted for future engine support.",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 4. Return ----
        component = self._build_component_dict(
            node=node,
            type_name="tParallelize",
            config=config,
            schema={"input": [], "output": []},
        )
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
