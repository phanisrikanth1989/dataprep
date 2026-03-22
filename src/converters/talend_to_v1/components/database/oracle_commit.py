"""Converter for Talend tOracleCommit -> v1 OracleCommit.

Fixes:
  CONV-OC-001: alignment with complex_converter/component_parser.py
    line 2201 — parse_t_oracle_commit extracted CONNECTION and CLOSE
    parameters.  This converter reproduces the same logic using the
    base-class helpers for safe type coercion.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tOracleCommit")
class OracleCommitConverter(ComponentConverter):
    """Convert a Talend tOracleCommit node into a v1 OracleCommit component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters ---
        connection = self._get_str(node, "CONNECTION")
        close_connection = self._get_bool(node, "CLOSE", default=True)

        # --- Validation warnings ---
        if not connection:
            warnings.append("CONNECTION is empty")

        # --- Build config dict ---
        config: Dict[str, Any] = {
            "connection": connection,
            "close_connection": close_connection,
        }

        component = self._build_component_dict(
            node=node,
            type_name="OracleCommit",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
