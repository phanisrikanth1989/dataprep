"""Converter for tFileInputMSXML -> FileInputMSXML.

Parses XML-based file input with XPath-mapped schema columns.
The SCHEMAS table param contains {elementRef, value} entries where
elementRef is the column name and value is the XPath expression.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputMSXML")
class FileInputMSXMLConverter(ComponentConverter):
    """Convert a Talend tFileInputMSXML node to v1 FileInputMSXML."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # Parse SCHEMAS table — each entry maps a column name to an XPath.
        # The XmlParser stores TABLE params as lists of {elementRef, value} dicts.
        schemas: List[Dict[str, str]] = []
        raw_schemas = self._get_param(node, "SCHEMAS", [])
        if isinstance(raw_schemas, list):
            for entry in raw_schemas:
                column = entry.get("elementRef", "")
                xpath = entry.get("value", "").strip('"')
                if column:
                    schemas.append({"column": column, "xpath": xpath})

        filename = self._get_str(node, "FILENAME")
        if not filename:
            warnings.append("FILENAME is empty — this is a required parameter")

        root_loop_query = self._get_str(node, "ROOT_LOOP_QUERY")
        if not root_loop_query:
            warnings.append(
                "ROOT_LOOP_QUERY is empty — this is a required parameter"
            )

        config: Dict[str, Any] = {
            "filename": filename,
            "root_loop_query": root_loop_query,
            "schemas": schemas,
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR"),
            "trim_all": self._get_bool(node, "TRIMALL"),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
        }

        output_schema = self._parse_schema(node, "FLOW")

        component = self._build_component_dict(
            node=node,
            type_name="FileInputMSXMLComponent",
            config=config,
            schema={"input": [], "output": output_schema},
        )

        return ComponentResult(component=component, warnings=warnings)
