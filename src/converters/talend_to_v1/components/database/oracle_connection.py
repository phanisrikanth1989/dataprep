"""Converter for Talend tOracleConnection / tDBConnection -> v1 OracleConnection.

Fixes:
  CONV-OC-001: indentation bug in complex_converter/component_parser.py
    line 1032 — config assignment ran unconditionally outside the ``if``
    block, so only the last parameter seen was stored.  This converter
    correctly extracts every parameter using the base-class helpers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tOracleConnection", "tDBConnection")
class OracleConnectionConverter(ComponentConverter):
    """Convert a Talend tOracleConnection / tDBConnection node into a v1
    OracleConnection component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters ---
        connection_type = self._get_str(node, "CONNECTION_TYPE")
        host = self._get_str(node, "HOST")
        port = self._get_int(node, "PORT", default=1521)
        dbname = self._get_str(node, "DBNAME")
        user = self._get_str(node, "USER")
        password = self._get_str(node, "PASS")
        auto_commit = self._get_bool(node, "AUTO_COMMIT")
        support_nls = self._get_bool(node, "SUPPORT_NLS")

        # --- Validation warnings ---
        if not host:
            warnings.append("HOST is empty")
        if not dbname:
            warnings.append("DBNAME is empty")
        if not user:
            warnings.append("USER is empty")

        # --- Build config dict ---
        config: Dict[str, Any] = {
            "connection_type": connection_type,
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password,
            "auto_commit": auto_commit,
            "support_nls": support_nls,
        }

        component = self._build_component_dict(
            node=node,
            type_name="OracleConnection",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
