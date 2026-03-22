"""Converter for Talend tOracleBulkExec -> v1 OracleBulkExec.

Extracts HOST, PORT, DBNAME, USER, PASS, DATA, TABLE, CLT_FILE,
and DIE_ON_ERROR from the Talend node parameters.

Config keys are kept UPPERCASE for backward compatibility with the original
complex_converter output (see component_parser.py lines 2411-2446).

Note: the password parameter is named PASS (not PASSWORD) in tOracleBulkExec,
matching the Talend component definition.

Schema: utility component — both input and output schemas are empty.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tOracleBulkExec")
class OracleBulkExecConverter(ComponentConverter):
    """Convert a Talend tOracleBulkExec node into a v1 OracleBulkExec component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters (UPPERCASE keys for backward compat) ---
        host = self._get_str(node, "HOST")
        port = self._get_int(node, "PORT", default=1521)
        dbname = self._get_str(node, "DBNAME")
        user = self._get_str(node, "USER")
        password = self._get_str(node, "PASS")
        data = self._get_str(node, "DATA")
        table = self._get_str(node, "TABLE")
        clt_file = self._get_str(node, "CLT_FILE")
        die_on_error = self._get_bool(node, "DIE_ON_ERROR")

        config: Dict[str, Any] = {
            "HOST": host,
            "PORT": port,
            "DBNAME": dbname,
            "USER": user,
            "PASS": password,
            "DATA": data,
            "TABLE": table,
            "CLT_FILE": clt_file,
            "DIE_ON_ERROR": die_on_error,
        }

        # --- Validation warnings ---
        if not host:
            warnings.append("HOST is empty")
        if not dbname:
            warnings.append("DBNAME is empty")
        if not table:
            warnings.append("TABLE is empty")

        component = self._build_component_dict(
            node=node,
            type_name="OracleBulkExec",
            config=config,
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
