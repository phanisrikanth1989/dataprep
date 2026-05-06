"""Converter for Talend tExtractXMLField component.

tExtractXMLField extracts structured data from an XML column by applying an
XPath loop query and mapping individual XPath expressions to output columns.

Config mapping (12 unique params):
  XMLFIELD         -> xmlfield (str, PREV_COLUMN_LIST, default "")
  LOOP_QUERY       -> loop_query (str, default "/bills/bill/line")
  MAPPING          -> mapping (list, TABLE BASED_ON_SCHEMA=true, SCHEMA_COLUMN+QUERY+NODECHECK)
  LIMIT            -> limit (str, default "")
  DIE_ON_ERROR     -> die_on_error (bool, default False)
  IGNORE_NS        -> ignore_ns (bool, default False)
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# MAPPING TABLE constants (BASED_ON_SCHEMA=true: SCHEMA_COLUMN + QUERY + NODECHECK)
# ------------------------------------------------------------------
_MAPPING_FIELDS = ("SCHEMA_COLUMN", "QUERY", "NODECHECK")
_MAPPING_GROUP_SIZE = len(_MAPPING_FIELDS)


# ------------------------------------------------------------------
# MAPPING TABLE parser (module-level, stride-3)
# ------------------------------------------------------------------
def _parse_mapping(raw: Any) -> List[Dict[str, Any]]:
    """Parse MAPPING TABLE into list of dicts.

    Despite BASED_ON_SCHEMA=true, Talend still writes SCHEMA_COLUMN to the XML.
    Each stride-3 group contains:
      SCHEMA_COLUMN  -> schema_column (str, column name from output schema)
      QUERY          -> query (str, XPath expression, stripped of outer quotes)
      NODECHECK      -> nodecheck (bool)

    An empty QUERY means "passthrough from input row" -- the column value is
    carried through from the upstream flow unchanged (no XPath evaluation).

    Incomplete trailing groups (< 3 entries) are skipped.
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
            if ref == "SCHEMA_COLUMN":
                row["schema_column"] = val
            elif ref == "QUERY":
                row["query"] = val.strip('"')
            elif ref == "NODECHECK":
                row["nodecheck"] = val.lower() in ("true", "1")
        if row.get("schema_column") is not None:
            result.append({
                "schema_column": row.get("schema_column", ""),
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
        config["loop_query"] = self._get_str(node, "LOOP_QUERY", "/bills/bill/line")
        config["limit"] = self._get_str(node, "LIMIT", "")
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)
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

        # ---- 5. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="ExtractXMLField",
            config=config,
            schema=schema,
        )

        # ---- 6. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
