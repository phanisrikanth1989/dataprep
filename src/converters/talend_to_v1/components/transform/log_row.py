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

        basic_mode = self._get_bool(node, "BASIC_MODE", False)

        config: Dict[str, Any] = {
            "basic_mode": basic_mode,
            "table_print": self._get_bool(node, "TABLE_PRINT", False),
            "vertical": self._get_bool(node, "VERTICAL", False),
            "print_header": self._get_bool(node, "PRINT_HEADER", False),
            "print_unique_name": self._get_bool(node, "PRINT_UNIQUE_NAME", False),
            "print_colnames": self._get_bool(node, "PRINT_COLNAMES", False) if basic_mode else False,
            "use_fixed_length": self._get_bool(node, "USE_FIXED_LENGTH", False) if basic_mode else False,
            "lengths": self._parse_lengths(node) if basic_mode else {},
        }

        schema_cols = self._parse_schema(node)

        component = self._build_component_dict(
            node=node,
            type_name="LogRow",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_lengths(node: TalendNode) -> Dict[str, int]:
        """Convert the flat LENGTHS table into a ``{column_name: length}`` map.

        The XML parser stores TABLE params as a flat list of
        ``{"elementRef": ..., "value": ...}`` dicts.  For LENGTHS the entries
        alternate between SCHEMA_COLUMN and LENGTH.  This helper pairs them up
        into a dict the engine can consume directly.
        """
        raw: list = node.params.get("LENGTHS", [])
        result: Dict[str, int] = {}
        col_name: str | None = None
        for entry in raw:
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                col_name = val
            elif ref == "LENGTH" and col_name is not None:
                try:
                    result[col_name] = int(val)
                except (ValueError, TypeError):
                    result[col_name] = 0
                col_name = None
        return result
