"""Converter for Talend tSetGlobalVar component."""
import re
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# Patterns that indicate a Java expression the engine cannot evaluate.
# The engine only handles values starting with "new " (constructor calls).
_JAVA_EXPR_PATTERNS = [
    ".get(", ".equals(", ".toString(", ".valueOf(",
    ".substring(", ".indexOf(", ".trim()", ".length()",
]

_CONTEXT_REF_RE = re.compile(r"\bcontext\.\w")


@REGISTRY.register("tSetGlobalVar")
class SetGlobalVarConverter(ComponentConverter):
    """Convert a Talend tSetGlobalVar node into a v1 SetGlobalVar component.

    The VARIABLES TABLE param contains interleaved KEY/VALUE elementValue
    entries.  Each KEY/VALUE pair is collected into a ``{name, value}`` dict.
    """

    @staticmethod
    def _looks_like_java_expression(value: str) -> bool:
        """Return True if value looks like a Java expression the engine cannot evaluate.

        The engine only handles values starting with "new " (constructor calls).
        This detects method calls, ternary operators, and cast expressions.
        """
        stripped = value.strip()
        # Engine handles "new " prefix — not a gap
        if stripped.startswith("new "):
            return False
        # Method call patterns
        for pattern in _JAVA_EXPR_PATTERNS:
            if pattern in stripped:
                return True
        # Ternary operator: both "? " and " : " present
        if "? " in stripped and " : " in stripped:
            return True
        # Cast expression: starts with "(("
        if stripped.startswith("(("):
            return True
        return False

    @staticmethod
    def _has_context_reference(value: str) -> bool:
        """Return True if value contains a context.xxx reference."""
        return bool(_CONTEXT_REF_RE.search(value.strip()))

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # Parse VARIABLES table.
        # XmlParser stores TABLE params as lists of {elementRef, value} dicts.
        # Entries come in KEY/VALUE pairs.
        variables: List[Dict[str, str]] = []
        raw_vars = self._get_param(node, "VARIABLES", [])

        if isinstance(raw_vars, list):
            current_key: str | None = None
            for entry in raw_vars:
                ref = entry.get("elementRef", "")
                val = entry.get("value", "").strip('"')
                if ref == "KEY":
                    # If we already had a KEY without a VALUE, emit a warning
                    if current_key is not None:
                        warnings.append(
                            f"KEY '{current_key}' has no matching VALUE — skipped"
                        )
                    current_key = val
                elif ref == "VALUE":
                    if current_key is not None:
                        variables.append({"name": current_key, "value": val})
                        current_key = None
                    else:
                        warnings.append(
                            f"VALUE '{val}' has no preceding KEY — skipped"
                        )

            # Handle trailing KEY with no VALUE
            if current_key is not None:
                warnings.append(
                    f"KEY '{current_key}' has no matching VALUE — skipped"
                )
        else:
            warnings.append(
                "VARIABLES param is not a list — expected TABLE structure"
            )

        if not variables:
            warnings.append("No variables defined — component will have no effect")

        config: Dict[str, Any] = {
            "variables": variables,
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        # Engine-gap warnings: per-variable checks
        for var in variables:
            name = var.get("name", "")
            value = var.get("value", "")
            if self._looks_like_java_expression(value):
                warnings.append(
                    f"Variable '{name}' value appears to contain a Java expression: "
                    f"engine only evaluates 'new ...' constructor calls, "
                    f"other expressions are stored as raw strings"
                )
            if self._has_context_reference(value):
                warnings.append(
                    f"Variable '{name}' value contains context reference: "
                    f"engine's resolve_dict() cannot reach values inside "
                    f"the VARIABLES list"
                )

        # Engine-gap warning: NB_LINE always 0
        warnings.append(
            "Engine NB_LINE is always 0: engine does not count pass-through "
            "rows when component receives flow input"
        )

        # Engine config key casing mismatch — needs engine fix, not user action
        needs_review.append({
            "issue": "Engine config key mismatch: converter outputs 'variables' "
                     "(lowercase) but engine reads 'VARIABLES' (uppercase) — "
                     "variables may not be found at runtime until engine is fixed",
            "component": node.component_id,
            "severity": "engine_bug",
        })

        component = self._build_component_dict(
            node=node,
            type_name="SetGlobalVar",
            config=config,
            # Utility component — no data flow schema (matches tWarn, tDie pattern)
            schema={"input": [], "output": []},
        )
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
