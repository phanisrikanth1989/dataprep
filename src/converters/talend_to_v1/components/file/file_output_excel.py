"""Converter for Talend tFileOutputExcel component.

Writes data to an Excel file with support for multiple sheets, formatting, and streaming.

Config mapping (29 unique + 2 framework = 31 params total):
  VERSION_2007                  -> version_2007                  (bool, default False)
  USESTREAM                     -> usestream                     (bool, default False)
  STREAMNAME                    -> streamname                    (str, default "outputStream")
  FILENAME                      -> filename                      (str, default "")
  SHEETNAME                     -> sheetname                     (str, default "Sheet1")
  INCLUDEHEADER                 -> includeheader                 (bool, default False)
  APPEND_FILE                   -> append_file                   (bool, default False)
  APPEND_SHEET                  -> append_sheet                  (bool, default False)
  FIRST_CELL_Y_ABSOLUTE         -> first_cell_y_absolute         (bool, default False)
  FIRST_CELL_X                  -> first_cell_x                  (str, default "0")
  FIRST_CELL_Y                  -> first_cell_y                  (str, default "0")
  KEEP_CELL_FORMATING           -> keep_cell_formating           (bool, default False)  # Talend spelling
  FONT                          -> font                          (str, default "NONE")
  IS_ALL_AUTO_SZIE              -> is_all_auto_szie              (bool, default False)  # Talend typo
  AUTO_SZIE_SETTING             -> auto_szie_setting             (list, TABLE)          # Talend typo
  PROTECT_FILE                  -> protect_file                  (bool, default False)
  PASSWORD                      -> password                      (str, default "")
  CREATE                        -> create                        (bool, default True)   # advanced
  FLUSHONROW                    -> flushonrow                    (bool, default False)  # advanced
  FLUSHONROW_NUM                -> flushonrow_num                (str, default "100")   # advanced
  ADVANCED_SEPARATOR            -> advanced_separator            (bool, default False)  # advanced
  THOUSANDS_SEPARATOR           -> thousands_separator           (str, default ",")     # advanced
  DECIMAL_SEPARATOR             -> decimal_separator             (str, default ".")     # advanced
  TRUNCATE_EXCEEDING_CHARACTERS -> truncate_exceeding_characters (bool, default False)  # advanced
  ENCODING                      -> encoding                      (str, default "ISO-8859-15")  # advanced
  DELETE_EMPTYFILE              -> delete_empty_file             (bool, default False)  # advanced
  RECALCULATE_FORMULA           -> recalculate_formula           (bool, default False)  # advanced
  STREAMING_APPEND              -> streaming_append              (bool, default False)  # advanced
  USE_SHARED_STRINGS_TABLE      -> use_shared_strings_table      (bool, default False)  # advanced
  --- framework ---
  TSTATCATCHER_STATS            -> tstatcatcher_stats            (bool, default False)
  LABEL                         -> label                         (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_auto_szie_setting(raw: Any) -> List[str]:
    """Parse AUTO_SZIE_SETTING TABLE into list of column name strings.

    Each entry has elementRef=SCHEMA_COLUMN with a quoted column name.
    Stride-1: one elementRef per row.

    Note: Talend uses the typo 'SZIE' (not 'SIZE') in the param name.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")
        if ref == "SCHEMA_COLUMN":
            result.append(val.strip('"'))
    return result


