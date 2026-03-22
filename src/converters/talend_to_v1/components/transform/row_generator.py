"""Converter for tRowGenerator -> RowGenerator.

tRowGenerator is a source component that produces rows based on configured
column expressions.  Key parameters:

* ``NB_ROWS`` -- number of rows to generate (int, defaults to ``1``).
* ``VALUES``  -- TABLE parameter containing interleaved SCHEMA_COLUMN / ARRAY
  elementValue entries.  Each pair maps a schema column name to the expression
  used to generate its value.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tRowGenerator")
class RowGeneratorConverter(ComponentConverter):
    """Convert a Talend tRowGenerator node into a v1 RowGenerator component."""

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
        nb_rows = self._get_int(node, "NB_ROWS", default=1)

        # ------------------------------------------------------------------
        # Parse VALUES table (interleaved SCHEMA_COLUMN / ARRAY pairs)
        # ------------------------------------------------------------------
        values: List[Dict[str, str]] = []
        raw_values = self._get_param(node, "VALUES", [])

        if isinstance(raw_values, list):
            current_column: str | None = None
            for entry in raw_values:
                ref = entry.get("elementRef", "")
                val = entry.get("value", "").strip('"')
                if ref == "SCHEMA_COLUMN":
                    # If we already had a SCHEMA_COLUMN without an ARRAY,
                    # emit a warning and skip the orphaned column.
                    if current_column is not None:
                        warnings.append(
                            f"SCHEMA_COLUMN '{current_column}' has no matching "
                            "ARRAY — skipped"
                        )
                    current_column = val
                elif ref == "ARRAY":
                    if current_column is not None:
                        values.append({
                            "schema_column": current_column,
                            "array": val,
                        })
                        current_column = None
                    else:
                        warnings.append(
                            f"ARRAY '{val}' has no preceding "
                            "SCHEMA_COLUMN — skipped"
                        )

            # Handle trailing SCHEMA_COLUMN with no ARRAY
            if current_column is not None:
                warnings.append(
                    f"SCHEMA_COLUMN '{current_column}' has no matching "
                    "ARRAY — skipped"
                )
        else:
            warnings.append(
                "VALUES param is not a list — expected TABLE structure"
            )

        # ------------------------------------------------------------------
        # Build config
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "nb_rows": nb_rows,
            "values": values,
        }

        # ------------------------------------------------------------------
        # Schema: source component — no input, output from FLOW metadata
        # ------------------------------------------------------------------
        output_schema = self._parse_schema(node)
        schema = {"input": [], "output": output_schema}

        component = self._build_component_dict(
            node=node,
            type_name="RowGenerator",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)
