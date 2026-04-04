"""Converter for Talend tExtractPositionalFields component.

tExtractPositionalFields extracts columns from a fixed-width (positional) input
field using a pattern that describes the column widths.  It supports optional
trimming, advanced numeric separators, die-on-error behaviour, and a FORMATS
TABLE that specifies per-column formatting (column, size, padding_char, align).

Config mapping (11 unique params + 2 framework = 13 total):
  FIELD                -> field (str, PREV_COLUMN_LIST, default "")
  IGNORE_SOURCE_NULL   -> ignore_source_null (bool, default True)
  ADVANCED_OPTION      -> advanced_option (bool, default False)
  PATTERN              -> pattern (str, default "5,4,5")
  FORMATS TABLE        -> formats (list, stride-4: COLUMN+SIZE+PADDING_CHAR+ALIGN)
  DIE_ON_ERROR         -> die_on_error (bool, default False)
  ADVANCED_SEPARATOR   -> advanced_separator (bool, default False)
  THOUSANDS_SEPARATOR  -> thousands_separator (str, default ",")
  DECIMAL_SEPARATOR    -> decimal_separator (str, default ".")
  TRIM                 -> trim (bool, default False)
  CHECK_FIELDS_NUM     -> check_fields_num (bool, default False)
  TSTATCATCHER_STATS   -> tstatcatcher_stats (bool, framework)
  LABEL                -> label (str, framework)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# FORMATS TABLE constants (stride-4)
# ------------------------------------------------------------------
_FORMATS_FIELDS = ("COLUMN", "SIZE", "PADDING_CHAR", "ALIGN")
_FORMATS_GROUP_SIZE = len(_FORMATS_FIELDS)
_ALIGN_MAP = {"-1": "left", "0": "center", "1": "right"}


# ------------------------------------------------------------------
# FORMATS TABLE parser (module-level, prefixed with underscore)
# ------------------------------------------------------------------
def _parse_formats(raw: Any) -> List[Dict[str, str]]:
    """Parse FORMATS TABLE into list of per-column format dicts.

    Each group of 4 consecutive elementRef entries maps to one row:
      COLUMN       -> column (str)
      SIZE         -> size (str)
      PADDING_CHAR -> padding_char (str, quotes stripped)
      ALIGN        -> align (str, mapped: -1=left, 0=center, 1=right)

    Incomplete trailing groups (< 4 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    formats: List[Dict[str, str]] = []
    for i in range(0, len(raw), _FORMATS_GROUP_SIZE):
        group = raw[i : i + _FORMATS_GROUP_SIZE]
        if len(group) < _FORMATS_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "COLUMN":
                row["column"] = val
            elif ref == "SIZE":
                row["size"] = val
            elif ref == "PADDING_CHAR":
                row["padding_char"] = val.strip("'\"")
            elif ref == "ALIGN":
                row["align"] = _ALIGN_MAP.get(val, "left")
        if row.get("column"):
            formats.append(row)
    return formats


@REGISTRY.register("tExtractPositionalFields")
class ExtractPositionalFieldsConverter(ComponentConverter):
    """Convert a Talend tExtractPositionalFields node to v1 ExtractPositionalFields."""

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
        config["field"] = self._get_str(node, "FIELD", "")
        config["ignore_source_null"] = self._get_bool(node, "IGNORE_SOURCE_NULL", True)
        config["advanced_option"] = self._get_bool(node, "ADVANCED_OPTION", False)
        config["pattern"] = self._get_str(node, "PATTERN", "5,4,5")
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)

        # ---- 2. TABLE parameters ----
        config["formats"] = _parse_formats(node.params.get("FORMATS"))

        # ---- 3. Advanced settings ----
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")
        config["trim"] = self._get_bool(node, "TRIM", False)
        config["check_fields_num"] = self._get_bool(node, "CHECK_FIELDS_NUM", False)

        # ---- 4. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 5. Validation warnings ----
        if not config["pattern"]:
            warnings.append("PATTERN is empty -- positional extraction will have no effect")

        # ---- 6. Schema: transform passthrough (input == output) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 7. Engine gap needs_review entries ----
        # Pattern default mismatch: engine default is '' but Talend default is '5,4,5'
        needs_review.append({
            "issue": "Engine default pattern='' but Talend default is '5,4,5' -- semantic mismatch",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # Engine reads: pattern, die_on_error, trim, advanced_separator,
        # thousands_separator, decimal_separator (validated in _validate_config).
        # These 5 keys are not read by the engine at all:
        _engine_gap_keys = [
            "field", "ignore_source_null", "advanced_option", "formats",
            "check_fields_num",
        ]
        for key in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' from config",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="ExtractPositionalFields",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
