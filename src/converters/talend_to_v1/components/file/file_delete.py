"""Converter for Talend tFileDelete component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileDelete")
class FileDeleteConverter(ComponentConverter):
    """Convert a Talend tFileDelete node into a v1 FileDelete component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "filename": self._get_str(node, "FILENAME"),
            "fail_on_error": self._get_bool(node, "FAILON", False),
            # Deletion mode
            "folder": self._get_bool(node, "FOLDER", False),
            "folder_file": self._get_bool(node, "FOLDER_FILE", False),
            "directory": self._get_str(node, "DIRECTORY"),
            "folder_file_path": self._get_str(node, "FOLDER_FILE_PATH"),
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        if not config["filename"] and not config["directory"] and not config["folder_file_path"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        # Engine-gap warnings
        if config["folder"]:
            warnings.append(
                "FOLDER=true: engine FileDelete does not distinguish "
                "file vs directory deletion modes"
            )
        if config["folder_file"]:
            warnings.append(
                "FOLDER_FILE=true: engine FileDelete does not have "
                "auto-detect file/folder mode"
            )

        component = self._build_component_dict(
            node=node,
            type_name="FileDelete",
            config=config,
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
