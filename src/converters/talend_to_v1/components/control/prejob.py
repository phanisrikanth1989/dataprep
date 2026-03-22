"""Converter for Talend tPrejob component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tPrejob")
class PrejobConverter(ComponentConverter):
    """Convert a Talend tPrejob node into a v1 PrejobComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # tPrejob has no configuration parameters
        config: Dict[str, Any] = {}

        component = self._build_component_dict(
            node=node,
            type_name="PrejobComponent",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
