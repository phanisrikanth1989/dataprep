"""Converter for tFlowToIterate -> FlowToIterate."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFlowToIterate")
class FlowToIterateConverter(ComponentConverter):
    """Convert a Talend tFlowToIterate node to v1 FlowToIterate.

    Config params
    -------------
    DEFAULT_MAP (CHECK -> bool)
        When True, all input columns are automatically mapped to
        globalMap variables.  When False, only explicit MAP entries
        are used.
    CONNECTION_FORMAT (TEXT -> str)
        The connection format string (typically ``"row"``).
    MAP (TABLE -> list of {elementRef, value} dicts)
        Explicit column-to-variable mappings used when DEFAULT_MAP
        is False.  Entries arrive as flat interleaved
        ``SCHEMA_COLUMN`` / ``COLUMN`` pairs.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # DEFAULT_MAP is stored as a bool by the XML parser (CHECK field)
        default_map = self._get_bool(node, "DEFAULT_MAP", True)
        connection_format = self._get_str(node, "CONNECTION_FORMAT", "row")

        # Parse explicit MAP table entries (used when default_map is False).
        # Each mapping is a SCHEMA_COLUMN / COLUMN pair in the flat list.
        map_entries = self._parse_map_entries(
            self._get_param(node, "MAP", []), warnings
        )

        if not default_map and not map_entries:
            warnings.append(
                "DEFAULT_MAP is false but no explicit MAP entries defined "
                "-- no columns will be mapped to globalMap variables"
            )

        config: Dict[str, Any] = {
            "default_map": default_map,
            "connection_format": connection_format,
            "map_entries": map_entries,
        }

        schema_cols = self._parse_schema(node)
        component = self._build_component_dict(
            node=node,
            type_name="FlowToIterate",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)

    # ------------------------------------------------------------------
    # MAP table helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_map_entries(
        raw_map: Any, warnings: List[str]
    ) -> List[Dict[str, str]]:
        """Parse the MAP TABLE param into a list of mapping dicts.

        The MAP table contains flat interleaved ``SCHEMA_COLUMN`` and
        ``COLUMN`` elementValue entries.  Each pair produces a dict
        ``{"schema_column": ..., "column": ...}``.
        """
        if not isinstance(raw_map, list):
            if raw_map is not None and raw_map != []:
                warnings.append(
                    "MAP param is not a list -- expected TABLE structure"
                )
            return []

        entries: List[Dict[str, str]] = []
        current_schema_col: str | None = None

        for item in raw_map:
            ref = item.get("elementRef", "")
            val = item.get("value", "").strip('"')

            if ref == "SCHEMA_COLUMN":
                if current_schema_col is not None:
                    warnings.append(
                        f"SCHEMA_COLUMN '{current_schema_col}' has no "
                        f"matching COLUMN -- skipped"
                    )
                current_schema_col = val
            elif ref == "COLUMN":
                if current_schema_col is not None:
                    entries.append({
                        "schema_column": current_schema_col,
                        "column": val,
                    })
                    current_schema_col = None
                else:
                    warnings.append(
                        f"COLUMN '{val}' has no preceding "
                        f"SCHEMA_COLUMN -- skipped"
                    )

        # Handle trailing SCHEMA_COLUMN without a COLUMN
        if current_schema_col is not None:
            warnings.append(
                f"SCHEMA_COLUMN '{current_schema_col}' has no "
                f"matching COLUMN -- skipped"
            )

        return entries
