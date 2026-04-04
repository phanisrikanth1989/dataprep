"""Converter for Talend tOracleRow component.

Executes arbitrary SQL statements (INSERT, UPDATE, DELETE, DDL) against
an Oracle database.  Supports prepared statements with typed parameters,
record set propagation, and all Oracle connection types.

Config mapping (28 params total):
  USE_EXISTING_CONNECTION          -> use_existing_connection (bool, default False)
  CONNECTION                       -> connection (str, default "")
  CONNECTION_TYPE                  -> connection_type (str, default "ORACLE_SID")
  DB_VERSION                       -> db_version (str, default "ORACLE_18")
  RAC_URL                          -> rac_url (str, default "")
  HOST                             -> host (str, default "")
  PORT                             -> port (str, default "1521")
  DBNAME                           -> dbname (str, default "")
  LOCAL_SERVICE_NAME               -> local_service_name (str, default "")
  SCHEMA_DB                        -> schema_db (str, default "")
  USER                             -> user (str, default "")
  PASS                             -> password (str, default "")
  TABLE                            -> table (str, default "")
  QUERY                            -> query (str, default "select id, name from employee")
  USE_NB_LINE                      -> use_nb_line (str, default "NONE")
  SPECIFY_DATASOURCE_ALIAS         -> specify_datasource_alias (bool, default False)
  DATASOURCE_ALIAS                 -> datasource_alias (str, default "")
  DIE_ON_ERROR                     -> die_on_error (bool, default False)
  PROPERTIES                       -> properties (str, default "")
  PROPAGATE_RECORD_SET             -> propagate_record_set (bool, default False)
  RECORD_SET_COLUMN                -> record_set_column (str, default "")
  USE_PREPAREDSTATEMENT            -> use_preparedstatement (bool, default False)
  SET_PREPAREDSTATEMENT_PARAMETERS -> set_preparedstatement_parameters (list, default [])
  ENCODING                         -> encoding (str, default "ISO-8859-15")
  COMMIT_EVERY                     -> commit_every (int, default 10000)
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
# TABLE constants
# ------------------------------------------------------------------
_PREPARED_FIELDS = ("PARAMETER_INDEX", "PARAMETER_TYPE", "PARAMETER_VALUE")
_PREPARED_GROUP_SIZE = len(_PREPARED_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_prepared_params(raw: Any) -> List[Dict[str, str]]:
    """Parse SET_PREPAREDSTATEMENT_PARAMETERS TABLE into list of dicts.

    Each group of 3 consecutive elementRef entries maps to one row:
      PARAMETER_INDEX  -> parameter_index (str)
      PARAMETER_TYPE   -> parameter_type (str)
      PARAMETER_VALUE  -> parameter_value (str, strip quotes)

    Incomplete trailing groups (< 3 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _PREPARED_GROUP_SIZE):
        group = raw[i: i + _PREPARED_GROUP_SIZE]
        if len(group) < _PREPARED_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "PARAMETER_INDEX":
                row["parameter_index"] = val.strip('"')
            elif ref == "PARAMETER_TYPE":
                row["parameter_type"] = val.strip('"')
            elif ref == "PARAMETER_VALUE":
                row["parameter_value"] = val.strip('"')
        if row:
            result.append(row)
    return result


@REGISTRY.register("tOracleRow")
class OracleRowConverter(ComponentConverter):
    """Convert Talend tOracleRow to v1 engine config."""

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
        config["use_existing_connection"] = self._get_bool(node, "USE_EXISTING_CONNECTION", False)
        config["connection"] = self._get_str(node, "CONNECTION", "")
        config["connection_type"] = self._get_str(node, "CONNECTION_TYPE", "ORACLE_SID")
        config["db_version"] = self._get_str(node, "DB_VERSION", "ORACLE_18")
        config["rac_url"] = self._get_str(node, "RAC_URL", "")
        config["host"] = self._get_str(node, "HOST", "")
        config["port"] = self._get_str(node, "PORT", "1521")
        config["dbname"] = self._get_str(node, "DBNAME", "")
        config["local_service_name"] = self._get_str(node, "LOCAL_SERVICE_NAME", "")
        config["schema_db"] = self._get_str(node, "SCHEMA_DB", "")
        config["user"] = self._get_str(node, "USER", "")
        config["password"] = self._get_str(node, "PASS", "")  # _java.xml: PASS (not PASSWORD)

        # ---- 2. Query parameters ----
        config["table"] = self._get_str(node, "TABLE", "")
        config["query"] = self._get_str(node, "QUERY", "select id, name from employee")
        config["use_nb_line"] = self._get_str(node, "USE_NB_LINE", "NONE")

        # ---- 3. Datasource alias parameters ----
        config["specify_datasource_alias"] = self._get_bool(node, "SPECIFY_DATASOURCE_ALIAS", False)
        config["datasource_alias"] = self._get_str(node, "DATASOURCE_ALIAS", "")

        # ---- 4. Error handling ----
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)

        # ---- 5. Advanced parameters ----
        config["properties"] = self._get_str(node, "PROPERTIES", "")
        config["propagate_record_set"] = self._get_bool(node, "PROPAGATE_RECORD_SET", False)
        config["record_set_column"] = self._get_str(node, "RECORD_SET_COLUMN", "")
        config["use_preparedstatement"] = self._get_bool(node, "USE_PREPAREDSTATEMENT", False)
        config["set_preparedstatement_parameters"] = _parse_prepared_params(
            node.params.get("SET_PREPAREDSTATEMENT_PARAMETERS", [])
        )
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["commit_every"] = self._get_int(node, "COMMIT_EVERY", 10000)
        config["support_nls"] = self._get_bool(node, "SUPPORT_NLS", False)

        # ---- 6. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 7. Engine gap needs_review entries ----
        needs_review.append({
            "issue": (
                "No concrete engine implementation for tOracleRow. "
                "All config keys are extracted for future engine support."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 8. Build standard component dict (bidirectional: reads and writes data) ----
        component = self._build_component_dict(
            node=node,
            type_name="tOracleRow",
            config=config,
            schema={"input": self._parse_schema(node), "output": self._parse_schema(node)},
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
