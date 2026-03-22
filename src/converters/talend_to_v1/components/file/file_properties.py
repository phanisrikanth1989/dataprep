"""Converter for tFileProperties -> FileProperties."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileProperties")
class FilePropertiesConverter(ComponentConverter):
    """Convert a Talend tFileProperties node to a v1 FileProperties component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config = {
            "filename": self._get_str(node, "FILENAME"),
            "calculate_md5": self._get_bool(node, "MD5"),
        }

        if not config["filename"]:
            warnings.append("FILENAME is empty")

        component = self._build_component_dict(
            node=node,
            type_name="FileProperties",
            config=config,
            schema={"input": [], "output": []},  # utility component
        )

        return ComponentResult(component=component, warnings=warnings)
