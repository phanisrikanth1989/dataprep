"""Converter for Talend tOracleRow -> v1 OracleRow component.

Extracts connection parameters, query configuration, and NLS/encoding
settings from the Talend node.  Supports both direct connections and
existing-connection references.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tOracleRow")
class OracleRowConverter(ComponentConverter):
    """Convert a Talend tOracleRow node into a v1 OracleRow component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Connection mode ---
        use_existing = self._get_bool(node, "USE_EXISTING_CONNECTION")

        config: Dict[str, Any] = {
            "USE_EXISTING_CONNECTION": use_existing,
            "CONNECTION": self._get_str(node, "CONNECTION"),
            "CONNECTION_TYPE": self._get_str(node, "CONNECTION_TYPE"),
            "HOST": self._get_str(node, "HOST"),
            "PORT": self._get_int(node, "PORT", 0),
            "DBNAME": self._get_str(node, "DBNAME"),
            "USER": self._get_str(node, "USER"),
            "PASSWORD": self._get_str(node, "PASSWORD"),
            "QUERY": self._get_str(node, "QUERY"),
            "ENCODING": self._get_str(node, "ENCODING"),
            "COMMIT_EVERY": self._get_int(node, "COMMIT_EVERY", 10000),
            "SUPPORT_NLS": self._get_bool(node, "SUPPORT_NLS"),
            "DIE_ON_ERROR": self._get_bool(node, "DIE_ON_ERROR"),
        }

        # --- Validation warnings ---
        if not config["QUERY"]:
            warnings.append("QUERY is empty — this is a required parameter")

        if use_existing:
            if not config["CONNECTION"]:
                warnings.append(
                    "USE_EXISTING_CONNECTION is true but CONNECTION is empty"
                )
        else:
            if not config["HOST"]:
                warnings.append("HOST is empty — this is a required parameter")
            if not config["DBNAME"]:
                warnings.append("DBNAME is empty — this is a required parameter")

        component = self._build_component_dict(
            node=node,
            type_name="OracleRow",
            config=config,
            schema={
                "input": self._parse_schema(node),
                "output": self._parse_schema(node),
            },
        )

        return ComponentResult(component=component, warnings=warnings)
