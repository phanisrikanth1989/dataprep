"""Converter for Talend tUnite component.

Merges multiple input flows into a single output using UNION ALL semantics.

Config mapping (0 unique params + framework):
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Engine has many extra features (mode, remove_duplicates, sort_output, merge_columns,
merge_how, keep, sort_columns) that are engine-specific extensions, NOT Talend _java.xml
params. Engine defaults (UNION mode, no dedup) match Talend UNION ALL behavior.
No needs_review needed since engine defaults are compatible.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tUnite")
class UniteConverter(ComponentConverter):
    """Convert Talend tUnite to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        """Convert a TalendNode into a v1 Unite component dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Config dict (no unique _java.xml params) ----
        config: Dict[str, Any] = {}

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema (passthrough transform: input == output) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="Unite",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
