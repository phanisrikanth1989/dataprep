"""Converter for tExtractRegexFields -> ExtractRegexFields."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tExtractRegexFields")
class ExtractRegexFieldsConverter(ComponentConverter):
    """Convert a Talend tExtractRegexFields node to v1 ExtractRegexFields."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        regex = self._get_str(node, "REGEX")
        group = self._get_int(node, "GROUP", 0)
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", False)

        if not regex:
            warnings.append(
                "REGEX is empty -- extract regex fields will have no effect"
            )

        config: Dict[str, Any] = {
            "regex": regex,
            "group": group,
            "die_on_error": die_on_error,
        }

        # Build schema: input and output from FLOW metadata (shared reference)
        schema_cols = self._parse_schema(node)
        schema: Dict[str, Any] = {
            "input": schema_cols,
            "output": schema_cols,
        }

        # Add reject schema if present
        reject_cols = self._parse_schema(node, "REJECT")
        if reject_cols:
            schema["reject"] = reject_cols

        component = self._build_component_dict(
            node=node,
            type_name="ExtractRegexFields",
            config=config,
            schema=schema,
        )

        return ComponentResult(component=component, warnings=warnings)
