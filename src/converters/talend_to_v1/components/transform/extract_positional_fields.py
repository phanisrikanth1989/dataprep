"""Converter for Talend tExtractPositionalFields -> v1 ExtractPositionalFields.

tExtractPositionalFields extracts columns from a fixed-width (positional) input
field using a pattern that describes the column widths.  It supports optional
trimming, advanced numeric separators, and die-on-error behaviour.

Config mapping:
  PATTERN              -> pattern (str)
  DIE_ON_ERROR         -> die_on_error (bool)
  TRIM                 -> trim (bool)
  ADVANCED_SEPARATOR   -> advanced_separator (bool)
  THOUSANDS_SEPARATOR  -> thousands_separator (str)
  DECIMAL_SEPARATOR    -> decimal_separator (str)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


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

        # ------------------------------------------------------------------
        # Extract parameters
        # ------------------------------------------------------------------
        pattern = self._get_str(node, "PATTERN", "")
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", False)
        trim = self._get_bool(node, "TRIM", False)
        advanced_separator = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        thousands_separator = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        decimal_separator = self._get_str(node, "DECIMAL_SEPARATOR", ".")

        # ------------------------------------------------------------------
        # Validation warnings
        # ------------------------------------------------------------------
        if not pattern:
            warnings.append(
                "PATTERN is empty — positional extraction will have no effect"
            )

        # ------------------------------------------------------------------
        # Build config
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "pattern": pattern,
            "die_on_error": die_on_error,
            "trim": trim,
            "advanced_separator": advanced_separator,
            "thousands_separator": thousands_separator,
            "decimal_separator": decimal_separator,
        }

        # ------------------------------------------------------------------
        # Schema: transform component passes schema through
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="ExtractPositionalFields",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)
