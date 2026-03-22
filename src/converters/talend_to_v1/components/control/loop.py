"""Converter for Talend tLoop component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tLoop")
class LoopConverter(ComponentConverter):
    """Convert a Talend tLoop node into a v1 Loop component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "loop_type": self._get_str(node, "LOOP_TYPE", default="FOR"),
            "start_value": self._get_str(node, "START_VALUE", default="0"),
            "end_value": self._get_str(node, "END_VALUE", default="10"),
            "step_value": self._get_str(node, "STEP_VALUE", default="1"),
            "iterate_on": self._get_str(node, "ITERATE_ON", default=""),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", default=False),
        }

        component = self._build_component_dict(
            node=node,
            type_name="Loop",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
