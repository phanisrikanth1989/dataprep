"""Converter for Talend tMemorizeRows component.

Memorizes the last N rows passing through the component.

Config mapping (2 unique params + framework):
  ROW_COUNT     -> row_count     (str, TEXT, default "1")  -- str for expression support
  SPECIFY_COLS  -> specify_cols  (list, TABLE BASED_ON_SCHEMA stride-1 MEMORIZE_IT CHECK)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: RESET_ON_CONDITION, CONDITION (not in _java.xml)
No v1 engine implementation -- single consolidated needs_review per D-27.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_SPECIFY_COLS_FIELDS = ("MEMORIZE_IT",)
_SPECIFY_COLS_GROUP_SIZE = len(_SPECIFY_COLS_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_specify_cols(raw: Any) -> List[Dict[str, Any]]:
    """Parse SPECIFY_COLS TABLE into list of dicts.

    Each group of 1 consecutive elementRef entry maps to one row:
      MEMORIZE_IT  -> memorize_it (bool, CHECK)

    BASED_ON_SCHEMA=true means one entry per schema column.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _SPECIFY_COLS_GROUP_SIZE):
        group = raw[i: i + _SPECIFY_COLS_GROUP_SIZE]
        if len(group) < _SPECIFY_COLS_GROUP_SIZE:
            break
        entry = group[0]
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")
        if ref == "MEMORIZE_IT":
            result.append({
                "memorize_it": val.lower() in ("true", "1"),
            })
    return result


@REGISTRY.register("tMemorizeRows")
class MemorizeRowsConverter(ComponentConverter):
    """Convert Talend tMemorizeRows to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        """Convert a TalendNode into a v1 tMemorizeRows component dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["row_count"] = self._get_str(node, "ROW_COUNT", "1")

        # ---- 3. TABLE parameters ----
        raw_specify_cols = node.params.get("SPECIFY_COLS", [])
        config["specify_cols"] = _parse_specify_cols(raw_specify_cols)

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema (passthrough transform: input == output) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 7. Engine gap needs_review (single consolidated per D-27) ----
        needs_review.append({
            "issue": (
                "No v1 engine implementation exists for tMemorizeRows. "
                "Converter output is syntactically valid but cannot execute at runtime."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tMemorizeRows",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
