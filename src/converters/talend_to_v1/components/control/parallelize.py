"""Converter for Talend tParallelize component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tParallelize")
class ParallelizeConverter(ComponentConverter):
    """Convert a Talend tParallelize node into a v1 Parallelize component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "wait_for": self._get_str(node, "WAIT_FOR", default="All"),
            "sleep_time": self._get_str(node, "SLEEPTIME", default="100"),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", default=False),
        }

        component = self._build_component_dict(
            node=node,
            type_name="Parallelize",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
