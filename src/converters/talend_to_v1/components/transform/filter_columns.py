"""Converter for Talend tFilterColumns -> v1 FilterColumns component.

tFilterColumns selects a subset of columns from the input flow.  The list of
columns to keep is determined by the output FLOW schema (metadata connector
"FLOW"), *not* by elementParameter entries.  The old converter extracted column
names from that same metadata section (see complex_converter lines 786-796).

Fixes vs. old code:
  - The _map_component_parameters fallback (lines 199-205) incorrectly tried
    to read COLUMNS / MODE / KEEP_ROW_ORDER from elementParameters; those
    params do not exist for tFilterColumns.  The dedicated parser at 786-796
    correctly reads from the FLOW schema.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFilterColumns")
class FilterColumnsConverter(ComponentConverter):
    """Convert a Talend tFilterColumns node into a v1 FilterColumns component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract column names from the FLOW schema ---
        # tFilterColumns defines which columns to keep via its output schema,
        # not via elementParameter entries.
        output_schema = self._parse_schema(node, connector="FLOW")
        columns = [col["name"] for col in output_schema]

        if not columns:
            warnings.append("No columns found in FLOW schema; output will be empty")

        # --- Build config dict ---
        config: Dict[str, Any] = {
            "columns": columns,
        }

        component = self._build_component_dict(
            node=node,
            type_name="FilterColumns",
            config=config,
            schema={
                "input": [],
                "output": output_schema,
            },
        )

        return ComponentResult(component=component, warnings=warnings)
