"""Converter for Talend tSetGlobalVar component.

Sets global variables in the globalMap for access by other components.
VARIABLES TABLE contains KEY/VALUE pairs parsed with stride-2.

Config mapping (1 TABLE + 2 framework = 3 params total):
  VARIABLES          -> variables          (TABLE stride-2: KEY/VALUE -> list of {key, value} dicts)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_VARIABLES_FIELDS = ("KEY", "VALUE")
_VARIABLES_GROUP_SIZE = len(_VARIABLES_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_variables(raw: Any) -> List[Dict[str, str]]:
    """Parse VARIABLES TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      KEY    -> key   (str)
      VALUE  -> value (str)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _VARIABLES_GROUP_SIZE):
        group = raw[i: i + _VARIABLES_GROUP_SIZE]
        if len(group) < _VARIABLES_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "").strip('"')
            if ref == "KEY":
                row["key"] = val
            elif ref == "VALUE":
                row["value"] = val
        if row:
            result.append(row)
    return result


@REGISTRY.register("tSetGlobalVar")
class SetGlobalVarConverter(ComponentConverter):
    """Convert Talend tSetGlobalVar to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. TABLE parameters ----
        raw_variables = node.params.get("VARIABLES", [])
        config: Dict[str, Any] = {}
        config["variables"] = _parse_variables(raw_variables)

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Engine gap needs_review entries ----
        # Engine reads VARIABLES (uppercase) but converter outputs 'variables' (lowercase)
        # Engine expects {name, value} dicts but converter outputs {key, value}
        needs_review.append({
            "issue": (
                "Engine reads config key 'VARIABLES' (uppercase) with {name, value} dicts "
                "but converter outputs 'variables' (lowercase) with {key, value} dicts -- "
                "variables may not be found at runtime until engine is aligned"
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 4. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="SetGlobalVar",
            config=config,
            # Utility component -- no data flow schema
            schema={"input": [], "output": []},
        )

        # ---- 5. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
