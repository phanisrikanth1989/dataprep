"""Converter for Talend tExtractJSONFields -> v1 ExtractJSONFields.

tExtractJSONFields extracts values from a JSON string column in the input
using JSONPath (or XPath-like) queries, mapping them to output schema columns.

Fixes vs. old code (CONV-EJF-001 to EJF-008):
  - CONV-EJF-001: Self-contained converter — no dual-parser conflict.
  - CONV-EJF-002: MAPPING_4_JSONPATH parsed via elementRef keys, not fragile
    stride-2 positional indexing that breaks when column order varies.
  - CONV-EJF-003: LOOP_QUERY falls back to JSON_LOOP_QUERY (alternate name).
  - CONV-EJF-004: Surrounding quotes stripped from loop_query and mapping values.
  - CONV-EJF-005: Boolean params (die_on_error, use_loop_as_root, split_list)
    are Python bools, not strings.
  - CONV-EJF-006: Schema passthrough (input == output) for transform component.
  - CONV-EJF-007: read_by defaults to 'JSONPATH' when absent.
  - CONV-EJF-008: json_field extracted correctly.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# Fields per mapping row in MAPPING_4_JSONPATH table
_MAPPING_FIELDS = ("SCHEMA_COLUMN", "JSON_PATH_QUERY")
_MAPPING_GROUP_SIZE = len(_MAPPING_FIELDS)


def _strip_quotes(value: str) -> str:
    """Remove surrounding double-quote pairs from *value*."""
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        return value[1:-1]
    return value


def _parse_mapping(raw: Any) -> List[Dict[str, str]]:
    """Parse the flat MAPPING_4_JSONPATH table into a list of mapping dicts.

    XmlParser stores TABLE params as a flat list of ``{elementRef, value}``
    dicts.  Each mapping row is a group of 2 consecutive entries with
    elementRef values ``SCHEMA_COLUMN`` and ``JSON_PATH_QUERY``.

    Using elementRef-based parsing (not positional stride-2) so the order
    of entries within a group does not matter (fixes CONV-EJF-002).
    """
    if not raw or not isinstance(raw, list):
        return []

    mapping: List[Dict[str, str]] = []
    for i in range(0, len(raw), _MAPPING_GROUP_SIZE):
        group = raw[i : i + _MAPPING_GROUP_SIZE]
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
            elif ref == "JSON_PATH_QUERY":
                row["query"] = _strip_quotes(val)

        if row.get("schema_column"):
            mapping.append({
                "schema_column": row.get("schema_column", ""),
                "query": row.get("query", ""),
            })

    return mapping


@REGISTRY.register("tExtractJSONFields")
class ExtractJSONFieldsConverter(ComponentConverter):
    """Convert a Talend tExtractJSONFields node to v1 ExtractJSONFields."""

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
        read_by = self._get_str(node, "READ_BY", "JSONPATH")
        json_path_version = self._get_str(node, "JSON_PATH_VERSION", "2_1_0")

        # LOOP_QUERY may appear under either name (CONV-EJF-003)
        loop_query = self._get_str(node, "LOOP_QUERY", "")
        if not loop_query:
            loop_query = self._get_str(node, "JSON_LOOP_QUERY", "")

        die_on_error = self._get_bool(node, "DIE_ON_ERROR", False)
        encoding = self._get_str(node, "ENCODING", "UTF-8")
        use_loop_as_root = self._get_bool(node, "USE_LOOP_AS_ROOT", False)
        split_list = self._get_bool(node, "SPLIT_LIST", False)
        json_field = self._get_str(node, "JSONFIELD", "")

        # ------------------------------------------------------------------
        # Parse mapping table (CONV-EJF-002)
        # ------------------------------------------------------------------
        mapping = _parse_mapping(node.params.get("MAPPING_4_JSONPATH"))

        # ------------------------------------------------------------------
        # Validation warnings
        # ------------------------------------------------------------------
        if not loop_query:
            warnings.append(
                "LOOP_QUERY is empty — JSONPath extraction may not work correctly"
            )
        if not mapping:
            warnings.append(
                "No MAPPING_4_JSONPATH entries — no fields will be extracted"
            )

        # ------------------------------------------------------------------
        # Build config
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "read_by": read_by,
            "json_path_version": json_path_version,
            "loop_query": loop_query,
            "die_on_error": die_on_error,
            "encoding": encoding,
            "use_loop_as_root": use_loop_as_root,
            "split_list": split_list,
            "json_field": json_field,
            "mapping": mapping,
        }

        # ------------------------------------------------------------------
        # Schema: transform component passes schema through (CONV-EJF-006)
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema: Dict[str, Any] = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="ExtractJSONFields",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)
