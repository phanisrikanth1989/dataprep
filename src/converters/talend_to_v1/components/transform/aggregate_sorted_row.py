"""Converter for Talend tAggregateSortedRow component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tAggregateSortedRow")
class AggregateSortedRowConverter(ComponentConverter):
    """Convert a Talend tAggregateSortedRow node into a v1 TAggregateSortedRow component.

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
        group_bys: List[str] = []
        raw_groupbys = self._get_param(node, "GROUPBYS", [])

        if isinstance(raw_groupbys, list):
            for entry in raw_groupbys:
                ref = entry.get("elementRef", "")
                val = entry.get("value", "").strip('"')
                if ref == "INPUT_COLUMN":
                    group_bys.append(val)
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
            # Collect entries in groups of 4
            i = 0
            while i < len(raw_operations):
                op: Dict[str, Any] = {}
                # Consume up to 4 entries for this operation
                consumed = 0
                for entry in raw_operations[i:i + 4]:
                    ref = entry.get("elementRef", "")
                    val = entry.get("value", "")
                    if ref == "OUTPUT_COLUMN":
                        op["output_column"] = val.strip('"')
                    elif ref == "INPUT_COLUMN":
                        op["input_column"] = val.strip('"')
                    elif ref == "FUNCTION":
                        op["function"] = val.strip('"')
                    elif ref == "IGNORE_NULL":
                        op["ignore_null"] = val.lower() in ("true", "1")
                    consumed += 1
                if op:
                    operations.append(op)
                i += max(consumed, 4)

            if not operations and raw_operations:
                warnings.append(
                    "OPERATIONS table has entries but no valid operations could be parsed"
                )
        else:
            warnings.append(
                "OPERATIONS param is not a list -- expected TABLE structure"
            )

        if not group_bys and not operations:
            warnings.append(
                "No group_bys or operations defined -- component has no aggregation logic"
            )

        # ------------------------------------------------------------------
        # Scalar parameters
        # ------------------------------------------------------------------
        row_count = self._get_str(node, "ROW_COUNT", default="")
        connection_format = self._get_str(node, "CONNECTION_FORMAT", default="")
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", default=False)

        config: Dict[str, Any] = {
            "group_bys": group_bys,
            "operations": operations,
            "die_on_error": die_on_error,
        }

        if row_count:
            config["row_count"] = row_count
        if connection_format:
            config["connection_format"] = connection_format

        logger.debug(
            "tAggregateSortedRow %s: group_bys=%s, operations=%d, die_on_error=%s",
            node.component_id,
            group_bys,
            len(operations),
            die_on_error,
        )

        # ------------------------------------------------------------------
        # Schema: transform -- input and output from FLOW metadata
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="TAggregateSortedRow",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)
