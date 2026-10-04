"""Converter for Talend tFilterRow to v2 FilterRows component.

Compiles Talend's stride-4 CONDITIONS table (INPUT_COLUMN, FUNCTION,
OPERATOR, RVALUE) into a single v2 DSL expression string. FUNCTION
pre-transforms are compiled to the corresponding DSL built-in function
(e.g. LOWER_CASE -> LOWER(col)), a clean upgrade from v1 which flagged
ALL FUNCTION values as engine gaps.

Config mapping:
  LOGICAL_OP + CONDITIONS -> condition (compiled v2 DSL expression)
  reject flow wired?     -> reject_output (bool)
  USE_ADVANCED           -> warning (UNSUPPORTED per D-09)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY as CONVERTER_REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# CONDITIONS TABLE constants
# ------------------------------------------------------------------
_CONDITION_FIELDS = ("INPUT_COLUMN", "FUNCTION", "OPERATOR", "RVALUE")
_CONDITION_GROUP_SIZE = len(_CONDITION_FIELDS)

# ------------------------------------------------------------------
# Talend FUNCTION -> v2 DSL function name mapping (D-07)
# ------------------------------------------------------------------
_FUNCTION_MAP: Dict[str, str] = {
    "": "",                    # no function pre-transform
    "LOWER_CASE": "LOWER",
    "UPPER_CASE": "UPPER",
    "TRIM": "TRIM",
    "TRIM_ALL": "TRIM",
    "LENGTH": "LENGTH",
    "ABS_VALUE": "ABS",
    "MATCH_REGEX": "REGEX_MATCH",
    "CONTAINS": "CONTAINS",
    "EMPTY": "",               # special-cased in _condition_to_expr
}

# ------------------------------------------------------------------
# Talend OPERATOR -> v2 DSL operator mapping
# ------------------------------------------------------------------
_OPERATOR_MAP: Dict[str, str] = {
    "==": "==",
    "!=": "!=",
    "<": "<",
    "<=": "<=",
    ">": ">",
    ">=": ">=",
}

# ------------------------------------------------------------------
# Talend LOGICAL_OP -> v2 DSL join operator
# ------------------------------------------------------------------
_LOGICAL_OP_MAP: Dict[str, str] = {
    "AND": "&&",
    "OR": "||",
    "&&": "&&",
    "||": "||",
}


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _strip_talend_quotes(value: str) -> str:
    """Strip surrounding double-quotes that Talend XML wraps around parameter values.

    Talend encodes string values as ``&quot;hello&quot;`` in XML which after
    XML parsing becomes ``"hello"`` (with literal surrounding double-quotes).
    This helper strips those outer quotes to produce ``hello``.

    Matches the v1 converter pattern (``filter_rows.py:69-75``) where ALL
    condition field values are ``.strip('"')``-ed.
    """
    return value.strip('"')


def _parse_conditions(raw: Any) -> List[Dict[str, str]]:
    """Parse CONDITIONS TABLE into list of dicts.

    Each group of 4 consecutive elementRef entries maps to one condition:
      INPUT_COLUMN -> column   (str)
      FUNCTION     -> function (str)
      OPERATOR     -> operator (str)
      RVALUE       -> value    (str)

    Incomplete trailing groups (< 4 entries) are skipped.
    All field values are run through ``_strip_talend_quotes`` to remove
    Talend's surrounding double-quotes before any further processing.
    """
    if not raw or not isinstance(raw, list):
        return []

    # Filter out entries not in the expected fields
    filtered = [
        entry for entry in raw
        if isinstance(entry, dict) and entry.get("elementRef", "") in _CONDITION_FIELDS
    ]

    result: List[Dict[str, str]] = []
    for i in range(0, len(filtered), _CONDITION_GROUP_SIZE):
        group = filtered[i: i + _CONDITION_GROUP_SIZE]
        if len(group) < _CONDITION_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            ref = entry.get("elementRef", "")
            val = _strip_talend_quotes(entry.get("value", ""))
            if ref == "INPUT_COLUMN":
                row["column"] = val
            elif ref == "FUNCTION":
                row["function"] = val
            elif ref == "OPERATOR":
                row["operator"] = val
            elif ref == "RVALUE":
                row["value"] = val
        if row:
            result.append(row)
    return result


def _format_value(val: str) -> str:
    """Format an RVALUE for the v2 DSL expression string.

    - Empty string -> ``''`` (empty string literal)
    - ``null`` (case-insensitive) -> ``null`` (DSL null keyword, unquoted)
    - Numeric value -> unquoted number
    - Otherwise -> single-quoted string literal for DSL
    """
    if val == "":
        return "''"
    if val.lower() == "null":
        return "null"
    try:
        float(val)
        return val
    except ValueError:
        return f"'{val}'"


def _condition_to_expr(cond: Dict[str, str]) -> Optional[str]:
    """Compile a single condition to a DSL expression fragment.

    Returns ``None`` if the FUNCTION is not supported, signalling the
    caller to emit an UNSUPPORTED warning.
    """
    col = cond.get("column", "")
    func = cond.get("function", "")
    op = cond.get("operator", "==")
    val = cond.get("value", "")

    # Map operator
    dsl_op = _OPERATOR_MAP.get(op, op)

    # EMPTY special case (D-07): column is null OR empty string
    # Respects operator: == means "is empty", != means "is NOT empty"
    if func == "EMPTY":
        empty_expr = f"ISNULL({col}) || {col} == ''"
        if op == "!=":
            return f"!({empty_expr})"
        return empty_expr

    # MATCH_REGEX special case: boolean result
    # Respects operator: != negates the match
    if func == "MATCH_REGEX":
        match_expr = f"REGEX_MATCH({col}, {_format_value(val)})"
        if op == "!=":
            return f"!({match_expr})"
        return match_expr

    # CONTAINS special case: boolean result
    # Respects operator: != means "does NOT contain"
    if func == "CONTAINS":
        contains_expr = f"CONTAINS({col}, {_format_value(val)})"
        if op == "!=":
            return f"!({contains_expr})"
        return contains_expr

    # Standard FUNCTION dispatch
    if func and func in _FUNCTION_MAP:
        dsl_func = _FUNCTION_MAP[func]
        if dsl_func:
            return f"{dsl_func}({col}) {dsl_op} {_format_value(val)}"
        # Empty mapping with non-empty func means it's handled above (EMPTY)
        # or not a real function -- fall through to no-function case
    elif func and func not in _FUNCTION_MAP:
        # Unsupported FUNCTION
        return None

    # No FUNCTION (empty/default): bare column comparison
    return f"{col} {dsl_op} {_format_value(val)}"


def _has_reject_connection(
    node: TalendNode, connections: list[TalendConnection],
) -> bool:
    """Return True if any outgoing connection from *node* is a REJECT flow."""
    return any(
        c.source == node.component_id and c.connector_type == "REJECT"
        for c in connections
    )


# ------------------------------------------------------------------
# Converter class
# ------------------------------------------------------------------


@CONVERTER_REGISTRY.register("tFilterRow", "tFilterRows")
class FilterRowsConverter(ComponentConverter):
    """Convert Talend tFilterRow to v2 filter_rows config."""

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        """Convert a TalendNode into a v2 FilterRows component dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Check USE_ADVANCED (D-09) ----
        use_advanced = node.params.get("USE_ADVANCED", False)
        if isinstance(use_advanced, str):
            use_advanced = use_advanced.lower() == "true"
        if use_advanced:
            advanced_cond = node.params.get("ADVANCED_COND", "")
            if isinstance(advanced_cond, str):
                advanced_cond = advanced_cond.strip('"')
            warnings.append(
                "Feature 'use_advanced' is UNSUPPORTED in v2: Freeform Java expressions "
                "cannot run in Polars. Rewrite as a v2 expression using supported DSL "
                f"functions. Original expression: {advanced_cond}"
            )
            needs_review.append({
                "issue": f"USE_ADVANCED condition cannot be converted: {advanced_cond}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 2. Parse CONDITIONS stride-4 ----
        raw_conditions = node.params.get("CONDITIONS", [])
        parsed = _parse_conditions(raw_conditions)

        # ---- 3. Compile to expression fragments ----
        fragments: List[str] = []
        for cond in parsed:
            expr_fragment = _condition_to_expr(cond)
            if expr_fragment is None:
                # Unsupported FUNCTION (D-08)
                func_name = cond.get("function", "")
                warnings.append(
                    f"FUNCTION '{func_name}' is UNSUPPORTED in v2 DSL. "
                    f"Rewrite condition on column '{cond.get('column', '')}' as a v2 expression."
                )
                needs_review.append({
                    "issue": f"Unsupported FUNCTION '{func_name}' in condition",
                    "component": node.component_id,
                    "severity": "engine_gap",
                })
            else:
                fragments.append(expr_fragment)

        # ---- 4. Join with LOGICAL_OP ----
        logical_op = node.params.get("LOGICAL_OP", "AND")
        if isinstance(logical_op, str):
            logical_op = _strip_talend_quotes(logical_op).upper()
        dsl_join = _LOGICAL_OP_MAP.get(logical_op, "&&")
        condition = f" {dsl_join} ".join(fragments) if fragments else "true"

        # ---- 5. Build config ----
        config: Dict[str, Any] = {"condition": condition}
        if _has_reject_connection(node, connections):
            config["reject_output"] = True

        # ---- 6. Introspection: UNSUPPORTED features ----
        try:
            from src.v2.components.capabilities import Support, get_supported_features
            from src.v2.components.transform.filter_rows import FilterRows

            features = get_supported_features(FilterRows)
            for feat_key, feat_support in features.items():
                if feat_support.support == Support.UNSUPPORTED:
                    param_name = feat_key.upper()
                    if node.params.get(param_name) and param_name not in (
                        "USE_ADVANCED", "ADVANCED_COND",
                    ):
                        warnings.append(
                            f"Feature '{feat_key}' is UNSUPPORTED in v2: {feat_support.note}"
                        )
        except ImportError:
            pass  # Graceful degradation if component not available

        # ---- 7. Build component dict ----
        component = {
            "id": node.component_id,
            "type": "filter_rows",
            "config": config,
        }

        # ---- 8. Build flows ----
        flows = self._build_simple_flows(node, connections)

        return ComponentResult(
            component=component,
            flows=flows,
            warnings=warnings,
            needs_review=needs_review,
        )
