"""Converter for tFileExist -> FileExistComponent.

tFileExist is a Talend utility component that checks whether a file exists.
It is a trigger/utility component with no data flow (FLOW MAX_INPUT=0, MAX_OUTPUT=0).

Key parameters:
* ``FILE_NAME`` -- path to the file to check (FILE type, required).

CRITICAL: The v1 engine reads ``self.config.get('file_path')`` or
``self.config.get('FILE_NAME')`` -- the config key MUST be ``file_path``,
NOT ``filename``.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileExist")
class FileExistConverter(ComponentConverter):
    """Converts a Talend tFileExist node into a v1 FileExistComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Config
        # ------------------------------------------------------------------
        file_path = self._get_str(node, "FILE_NAME")

        config: Dict[str, Any] = {
            # CRITICAL: key is "file_path" -- engine reads file_path or FILE_NAME
            "file_path": file_path,
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        # ------------------------------------------------------------------
        # Warnings
        # ------------------------------------------------------------------
        if not file_path:
            warnings.append(
                "FILE_NAME is empty; the file-exist check may fail at runtime."
            )

        # Engine-gap warning: EXISTS globalMap variable not set (ENG-FE-001)
        warnings.append(
            f"Engine does not set {node.component_id}_EXISTS globalMap variable "
            f"-- downstream RunIf conditions checking EXISTS will not work"
        )

        # ------------------------------------------------------------------
        # Build component
        # ------------------------------------------------------------------
        component = self._build_component_dict(
            node=node,
            type_name="FileExistComponent",
            config=config,
            # Utility component -- no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
