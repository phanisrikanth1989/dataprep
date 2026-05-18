"""Groovy script generation for tMap compiled execution.

Pure functions: takes parsed MapConfig in, returns a Groovy source string.
No bridge calls, no state. See spec section 7.

Two entry points (added in subsequent tasks):
- build_active_script(cfg) -> active-pass script (vars + outputs + is_reject +
  catch_output_reject error capture).
- build_reject_script(cfg) -> reject-pass script (inner_join_reject column
  expressions only).

This module is built incrementally:
- Task 3.1: groovy_escape_expression (helper)
- Task 3.2+3.3: build_active_script
- Task 3.4: build_reject_script
"""
from __future__ import annotations


def groovy_escape_expression(java_expr: str) -> str:
    """Escape ``$`` inside double-quoted string literals.

    Groovy GString interpolates ``$identifier`` / ``${expr}`` at runtime.
    Talend Java expressions like ``"Total: $100"`` would either parse-error
    or, worse, evaluate an unintended identifier. Outside string literals,
    ``$`` is a legal identifier character in both Java and Groovy -- left
    alone.

    Escape sequences (``\\\\``, ``\\"``) inside a string region are consumed
    as two-character units so they cannot mis-detect the closing quote.

    Single-quoted strings (Groovy char literals) are treated as
    outside-string regions; ``$`` inside them is not interpolated by Groovy
    anyway.

    Args:
        java_expr: Java/Groovy expression text (already stripped of any
            ``{{java}}`` marker by the caller).

    Returns:
        Expression with ``$`` inside double-quoted strings escaped to ``\\$``.
    """
    result: list[str] = []
    in_string = False
    i = 0
    n = len(java_expr)
    while i < n:
        ch = java_expr[i]
        if not in_string:
            if ch == '"':
                in_string = True
            result.append(ch)
            i += 1
            continue
        # Inside a double-quoted string literal
        if ch == "\\" and i + 1 < n:
            # Two-char escape (e.g. \" or \\); consume both
            result.append(ch)
            result.append(java_expr[i + 1])
            i += 2
        elif ch == '"':
            in_string = False
            result.append(ch)
            i += 1
        elif ch == "$":
            result.append("\\$")
            i += 1
        else:
            result.append(ch)
            i += 1
    return "".join(result)
