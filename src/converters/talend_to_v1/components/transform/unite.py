"""Converter for Talend tUnite component.

Fixes an indentation bug in the old complex_converter implementation where
the ``if name == 'REMOVE_DUPLICATES'`` check was outside the for-loop,
so only the *last* parameter's name/value was ever inspected.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tUnite")
class UniteConverter(ComponentConverter):
    """Convert a Talend tUnite node into a v1 Unite component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        remove_duplicates = self._get_bool(node, "REMOVE_DUPLICATES", default=False)
        mode = self._get_str(node, "MODE", default="UNION")

        config: Dict[str, Any] = {
            "remove_duplicates": remove_duplicates,
            "mode": mode,
        }

        schema_cols = self._parse_schema(node)
        component = self._build_component_dict(
            node=node,
            type_name="Unite",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )
        return ComponentResult(component=component, warnings=warnings)
