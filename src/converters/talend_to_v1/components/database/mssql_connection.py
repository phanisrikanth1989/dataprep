"""Converter for Talend tMSSqlConnection component.

Establishes a Microsoft SQL Server database connection.

Config mapping (18 params total):
  DRIVER                   -> driver (str, default "MSSQL_PROP")
  HOST                     -> host (str, default "")
  PORT                     -> port (str, default "1433")
  SCHEMA_DB                -> schema_db (str, default "")
  DBNAME                   -> dbname (str, default "")
  USER                     -> user (str, default "")
  PASS                     -> password (str, default "", encrypted prefix stripped)
  ENCODING                 -> encoding (str, default "ISO-8859-15")
  PROPERTIES               -> properties (str, default "")
  USE_SHARED_CONNECTION    -> use_shared_connection (bool, default False)
  SHARED_CONNECTION_NAME   -> shared_connection_name (str, default "")
  SPECIFY_DATASOURCE_ALIAS -> specify_datasource_alias (bool, default False)
  DATASOURCE_ALIAS         -> datasource_alias (str, default "")
  ACTIVE_DIR_AUTH          -> active_dir_auth (bool, default False)
  AUTO_COMMIT              -> auto_commit (bool, default False)
  SHARE_IDENTITY_SETTING   -> share_identity_setting (bool, default False)
  TSTATCATCHER_STATS       -> tstatcatcher_stats (bool, default False)
  LABEL                    -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_ENCRYPTED_PREFIX = "enc:system.encryption.key.v1:"


@REGISTRY.register("tMSSqlConnection")
class MSSqlConnectionConverter(ComponentConverter):
    """Convert Talend tMSSqlConnection to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core connection parameters ----
        config: Dict[str, Any] = {}
        config["driver"] = self._get_str(node, "DRIVER", "MSSQL_PROP")
        config["host"] = self._get_str(node, "HOST", "")
        config["port"] = self._get_str(node, "PORT", "1433")
        config["schema_db"] = self._get_str(node, "SCHEMA_DB", "")
        config["dbname"] = self._get_str(node, "DBNAME", "")
        config["user"] = self._get_str(node, "USER", "")
        config["password"] = self._extract_password(self._get_str(node, "PASS", ""))
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["properties"] = self._get_str(node, "PROPERTIES", "")

        # ---- 2. Shared connection ----
        config["use_shared_connection"] = self._get_bool(node, "USE_SHARED_CONNECTION", False)
        config["shared_connection_name"] = self._get_str(node, "SHARED_CONNECTION_NAME", "")

        # ---- 3. Datasource alias ----
        config["specify_datasource_alias"] = self._get_bool(node, "SPECIFY_DATASOURCE_ALIAS", False)
        config["datasource_alias"] = self._get_str(node, "DATASOURCE_ALIAS", "")

        # ---- 4. Advanced ----
        config["active_dir_auth"] = self._get_bool(node, "ACTIVE_DIR_AUTH", False)
        config["auto_commit"] = self._get_bool(node, "AUTO_COMMIT", False)
        config["share_identity_setting"] = self._get_bool(node, "SHARE_IDENTITY_SETTING", False)

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Engine gap needs_review entries ----
        needs_review.append({
            "issue": (
                "No concrete engine implementation for tMSSqlConnection. "
                "All config keys are extracted for future engine support."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 7. Build component dict ----
        component = self._build_component_dict(
            node=node,
            type_name="tMSSqlConnection",
            config=config,
            schema={"input": [], "output": []},
        )

        # ---- 8. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )

    # ------------------------------------------------------------------
    # Password helper
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_password(raw: str) -> str:
        """Extract password, stripping the encrypted prefix if present.

        Talend Studio stores encrypted passwords with the prefix
        ``enc:system.encryption.key.v1:`` -- this method strips it to
        expose the encrypted value for downstream processing.
        """
        if not raw:
            return ""
        if raw.startswith(_ENCRYPTED_PREFIX):
            return raw[len(_ENCRYPTED_PREFIX):]
        return raw
