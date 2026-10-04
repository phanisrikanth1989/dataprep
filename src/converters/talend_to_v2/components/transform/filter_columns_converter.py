"""Converter for Talend tFilterColumns to v2 FilterColumns component.

Talend tFilterColumns is a simple column selection/removal component.
The output schema IS the filter -- columns present in the output schema
are kept, columns absent are removed. The REMOVE_OR_KEEP parameter
(if present) controls mode semantics.

Config mapping:
  Schema columns       -> columns list (v2 config)
  REMOVE_OR_KEEP param -> mode ("keep" or "remove", default "keep")
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY as CONVERTER_REGISTRY

logger = logging.getLogger(__name__)


@CONVERTER_REGISTRY.register("tFilterColumns")
class FilterColumnsConverter(ComponentConverter):
    """Convert Talend tFilterColumns to v2 filter_columns config."""

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        """Convert a TalendNode into a v2 FilterColumns component dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Extract mode from REMOVE_OR_KEEP param ----
        remove_or_keep = node.params.get("REMOVE_OR_KEEP", "keep")
        if isinstance(remove_or_keep, str):
            mode = remove_or_keep.lower()
        else:
            mode = "keep"

        if mode not in ("keep", "remove"):
            warnings.append(
                f"Unexpected REMOVE_OR_KEEP value '{remove_or_keep}', defaulting to 'keep'"
            )
            mode = "keep"

        # ---- 2. Extract columns from schema ----
        columns: List[str | Dict[str, str]] = []
        schema = node.schema or {}

        # Schema columns define what gets kept/removed
        if isinstance(schema, dict):
            for col_name in schema:
                columns.append(col_name)
        elif isinstance(schema, list):
            for col_def in schema:
                if isinstance(col_def, dict):
                    columns.append(col_def.get("name", ""))
                elif isinstance(col_def, str):
                    columns.append(col_def)

        # ---- 3. Build v2 config ----
        config: Dict[str, Any] = {
            "columns": columns,
        }
        if mode != "keep":
            config["mode"] = mode

        # ---- 4. Introspection: warn on UNSUPPORTED features (D-07) ----
        try:
            from src.v2.components.capabilities import Support, get_supported_features
            from src.v2.components.transform.filter_columns import FilterColumns

            features = get_supported_features(FilterColumns)
            for feat_key, feat_support in features.items():
                if feat_support.support == Support.UNSUPPORTED:
                    param_name = feat_key.upper()
                    if node.params.get(param_name):
                        warnings.append(
                            f"Feature '{feat_key}' is UNSUPPORTED in v2: {feat_support.note}"
                        )
                elif feat_support.support == Support.NOT_PLANNED:
                    param_name = feat_key.upper()
                    if node.params.get(param_name):
                        warnings.append(
                            f"Feature '{feat_key}' is NOT_PLANNED in v2: {feat_support.note}. Skipping."
                        )
        except ImportError:
            pass  # Graceful degradation if component not available

        # ---- 5. Build component dict ----
        component = {
            "id": node.component_id,
            "type": "filter_columns",
            "config": config,
        }

        # ---- 6. Build flows ----
        flows = self._build_simple_flows(node, connections)

        return ComponentResult(
            component=component,
            flows=flows,
            warnings=warnings,
            needs_review=needs_review,
        )
