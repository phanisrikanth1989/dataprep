"""Converter for Talend tReplicate component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tReplicate")
class ReplicateConverter(ComponentConverter):
    """Convert a Talend tReplicate node into a v1 Replicate component.

    tReplicate is a simple passthrough component that duplicates its input
    data to multiple outputs.  The only configuration parameter is
    ``CONNECTION_FORMAT`` which defaults to ``"row"``.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "connection_format": self._get_str(node, "CONNECTION_FORMAT", "row"),
        }

        schema_cols = self._parse_schema(node)

        component = self._build_component_dict(
            node=node,
            type_name="Replicate",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
