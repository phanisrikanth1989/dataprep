"""Converter for Talend tExtractXMLField component.

tExtractXMLField extracts structured data from an XML column by applying an
XPath loop query and mapping individual XPath expressions to output columns.

Config mapping (12 unique params):
  XMLFIELD         -> xmlfield (str, PREV_COLUMN_LIST, default "")
  USE_ITEMS        -> use_items (bool, hidden, default False)
  LOOP_QUERY_BASE  -> loop_query_base (str, hidden, default "")
  LOOP_QUERY       -> loop_query (str, default "/bills/bill/line")
  MAPPING          -> mapping (list, TABLE BASED_ON_SCHEMA=true, QUERY+NODECHECK)
  LIMIT            -> limit (str, default "")
  DIE_ON_ERROR     -> die_on_error (bool, default False)
  USE_XML_FIELD    -> use_xml_field (bool, hidden, default False)
  XML_TEXT         -> xml_text (str, hidden, default "")
  XML_PREFIX       -> xml_prefix (str, hidden, default "")
  SCHEMA_OPT_NUM   -> schema_opt_num (str, hidden, default "100")
  IGNORE_NS        -> ignore_ns (bool, default False)
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# MAPPING TABLE constants (BASED_ON_SCHEMA=true: QUERY + NODECHECK)
# ------------------------------------------------------------------
_MAPPING_FIELDS = ("QUERY", "NODECHECK")
_MAPPING_GROUP_SIZE = len(_MAPPING_FIELDS)


# ------------------------------------------------------------------
# MAPPING TABLE parser (module-level, stride-2)
# ------------------------------------------------------------------
def _parse_mapping(raw: Any) -> List[Dict[str, Any]]:
    """Parse MAPPING TABLE into list of dicts.

    BASED_ON_SCHEMA=true means SCHEMA_COLUMN is auto-populated from schema,
    so each stride-2 group contains:
      QUERY      -> query (str, stripped)
      NODECHECK  -> nodecheck (bool)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _MAPPING_GROUP_SIZE):
        group = raw[i: i + _MAPPING_GROUP_SIZE]
        if len(group) < _MAPPING_GROUP_SIZE:
            break
        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "QUERY":
                row["query"] = val.strip('"')
            elif ref == "NODECHECK":
                row["nodecheck"] = val.lower() in ("true", "1")
        if row.get("query") is not None:
            result.append({
                "query": row.get("query", ""),
                "nodecheck": row.get("nodecheck", False),
            })
    return result


@REGISTRY.register("tExtractXMLField")
class ExtractXMLFieldConverter(ComponentConverter):
    """Convert Talend tExtractXMLField to v1 engine config."""

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
        config["xmlfield"] = self._get_str(node, "XMLFIELD", "")
        config["use_items"] = self._get_bool(node, "USE_ITEMS", False)
        config["loop_query_base"] = self._get_str(node, "LOOP_QUERY_BASE", "")
        config["loop_query"] = self._get_str(node, "LOOP_QUERY", "/bills/bill/line")
        config["limit"] = self._get_str(node, "LIMIT", "")
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)
        config["use_xml_field"] = self._get_bool(node, "USE_XML_FIELD", False)
        config["xml_text"] = self._get_str(node, "XML_TEXT", "")
        config["xml_prefix"] = self._get_str(node, "XML_PREFIX", "")
        config["schema_opt_num"] = self._get_str(node, "SCHEMA_OPT_NUM", "100")
        config["ignore_ns"] = self._get_bool(node, "IGNORE_NS", False)

        # ---- 2. TABLE parameters ----
        raw_mapping = node.params.get("MAPPING", [])
        config["mapping"] = _parse_mapping(raw_mapping)

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Schema (transform passthrough) ----
        schema_cols = self._parse_schema(node)
        schema: Dict[str, Any] = {"input": schema_cols, "output": schema_cols}

        # ---- 5. Engine gap needs_review entries (per-feature) ----
        _engine_gap_keys = [
            ("use_items", "engine does not read 'use_items' config key -- hidden param for item-based XML input mode"),
            ("loop_query_base", "engine does not read 'loop_query_base' config key -- hidden base path for loop query"),
            ("use_xml_field", "engine does not read 'use_xml_field' config key -- hidden toggle for XML field source"),
            ("xml_text", "engine does not read 'xml_text' config key -- hidden inline XML text content"),
            ("xml_prefix", "engine does not read 'xml_prefix' config key -- hidden namespace prefix override"),
            ("schema_opt_num", "engine does not read 'schema_opt_num' config key -- hidden schema optimization number"),
            ("limit", "engine treats limit=0 as 'no limit' but Talend treats 0 as 'read nothing' -- semantic mismatch"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}" if "engine treats" not in detail else detail,
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 6. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="ExtractXMLField",
            config=config,
            schema=schema,
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
