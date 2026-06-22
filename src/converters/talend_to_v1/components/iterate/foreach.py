"""Converter for Talend tForeach component.

Iterates over a static list of values, exposing each as CURRENT_VALUE in globalMap.

Config mapping (3 params total):
  VALUES             -> values (list[str], default [])
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
_VALUES_FIELDS = ("VALUE",)
_VALUES_GROUP_SIZE = 1


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_values_table(raw: Any) -> List[str]:
    """Parse VALUES TABLE into list of strings.

    Each group of 1 consecutive elementRef entry maps to one row:
      VALUE  -> value (str, strip quotes)

    Incomplete trailing groups (< 1 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[str] = []
    for i in range(0, len(raw), _VALUES_GROUP_SIZE):
        group = raw[i: i + _VALUES_GROUP_SIZE]
        if len(group) < _VALUES_GROUP_SIZE:
            break
        entry = group[0]
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        if ref == "VALUE":
            val = entry.get("value", "")
            result.append(val.strip('"'))
    return result


@REGISTRY.register("tForeach")
class ForeachConverter(ComponentConverter):
    """Convert Talend tForeach to v1 engine config."""

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

        # ---- 2. TABLE parameters ----
        config["values"] = _parse_values_table(params.get("VALUES", []))

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tForeach",
            config=config,
            schema={"input": [], "output": []},
        )

        # ---- 5. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
