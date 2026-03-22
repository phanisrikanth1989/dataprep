"""Converter for tFileExist → FileExistComponent."""
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
        filename = self._get_str(node, "FILE_NAME")

        config: Dict[str, Any] = {
            "filename": filename,
        }

        warnings: List[str] = []
        if not filename:
            warnings.append("FILE_NAME is empty; the file-exist check may fail at runtime.")

        component = self._build_component_dict(
            node=node,
            type_name="FileExistComponent",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(
            component=component,
            warnings=warnings,
        )
