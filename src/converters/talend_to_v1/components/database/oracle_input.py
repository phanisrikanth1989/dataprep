"""Converter for Talend tOracleInput component.

Reads data from an Oracle database using SQL queries.

Config mapping (28 params total):
  USE_EXISTING_CONNECTION    -> use_existing_connection (bool, default False)
  CONNECTION                 -> connection (str, default "")
  CONNECTION_TYPE            -> connection_type (str, default "ORACLE_SID")
  DB_VERSION                 -> db_version (str, default "ORACLE_18")
  RAC_URL                    -> rac_url (str, default "")
  HOST                       -> host (str, default "")
  PORT                       -> port (str, default "1521")
  DBNAME                     -> dbname (str, default "")
  LOCAL_SERVICE_NAME         -> local_service_name (str, default "")
  SCHEMA_DB                  -> schema_db (str, default "")
  USER                       -> user (str, default "")
  PASS                       -> password (str, default "")
  JDBC_URL                   -> jdbc_url (str, default "")
  TABLE                      -> table (str, default "")
  QUERY                      -> query (str, default "select id, name from employee")
  SPECIFY_DATASOURCE_ALIAS   -> specify_datasource_alias (bool, default False)
  DATASOURCE_ALIAS           -> datasource_alias (str, default "")
  PROPERTIES                 -> properties (str, default "")
  IS_CONVERT_XMLTYPE         -> is_convert_xmltype (bool, default False)
  CONVERT_XMLTYPE            -> convert_xmltype (list, default [])
  ENCODING                   -> encoding (str, default "ISO-8859-15")
  USE_CURSOR                 -> use_cursor (bool, default False)
  CURSOR_SIZE                -> cursor_size (int, default 1000)
  TRIM_ALL_COLUMN            -> trim_all_column (bool, default False)
  TRIM_COLUMN                -> trim_column (list, default [])
  NO_NULL_VALUES             -> no_null_values (bool, default False)
  SUPPORT_NLS                -> support_nls (bool, default False)
  TSTATCATCHER_STATS         -> tstatcatcher_stats (bool, default False)
  LABEL                      -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_CONVERT_XMLTYPE_FIELDS = ("SCHEMA_COLUMN", "XML_COLUMN")
_CONVERT_XMLTYPE_GROUP_SIZE = len(_CONVERT_XMLTYPE_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_convert_xmltype(raw: Any) -> List[Dict[str, str]]:
    """Parse CONVERT_XMLTYPE TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN  -> schema_column (str, strip quotes)
      XML_COLUMN     -> xml_column (str, strip quotes)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _CONVERT_XMLTYPE_GROUP_SIZE):
        group = raw[i: i + _CONVERT_XMLTYPE_GROUP_SIZE]
        if len(group) < _CONVERT_XMLTYPE_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                row["schema_column"] = val.strip('"')
            elif ref == "XML_COLUMN":
                row["xml_column"] = val.strip('"')
        if row:
            result.append(row)
    return result


def _parse_trim_column(raw: Any) -> List[Dict[str, Any]]:
    """Parse TRIM_COLUMN TABLE into list of dicts.

    The TRIM_COLUMN TABLE structure may contain per-column trim settings.
    If raw data is not a list, returns empty list.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for entry in raw:
        if isinstance(entry, dict):
            row: Dict[str, Any] = {}
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref:
                row[ref.lower()] = val.strip('"') if isinstance(val, str) else val
            if row:
                result.append(row)
    return result


@REGISTRY.register("tOracleInput")
class OracleInputConverter(ComponentConverter):
    """Convert Talend tOracleInput to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Connection mode parameters ----
        config: Dict[str, Any] = {}
        config["use_existing_connection"] = self._get_bool(node, "USE_EXISTING_CONNECTION", False)
        config["connection"] = self._get_str(node, "CONNECTION", "")

        # ---- 2. Connection type parameters ----
        config["connection_type"] = self._get_str(node, "CONNECTION_TYPE", "ORACLE_SID")
        config["db_version"] = self._get_str(node, "DB_VERSION", "ORACLE_18")
        config["rac_url"] = self._get_str(node, "RAC_URL", "")

        # ---- 3. Core connection parameters ----
        config["host"] = self._get_str(node, "HOST", "")
        config["port"] = self._get_str(node, "PORT", "1521")
        config["dbname"] = self._get_str(node, "DBNAME", "")
        config["local_service_name"] = self._get_str(node, "LOCAL_SERVICE_NAME", "")
        config["schema_db"] = self._get_str(node, "SCHEMA_DB", "")
        config["user"] = self._get_str(node, "USER", "")
        config["password"] = self._get_str(node, "PASS", "")  # _java.xml uses PASS, not PASSWORD
        config["jdbc_url"] = self._get_str(node, "JDBC_URL", "")

        # ---- 4. Query parameters ----
        config["table"] = self._get_str(node, "TABLE", "")
        config["query"] = self._get_str(node, "QUERY", "select id, name from employee")

        # ---- 5. Datasource alias parameters ----
        config["specify_datasource_alias"] = self._get_bool(node, "SPECIFY_DATASOURCE_ALIAS", False)
        config["datasource_alias"] = self._get_str(node, "DATASOURCE_ALIAS", "")

        # ---- 6. Advanced parameters ----
        config["properties"] = self._get_str(node, "PROPERTIES", "")
        config["is_convert_xmltype"] = self._get_bool(node, "IS_CONVERT_XMLTYPE", False)
        config["convert_xmltype"] = _parse_convert_xmltype(node.params.get("CONVERT_XMLTYPE", []))
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["use_cursor"] = self._get_bool(node, "USE_CURSOR", False)
        config["cursor_size"] = self._get_int(node, "CURSOR_SIZE", 1000)
        config["trim_all_column"] = self._get_bool(node, "TRIM_ALL_COLUMN", False)
        config["trim_column"] = _parse_trim_column(node.params.get("TRIM_COLUMN"))
        config["no_null_values"] = self._get_bool(node, "NO_NULL_VALUES", False)
        config["support_nls"] = self._get_bool(node, "SUPPORT_NLS", False)

        # ---- 7. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 8. Engine gap needs_review entries ----
        needs_review.append({
            "issue": (
                "No concrete engine implementation for tOracleInput. "
                "All config keys are extracted for future engine support."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 9. Build standard component dict (source: data flows OUT) ----
        component = self._build_component_dict(
            node=node,
            type_name="tOracleInput",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        # ---- 10. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
