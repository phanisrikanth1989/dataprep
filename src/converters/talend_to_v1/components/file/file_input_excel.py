"""Converter for tFileInputExcel -> FileInputExcel.

Parses all tFileInputExcel parameters including complex TABLE params
(SHEETLIST, TRIMSELECT, DATESELECT) with elementRef/value entries.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputExcel")
class FileInputExcelConverter(ComponentConverter):
    """Convert a Talend tFileInputExcel node to v1 FileInputExcel."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Basic file parameters ---
        filepath = self._get_str(node, "FILENAME")
        if not filepath:
            warnings.append("FILENAME is empty — this is a required parameter")

        # --- Sheet list TABLE param ---
        sheetlist = self._parse_sheetlist(node)

        # --- Trim select TABLE param ---
        trim_select = self._parse_trim_select(node)

        # --- Date select TABLE param ---
        date_select = self._parse_date_select(node)

        config: Dict[str, Any] = {
            # Basic
            "filepath": filepath,
            "password": self._get_str(node, "PASSWORD"),
            "version_2007": self._get_bool(node, "VERSION_2007", True),
            "all_sheets": self._get_bool(node, "ALL_SHEETS", False),
            # Sheet selection
            "sheetlist": sheetlist,
            # Row/column
            "header": self._get_int(node, "HEADER", 1),
            "footer": self._get_int(node, "FOOTER", 0),
            "limit": self._get_str(node, "LIMIT"),
            "affect_each_sheet": self._get_bool(node, "AFFECT_EACH_SHEET", False),
            "first_column": self._get_int(node, "FIRST_COLUMN", 1),
            "last_column": self._get_str(node, "LAST_COLUMN"),
            # Error handling
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
            "suppress_warn": self._get_bool(node, "SUPPRESS_WARN", False),
            "novalidate_on_cell": self._get_bool(node, "NOVALIDATE_ON_CELL", False),
            # Advanced separators
            "advanced_separator": self._get_bool(node, "ADVANCED_SEPARATOR", False),
            "thousands_separator": self._get_str(node, "THOUSANDS_SEPARATOR", ","),
            "decimal_separator": self._get_str(node, "DECIMAL_SEPARATOR", "."),
            # Trimming
            "trimall": self._get_bool(node, "TRIMALL", False),
            "trim_select": trim_select,
            # Date conversion
            "convertdatetostring": self._get_bool(node, "CONVERTDATETOSTRING", False),
            "date_select": date_select,
            # Reading behaviour
            "read_real_value": self._get_bool(node, "READ_REAL_VALUE", False),
            "stopread_on_emptyrow": self._get_bool(node, "STOPREAD_ON_EMPTYROW", False),
            # Generation / performance
            "generation_mode": self._get_str(node, "GENERATION_MODE", "EVENT_MODE"),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            # Extra
            "sheet_name": self._get_str(node, "SHEET_NAME"),
            "execution_mode": self._get_str(node, "EXECUTION_MODE"),
            "chunk_size": self._get_str(node, "CHUNK_SIZE"),
        }

        component = self._build_component_dict(
            node=node,
            type_name="FileInputExcel",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)

    # ------------------------------------------------------------------
    # TABLE param parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_sheetlist(node: TalendNode) -> List[Dict[str, Any]]:
        """Parse SHEETLIST TABLE param into list of {sheetname, use_regex} dicts."""
        raw = node.params.get("SHEETLIST", [])
        result: List[Dict[str, Any]] = []
        if not isinstance(raw, list):
            return result
        for entry in raw:
            ref = entry.get("elementRef", "")
            value = entry.get("value", "")
            # SHEETLIST entries have elementRef of SHEETNAME or USE_REGEX.
            # However TABLE params may come pre-grouped as dicts or as flat
            # elementRef/value pairs.  We handle both forms.
            if isinstance(entry, dict) and "sheetname" in entry:
                # Already pre-parsed dict
                sheet: Dict[str, Any] = {"sheetname": entry["sheetname"]}
                use_regex = entry.get("use_regex", False)
                if isinstance(use_regex, str):
                    use_regex = use_regex.lower() in ("true", "1")
                sheet["use_regex"] = bool(use_regex)
                result.append(sheet)
            elif ref == "SHEETNAME":
                val = value.strip('"') if isinstance(value, str) else value
                result.append({"sheetname": val, "use_regex": False})
        # Second pass: patch use_regex from flat entries
        regex_idx = 0
        for entry in raw:
            ref = entry.get("elementRef", "")
            value = entry.get("value", "")
            if ref == "USE_REGEX" and regex_idx < len(result):
                if isinstance(value, str):
                    result[regex_idx]["use_regex"] = value.lower() in ("true", "1")
                else:
                    result[regex_idx]["use_regex"] = bool(value)
                regex_idx += 1
        return result

    @staticmethod
    def _parse_trim_select(node: TalendNode) -> List[Dict[str, Any]]:
        """Parse TRIMSELECT TABLE param into list of {column, trim} dicts."""
        raw = node.params.get("TRIMSELECT", [])
        result: List[Dict[str, Any]] = []
        if not isinstance(raw, list):
            return result
        for entry in raw:
            if isinstance(entry, dict) and "column" in entry:
                trim_val = entry.get("trim", False)
                if isinstance(trim_val, str):
                    trim_val = trim_val.lower() in ("true", "1")
                result.append({"column": entry["column"], "trim": bool(trim_val)})
            else:
                ref = entry.get("elementRef", "")
                value = entry.get("value", "")
                if ref == "SCHEMA_COLUMN":
                    result.append({"column": value, "trim": False})
                elif ref == "TRIM" and result:
                    if isinstance(value, str):
                        result[-1]["trim"] = value.lower() in ("true", "1")
                    else:
                        result[-1]["trim"] = bool(value)
        return result

    @staticmethod
    def _parse_date_select(node: TalendNode) -> List[Dict[str, Any]]:
        """Parse DATESELECT TABLE param into list of {column, convert_date, pattern} dicts.

        Note: Patterns are stored as Java SimpleDateFormat format (e.g., "yyyy-MM-dd"),
        NOT converted to Python strftime. This matches the old complex_converter behavior.
        The v1 engine's FileInputExcel component handles the Java-to-Python conversion
        internally when processing date columns.
        """
        raw = node.params.get("DATESELECT", [])
        result: List[Dict[str, Any]] = []
        if not isinstance(raw, list):
            return result
        for entry in raw:
            if isinstance(entry, dict) and "column" in entry:
                cd = entry.get("convert_date", False)
                if isinstance(cd, str):
                    cd = cd.lower() in ("true", "1")
                pat = entry.get("pattern", "MM-dd-yyyy")
                if isinstance(pat, str):
                    pat = pat.strip('"')
                result.append({
                    "column": entry["column"],
                    "convert_date": bool(cd),
                    "pattern": pat,
                })
            else:
                ref = entry.get("elementRef", "")
                value = entry.get("value", "")
                if ref == "SCHEMA_COLUMN":
                    result.append({
                        "column": value,
                        "convert_date": False,
                        "pattern": "MM-dd-yyyy",
                    })
                elif ref == "CONVERTDATE" and result:
                    if isinstance(value, str):
                        result[-1]["convert_date"] = value.lower() in ("true", "1")
                    else:
                        result[-1]["convert_date"] = bool(value)
                elif ref == "PATTERN" and result:
                    if isinstance(value, str):
                        result[-1]["pattern"] = value.strip('"') if value else "MM-dd-yyyy"
                    else:
                        result[-1]["pattern"] = "MM-dd-yyyy"
        return result
