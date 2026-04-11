"""Converter for Talend tJoin component.

Joins main input with lookup input using key columns.

Config mapping (4 unique params + framework):
  USE_INNER_JOIN  -> use_inner_join  (bool, default False)
  JOIN_KEY        -> join_key        (list, TABLE stride-2 INPUT_COLUMN+LOOKUP_COLUMN)
  USE_LOOKUP_COLS -> use_lookup_cols (bool, default False)
  LOOKUP_COLS     -> lookup_cols     (list, TABLE stride-2 OUTPUT_COLUMN+LOOKUP_COLUMN)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: CASE_SENSITIVE, DIE_ON_ERROR (not in _java.xml)
Engine reads UPPERCASE keys (JOIN_KEY, USE_INNER_JOIN, CASE_SENSITIVE, DIE_ON_ERROR, OUTPUT_COLUMNS)
-- documented as needs_review entries for key mismatch.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_JOIN_KEY_FIELDS = ("INPUT_COLUMN", "LOOKUP_COLUMN")
_JOIN_KEY_FALLBACK = {"LEFT_COLUMN": "INPUT_COLUMN", "RIGHT_COLUMN": "LOOKUP_COLUMN"}
_JOIN_KEY_GROUP_SIZE = len(_JOIN_KEY_FIELDS)

_LOOKUP_COLS_FIELDS = ("OUTPUT_COLUMN", "LOOKUP_COLUMN")
_LOOKUP_COLS_GROUP_SIZE = len(_LOOKUP_COLS_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_join_key(raw: Any) -> List[Dict[str, str]]:
    """Parse JOIN_KEY TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      INPUT_COLUMN   -> input_column  (str)
      LOOKUP_COLUMN  -> lookup_column (str)

    Supports LEFT_COLUMN/RIGHT_COLUMN as fallback elementRef names
    (mapped to input_column/lookup_column respectively).

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _JOIN_KEY_GROUP_SIZE):
        group = raw[i: i + _JOIN_KEY_GROUP_SIZE]
        if len(group) < _JOIN_KEY_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "").strip('"')
            # Map canonical names
            if ref in ("INPUT_COLUMN", "LEFT_COLUMN"):
                row["input_column"] = val
            elif ref in ("LOOKUP_COLUMN", "RIGHT_COLUMN"):
                row["lookup_column"] = val
        if row:
            result.append(row)
    return result


def _parse_lookup_cols(raw: Any) -> List[Dict[str, str]]:
    """Parse LOOKUP_COLS TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      OUTPUT_COLUMN  -> output_column  (str)
      LOOKUP_COLUMN  -> lookup_column  (str)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _LOOKUP_COLS_GROUP_SIZE):
        group = raw[i: i + _LOOKUP_COLS_GROUP_SIZE]
        if len(group) < _LOOKUP_COLS_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "").strip('"')
            if ref == "OUTPUT_COLUMN":
                row["output_column"] = val
            elif ref == "LOOKUP_COLUMN":
                row["lookup_column"] = val
        if row:
            result.append(row)
    return result


@REGISTRY.register("tJoin")
class JoinConverter(ComponentConverter):
    """Convert Talend tJoin to v1 engine config."""

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
        config["use_inner_join"] = self._get_bool(node, "USE_INNER_JOIN", False)

        # ---- 2. TABLE parameters ----
        raw_join_key = node.params.get("JOIN_KEY", [])
        config["join_key"] = _parse_join_key(raw_join_key)

        config["use_lookup_cols"] = self._get_bool(node, "USE_LOOKUP_COLS", False)

        raw_lookup_cols = node.params.get("LOOKUP_COLS", [])
        config["lookup_cols"] = _parse_lookup_cols(raw_lookup_cols)

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Schema ----
        schema_cols = self._parse_schema(node)
        reject_cols = self._parse_schema(node, "REJECT")
        schema = {"input": schema_cols, "output": schema_cols}
        if reject_cols:
            schema["reject"] = reject_cols

        # ---- 5. Engine gap needs_review entries ----
        _engine_gap_keys = [
            ("use_inner_join", "Engine reads 'USE_INNER_JOIN' (UPPERCASE) not 'use_inner_join'"),
            ("join_key", "Engine reads 'JOIN_KEY' (UPPERCASE) not 'join_key'; also expects {main, lookup} dict keys"),
            ("use_lookup_cols", "Engine does not read 'use_lookup_cols' -- no INCLUDE_LOOKUP toggle implemented"),
            ("lookup_cols", "Engine does not read 'lookup_cols' -- no lookup column selection implemented"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 6. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="Join",
            config=config,
            schema=schema,
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
