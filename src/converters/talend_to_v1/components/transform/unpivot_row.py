"""Converter for Talend tUnpivotRow component.

Unpivots (melts) columns into rows, transforming wide data into long format.

Config mapping (4 unique params + framework):
  ROW_KEYS              -> row_keys              (list, TABLE stride-1 COLUMN, default [])
  (derived)             -> pivot_key             (str, engine-expected column name)
  (derived)             -> pivot_value           (str, engine-expected column name)
  INCLUDE_EMPTY_VALUES  -> include_empty_values  (bool, CHECK, default True)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Community component (michimau/talend_components). _java.xml 404. MEDIUM confidence.
Phantom params previously removed: PIVOT_COLUMN, VALUE_COLUMN, GROUP_BY_COLUMNS, DIE_ON_ERROR.
Engine reads all config params -- 0 needs_review entries.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tUnpivotRow")
class UnpivotRowConverter(ComponentConverter):
    """Convert Talend tUnpivotRow to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. ROW_KEYS TABLE parameter (stride-1, COLUMN elementRef) ----
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

        if not row_keys:
            warnings.append(
                "No row keys defined — unpivot may not preserve any key columns"
            )

        # ---- 2. Core parameters ----
        config: Dict[str, Any] = {
            "row_keys": row_keys,
            "pivot_key": "pivot_key",
            "pivot_value": "pivot_value",
            "include_empty_values": self._get_bool(node, "INCLUDE_EMPTY_VALUES", True),
        }

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL")

        # ---- 4. Schema: transform — passthrough ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 5. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="UnpivotRow",
            config=config,
            schema=schema,
        )

        # ---- 6. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
