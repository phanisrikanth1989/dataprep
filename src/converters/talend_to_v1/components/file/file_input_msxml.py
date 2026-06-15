"""Converter for Talend tFileInputMSXML component.

Parses XML-based file input with XPath-mapped schema columns using
Microsoft XML parsing (MSXML). Supports DOM4J and SAX generation modes.

Config mapping (12 params total):
  FILENAME           -> filename           (str, default "")
  ROOT_LOOP_QUERY    -> root_loop_query    (str, default "/mailbox/emails/email")
  IGNORE_ORDER       -> ignore_order       (bool, default False)
  SCHEMAS            -> schemas            (TABLE stride-3, parsed)
  DIE_ON_ERROR       -> die_on_error       (bool, default False)
  TRIMALL            -> trim_all           (bool, default True)
  CHECK_DATE         -> check_date         (bool, default False)
  IGNORE_DTD         -> ignore_dtd         (bool, default False)
  GENERATION_MODE    -> generation_mode    (str/CLOSED_LIST, default "DOM4J")
  ENCODING           -> encoding           (str, default "ISO-8859-15")
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY
from ...expression_converter import ExpressionConverter

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_SCHEMAS_FIELDS = ("LOOP_PATH", "MAPPING", "CREATE_EMPTY_ROW")
_SCHEMAS_GROUP_SIZE = len(_SCHEMAS_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_schemas(raw: Any) -> List[Dict[str, Any]]:
    """Parse SCHEMAS TABLE into list of dicts.

    Each group of 3 consecutive elementRef entries maps to one row:
      LOOP_PATH        -> loop_path (str, strip quotes)
      MAPPING          -> mapping (str, strip quotes)
      CREATE_EMPTY_ROW -> create_empty_row (bool)

    Incomplete trailing groups (< 3 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _SCHEMAS_GROUP_SIZE):
        group = raw[i: i + _SCHEMAS_GROUP_SIZE]
        if len(group) < _SCHEMAS_GROUP_SIZE:
            break
        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "LOOP_PATH":
                row["loop_path"] = val.strip('"')
            elif ref == "MAPPING":
                row["mapping"] = val.strip('"')
            elif ref == "CREATE_EMPTY_ROW":
                row["create_empty_row"] = val.lower() in ("true", "1")
        if row:
            result.append(row)
    return result


@REGISTRY.register("tFileInputMSXML")
class FileInputMSXMLConverter(ComponentConverter):
    """Convert Talend tFileInputMSXML to v1 engine config."""

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
        config["root_loop_query"] = self._get_str(node, "ROOT_LOOP_QUERY", "/mailbox/emails/email")
        config["ignore_order"] = self._get_bool(node, "IGNORE_ORDER", False)
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)
        config["trim_all"] = self._get_bool(node, "TRIMALL", True)  # _java.xml default is true
        config["check_date"] = self._get_bool(node, "CHECK_DATE", False)
        config["ignore_dtd"] = self._get_bool(node, "IGNORE_DTD", False)

        # ---- 2. CLOSED_LIST parameters ----
        config["generation_mode"] = self._get_str(node, "GENERATION_MODE", "DOM4J")
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")  # _java.xml default

        # ---- 3. TABLE parameters ----
        raw_schemas = node.params.get("SCHEMAS", [])
        config["schemas"] = _parse_schemas(raw_schemas)

        # ---- 4. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 5. Schema (source component: output only) ----
        schema = {"input": [], "output": self._parse_schema(node)}

        # ---- 6. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tFileInputMSXML",  # No engine -- use Talend name per D-43
            config=config,
            schema=schema,
        )

        # ---- 7. Engine gap needs_review entries ----
        # Single consolidated entry per D-37 (no engine implementation)
        needs_review.append({
            "issue": "No concrete engine implementation for tFileInputMSXML -- all config keys are extracted for future engine support.",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 8. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
