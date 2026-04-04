"""Converter for Talend tSleep component.

Pauses job execution for a specified duration in seconds.

Config mapping (3 params total):
  PAUSE              -> pause_duration (str, default "1")
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tSleep")
class SleepConverter(ComponentConverter):
    """Convert Talend tSleep to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        """Convert a TalendNode into a v1 SleepComponent config dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["pause_duration"] = self._get_str(node, "PAUSE", "1")

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Return ----
        return ComponentResult(
            component=self._build_component_dict(
                node=node,
                type_name="SleepComponent",
                config=config,
                schema={"input": [], "output": []},
            ),
            warnings=warnings,
            needs_review=needs_review,
        )
