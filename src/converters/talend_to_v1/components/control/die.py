"""Converter for Talend tDie component."""
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
        warnings: List[str] = []

        config = {
            "message": self._get_str(node, "MESSAGE", "Job execution stopped"),
            "code": self._get_int(node, "CODE", 1),
            "priority": self._get_int(node, "PRIORITY", 5),
            "exit_code": self._get_int(node, "EXIT_CODE", 1),
        }

        component = self._build_component_dict(
            node=node,
            type_name="Die",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
