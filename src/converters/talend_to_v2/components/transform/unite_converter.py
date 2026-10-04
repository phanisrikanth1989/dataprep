"""Converter for Talend tUnite to v2 Unite component.

Merges multiple input flows into a single output using UNION ALL semantics.
tUnite has zero unique Talend parameters beyond SCHEMA and framework params.
The converter produces a minimal v2 config -- engine defaults handle the rest.

Config mapping:
  (no unique params)
  Framework: TSTATCATCHER_STATS, LABEL -> warnings only
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY as CONVERTER_REGISTRY

logger = logging.getLogger(__name__)


@CONVERTER_REGISTRY.register("tUnite")
class UniteConverter(ComponentConverter):
    """Convert Talend tUnite to v2 unite config."""

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        """Convert a TalendNode into a v2 Unite component dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Build config (tUnite has zero unique params) ----
        config: Dict[str, Any] = {}

        # ---- 2. Introspection: warn on UNSUPPORTED/NOT_PLANNED features ----
        try:
            from src.v2.components.capabilities import Support, get_supported_features
            from src.v2.components.transform.unite import Unite

            features = get_supported_features(Unite)
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
                            f"Feature '{feat_key}' is NOT_PLANNED in v2: "
                            f"{feat_support.note}. Skipping."
                        )
        except ImportError:
            # Deliberate cross-layer import for feature introspection.
            # If src.v2 is not installed or restructured, we degrade
            # gracefully -- the converter still produces valid output,
            # it just cannot auto-generate unsupported-feature warnings.
            logger.debug("Could not import Unite component for feature introspection")

        # ---- 3. Build component dict ----
        component = {
            "id": node.component_id,
            "type": "unite",
            "config": config,
        }

        # ---- 4. Build flows ----
        flows = self._build_simple_flows(node, connections)

        return ComponentResult(
            component=component,
            flows=flows,
            warnings=warnings,
            needs_review=needs_review,
        )
