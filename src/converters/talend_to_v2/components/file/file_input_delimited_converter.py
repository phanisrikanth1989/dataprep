"""Converter for Talend tFileInputDelimited to v2 FileInputDelimited component.

Restructured onto the v2 Component Standard (Phase 7, COMP-05).
Covers 33 Talend parameters mapped to v2 config, SUPPORTED_FEATURES
introspection for UNSUPPORTED/NOT_PLANNED warnings, and encoding advice.

Config mapping:
  FILENAME         -> path (context expression converted)
  FIELDSEPARATOR   -> delimiter (single-byte only)
  HEADER           -> has_header (bool), skip_rows (int)
  FOOTER           -> footer_rows (int)
  LIMIT            -> limit (int)
  ENCODING         -> encoding (utf8/utf8-lossy only; warns on others per D-01)
  REMOVE_EMPTY_ROW -> skip_empty_rows (bool)
  TRIMALL          -> trim_all (bool)
  TRIMSELECT       -> trim_columns (list of per-column trim configs)
  DIE_ON_ERROR     -> die_on_error (bool)
  CSV_OPTION       -> quote_char (from TEXT_ENCLOSURE), eol_char (from CSVROWSEPARATOR)
  TEXT_ENCLOSURE   -> quote_char (when CSV_OPTION=true)
  ESCAPE_CHAR      -> warning if differs from TEXT_ENCLOSURE
  ROWSEPARATOR     -> eol_char (with warning for non-standard values per review)
  UNCOMPRESS       -> warning (gzip auto-detected; ZIP unsupported)
  REJECT flow      -> die_on_error=false (when REJECT connector wired)
  LABEL            -> label
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

_VALID_ENCODINGS = frozenset({"utf8", "utf-8", "UTF-8", "utf8-lossy"})

_TRIMSELECT_FIELDS = ("SCHEMA_COLUMN", "TRIM")
_TRIMSELECT_GROUP_SIZE = len(_TRIMSELECT_FIELDS)

# Talend TRIM values -> v2 trim types
_TRIM_VALUE_MAP = {
    "BOTH": "both",
    "LEFT": "left",
    "RIGHT": "right",
    "both": "both",
    "left": "left",
    "right": "right",
}

# Common Talend escape sequences -> actual characters
_ESCAPE_MAP = {"\\n": "\n", "\\r": "\r", "\\t": "\t"}

# UNSUPPORTED parameter warnings
_UNSUPPORTED_PARAMS = {
    "ADVANCED_SEPARATOR": (
        "ADVANCED_SEPARATOR (locale-aware numeric parsing) is UNSUPPORTED in v2. "
        "Polars has decimal_comma but no thousands_separator."
    ),
    "THOUSANDS_SEPARATOR": "THOUSANDS_SEPARATOR is UNSUPPORTED in v2.",
    "DECIMAL_SEPARATOR": "DECIMAL_SEPARATOR is UNSUPPORTED in v2.",
}

# NOT_PLANNED parameter warnings
_NOT_PLANNED_PARAMS = {
    "RANDOM": "RANDOM is NOT_PLANNED -- use downstream sampling expressions instead.",
    "NB_RANDOM": "NB_RANDOM is NOT_PLANNED -- use downstream sampling expressions instead.",
    "ENABLE_DECODE": "ENABLE_DECODE is NOT_PLANNED -- hex/octal decoding has no Polars native support.",
    "DECODE_COLS": "DECODE_COLS is NOT_PLANNED.",
    "SPLITRECORD": "SPLITRECORD is NOT_PLANNED -- Polars quote_char handles embedded newlines (RFC4180).",
    "CHECK_FIELDS_NUM": "CHECK_FIELDS_NUM is NOT_PLANNED -- Polars truncate_ragged_lines has different semantics.",
    "CHECK_DATE": "CHECK_DATE is NOT_PLANNED -- date validation handled by schema typing.",
    "SCHEMA_OPT_NUM": "SCHEMA_OPT_NUM is NOT_PLANNED -- Talend Studio UI feature.",
    "USE_HEADER_AS_IS": "USE_HEADER_AS_IS is NOT_PLANNED -- Polars reads headers natively.",
    "TSTATCATCHER_STATS": "TSTATCATCHER_STATS is NOT_PLANNED -- use Python logging.",
}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def convert_path_expression(expr: str) -> str:
    """Convert a Talend path expression to V2 format.

    Handles:
    - ``context.var`` -> ``${context.var}``
    - ``context.dir + "file_" + context.date + ".csv"`` ->
      ``${context.dir}file_${context.date}.csv``
    """
    expr = expr.strip()

    # Simple case: bare context reference
    if re.fullmatch(r"context\.\w+", expr):
        return f"${{{expr}}}"

    # Concatenation: split on '+', resolve each segment
    if "+" in expr:
        parts = [p.strip() for p in expr.split("+")]
        result = []
        for part in parts:
            if re.fullmatch(r"context\.\w+", part):
                result.append(f"${{{part}}}")
            elif len(part) >= 2 and part[0] == '"' and part[-1] == '"':
                result.append(part[1:-1])
            else:
                result.append(part)
        return "".join(result)

    return expr


def _safe_int(value: str, default: int = 0) -> int:
    """Parse an integer from a string, returning *default* on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _strip_talend_quotes(value: str) -> str:
    """Strip surrounding double-quotes that Talend XML wraps around parameter values.

    Talend encodes string values as ``&quot;hello&quot;`` in XML which after
    XML parsing becomes ``"hello"`` (with literal surrounding double-quotes).
    This helper strips those outer quotes to produce ``hello``.
    """
    return value.strip('"')


