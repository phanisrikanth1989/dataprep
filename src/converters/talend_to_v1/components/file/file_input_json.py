"""Converter for tFileInputJSON -> FileInputJSON."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputJSON")
class FileInputJSONConverter(ComponentConverter):
    """Convert a Talend tFileInputJSON node to v1 FileInputJSON.

    Fixes CONV-NAME-002: uses type name ``FileInputJSON`` instead of the
    incorrect ``FileInputJSONComponent`` that existed in the old converter.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "filename": self._get_str(node, "FILENAME"),
            "json_loop_query": self._get_str(node, "JSON_LOOP_QUERY"),
            "mapping": self._parse_mapping(node),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
        }

        # Warn when filename is empty — it is mandatory in Talend
        if not config["filename"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        # Warn when json_loop_query is empty — typically required
        if not config["json_loop_query"]:
            warnings.append("JSON_LOOP_QUERY is empty — this is usually required")

        component = self._build_component_dict(
            node=node,
            type_name="FileInputJSON",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)

    @staticmethod
    def _parse_mapping(node: TalendNode) -> List[Dict[str, str]]:
        """Parse MAPPING_JSONPATH table parameter into list of {column, jsonpath} dicts."""
        raw = node.params.get("MAPPING_JSONPATH", [])
        mapping: List[Dict[str, str]] = []
        for entry in raw:
            column = entry.get("elementRef", "").strip('"')
            jsonpath = entry.get("value", "").strip('"')
            if column:
                mapping.append({"column": column, "jsonpath": jsonpath})
        return mapping
