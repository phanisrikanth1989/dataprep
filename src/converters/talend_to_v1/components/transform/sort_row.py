"""Converter for Talend tSortRow component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tSortRow")
class SortRowConverter(ComponentConverter):
    """Convert a Talend tSortRow node into a v1 SortRow component.

    The CRITERIA TABLE param contains interleaved COLNAME/SORT elementValue
    entries.  Each COLNAME/SORT pair defines one sort criterion (column name
    and sort direction).
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Parse CRITERIA table
        # ------------------------------------------------------------------
        sort_columns: List[str] = []
        sort_orders: List[str] = []
        raw_criteria = self._get_param(node, "CRITERIA", [])

        if isinstance(raw_criteria, list):
            current_colname: str | None = None
            for entry in raw_criteria:
                ref = entry.get("elementRef", "")
                val = entry.get("value", "").strip('"')
                if ref == "COLNAME":
                    # If we already had a COLNAME without a SORT, emit a warning
                    if current_colname is not None:
                        warnings.append(
                            f"COLNAME '{current_colname}' has no matching SORT "
                            "— defaulting to asc"
                        )
                        sort_columns.append(current_colname)
                        sort_orders.append("asc")
                    current_colname = val
                elif ref == "SORT":
                    if current_colname is not None:
                        sort_columns.append(current_colname)
                        sort_orders.append(val.lower() if val else "asc")
                        current_colname = None
                    else:
                        warnings.append(
                            f"SORT '{val}' has no preceding COLNAME — skipped"
                        )

            # Handle trailing COLNAME with no SORT
            if current_colname is not None:
                warnings.append(
                    f"COLNAME '{current_colname}' has no matching SORT "
                    "— defaulting to asc"
                )
                sort_columns.append(current_colname)
                sort_orders.append("asc")
        else:
            warnings.append(
                "CRITERIA param is not a list — expected TABLE structure"
            )

        if not sort_columns:
            warnings.append(
                "No sort criteria defined — component will pass data through unsorted"
            )

        # ------------------------------------------------------------------
        # Other parameters
        # ------------------------------------------------------------------
        external_sort = self._get_bool(node, "EXTERNAL_SORT", default=False)
        temp_file = self._get_str(node, "TEMPFILE", default="")

        config: Dict[str, Any] = {
            "sort_columns": sort_columns,
            "sort_orders": sort_orders,
            "external_sort": external_sort,
        }

        if temp_file:
            config["temp_file"] = temp_file

        # ------------------------------------------------------------------
        # Schema: transform component passes schema through
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="SortRow",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)
