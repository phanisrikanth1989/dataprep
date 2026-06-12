"""Engine component for FixedFlowInput (tFixedFlowInput).

Generates a fixed number of rows from static configuration -- no input
DataFrame required. Three mutually exclusive modes:

  Single mode    : VALUES template row repeated nb_rows times (use_singlemode=True)
  Inline Table   : INTABLE flat entry list grouped by schema columns (use_intable=True)
  Inline Content : free-text delimited block, all lines emitted (use_inlinecontent=True)

Config keys consumed:
  nb_rows           (int, default 1)         -- rows to generate (single / intable)
  use_singlemode    (bool, default True)      -- enable VALUES single-template mode
  use_intable       (bool, default False)     -- enable INTABLE multi-row mode
  use_inlinecontent (bool, default False)     -- enable free-text delimited mode
  values_config     (list[dict], default []) -- [{"schema_column": col, "value": val}, ...]
  intable           (list[dict], default []) -- flat [{element_ref: col, value: val}, ...]
  inline_content    (str, default "")        -- delimited text block
  row_separator     (str, default "\\\\n")   -- row separator (Java escapes supported)
  field_separator   (str, default ";")       -- field separator (Java escapes supported)
"""
import logging
import re
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Java escape sequences accepted in row_separator / field_separator config values.
# Order matters: longer / multi-token sequences first so a "\\r\\n" separator
# (4 literal chars: backslash-r-backslash-n) decodes correctly even though
# `_ESCAPE_MAP.get(...)` -- the prior implementation -- only matched single
# 2-char tokens. Single-key dict lookup cannot translate composites like
# "\\r\\n", "\\t\\n" or "\\\\n"; iterative replacement does.
_ESCAPE_MAP: dict[str, str] = {
    "\\n": "\n",
    "\\t": "\t",
    "\\r": "\r",
    "\\|": "|",
}


def _decode_separator(raw: str) -> str:
    """Translate Java-style escape tokens in a config separator string.

    Iteratively replaces every ``_ESCAPE_MAP`` token in ``raw`` so multi-token
    separators like ``"\\r\\n"`` decode to ``"\r\n"`` (CRLF), not the literal
    4-char string.

    Empty / non-string values are returned unchanged so callers can pass
    ``None``-like fallbacks safely.
    """
    if not isinstance(raw, str) or not raw:
        return raw
    out = raw
    for tok, real in _ESCAPE_MAP.items():
        if tok in out:
            out = out.replace(tok, real)
    return out


