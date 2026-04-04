"""Converter for Talend tFileCopy component.

Copies files from source to destination with options for renaming,
directory copy, and move (remove source) semantics.

Config mapping (12 unique params + framework):
  FILENAME                    -> filename                    (str, default "")
  ENABLE_COPY_DIRECTORY       -> enable_copy_directory       (bool, default False)
  SOURCE_DERECTORY            -> source_derectory            (str, default "")  # Talend typo preserved
  DESTINATION                 -> destination                 (str, default "")
  RENAME                      -> rename                      (bool, default False)
  DESTINATION_RENAME          -> destination_rename          (str, default "NewName.temp")
  REMOVE_FILE                 -> remove_file                 (bool, default False)
  REPLACE_FILE                -> replace_file                (bool, default True)
  CREATE_DIRECTORY            -> create_directory            (bool, default True)
  FAILON                      -> failon                      (bool, default False)
  FORCE_COPY_DELETE           -> force_copy_delete           (bool, default False)
  PRESERVE_LAST_MODIFIED_TIME -> preserve_last_modified_time (bool, default False)
  --- framework ---
  TSTATCATCHER_STATS          -> tstatcatcher_stats          (bool, default False)
  LABEL                       -> label                       (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileCopy")
class FileCopyConverter(ComponentConverter):
    """Convert Talend tFileCopy to v1 engine config."""

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
        config["enable_copy_directory"] = self._get_bool(node, "ENABLE_COPY_DIRECTORY", False)
        config["source_derectory"] = self._get_str(node, "SOURCE_DERECTORY", "")  # Talend typo preserved
        config["destination"] = self._get_str(node, "DESTINATION", "")
        config["rename"] = self._get_bool(node, "RENAME", False)
        config["destination_rename"] = self._get_str(node, "DESTINATION_RENAME", "NewName.temp")
        config["remove_file"] = self._get_bool(node, "REMOVE_FILE", False)
        config["replace_file"] = self._get_bool(node, "REPLACE_FILE", True)
        config["create_directory"] = self._get_bool(node, "CREATE_DIRECTORY", True)
        config["failon"] = self._get_bool(node, "FAILON", False)
        config["force_copy_delete"] = self._get_bool(node, "FORCE_COPY_DELETE", False)
        config["preserve_last_modified_time"] = self._get_bool(node, "PRESERVE_LAST_MODIFIED_TIME", False)

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema ----
        # Utility component -- no data flow schema
        schema = {"input": [], "output": []}

        # ---- 7. Engine gap needs_review entries ----
        # Engine reads 'source' but converter outputs 'filename' per _java.xml FILENAME
        needs_review.append({
            "issue": "Engine reads 'source' but converter outputs 'filename' per _java.xml param name FILENAME",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine reads 'new_name' but converter outputs 'destination_rename' per _java.xml DESTINATION_RENAME
        needs_review.append({
            "issue": "Engine reads 'new_name' but converter outputs 'destination_rename' per _java.xml param name DESTINATION_RENAME",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine reads 'preserve_last_modified' but converter outputs 'preserve_last_modified_time' per _java.xml
        needs_review.append({
            "issue": "Engine reads 'preserve_last_modified' but converter outputs 'preserve_last_modified_time' per _java.xml param name PRESERVE_LAST_MODIFIED_TIME",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read 'enable_copy_directory' -- not implemented in engine
        needs_review.append({
            "issue": "Engine does not read 'enable_copy_directory' -- not implemented in engine",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read 'source_derectory' -- not implemented in engine
        needs_review.append({
            "issue": "Engine does not read 'source_derectory' -- not implemented in engine",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read 'remove_file' -- not implemented in engine
        needs_review.append({
            "issue": "Engine does not read 'remove_file' -- not implemented in engine",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read 'failon' -- not implemented in engine
        needs_review.append({
            "issue": "Engine does not read 'failon' -- not implemented in engine",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read 'force_copy_delete' -- not implemented in engine
        needs_review.append({
            "issue": "Engine does not read 'force_copy_delete' -- not implemented in engine",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileCopy",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
