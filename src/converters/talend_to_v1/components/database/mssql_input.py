"""Converter for Talend tMSSqlInput -> v1 MSSqlInput.

Maps the Talend tMSSqlInput component to a v1 MSSqlInput database-read
component.  Handles encrypted password values by stripping the
``enc:system.encryption.key.v1:`` prefix.

**Bug fix:** The old ``complex_converter`` implementation
(``component_parser.py`` line 2582) had ``return component`` *inside* the
``for`` loop, causing only the first ``elementParameter`` to be processed.
By using the base-class helpers the entire parameter set is extracted
correctly.

Reference: complex_converter/component_parser.py lines 2544-2582.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_ENCRYPTED_PREFIX = "enc:system.encryption.key.v1:"


@REGISTRY.register("tMSSqlInput")
class MSSqlInputConverter(ComponentConverter):
    """Convert a Talend tMSSqlInput node into a v1 MSSqlInput component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters --------------------------------
        host = self._get_str(node, "HOST")
        port = self._get_int(node, "PORT", default=1433)
        dbname = self._get_str(node, "DBNAME")
        user = self._get_str(node, "USER")
        password = self._extract_password(node)
        query = self._get_str(node, "QUERY")
        properties = self._get_str(node, "PROPERTIES")
        query_timeout = self._get_int(node, "QUERY_TIMEOUT_IN_SECONDS", default=30)
        trim_all_columns = self._get_bool(node, "TRIM_ALL_COLUMN")

        # --- Validation warnings --------------------------------------
        if not host:
            warnings.append("HOST is empty")
        if not dbname:
            warnings.append("DBNAME is empty")
        if not query:
            warnings.append("QUERY is empty")

        # --- Build config dict ----------------------------------------
        config: Dict[str, Any] = {
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password,
            "query": query,
            "properties": properties,
            "query_timeout": query_timeout,
            "trim_all_columns": trim_all_columns,
        }

        component = self._build_component_dict(
            node=node,
            type_name="MSSqlInput",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
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
