"""Converter for Talend tFileDelete component.

Deletes files or directories from the filesystem. Supports three modes:
file-only (default), directory-only (FOLDER), and auto-detect (FOLDER_FILE).

Config mapping (6 params + framework):
  FILENAME    -> filename    (str, default "")
  DIRECTORY   -> directory   (str, default "")
  PATH        -> path        (str, default "")  -- FOLDER_FILE mode path
  FAILON      -> failon      (bool, default True)  -- _java.xml says true
  FOLDER      -> folder      (bool, default False)
  FOLDER_FILE -> folder_file (bool, default False)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileDelete")
class FileDeleteConverter(ComponentConverter):
    """Convert Talend tFileDelete to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["filename"] = self._get_str(node, "FILENAME", "")
        config["directory"] = self._get_str(node, "DIRECTORY", "")
        config["path"] = self._get_str(node, "PATH", "")
        config["failon"] = self._get_bool(node, "FAILON", True)
        config["folder"] = self._get_bool(node, "FOLDER", False)
        config["folder_file"] = self._get_bool(node, "FOLDER_FILE", False)

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema ----
        # Utility component -- no data flow schema
        schema = {"input": [], "output": []}

        # ---- 7. Engine gap needs_review entries ----
        # Engine reads different config keys than _java.xml param names
        _engine_gap_keys = [
            ("failon", "Engine reads 'fail_on_error' (default True) but converter outputs 'failon' per _java.xml param FAILON"),
            ("folder", "Engine reads 'is_directory' but converter outputs 'folder' per _java.xml param FOLDER"),
            ("folder_file", "Engine reads 'is_folder_file' but converter outputs 'folder_file' per _java.xml param FOLDER_FILE"),
            ("filename", "Engine reads 'path' for all modes but converter outputs 'filename'/'directory'/'path' per _java.xml"),
            ("recursive", "Engine reads 'recursive' config key but no RECURSIVE param exists in _java.xml"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine config key mismatch for '{key}' -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileDelete",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
