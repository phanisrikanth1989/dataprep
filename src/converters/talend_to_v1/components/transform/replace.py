"""Converter for tReplace -> Replace."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# Fields per substitution row, in the order Talend serialises them
_SUBST_FIELDS = (
    "INPUT_COLUMN",
    "SEARCH_PATTERN",
    "REPLACE_STRING",
    "WHOLE_WORD",
    "CASE_SENSITIVE",
    "USE_GLOB",
    "COMMENT",
)

_SUBST_GROUP_SIZE = len(_SUBST_FIELDS)


def _strip_quotes(value: str) -> str:
    """Remove surrounding &quot; or plain double-quote pairs from *value*."""
    if value.startswith("&quot;") and value.endswith("&quot;"):
        return value[6:-6]
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        return value[1:-1]
    return value


def _parse_substitutions(raw: Any) -> List[Dict[str, Any]]:
    """Parse the flat SUBSTITUTIONS table into a list of substitution dicts.

    XmlParser stores TABLE params as a flat list of ``{elementRef, value}``
    dicts.  Each substitution group is 7 consecutive entries (see
    ``_SUBST_FIELDS``).
    """
    if not raw or not isinstance(raw, list):
        return []

    substitutions: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _SUBST_GROUP_SIZE):
        group = raw[i : i + _SUBST_GROUP_SIZE]
        if len(group) < _SUBST_GROUP_SIZE:
            break

        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")

            if ref == "INPUT_COLUMN":
                row["input_column"] = val
            elif ref == "SEARCH_PATTERN":
                row["search_pattern"] = _strip_quotes(val)
            elif ref == "REPLACE_STRING":
                row["replace_string"] = _strip_quotes(val)
            elif ref == "WHOLE_WORD":
                row["whole_word"] = val.lower() == "true"
            elif ref == "CASE_SENSITIVE":
                row["case_sensitive"] = val.lower() == "true"
            elif ref == "USE_GLOB":
                row["use_glob"] = val.lower() == "true"
            elif ref == "COMMENT":
                row["comment"] = val

        # Only emit when we have the two mandatory fields
        if row.get("input_column") and "search_pattern" in row:
            substitutions.append({
                "input_column": row.get("input_column", ""),
                "search_pattern": row.get("search_pattern", ""),
                "replace_string": row.get("replace_string", ""),
                "whole_word": row.get("whole_word", False),
                "case_sensitive": row.get("case_sensitive", False),
                "use_glob": row.get("use_glob", False),
                "comment": row.get("comment", ""),
            })

    return substitutions


@REGISTRY.register("tReplace")
class ReplaceConverter(ComponentConverter):
    """Convert a Talend tReplace node to v1 Replace."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        simple_mode = self._get_bool(node, "SIMPLE_MODE", True)
        advanced_mode = self._get_bool(node, "ADVANCED_MODE", False)
        strict_match = self._get_bool(node, "STRICT_MATCH", True)
        connection_format = self._get_str(node, "CONNECTION_FORMAT", "row")

        substitutions = _parse_substitutions(
            node.params.get("SUBSTITUTIONS")
        )

        if not substitutions:
            warnings.append(
                "No SUBSTITUTIONS defined -- replace will have no effect"
            )

        # Derive unique columns referenced by the substitution rules
        columns = sorted(
            {s["input_column"] for s in substitutions if s.get("input_column")}
        )

        config: Dict[str, Any] = {
            "simple_mode": simple_mode,
            "advanced_mode": advanced_mode,
            "strict_match": strict_match,
            "connection_format": connection_format,
            "substitutions": substitutions,
            "columns": columns,
        }

        schema_cols = self._parse_schema(node)
        component = self._build_component_dict(
            node=node,
            type_name="Replace",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
