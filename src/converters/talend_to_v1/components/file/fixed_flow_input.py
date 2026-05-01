"""Converter for Talend tFixedFlowInput component.

tFixedFlowInput generates fixed rows of data. Supports three modes:
single mode (VALUES table), inline table mode (INTABLE table), and
inline content mode (delimited text with separators).

Config mapping (10 params total, 8 unique + 2 framework):
  NB_ROWS            -> nb_rows            (int, default 1)
  USE_SINGLEMODE     -> use_singlemode     (bool/RADIO, default True)
  VALUES             -> values_config      (TABLE stride-2: SCHEMA_COLUMN, VALUE)
  USE_INTABLE        -> use_intable        (bool/RADIO, default False)
  INTABLE            -> intable            (TABLE, raw entries)
  USE_INLINECONTENT  -> use_inlinecontent  (bool/RADIO, default False)
  ROWSEPARATOR       -> row_separator      (str, default "\\n")
  FIELDSEPARATOR     -> field_separator    (str, default ";")
  INLINECONTENT      -> inline_content     (str, default "")
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
_VALUES_FIELDS = ("SCHEMA_COLUMN", "VALUE")
_VALUES_GROUP_SIZE = len(_VALUES_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_values(raw: Any) -> List[Dict[str, Any]]:
    """Parse VALUES TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN -> schema_column (str)
      VALUE         -> value (str, quotes stripped)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _VALUES_GROUP_SIZE):
        group = raw[i: i + _VALUES_GROUP_SIZE]
        if len(group) < _VALUES_GROUP_SIZE:
            break
        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                row["schema_column"] = val.strip('"')
            elif ref == "VALUE":
                stripped = val.strip('"')
                row["value"] = ExpressionConverter.mark_java_expression(stripped)
        if row:
            result.append(row)
    return result


def _parse_intable(raw: Any) -> List[Dict[str, Any]]:
    """Parse INTABLE TABLE into list of dicts.

    INTABLE has a dynamic schema (one elementRef per schema column).
    Each entry is preserved as {element_ref, value} with quotes stripped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")
        result.append({
            "element_ref": ref,
            "value": val.strip('"'),
        })
    return result


@REGISTRY.register("tFixedFlowInput")
class FixedFlowInputConverter(ComponentConverter):
    """Convert Talend tFixedFlowInput to v1 engine config."""

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
        config["nb_rows"] = self._get_int(node, "NB_ROWS", 1)
        config["use_singlemode"] = self._get_bool(node, "USE_SINGLEMODE", True)
        config["use_intable"] = self._get_bool(node, "USE_INTABLE", False)
        config["use_inlinecontent"] = self._get_bool(node, "USE_INLINECONTENT", False)
        config["row_separator"] = self._get_str(node, "ROWSEPARATOR", "\\n")
        config["field_separator"] = self._get_str(node, "FIELDSEPARATOR", ";")
        config["inline_content"] = self._get_str(node, "INLINECONTENT", "")

        # ---- 2. TABLE parameters ----
        raw_values = node.params.get("VALUES", [])
        config["values_config"] = _parse_values(raw_values)

        raw_intable = node.params.get("INTABLE", [])
        config["intable"] = _parse_intable(raw_intable)

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Schema ----
        schema = {"input": [], "output": self._parse_schema(node)}

        # ---- 5. Engine gap needs_review entries ----
        # Engine reads 'die_on_error' but param is not in _java.xml -- engine has hardcoded behavior
        needs_review.append({
            "issue": "Engine reads 'die_on_error' config key but DIE_ON_ERROR is not in _java.xml -- "
                     "engine default (True) applies without converter extraction",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 6. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FixedFlowInputComponent",
            config=config,
            schema=schema,
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
