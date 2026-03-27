"""Converter for tFilterRow / tFilterRows -> FilterRows."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# Map Talend XML-escaped logical operators to clean names
_LOGICAL_OP_MAP = {
    "&&": "AND",
    "&amp;&amp;": "AND",
    "||": "OR",
}


def _clean_logical_op(raw: str) -> str:
    """Normalise a Talend LOGICAL_OP value to AND / OR."""
    return _LOGICAL_OP_MAP.get(raw, raw)


def _parse_conditions(node: TalendNode) -> List[Dict[str, str]]:
    """Parse the CONDITIONS table parameter into a list of condition dicts.

    Each condition row has 5 fields: INPUT_COLUMN, FUNCTION, OPERATOR, RVALUE, PREFILTER.
    """
    raw = node.params.get("CONDITIONS")
    if not raw or not isinstance(raw, list):
        return []

    conditions: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")
        if ref == "INPUT_COLUMN":
            if current:
                conditions.append(current)
            current = {"column": val, "function": "", "operator": "", "value": "", "prefilter": ""}
        elif ref == "FUNCTION" and current:
            current["function"] = val
        elif ref == "OPERATOR" and current:
            current["operator"] = val
        elif ref == "RVALUE" and current:
            current["value"] = val
        elif ref == "PREFILTER" and current:
            current["prefilter"] = val
    if current:
        conditions.append(current)
    return conditions


@REGISTRY.register("tFilterRow", "tFilterRows")
class FilterRowsConverter(ComponentConverter):
    """Convert a Talend tFilterRow / tFilterRows node to v1 FilterRows."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        logical_op_raw = self._get_str(node, "LOGICAL_OP", "AND")
        logical_operator = _clean_logical_op(logical_op_raw)

        use_advanced = self._get_bool(node, "USE_ADVANCED", False)
        advanced_condition = self._get_str(node, "ADVANCED_COND", "")

        conditions = _parse_conditions(node)

        if not use_advanced and not conditions:
            warnings.append(
                "No CONDITIONS defined and USE_ADVANCED is false "
                "-- filter will have no effect"
            )

        # Engine-gap warnings
        if self._get_bool(node, "DIE_ON_ERROR", False):
            warnings.append(
                "DIE_ON_ERROR=true: engine FilterRows does not implement "
                "die_on_error — all errors propagate as exceptions"
            )

        unsupported_functions = {
            c.get("function", "")
            for c in conditions
            if c.get("function", "") and c.get("function", "") != "EMPTY"
        }
        if unsupported_functions:
            warnings.append(
                f"CONDITIONS use FUNCTION pre-transforms {unsupported_functions}: "
                "engine does not support function pre-transforms"
            )

        string_ops = {"CONTAINS", "NOT_CONTAINS", "STARTS_WITH", "ENDS_WITH", "MATCH_REGEX"}
        used_string_ops = {
            c.get("operator", "") for c in conditions if c.get("operator", "") in string_ops
        }
        if used_string_ops:
            warnings.append(
                f"CONDITIONS use string operators {used_string_ops}: "
                "engine only supports ==, !=, <, >, <=, >="
            )

        if any(c.get("prefilter", "").strip() for c in conditions):
            warnings.append(
                "CONDITIONS use PREFILTER expressions: "
                "engine does not support pre-filter evaluation"
            )

        config: Dict[str, Any] = {
            "logical_operator": logical_operator,
            "use_advanced": use_advanced,
            "advanced_condition": advanced_condition,
            "conditions": conditions,
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        schema_cols = self._parse_schema(node)
        component = self._build_component_dict(
            node=node,
            type_name="FilterRows",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
