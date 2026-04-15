"""Converter for Talend tAggregateRow component.

Groups input rows by specified columns and applies aggregate functions
(count, min, max, avg, sum, first, last, list, list_object, distinct, std_dev, union).

Config mapping (8 params total):
  GROUPBYS               -> groupbys (TABLE stride-2: OUTPUT_COLUMN, INPUT_COLUMN)
  OPERATIONS             -> operations (list[dict], default [])
  LIST_DELIMITER         -> list_delimiter (str, default ",")
  USE_FINANCIAL_PRECISION -> use_financial_precision (bool, default True)
  CHECK_TYPE_OVERFLOW    -> check_type_overflow (bool, default False)
  CHECK_ULP              -> check_ulp (bool, default False)
  TSTATCATCHER_STATS     -> tstatcatcher_stats (bool, default False)
  LABEL                  -> label (str, default "")
"""
import logging
from typing import Any, Dict, List, Optional

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# GROUPBYS TABLE constants
# ------------------------------------------------------------------
_GROUPBYS_FIELDS = ("OUTPUT_COLUMN", "INPUT_COLUMN")
_GROUPBYS_STRIDE = len(_GROUPBYS_FIELDS)

# ------------------------------------------------------------------
# OPERATIONS TABLE constants
# ------------------------------------------------------------------
_OPERATIONS_FIELDS = ("OUTPUT_COLUMN", "FUNCTION", "INPUT_COLUMN", "IGNORE_NULL")
_OPERATIONS_GROUP_SIZE = len(_OPERATIONS_FIELDS)

# ------------------------------------------------------------------
# Function mapping: Talend function names -> normalised v1 names
# ------------------------------------------------------------------
# All 12 _java.xml CLOSED_LIST functions plus common aliases.
# Unknown functions pass through as-is (lowercased) so downstream can detect them.
_FUNCTION_MAP: Dict[str, str] = {
    "count": "count",
    "min": "min",
    "max": "max",
    "avg": "avg",
    "sum": "sum",
    "first": "first",
    "last": "last",
    "list": "list",
    "list_object": "list_object",       # preserved -- engine implements as delimited string
    "distinct": "count_distinct",       # CONV-AGG-001: Talend distinct = count distinct
    "count_distinct": "count_distinct",
    "std_dev": "std",                   # CONV-AGG-002: Talend XML name -> engine std
    "standard_deviation": "std",        # alias -> engine std
    "population_std_dev": "population_std_dev",  # preserved -- engine handles ddof=0
    "union": "union",                   # passthrough -- no engine support
    "variance": "variance",
    "median": "median",
}


