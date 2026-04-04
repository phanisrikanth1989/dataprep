"""Converter for Talend tSampleRow component.

Selects specific rows by range specification (e.g., '1,5,10..20').

Config mapping (1 param + framework):
  RANGE -> range (str, MEMO_JAVA, default "1,5,10..20")
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: CONNECTION_FORMAT (not in _java.xml)
INFO_RANGE is a LABEL param (informational text) -- not extracted.

No v1 engine implementation exists -- single consolidated needs_review per D-27.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tSampleRow")
class SampleRowConverter(ComponentConverter):
    """Convert Talend tSampleRow to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        """Convert a TalendNode into a v1 tSampleRow component dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["range"] = self._get_str(node, "RANGE", "1,5,10..20")

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema (passthrough transform: input == output) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 7. Engine gap needs_review (single consolidated per D-27) ----
        needs_review.append({
            "issue": (
                "No v1 engine implementation exists for tSampleRow. "
                "Converter output is syntactically valid but cannot execute at runtime."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tSampleRow",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
