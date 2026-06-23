"""Converter for Talend tOracleSP component.

Executes an Oracle stored procedure or function on a database connection.
Supports standalone or shared connections, IN/OUT/INOUT parameters, custom
Oracle types (STRUCT/ARRAY), and NLS settings.

Config mapping (25 params total):
  USE_EXISTING_CONNECTION  -> use_existing_connection (bool, default False)
  CONNECTION               -> connection (str, default "")
  CONNECTION_TYPE          -> connection_type (str, default "ORACLE_SID")
  DB_VERSION               -> db_version (str, default "ORACLE_18")
  HOST                     -> host (str, default "")
  PORT                     -> port (str, default "1521")
  DBNAME                   -> dbname (str, default "")
  LOCAL_SERVICE_NAME       -> local_service_name (str, default "")
  SCHEMA_DB                -> schema_db (str, default "")
  USER                     -> user (str, default "")
  PASS                     -> password (str, default "")
  SP_NAME                  -> sp_name (str, default "myfunction")
  IS_FUNCTION              -> is_function (bool, default False)
  RETURN                   -> return_column (str, default "")
  RETURN_BDTYPE            -> return_bdtype (str, default "AUTOMAPPING")
  SP_ARGS                  -> sp_args (list[dict], default [])
  SPECIFY_DATASOURCE_ALIAS -> specify_datasource_alias (bool, default False)
  DATASOURCE_ALIAS         -> datasource_alias (str, default "")
  PROPERTIES               -> properties (str, default "")
  ENCODING                 -> encoding (str, default "ISO-8859-15")
  NLS_LANGUAGE             -> nls_language (str, default "NONE")
  NLS_TERRITORY            -> nls_territory (str, default "NONE")
  SUPPORT_NLS              -> support_nls (bool, default False)
  TSTATCATCHER_STATS       -> tstatcatcher_stats (bool, default False)
  LABEL                    -> label (str, default "")

Removed phantom params:
  PROCEDURE  -- not in _java.xml, old converter used this instead of SP_NAME
  PASSWORD   -- not in _java.xml for tOracleSP, old converter used this instead of PASS
  DIE_ON_ERROR -- not in _java.xml for tOracleSP
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_SP_ARGS_FIELDS = ("COLUMN", "TYPE", "DBTYPE", "ISCUSTOME", "CUSTOME_TYPE", "CUSTOMENAME")
_SP_ARGS_GROUP_SIZE = len(_SP_ARGS_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_sp_args(raw: Any) -> List[Dict[str, Any]]:
    """Parse SP_ARGS TABLE into list of dicts (stride-6).

    Each group of 6 consecutive elementRef entries maps to one row:
      COLUMN       -> column (str, strip quotes)
      TYPE         -> type (str, strip quotes)
      DBTYPE       -> dbtype (str, strip quotes)
      ISCUSTOME    -> is_custom (bool)
      CUSTOME_TYPE -> custom_type (str, strip quotes)
      CUSTOMENAME  -> custom_name (str, strip quotes)

    Incomplete trailing groups (< 6 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _SP_ARGS_GROUP_SIZE):
        group = raw[i: i + _SP_ARGS_GROUP_SIZE]
        if len(group) < _SP_ARGS_GROUP_SIZE:
            break
        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "COLUMN":
                row["column"] = val.strip('"')
            elif ref == "TYPE":
                row["type"] = val.strip('"')
            elif ref == "DBTYPE":
                row["dbtype"] = val.strip('"')
            elif ref == "ISCUSTOME":
                row["is_custom"] = val.strip('"').lower() in ("true", "1")
            elif ref == "CUSTOME_TYPE":
                row["custom_type"] = val.strip('"')
            elif ref == "CUSTOMENAME":
                row["custom_name"] = val.strip('"')
        if row:
            result.append(row)
    return result


@REGISTRY.register("tOracleSP")
class OracleSPConverter(ComponentConverter):
    """Convert Talend tOracleSP to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        params = node.params
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}

        # Connection parameters
        config["use_existing_connection"] = self._get_bool(node, "USE_EXISTING_CONNECTION", False)
        config["connection"] = self._get_str(node, "CONNECTION", "")
        config["connection_type"] = self._get_str(node, "CONNECTION_TYPE", "ORACLE_SID")
        config["db_version"] = self._get_str(node, "DB_VERSION", "ORACLE_18")
        config["host"] = self._get_str(node, "HOST", "")
        config["port"] = self._get_str(node, "PORT", "1521")
        config["dbname"] = self._get_str(node, "DBNAME", "")
        config["local_service_name"] = self._get_str(node, "LOCAL_SERVICE_NAME", "")
        config["schema_db"] = self._get_str(node, "SCHEMA_DB", "")
        config["user"] = self._get_str(node, "USER", "")
        config["password"] = self._extract_password(self._get_str(node, "PASS", ""), log_id=node.component_id)

        # Stored procedure parameters
        config["sp_name"] = self._get_str(node, "SP_NAME", "myfunction")  # XML name is SP_NAME, not PROCEDURE
        config["is_function"] = self._get_bool(node, "IS_FUNCTION", False)
        config["return_column"] = self._get_str(node, "RETURN", "")
        config["return_bdtype"] = self._get_str(node, "RETURN_BDTYPE", "AUTOMAPPING")

        # ---- 2. TABLE parameters ----
        config["sp_args"] = _parse_sp_args(params.get("SP_ARGS", []))

        # Datasource alias
        config["specify_datasource_alias"] = self._get_bool(node, "SPECIFY_DATASOURCE_ALIAS", False)
        config["datasource_alias"] = self._get_str(node, "DATASOURCE_ALIAS", "")

        # ---- 3. Advanced parameters ----
        config["properties"] = self._get_str(node, "PROPERTIES", "")
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["nls_language"] = self._get_str(node, "NLS_LANGUAGE", "NONE")
        config["nls_territory"] = self._get_str(node, "NLS_TERRITORY", "NONE")
        config["support_nls"] = self._get_bool(node, "SUPPORT_NLS", False)

        # ---- 4. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 5. Engine gap needs_review entries ----
        needs_review.append({
            "issue": (
                "No concrete engine implementation for tOracleSP. "
                "All config keys are extracted for future engine support."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 6. Build component dict and return ----
        component = self._build_component_dict(
            node=node,
            type_name="tOracleSP",
            config=config,
            schema={"input": self._parse_schema(node), "output": self._parse_schema(node)},
        )
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
