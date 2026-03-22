"""Converter for tAdvancedFileOutputXML -> AdvancedFileOutputXMLComponent."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tAdvancedFileOutputXML")
class AdvancedFileOutputXMLConverter(ComponentConverter):
    """Convert a Talend tAdvancedFileOutputXML node to v1 AdvancedFileOutputXMLComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "filename": self._get_str(node, "FILENAME"),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            "pretty_compact": self._get_bool(node, "PRETTY_COMPACT", False),
            "create": self._get_bool(node, "CREATE", True),
            "create_empty_element": self._get_bool(node, "CREATE_EMPTY_ELEMENT", True),
            "add_blank_line_after_declaration": self._get_bool(
                node, "ADD_BLANK_LINE_AFTER_DECLARATION", False
            ),
        }

        # Warn when filename is empty -- it is mandatory in Talend
        if not config["filename"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        component = self._build_component_dict(
            node=node,
            type_name="AdvancedFileOutputXMLComponent",
            config=config,
            schema={"input": self._parse_schema(node), "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
