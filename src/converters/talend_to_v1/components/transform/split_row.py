"""Converter for Talend tSplitRow component.

Splits rows from input to multiple outputs based on column mapping.

Config mapping (1 TABLE param + framework):
  COL_MAPPING -> col_mapping (list of dicts, stride-2 TABLE)
    SOURCE_COLUMN -> source_column (str)
    TARGET_COLUMN -> target_column (str)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: CONNECTION_FORMAT (not in _java.xml)

Note: _java.xml defines COL_MAPPING with COLUMNS_BASED_ON_SCHEMA="true" but
.item file exports contain SOURCE_COLUMN/TARGET_COLUMN elementRef entries.
Parser handles the .item export format per project convention (.item is source of truth).

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
_COL_MAPPING_FIELDS = ("SOURCE_COLUMN", "TARGET_COLUMN")
_COL_MAPPING_GROUP_SIZE = len(_COL_MAPPING_FIELDS)


# ------------------------------------------------------------------
# TABLE parser
# ------------------------------------------------------------------
def _parse_col_mapping(raw: Any) -> List[Dict[str, str]]:
    """Parse COL_MAPPING TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      SOURCE_COLUMN -> source_column (str, quotes stripped)
      TARGET_COLUMN -> target_column (str, quotes stripped)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _COL_MAPPING_GROUP_SIZE):
        group = raw[i: i + _COL_MAPPING_GROUP_SIZE]
        if len(group) < _COL_MAPPING_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SOURCE_COLUMN":
                row["source_column"] = val.strip('"')
            elif ref == "TARGET_COLUMN":
                row["target_column"] = val.strip('"')
        if row:
            result.append(row)
    return result


@REGISTRY.register("tSplitRow")
class SplitRowConverter(ComponentConverter):
    """Convert Talend tSplitRow to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters: COL_MAPPING TABLE ----
        config: Dict[str, Any] = {}
        raw_table = node.params.get("COL_MAPPING", [])
        config["col_mapping"] = _parse_col_mapping(raw_table)

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Schema: transform component passes schema through ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 4. Engine gap needs_review entries ----
        # No v1 engine implementation -- single consolidated per D-27
        needs_review.append({
            "issue": (
                "No v1 engine implementation for tSplitRow -- "
                "entire component is unimplemented; converter output "
                "cannot be executed at runtime"
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 5. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tSplitRow",
            config=config,
            schema=schema,
        )

        # ---- 6. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
