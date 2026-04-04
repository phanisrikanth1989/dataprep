"""Converter for Talend tFilterColumns component.

Filters columns from the input schema, passing only selected columns through.

Config mapping (0 unique params + framework):
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Engine reads 'mode' (default 'include') and 'keep_row_order' (default True)
which are NOT _java.xml params -- documented as needs_review.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFilterColumns")
class FilterColumnsConverter(ComponentConverter):
    """Convert Talend tFilterColumns to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        """Convert a TalendNode into a v1 FilterColumns component dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Config dict (no unique params) ----
        config: Dict[str, Any] = {}

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema (passthrough transform: input == output) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 7. Engine gap needs_review entries ----
        needs_review.append({
            "issue": "Engine reads 'mode' (default 'include') but this is not a _java.xml param. "
                     "Converter does not output this key.",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        needs_review.append({
            "issue": "Engine reads 'keep_row_order' (default True) but this is not a _java.xml param. "
                     "Converter does not output this key.",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FilterColumns",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
