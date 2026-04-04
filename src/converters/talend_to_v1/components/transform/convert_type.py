"""Converter for Talend tConvertType component.

Converts column data types with optional auto-casting and manual type mapping.

Config mapping (4 params + framework):
  AUTOCAST    -> autocast    (bool, CHECK, default False)
  MANUALTABLE -> manualtable (list of dicts, stride-2 TABLE)
    INPUT_COLUMN  -> input_column  (str)
    OUTPUT_COLUMN -> output_column (str)
  EMPTYTONULL -> emptytonull (bool, CHECK, default False)
  DIEONERROR  -> dieonerror  (bool, CHECK, default False)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Note: _java.xml defines MANUALTABLE with INPUT_COLUMN/OUTPUT_COLUMN elementRefs.
No .item file evidence found to contradict, so _java.xml names are used.

No v1 engine implementation exists -- single consolidated needs_review per D-27.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_MANUALTABLE_FIELDS = ("INPUT_COLUMN", "OUTPUT_COLUMN")
_MANUALTABLE_GROUP_SIZE = len(_MANUALTABLE_FIELDS)


# ------------------------------------------------------------------
# TABLE parser
# ------------------------------------------------------------------
def _parse_manualtable(raw: Any) -> List[Dict[str, str]]:
    """Parse MANUALTABLE TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      INPUT_COLUMN  -> input_column  (str)
      OUTPUT_COLUMN -> output_column (str)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _MANUALTABLE_GROUP_SIZE):
        group = raw[i: i + _MANUALTABLE_GROUP_SIZE]
        if len(group) < _MANUALTABLE_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "INPUT_COLUMN":
                row["input_column"] = val.strip('"')
            elif ref == "OUTPUT_COLUMN":
                row["output_column"] = val.strip('"')
        if row:
            result.append(row)
    return result


@REGISTRY.register("tConvertType")
class ConvertTypeConverter(ComponentConverter):
    """Convert Talend tConvertType to v1 engine config."""

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
        config["autocast"] = self._get_bool(node, "AUTOCAST", False)
        config["manualtable"] = _parse_manualtable(node.params.get("MANUALTABLE"))
        config["emptytonull"] = self._get_bool(node, "EMPTYTONULL", False)
        config["dieonerror"] = self._get_bool(node, "DIEONERROR", False)

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Schema (passthrough: input == output) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 4. Consolidated needs_review (no engine, D-27) ----
        needs_review.append({
            "issue": "No v1 engine implementation for tConvertType -- all config keys unread",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 5. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tConvertType",
            config=config,
            schema=schema,
        )

        # ---- 6. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
