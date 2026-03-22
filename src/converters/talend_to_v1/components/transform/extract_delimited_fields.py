"""Converter for Talend tExtractDelimitedFields -> v1 ExtractDelimitedFields.

tExtractDelimitedFields splits a single input field into multiple output columns
using configurable field and row separators.  It supports advanced separator
options (thousands / decimal) and optional trimming / empty-row removal.

Fixes vs. old code (CONV-EDF-001 to EDF-006):
  - CONV-EDF-001: Self-contained converter — no dual-parser conflict between
    the dedicated parser (component_parser.py:1973) and the generic
    _map_component_parameters (component_parser.py:294).
  - CONV-EDF-002: Correct default for FIELDSEPARATOR (';') and proper quote
    stripping.
  - CONV-EDF-003: row_separator, trim_all, remove_empty_row properly extracted
    (previously missing or defaulted incorrectly).
  - CONV-EDF-004: advanced_separator is a bool, not a string.
  - CONV-EDF-005: Schema passthrough (input == output) instead of empty schema.
  - CONV-EDF-006: die_on_error extracted as bool.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tExtractDelimitedFields")
class ExtractDelimitedFieldsConverter(ComponentConverter):
    """Convert a Talend tExtractDelimitedFields node to v1 ExtractDelimitedFields."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Extract parameters
        # ------------------------------------------------------------------
        field_separator = self._get_str(node, "FIELDSEPARATOR", ";")
        row_separator = self._get_str(node, "ROWSEPARATOR", "\\n")
        advanced_separator = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        thousands_separator = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        decimal_separator = self._get_str(node, "DECIMAL_SEPARATOR", ".")
        trim_all = self._get_bool(node, "TRIMALL", False)
        remove_empty_row = self._get_bool(node, "REMOVE_EMPTY_ROW", False)
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", False)

        # ------------------------------------------------------------------
        # Validation warnings
        # ------------------------------------------------------------------
        if not field_separator:
            warnings.append(
                "FIELDSEPARATOR is empty — extraction may not split correctly"
            )

        # ------------------------------------------------------------------
        # Build config
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "field_separator": field_separator,
            "row_separator": row_separator,
            "advanced_separator": advanced_separator,
            "thousands_separator": thousands_separator,
            "decimal_separator": decimal_separator,
            "trim_all": trim_all,
            "remove_empty_row": remove_empty_row,
            "die_on_error": die_on_error,
        }

        # ------------------------------------------------------------------
        # Schema: transform component passes schema through
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="ExtractDelimitedFields",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)
