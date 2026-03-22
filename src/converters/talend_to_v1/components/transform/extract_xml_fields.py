"""Converter for Talend tExtractXMLField -> v1 ExtractXMLField.

tExtractXMLField extracts structured data from an XML column by applying an
XPath loop query and mapping individual XPath expressions to output columns.

The MAPPING TABLE parameter is serialised as a flat list of
``{elementRef, value}`` dicts with three entries per mapping row:
SCHEMA_COLUMN, QUERY, and NODECHECK.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# Fields per mapping row, in Talend serialisation order
_MAPPING_FIELDS = ("SCHEMA_COLUMN", "QUERY", "NODECHECK")
_MAPPING_GROUP_SIZE = len(_MAPPING_FIELDS)


def _strip_quotes(value: str) -> str:
    """Remove surrounding double-quote pairs from *value*."""
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        return value[1:-1]
    return value


def _parse_mapping(raw: Any) -> List[Dict[str, str]]:
    """Parse the flat MAPPING table into a list of mapping dicts.

    XmlParser stores TABLE params as a flat list of ``{elementRef, value}``
    dicts.  Each mapping group is 3 consecutive entries:
    SCHEMA_COLUMN, QUERY, NODECHECK.
    """
    if not raw or not isinstance(raw, list):
        return []

    mappings: List[Dict[str, str]] = []
    for i in range(0, len(raw), _MAPPING_GROUP_SIZE):
        group = raw[i: i + _MAPPING_GROUP_SIZE]
        if len(group) < _MAPPING_GROUP_SIZE:
            break

        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")

            if ref == "SCHEMA_COLUMN":
                row["schema_column"] = _strip_quotes(val)
            elif ref == "QUERY":
                row["query"] = _strip_quotes(val)
            elif ref == "NODECHECK":
                row["nodecheck"] = val

        if row.get("schema_column"):
            mappings.append({
                "schema_column": row.get("schema_column", ""),
                "query": row.get("query", ""),
                "nodecheck": row.get("nodecheck", ""),
            })

    return mappings


@REGISTRY.register("tExtractXMLField")
class ExtractXMLFieldConverter(ComponentConverter):
    """Convert a Talend tExtractXMLField node to v1 ExtractXMLField."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Extract parameters
        # ------------------------------------------------------------------
        xml_field = self._get_str(node, "XMLFIELD", "line")
        loop_query = self._get_str(node, "LOOP_QUERY", "")
        limit = self._get_str(node, "LIMIT", "0")
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", False)
        ignore_ns = self._get_bool(node, "IGNORE_NS", False)

        # Parse MAPPING table
        mapping = _parse_mapping(node.params.get("MAPPING"))

        # ------------------------------------------------------------------
        # Validation warnings
        # ------------------------------------------------------------------
        if not loop_query:
            warnings.append(
                "LOOP_QUERY is empty -- XML extraction will have no effect"
            )

        if not mapping:
            warnings.append(
                "No MAPPING entries defined -- no columns will be extracted"
            )

        # ------------------------------------------------------------------
        # Build config
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "xml_field": xml_field,
            "loop_query": loop_query,
            "mapping": mapping,
            "limit": limit,
            "die_on_error": die_on_error,
            "ignore_ns": ignore_ns,
        }

        # ------------------------------------------------------------------
        # Schema: transform component passes schema through
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema: Dict[str, Any] = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="ExtractXMLField",
            config=config,
            schema=schema,
        )

        return ComponentResult(component=component, warnings=warnings)
