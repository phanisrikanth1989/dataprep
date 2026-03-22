"""Converter for Talend tPivotToColumnsDelimited component.

tPivotToColumnsDelimited pivots rows into columns and writes the result to a
delimited file.  It groups rows by one or more group-by columns, pivots on a
named column, and aggregates values from another column using a specified
function (e.g. sum, count, avg).

The GROUPBYS TABLE parameter contains flat {elementRef, value} entries whose
values identify the group-by columns.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tPivotToColumnsDelimited")
class PivotToColumnsDelimitedConverter(ComponentConverter):
    """Convert a Talend tPivotToColumnsDelimited node into a v1
    PivotToColumnsDelimited component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Scalar parameters
        # ------------------------------------------------------------------
        pivot_column = self._get_str(node, "PIVOT_COLUMN")
        aggregation_column = self._get_str(node, "AGGREGATION_COLUMN")
        aggregation_function = self._get_str(
            node, "AGGREGATION_FUNCTION", default="sum",
        )
        filename = self._get_str(node, "FILENAME")
        row_separator = self._get_str(node, "ROWSEPARATOR", default="\\n")
        field_separator = self._get_str(node, "FIELDSEPARATOR", default=";")
        encoding = self._get_str(node, "ENCODING", default="UTF-8")
        create = self._get_bool(node, "CREATE", default=True)

        # ------------------------------------------------------------------
        # GROUPBYS table parameter — list of {elementRef, value} entries
        # ------------------------------------------------------------------
        group_by_columns = self._parse_group_bys(node, warnings)

        # ------------------------------------------------------------------
        # Validation warnings
        # ------------------------------------------------------------------
        if not pivot_column:
            warnings.append(
                "PIVOT_COLUMN is empty — pivot operation has no pivot column"
            )
        if not aggregation_column:
            warnings.append(
                "AGGREGATION_COLUMN is empty — pivot has no aggregation target"
            )
        if not filename:
            warnings.append(
                "FILENAME is empty — output file path is not defined"
            )

        # ------------------------------------------------------------------
        # Build config
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "pivot_column": pivot_column,
            "aggregation_column": aggregation_column,
            "aggregation_function": aggregation_function,
            "group_by_columns": group_by_columns,
            "filename": filename,
            "row_separator": row_separator,
            "field_separator": field_separator,
            "encoding": encoding,
            "create": create,
        }

        # ------------------------------------------------------------------
        # Schema: transform — input and output are the same parsed schema
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="PivotToColumnsDelimited",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)

    # ------------------------------------------------------------------
    # GROUPBYS table parser
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_group_bys(
        node: TalendNode,
        warnings: List[str],
    ) -> List[str]:
        """Parse the GROUPBYS table parameter.

        The table is stored as a list of dicts, each with a ``value`` key
        that holds a quoted column name.
        """
        raw = node.params.get("GROUPBYS", [])
        if not isinstance(raw, list):
            warnings.append(
                "GROUPBYS param is not a list — expected TABLE structure"
            )
            return []

        result: List[str] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            val = entry.get("value", "").strip('"')
            if val:
                result.append(val)

        return result
