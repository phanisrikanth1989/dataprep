"""Converter for Talend tRowGenerator component.

Generates rows with user-defined values and expressions.

Config mapping (2 unique params + framework):
  NB_ROWS -> nb_rows (str, hidden, default "100")
  VALUES  -> values  (list, TABLE stride-2 SCHEMA_COLUMN+ARRAY, BASED_ON_SCHEMA=true)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

MAP param (EXTERNAL type) is a visual editor reference -- not extracted.

Engine reads: nb_rows (as int), values (list), schema.output.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY
from ...expression_converter import ExpressionConverter

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants (VALUES TABLE -- stride-2, BASED_ON_SCHEMA=true)
# ------------------------------------------------------------------
_VALUES_FIELDS = ("SCHEMA_COLUMN", "ARRAY")
_VALUES_GROUP_SIZE = len(_VALUES_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_values(raw: Any) -> List[Dict[str, str]]:
    """Parse VALUES TABLE into list of {schema_column, array} dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN -> schema_column (str)
      ARRAY         -> array         (str)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _VALUES_GROUP_SIZE):
        group = raw[i : i + _VALUES_GROUP_SIZE]
        if len(group) < _VALUES_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                row["schema_column"] = val.strip('"')
            elif ref == "ARRAY":
                row["array"] = val.strip('"')
        if row:
            result.append(row)
    return result


@REGISTRY.register("tRowGenerator")
class RowGeneratorConverter(ComponentConverter):
    """Convert Talend tRowGenerator to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        config: Dict[str, Any] = {}

        # ---- 1. Core parameters ----
        config["nb_rows"] = self._get_str(node, "NB_ROWS", "100")

        # ---- 2. TABLE parameter ----
        values = _parse_values(node.params.get("VALUES", []))

        # Mark ARRAY expressions with {{java}} when they contain Java code
        for val in values:
            if "array" in val:
                val["array"] = ExpressionConverter.mark_java_expression(val["array"])

        config["values"] = values
        config["requires_java_bridge"] = True

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Schema: SOURCE pattern -- no input, output from FLOW ----
        schema = {"input": [], "output": self._parse_schema(node)}

        # ---- 5. Engine gap needs_review entries ----
        needs_review.append({
            "issue": (
                "tRowGenerator ARRAY expressions are Java code that must be "
                "executed via Java Bridge at runtime. Values containing Java "
                "expressions are marked with {{java}} prefix."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # Engine default mismatch: engine defaults nb_rows to 1, Talend to 100
        needs_review.append({
            "issue": (
                "Engine default for 'nb_rows' is 1 but Talend default is 100 "
                "-- when converter emits the Talend default, engine behavior "
                "matches; but if the config key is stripped, engine falls back "
                "to wrong default"
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # Engine reads schema from config['schema'] but _build_component_dict
        # places schema at top level -- engine path mismatch
        needs_review.append({
            "issue": (
                "Engine reads schema via self.config.get('schema', {}).get('output', []) "
                "but converter places schema at component['schema'] not inside config "
                "-- engine will not find output schema through its config path"
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 6. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="RowGenerator",
            config=config,
            schema=schema,
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
