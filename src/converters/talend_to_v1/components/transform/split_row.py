"""Converter for Talend tSplitRow component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tSplitRow")
class SplitRowConverter(ComponentConverter):
    """Convert a Talend tSplitRow node into a v1 SplitRow component.

    The COL_MAPPING TABLE param contains interleaved SOURCE_COLUMN/TARGET_COLUMN
    elementValue entries.  Each SOURCE_COLUMN/TARGET_COLUMN pair defines one
    column mapping (source column to target column).

    CONNECTION_FORMAT is a scalar string (typically ``"row"``).
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Parse COL_MAPPING table
        # ------------------------------------------------------------------
        col_mapping: List[Dict[str, str]] = []
        raw_mapping = self._get_param(node, "COL_MAPPING", [])

        if isinstance(raw_mapping, list):
            current_source: str | None = None
            for entry in raw_mapping:
                ref = entry.get("elementRef", "")
                val = entry.get("value", "").strip('"')
                if ref == "SOURCE_COLUMN":
                    # If we already had a SOURCE_COLUMN without a TARGET_COLUMN,
                    # emit a warning and skip the orphaned source.
                    if current_source is not None:
                        warnings.append(
                            f"SOURCE_COLUMN '{current_source}' has no matching "
                            "TARGET_COLUMN — skipped"
                        )
                    current_source = val
                elif ref == "TARGET_COLUMN":
                    if current_source is not None:
                        if current_source and val:
                            col_mapping.append({
                                "source": current_source,
                                "target": val,
                            })
                        else:
                            warnings.append(
                                "Empty source or target in COL_MAPPING pair — skipped"
                            )
                        current_source = None
                    else:
                        warnings.append(
                            f"TARGET_COLUMN '{val}' has no preceding "
                            "SOURCE_COLUMN — skipped"
                        )

            # Handle trailing SOURCE_COLUMN with no TARGET_COLUMN
            if current_source is not None:
                warnings.append(
                    f"SOURCE_COLUMN '{current_source}' has no matching "
                    "TARGET_COLUMN — skipped"
                )
        else:
            warnings.append(
                "COL_MAPPING param is not a list — expected TABLE structure"
            )

        if not col_mapping:
            warnings.append(
                "No column mappings defined — component will have empty mapping"
            )

        # ------------------------------------------------------------------
        # Scalar parameters
        # ------------------------------------------------------------------
        connection_format = self._get_str(node, "CONNECTION_FORMAT", default="row")

        # ------------------------------------------------------------------
        # Build config
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "col_mapping": col_mapping,
            "connection_format": connection_format,
        }

        # ------------------------------------------------------------------
        # Schema: transform component — input and output are the same
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="SplitRow",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)
