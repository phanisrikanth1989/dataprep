"""Converter for Talend tExtractRegexFields component.

Extracts fields from a column using regex capture groups.

Config mapping (4 unique params + framework):
  FIELD           -> field           (str, PREV_COLUMN_LIST, default "")
  REGEX           -> regex           (str, MEMO, default "")
  DIE_ON_ERROR    -> die_on_error    (bool, default True)
  CHECK_FIELDS_NUM -> check_fields_num (bool, default False)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: GROUP (not in _java.xml)
REGEX_HELP is a LABEL param (informational text) -- not extracted.

No v1 engine implementation exists -- single consolidated needs_review per D-27.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tExtractRegexFields")
class ExtractRegexFieldsConverter(ComponentConverter):
    """Convert Talend tExtractRegexFields to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        """Convert a TalendNode into a v1 tExtractRegexFields component dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["field"] = self._get_str(node, "FIELD", "")
        config["regex"] = self._get_str(node, "REGEX", "")
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", True)
        config["check_fields_num"] = self._get_bool(node, "CHECK_FIELDS_NUM", False)

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema (passthrough transform: input == output) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 7. Engine gap needs_review (single consolidated per D-27) ----
        needs_review.append({
            "issue": (
                "No v1 engine implementation exists for tExtractRegexFields. "
                "Converter output is syntactically valid but cannot execute at runtime."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tExtractRegexFields",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
