"""Converter for Talend tFilterRow component.

Filters rows based on conditions or advanced expressions.

Config mapping (4 params + framework):
  LOGICAL_OP    -> logical_op    (str, CLOSED_LIST, default "AND")
  CONDITIONS    -> conditions    (list of dicts, stride-4 TABLE)
    INPUT_COLUMN -> column   (str)
    FUNCTION     -> function (str)
    OPERATOR     -> operator (str)
    RVALUE       -> value    (str)
  USE_ADVANCED  -> use_advanced  (bool, CHECK, default False)
  ADVANCED_COND -> advanced_cond (str, MEMO_JAVA, default "")
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: DIE_ON_ERROR (not in _java.xml), PREFILTER (not a _java.xml column in CONDITIONS TABLE)
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# CONDITIONS TABLE constants
# ------------------------------------------------------------------
_CONDITION_FIELDS = ("INPUT_COLUMN", "FUNCTION", "OPERATOR", "RVALUE")
_CONDITION_GROUP_SIZE = len(_CONDITION_FIELDS)


# ------------------------------------------------------------------
# Talend FUNCTION Java template -> engine keyword translation
# ------------------------------------------------------------------
# Talend stores FUNCTION as Java code templates. The engine expects
# simple keywords (LOWER, UPPER, etc.). This map translates known
# Talend templates to engine-compatible function names.
#
# Detection is done by matching distinctive substrings in the Java
# template, ordered from most specific to least specific.

_FUNCTION_TEMPLATE_PATTERNS: List[tuple] = [
    # String functions -- more specific patterns MUST come before generic ones
    (".toLowerCase().charAt(0)",    "LOWER_FIRST"),
    (".toUpperCase().charAt(0)",    "UPPER_FIRST"),
    (".toLowerCase()",              "LOWER"),
    (".toUpperCase()",              "UPPER"),
    (".trim().compareTo(",          "TRIM"),
    ('replaceAll("^\\\\s+","")',    "LTRIM"),
    ("replaceAll(\"^\\\\s+\",\"\")", "LTRIM"),
    ('replaceAll("\\\\s+$","")',    "RTRIM"),
    ("replaceAll(\"\\\\s+$\",\"\")", "RTRIM"),
    (".length()",                   "LENGTH"),
    # Numeric functions (int/float/double)
    ("Math.abs(",                   "ABS"),
    # BigDecimal absolute value
    (".abs().compareTo(",           "ABS"),
]


def _translate_function(raw_function: str) -> str:
    """Translate a Talend FUNCTION Java template to an engine keyword.

    Args:
        raw_function: The raw FUNCTION value from the Talend XML.
            May be empty, a simple keyword, or a full Java template.

    Returns:
        Engine-compatible function keyword (e.g. "LOWER", "ABS", "")
        or the original string if no translation is found.
    """
    if not raw_function:
        return ""

    # Already a simple keyword (e.g. manually edited JSON)
    upper = raw_function.upper().strip()
    if upper in ("", "LOWER", "UPPER", "LOWER_FIRST", "UPPER_FIRST", "LENGTH", "TRIM", "LTRIM", "RTRIM", "ABS"):
        return upper

    # Match against known Talend Java template patterns
    for pattern, keyword in _FUNCTION_TEMPLATE_PATTERNS:
        if pattern in raw_function:
            return keyword

    # Unrecognized — return as-is and let engine handle/warn
    logger.warning(
        "Unrecognized tFilterRow FUNCTION template, passing through: %r",
        raw_function,
    )
    return raw_function


# ------------------------------------------------------------------
# CONDITIONS TABLE parser
# ------------------------------------------------------------------
def _parse_conditions(raw: Any) -> List[Dict[str, str]]:
    """Parse CONDITIONS TABLE into list of dicts.

    Each group of 4 consecutive elementRef entries maps to one condition:
      INPUT_COLUMN -> column   (str)
      FUNCTION     -> function (str)
      OPERATOR     -> operator (str)
      RVALUE       -> value    (str)

    Incomplete trailing groups (< 4 entries) are skipped.
    PREFILTER entries are ignored (phantom -- not in _java.xml).
    """
    if not raw or not isinstance(raw, list):
        return []

    # Filter out any PREFILTER entries (phantom param)
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
            val = entry.get("value", "")
            if ref == "INPUT_COLUMN":
                row["column"] = val.strip('"')
            elif ref == "FUNCTION":
                row["function"] = _translate_function(val.strip('"'))
            elif ref == "OPERATOR":
                row["operator"] = val.strip('"')
            elif ref == "RVALUE":
                row["value"] = val.strip('"')
        if row:
            result.append(row)
    return result


@REGISTRY.register("tFilterRow")
@REGISTRY.register("tFilterRows")
class FilterRowsConverter(ComponentConverter):
    """Convert Talend tFilterRow / tFilterRows to v1 FilterRows config."""

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
        config["logical_op"] = self._get_str(node, "LOGICAL_OP", "AND")
        config["use_advanced"] = self._get_bool(node, "USE_ADVANCED", False)
        advanced_cond = self._get_str(node, "ADVANCED_COND", "")
        if advanced_cond:
            advanced_cond = "{{java}}" + advanced_cond
        config["advanced_cond"] = advanced_cond

        # ---- 2. TABLE parameters ----
        raw_conditions = node.params.get("CONDITIONS", [])
        config["conditions"] = _parse_conditions(raw_conditions)

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Schema (transform passthrough) ----
        # tFilterRow has up to three connector schemas in the XML:
        #   FLOW   -- inherited input layout (fallback)
        #   FILTER -- rows that pass the condition (same columns as input)
        #   REJECT -- rows that fail, with an extra `errorMessage` column
        # Emit a per-connector `outputs` map so downstream components on the
        # REJECT path receive the errorMessage column via schema propagation.
        flow_cols = self._parse_schema(node, connector="FLOW")
        filter_cols = self._parse_schema(node, connector="FILTER") or flow_cols
        reject_cols = self._parse_schema(node, connector="REJECT") or flow_cols
        schema = {
            "input": flow_cols,
            "output": filter_cols,
            "outputs": {
                "FILTER": filter_cols,
                "REJECT": reject_cols,
            },
        }

        # ---- 5. Engine gap needs_review entries ----
        # ENG-WR-08: removed the stale "engine uses eval()" claim (FALSE as of Phase 6).
        # The engine uses java_bridge.execute_tmap_preprocessing for advanced_cond evaluation.
        # Also removed the "no FUNCTION support" claim -- the engine has _FUNCTION_MAP
        # supporting LOWER/UPPER/TRIM/LTRIM/RTRIM/ABS/LENGTH/LEFT/RIGHT.
        # No current engine gaps require needs_review entries for this component.

        # ---- 6. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FilterRows",
            config=config,
            schema=schema,
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
