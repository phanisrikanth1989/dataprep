"""Converter for tFileList -> FileList component."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileList")
class FileListConverter(ComponentConverter):
    """Converts a Talend tFileList node into a v1 FileList component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        directory = self._get_str(node, "DIRECTORY")
        if not directory:
            warnings.append(
                "DIRECTORY is empty; the file-list component requires a directory path."
            )

        # Parse FILES table — list of {elementRef: "FILEMASK", value: "*.csv"} entries
        files_raw = node.params.get("FILES", [])
        files: List[Dict[str, str]] = []
        if isinstance(files_raw, list):
            for entry in files_raw:
                if isinstance(entry, dict):
                    # Case-insensitive lookup for FILEMASK key
                    mask = (
                        entry.get("FILEMASK")
                        or entry.get("filemask")
                        or entry.get("value", "*")
                    )
                    # Strip quotes — cannot use _get_str here as it reads from node.params
                    if isinstance(mask, str) and mask.startswith('"') and mask.endswith('"') and len(mask) >= 2:
                        mask = mask[1:-1]
                    files.append({"filemask": mask})
                else:
                    files.append({"filemask": str(entry)})

        config: Dict[str, Any] = {
            "directory": directory,
            "list_mode": self._get_str(node, "LIST_MODE", "FILES"),
            "include_subdirs": self._get_bool(node, "INCLUDESUBDIR"),
            "case_sensitive": self._get_str(node, "CASE_SENSITIVE", "YES"),
            "error": self._get_bool(node, "ERROR", default=True),
            "glob_expressions": self._get_bool(node, "GLOBEXPRESSIONS", default=True),
            "files": files,
            "order_by_nothing": self._get_bool(node, "ORDER_BY_NOTHING"),
            "order_by_filename": self._get_bool(node, "ORDER_BY_FILENAME"),
            "order_by_filesize": self._get_bool(node, "ORDER_BY_FILESIZE"),
            "order_by_modifieddate": self._get_bool(node, "ORDER_BY_MODIFIEDDATE"),
            "order_action_asc": self._get_bool(node, "ORDER_ACTION_ASC", default=True),
            "order_action_desc": self._get_bool(node, "ORDER_ACTION_DESC"),
            "exclude_file": self._get_bool(node, "IFEXCLUDE"),
            "exclude_filemask": self._get_str(node, "EXCLUDEFILEMASK"),
        }

        component = self._build_component_dict(
            node=node,
            type_name="FileList",
            config=config,
            # Iterate-style component — no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
