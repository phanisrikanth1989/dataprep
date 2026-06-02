"""Converter for Talend tFileInputDelimited component.

Reads a character-delimited flat file (CSV, TSV, etc.) and outputs rows as a
data flow. The most commonly used input component in Talend.

Config mapping (31 params total):
  FILENAME             -> filepath             (str, default "")
  CSV_OPTION           -> csv_option           (bool, default False)
  ROWSEPARATOR         -> row_separator        (str, default "\\n")
  CSVROWSEPARATOR      -> csv_row_separator    (str, default "\\n")
  FIELDSEPARATOR       -> fieldseparator       (str, default ";") -- engine reads "delimiter"
  ESCAPE_CHAR          -> escape_char          (str, default '"')
  TEXT_ENCLOSURE        -> text_enclosure       (str, default '"')
  HEADER               -> header_rows          (int, default 0)
  FOOTER               -> footer_rows          (int, default 0)
  LIMIT                -> limit                (str, default "")
  REMOVE_EMPTY_ROW     -> remove_empty_row     (bool, default True)
  UNCOMPRESS           -> uncompress           (bool, default False)
  DIE_ON_ERROR         -> die_on_error         (bool, default False)
  ADVANCED_SEPARATOR   -> advanced_separator   (bool, default False)
  THOUSANDS_SEPARATOR  -> thousands_separator  (str, default ",")
  DECIMAL_SEPARATOR    -> decimal_separator    (str, default ".")
  RANDOM               -> random               (bool, default False)
  NB_RANDOM            -> nb_random            (int, default 10)
  TRIMALL              -> trim_all             (bool, default False)
  TRIMSELECT           -> trim_select          (TABLE)
  CHECK_FIELDS_NUM     -> check_fields_num     (bool, default False)
  CHECK_DATE           -> check_date           (bool, default False)
  ENCODING             -> encoding             (str, default "ISO-8859-15")
  SPLITRECORD          -> split_record         (bool, default False)
  ENABLE_DECODE        -> enable_decode        (bool, default False)
  DECODE_COLS          -> decode_cols          (TABLE)
  --- framework ---
  TSTATCATCHER_STATS   -> tstatcatcher_stats   (bool, default False)
  LABEL                -> label                (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY
from ...expression_converter import ExpressionConverter

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_TRIM_SELECT_FIELDS = ("SCHEMA_COLUMN", "TRIM")
_TRIM_SELECT_STRIDE = len(_TRIM_SELECT_FIELDS)

_DECODE_COLS_FIELDS = ("SCHEMA_COLUMN", "DECODE")
_DECODE_COLS_STRIDE = len(_DECODE_COLS_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions (module-level, prefixed with underscore)
# ------------------------------------------------------------------
def _parse_trim_select(raw: Any) -> List[Dict[str, Any]]:
    """Parse TRIMSELECT TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN -> column (str)
      TRIM          -> trim   (bool)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _TRIM_SELECT_STRIDE):
        group = raw[i: i + _TRIM_SELECT_STRIDE]
        if len(group) < _TRIM_SELECT_STRIDE:
            break
        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                row["column"] = val.strip('"')
            elif ref == "TRIM":
                row["trim"] = val.strip('"').lower() in ("true", "1")
        if row:
            result.append(row)
    return result


def _parse_decode_cols(raw: Any) -> List[Dict[str, Any]]:
    """Parse DECODE_COLS TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN -> column (str)
      DECODE        -> decode (bool)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _DECODE_COLS_STRIDE):
        group = raw[i: i + _DECODE_COLS_STRIDE]
        if len(group) < _DECODE_COLS_STRIDE:
            break
        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                row["column"] = val.strip('"')
            elif ref == "DECODE":
                row["decode"] = val.strip('"').lower() in ("true", "1")
        if row:
            result.append(row)
    return result


@REGISTRY.register("tFileInputDelimited")
class FileInputDelimitedConverter(ComponentConverter):
    """Convert Talend tFileInputDelimited to v1 FileInputDelimited config."""

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
        # Mark Java expressions in filepath (e.g. ((String)globalMap.get(...))) with {{java}}
        # so the engine's Java bridge can resolve them at runtime.
        config["filepath"] = ExpressionConverter.mark_java_expression(
            self._get_str(node, "FILENAME", "")
        )
        config["csv_option"] = self._get_bool(node, "CSV_OPTION", False)
        config["row_separator"] = self._get_str(node, "ROWSEPARATOR", "\\n")
        config["csv_row_separator"] = self._get_str(node, "CSVROWSEPARATOR", "\\n")
        config["fieldseparator"] = self._get_str(node, "FIELDSEPARATOR", ";")
        config["escape_char"] = self._get_str(node, "ESCAPE_CHAR", '"')
        config["text_enclosure"] = self._get_str(node, "TEXT_ENCLOSURE", '"')
        config["header_rows"] = self._get_int_or_context(node, "HEADER", 0)
        config["footer_rows"] = self._get_int_or_context(node, "FOOTER", 0)
        config["limit"] = self._get_str(node, "LIMIT", "")
        config["remove_empty_row"] = self._get_bool(node, "REMOVE_EMPTY_ROW", True)
        config["uncompress"] = self._get_bool(node, "UNCOMPRESS", False)
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)

        # ---- 2. Advanced parameters ----
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")
        config["random"] = self._get_bool(node, "RANDOM", False)
        config["nb_random"] = self._get_int(node, "NB_RANDOM", 10)
        config["trim_all"] = self._get_bool(node, "TRIMALL", False)
        config["check_fields_num"] = self._get_bool(node, "CHECK_FIELDS_NUM", False)
        config["check_date"] = self._get_bool(node, "CHECK_DATE", False)
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["split_record"] = self._get_bool(node, "SPLITRECORD", False)
        config["enable_decode"] = self._get_bool(node, "ENABLE_DECODE", False)

        # ---- 3. TABLE parameters ----
        raw_trim_select = node.params.get("TRIMSELECT", [])
        config["trim_select"] = _parse_trim_select(raw_trim_select)

        raw_decode_cols = node.params.get("DECODE_COLS", [])
        config["decode_cols"] = _parse_decode_cols(raw_decode_cols)

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema ----
        schema = {"input": [], "output": self._parse_schema(node)}

        # ---- 7. Engine gap needs_review entries (deferred features only) ----
        # NOTE: keys removed after engine alignment (engine now reads them):
        #   fieldseparator, csv_option, csv_row_separator, check_fields_num, check_date
        # Remaining entries are TRULY deferred features (see _DEFERRED_FEATURES in
        # src/v1/engine/components/file/file_input_delimited.py).
        _engine_gap_keys = [
            ("split_record", "engine has no explicit multi-line field toggle"),
            ("random", "engine does not support random line extraction"),
            ("enable_decode", "engine does not support hex/octal number parsing"),
            ("advanced_separator", "engine has partial support -- applies to all string columns, not just numeric"),
            ("uncompress", "engine does not support compressed file reading"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileInputDelimited",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