def _parse_trimselect(raw: Any) -> List[Dict[str, str]]:
    """Parse TRIMSELECT TABLE into list of per-column trim configs.

    Stride-2: SCHEMA_COLUMN, TRIM.  Returns list of dicts:
    [{"column": "col_name", "trim": "both"|"left"|"right"}]
    """
    if not raw or not isinstance(raw, list):
        return []

    result: List[Dict[str, str]] = []
    entries = raw
    for i in range(0, len(entries), _TRIMSELECT_GROUP_SIZE):
        group = entries[i : i + _TRIMSELECT_GROUP_SIZE]
        if len(group) < _TRIMSELECT_GROUP_SIZE:
            break

        # Build a dict keyed by elementRef
        by_ref = {}
        for entry in group:
            ref = entry.get("elementRef", "")
            val = _strip_talend_quotes(entry.get("value", ""))
            by_ref[ref] = val

        col_name = by_ref.get("SCHEMA_COLUMN", "")
        trim_raw = by_ref.get("TRIM", "BOTH")
        trim_type = _TRIM_VALUE_MAP.get(trim_raw, "both")

        if col_name:
            result.append({"column": col_name, "trim": trim_type})

    return result


def _has_reject_connection(
    node: TalendNode, connections: list[TalendConnection],
) -> bool:
    """Return True if any outgoing connection from *node* is a REJECT flow."""
    return any(
        c.source == node.component_id and c.connector_type == "REJECT"
        for c in connections
    )


# ------------------------------------------------------------------
# Converter
# ------------------------------------------------------------------

