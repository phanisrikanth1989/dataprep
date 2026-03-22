"""Converter for Talend tForeach component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tForeach")
class ForeachConverter(ComponentConverter):
    """Convert a Talend tForeach node into a v1 Foreach component.

    The VALUES TABLE param contains flat {elementRef, value} entries.
    Each entry with elementRef='value' provides one iteration value.
    CONNECTION_FORMAT is a simple string parameter (e.g. 'row').
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Parse VALUES table
        # ------------------------------------------------------------------
        values: List[str] = []
        raw_values = self._get_param(node, "VALUES", [])

        if isinstance(raw_values, list):
            for entry in raw_values:
                if not isinstance(entry, dict):
                    continue
                # Only collect entries with elementRef="value" (skip metadata entries)
                ref = entry.get("elementRef", "")
                if ref and ref.lower() != "value":
                    continue
                val = entry.get("value", "")
                if isinstance(val, str):
                    val = val.strip('"')
                values.append(val)
        else:
            warnings.append(
                "VALUES param is not a list — expected TABLE structure"
            )

        if not values:
            warnings.append(
                "No iteration values defined — Foreach will have nothing to iterate"
            )

        # ------------------------------------------------------------------
        # CONNECTION_FORMAT
        # ------------------------------------------------------------------
        connection_format = self._get_str(node, "CONNECTION_FORMAT", default="row")

        config: Dict[str, Any] = {
            "values": values,
            "connection_format": connection_format,
        }

        # ------------------------------------------------------------------
        # Schema: utility/iterate component — no data flow schema
        # ------------------------------------------------------------------
        component = self._build_component_dict(
            node=node,
            type_name="Foreach",
            config=config,
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
