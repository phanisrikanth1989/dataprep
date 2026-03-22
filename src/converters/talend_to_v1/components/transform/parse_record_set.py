"""Converter for Talend tParseRecordSet -> v1 ParseRecordSet component.

tParseRecordSet parses a recordset field into individual columns based on
an attribute table mapping.  The ATTRIBUTE_TABLE table parameter contains
flat ``{elementRef, value}`` entries — each entry's ``value`` is extracted
into a simple list of attribute names.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tParseRecordSet")
class ParseRecordSetConverter(ComponentConverter):
    """Convert a Talend tParseRecordSet node into a v1 ParseRecordSet component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Simple parameters
        # ------------------------------------------------------------------
        recordset_field = self._get_str(node, "RECORDSET_FIELD")
        connection_format = self._get_str(
            node, "CONNECTION_FORMAT", default="row",
        )

        if not recordset_field:
            warnings.append(
                "RECORDSET_FIELD is empty — component will have no effect"
            )

        # ------------------------------------------------------------------
        # Parse ATTRIBUTE_TABLE
        # ------------------------------------------------------------------
        attribute_table = self._parse_attribute_table(node, warnings)

        # ------------------------------------------------------------------
        # Build config
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "recordset_field": recordset_field,
            "connection_format": connection_format,
            "attribute_table": attribute_table,
        }

        # ------------------------------------------------------------------
        # Schema: transform component passes schema through
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="ParseRecordSet",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)

    # ------------------------------------------------------------------
    # ATTRIBUTE_TABLE parser
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_attribute_table(
        node: TalendNode,
        warnings: List[str],
    ) -> List[str]:
        """Parse the ATTRIBUTE_TABLE table parameter.

        The table is stored as a flat list of ``{elementRef, value}`` dicts.
        Each entry's ``value`` is an attribute name to extract.  Values are
        stripped of surrounding quotes.
        """
        raw = node.params.get("ATTRIBUTE_TABLE", [])
        if not isinstance(raw, list):
            warnings.append(
                "ATTRIBUTE_TABLE param is not a list "
                "— expected TABLE structure"
            )
            return []

        result: List[str] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            value = entry.get("value", "")
            # Strip surrounding quotes
            if isinstance(value, str):
                value = value.strip('"')
            if value:
                result.append(value)

        return result
