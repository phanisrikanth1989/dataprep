"""Converter for Talend tFileOutputDelimited to v2 FileOutputDelimited component.

Restructured onto the v2 Component Standard (Phase 8, COMP-06).
Covers all Talend parameters mapped to v2 config, with
UNSUPPORTED/NOT_PLANNED warnings and encoding advice.

Config mapping:
  FILENAME             -> path (context expression converted)
  FIELDSEPARATOR       -> delimiter (single-byte, escape sequences resolved)
  ROWSEPARATOR         -> line_terminator (escape sequences resolved)
  INCLUDEHEADER        -> has_header (bool; Talend default false)
  APPEND               -> append (bool)
  CSV_OPTION           -> quote_char (from TEXT_ENCLOSURE), quote_style
  TEXT_ENCLOSURE       -> quote_char (when CSV_OPTION=true)
  ESCAPE_CHAR          -> warning if differs from TEXT_ENCLOSURE (RFC4180)
  CSVROWSEPARATOR      -> line_terminator (CLOSED_LIST: LF/CR/CRLF; when CSV_OPTION=true)
  DELETE_EMPTYFILE     -> delete_empty_file (bool)
  FILE_EXIST_EXCEPTION -> error_if_exists (bool; Talend default true)
  ENCODING             -> warning if non-UTF-8 (Polars writes UTF-8 only)
  LABEL                -> label
  Schema               -> schema (column selection/ordering)
  COMPRESS             -> warning (UNSUPPORTED)
  SPLIT/SPLIT_EVERY    -> warning (UNSUPPORTED)
  ADVANCED_SEPARATOR   -> warning (UNSUPPORTED)
  USESTREAM            -> warning (NOT_PLANNED)
  FLUSHONROW           -> warning (NOT_PLANNED)
  ROW_MODE             -> warning (NOT_PLANNED)
  OS_LINE_SEPARATOR    -> warning (NOT_PLANNED)
  TSTATCATCHER_STATS   -> warning (NOT_PLANNED)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY
from .file_input_delimited_converter import convert_path_expression, _strip_talend_quotes

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

# Common Talend escape sequences -> actual characters
_ESCAPE_MAP = {"\\n": "\n", "\\r": "\r", "\\t": "\t"}

# CSVROWSEPARATOR CLOSED_LIST values -> actual characters
_CSVROWSEP_MAP = {"LF": "\n", "CR": "\r", "CRLF": "\r\n"}

# Valid UTF-8 encoding variants (case-insensitive comparison via lower+strip)
_UTF8_VARIANTS = frozenset({"utf8", "utf-8", "utf8-lossy"})

# UNSUPPORTED parameter warnings
_UNSUPPORTED_PARAMS = {
    "COMPRESS": (
        "COMPRESS is UNSUPPORTED in v2. Polars cannot write ZIP-compressed CSV. "
        "Use gzip post-processing or downstream compression tooling."
    ),
    "SPLIT": (
        "SPLIT is UNSUPPORTED in v2. Polars has no native file splitting. "
        "Split files post-processing or use downstream tooling."
    ),
    "SPLIT_EVERY": "SPLIT_EVERY is UNSUPPORTED in v2.",
    "ADVANCED_SEPARATOR": (
        "ADVANCED_SEPARATOR is UNSUPPORTED in v2. "
        "Polars has decimal_comma on write but no thousands_separator."
    ),
    "THOUSANDS_SEPARATOR": "THOUSANDS_SEPARATOR is UNSUPPORTED in v2.",
    "DECIMAL_SEPARATOR": "DECIMAL_SEPARATOR is UNSUPPORTED in v2.",
}

# NOT_PLANNED parameter warnings
_NOT_PLANNED_PARAMS = {
    "USESTREAM": (
        "USESTREAM is NOT_PLANNED -- Java OutputStream sink has no Python equivalent."
    ),
    "STREAMNAME": "STREAMNAME is NOT_PLANNED.",
    "FLUSHONROW": (
        "FLUSHONROW is NOT_PLANNED -- Polars manages write buffering internally."
    ),
    "FLUSHONROW_NUM": "FLUSHONROW_NUM is NOT_PLANNED.",
    "ROW_MODE": (
        "ROW_MODE is NOT_PLANNED -- Polars manages write buffering internally."
    ),
    "OS_LINE_SEPARATOR_AS_ROW_SEPARATOR": (
        "OS_LINE_SEPARATOR_AS_ROW_SEPARATOR is NOT_PLANNED -- "
        "v2 uses explicit line_terminator config."
    ),
    "TSTATCATCHER_STATS": "TSTATCATCHER_STATS is NOT_PLANNED -- use Python logging.",
}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _resolve_escape_sequences(value: str) -> str:
    """Resolve Talend escape sequences to actual characters.

    Handles multi-character escape sequences like ``\\r\\n`` by iterating
    through ``_ESCAPE_MAP`` and replacing all occurrences.
    """
    result = value
    for seq, char in _ESCAPE_MAP.items():
        result = result.replace(seq, char)
    return result


def _to_bool(value: Any) -> bool:
    """Convert a Talend parameter value to a Python bool."""
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


# ------------------------------------------------------------------
# Converter
# ------------------------------------------------------------------

@REGISTRY.register("tFileOutputDelimited")
class FileOutputDelimitedConverter(ComponentConverter):
    """Converts tFileOutputDelimited to v2 FileOutputDelimited.

    Covers all Talend parameters with v2 config mapping,
    UNSUPPORTED/NOT_PLANNED warnings, and encoding advice.
    """

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        """Convert a tFileOutputDelimited node into a v2 component dict."""
        params = node.params
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []
        config: Dict[str, Any] = {}

        # ---- 1. Path (D-05) ----
        config["path"] = convert_path_expression(params.get("FILENAME", ""))

        # ---- 2. Delimiter (D-06) ----
        separator = params.get("FIELDSEPARATOR", ";")
        separator = _strip_talend_quotes(separator)
        # Resolve escape sequences (e.g., "\\t" -> "\t")
        separator = _resolve_escape_sequences(separator)
        if len(separator) > 1:
            warnings.append(
                f"{node.component_id}: Multi-char FIELDSEPARATOR is UNSUPPORTED in v2 "
                f"(Polars requires single-byte). Got: '{separator}'"
            )
        config["delimiter"] = separator

        # ---- 3. Row separator (D-07) ----
        rowsep = params.get("ROWSEPARATOR", "\\n")
        rowsep = _strip_talend_quotes(rowsep)
        # Resolve escape sequences to actual characters
        config["line_terminator"] = _resolve_escape_sequences(rowsep)

        # ---- 4. Include header (D-09; Talend default false) ----
        if "INCLUDEHEADER" in params:
            config["has_header"] = _to_bool(params["INCLUDEHEADER"])
        else:
            config["has_header"] = False  # Talend default

        # ---- 5. Append (D-08) ----
        if "APPEND" in params:
            config["append"] = _to_bool(params["APPEND"])

        # ---- 6. CSV_OPTION + TEXT_ENCLOSURE + ESCAPE_CHAR (D-11, D-19) ----
        csv_option = _to_bool(params.get("CSV_OPTION", False))

        if csv_option:
            text_enclosure = _strip_talend_quotes(params.get("TEXT_ENCLOSURE", '"'))
            config["quote_char"] = text_enclosure
            config["quote_style"] = "always"

            # ESCAPE_CHAR warning (D-19)
            escape_char = _strip_talend_quotes(params.get("ESCAPE_CHAR", '"'))
            if escape_char != text_enclosure:
                warnings.append(
                    f"{node.component_id}: ESCAPE_CHAR ('{escape_char}') differs from "
                    f"TEXT_ENCLOSURE ('{text_enclosure}') -- "
                    f"Polars uses RFC4180 quote doubling. Custom escape characters "
                    f"are not supported."
                )

            # CSVROWSEPARATOR (D-14) -- overrides ROWSEPARATOR when CSV_OPTION=true
            csvrowsep = params.get("CSVROWSEPARATOR")
            if csvrowsep:
                stripped_csv = _strip_talend_quotes(csvrowsep)
                mapped = _CSVROWSEP_MAP.get(stripped_csv)
                if mapped is not None:
                    config["line_terminator"] = mapped
                else:
                    # Not a CLOSED_LIST value, resolve escape sequences
                    config["line_terminator"] = _resolve_escape_sequences(stripped_csv)

        # ---- 7. DELETE_EMPTYFILE (D-12) ----
        if "DELETE_EMPTYFILE" in params:
            config["delete_empty_file"] = _to_bool(params["DELETE_EMPTYFILE"])

        # ---- 8. FILE_EXIST_EXCEPTION (D-13; Talend default true) ----
        if "FILE_EXIST_EXCEPTION" in params:
            config["error_if_exists"] = _to_bool(params["FILE_EXIST_EXCEPTION"])
        else:
            config["error_if_exists"] = True  # Talend default

        # ---- 9. ENCODING (D-01, D-23) ----
        encoding = _strip_talend_quotes(params.get("ENCODING", "UTF-8"))
        if encoding.lower().replace("-", "") not in ("utf8", "utf8lossy"):
            warnings.append(
                f"ENCODING '{encoding}' is UNSUPPORTED in v2. "
                f"Polars writes UTF-8 only. Use downstream transcoding if "
                f"{encoding} or other encoding is required."
            )

        # ---- 10. Label (D-15) ----
        label = params.get("LABEL")
        if label:
            config["label"] = _strip_talend_quotes(label)

        # ---- 11. Schema (D-16) ----
        flow_schema = node.schema.get("FLOW", [])
        if flow_schema:
            from ...type_mapping import convert_schema
            config["schema"] = convert_schema(flow_schema)

        # ---- 12. UNSUPPORTED params (D-20 through D-22) ----
        for param_name, msg in _UNSUPPORTED_PARAMS.items():
            raw_val = params.get(param_name)
            if raw_val is not None:
                is_active = raw_val
                if isinstance(is_active, str):
                    is_active = is_active.lower() not in ("false", "0", "")
                if is_active:
                    warnings.append(f"{node.component_id}: {msg}")

        # ---- 13. NOT_PLANNED params (D-24 through D-28) ----
        for param_name, msg in _NOT_PLANNED_PARAMS.items():
            raw_val = params.get(param_name)
            if raw_val is not None:
                is_active = raw_val
                if isinstance(is_active, str):
                    is_active = is_active.lower() not in ("false", "0", "")
                if is_active:
                    warnings.append(f"{node.component_id}: {msg}")

        # ---- 14. Build component + flows ----
        component = {
            "id": node.component_id,
            "type": "file_output_delimited",
            "config": config,
        }
        flows = self._build_simple_flows(node, connections)
        return ComponentResult(
            component=component,
            flows=flows,
            warnings=warnings,
            needs_review=needs_review,
        )
