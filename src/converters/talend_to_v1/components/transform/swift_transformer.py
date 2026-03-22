"""Converter for Talend tSwiftDataTransformer component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tSwiftDataTransformer")
class SwiftTransformerConverter(ComponentConverter):
    """Convert a Talend tSwiftDataTransformer node into a v1 SwiftTransformer component.

    The old complex_converter mapped this to 'TSwiftDataTransformer' which was
    incorrect (CONV-NAME-004). The v1 engine class is ``SwiftTransformer``
    (see ``src/v1/engine/components/transform/swift_transformer.py``).

    tSwiftDataTransformer had no dedicated parser in the old converter -- it
    relied on generic fallback logic.  This converter extracts commonly seen
    parameters from ``node.params`` and builds the standard v1 component dict.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ---- config --------------------------------------------------------
        connection_format = self._get_str(node, "CONNECTION_FORMAT", "row")

        config: Dict[str, Any] = {
            "connection_format": connection_format,
        }

        # Forward any extra known params when present
        config_file = self._get_str(node, "CONFIG_FILE", "")
        if config_file:
            config["config_file"] = config_file

        die_on_error = self._get_bool(node, "DIE_ON_ERROR", True)
        config["die_on_error"] = die_on_error

        # ---- schema --------------------------------------------------------
        schema_cols = self._parse_schema(node)

        schema: Dict[str, Any] = {
            "input": schema_cols,
            "output": schema_cols,
        }

        # ---- assemble ------------------------------------------------------
        component = self._build_component_dict(
            node=node,
            type_name="SwiftTransformer",
            config=config,
            schema=schema,
        )

        return ComponentResult(component=component, warnings=warnings)
