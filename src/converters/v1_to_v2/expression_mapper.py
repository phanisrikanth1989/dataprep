"""Translate V1 expressions to V2 DSL.

V1 uses Java-style expressions with main.column references.
V2 uses a simpler DSL with bare column names.
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExpressionResult:
    """Result of translating a V1 expression."""
    expression: str
    needs_review: bool = False
    review_reason: str = ""


# Java date pattern tokens -> Python strftime (order matters: longest first)
_JAVA_TO_PYTHON_DATE = [
    ("yyyy", "%Y"),
    ("yy", "%y"),
    ("MM", "%m"),
    ("dd", "%d"),
    ("HH", "%H"),
    ("hh", "%I"),
    ("mm", "%M"),
    ("ss", "%S"),
    ("SSS", "%f"),
    ("a", "%p"),
]

# Patterns that indicate Java code needing manual rewrite
_JAVA_MARKERS = [
    (r"\{\{java\}\}", "Java code block"),
    (r"\.substring\s*\(", "Java .substring() method"),
    (r"\.length\s*\(", "Java .length() method"),
    (r"\.trim\s*\(", "Java .trim() method"),
    (r"\.toUpperCase\s*\(", "Java .toUpperCase() method"),
    (r"\.toLowerCase\s*\(", "Java .toLowerCase() method"),
    (r"\.charAt\s*\(", "Java .charAt() method"),
    (r"\.indexOf\s*\(", "Java .indexOf() method"),
    (r"\.replace\s*\(", "Java .replace() method"),
    (r"\.split\s*\(", "Java .split() method"),
    (r"\.equals\s*\(", "Java .equals() method"),
    (r"\.compareTo\s*\(", "Java .compareTo() method"),
    (r"\.matches\s*\(", "Java .matches() method"),
    (r"\bTalendDate\.", "Talend date routine"),
    (r"\bTalendString\.", "Talend string routine"),
    (r"\bglobalMap\.get\s*\(", "globalMap reference (no V2 equivalent)"),
    (r"\bglobalMap\.put\s*\(", "globalMap reference (no V2 equivalent)"),
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


def translate_expression(expr: Optional[str]) -> ExpressionResult:
    """Translate a V1 expression to V2 DSL."""
    if expr is None:
        return ExpressionResult(expression="")
    if not expr.strip():
        return ExpressionResult(expression=expr)

    # --- Check for Java markers first (before any transformation) ---
    for pattern, reason in _JAVA_MARKERS:
        if re.search(pattern, expr, re.IGNORECASE):
            cleaned = _basic_translate(expr)
            return ExpressionResult(
                expression=cleaned,
                needs_review=True,
                review_reason=reason,
            )

    # --- Check for nested ternary ---
    if expr.count("?") > 1:
        cleaned = _basic_translate(expr)
        return ExpressionResult(
            expression=cleaned,
            needs_review=True,
            review_reason="Nested ternary — simplify manually",
        )

    # --- Full translation ---
    result = _basic_translate(expr)
    result = _convert_simple_ternary(result)

    return ExpressionResult(expression=result)


def _basic_translate(expr: str) -> str:
    """Apply safe, mechanical translations."""
    result = expr
    result = re.sub(r"\{\{java\}\}\s*", "", result)
    result = re.sub(r"\bmain\.(\w+)", r"\1", result)
    result = re.sub(r'"([^"]*)"', r"'\1'", result)
    return result


def _convert_simple_ternary(expr: str) -> str:
    """Convert ``cond ? a : b`` to ``IF(cond, a, b)``."""
    match = re.match(r"^(.+?)\s*\?\s*(.+?)\s*:\s*(.+)$", expr.strip())
    if match:
        cond, if_true, if_false = match.groups()
        return f"IF({cond.strip()}, {if_true.strip()}, {if_false.strip()})"
    return expr
