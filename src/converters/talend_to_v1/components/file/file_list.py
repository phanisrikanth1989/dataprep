"""Converter for Talend tFileList component.

Lists files/directories matching filter criteria. Iterate-style component
with no data flow schema -- drives downstream via ITERATE connector.

Config mapping (17 params total):
  DIRECTORY              -> directory              (str, default "")
  LIST_MODE              -> list_mode              (str/CLOSED_LIST, default "FILES")
  INCLUDSUBDIR           -> include_subdirs        (bool, default False) -- NOTE: _java.xml spelling has no E
  CASE_SENSITIVE         -> case_sensitive         (str/CLOSED_LIST, default "YES")
  ERROR                  -> error                  (bool, default False)
  GLOBEXPRESSIONS        -> glob_expressions       (bool, default True)
  FILES                  -> files                  (TABLE, stride-1 FILEMASK elementRef)
  ORDER_BY_NOTHING       -> order_by_nothing       (bool/RADIO, default True)
  ORDER_BY_FILENAME      -> order_by_filename      (bool/RADIO, default False)
  ORDER_BY_FILESIZE      -> order_by_filesize      (bool/RADIO, default False)
  ORDER_BY_MODIFIEDDATE  -> order_by_modifieddate  (bool/RADIO, default False)
  ORDER_ACTION_ASC       -> order_action_asc       (bool/RADIO, default True)
  ORDER_ACTION_DESC      -> order_action_desc      (bool/RADIO, default False)
  IFEXCLUDE              -> exclude_file           (bool, default False)
  EXCLUDEFILEMASK        -> exclude_filemask       (str, default "*.txt")
  FORMAT_FILEPATH_TO_SLASH -> format_filepath_to_slash (bool, default False)
  --- framework ---
  TSTATCATCHER_STATS     -> tstatcatcher_stats     (bool, default False)
  LABEL                  -> label                  (str, default "")
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_FILES_FIELDS = ("FILEMASK",)
_FILES_GROUP_SIZE = 1


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_files(raw: Any) -> List[Dict[str, str]]:
    """Parse FILES TABLE into list of dicts.

    Each elementRef entry maps to one row:
      FILEMASK -> filemask (str, strip quotes)

    Non-dict entries are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")
        if ref == "FILEMASK":
            result.append({"filemask": val.strip('"')})
    return result


@REGISTRY.register("tFileList")
class FileListConverter(ComponentConverter):
    """Convert Talend tFileList to v1 engine config."""

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
        config["directory"] = self._get_str(node, "DIRECTORY")
        config["list_mode"] = self._get_str(node, "LIST_MODE", "FILES")
        # NOTE: _java.xml spelling is INCLUDSUBDIR (no E)
        config["include_subdirs"] = self._get_bool(node, "INCLUDSUBDIR")
        config["case_sensitive"] = self._get_str(node, "CASE_SENSITIVE", "YES")
        config["error"] = self._get_bool(node, "ERROR")
        config["glob_expressions"] = self._get_bool(node, "GLOBEXPRESSIONS", default=True)

        # ---- 2. TABLE parameters ----
        config["files"] = _parse_files(node.params.get("FILES", []))

        # ---- 3. RADIO parameters (ORDER_BY group) ----
        config["order_by_nothing"] = self._get_bool(node, "ORDER_BY_NOTHING", default=True)
        config["order_by_filename"] = self._get_bool(node, "ORDER_BY_FILENAME")
        config["order_by_filesize"] = self._get_bool(node, "ORDER_BY_FILESIZE")
        config["order_by_modifieddate"] = self._get_bool(node, "ORDER_BY_MODIFIEDDATE")

        # ---- 4. RADIO parameters (ORDER_ACTION group) ----
        config["order_action_asc"] = self._get_bool(node, "ORDER_ACTION_ASC", default=True)
        config["order_action_desc"] = self._get_bool(node, "ORDER_ACTION_DESC")

        # ---- 5. Exclusion parameters ----
        config["exclude_file"] = self._get_bool(node, "IFEXCLUDE")
        config["exclude_filemask"] = self._get_str(node, "EXCLUDEFILEMASK", "*.txt")
        config["format_filepath_to_slash"] = self._get_bool(node, "FORMAT_FILEPATH_TO_SLASH")

        # ---- 6. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS")
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 7. Warnings ----
        if not config["directory"]:
            warnings.append(
                "DIRECTORY is empty; the file-list component requires a directory path."
            )

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tFileList",
            config=config,
            # Iterate-style component -- no data flow schema
            schema={"input": [], "output": []},
        )

        # ---- 9. Engine gap needs_review entries ----
        needs_review.append({
            "issue": "No concrete engine implementation for tFileList. All config keys are extracted for future engine support.",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 10. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
