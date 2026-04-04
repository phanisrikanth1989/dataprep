"""Converter for Talend tAggregateSortedRow component.

Performs sorted-input aggregation (group-by + aggregate functions on pre-sorted data).
Lighter-weight than tAggregateRow because it assumes input is already sorted by group keys.

Config mapping (3 unique + 2 framework = 5 params total):
  GROUPBYS       -> groupbys       (TABLE stride-2: OUTPUT_COLUMN, INPUT_COLUMN)
  OPERATIONS     -> operations     (TABLE stride-4: OUTPUT_COLUMN, INPUT_COLUMN, FUNCTION, IGNORE_NULL)
  ROW_COUNT      -> row_count      (str, default "")  -- TEXT type in _java.xml, supports expressions
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL          -> label          (str, default "")

TABLE parsing:
  GROUPBYS: stride-2 (OUTPUT_COLUMN, INPUT_COLUMN) -> list of {output_column, input_column} dicts
  OPERATIONS: stride-4 with state-machine parser (flush-on-OUTPUT_COLUMN) for robustness
    with optional IGNORE_NULL field. Function mapping: distinct->count_distinct, list_object->list.

Phantom params NOT in _java.xml (excluded):
  DIE_ON_ERROR, CONNECTION_FORMAT
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Function mapping: Talend aggregate function names -> v1 engine names
# ------------------------------------------------------------------
_FUNCTION_MAP: Dict[str, str] = {
    "sum": "sum",
    "count": "count",
    "min": "min",
    "max": "max",
    "avg": "avg",
    "first": "first",
    "last": "last",
    "list": "list",
    "list_object": "list",
    "count_distinct": "count_distinct",
    "distinct": "count_distinct",
}

# ------------------------------------------------------------------
# GROUPBYS TABLE constants
# ------------------------------------------------------------------
_GROUPBYS_FIELDS = ("OUTPUT_COLUMN", "INPUT_COLUMN")
_GROUPBYS_STRIDE = len(_GROUPBYS_FIELDS)

# ------------------------------------------------------------------
# OPERATIONS TABLE fields (stride-4, parsed via state machine)
# ------------------------------------------------------------------
_OPERATIONS_FIELDS = ("OUTPUT_COLUMN", "INPUT_COLUMN", "FUNCTION", "IGNORE_NULL")


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_groupbys(raw: Any) -> List[Dict[str, str]]:
    """Parse GROUPBYS TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      OUTPUT_COLUMN -> output_column (str)
      INPUT_COLUMN  -> input_column  (str)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _GROUPBYS_STRIDE):
        group = raw[i: i + _GROUPBYS_STRIDE]
        if len(group) < _GROUPBYS_STRIDE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "").strip('"')
            if ref == "OUTPUT_COLUMN":
                row["output_column"] = val
            elif ref == "INPUT_COLUMN":
                row["input_column"] = val
        if row:
            result.append(row)
    return result


def _parse_operations(raw: Any, warnings: List[str]) -> List[Dict[str, Any]]:
    """Parse OPERATIONS TABLE using state-machine parser (flush-on-OUTPUT_COLUMN).

    Each operation group contains up to 4 elementRef entries:
      OUTPUT_COLUMN -> output_column (str)
      INPUT_COLUMN  -> input_column  (str)
      FUNCTION      -> function      (str, mapped via _FUNCTION_MAP)
      IGNORE_NULL   -> ignore_null   (bool)

    The state-machine flushes the current operation when a new OUTPUT_COLUMN
    is encountered, which is more robust than fixed-stride parsing when the
    optional IGNORE_NULL field is absent.
    """
    if not raw or not isinstance(raw, list):
        return []

    operations: List[Dict[str, Any]] = []
    current_op: Dict[str, Any] = {}

    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")

        if ref == "OUTPUT_COLUMN":
            # Flush previous operation (if any)
            if current_op:
                operations.append(current_op)
            current_op = {"output_column": val.strip('"')}
        elif ref == "INPUT_COLUMN":
            current_op["input_column"] = val.strip('"')
        elif ref == "FUNCTION":
            raw_fn = val.strip('"').lower()
            mapped = _FUNCTION_MAP.get(raw_fn, raw_fn)
            current_op["function"] = mapped
            if raw_fn == "list_object":
                warnings.append(
                    "function 'list_object' mapped to 'list' -- "
                    "object references are not preserved"
                )
        elif ref == "IGNORE_NULL":
            current_op["ignore_null"] = val.lower() in ("true", "1")

    # Flush last operation
    if current_op:
        operations.append(current_op)

    return operations


@REGISTRY.register("tAggregateSortedRow")
class AggregateSortedRowConverter(ComponentConverter):
    """Convert Talend tAggregateSortedRow to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. TABLE parameters ----
        raw_groupbys = node.params.get("GROUPBYS", [])
        groupbys = _parse_groupbys(raw_groupbys)

        raw_operations = node.params.get("OPERATIONS", [])
        operations = _parse_operations(raw_operations, warnings)

        # ---- 2. Core parameters ----
        config: Dict[str, Any] = {}
        config["groupbys"] = groupbys
        config["operations"] = operations
        config["row_count"] = self._get_str(node, "ROW_COUNT", "")

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Schema: transform -- input and output from FLOW metadata ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 5. Engine gap needs_review entries (per-feature) ----
        # Static: row_count not read by engine
        needs_review.append({
            "issue": "Engine does not read 'row_count' config key -- engine processes all rows regardless",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # Conditional: GROUPBYS output/input column renaming
        has_renaming = any(
            gb.get("output_column") != gb.get("input_column")
            for gb in groupbys
        )
        if has_renaming:
            needs_review.append({
                "issue": (
                    "GROUPBYS OUTPUT_COLUMN differs from INPUT_COLUMN -- "
                    "engine does not support group-by column renaming"
                ),
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # Conditional: IGNORE_NULL engine gap
        has_ignore_null = any("ignore_null" in op for op in operations)
        if has_ignore_null:
            needs_review.append({
                "issue": (
                    "Engine ignores per-operation ignore_null flag -- "
                    "always uses pandas default skipna=True"
                ),
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 6. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="AggregateSortedRow",
            config=config,
            schema=schema,
        )

        logger.debug(
            "tAggregateSortedRow %s: groupbys=%d, operations=%d",
            node.component_id,
            len(groupbys),
            len(operations),
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
