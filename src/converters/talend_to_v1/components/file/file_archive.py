"""Converter for Talend tFileArchive -> v1 FileArchive component.

Maps tFileArchive parameters to a v1 FileArchive config:
  SOURCE        -> source
  TARGET        -> target
  ARCHIVE_FORMAT -> archive_format  (default "zip")
  SUB_DIRECTORY -> include_subdirectories (bool)
  OVERWRITE     -> overwrite (bool)
  LEVEL         -> compression_level (int, default 4)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileArchive")
class FileArchiveConverter(ComponentConverter):
    """Convert a Talend tFileArchive node into a v1 FileArchive component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters ---
        source = self._get_str(node, "SOURCE")
        target = self._get_str(node, "TARGET")
        archive_format = self._get_str(node, "ARCHIVE_FORMAT", default="zip")
        include_subdirectories = self._get_bool(node, "SUB_DIRECTORY")
        overwrite = self._get_bool(node, "OVERWRITE")
        compression_level = self._get_int(node, "LEVEL", 4)
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", True)

        # --- Validation warnings ---
        if not source:
            warnings.append("SOURCE is empty — this is a required parameter")
        if not target:
            warnings.append("TARGET is empty — this is a required parameter")

        # --- Build config dict ---
        config: Dict[str, Any] = {
            "source": source,
            "target": target,
            "archive_format": archive_format,
            "include_subdirectories": include_subdirectories,
            "overwrite": overwrite,
            "compression_level": compression_level,
            "die_on_error": die_on_error,
        }

        component = self._build_component_dict(
            node=node,
            type_name="FileArchiveComponent",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
