"""Converter for Talend tSplitRow component.

Expands each input row into multiple output rows based on column mapping groups.
Each mapping group defines one output row using target column names and
source expressions (column references or literal values).

Config mapping (1 TABLE param + framework):
  COL_MAPPING -> col_mapping (list of group dicts)
    Each group: {target_col_name: source_expression, ...}
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: CONNECTION_FORMAT (not in _java.xml)

COL_MAPPING format in .item XML:
  Each <elementValue elementRef="target_col" value="source_expr"/>
  Groups are detected by repeated elementRef values (a new group starts
  when a target column name is seen again in the sequence).

  Example .item XML:
    elementRef="id"     value="row1.id"
    elementRef="Month"  value="&quot;Jan&quot;"   <- literal "Jan"
    elementRef="amount" value="row1.Jan"
    elementRef="id"     value="row1.id"          <- starts group 2
    elementRef="Month"  value="&quot;Feb&quot;"
    elementRef="amount" value="row1.Feb"

  Parsed output:
    [
      {"id": "row1.id", "Month": "\"Jan\"", "amount": "row1.Jan"},
      {"id": "row1.id", "Month": "\"Feb\"", "amount": "row1.Feb"},
    ]
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# TABLE parser
# ------------------------------------------------------------------
def _parse_col_mapping(raw: Any) -> List[Dict[str, str]]:
    """Parse COL_MAPPING TABLE into list of row-template group dicts.

    Each elementValue entry has:
      elementRef = target column name (output schema column)
      value      = source expression (e.g. "row1.colname" or '"literal"')

    A new group is detected when an elementRef value is seen again in the
    sequence.  Each completed group is appended to the result list.

    Returns:
        List of dicts, each mapping target column names to source expressions.
    """
    if not raw or not isinstance(raw, list):
        return []
    groups: List[Dict[str, str]] = []
    current_group: Dict[str, str] = {}
    seen_refs: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")
        if not ref:
            continue
        if ref in seen_refs:
            # Repeated target column signals start of a new group
            if current_group:
                groups.append(current_group)
            current_group = {}
            seen_refs = set()
        current_group[ref] = val
        seen_refs.add(ref)
    if current_group:
        groups.append(current_group)
    return groups


@REGISTRY.register("tSplitRow")
class SplitRowConverter(ComponentConverter):
    """Convert Talend tSplitRow to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters: COL_MAPPING TABLE ----
        config: Dict[str, Any] = {}
        raw_table = node.params.get("COL_MAPPING", [])
        config["col_mapping"] = _parse_col_mapping(raw_table)

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Schema: output schema from node metadata ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 4. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="SplitRow",
            config=config,
            schema=schema,
        )

        # ---- 5. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
