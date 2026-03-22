"""Converter for Talend tWarn component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tWarn")
class WarnConverter(ComponentConverter):
    """Convert a Talend tWarn node into a v1 Warn component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config = {
            "message": self._get_str(node, "MESSAGE", default="Warning"),
            "code": self._get_int(node, "CODE", default=0),
            "priority": self._get_int(node, "PRIORITY", default=4),
        }

        component = self._build_component_dict(
            node=node,
            type_name="Warn",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
