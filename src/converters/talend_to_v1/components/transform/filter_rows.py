"""Converter for Talend tFilterRow component.

Filters rows based on conditions or advanced expressions.

Config mapping (4 params + framework):
  LOGICAL_OP    -> logical_op    (str, CLOSED_LIST, default "AND")
  CONDITIONS    -> conditions    (list of dicts, stride-4 TABLE)
    INPUT_COLUMN -> column   (str)
    FUNCTION     -> function (str)
    OPERATOR     -> operator (str)
    RVALUE       -> value    (str)
  USE_ADVANCED  -> use_advanced  (bool, CHECK, default False)
  ADVANCED_COND -> advanced_cond (str, MEMO_JAVA, default "")
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: DIE_ON_ERROR (not in _java.xml), PREFILTER (not a _java.xml column in CONDITIONS TABLE)
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# CONDITIONS TABLE constants
# ------------------------------------------------------------------
_CONDITION_FIELDS = ("INPUT_COLUMN", "FUNCTION", "OPERATOR", "RVALUE")
_CONDITION_GROUP_SIZE = len(_CONDITION_FIELDS)


# ------------------------------------------------------------------
# CONDITIONS TABLE parser
# ------------------------------------------------------------------
def _parse_conditions(raw: Any) -> List[Dict[str, str]]:
    """Parse CONDITIONS TABLE into list of dicts.

    Each group of 4 consecutive elementRef entries maps to one condition:
      INPUT_COLUMN -> column   (str)
      FUNCTION     -> function (str)
      OPERATOR     -> operator (str)
      RVALUE       -> value    (str)

    Incomplete trailing groups (< 4 entries) are skipped.
    PREFILTER entries are ignored (phantom -- not in _java.xml).
    """
    if not raw or not isinstance(raw, list):
        return []

    # Filter out any PREFILTER entries (phantom param)
    filtered = [
        entry for entry in raw
        if isinstance(entry, dict) and entry.get("elementRef", "") in _CONDITION_FIELDS
    ]

    result: List[Dict[str, str]] = []
    for i in range(0, len(filtered), _CONDITION_GROUP_SIZE):
        group = filtered[i: i + _CONDITION_GROUP_SIZE]
        if len(group) < _CONDITION_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "INPUT_COLUMN":
                row["column"] = val.strip('"')
            elif ref == "FUNCTION":
                row["function"] = val.strip('"')
            elif ref == "OPERATOR":
                row["operator"] = val.strip('"')
            elif ref == "RVALUE":
                row["value"] = val.strip('"')
        if row:
            result.append(row)
    return result


@REGISTRY.register("tFilterRow")
@REGISTRY.register("tFilterRows")
class FilterRowsConverter(ComponentConverter):
    """Convert Talend tFilterRow / tFilterRows to v1 FilterRows config."""

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
        config["logical_op"] = self._get_str(node, "LOGICAL_OP", "AND")
        config["use_advanced"] = self._get_bool(node, "USE_ADVANCED", False)
        advanced_cond = self._get_str(node, "ADVANCED_COND", "")
        if advanced_cond:
            advanced_cond = "{{java}}" + advanced_cond
        config["advanced_cond"] = advanced_cond

        # ---- 2. TABLE parameters ----
        raw_conditions = node.params.get("CONDITIONS", [])
        config["conditions"] = _parse_conditions(raw_conditions)

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Schema (transform passthrough) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 5. Engine gap needs_review entries ----
        _engine_gap_keys = [
            ("conditions.function", "Engine does not support FUNCTION pre-transforms on conditions"),
            ("advanced_cond", "Engine uses eval() for advanced conditions -- security risk, limited operator support"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine gap for '{key}' -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 6. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FilterRows",
            config=config,
            schema=schema,
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