@REGISTRY.register("tFileInputDelimited")
class FileInputDelimitedConverter(ComponentConverter):
    """Converts tFileInputDelimited to v2 FileInputDelimited.

    Covers all 33 Talend parameters with v2 config mapping,
    UNSUPPORTED/NOT_PLANNED warnings, and encoding advice.
    """

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        """Convert a tFileInputDelimited node into a v2 component dict."""
        params = node.params
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []
        config: Dict[str, Any] = {}

        # ---- 1. Path (D-07) ----
        config["path"] = convert_path_expression(params.get("FILENAME", ""))

        # ---- 2. Delimiter (D-08, D-30) ----
        separator = params.get("FIELDSEPARATOR", ",")
        separator = _strip_talend_quotes(separator)
        if len(separator) > 1:
            warnings.append(
                f"{node.component_id}: Multi-char FIELDSEPARATOR is UNSUPPORTED in v2 "
                f"(Polars requires single-byte). Got: '{separator}'"
            )
        config["delimiter"] = separator

        # ---- 3. Header/Footer/Limit (D-09) ----
        header_val = _safe_int(params.get("HEADER", "0"))
        config["has_header"] = header_val > 0
        if header_val > 1:
            config["skip_rows"] = header_val - 1  # skip extra header rows beyond the first

        footer = _safe_int(params.get("FOOTER", "0"))
        if footer > 0:
            config["footer_rows"] = footer

        limit_val = _safe_int(params.get("LIMIT", ""))
        if limit_val > 0:
            config["limit"] = limit_val

        # ---- 4. Encoding (D-01, D-02, D-29) ----
        encoding = _strip_talend_quotes(params.get("ENCODING", "UTF-8"))
        if encoding.lower().replace("-", "") in ("utf8", "utf8lossy"):
            config["encoding"] = "utf8" if "lossy" not in encoding.lower() else "utf8-lossy"
        else:
            config["encoding"] = "utf8"  # default to utf8
            warnings.append(
                f"ENCODING '{encoding}' is UNSUPPORTED in v2 (Polars supports utf8/utf8-lossy only). "
                f"Pre-convert file to UTF-8 or use a dedicated encoding component."
            )

        # ---- 5. skip_empty_rows (D-10) ----
        if "REMOVE_EMPTY_ROW" in params:
            val = params["REMOVE_EMPTY_ROW"]
            config["skip_empty_rows"] = val if isinstance(val, bool) else str(val).lower() == "true"

        # ---- 6. Trim (D-12, D-13) ----
        if "TRIMALL" in params:
            val = params["TRIMALL"]
            config["trim_all"] = val if isinstance(val, bool) else str(val).lower() == "true"

        if "TRIMSELECT" in params:
            trim_cols = _parse_trimselect(params["TRIMSELECT"])
            if trim_cols:
                config["trim_columns"] = trim_cols

        # ---- 7. DIE_ON_ERROR / REJECT (D-11, D-16) ----
        if "DIE_ON_ERROR" in params:
            val = params["DIE_ON_ERROR"]
            config["die_on_error"] = val if isinstance(val, bool) else str(val).lower() == "true"

        if _has_reject_connection(node, connections):
            config["die_on_error"] = False  # REJECT wired implies die_on_error=false

        # ---- 8. CSV_OPTION (D-18) ----
        csv_option = params.get("CSV_OPTION", False)
        if isinstance(csv_option, str):
            csv_option = csv_option.lower() == "true"

        if csv_option:
            text_enclosure = _strip_talend_quotes(params.get("TEXT_ENCLOSURE", '"'))
            config["quote_char"] = text_enclosure

            escape_char = _strip_talend_quotes(params.get("ESCAPE_CHAR", '"'))
            if escape_char != text_enclosure:
                warnings.append(
                    f"{node.component_id}: ESCAPE_CHAR ('{escape_char}') differs from "
                    f"TEXT_ENCLOSURE ('{text_enclosure}') -- "
                    f"v2 does not support a separate escape character"
                )

            csvrowsep = params.get("CSVROWSEPARATOR")
            if csvrowsep:
                stripped_csv = _strip_talend_quotes(csvrowsep)
                config["eol_char"] = _ESCAPE_MAP.get(stripped_csv, stripped_csv)
        elif "TEXT_ENCLOSURE" in params:
            config["quote_char"] = _strip_talend_quotes(params["TEXT_ENCLOSURE"])

        # ---- 9. ROWSEPARATOR + eol_char warning (D-14) ----
        # Addresses review concern: eol_char custom separators (MEDIUM)
        rowsep = params.get("ROWSEPARATOR")
        if rowsep and "eol_char" not in config:
            stripped = _strip_talend_quotes(rowsep)
            resolved = _ESCAPE_MAP.get(stripped, stripped)
            config["eol_char"] = resolved
            # Warn on non-standard row separators -- Polars fast CSV parser is
            # optimized for \n and \r\n. Custom eol_char values may cause slower
            # parsing or unexpected behavior with multi-byte line endings.
            if stripped not in ("\n", "\r\n", "\\n", "\\r\\n"):
                warnings.append(
                    f"{node.component_id}: ROWSEPARATOR '{stripped}' is non-standard. "
                    f"Polars CSV parser is optimized for \\n and \\r\\n line endings. "
                    f"Custom row separators may cause slower parsing."
                )

        # ---- 10. NaN-to-null (always enabled for converted jobs, D-05) ----
        config["nan_is_null"] = True

        # ---- 11. UNCOMPRESS (D-19) ----
        uncompress = params.get("UNCOMPRESS", False)
        if isinstance(uncompress, str):
            uncompress = uncompress.lower() == "true"
        if uncompress:
            warnings.append(
                f"{node.component_id}: UNCOMPRESS -- gzip (.gz) is auto-detected by Polars "
                f"(no config needed). ZIP archives are UNSUPPORTED. Use gzip compression "
                f"or extract ZIP before processing."
            )

        # ---- 12. Label (D-17) ----
        label = params.get("LABEL")
        if label:
            config["label"] = _strip_talend_quotes(label)

        # ---- 13. Schema ----
        flow_schema = node.schema.get("FLOW", [])
        if flow_schema:
            from ...type_mapping import convert_schema
            config["schema"] = convert_schema(flow_schema)

        # ---- 14. UNSUPPORTED/NOT_PLANNED introspection (D-20..D-28) ----
        for param_name, msg in {**_UNSUPPORTED_PARAMS, **_NOT_PLANNED_PARAMS}.items():
            raw_val = params.get(param_name)
            if raw_val is not None:
                # Check if param is set to a truthy value
                is_active = raw_val
                if isinstance(is_active, str):
                    is_active = is_active.lower() not in ("false", "0", "")
                if is_active:
                    warnings.append(f"{node.component_id}: {msg}")

        # ---- 15. Build component + flows ----
        component = {
            "id": node.component_id,
            "type": "file_input_delimited",
            "config": config,
        }
        flows = self._build_simple_flows(node, connections)
        return ComponentResult(
            component=component,
            flows=flows,
            warnings=warnings,
            needs_review=needs_review,
        )
