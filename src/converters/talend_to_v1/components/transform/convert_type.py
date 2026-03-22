"""Converter for tConvertType -> ConvertType."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


def _parse_manual_table(node: TalendNode) -> List[Dict[str, str]]:
    """Parse the MANUALTABLE table parameter into a list of column/target_type dicts.

    XmlParser stores TABLE params as a flat list of {elementRef, value} dicts.
    Each entry pair is: SCHEMA_COLUMN (column name), CONVERT_TO (target type).
    """
    raw = node.params.get("MANUALTABLE")
    if not raw or not isinstance(raw, list):
        return []

    entries: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")
        if ref == "SCHEMA_COLUMN":
            if current:
                entries.append(current)
            current = {"column": val}
        elif ref == "CONVERT_TO" and current:
            current["target_type"] = val
            entries.append(current)
            current = {}
    # Flush any partial entry (column without target_type)
    if current:
        entries.append(current)
    return entries


@REGISTRY.register("tConvertType")
class ConvertTypeConverter(ComponentConverter):
    """Convert a Talend tConvertType node to v1 ConvertType."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        autocast = self._get_bool(node, "AUTOCAST", False)
        empty_to_null = self._get_bool(node, "EMPTYTONULL", False)
        die_on_error = self._get_bool(node, "DIEONERROR", False)

        manual_table = _parse_manual_table(node)

        if not autocast and not manual_table:
            warnings.append(
                "AUTOCAST is disabled and MANUALTABLE is empty "
                "-- conversion will have no effect"
            )

        config: Dict[str, Any] = {
            "autocast": autocast,
            "empty_to_null": empty_to_null,
            "die_on_error": die_on_error,
            "manual_table": manual_table,
        }

        schema_cols = self._parse_schema(node)
        component = self._build_component_dict(
            node=node,
            type_name="ConvertType",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
