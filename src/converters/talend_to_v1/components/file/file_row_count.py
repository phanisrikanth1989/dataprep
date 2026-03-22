"""Converter for tFileRowCount -> FileRowCount component.

Fixes:
  CONV-FRC-001: DIE_ON_ERROR was not extracted by the old converter.
  CONV-FRC-002: Default encoding corrected to "UTF-8" (old code used bare UTF-8
                without quotes, which could mismatch Talend's quoted default).
  CONV-FRC-005: Null-safety — old code crashed when XML elements were missing
                because it called .get() on None. The new code uses safe helpers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileRowCount")
class FileRowCountConverter(ComponentConverter):
    """Convert a Talend tFileRowCount node into a v1 FileRowCount component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        filename = self._get_str(node, "FILENAME")
        row_separator = self._get_str(node, "ROWSEPARATOR", default="\\n")
        ignore_empty_row = self._get_bool(node, "IGNORE_EMPTY_ROW", default=False)
        encoding = self._get_str(node, "ENCODING", default="UTF-8")
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", default=False)

        if not filename:
            warnings.append(
                "FILENAME is empty — this is a required parameter"
            )

        config: Dict[str, Any] = {
            "filename": filename,
            "row_separator": row_separator,
            "ignore_empty_row": ignore_empty_row,
            "encoding": encoding,
            "die_on_error": die_on_error,
        }

        component = self._build_component_dict(
            node=node,
            type_name="FileRowCount",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