@REGISTRY.register("tFileOutputExcel")
class FileOutputExcelConverter(ComponentConverter):
    """Convert Talend tFileOutputExcel to v1 engine config."""

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
        config["version_2007"] = self._get_bool(node, "VERSION_2007", False)
        config["usestream"] = self._get_bool(node, "USESTREAM", False)
        config["streamname"] = self._get_str(node, "STREAMNAME", "outputStream")
        config["filename"] = self._get_str(node, "FILENAME", "")
        config["sheetname"] = self._get_str(node, "SHEETNAME", "Sheet1")
        config["includeheader"] = self._get_bool(node, "INCLUDEHEADER", False)
        config["append_file"] = self._get_bool(node, "APPEND_FILE", False)
        config["append_sheet"] = self._get_bool(node, "APPEND_SHEET", False)

        # ---- 2. Positioning parameters ----
        config["first_cell_y_absolute"] = self._get_bool(node, "FIRST_CELL_Y_ABSOLUTE", False)
        config["first_cell_x"] = self._get_str(node, "FIRST_CELL_X", "0")
        config["first_cell_y"] = self._get_str(node, "FIRST_CELL_Y", "0")
        config["keep_cell_formating"] = self._get_bool(node, "KEEP_CELL_FORMATING", False)  # Talend spelling

        # ---- 3. CLOSED_LIST parameters ----
        config["font"] = self._get_str(node, "FONT", "NONE")

        # ---- 4. Auto-size parameters (Talend typos preserved) ----
        config["is_all_auto_szie"] = self._get_bool(node, "IS_ALL_AUTO_SZIE", False)

        # ---- 5. TABLE parameters ----
        raw_auto_szie = node.params.get("AUTO_SZIE_SETTING", [])
        config["auto_szie_setting"] = _parse_auto_szie_setting(raw_auto_szie)

        # ---- 6. Protection parameters ----
        config["protect_file"] = self._get_bool(node, "PROTECT_FILE", False)
        config["password"] = self._get_str(node, "PASSWORD", "")

        # ---- 7. Advanced parameters ----
        config["create"] = self._get_bool(node, "CREATE", True)
        config["flushonrow"] = self._get_bool(node, "FLUSHONROW", False)
        config["flushonrow_num"] = self._get_str(node, "FLUSHONROW_NUM", "100")
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")
        config["truncate_exceeding_characters"] = self._get_bool(node, "TRUNCATE_EXCEEDING_CHARACTERS", False)
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["delete_empty_file"] = self._get_bool(node, "DELETE_EMPTYFILE", False)
        config["recalculate_formula"] = self._get_bool(node, "RECALCULATE_FORMULA", False)
        config["streaming_append"] = self._get_bool(node, "STREAMING_APPEND", False)
        config["use_shared_strings_table"] = self._get_bool(node, "USE_SHARED_STRINGS_TABLE", False)

        # ---- 8. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 9. Schema ----
        # Sink component: input populated, output empty (D-55)
        schema = {"input": self._parse_schema(node), "output": []}

        # ---- 10. Engine gap needs_review entries ----
        # Engine reads 'encoding' with default 'UTF-8' but _java.xml default is 'ISO-8859-15'
        needs_review.append({
            "issue": "Engine default encoding is 'UTF-8' but _java.xml default is 'ISO-8859-15' -- charset mismatch on default config",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read usestream/streamname
        needs_review.append({
            "issue": "Engine does not read 'usestream'/'streamname' config keys -- OutputStream mode not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read font
        needs_review.append({
            "issue": "Engine does not read 'font' config key -- font selection not supported in engine",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read is_all_auto_szie/auto_szie_setting
        needs_review.append({
            "issue": "Engine does not read 'is_all_auto_szie'/'auto_szie_setting' config keys -- column auto-sizing not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read protect_file/password
        needs_review.append({
            "issue": "Engine does not read 'protect_file'/'password' config keys -- workbook protection not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read first_cell_y_absolute/first_cell_x/first_cell_y
        needs_review.append({
            "issue": "Engine does not read 'first_cell_y_absolute'/'first_cell_x'/'first_cell_y' -- cell offset positioning not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read keep_cell_formating
        needs_review.append({
            "issue": "Engine does not read 'keep_cell_formating' config key -- existing cell formatting not preserved",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read advanced_separator/thousands_separator/decimal_separator
        needs_review.append({
            "issue": "Engine does not read 'advanced_separator'/'thousands_separator'/'decimal_separator' -- locale number formatting not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read truncate_exceeding_characters
        needs_review.append({
            "issue": "Engine does not read 'truncate_exceeding_characters' config key -- cell content truncation not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read delete_empty_file
        needs_review.append({
            "issue": "Engine does not read 'delete_empty_file' config key -- empty file cleanup not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read recalculate_formula
        needs_review.append({
            "issue": "Engine does not read 'recalculate_formula' config key -- formula recalculation not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read flushonrow/flushonrow_num
        needs_review.append({
            "issue": "Engine does not read 'flushonrow'/'flushonrow_num' config keys -- row flush buffer control not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read streaming_append
        needs_review.append({
            "issue": "Engine does not read 'streaming_append' config key -- SXSSF streaming write mode not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read use_shared_strings_table
        needs_review.append({
            "issue": "Engine does not read 'use_shared_strings_table' config key -- shared strings optimization not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read version_2007 (always writes xlsx via openpyxl)
        needs_review.append({
            "issue": "Engine does not read 'version_2007' config key -- always writes .xlsx format via openpyxl",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine reads 'die_on_error' (default True) but _java.xml does not have DIE_ON_ERROR param
        needs_review.append({
            "issue": "Engine reads 'die_on_error' (default True) but param not in _java.xml -- engine-only config key",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 11. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileOutputExcel",
            config=config,
            schema=schema,
        )

        # ---- 12. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
