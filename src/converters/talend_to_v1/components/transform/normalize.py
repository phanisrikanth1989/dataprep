"""Converter for tNormalize -> Normalize."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tNormalize")
class NormalizeConverter(ComponentConverter):
    """Convert a Talend tNormalize node to v1 Normalize."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        normalize_column = self._get_str(node, "NORMALIZE_COLUMN")
        item_separator = self._get_str(node, "ITEMSEPARATOR", ";")
        deduplicate = self._get_bool(node, "DEDUPLICATE", False)
        trim = self._get_bool(node, "TRIM", False)
        discard_trailing_empty_str = self._get_bool(
            node, "DISCARD_TRAILING_EMPTY_STR", False
        )
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", False)

        if not normalize_column:
            warnings.append(
                "NORMALIZE_COLUMN is empty -- normalize will have no effect"
            )

        config: Dict[str, Any] = {
            "normalize_column": normalize_column,
            "item_separator": item_separator,
            "deduplicate": deduplicate,
            "trim": trim,
            "discard_trailing_empty_str": discard_trailing_empty_str,
            "die_on_error": die_on_error,
        }

        schema_cols = self._parse_schema(node)
        component = self._build_component_dict(
            node=node,
            type_name="Normalize",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
