"""Converter for Talend tOracleOutput -> v1 OracleOutput.

Extracts HOST, PORT, DBNAME, USER, PASSWORD, TABLE, DATA_ACTION,
CONNECTION, and USE_EXISTING_CONNECTION from the Talend node parameters.

Config keys are kept UPPERCASE for backward compatibility with the original
complex_converter output (see component_parser.py lines 2297-2332).

Schema: output component — input schema is populated from the FLOW connector;
output schema is always empty.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tOracleOutput")
class OracleOutputConverter(ComponentConverter):
    """Convert a Talend tOracleOutput node into a v1 OracleOutput component."""

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
        password = self._get_str(node, "PASSWORD")
        table = self._get_str(node, "TABLE")
        data_action = self._get_str(node, "DATA_ACTION")
        connection = self._get_str(node, "CONNECTION")
        use_existing = self._get_bool(node, "USE_EXISTING_CONNECTION")

        config: Dict[str, Any] = {
            "HOST": host,
            "PORT": port,
            "DBNAME": dbname,
            "USER": user,
            "PASSWORD": password,
            "TABLE": table,
            "DATA_ACTION": data_action,
            "CONNECTION": connection,
            "USE_EXISTING_CONNECTION": use_existing,
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
            type_name="OracleOutput",
            config=config,
            schema={"input": self._parse_schema(node), "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
