"""Converter for tFileInputXML -> FileInputXML.

Fixes:
  CONV-FIX-001: LOOP_XPATH (LOOP_QUERY) is now properly extracted.
  CONV-FIX-002: MAPPING table parsed with elementRef semantics
                (SCHEMA_COLUMN / QUERY pairs) instead of flat values.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputXML")
class FileInputXMLConverter(ComponentConverter):
    """Convert a Talend tFileInputXML node to v1 FileInputXML."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # Parse MAPPING table from params.
        # XmlParser stores TABLE params as lists of {elementRef, value} dicts.
        # Entries come in pairs: SCHEMA_COLUMN followed by QUERY.
        mapping: List[Dict[str, str]] = []
        raw_mapping = self._get_param(node, "MAPPING", [])
        if isinstance(raw_mapping, list):
            column = None
            for entry in raw_mapping:
                ref = entry.get("elementRef", "")
                val = entry.get("value", "").strip('"')
                if ref == "SCHEMA_COLUMN":
                    column = val
                elif ref == "QUERY" and column:
                    mapping.append({"column": column, "xpath": val})
                    column = None

        filename = self._get_str(node, "FILENAME")
        if not filename:
            warnings.append("FILENAME is empty — this is a required parameter")

        loop_query = self._get_str(node, "LOOP_QUERY")
        if not loop_query:
            warnings.append("LOOP_QUERY is empty — this is a required parameter")

        config: Dict[str, Any] = {
            "filename": filename,
            "loop_query": loop_query,
            "mapping": mapping,
            "limit": self._get_int(node, "LIMIT"),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR"),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            "ignore_ns": self._get_bool(node, "IGNORE_NS"),
        }

        # Build output schema from FLOW metadata
        output_schema = self._parse_schema(node, "FLOW")

        component = self._build_component_dict(
            node=node,
            type_name="FileInputXML",
            config=config,
            schema={"input": [], "output": output_schema},
        )

        return ComponentResult(component=component, warnings=warnings)
