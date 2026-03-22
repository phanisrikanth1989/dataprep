"""Converter for Talend tOracleClose -> v1 OracleClose.

Closes a named Oracle connection that was previously opened by
tOracleConnection.  The only meaningful parameter is CONNECTION,
which identifies the connection to close.

Reference: complex_converter/component_parser.py lines 2213-2221.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tOracleClose")
class OracleCloseConverter(ComponentConverter):
    """Convert a Talend tOracleClose node into a v1 OracleClose component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters ---
        connection = self._get_str(node, "CONNECTION")

        # --- Validation warnings ---
        if not connection:
            warnings.append("CONNECTION is empty")

        # --- Build config dict ---
        config: Dict[str, Any] = {
            "connection": connection,
        }

        component = self._build_component_dict(
            node=node,
            type_name="OracleClose",
            config=config,
            # Utility component -- no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
