"""Converter for Talend tAggregateRow component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# Talend function names -> normalised v1 function names.
# CONV-AGG-001: 'distinct' was previously unmapped; we normalise it to
# 'count_distinct' which is the canonical aggregate semantic.
_FUNCTION_MAP: Dict[str, str] = {
    "sum": "sum",
    "count": "count",
    "min": "min",
    "max": "max",
    "avg": "avg",
    "first": "first",
    "last": "last",
    "list": "list",
    "list_object": "list_object",
    "count_distinct": "count_distinct",
    "distinct": "count_distinct",       # CONV-AGG-001 fix
    "standard_deviation": "standard_deviation",
    "variance": "variance",
    "median": "median",
}


def _normalise_function(raw: str) -> str:
    """Return the canonical v1 function name for a Talend aggregate function.

    Unknown functions are passed through as-is so that downstream stages can
    detect them rather than silently dropping information.
    """
    return _FUNCTION_MAP.get(raw.lower(), raw)


@REGISTRY.register("tAggregateRow")
class AggregateRowConverter(ComponentConverter):
    """Convert a Talend tAggregateRow node into a v1 AggregateRow component.

    The GROUPBYS TABLE param contains INPUT_COLUMN elementValue entries that
    specify the columns to group by.

    The OPERATIONS TABLE param contains groups of four elementValue entries
    (OUTPUT_COLUMN, INPUT_COLUMN, FUNCTION, IGNORE_NULL) defining each
    aggregation operation.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Parse GROUPBYS table
        # ------------------------------------------------------------------
        group_by: List[str] = []
        raw_groupbys = self._get_param(node, "GROUPBYS", [])

        if isinstance(raw_groupbys, list):
            for entry in raw_groupbys:
                ref = entry.get("elementRef", "")
                val = entry.get("value", "").strip('"')
                if ref == "INPUT_COLUMN":
                    group_by.append(val)
        else:
            warnings.append(
                "GROUPBYS param is not a list -- expected TABLE structure"
            )

        # ------------------------------------------------------------------
        # Parse OPERATIONS table (groups of 4: OUTPUT_COLUMN, INPUT_COLUMN,
        # FUNCTION, IGNORE_NULL)
        # ------------------------------------------------------------------
        operations: List[Dict[str, Any]] = []
        raw_operations = self._get_param(node, "OPERATIONS", [])

        if isinstance(raw_operations, list):
            # Collect entries by elementRef rather than relying on a fragile
            # fixed stride of 4 (CONV-AGG-005).  We accumulate fields into
            # the current operation dict and flush whenever we see an
            # OUTPUT_COLUMN ref that starts a new group.
            current_op: Dict[str, Any] = {}
            for entry in raw_operations:
                ref = entry.get("elementRef", "")
                val = entry.get("value", "")

                if ref == "OUTPUT_COLUMN":
                    # Flush the previous operation (if any)
                    if current_op:
                        operations.append(current_op)
                    current_op = {"output_column": val.strip('"')}
                elif ref == "INPUT_COLUMN":
                    current_op["input_column"] = val.strip('"')
                elif ref == "FUNCTION":
                    raw_fn = val.strip('"')
                    current_op["function"] = _normalise_function(raw_fn)
                elif ref == "IGNORE_NULL":
                    current_op["ignore_null"] = val.lower() in ("true", "1")

            # Flush last operation
            if current_op:
                operations.append(current_op)

            if not operations and raw_operations:
                warnings.append(
                    "OPERATIONS table has entries but no valid operations "
                    "could be parsed"
                )
        else:
            warnings.append(
                "OPERATIONS param is not a list -- expected TABLE structure"
            )

        if not group_by and not operations:
            warnings.append(
                "No group_by or operations defined -- component has no "
                "aggregation logic"
            )

        # ------------------------------------------------------------------
        # Build config
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "group_by": group_by,
            "operations": operations,
        }

        logger.debug(
            "tAggregateRow %s: group_by=%s, operations=%d",
            node.component_id,
            group_by,
            len(operations),
        )

        # ------------------------------------------------------------------
        # Schema: input and output from FLOW metadata
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="AggregateRow",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)
