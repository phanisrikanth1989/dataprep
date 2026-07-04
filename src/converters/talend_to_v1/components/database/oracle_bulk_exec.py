"""Converter for Talend tOracleBulkExec component.

Performs Oracle bulk data loading via SQL*Loader (sqlldr). Most parameter-rich
database component with 38 configurable parameters spanning connection, core,
SQL*Loader control file, NLS, and encoding settings.

Config mapping (40 params total):
  USE_EXISTING_CONNECTION          -> use_existing_connection (bool, default False)
  CONNECTION                       -> connection (str, default "")
  CONNECTION_TYPE                  -> connection_type (str, default "ORACLE_SID")
  DB_VERSION                       -> db_version (str, default "ORACLE_18")
  HOST                             -> host (str, default "")
  PORT                             -> port (str, default "1521")
  DBNAME                           -> dbname (str, default "")
  LOCAL_SERVICE_NAME               -> local_service_name (str, default "")
  SCHEMA_DB                        -> schema_db (str, default "")
  USER                             -> user (str, default "")
  PASS                             -> password (str, default "")
  TABLE                            -> table (str, default "")
  TABLE_ACTION                     -> table_action (str, default "NONE")
  DATA                             -> data (str, default "")
  DATA_ACTION                      -> data_action (str, default "INSERT")
  PROPERTIES                       -> properties (str, default "")
  ADVANCED_SEPARATOR               -> advanced_separator (bool, default False)
  THOUSANDS_SEPARATOR              -> thousands_separator (str, default ",")
  DECIMAL_SEPARATOR                -> decimal_separator (str, default ".")
  USE_EXISTING_CLT_FILE            -> use_existing_clt_file (bool, default False)
  CLT_FILE                         -> clt_file (str, default "")
  RECORD_FORMAT                    -> record_format (str, default "DEFAULT")
  INPUT_INTO_TABLE_CLAUSE          -> input_into_table_clause (bool, default False)
  FIELDS_TERMINATOR                -> fields_terminator (str, default "OTHER")
  TERMINATOR_VALUE                 -> terminator_value (str, default ";")
  USE_FIELDS_ENCLOSURE             -> use_fields_enclosure (bool, default False)
  USE_DATE_PATTERN                 -> use_date_pattern (bool, default False)
  PRESERVE_BLANKS                  -> preserve_blanks (bool, default False)
  TRAILING_NULLCOLS                -> trailing_nullcols (bool, default False)
  OPTIONS                          -> options (list[str], default [])
  NLS_LANGUAGE                     -> nls_language (str, default "DEFAULT")
  NLS_DATE_LANGUAGE                -> nls_date_language (str, default "DEFAULT")
  SET_NLS_TERRITORY                -> set_nls_territory (bool, default True)
  NLS_TERRITORY                    -> nls_territory (str, default "DEFAULT")
  ENCODING                         -> encoding (str, default "UTF8")
  OUTPUT                           -> output (str, default "OUTPUT_TO_CONSOLE")
  CONVERT_COLUMN_TABLE_TO_UPPERCASE -> convert_column_table_to_uppercase (bool, default False)
  SUPPORT_NLS                      -> support_nls (bool, default False)
  TSTATCATCHER_STATS               -> tstatcatcher_stats (bool, default False)
  LABEL                            -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_options_table(raw: Any) -> List[str]:
    """Parse OPTIONS TABLE into list of option strings.

    Each elementRef entry with ref "OPTIONS" contains one option value.
    Values are stripped of surrounding quotes.

    Returns empty list if raw is None, not a list, or empty.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        val = entry.get("value", "")
        result.append(val.strip('"'))
    return result


