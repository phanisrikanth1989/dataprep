"""Converter for Talend tPostjob component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tPostjob")
class PostjobConverter(ComponentConverter):
    """Convert a Talend tPostjob node into a v1 PostjobComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # tPostjob has no configuration parameters
        config: Dict[str, Any] = {}

        component = self._build_component_dict(
            node=node,
            type_name="PostjobComponent",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
