"""Converter for Talend tMSSqlInput component.

Reads data from a Microsoft SQL Server database using SQL queries.

Config mapping (20 params total):
  USE_EXISTING_CONNECTION    -> use_existing_connection (bool, default False)
  CONNECTION                 -> connection (str, default "")
  DRIVER                     -> driver (str, default "MSSQL_PROP")
  HOST                       -> host (str, default "")
  PORT                       -> port (str, default "1433")
  DB_SCHEMA                  -> schema_db (str, default "")
  DBNAME                     -> dbname (str, default "")
  USER                       -> user (str, default "")
  PASS                       -> password (str, default "", encrypted prefix stripped)
  QUERY                      -> query (str, default "select id, name from employee")
  SPECIFY_DATASOURCE_ALIAS   -> specify_datasource_alias (bool, default False)
  DATASOURCE_ALIAS           -> datasource_alias (str, default "")
  PROPERTIES                 -> properties (str, default "noDatetimeStringSync=true")
  ACTIVE_DIR_AUTH            -> active_dir_auth (bool, default False)
  ENCODING                   -> encoding (str, default "ISO-8859-15")
  TRIM_ALL_COLUMN            -> trim_all_column (bool, default False)
  TRIM_COLUMN                -> trim_column (list, default [])
  SET_QUERY_TIMEOUT          -> set_query_timeout (bool, default False)
  QUERY_TIMEOUT_IN_SECONDS   -> query_timeout_in_seconds (int, default 30)
  TSTATCATCHER_STATS         -> tstatcatcher_stats (bool, default False)
  LABEL                      -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

@REGISTRY.register("tMSSqlInput")
class MSSqlInputConverter(ComponentConverter):
    """Convert Talend tMSSqlInput to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["use_existing_connection"] = self._get_bool(node, "USE_EXISTING_CONNECTION", False)
        config["connection"] = self._get_str(node, "CONNECTION", "")
        config["driver"] = self._get_str(node, "DRIVER", "MSSQL_PROP")
        config["host"] = self._get_str(node, "HOST", "")
        config["port"] = self._get_str(node, "PORT", "1433")
        config["schema_db"] = self._get_str(node, "DB_SCHEMA", "")  # XML: DB_SCHEMA -> config: schema_db per D-30
        config["dbname"] = self._get_str(node, "DBNAME", "")
        config["user"] = self._get_str(node, "USER", "")
        config["password"] = self._extract_password(self._get_str(node, "PASS", ""), log_id=node.component_id)
        config["query"] = self._get_str(node, "QUERY", "select id, name from employee")

        # ---- 2. Datasource alias parameters ----
        config["specify_datasource_alias"] = self._get_bool(node, "SPECIFY_DATASOURCE_ALIAS", False)
        config["datasource_alias"] = self._get_str(node, "DATASOURCE_ALIAS", "")

        # ---- 3. Advanced parameters ----
        config["properties"] = self._get_str(node, "PROPERTIES", "noDatetimeStringSync=true")
        config["active_dir_auth"] = self._get_bool(node, "ACTIVE_DIR_AUTH", False)
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["trim_all_column"] = self._get_bool(node, "TRIM_ALL_COLUMN", False)
        config["trim_column"] = self._parse_trim_column(node.params.get("TRIM_COLUMN"))
        config["set_query_timeout"] = self._get_bool(node, "SET_QUERY_TIMEOUT", False)
        config["query_timeout_in_seconds"] = self._get_int(node, "QUERY_TIMEOUT_IN_SECONDS", 30)

        # ---- 4. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 5. Engine gap needs_review entries ----
        needs_review.append({
            "issue": (
                "No concrete engine implementation for tMSSqlInput. "
                "All config keys are extracted for future engine support."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 6. Build standard component dict (source: data flows OUT) ----
        component = self._build_component_dict(
            node=node,
            type_name="tMSSqlInput",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
    # ------------------------------------------------------------------
    # TRIM_COLUMN TABLE parser
    # ------------------------------------------------------------------

    @staticmethod
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
