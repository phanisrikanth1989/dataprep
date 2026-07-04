"""Converter for Talend tFileInputJSON component.

Reads JSON files using JSONPath or XPath expressions for data extraction.
Supports three read modes: JSONPATH, XPATH, and JSONPATH_WITHOUTPUT_LOOP,
each with its own MAPPING TABLE variant.

Config mapping (17 params total):
  READ_BY              -> read_by              (str/CLOSED_LIST, default "JSONPATH")
  JSON_PATH_VERSION    -> json_path_version    (str/CLOSED_LIST, default "2_1_0")
  USEURL               -> useurl               (bool, default False)
  URLPATH              -> urlpath              (str, default "")
  FILENAME             -> filename             (str, default "")
  LOOP_QUERY           -> loop_query           (str, default "/bills/bill/line")
  JSON_LOOP_QUERY      -> json_loop_query      (str, default "$.bills.bill.line[*]")
  MAPPING              -> mapping              (TABLE for JSONPATH_WITHOUTPUT_LOOP mode)
  MAPPING_JSONPATH     -> mapping              (TABLE for JSONPATH mode)
  MAPPINGXPATH         -> mapping              (TABLE for XPATH mode, with NODECHECK)
  DIE_ON_ERROR         -> die_on_error         (bool, default False)
  ADVANCED_SEPARATOR   -> advanced_separator   (bool, default False)
  THOUSANDS_SEPARATOR  -> thousands_separator  (str, default ",")
  DECIMAL_SEPARATOR    -> decimal_separator    (str, default ".")
  CHECK_DATE           -> check_date           (bool, default False)
  USE_LOOP_AS_ROOT     -> use_loop_as_root     (bool, default True)
  ENCODING             -> encoding             (str, default "UTF-8")
  --- framework ---
  TSTATCATCHER_STATS   -> tstatcatcher_stats   (bool, default False)
  LABEL                -> label                (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY
from ...expression_converter import ExpressionConverter

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------

def _parse_mapping(raw: Any, include_nodecheck: bool = False) -> List[Dict[str, Any]]:
    """Parse MAPPING TABLE from flat elementRef/value pairs.

    Uses "push-on-next-SCHEMA_COLUMN" state machine: accumulates all
    fields (SCHEMA_COLUMN, QUERY, NODECHECK) per row, flushes when the
    next SCHEMA_COLUMN arrives or at end of loop.

    Input (from XML parser):
        [{"elementRef": "SCHEMA_COLUMN", "value": "user_id"},
         {"elementRef": "QUERY", "value": '"$.id"'},
         {"elementRef": "NODECHECK", "value": "false"},  # only in MAPPINGXPATH
         {"elementRef": "SCHEMA_COLUMN", "value": "username"}, ...]

    Output:
        [{"column": "user_id", "jsonpath": "$.id", "nodecheck": False}, ...]
    """
    if not raw or not isinstance(raw, list):
        return []

    result: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}

    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "").strip('"')

        if ref == "SCHEMA_COLUMN":
            # Flush previous row when we hit a new SCHEMA_COLUMN
            if current and "column" in current:
                result.append(current)
            current = {"column": val, "jsonpath": ""}
            if include_nodecheck:
                current["nodecheck"] = False
        elif ref == "QUERY":
            current["jsonpath"] = val
        elif ref == "NODECHECK" and include_nodecheck:
            current["nodecheck"] = val.lower() in ("true", "1")

    # Flush the last accumulated row
    if current and "column" in current:
        result.append(current)

    return result


@REGISTRY.register("tFileInputJSON")
class FileInputJSONConverter(ComponentConverter):
    """Convert Talend tFileInputJSON to v1 FileInputJSON config."""

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
        config["filename"] = ExpressionConverter.mark_java_expression(
            self._get_str(node, "FILENAME", "")
        )
        config["encoding"] = self._get_str(node, "ENCODING", "UTF-8")

        # ---- 2. CLOSED_LIST parameters ----
        config["read_by"] = self._get_str(node, "READ_BY", "JSONPATH")
        config["json_path_version"] = self._get_str(node, "JSON_PATH_VERSION", "2_1_0")

        # ---- 3. Mode-dependent parameters ----
        config["useurl"] = self._get_bool(node, "USEURL", False)
        config["urlpath"] = self._get_str(node, "URLPATH", "")
        config["loop_query"] = self._get_str(node, "LOOP_QUERY", "/bills/bill/line")
        config["json_loop_query"] = self._get_str(node, "JSON_LOOP_QUERY", "$.bills.bill.line[*]")

        # ---- 4. TABLE parameters (mode-dependent MAPPING variants) ----
        read_by = config["read_by"]
        if read_by == "XPATH":
            config["mapping"] = _parse_mapping(
                node.params.get("MAPPINGXPATH", []), include_nodecheck=True
            )
        elif read_by == "JSONPATH_WITHOUTPUT_LOOP":
            config["mapping"] = _parse_mapping(
                node.params.get("MAPPING", [])
            )
        else:
            # Default: JSONPATH mode
            config["mapping"] = _parse_mapping(
                node.params.get("MAPPING_JSONPATH", [])
            )

        # ---- 5. Advanced parameters ----
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")
        config["check_date"] = self._get_bool(node, "CHECK_DATE", False)
        config["use_loop_as_root"] = self._get_bool(node, "USE_LOOP_AS_ROOT", True)

        # ---- 6. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 7. Schema ----
        schema = {"input": [], "output": self._parse_schema(node)}

        # ---- 8. Engine gap needs_review entries ----
        _engine_gap_keys = [
            ("loop_query", "engine only supports JSONPATH mode via json_loop_query; XPath loop_query is ignored"),
            ("json_path_version", "engine reads this key but never uses it in processing logic"),
            ("use_loop_as_root", "engine default is False but Talend default is True -- behavioral mismatch"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 9. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileInputJSON",
            config=config,
            schema=schema,
        )

        # ---- 10. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
