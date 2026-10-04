"""Converter for tAggregateRow."""
from __future__ import annotations

from typing import Any, Dict, List

from .base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from .registry import REGISTRY
from .utils import _parse_table_rows


@REGISTRY.register("tAggregateRow")
class AggregateRowConverter(ComponentConverter):
    """Converts tAggregateRow to V2 aggregate."""

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        params = node.params

        # Group-by columns
        raw_groupbys = params.get("GROUPBYS", [])
        group_by = [entry["value"] for entry in raw_groupbys if entry.get("elementRef") == "OUTPUT_COLUMN"]

        # Operations
        raw_ops = params.get("OPERATIONS", [])
        parsed_ops = _parse_table_rows(raw_ops)

        operations: List[Dict[str, Any]] = []
        for row in parsed_ops:
            ignore_null_val = row.get("IGNORE_NULL", False)
            # Handle both string "true"/"false" and bool
            if isinstance(ignore_null_val, str):
                ignore_null_val = ignore_null_val.lower() == "true"
            operations.append({
                "name": row.get("OUTPUT_COLUMN", ""),
                "function": row.get("FUNCTION", ""),
                "column": row.get("INPUT_COLUMN", ""),
                "ignore_nulls": ignore_null_val,
            })

        return ComponentResult(
            component={
                "id": node.component_id,
                "type": "aggregate",
                "config": {
                    "group_by": group_by,
                    "operations": operations,
                },
            },
            flows=self._build_simple_flows(node, connections),
        )
