"""Converter for Talend tExtractJSONFields component.

tExtractJSONFields extracts values from a JSON string column in the input
using JSONPath or XPath queries, mapping them to output schema columns.

Config mapping (15 params total):
  READ_BY              -> read_by (str, CLOSED_LIST, default "JSONPATH")
  JSON_PATH_VERSION    -> json_path_version (str, CLOSED_LIST, default "2_1_0")
  JSONFIELD            -> jsonfield (str, PREV_COLUMN_LIST, default "")
  LOOP_QUERY           -> loop_query (str, default "/bills/bill/line")
  JSON_LOOP_QUERY      -> json_loop_query (str, default "$.bills.bill.line[*]")
  MAPPING              -> mapping (list, TABLE stride-4 SCHEMA_COLUMN+QUERY+NODECHECK+ISARRAY, XPath mode)
  MAPPING_4_JSONPATH   -> mapping_4_jsonpath (list, TABLE stride-2, JSONPath mode)
  DIE_ON_ERROR         -> die_on_error (bool, default False)
  ENCODING             -> encoding (str, default "UTF-8")
  USE_LOOP_AS_ROOT     -> use_loop_as_root (bool, default True)
  TSTATCATCHER_STATS   -> tstatcatcher_stats (bool, framework, default False)
  LABEL                -> label (str, framework, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants for MAPPING (XPath mode) -- stride-4
# ------------------------------------------------------------------
_XPATH_MAPPING_FIELDS = ("SCHEMA_COLUMN", "QUERY", "NODECHECK", "ISARRAY")
_XPATH_MAPPING_GROUP_SIZE = len(_XPATH_MAPPING_FIELDS)

# ------------------------------------------------------------------
# TABLE constants for MAPPING_4_JSONPATH -- stride-2
# ------------------------------------------------------------------
_JSONPATH_MAPPING_FIELDS = ("SCHEMA_COLUMN", "QUERY")
_JSONPATH_MAPPING_GROUP_SIZE = len(_JSONPATH_MAPPING_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions (module-level, prefixed with underscore)
# ------------------------------------------------------------------


def _parse_mapping_xpath(raw: Any) -> List[Dict[str, Any]]:
    """Parse MAPPING TABLE (XPath mode) into list of dicts.

    Each group of 4 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN -> schema_column (str, column name)
      QUERY         -> query (str, XPath expression; empty = passthrough)
      NODECHECK     -> nodecheck (bool, default False)
      ISARRAY       -> isarray (bool, default False)

    Incomplete trailing groups (< 4 entries) are skipped.
    Empty QUERY is valid -- it means copy from the input row (passthrough).
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _XPATH_MAPPING_GROUP_SIZE):
        group = raw[i: i + _XPATH_MAPPING_GROUP_SIZE]
        if len(group) < _XPATH_MAPPING_GROUP_SIZE:
            break
        row: Dict[str, Any] = {"schema_column": "", "query": "", "nodecheck": False, "isarray": False}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                row["schema_column"] = val.strip('"')
            elif ref == "QUERY":
                row["query"] = val.strip('"')
            elif ref == "NODECHECK":
                row["nodecheck"] = val.lower() in ("true", "1")
            elif ref == "ISARRAY":
                row["isarray"] = val.lower() in ("true", "1")
        if row["schema_column"]:
            result.append(row)
    return result


def _parse_mapping_jsonpath(raw: Any) -> List[Dict[str, str]]:
    """Parse MAPPING_4_JSONPATH TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN     -> schema_column (str)
      QUERY/JSON_PATH_QUERY -> query (str, JSONPath expression)

    Both QUERY (canonical _java.xml) and JSON_PATH_QUERY (legacy .item)
    elementRef names are accepted for the query field.

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _JSONPATH_MAPPING_GROUP_SIZE):
        group = raw[i: i + _JSONPATH_MAPPING_GROUP_SIZE]
        if len(group) < _JSONPATH_MAPPING_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                row["schema_column"] = val.strip('"')
            elif ref in ("QUERY", "JSON_PATH_QUERY"):
                row["query"] = val.strip('"')
        if row.get("schema_column"):
            result.append({
                "schema_column": row.get("schema_column", ""),
                "query": row.get("query", ""),
            })
    return result


@REGISTRY.register("tExtractJSONFields")
class ExtractJSONFieldsConverter(ComponentConverter):
    """Convert a Talend tExtractJSONFields node to v1 ExtractJSONFields."""

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
        config["read_by"] = self._get_str(node, "READ_BY", "JSONPATH")
        config["json_path_version"] = self._get_str(node, "JSON_PATH_VERSION", "2_1_0")
        config["jsonfield"] = self._get_str(node, "JSONFIELD", "")
        config["loop_query"] = self._get_str(node, "LOOP_QUERY", "/bills/bill/line")
        config["json_loop_query"] = self._get_str(node, "JSON_LOOP_QUERY", "$.bills.bill.line[*]")

        # ---- 2. TABLE parameters ----
        # XPath mode: MAPPING with stride-3 (QUERY, NODECHECK, ISARRAY)
        config["mapping"] = _parse_mapping_xpath(node.params.get("MAPPING"))

        # JSONPath mode: MAPPING_4_JSONPATH with stride-2 (SCHEMA_COLUMN, QUERY)
        config["mapping_4_jsonpath"] = _parse_mapping_jsonpath(node.params.get("MAPPING_4_JSONPATH"))

        # ---- 3. Boolean / other parameters ----
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)
        config["encoding"] = self._get_str(node, "ENCODING", "UTF-8")
        config["use_loop_as_root"] = self._get_bool(node, "USE_LOOP_AS_ROOT", True)

        # ---- 4. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 5. Schema: transform passthrough ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 6. Engine gap needs_review entries ----
        # Engine reads: read_by, jsonfield, json_loop_query, use_loop_as_root,
        #   mapping, mapping_4_jsonpath, die_on_error
        # Engine does NOT read the following config keys:
        _engine_gap_keys = [
            ("json_path_version", "Engine does not read 'json_path_version' config key"),
            ("encoding", "Engine does not read 'encoding' config key"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"{detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 7. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="ExtractJSONFields",
            config=config,
            schema=schema,
        )

        # ---- 8. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
