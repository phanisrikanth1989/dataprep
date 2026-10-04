"""Converter for tJavaRow."""
from __future__ import annotations

from .base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from .registry import REGISTRY


@REGISTRY.register("tJavaRow")
class JavaRowConverter(ComponentConverter):
    """Converts tJavaRow to V2 python_row placeholder."""

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        code_param = node.params.get("CODE", "")

        return ComponentResult(
            component={
                "id": node.component_id,
                "type": "python_row",
                "config": {
                    "code": "# TODO: Manually rewrite from Java",
                    "_original_java_code": code_param,
                    "_needs_rewrite": True,
                },
            },
            flows=self._build_simple_flows(node, connections),
            warnings=[f"{node.component_id}: Java code requires manual rewrite to Python"],
            needs_review=[{
                "component": node.component_id,
                "reason": "Java code needs manual Python rewrite",
            }],
        )
