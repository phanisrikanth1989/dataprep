"""Converter for Talend tLogRow component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tLogRow")
class LogRowConverter(ComponentConverter):
    """Convert a Talend tLogRow node into a v1 LogRow component.

    tLogRow is a simple passthrough component that logs data flowing through
    the pipeline.  It supports several display modes (basic, table, vertical)
    and optional header / unique-name printing.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "basic_mode": self._get_bool(node, "BASIC_MODE", False),
            "table_print": self._get_bool(node, "TABLE_PRINT", False),
            "vertical": self._get_bool(node, "VERTICAL", False),
            "print_header": self._get_bool(node, "PRINT_HEADER", False),
            "print_unique_name": self._get_bool(node, "PRINT_UNIQUE_NAME", False),
        }

        schema_cols = self._parse_schema(node)

        component = self._build_component_dict(
            node=node,
            type_name="LogRow",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
