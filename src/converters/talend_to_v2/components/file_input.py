"""Converters for Talend file input components (non-delimited).

FileInputDelimitedConverter has been moved to
``src/converters/talend_to_v2/components/file/file_input_delimited_converter.py``
as part of the Phase 7 restructuring (COMP-05).

This module retains only FileInputFullRowConverter.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from .registry import REGISTRY
from ..type_mapping import convert_schema


def convert_path_expression(expr: str) -> str:
    """Convert a Talend path expression to V2 format.

    Handles:
    - ``context.var`` -> ``${context.var}``
    - ``context.dir + "file_" + context.date + ".csv"`` ->
      ``${context.dir}file_${context.date}.csv``
    """
    expr = expr.strip()

    # Simple case: bare context reference
    if re.fullmatch(r"context\.\w+", expr):
        return f"${{{expr}}}"

    # Concatenation: split on '+', resolve each segment
    if "+" in expr:
        parts = [p.strip() for p in expr.split("+")]
        result = []
        for part in parts:
            if re.fullmatch(r"context\.\w+", part):
                result.append(f"${{{part}}}")
            elif (len(part) >= 2 and part[0] == '"' and part[-1] == '"'):
                result.append(part[1:-1])
            else:
                result.append(part)
        return "".join(result)

    return expr


def _safe_int(value: str, default: int = 0) -> int:
    """Parse an integer from a string, returning *default* on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


@REGISTRY.register("tFileInputFullRow")
class FileInputFullRowConverter(ComponentConverter):
    """Converts tFileInputFullRow to V2 file_input_full_row."""

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        params = node.params
        config: Dict[str, Any] = {
            "path": convert_path_expression(params.get("FILENAME", "")),
        }

        if "HEADER" in params:
            config["header_rows"] = _safe_int(params["HEADER"])

        footer = _safe_int(params.get("FOOTER", "0"))
        if footer > 0:
            config["footer_rows"] = footer

        limit_raw = params.get("LIMIT", "")
        limit_val = _safe_int(limit_raw)
        if limit_val > 0:
            config["limit"] = limit_val

        if "ENCODING" in params:
            config["encoding"] = params["ENCODING"]

        flow_schema = node.schema.get("FLOW", [])
        if flow_schema:
            config["schema"] = convert_schema(flow_schema)

        return ComponentResult(
            component={
                "id": node.component_id,
                "type": "file_input_full_row",
                "config": config,
            },
            flows=self._build_simple_flows(node, connections),
        )
