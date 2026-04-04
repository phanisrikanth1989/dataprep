"""Converter for Talend tParseRecordSet component.

Parses a record set (JDBC ResultSet) column into individual columns.

Config mapping (2 unique params + framework):
  RECORDSET_FIELD  -> recordset_field  (str, PREV_COLUMN_LIST, default "")
  ATTRIBUTE_TABLE  -> attribute_table  (list, TABLE stride-1 VALUE from schema)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: CONNECTION_FORMAT (not in _java.xml)
No v1 engine implementation -- single consolidated needs_review per D-27.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# TABLE parser
# ------------------------------------------------------------------
def _parse_attribute_table(raw: Any) -> List[str]:
    """Parse ATTRIBUTE_TABLE TABLE into list of attribute name strings.

    The table uses stride-1 with a single VALUE field (BASED_ON_SCHEMA=true).
    Each entry's ``value`` is an attribute name to extract.  Values are
    stripped of surrounding quotes.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        value = entry.get("value", "")
        if isinstance(value, str):
            value = value.strip('"')
        if value:
            result.append(value)
    return result


@REGISTRY.register("tParseRecordSet")
class ParseRecordSetConverter(ComponentConverter):
    """Convert Talend tParseRecordSet to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["recordset_field"] = self._get_str(node, "RECORDSET_FIELD", "")

        # ---- 2. TABLE parameters ----
        raw_table = node.params.get("ATTRIBUTE_TABLE", [])
        config["attribute_table"] = _parse_attribute_table(raw_table)

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Schema: transform component passes schema through ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 5. Engine gap needs_review entries ----
        # No v1 engine implementation -- single consolidated per D-27
        needs_review.append({
            "issue": (
                "No v1 engine implementation for tParseRecordSet -- "
                "entire component is unimplemented; converter output "
                "cannot be executed at runtime"
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 6. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tParseRecordSet",
            config=config,
            schema=schema,
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
