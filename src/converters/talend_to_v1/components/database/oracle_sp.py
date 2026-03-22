"""Converter for Talend tOracleSP -> v1 OracleSP.

Maps the tOracleSP stored-procedure invocation component, extracting
HOST, PORT, DBNAME, USER, PASSWORD, PROCEDURE, and DIE_ON_ERROR from
the Talend parameter set.

Reference: complex_converter/component_parser.py lines 2379-2409.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tOracleSP")
class OracleSPConverter(ComponentConverter):
    """Convert a Talend tOracleSP node into a v1 OracleSP component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters (UPPERCASE keys) ---
        host = self._get_str(node, "HOST")
        port = self._get_int(node, "PORT", default=1521)
        dbname = self._get_str(node, "DBNAME")
        user = self._get_str(node, "USER")
        password = self._get_str(node, "PASSWORD")
        procedure = self._get_str(node, "PROCEDURE")
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", default=False)

        # --- Validation warnings ---
        if not host:
            warnings.append("HOST is empty")
        if not dbname:
            warnings.append("DBNAME is empty")
        if not user:
            warnings.append("USER is empty")
        if not procedure:
            warnings.append("PROCEDURE is empty")

        # --- Build config dict (UPPERCASE keys) ---
        config: Dict[str, Any] = {
            "HOST": host,
            "PORT": port,
            "DBNAME": dbname,
            "USER": user,
            "PASSWORD": password,
            "PROCEDURE": procedure,
            "DIE_ON_ERROR": die_on_error,
        }

        component = self._build_component_dict(
            node=node,
            type_name="OracleSP",
            config=config,
            # Utility component -- no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
