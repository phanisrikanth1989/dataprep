"""Converter for Talend tMSSqlConnection -> v1 MSSqlConnection.

Maps the Talend tMSSqlConnection component to a v1 MSSqlConnection utility
component.  Handles encrypted password values by stripping the
``enc:system.encryption.key.v1:`` prefix.

Reference: complex_converter/component_parser.py lines 2508-2542.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_ENCRYPTED_PREFIX = "enc:system.encryption.key.v1:"


@REGISTRY.register("tMSSqlConnection")
class MSSqlConnectionConverter(ComponentConverter):
    """Convert a Talend tMSSqlConnection node into a v1
    MSSqlConnection component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters ---
        host = self._get_str(node, "HOST")
        port = self._get_int(node, "PORT", default=1433)
        dbname = self._get_str(node, "DBNAME")
        user = self._get_str(node, "USER")
        password = self._extract_password(node)
        properties = self._get_str(node, "PROPERTIES")
        auto_commit = self._get_bool(node, "AUTO_COMMIT")

        # --- Validation warnings ---
        if not host:
            warnings.append("HOST is empty")
        if not dbname:
            warnings.append("DBNAME is empty")
        if not user:
            warnings.append("USER is empty")

        # --- Build config dict ---
        config: Dict[str, Any] = {
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password,
            "properties": properties,
            "auto_commit": auto_commit,
        }

        component = self._build_component_dict(
            node=node,
            type_name="MSSqlConnection",
            config=config,
            # Utility component -- no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)

    # ------------------------------------------------------------------
    # Password helper
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_password(node: TalendNode) -> str:
        """Extract password, stripping the encrypted prefix if present."""
        raw = node.params.get("PASSWORD")
        if raw is None:
            return ""
        if isinstance(raw, str) and raw.startswith(_ENCRYPTED_PREFIX):
            return raw[len(_ENCRYPTED_PREFIX):]
        # Fall back to normal string extraction (strip quotes)
        if isinstance(raw, str):
            if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
                return raw[1:-1]
            return raw
        return str(raw)
