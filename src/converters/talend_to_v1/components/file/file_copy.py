"""Converter for Talend tFileCopy -> v1 FileCopy component.

Fixes:
  CONV-FC-001: parse_tfilecopy method did not exist in old converter
  CONV-FC-002: component crashed at conversion with AttributeError
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileCopy")
class FileCopyConverter(ComponentConverter):
    """Convert a Talend tFileCopy node into a v1 FileCopy component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters ---
        source = self._get_str(node, "FILENAME")
        destination = self._get_str(node, "DESTINATION")
        rename = self._get_bool(node, "RENAME")
        new_name = self._get_str(node, "DESTINATION_RENAME")
        replace_file = self._get_bool(node, "REPLACE_FILE", False)
        create_directory = self._get_bool(node, "CREATE_DIRECTORY", False)
        preserve_last_modified = self._get_bool(node, "PRESERVE_LAST_MODIFIED_TIME")
        remove_source_file = self._get_bool(node, "REMOVE_SOURCE_FILE")
        copy_directory = self._get_bool(node, "COPY_DIRECTORY")
        source_directory = self._get_str(node, "SOURCE_DIRECTORY")

        # --- Validation warnings ---
        if not source:
            warnings.append("FILENAME (source) is empty")
        if not destination:
            warnings.append("DESTINATION is empty")
        if rename and not new_name:
            warnings.append("RENAME is true but DESTINATION_RENAME is empty")

        # --- Engine-gap warnings ---
        if remove_source_file:
            warnings.append(
                "REMOVE_SOURCE_FILE=true: engine uses shutil.copy2 not "
                "os.rename — not atomic move semantics"
            )
        if copy_directory:
            warnings.append(
                "COPY_DIRECTORY=true: engine has partial directory copy "
                "support via shutil.copytree"
            )

        # --- Build config dict ---
        config: Dict[str, Any] = {
            "source": source,
            "destination": destination,
            "rename": rename,
            "new_name": new_name,
            "replace_file": replace_file,
            "create_directory": create_directory,
            "preserve_last_modified": preserve_last_modified,
            "remove_source_file": remove_source_file,
            "copy_directory": copy_directory,
            "source_directory": source_directory,
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        component = self._build_component_dict(
            node=node,
            type_name="FileCopy",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
