"""Converter for Talend tOracleRollback -> v1 OracleRollback.

Fixes:
  CONV-OR-001: complex_converter/component_parser.py line 2223-2235
    The original parser manually navigated XML with ``node.find()``, requiring
    raw XML access and lacking default handling for missing attributes.
    This converter uses the base-class helpers for safe extraction and
    consistent type coercion.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tOracleRollback")
class OracleRollbackConverter(ComponentConverter):
    """Convert a Talend tOracleRollback node into a v1 OracleRollback component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters ---
        connection = self._get_str(node, "CONNECTION")
        close = self._get_bool(node, "CLOSE", default=True)
        connection_format = self._get_str(node, "CONNECTION_FORMAT")

        # --- Validation warnings ---
        if not connection:
            warnings.append("CONNECTION is empty")

        # --- Build config dict ---
        config: Dict[str, Any] = {
            "connection": connection,
            "close": close,
            "connection_format": connection_format,
        }

        component = self._build_component_dict(
            node=node,
            type_name="OracleRollback",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
