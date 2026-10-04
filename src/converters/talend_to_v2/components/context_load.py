"""Converter for tContextLoad."""
from __future__ import annotations

from typing import Any, Dict

from .base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from .registry import REGISTRY


@REGISTRY.register("tContextLoad")
class ContextLoadConverter(ComponentConverter):
    """Converts tContextLoad to V2 context_load."""

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        params = node.params
        config: Dict[str, Any] = {
            "path": params.get("CONTEXTFILE", ""),
        }

        # Format: "csv" -> "delimited", "properties" stays
        fmt = params.get("FORMAT", "")
        if fmt:
            config["format"] = "delimited" if fmt == "csv" else fmt

        # Delimiter depends on format
        if fmt == "csv":
            if "CSV_SEPARATOR" in params:
                config["delimiter"] = params["CSV_SEPARATOR"]
        else:
            if "FIELDSEPARATOR" in params:
                config["delimiter"] = params["FIELDSEPARATOR"]

        if "PRINT_OPERATIONS" in params:
            config["print_operations"] = params["PRINT_OPERATIONS"]

        if "ERROR_IF_NOT_EXISTS" in params:
            config["die_on_error"] = params["ERROR_IF_NOT_EXISTS"]

        return ComponentResult(
            component={
                "id": node.component_id,
                "type": "context_load",
                "config": config,
            },
            flows=self._build_simple_flows(node, connections),
        )
