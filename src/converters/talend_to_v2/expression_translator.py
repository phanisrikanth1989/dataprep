"""Edge-aware expression translation from Talend Java expressions to V2 DSL."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class EdgeContext:
    """Maps edge names to their roles for expression translation."""
    main_edge: str
    lookup_edges: Dict[str, str]  # {edge_name: lookup_name}


@dataclass
class TranslationResult:
    """Result of translating a Talend expression."""
    expression: str
    needs_review: bool = False
    review_reason: str = ""


# Java patterns that indicate manual rewrite is needed
_JAVA_MARKERS = [
    (r"\.substring\s*\(", ".substring() method"),
    (r"\.length\s*\(", ".length() method"),
    (r"\.trim\s*\(", ".trim() method"),
    (r"\.toUpperCase\s*\(", ".toUpperCase() method"),
    (r"\.toLowerCase\s*\(", ".toLowerCase() method"),
    (r"\.charAt\s*\(", ".charAt() method"),
    (r"\.indexOf\s*\(", ".indexOf() method"),
    (r"\.replace\s*\(", ".replace() method"),
    (r"\.split\s*\(", ".split() method"),
    (r"\.equals\s*\(", ".equals() method"),
    (r"\.compareTo\s*\(", ".compareTo() method"),
    (r"\.matches\s*\(", ".matches() method"),
    (r"\.startsWith\s*\(", ".startsWith() method"),
    (r"\.endsWith\s*\(", ".endsWith() method"),
    (r"\bTalendDate\.", "TalendDate routine"),
    (r"\bTalendString\.", "TalendString routine"),
    (r"\bglobalMap\.get\s*\(", "globalMap.get() reference"),
    (r"\bglobalMap\.put\s*\(", "globalMap.put() reference"),
    (r"\(\s*\w+\s*\)\s*globalMap", "globalMap cast"),
]

# Java date pattern tokens -> Python strftime (longest tokens first per family
# to avoid partial replacement, e.g. SSS before ss).
_JAVA_TO_PYTHON_DATE = [
    ("yyyy", "%Y"),
    ("yy", "%y"),
    ("SSS", "%f"),
    ("MM", "%m"),
    ("dd", "%d"),
    ("HH", "%H"),
    ("hh", "%I"),
    ("mm", "%M"),
    ("ss", "%S"),
    ("a", "%p"),
]


def convert_date_pattern(java_pattern: Optional[str]) -> Optional[str]:
    """Convert a Java SimpleDateFormat pattern to Python strftime."""
    if java_pattern is None:
        return None
    if not java_pattern:
        return java_pattern
    result = java_pattern
    for java_tok, py_tok in _JAVA_TO_PYTHON_DATE:
        result = result.replace(java_tok, py_tok)
    return result


def translate_expression(
    expr: Optional[str],
    edge_context: Optional[EdgeContext] = None,
) -> TranslationResult:
    """Translate a Talend expression to V2 DSL."""
    if expr is None:
        return TranslationResult(expression="")
    expr = expr.strip()
    if not expr:
        return TranslationResult(expression="")

    # Check for Java markers first
    review_reason = _detect_java(expr)
    needs_review = bool(review_reason)

    # Check for Talend routine calls:
    # - routines.ClassName.method(...)
    # - ClassName.method(...) where ClassName starts uppercase (not Var/context)
    if re.search(r"\broutines\.\w+\.\w+", expr) or re.search(
        r"\b(?!Var\b|context\b)[A-Z]\w+\.\w+\s*\(", expr
    ):
        needs_review = True
        review_reason = review_reason or "Talend routine call — needs Python equivalent"

    # Check for nested ternary
    if expr.count("?") > 1:
        needs_review = True
        review_reason = review_reason or "Nested ternary — simplify manually"

    # Apply translations
    result = expr
    result = _strip_routines_prefix(result)
    if edge_context:
        result = _strip_main_edge(result, edge_context.main_edge)
    result = _convert_var_case(result)
    result = _convert_string_quotes(result)
    if not needs_review:
        result = _convert_simple_ternary(result)

    return TranslationResult(
        expression=result,
        needs_review=needs_review,
        review_reason=review_reason,
    )


def _detect_java(expr: str) -> str:
    """Check for Java patterns and return the reason if found.

    Uses case-insensitive matching intentionally — better to over-flag
    than to miss a Java method that happens to differ in casing.
    """
    for pattern, reason in _JAVA_MARKERS:
        if re.search(pattern, expr, re.IGNORECASE):
            return reason
    return ""


def _strip_main_edge(expr: str, main_edge: str) -> str:
    """Replace '{main_edge}.column' with 'column'.

    Uses word boundary to avoid partial matches (e.g., 'orders_extra.col'
    should NOT match main_edge='orders').
    """
    return re.sub(rf"\b{re.escape(main_edge)}\.(\w+)", r"\1", expr)


def _convert_var_case(expr: str) -> str:
    """Convert 'Var.name' to 'var.name'."""
    return re.sub(r"\bVar\.", "var.", expr)


def _strip_routines_prefix(expr: str) -> str:
    """Convert 'routines.RoutineName.func()' to 'RoutineName.func()'."""
    return re.sub(r"\broutines\.", "", expr)


def _convert_string_quotes(expr: str) -> str:
    """Convert Java double-quoted strings to single-quoted.

    Escapes any embedded single quotes in the content.
    """
    def _escape_and_wrap(m: re.Match) -> str:
        content = m.group(1).replace("'", "\\'")
        return f"'{content}'"

    return re.sub(r'"([^"]*)"', _escape_and_wrap, expr)


def _convert_simple_ternary(expr: str) -> str:
    """Convert 'cond ? a : b' to 'IF(cond, a, b)'.

    Skips conversion when colons appear inside quoted strings (ambiguous parse).
    """
    if "?" not in expr:
        return expr
    # Bail out if colons appear inside quoted strings — ambiguous parse
    if re.search(r"'[^']*:[^']*'", expr):
        return expr
    match = re.match(r"^(.+?)\s*\?\s*(.+?)\s*:\s*(.+)$", expr.strip())
    if match:
        cond, if_true, if_false = match.groups()
        return f"IF({cond.strip()}, {if_true.strip()}, {if_false.strip()})"
    return expr
