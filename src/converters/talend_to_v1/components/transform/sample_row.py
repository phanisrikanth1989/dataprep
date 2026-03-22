"""Converter for Talend tSampleRow component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tSampleRow")
class SampleRowConverter(ComponentConverter):
    """Convert a Talend tSampleRow node into a v1 SampleRow component.

    tSampleRow samples a subset of rows from its input based on a configured
    range expression.  Parameters:

    * ``RANGE`` -- the row-range expression (e.g. ``"1..100"``).
    * ``CONNECTION_FORMAT`` -- connection format, defaults to ``"row"``.

    Schema is a passthrough: input equals output from FLOW.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        range_config = self._get_str(node, "RANGE", "")
        connection_format = self._get_str(node, "CONNECTION_FORMAT", "row")

        if not range_config:
            warnings.append("RANGE parameter is empty or missing")

        config: Dict[str, Any] = {
            "range": range_config,
            "connection_format": connection_format,
        }

        schema_cols = self._parse_schema(node)

        component = self._build_component_dict(
            node=node,
            type_name="SampleRow",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
