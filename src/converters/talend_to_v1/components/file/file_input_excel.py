"""Converter for Talend tFileInputExcel component.

Reads Excel files (.xls/.xlsx) with support for multiple sheets,
password protection, trimming, date conversion, and advanced separators.

Config mapping (30 params total):
  VERSION_2007              -> version_2007              (bool, default False)
  FILENAME                  -> filepath                  (str, default "")
  PASSWORD                  -> password                  (str, always empty -- cleared for security)
  ALL_SHEETS                -> all_sheets                (bool, default False)
  SHEETLIST                 -> sheetlist                 (TABLE stride-2: SHEETNAME, USE_REGEX)
  HEADER                    -> header                    (int, default 0)
  FOOTER                    -> footer                    (int, default 0)
  LIMIT                     -> limit                     (str, default "")
  AFFECT_EACH_SHEET         -> affect_each_sheet         (str, default "")
  FIRST_COLUMN              -> first_column              (int, default 1)
  LAST_COLUMN               -> last_column               (str, default "")
  DIE_ON_ERROR              -> die_on_error              (bool, default False)
  ADVANCED_SEPARATOR        -> advanced_separator        (bool, default False)
  THOUSANDS_SEPARATOR       -> thousands_separator       (str, default ",")
  DECIMAL_SEPARATOR         -> decimal_separator         (str, default ".")
  TRIMALL                   -> trimall                   (bool, default False)
  TRIMSELECT                -> trim_select               (TABLE stride-2: SCHEMA_COLUMN, TRIM)
  CONVERTDATETOSTRING       -> convertdatetostring       (bool, default False)
  DATESELECT                -> date_select               (TABLE stride-3: SCHEMA_COLUMN, CONVERTDATE, PATTERN)
  ENCODING                  -> encoding                  (str, default "ISO-8859-15")
  READ_REAL_VALUE           -> read_real_value           (bool, default False)
  STOPREAD_ON_EMPTYROW      -> stopread_on_emptyrow      (bool, default False)
  NOVALIDATE_ON_CELL        -> novalidate_on_cell        (bool, default False)
  SUPPRESS_WARN             -> suppress_warn             (bool, default False)
  GENERATION_MODE           -> generation_mode           (str/CLOSED_LIST, default "USER_MODE")
  INCLUDE_PHONETICRUNS      -> include_phoneticruns      (bool, default True)
  CONFIGURE_INFLATION_RATIO -> configure_inflation_ratio (bool, default False)
  INFLATION_RATIO           -> inflation_ratio           (str, default "")
  --- framework ---
  TSTATCATCHER_STATS        -> tstatcatcher_stats        (bool, default False)
  LABEL                     -> label                     (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_SHEETLIST_FIELDS = ("SHEETNAME", "USE_REGEX")
_SHEETLIST_GROUP_SIZE = len(_SHEETLIST_FIELDS)

_TRIMSELECT_FIELDS = ("SCHEMA_COLUMN", "TRIM")
_TRIMSELECT_GROUP_SIZE = len(_TRIMSELECT_FIELDS)

_DATESELECT_FIELDS = ("SCHEMA_COLUMN", "CONVERTDATE", "PATTERN")
_DATESELECT_GROUP_SIZE = len(_DATESELECT_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions (module-level)
# ------------------------------------------------------------------

def _parse_sheetlist(raw: Any) -> List[Dict[str, Any]]:
    """Parse SHEETLIST TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      SHEETNAME  -> sheetname (str, quote-stripped)
      USE_REGEX  -> use_regex (bool)

    Incomplete trailing groups (< 2 entries) produce a row with
    use_regex defaulting to False.
    """
    if not raw or not isinstance(raw, list):
        return []

    result: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}

    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")

        if ref == "SHEETNAME":
            # Flush previous row
            if current and "sheetname" in current:
                result.append(current)
            current = {
                "sheetname": val.strip('"') if isinstance(val, str) else val,
                "use_regex": False,
            }
        elif ref == "USE_REGEX":
            if isinstance(val, str):
                current["use_regex"] = val.lower() in ("true", "1")
            else:
                current["use_regex"] = bool(val)

    # Flush the last accumulated row
    if current and "sheetname" in current:
        result.append(current)

    return result


def _parse_trim_select(raw: Any) -> List[Dict[str, Any]]:
    """Parse TRIMSELECT TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN  -> column (str)
      TRIM           -> trim   (bool)
    """
    if not raw or not isinstance(raw, list):
        return []

    result: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}

    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")

        if ref == "SCHEMA_COLUMN":
            # Flush previous row
            if current and "column" in current:
                result.append(current)
            current = {"column": val, "trim": False}
        elif ref == "TRIM":
            if isinstance(val, str):
                current["trim"] = val.lower() in ("true", "1")
            else:
                current["trim"] = bool(val)

    # Flush the last accumulated row
    if current and "column" in current:
        result.append(current)

    return result


def _parse_date_select(raw: Any) -> List[Dict[str, Any]]:
    """Parse DATESELECT TABLE into list of dicts.

    Each group of 3 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN  -> column       (str)
      CONVERTDATE    -> convert_date (bool)
      PATTERN        -> pattern      (str, quote-stripped, default "MM-dd-yyyy")

    Patterns are stored as Java SimpleDateFormat format (e.g., "yyyy-MM-dd"),
    NOT converted to Python strftime. The v1 engine handles conversion internally.
    """
    if not raw or not isinstance(raw, list):
        return []

    result: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}

    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")

        if ref == "SCHEMA_COLUMN":
            # Flush previous row
            if current and "column" in current:
                result.append(current)
            current = {"column": val, "convert_date": False, "pattern": "MM-dd-yyyy"}
        elif ref == "CONVERTDATE":
            if isinstance(val, str):
                current["convert_date"] = val.lower() in ("true", "1")
            else:
                current["convert_date"] = bool(val)
        elif ref == "PATTERN":
            if isinstance(val, str):
                current["pattern"] = val.strip('"') if val else "MM-dd-yyyy"
            else:
                current["pattern"] = "MM-dd-yyyy"

    # Flush the last accumulated row
    if current and "column" in current:
        result.append(current)

    return result


@REGISTRY.register("tFileInputExcel")
class FileInputExcelConverter(ComponentConverter):
    """Convert Talend tFileInputExcel to v1 FileInputExcel config."""

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
        config["filepath"] = self._get_str(node, "FILENAME", "")
        config["password"] = ""  # Always empty -- never carry passwords into JSON
        config["all_sheets"] = self._get_bool(node, "ALL_SHEETS", False)
        config["header"] = self._get_int(node, "HEADER", 0)
        config["footer"] = self._get_int(node, "FOOTER", 0)
        config["limit"] = self._get_str(node, "LIMIT", "")
        config["affect_each_sheet"] = self._get_str(node, "AFFECT_EACH_SHEET", "")
        config["first_column"] = self._get_int(node, "FIRST_COLUMN", 1)
        config["last_column"] = self._get_str(node, "LAST_COLUMN", "")
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)
        config["suppress_warn"] = self._get_bool(node, "SUPPRESS_WARN", False)
        config["novalidate_on_cell"] = self._get_bool(node, "NOVALIDATE_ON_CELL", False)

        # ---- 2. Advanced separators ----
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")

        # ---- 3. Trimming ----
        config["trimall"] = self._get_bool(node, "TRIMALL", False)

        # ---- 4. TABLE parameters ----
        config["sheetlist"] = _parse_sheetlist(node.params.get("SHEETLIST", []))
        config["trim_select"] = _parse_trim_select(node.params.get("TRIMSELECT", []))

        # ---- 5. Date conversion ----
        config["convertdatetostring"] = self._get_bool(node, "CONVERTDATETOSTRING", False)
        config["date_select"] = _parse_date_select(node.params.get("DATESELECT", []))

        # ---- 6. Reading behaviour ----
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["read_real_value"] = self._get_bool(node, "READ_REAL_VALUE", False)
        config["stopread_on_emptyrow"] = self._get_bool(node, "STOPREAD_ON_EMPTYROW", False)

        # ---- 7. CLOSED_LIST / generation ----
        config["generation_mode"] = self._get_str(node, "GENERATION_MODE", "USER_MODE")

        # ---- 8. Phonetic / inflation ----
        config["include_phoneticruns"] = self._get_bool(node, "INCLUDE_PHONETICRUNS", True)
        config["configure_inflation_ratio"] = self._get_bool(node, "CONFIGURE_INFLATION_RATIO", False)
        config["inflation_ratio"] = self._get_str(node, "INFLATION_RATIO", "")

        # ---- 9. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 10. Warnings ----
        if not config["filepath"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        # ---- 11. Schema ----
        schema = {"input": [], "output": self._parse_schema(node)}

        # ---- 12. Engine gap needs_review entries ----
        # These 9 config keys are extracted from _java.xml but the engine
        # (1022 lines) does not read them at all.
        _engine_gap_keys = [
            ("version_2007", "engine auto-detects .xls vs .xlsx from file extension"),
            ("affect_each_sheet", "engine does not apply header/footer per-sheet independently"),
            ("novalidate_on_cell", "engine does not skip cell type validation"),
            ("generation_mode", "engine does not switch between USER_MODE/EVENT_MODE/STREAM_MODE"),
            ("encoding", "engine relies on openpyxl/xlrd internal encoding handling"),
            ("read_real_value", "engine does not support reading underlying cell values"),
            ("include_phoneticruns", "engine does not handle East Asian phonetic annotations"),
            ("configure_inflation_ratio", "engine does not configure zip inflation ratio"),
            ("inflation_ratio", "engine does not configure zip inflation ratio"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 13. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileInputExcel",
            config=config,
            schema=schema,
        )

        # ---- 14. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
