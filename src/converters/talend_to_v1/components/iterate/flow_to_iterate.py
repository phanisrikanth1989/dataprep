"""Converter for Talend tFlowToIterate component.

Converts input flow rows into iterate loop variables via globalMap.

Config mapping (5 params total):
  DEFAULT_MAP        -> default_map (bool, default True)
  MAP                -> map_entries (list[dict], default [])
  CONNECTION_FORMAT  -> connection_format (str, default "row")  [not in _java.xml]
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_MAP_FIELDS = ("KEY", "VALUE")
_MAP_GROUP_SIZE = 2


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_map_table(raw: Any) -> List[Dict[str, str]]:
    """Parse MAP TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      KEY    -> key (str, strip quotes)
      VALUE  -> value (str, strip quotes)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _MAP_GROUP_SIZE):
        group = raw[i: i + _MAP_GROUP_SIZE]
        if len(group) < _MAP_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "KEY":
                row["key"] = val.strip('"')
            elif ref == "VALUE":
                row["value"] = val.strip('"')
        if row:
            result.append(row)
    return result


@REGISTRY.register("tFlowToIterate")
class FlowToIterateConverter(ComponentConverter):
    """Convert Talend tFlowToIterate to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        params = node.params
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        default_map = self._get_bool(node, "DEFAULT_MAP", True)
        config["default_map"] = default_map
        config["connection_format"] = self._get_str(node, "CONNECTION_FORMAT", "row")

        # ---- 2. TABLE parameters ----
        if not default_map:
            config["map_entries"] = _parse_map_table(params.get("MAP", []))
        else:
            config["map_entries"] = []

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tFlowToIterate",
            config=config,
            schema={"input": [], "output": []},
        )

        # ---- 5. Engine gap needs_review entries ----
        needs_review.append({
            "issue": "No concrete engine implementation for tFlowToIterate -- only BaseIterateComponent abstract base exists. All config keys are extracted for future engine support.",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 6. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
