"""Converter for Talend tOracleOutput component.

Writes data to an Oracle database table with configurable table/data actions,
batch operations, and Oracle-specific settings.

Config mapping (26 params total):
  USE_EXISTING_CONNECTION              -> use_existing_connection (bool, default False)
  CONNECTION                           -> connection (str, default "")
  CONNECTION_TYPE                      -> connection_type (str, default "ORACLE_SID")
  DB_VERSION                           -> db_version (str, default "ORACLE_18")
  HOST                                 -> host (str, default "")
  PORT                                 -> port (str, default "1521")
  DBNAME                               -> dbname (str, default "")
  TABLESCHEMA                          -> table_schema (str, default "")
  USER                                 -> user (str, default "")
  PASS                                 -> password (str, default "")
  TABLE                                -> table (str, default "")
  TABLE_ACTION                         -> table_action (str, default "NONE")
  DATA_ACTION                          -> data_action (str, default "INSERT")
  COMMIT_EVERY                         -> commit_every (int, default 10000)
  USE_BATCH_SIZE                       -> use_batch_size (bool, default True)
  BATCH_SIZE                           -> batch_size (int, default 10000)
  USE_FIELD_OPTIONS                    -> use_field_options (bool, default False)
  USE_HINT_OPTIONS                     -> use_hint_options (bool, default False)
  DIE_ON_ERROR                         -> die_on_error (bool, default False)
  ENABLE_DEBUG_MODE                    -> enable_debug_mode (bool, default False)
  CONVERT_COLUMN_TABLE_TO_UPPERCASE    -> convert_column_table_to_uppercase (bool, default False)
  USE_TIMESTAMP_FOR_DATE_TYPE          -> use_timestamp_for_date_type (bool, default True)
  TRIM_CHAR                            -> trim_char (bool, default True)
  SUPPORT_NLS                          -> support_nls (bool, default False)
  TSTATCATCHER_STATS                   -> tstatcatcher_stats (bool, default False)
  LABEL                                -> label (str, default "")

NOTE: tOracleOutput uses TABLESCHEMA (not SCHEMA_DB like other Oracle components).
NOTE: _java.xml param name is PASS (not PASSWORD). Config key is password.
NOTE: USE_BATCH_SIZE, USE_TIMESTAMP_FOR_DATE_TYPE, TRIM_CHAR default to True.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tOracleOutput")
class OracleOutputConverter(ComponentConverter):
    """Convert Talend tOracleOutput to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Basic connection parameters ----
        config: Dict[str, Any] = {}
        config["use_existing_connection"] = self._get_bool(node, "USE_EXISTING_CONNECTION", False)
        config["connection"] = self._get_str(node, "CONNECTION", "")
        config["connection_type"] = self._get_str(node, "CONNECTION_TYPE", "ORACLE_SID")
        config["db_version"] = self._get_str(node, "DB_VERSION", "ORACLE_18")
        config["host"] = self._get_str(node, "HOST", "")
        config["port"] = self._get_str(node, "PORT", "1521")
        config["dbname"] = self._get_str(node, "DBNAME", "")

        # NOTE: tOracleOutput uses TABLESCHEMA (not SCHEMA_DB)
        config["table_schema"] = self._get_str(node, "TABLESCHEMA", "")

        config["user"] = self._get_str(node, "USER", "")

        # NOTE: _java.xml param name is PASS (not PASSWORD)
        config["password"] = self._get_str(node, "PASS", "")

        # ---- 2. Table and action parameters ----
        config["table"] = self._get_str(node, "TABLE", "")
        config["table_action"] = self._get_str(node, "TABLE_ACTION", "NONE")
        config["data_action"] = self._get_str(node, "DATA_ACTION", "INSERT")

        # ---- 3. Advanced parameters ----
        config["commit_every"] = self._get_int(node, "COMMIT_EVERY", 10000)
        config["use_batch_size"] = self._get_bool(node, "USE_BATCH_SIZE", True)  # default True
        config["batch_size"] = self._get_int(node, "BATCH_SIZE", 10000)
        config["use_field_options"] = self._get_bool(node, "USE_FIELD_OPTIONS", False)
        config["use_hint_options"] = self._get_bool(node, "USE_HINT_OPTIONS", False)
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)
        config["enable_debug_mode"] = self._get_bool(node, "ENABLE_DEBUG_MODE", False)
        config["convert_column_table_to_uppercase"] = self._get_bool(
            node, "CONVERT_COLUMN_TABLE_TO_UPPERCASE", False
        )
        config["use_timestamp_for_date_type"] = self._get_bool(
            node, "USE_TIMESTAMP_FOR_DATE_TYPE", True
        )  # default True
        config["trim_char"] = self._get_bool(node, "TRIM_CHAR", True)  # default True
        config["support_nls"] = self._get_bool(node, "SUPPORT_NLS", False)

        # ---- 4. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 5. Connection-type review entries (D-E1, Phase 11) ----
        # Engine ships ORACLE_SID / ORACLE_SERVICE_NAME / ORACLE_RAC in Phase 11;
        # ORACLE_OCI / ORACLE_WALLET require thick mode + Instant Client (deferred).
        if config["connection_type"] in ("ORACLE_WALLET", "ORACLE_OCI"):
            needs_review.append({
                "issue": (
                    f"Connection type {config['connection_type']} requires "
                    f"oracle_config.thick_mode=true in job config, plus Oracle "
                    f"Instant Client on the host. Phase 11 raises ConfigurationError "
                    f"until thick_mode is set."
                ),
                "component": node.component_id,
                "severity": "needs_review",
            })

        # ---- 6. Build standard component dict (sink: data flows IN) ----
        component = self._build_component_dict(
            node=node,
            type_name="tOracleOutput",
            config=config,
            schema={"input": self._parse_schema(node), "output": []},
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
