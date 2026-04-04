"""Converter for Talend tOracleConnection component.

Establishes an Oracle database connection with support for SID,
Service Name, OCI, Custom URL, RAC, and Wallet connection types.

Config mapping (30 params total):
  CONNECTION_TYPE            -> connection_type (str, default "ORACLE_SID")
  DB_VERSION                 -> db_version (str, default "ORACLE_18")
  RAC_URL                    -> rac_url (str, default "")
  USE_TNS_FILE               -> use_tns_file (bool, default False)
  TNS_FILE                   -> tns_file (str, default "")
  HOST                       -> host (str, default "")
  PORT                       -> port (str, default "1521")
  DBNAME                     -> dbname (str, default "")
  LOCAL_SERVICE_NAME         -> local_service_name (str, default "")
  SCHEMA_DB                  -> schema_db (str, default "")
  USER                       -> user (str, default "")
  PASS                       -> password (str, default "")
  JDBC_URL                   -> jdbc_url (str, default "jdbc:oracle:thin:USER/MDP@server")
  ENCODING                   -> encoding (str, default "ISO-8859-15")
  PROPERTIES                 -> properties (str, default "")
  USE_SHARED_CONNECTION      -> use_shared_connection (bool, default False)
  SHARED_CONNECTION_NAME     -> shared_connection_name (str, default "")
  SPECIFY_DATASOURCE_ALIAS   -> specify_datasource_alias (bool, default False)
  DATASOURCE_ALIAS           -> datasource_alias (str, default "")
  USE_SSL                    -> use_ssl (bool, default False)
  SSL_TRUSTSERVER_TRUSTSTORE -> ssl_trustserver_truststore (str, default "")
  SSL_TRUSTSERVER_PASSWORD   -> ssl_trustserver_password (str, default "")
  NEED_CLIENT_AUTH           -> need_client_auth (bool, default False)
  SSL_KEYSTORE               -> ssl_keystore (str, default "")
  SSL_KEYSTORE_PASSWORD      -> ssl_keystore_password (str, default "")
  DISABLE_CBC_PROTECTION     -> disable_cbc_protection (bool, default True)
  AUTO_COMMIT                -> auto_commit (bool, default False)
  SUPPORT_NLS                -> support_nls (bool, default False)
  TSTATCATCHER_STATS         -> tstatcatcher_stats (bool, default False)
  LABEL                      -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tOracleConnection", "tDBConnection")
class OracleConnectionConverter(ComponentConverter):
    """Convert Talend tOracleConnection / tDBConnection to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Connection type parameters ----
        config: Dict[str, Any] = {}
        config["connection_type"] = self._get_str(node, "CONNECTION_TYPE", "ORACLE_SID")
        config["db_version"] = self._get_str(node, "DB_VERSION", "ORACLE_18")
        config["rac_url"] = self._get_str(node, "RAC_URL", "")
        config["use_tns_file"] = self._get_bool(node, "USE_TNS_FILE", False)
        config["tns_file"] = self._get_str(node, "TNS_FILE", "")

        # ---- 2. Core connection parameters ----
        config["host"] = self._get_str(node, "HOST", "")
        config["port"] = self._get_str(node, "PORT", "1521")
        config["dbname"] = self._get_str(node, "DBNAME", "")
        config["local_service_name"] = self._get_str(node, "LOCAL_SERVICE_NAME", "")
        config["schema_db"] = self._get_str(node, "SCHEMA_DB", "")
        config["user"] = self._get_str(node, "USER", "")
        config["password"] = self._get_str(node, "PASS", "")
        config["jdbc_url"] = self._get_str(node, "JDBC_URL", "jdbc:oracle:thin:USER/MDP@server")

        # ---- 3. Configuration parameters ----
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["properties"] = self._get_str(node, "PROPERTIES", "")

        # ---- 4. Shared connection parameters ----
        config["use_shared_connection"] = self._get_bool(node, "USE_SHARED_CONNECTION", False)
        config["shared_connection_name"] = self._get_str(node, "SHARED_CONNECTION_NAME", "")

        # ---- 5. Datasource alias parameters ----
        config["specify_datasource_alias"] = self._get_bool(node, "SPECIFY_DATASOURCE_ALIAS", False)
        config["datasource_alias"] = self._get_str(node, "DATASOURCE_ALIAS", "")

        # ---- 6. SSL parameters ----
        config["use_ssl"] = self._get_bool(node, "USE_SSL", False)
        config["ssl_trustserver_truststore"] = self._get_str(node, "SSL_TRUSTSERVER_TRUSTSTORE", "")
        config["ssl_trustserver_password"] = self._get_str(node, "SSL_TRUSTSERVER_PASSWORD", "")
        config["need_client_auth"] = self._get_bool(node, "NEED_CLIENT_AUTH", False)
        config["ssl_keystore"] = self._get_str(node, "SSL_KEYSTORE", "")
        config["ssl_keystore_password"] = self._get_str(node, "SSL_KEYSTORE_PASSWORD", "")
        config["disable_cbc_protection"] = self._get_bool(node, "DISABLE_CBC_PROTECTION", True)

        # ---- 7. Advanced parameters ----
        config["auto_commit"] = self._get_bool(node, "AUTO_COMMIT", False)
        config["support_nls"] = self._get_bool(node, "SUPPORT_NLS", False)

        # ---- 8. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 9. Engine gap needs_review entries ----
        needs_review.append({
            "issue": (
                "No concrete engine implementation for tOracleConnection. "
                "All config keys are extracted for future engine support."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 10. Build component dict ----
        component = self._build_component_dict(
            node=node,
            type_name="tOracleConnection",
            config=config,
            schema={"input": [], "output": []},
        )

        # ---- 11. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