@REGISTRY.register("FixedFlowInputComponent", "tFixedFlowInput")
class FixedFlowInputComponent(BaseComponent):
    """tFixedFlowInput engine implementation.

    Generates fixed rows of data in single, inline-table, or inline-content
    mode and emits them as a single FLOW (main) output.  No REJECT output --
    all data is predefined so there is no concept of malformed input.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate structural correctness of config (Rule 12).

        Group B carve-out: ``nb_rows`` is always emitted as ``int`` by the
        converter via ``_get_int(node, "NB_ROWS", 1)``, so the isinstance
        check below is structural, not content-based.
        See MANUAL_COMPONENT_AUTHORING.md Rule 12.

        Raises:
            ConfigurationError: If ``nb_rows`` is present but not an int.
        """
        nb_rows = self.config.get("nb_rows")
        if nb_rows is not None and not isinstance(nb_rows, int):
            raise ConfigurationError(
                self.id,
                f"'nb_rows' must be an int, got {type(nb_rows).__name__}",
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict[str, Any]:
        """Generate fixed rows and return them as a DataFrame.

        Args:
            input_data: Not used -- this is a source component.

        Returns:
            dict with ``'main'`` key containing the generated DataFrame.

        Raises:
            ConfigurationError: If ``nb_rows`` is negative.
        """
        nb_rows: int = self.config.get("nb_rows", 1)
        if nb_rows < 0:
            raise ConfigurationError(self.id, f"'nb_rows' must be >= 0, got {nb_rows}")

        # Use output_schema set by the engine (schema is a sibling of config in
        # the component JSON, not nested inside config).  Fall back to
        # config["schema"] so existing unit-test fixtures continue to work.
        schema_cols = getattr(self, "output_schema", None) or self.config.get("schema", [])
        col_names = [c["name"] if isinstance(c, dict) else c for c in schema_cols]

        use_singlemode = self.config.get("use_singlemode", True)
        use_intable = self.config.get("use_intable", False)
        use_inlinecontent = self.config.get("use_inlinecontent", False)

        logger.info(
            "[%s] mode: single=%s intable=%s inlinecontent=%s nb_rows=%d",
            self.id, use_singlemode, use_intable, use_inlinecontent, nb_rows,
        )

        if use_inlinecontent:
            rows = self._build_inline_content_rows(col_names)
        elif use_intable:
            rows = self._build_intable_rows(nb_rows, col_names)
        elif use_singlemode:
            rows = self._build_single_mode_rows(nb_rows, col_names)
        else:
            logger.warning("[%s] no mode selected, defaulting to single", self.id)
            rows = self._build_single_mode_rows(nb_rows, col_names)

        row_count = len(rows)
        self._update_stats(row_count, row_count, 0)

        df = pd.DataFrame(rows, columns=col_names) if rows else pd.DataFrame(columns=col_names)
        logger.info("[%s] generated %d rows", self.id, row_count)
        return {"main": df}

    # ------------------------------------------------------------------
    # Mode builders
    # ------------------------------------------------------------------

    def _build_single_mode_rows(self, nb_rows: int, col_names: list[str]) -> list[dict]:
        """Build rows for single mode (VALUES template repeated nb_rows times).

        ``values_config`` is a list[dict] emitted by the converter::

            [{"schema_column": "id", "value": "1"},
             {"schema_column": "name", "value": "Alice"}]

        A plain dict ``{col: val}`` is also accepted for backward compatibility.
        """
        raw = self.config.get("values_config", [])

        if isinstance(raw, list):
            lookup: dict[str, Any] = {
                e["schema_column"]: e.get("value")
                for e in raw
                if isinstance(e, dict) and "schema_column" in e
            }
        elif isinstance(raw, dict):
            lookup = raw
        else:
            lookup = {}

        rows = []
        for _ in range(nb_rows):
            row = {col: self._resolve_value(lookup.get(col)) for col in col_names}
            rows.append(row)
        return rows

    def _build_intable_rows(self, nb_rows: int, col_names: list[str]) -> list[dict]:
        """Build rows for inline table mode (INTABLE).

        ``intable`` is the flat list emitted by the converter::

            [{"element_ref": "id",   "value": "1"},
             {"element_ref": "name", "value": "Alice"},
             {"element_ref": "id",   "value": "2"},
             {"element_ref": "name", "value": "Bob"}, ...]

        Every ``len(col_names)`` consecutive entries form one row.
        At rows defined in intable are emitted(nb_rows is ignored in this mode ); 
        no null-padding beyond actual data.
        """
        entries = self.config.get("intable", [])
        if not entries or not col_names:
            return []

        ncols = len(col_names)
        rows: list[dict] = []
        for start in range(0, len(entries), ncols):
            group = entries[start: start + ncols]
            row: dict[str, Any] = {col: None for col in col_names}
            for entry in group:
                if isinstance(entry, dict):
                    col = entry.get("element_ref", "")
                    if col in col_names:
                        row[col] = self._resolve_value(entry.get("value"))
            rows.append(row)
        return rows

    def _build_inline_content_rows(self, col_names: list[str]) -> list[dict]:
        """Build rows from inline content (delimited free-text block).

        ``nb_rows`` is ignored -- all non-empty lines from the content are emitted.
        Separator config values support Java escape sequences via ``_ESCAPE_MAP``.
        """
        content = self.config.get("inline_content", "")
        raw_row_sep = self.config.get("row_separator", "\\n")
        raw_field_sep = self.config.get("field_separator", ";")

        # Decode Java-style escape sequences in separators (e.g. "\\r\\n" -> "\r\n").
        # This allows users to specify common delimiters using familiar Java escape syntax.
        # The prior implementation only supported single 2-char tokens via dict lookup, so a composite like "\\r\\n" would not decode correctly.  Iterative replacement in _decode_separator handles multi-token strings properly.
        row_sep = _decode_separator(raw_row_sep)
        field_sep = _decode_separator(raw_field_sep)

        if not content:
            return []

        rows: list[dict] = []
        for line in content.split(row_sep):
            if not line.strip():
                continue
            fields = line.split(field_sep)
            row = {}
            for idx, col in enumerate(col_names):
                raw_val = fields[idx] if idx < len(fields) else None
                row[col] = self._resolve_value(raw_val)
            rows.append(row)
            logger.debug("[%s] parsed row: %s", self.id, row)
        return rows

    # ------------------------------------------------------------------
    # Value resolution
    # ------------------------------------------------------------------

    def _resolve_value(self, value: Any) -> Any:
        """Resolve a single cell value from config.

        Handles:
        - Non-string values: returned as-is.
        - ``${context.X}`` / ``context.X``: delegated to ContextManager.
        - ``globalMap.get("KEY")``: resolved via GlobalMap if available.
        - Numeric strings: coerced to int / float where unambiguous.

        No ``eval()`` is used -- arithmetic expressions are not supported.
        """
        if not isinstance(value, str):
            return value

        # ContextManager handles ${context.X} and context.X patterns
        try:
            resolved = self.context_manager.resolve_string(value) if self.context_manager else value
        except Exception:
            resolved = value

        if resolved != value:
            return _coerce_numeric(resolved)

        # globalMap.get("KEY") reference (runtime-only -- not resolvable earlier)
        if self.global_map and "globalMap.get" in value:
            match = re.search(r'globalMap\.get\("([^"]+)"\)', value)
            if match:
                gm_val = self.global_map.get(match.group(1))
                if gm_val is not None:
                    return gm_val

        return _coerce_numeric(value)


def _coerce_numeric(value: Any) -> Any:
    """Coerce a string to int or float if it represents a plain number.

    Uses regex to avoid any eval() risk.  Returns the original value unchanged
    if it does not match a plain integer or decimal pattern.
    """
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    if re.fullmatch(r"-?\d*\.\d+", stripped):
        return float(stripped)
    return value

