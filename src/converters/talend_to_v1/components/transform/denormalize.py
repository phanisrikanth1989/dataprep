"""Converter for Talend tDenormalize -> v1 Denormalize component.

tDenormalize merges multiple rows into a single row by concatenating values
from specified columns using delimiters.  The DENORMALIZE_COLUMNS table
parameter contains flat {elementRef, value} entries grouped in triplets:
INPUT_COLUMN, DELIMITER, MERGE.

Fixes vs. old code (CONV-DNR-001 to DNR-004):
  - CONV-DNR-001: Dedicated converter instead of generic fallback.
  - CONV-DNR-002: Old code defaulted merge=True; Talend defaults to false.
  - CONV-DNR-003: Proper schema passthrough (input == output).
  - CONV-DNR-004: Robust DENORMALIZE_COLUMNS table parsing with warnings
    for malformed entries.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tDenormalize")
class DenormalizeConverter(ComponentConverter):
    """Convert a Talend tDenormalize node into a v1 Denormalize component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Simple parameters
        # ------------------------------------------------------------------
        null_as_empty = self._get_bool(node, "NULL_AS_EMPTY", default=False)
        connection_format = self._get_str(
            node, "CONNECTION_FORMAT", default="row",
        )

        # ------------------------------------------------------------------
        # Parse DENORMALIZE_COLUMNS table
        # ------------------------------------------------------------------
        denormalize_columns = self._parse_denormalize_columns(node, warnings)

        if not denormalize_columns:
            warnings.append(
                "No denormalize columns defined — component will have no effect"
            )

        # ------------------------------------------------------------------
        # Build config
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "null_as_empty": null_as_empty,
            "connection_format": connection_format,
            "denormalize_columns": denormalize_columns,
        }

        # ------------------------------------------------------------------
        # Schema: transform component passes schema through
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="Denormalize",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)

    # ------------------------------------------------------------------
    # DENORMALIZE_COLUMNS table parser
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_denormalize_columns(
        node: TalendNode,
        warnings: List[str],
    ) -> List[Dict[str, Any]]:
        """Parse the DENORMALIZE_COLUMNS table parameter.

        The table is stored as a flat list of {elementRef, value} dicts
        grouped in triplets: INPUT_COLUMN, DELIMITER, MERGE.

        CONV-DNR-002: merge defaults to False (Talend's actual default),
        correcting the old code which defaulted to True.
        """
        raw = node.params.get("DENORMALIZE_COLUMNS", [])
        if not isinstance(raw, list):
            warnings.append(
                "DENORMALIZE_COLUMNS param is not a list "
                "— expected TABLE structure"
            )
            return []

        result: List[Dict[str, Any]] = []

        # Group entries into triplets
        for i in range(0, len(raw), 3):
            triplet = raw[i: i + 3]

            # Build a lookup from the triplet entries
            row_data: Dict[str, Any] = {}
            for entry in triplet:
                ref = entry.get("elementRef", "")
                val = entry.get("value", "")

                if ref == "INPUT_COLUMN":
                    row_data["input_column"] = val.strip('"')
                elif ref == "DELIMITER":
                    # Strip surrounding quotes (plain or XML-encoded)
                    if val.startswith("&quot;") and val.endswith("&quot;"):
                        val = val[6:-6]
                    elif val.startswith('"') and val.endswith('"') and len(val) >= 2:
                        val = val[1:-1]
                    row_data["delimiter"] = val
                elif ref == "MERGE":
                    row_data["merge"] = val.lower() == "true"

            # Validate: require input_column at minimum
            input_col = row_data.get("input_column", "")
            if not input_col:
                if triplet:
                    warnings.append(
                        f"DENORMALIZE_COLUMNS triplet at index {i} has no "
                        "INPUT_COLUMN — skipped"
                    )
                continue

            result.append({
                "input_column": input_col,
                "delimiter": row_data.get("delimiter", ","),
                "merge": row_data.get("merge", False),  # DNR-002: default False
            })

        return result