@REGISTRY.register("tOracleBulkExec")
class OracleBulkExecConverter(ComponentConverter):
    """Convert Talend tOracleBulkExec to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        params = node.params
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- Base ----
        config: Dict[str, Any] = {}

        # ---- 1. Connection mode ----
        config["use_existing_connection"] = self._get_bool(node, "USE_EXISTING_CONNECTION", False)
        config["connection"] = self._get_str(node, "CONNECTION", "")

        # ---- 2. Connection type ----
        config["connection_type"] = self._get_str(node, "CONNECTION_TYPE", "ORACLE_SID")
        config["db_version"] = self._get_str(node, "DB_VERSION", "ORACLE_18")

        # ---- 3. Core connection ----
        config["host"] = self._get_str(node, "HOST", "")
        config["port"] = self._get_str(node, "PORT", "1521")
        config["dbname"] = self._get_str(node, "DBNAME", "")
        config["local_service_name"] = self._get_str(node, "LOCAL_SERVICE_NAME", "")
        config["schema_db"] = self._get_str(node, "SCHEMA_DB", "")
        config["user"] = self._get_str(node, "USER", "")
        config["password"] = self._extract_password(self._get_str(node, "PASS", ""), log_id=node.component_id)

        # ---- 4. Target ----
        config["table"] = self._get_str(node, "TABLE", "")
        config["table_action"] = self._get_str(node, "TABLE_ACTION", "NONE")
        config["data"] = self._get_str(node, "DATA", "")
        config["data_action"] = self._get_str(node, "DATA_ACTION", "INSERT")

        # ---- 5. Separators ----
        config["properties"] = self._get_str(node, "PROPERTIES", "")
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")

        # ---- 6. Control file ----
        config["use_existing_clt_file"] = self._get_bool(node, "USE_EXISTING_CLT_FILE", False)
        config["clt_file"] = self._get_str(node, "CLT_FILE", "")

        # ---- 7. Record format ----
        config["record_format"] = self._get_str(node, "RECORD_FORMAT", "DEFAULT")
        config["input_into_table_clause"] = self._get_bool(node, "INPUT_INTO_TABLE_CLAUSE", False)
        config["fields_terminator"] = self._get_str(node, "FIELDS_TERMINATOR", "OTHER")
        config["terminator_value"] = self._get_str(node, "TERMINATOR_VALUE", ";")
        config["use_fields_enclosure"] = self._get_bool(node, "USE_FIELDS_ENCLOSURE", False)
        config["use_date_pattern"] = self._get_bool(node, "USE_DATE_PATTERN", False)
        config["preserve_blanks"] = self._get_bool(node, "PRESERVE_BLANKS", False)
        config["trailing_nullcols"] = self._get_bool(node, "TRAILING_NULLCOLS", False)

        # ---- 8. Options TABLE ----
        config["options"] = _parse_options_table(params.get("OPTIONS", []))

        # ---- 9. NLS ----
        config["nls_language"] = self._get_str(node, "NLS_LANGUAGE", "DEFAULT")
        config["nls_date_language"] = self._get_str(node, "NLS_DATE_LANGUAGE", "DEFAULT")
        config["set_nls_territory"] = self._get_bool(node, "SET_NLS_TERRITORY", True)  # NOTE: default True
        config["nls_territory"] = self._get_str(node, "NLS_TERRITORY", "DEFAULT")

        # ---- 10. Other advanced ----
        config["encoding"] = self._get_str(node, "ENCODING", "UTF8")  # NOTE: UTF8 not ISO-8859-15
        config["output"] = self._get_str(node, "OUTPUT", "OUTPUT_TO_CONSOLE")
        config["convert_column_table_to_uppercase"] = self._get_bool(
            node, "CONVERT_COLUMN_TABLE_TO_UPPERCASE", False
        )
        config["support_nls"] = self._get_bool(node, "SUPPORT_NLS", False)

        # ---- 11. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 12. Engine gap needs_review entries ----
        needs_review.append({
            "issue": (
                "No concrete engine implementation for tOracleBulkExec -- "
                "SQL*Loader integration required. All 38 config keys are extracted "
                "for future engine support."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 13. Build standard component dict (sink: data flows IN) ----
        component = self._build_component_dict(
            node=node,
            type_name="tOracleBulkExec",
            config=config,
            schema={"input": self._parse_schema(node), "output": []},
        )

        # ---- 14. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
