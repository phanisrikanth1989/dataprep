"""Converter for Talend tDenormalize component.

Concatenates multiple rows into single rows using delimiter-based merging.

Config mapping (1 TABLE param + framework):
  DENORMALIZE_COLUMNS -> denormalize_columns (list of dicts, stride-3 TABLE)
    INPUT_COLUMN -> input_column (str)
    DELIMITER    -> delimiter    (str, default ";")
    MERGE        -> merge        (bool, default False)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: CONNECTION_FORMAT (not in _java.xml), NULL_AS_EMPTY (not in _java.xml)
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_DENORM_FIELDS = ("INPUT_COLUMN", "DELIMITER", "MERGE")
_DENORM_GROUP_SIZE = len(_DENORM_FIELDS)


# ------------------------------------------------------------------
# TABLE parser
# ------------------------------------------------------------------
def _parse_denormalize_columns(raw: Any) -> List[Dict[str, Any]]:
    """Parse DENORMALIZE_COLUMNS TABLE into list of dicts.

    Each group of 3 consecutive elementRef entries maps to one row:
      INPUT_COLUMN -> input_column (str, quotes stripped)
      DELIMITER    -> delimiter    (str, default ";")
      MERGE        -> merge        (bool, default False)

    Incomplete trailing groups (< 3 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _DENORM_GROUP_SIZE):
        group = raw[i: i + _DENORM_GROUP_SIZE]
        if len(group) < _DENORM_GROUP_SIZE:
            break
        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "INPUT_COLUMN":
                row["input_column"] = val.strip('"')
            elif ref == "DELIMITER":
                row["delimiter"] = val.strip('"')
            elif ref == "MERGE":
                row["merge"] = val.strip().lower() == "true"
        # Apply defaults for missing fields
        if "input_column" in row:
            row.setdefault("delimiter", ";")
            row.setdefault("merge", False)
            result.append(row)
    return result


@REGISTRY.register("tDenormalize")
class DenormalizeConverter(ComponentConverter):
    """Convert Talend tDenormalize to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters: DENORMALIZE_COLUMNS TABLE ----
        config: Dict[str, Any] = {}
        raw_table = node.params.get("DENORMALIZE_COLUMNS", [])
        config["denormalize_columns"] = _parse_denormalize_columns(raw_table)

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Schema: transform component passes schema through ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 4. Engine gap needs_review entries ----
        # Engine delimiter default is "," (line 181) but _java.xml default is ";"
        needs_review.append({
            "issue": (
                "Engine Denormalize uses delimiter default ',' (line 181) "
                "but _java.xml DEFAULT is ';' -- converter emits explicit "
                "delimiter per column so engine fallback is not reached for "
                "converter-produced configs"
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # Engine reads null_as_empty (default False) but this param is not in _java.xml
        needs_review.append({
            "issue": (
                "Engine reads 'null_as_empty' config key (default False) "
                "but NULL_AS_EMPTY is not a _java.xml parameter -- "
                "engine-only config key"
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # Conditional: merge flag engine gap (engine does not read merge)
        merge_cols = [
            col["input_column"]
            for col in config["denormalize_columns"]
            if col.get("merge") is True
        ]
        if merge_cols:
            needs_review.append({
                "issue": (
                    f"Column(s) {merge_cols} have merge=True but the v1 "
                    f"engine Denormalize component does not read the merge "
                    f"flag -- deduplication before concatenation will not "
                    f"occur at runtime"
                ),
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 5. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="Denormalize",
            config=config,
            schema=schema,
        )

        # ---- 6. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
