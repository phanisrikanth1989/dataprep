"""Converter for Talend tFileInputXML component.

Reads XML files using XPath expressions with loop-based row extraction
and per-column MAPPING TABLE defining column/xpath/nodecheck triplets.

Config mapping (18 params total):
  FILENAME             -> filepath             (str, default "")
  LOOP_QUERY           -> loop_query           (str, default "/bills/bill/line")
  MAPPING              -> mapping              (TABLE, stride-3: SCHEMA_COLUMN + QUERY + NODECHECK)
  LIMIT                -> limit                (str, default "")
  DIE_ON_ERROR         -> die_on_error         (bool, default False)
  ADVANCED_SEPARATOR   -> advanced_separator   (bool, default False)
  THOUSANDS_SEPARATOR  -> thousands_separator  (str, default ",")
  DECIMAL_SEPARATOR    -> decimal_separator    (str, default ".")
  IGNORE_NS            -> ignore_ns            (bool, default False)
  IGNORE_DTD           -> ignore_dtd           (bool, default False)
  USE_SEPARATOR        -> use_separator        (bool, default False)
  FIELD_SEPARATOR      -> field_separator      (str, default ",")
  GENERATION_MODE      -> generation_mode      (str/CLOSED_LIST, default "Dom4j")
  CHECK_DATE           -> check_date           (bool, default False)
  ENCODING             -> encoding             (str, default "ISO-8859-15")
  --- framework ---
  TSTATCATCHER_STATS   -> tstatcatcher_stats   (bool, default False)
  LABEL                -> label                (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------

def _parse_mapping(raw: Any) -> List[Dict[str, Any]]:
    """Parse MAPPING TABLE from flat elementRef/value pairs.

    Uses "push-on-next-SCHEMA_COLUMN" state machine: accumulates all
    fields (SCHEMA_COLUMN, QUERY, NODECHECK) per row, flushes when the
    next SCHEMA_COLUMN arrives or at end of loop.

    Input (from XML parser):
        [{"elementRef": "SCHEMA_COLUMN", "value": '"order_id"'},
         {"elementRef": "QUERY", "value": '"@id"'},
         {"elementRef": "NODECHECK", "value": "false"},
         {"elementRef": "SCHEMA_COLUMN", "value": '"customer"'}, ...]

    Output:
        [{"column": "order_id", "xpath": "@id", "nodecheck": False},
         {"column": "customer", "xpath": "...", "nodecheck": ...}, ...]
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
            current = {"column": val, "xpath": "", "nodecheck": False}
        elif ref == "QUERY":
            current["xpath"] = val
        elif ref == "NODECHECK":
            current["nodecheck"] = val.lower() in ("true", "1")

    # Flush the last accumulated row
    if current and "column" in current:
        result.append(current)

    return result


@REGISTRY.register("tFileInputXML")
class FileInputXMLConverter(ComponentConverter):
    """Convert Talend tFileInputXML to v1 FileInputXML config."""

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
        config["filepath"] = self._get_str(node, "FILENAME", "")
        config["loop_query"] = self._get_str(node, "LOOP_QUERY", "/bills/bill/line")
        config["limit"] = self._get_str(node, "LIMIT", "")
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["ignore_ns"] = self._get_bool(node, "IGNORE_NS", False)
        config["ignore_dtd"] = self._get_bool(node, "IGNORE_DTD", False)

        # ---- 2. CLOSED_LIST parameters ----
        config["generation_mode"] = self._get_str(node, "GENERATION_MODE", "Dom4j")

        # ---- 3. TABLE parameters ----
        config["mapping"] = _parse_mapping(node.params.get("MAPPING", []))

        # ---- 4. Advanced parameters ----
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")
        config["check_date"] = self._get_bool(node, "CHECK_DATE", False)
        config["use_separator"] = self._get_bool(node, "USE_SEPARATOR", False)
        config["field_separator"] = self._get_str(node, "FIELD_SEPARATOR", ",")

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema ----
        schema = {"input": [], "output": self._parse_schema(node)}

        # ---- 7. Validation warnings ----
        if not config["filepath"]:
            warnings.append("FILENAME is empty -- this is a required parameter")
        if not config["loop_query"]:
            warnings.append("LOOP_QUERY is empty -- this is a required parameter")

        # ---- 8. Engine gap needs_review entries ----
        _engine_gap_keys = [
            ("generation_mode", "engine only supports Dom4j-style DOM processing; SAX mode not implemented"),
            ("advanced_separator", "engine does not support locale-aware number formatting for XML"),
            ("check_date", "engine does not validate date fields during XML extraction"),
            ("use_separator", "engine does not support field separator concatenation for XML"),
            ("field_separator", "engine does not read field_separator config key"),
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
            type_name="FileInputXML",
            config=config,
            schema=schema,
        )

        # ---- 10. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
