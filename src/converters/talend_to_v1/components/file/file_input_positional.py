"""Converter for Talend tFileInputPositional component.

Reads fixed-width (positional) files where columns are defined by character positions.

Config mapping (20 unique + 2 framework = 22 params total):
  FILENAME             -> filepath             (str, default "")  -- engine reads "filepath", intentional D-38 deviation
  ROWSEPARATOR         -> row_separator        (str, default "\\n")
  PATTERN              -> pattern              (str, default "5,4,5")
  PATTERN_UNITS        -> pattern_units        (str/CLOSED_LIST, default "SYMBOLS")
  ADVANCED_OPTION      -> advanced_option      (bool, default False)
  REMOVE_EMPTY_ROW     -> remove_empty_row     (bool, default True)
  TRIMALL              -> trim_all             (bool, default True)
  ENCODING             -> encoding             (str, default "ISO-8859-15")
  HEADER               -> header_rows          (int, default 0)
  FOOTER               -> footer_rows          (int, default 0)
  LIMIT                -> limit                (str, default "")
  DIE_ON_ERROR         -> die_on_error         (bool, default False)
  PROCESS_LONG_ROW     -> process_long_row     (bool, default False)
  ADVANCED_SEPARATOR   -> advanced_separator   (bool, default False)
  THOUSANDS_SEPARATOR  -> thousands_separator  (str, default ",")
  DECIMAL_SEPARATOR    -> decimal_separator    (str, default ".")
  CHECK_DATE           -> check_date           (bool, default False)
  UNCOMPRESS           -> uncompress           (bool, default False)
  FORMATS              -> formats              (TABLE, stride-4: SCHEMA_COLUMN/SIZE/PADDING_CHAR/ALIGN)
  TRIMSELECT           -> trim_select          (TABLE, stride-2: SCHEMA_COLUMN/TRIM)
  --- framework ---
  TSTATCATCHER_STATS   -> tstatcatcher_stats   (bool, default False)
  LABEL                -> label                (str, default "")

Note: USE_BYTE is a phantom param -- engine reads PATTERN_UNITS instead. Excluded from config.
Note: Config key is "filepath" (not "filename") to match engine's config.get("filepath") pattern.
      This is an intentional deviation from D-38 snake_case convention, documented per D-38.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# TABLE parsers (module-level, prefixed with underscore)
# ------------------------------------------------------------------


def _parse_formats_table(raw: Any) -> List[Dict[str, str]]:
    """Parse FORMATS TABLE from flat elementRef/value pairs into per-column dicts.

    Each group starts with SCHEMA_COLUMN; subsequent entries (SIZE, PADDING_CHAR,
    ALIGN) are optional and accumulate until the next SCHEMA_COLUMN.

    Input (from XML parser):
        [{"elementRef": "SCHEMA_COLUMN", "value": "id"},
         {"elementRef": "SIZE", "value": "10"},
         {"elementRef": "PADDING_CHAR", "value": "' '"},
         {"elementRef": "ALIGN", "value": "'L'"},
         {"elementRef": "SCHEMA_COLUMN", "value": "name"}, ...]

    Output:
        [{"schema_column": "id", "size": "10", "padding_char": "' '", "align": "'L'"},
         {"schema_column": "name", ...}, ...]
    """
    if not raw or not isinstance(raw, list):
        return []

    result: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")
        if ref == "SCHEMA_COLUMN":
            if current and "schema_column" in current:
                result.append(current)
            current = {"schema_column": val}
        elif ref == "SIZE":
            current["size"] = val
        elif ref == "PADDING_CHAR":
            current["padding_char"] = val
        elif ref == "ALIGN":
            current["align"] = val
    if current and "schema_column" in current:
        result.append(current)
    return result


def _parse_trim_select(raw: Any) -> List[Dict[str, Any]]:
    """Parse TRIMSELECT TABLE from flat elementRef/value pairs.

    Each group of 2 entries maps to one row:
      SCHEMA_COLUMN -> column (str)
      TRIM          -> trim   (bool)

    Input:  [{"elementRef": "SCHEMA_COLUMN", "value": "id"},
             {"elementRef": "TRIM", "value": "false"}, ...]
    Output: [{"column": "id", "trim": False}, ...]
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
            if current and "column" in current:
                result.append(current)
            current = {"column": val}
        elif ref == "TRIM":
            current["trim"] = val.lower() in ("true", "1")
    if current and "column" in current:
        result.append(current)
    return result


@REGISTRY.register("tFileInputPositional")
class FileInputPositionalConverter(ComponentConverter):
    """Convert Talend tFileInputPositional to v1 FileInputPositional config."""

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
        config["filepath"] = self._get_str(node, "FILENAME", "")
        config["row_separator"] = self._get_str(node, "ROWSEPARATOR", "\\n")
        config["pattern"] = self._get_str(node, "PATTERN", "5,4,5")
        config["pattern_units"] = self._get_str(node, "PATTERN_UNITS", "SYMBOLS")
        config["advanced_option"] = self._get_bool(node, "ADVANCED_OPTION", False)
        config["remove_empty_row"] = self._get_bool(node, "REMOVE_EMPTY_ROW", True)
        config["trim_all"] = self._get_bool(node, "TRIMALL", True)
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["header_rows"] = self._get_int_or_context(node, "HEADER", 0)
        config["footer_rows"] = self._get_int_or_context(node, "FOOTER", 0)
        config["limit"] = self._get_str(node, "LIMIT", "")
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)

        # ---- 2. Advanced parameters ----
        config["process_long_row"] = self._get_bool(node, "PROCESS_LONG_ROW", False)
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")
        config["check_date"] = self._get_bool(node, "CHECK_DATE", False)
        config["uncompress"] = self._get_bool(node, "UNCOMPRESS", False)

        # ---- 3. TABLE parameters ----
        config["formats"] = _parse_formats_table(node.params.get("FORMATS", []))
        config["trim_select"] = _parse_trim_select(node.params.get("TRIMSELECT", []))

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema ----
        schema = {"input": [], "output": self._parse_schema(node)}

        # ---- 7. Engine gap needs_review entries (per D-36: per-feature) ----
        _engine_gap_keys = [
            ("process_long_row", "engine does not implement long-row buffering"),
            ("uncompress", "engine does not support reading from ZIP archives"),
            ("advanced_separator", "engine does not support locale-aware number formatting"),
            ("check_date", "engine does not validate date fields against schema patterns"),
            ("trim_select", "engine only supports all-or-nothing trim via trim_all, not per-column"),
            ("encoding", "engine defaults to UTF-8 while Talend defaults to ISO-8859-15"),
            ("formats", "engine does not read FORMATS table -- uses pattern widths only"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- Warnings for empty required params ----
        if not config["filepath"]:
            warnings.append("FILENAME is empty -- this is a required parameter")

        if not config["advanced_option"] and not config["pattern"]:
            warnings.append("PATTERN is empty -- positional file parsing requires a pattern")
        elif config["advanced_option"] and not config["formats"]:
            warnings.append("FORMATS table is empty -- 'Customize' positional parsing requires formats")

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileInputPositional",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
