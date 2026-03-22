"""Converter for Talend tUnpivotRow component.

Fixes CONV-UPV-001: removes hardcoded business-specific column names that
were used as fallback defaults in the old ``parse_unpivot_row``.
Fixes CONV-UPV-002: uses ``_get_str()`` helper instead of ``node.get()``.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tUnpivotRow")
class UnpivotRowConverter(ComponentConverter):
    """Convert a Talend tUnpivotRow node into a v1 UnpivotRow component.

    The ROW_KEYS TABLE param contains elementValue entries with
    elementRef='COLUMN' whose values identify the key columns to preserve
    during the unpivot operation.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Scalar parameters
        # ------------------------------------------------------------------
        pivot_column = self._get_str(node, "PIVOT_COLUMN", default="pivot_key")
        value_column = self._get_str(node, "VALUE_COLUMN", default="pivot_value")
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", default=False)

        # GROUP_BY_COLUMNS is a semicolon-separated string
        group_by_raw = self._get_str(node, "GROUP_BY_COLUMNS", default="")
        group_by_columns = [c for c in group_by_raw.split(";") if c]

        # ------------------------------------------------------------------
        # ROW_KEYS table parameter
        # ------------------------------------------------------------------
        row_keys: List[str] = []
        raw_row_keys = self._get_param(node, "ROW_KEYS", [])

        if isinstance(raw_row_keys, list):
            for entry in raw_row_keys:
                ref = entry.get("elementRef", "")
                val = entry.get("value", "").strip('"')
                if ref == "COLUMN" and val:
                    row_keys.append(val)
        else:
            warnings.append(
                "ROW_KEYS param is not a list — expected TABLE structure"
            )

        # NOTE: intentionally NO hardcoded fallback defaults for row_keys.
        # The old code fell back to business-specific column names; that is
        # removed per CONV-UPV-001.
        if not row_keys:
            warnings.append(
                "No row keys defined — unpivot may not preserve any key columns"
            )

        # ------------------------------------------------------------------
        # Build config
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "pivot_column": pivot_column,
            "value_column": value_column,
            "group_by_columns": group_by_columns,
            "row_keys": row_keys,
            "die_on_error": die_on_error,
        }

        # ------------------------------------------------------------------
        # Schema: transform — input and output are the same parsed schema
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="UnpivotRow",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)
