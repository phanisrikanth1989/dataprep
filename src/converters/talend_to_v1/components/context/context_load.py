"""Converter for Talend tContextLoad component."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tContextLoad")
class ContextLoadConverter(ComponentConverter):
    """Convert a Talend tContextLoad node into a v1 ContextLoad component.

    Maps all Talend parameters including DIE_ON_ERROR and DISABLE_WARNINGS
    which were previously missing (fixes CONV-CL-002 and CONV-CL-003).
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        filepath = self._get_str(node, "CONTEXTFILE")
        fmt = self._get_str(node, "FORMAT", default="properties")
        delimiter = self._get_str(node, "FIELDSEPARATOR", default=";")
        csv_separator = self._get_str(node, "CSV_SEPARATOR", default=",")
        print_operations = self._get_bool(node, "PRINT_OPERATIONS")
        error_if_not_exists = self._get_bool(node, "ERROR_IF_NOT_EXISTS", default=True)
        die_on_error = self._get_bool(node, "DIE_ON_ERROR")
        disable_warnings = self._get_bool(node, "DISABLE_WARNINGS")

        config: Dict[str, Any] = {
            "filepath": filepath,
            "format": fmt,
            "delimiter": delimiter,
            "csv_separator": csv_separator,
            "print_operations": print_operations,
            "error_if_not_exists": error_if_not_exists,
            "die_on_error": die_on_error,
            "disable_warnings": disable_warnings,
        }

        if not filepath:
            warnings.append(
                "CONTEXTFILE is empty — context load requires a file path"
            )

        component = self._build_component_dict(
            node=node,
            type_name="ContextLoad",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
