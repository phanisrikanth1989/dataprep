"""Converter for Talend tSortRow component.

Sorts rows by one or more columns with configurable type and direction.

Config mapping (5 params + framework):
  CRITERIA -> criteria (list of dicts, stride-3 TABLE)
    COLNAME              -> column    (str)
    SORT                 -> sort_type (str: "num"/"alpha"/"date", default "num")
    ORDER                -> order     (str: "asc"/"desc", default "asc")
  EXTERNAL               -> external               (bool, CHECK, default False)
  TEMPFILE               -> tempfile                (str, DIRECTORY, default "__COMP_DEFAULT_FILE_DIR__/temp")
  CREATEDIR              -> createdir               (bool, CHECK, default True)
  EXTERNAL_SORT_BUFFERSIZE -> external_sort_buffersize (str, TEXT, default "1000000")
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: SORT_TYPE (not a _java.xml column -- SORT is the type column),
EXTERNAL_SORT (correct name is EXTERNAL), BUFFER_SIZE (correct name is EXTERNAL_SORT_BUFFERSIZE)

CRITICAL FIX: _java.xml SORT column = data type (NUM/ALPHA/DATE), ORDER column = direction (ASC/DESC).
Previous converter had these inverted.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# CRITERIA TABLE constants
# ------------------------------------------------------------------
_CRITERIA_FIELDS = ("COLNAME", "SORT", "ORDER")
_CRITERIA_GROUP_SIZE = len(_CRITERIA_FIELDS)


# ------------------------------------------------------------------
# CRITERIA TABLE parser
# ------------------------------------------------------------------
def _parse_criteria(raw: Any) -> List[Dict[str, str]]:
    """Parse CRITERIA TABLE into list of sort criterion dicts.

    Each group of 3 consecutive elementRef entries maps to one criterion:
      COLNAME -> column    (str)
      SORT    -> sort_type (str: "num", "alpha", "date"; default "num")
      ORDER   -> order     (str: "asc", "desc"; default "asc")

    Incomplete trailing groups (< 3 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _CRITERIA_GROUP_SIZE):
        group = raw[i: i + _CRITERIA_GROUP_SIZE]
        if len(group) < _CRITERIA_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "").strip('"')
            if ref == "COLNAME":
                row["column"] = val
            elif ref == "SORT":
                row["sort_type"] = val.lower() if val else "num"
            elif ref == "ORDER":
                row["order"] = val.lower() if val else "asc"
        if row.get("column"):
            result.append({
                "column": row.get("column", ""),
                "sort_type": row.get("sort_type", "num"),
                "order": row.get("order", "asc"),
            })
    return result


@REGISTRY.register("tSortRow")
class SortRowConverter(ComponentConverter):
    """Convert Talend tSortRow to v1 SortRow config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. TABLE parameters ----
        config: Dict[str, Any] = {}
        raw_criteria = node.params.get("CRITERIA", [])
        config["criteria"] = _parse_criteria(raw_criteria)

        # ---- 2. Core parameters ----
        config["external"] = self._get_bool(node, "EXTERNAL", False)
        config["tempfile"] = self._get_str(node, "TEMPFILE", "__COMP_DEFAULT_FILE_DIR__/temp")
        config["createdir"] = self._get_bool(node, "CREATEDIR", True)
        config["external_sort_buffersize"] = self._get_str(node, "EXTERNAL_SORT_BUFFERSIZE", "1000000")

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Schema (transform passthrough) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 5. Engine gap needs_review entries ----
        _engine_gap_keys = [
            ("na_position", "Engine reads 'na_position' (default 'last') but this is not a _java.xml param"),
            ("case_sensitive", "Engine reads 'case_sensitive' (default True) but this is not a _java.xml param"),
            ("chunk_size", "Engine reads 'chunk_size' (default 10000) but this is not a _java.xml param"),
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
            type_name="SortRow",
            config=config,
            schema=schema,
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