def _normalise_function(raw: str, warnings: Optional[List[str]] = None) -> str:
    """Return the canonical v1 function name for a Talend aggregate function.

    Unknown functions pass through lowercased so downstream stages can detect them.
    When *warnings* is provided, lossy-mapping alerts are appended.
    """
    lowered = raw.lower()
    result = _FUNCTION_MAP.get(lowered, lowered)

    if warnings is not None:
        if lowered == "list_object":
            pass  # no warning needed -- engine implements list_object as delimited string
        elif lowered == "population_std_dev":
            pass  # no warning needed -- engine handles population_std_dev directly
        elif lowered == "union":
            warnings.append(
                "function 'union' has no engine equivalent -- "
                "geometry/set union is not supported, will fall back to sum"
            )

    return result


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
    """Parse OPERATIONS TABLE into list of operation dicts.

    Uses a state-machine parser that flushes on OUTPUT_COLUMN ref.
    Each operation dict contains:
      output_column (str), function (str), input_column (str), ignore_null (bool)

    The state-machine approach handles edge cases (missing fields,
    extra unknown refs, non-stride-4 layouts) better than simple stride-based.

    Returns:
        List of operation dicts.
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
            # Flush the previous operation (if any)
            if current_op:
                _validate_and_append_op(current_op, operations, warnings)
            current_op = {"output_column": val.strip('"')}
        elif ref == "FUNCTION":
            raw_fn = val.strip('"')
            current_op["function"] = _normalise_function(raw_fn, warnings)
        elif ref == "INPUT_COLUMN":
            current_op["input_column"] = val.strip('"')
        elif ref == "IGNORE_NULL":
            current_op["ignore_null"] = val.lower() in ("true", "1")

    # Flush last operation
    if current_op:
        _validate_and_append_op(current_op, operations, warnings)

    if not operations and raw:
        warnings.append(
            "OPERATIONS table has entries but no valid operations "
            "could be parsed"
        )

    return operations


def _validate_and_append_op(
    op: Dict[str, Any],
    operations: List[Dict[str, Any]],
    warnings: List[str],
) -> None:
    """Validate a parsed operation and append to the operations list.

    Emits a warning if the operation is missing required fields
    (FUNCTION or INPUT_COLUMN).
    """
    missing = []
    if "output_column" not in op:
        missing.append("OUTPUT_COLUMN")
    if "function" not in op:
        missing.append("FUNCTION")
    if "input_column" not in op:
        missing.append("INPUT_COLUMN")

    if missing:
        out_col = op.get("output_column", "<unknown>")
        warnings.append(
            f"Operation '{out_col}' is missing {', '.join(missing)} "
            "-- may produce incorrect results"
        )

    operations.append(op)


# ------------------------------------------------------------------
# Converter class
# ------------------------------------------------------------------

@REGISTRY.register("tAggregateRow")
class AggregateRowConverter(ComponentConverter):
    """Convert Talend tAggregateRow to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. TABLE parameters ----
        raw_groupbys = self._get_param(node, "GROUPBYS", [])
        if isinstance(raw_groupbys, list):
            groupbys = _parse_groupbys(raw_groupbys)
        else:
            warnings.append("GROUPBYS param is not a list -- expected TABLE structure")
            groupbys = []

        raw_operations = self._get_param(node, "OPERATIONS", [])
        if isinstance(raw_operations, list):
            operations = _parse_operations(raw_operations, warnings)
        else:
            warnings.append("OPERATIONS param is not a list -- expected TABLE structure")
            operations = []

        if not groupbys and not operations:
            warnings.append(
                "No groupbys or operations defined -- component has no "
                "aggregation logic"
            )

        # ---- 2. Advanced parameters ----
        list_delimiter = self._get_str(node, "LIST_DELIMITER", default=",")
        use_financial_precision = self._get_bool(node, "USE_FINANCIAL_PRECISION", default=True)
        check_type_overflow = self._get_bool(node, "CHECK_TYPE_OVERFLOW", default=False)
        check_ulp = self._get_bool(node, "CHECK_ULP", default=False)

        # ---- 3. Inject list_delimiter into list-function operations ----
        for op in operations:
            if op.get("function") == "list":
                op["delimiter"] = list_delimiter

        # ---- 4. Framework parameters (ALWAYS LAST) ----
        tstatcatcher_stats = self._get_bool(node, "TSTATCATCHER_STATS", default=False)
        label = self._get_str(node, "LABEL")

        # ---- 5. Build config ----
        config: Dict[str, Any] = {
            "groupbys": groupbys,
            "operations": operations,
            "list_delimiter": list_delimiter,
            "use_financial_precision": use_financial_precision,
            "check_type_overflow": check_type_overflow,
            "check_ulp": check_ulp,
            "tstatcatcher_stats": tstatcatcher_stats,
            "label": label,
        }

        logger.debug(
            "tAggregateRow %s: groupbys=%s, operations=%d",
            node.component_id,
            groupbys,
            len(operations),
        )

        # ---- 6. Schema ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 7. Engine gap needs_review entries (per-feature, conditional) ----
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

        has_ignore_null = any("ignore_null" in op for op in operations)
        if has_ignore_null:
            needs_review.append({
                "issue": (
                    "Engine ignores per-operation ignore_null flag entirely "
                    "-- always uses pandas default skipna=True (ENG-AGG-002). "
                    "When ignore_null=false, engine incorrectly skips nulls."
                ),
                "component": node.component_id,
                "severity": "engine_gap",
            })

        if check_type_overflow:
            needs_review.append({
                "issue": (
                    "CHECK_TYPE_OVERFLOW is enabled but engine does not "
                    "implement overflow checking"
                ),
                "component": node.component_id,
                "severity": "engine_gap",
            })

        if check_ulp:
            needs_review.append({
                "issue": (
                    "CHECK_ULP is enabled but engine does not implement "
                    "ULP (unit in the last place) verification"
                ),
                "component": node.component_id,
                "severity": "engine_gap",
            })

        has_list_function = any(op.get("function") == "list" for op in operations)
        if has_list_function:
            needs_review.append({
                "issue": (
                    "Talend 'list' function produces a delimited string "
                    "(e.g. 'a,b,c') but engine 'list' returns a Python "
                    "list object. Delimiter injected per-op but engine "
                    "may use concat path instead."
                ),
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 8. Return ----
        component = self._build_component_dict(
            node=node,
            type_name="AggregateRow",
            config=config,
            schema=schema,
        )
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
