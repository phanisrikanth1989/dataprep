"""Converter for Talend tUniqueRow / tUniqRow / tUnqRow components."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tUniqueRow", "tUniqRow", "tUnqRow")
class UniqueRowConverter(ComponentConverter):
    """Convert a Talend tUniqueRow node into a v1 UniqueRow component.

    The UNIQUE_KEY TABLE param contains flat {elementRef, value} entries
    grouped by 3: SCHEMA_COLUMN, KEY_ATTRIBUTE, CASE_SENSITIVE.  Only
    entries where KEY_ATTRIBUTE is ``"true"`` are included as key columns.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Parse UNIQUE_KEY table
        # ------------------------------------------------------------------
        key_columns: List[str] = []
        raw_unique_key = self._get_param(node, "UNIQUE_KEY", [])

        if isinstance(raw_unique_key, list):
            # Entries are grouped in triples:
            #   SCHEMA_COLUMN, KEY_ATTRIBUTE, CASE_SENSITIVE
            for i in range(0, len(raw_unique_key), 3):
                group = raw_unique_key[i : i + 3]
                if len(group) < 3:
                    warnings.append(
                        f"Incomplete UNIQUE_KEY group at index {i} "
                        f"— expected 3 entries, got {len(group)}"
                    )
                    continue

                schema_col_entry = group[0]
                key_attr_entry = group[1]

                if (
                    schema_col_entry.get("elementRef") == "SCHEMA_COLUMN"
                    and key_attr_entry.get("elementRef") == "KEY_ATTRIBUTE"
                    and key_attr_entry.get("value", "false").lower() == "true"
                ):
                    col_name = schema_col_entry.get("value", "").strip('"')
                    if col_name:
                        key_columns.append(col_name)
        else:
            warnings.append(
                "UNIQUE_KEY param is not a list — expected TABLE structure"
            )

        if not key_columns:
            warnings.append(
                "No key columns defined — component cannot determine uniqueness"
            )

        # ------------------------------------------------------------------
        # Other parameters
        # ------------------------------------------------------------------
        only_once = self._get_bool(
            node, "ONLY_ONCE_EACH_DUPLICATED_KEY", default=False
        )
        keep = "last" if only_once else "first"

        connection_format = self._get_str(
            node, "CONNECTION_FORMAT", default="row"
        )

        config: Dict[str, Any] = {
            "key_columns": key_columns,
            "keep": keep,
            "connection_format": connection_format,
        }

        # ------------------------------------------------------------------
        # Schema: transform — input == output
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="UniqueRow",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)
