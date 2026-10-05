"""RunIf conditions.

A condition is read the way v1 reads it, so the conditions v1 job configs
carry keep working: it is Python, with a few Java left-overs the converter
leaves behind rewritten first (``&&``, ``||``, ``!``, ``null``, ``true``,
``false`` and ``((Integer)globalMap.get("key"))`` casts). References to
context variables and globalMap entries are replaced by their values before
the condition is evaluated; nothing else can be named in it.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Mapping, Optional

from ..errors import ConfigurationError

_CASTS: Dict[str, Callable[[Any], Any]] = {
    "Integer": int,
    "Long": int,
    "Short": int,
    "Byte": int,
    "Float": float,
    "Double": float,
    "Boolean": bool,
    "String": str,
}
_CAST = re.compile(r"""\(\((\w+)\)globalMap\.get\(['"]([^'"]+)['"]\)\)""")
_GLOBAL = re.compile(r"""globalMap\.get\(['"]([^'"]+)['"]\)""")
_TEMPLATE = re.compile(r"\$\{context\.(\w+)\}")
_BARE = re.compile(r"\bcontext\.(\w+)\b")
_NAMES: Dict[str, Any] = {
    "__builtins__": {},
    "None": None,
    "True": True,
    "False": False,
    "int": int,
    "str": str,
    "float": float,
    "bool": bool,
}


def evaluate(condition: Optional[str], context: Mapping[str, Any], global_map: Mapping[str, Any]) -> bool:
    """Whether a RunIf condition holds. An empty condition holds.

    Raises:
        ConfigurationError: When the condition cannot be evaluated.
    """
    if not condition or not condition.strip():
        return True
    try:
        text = _context_values(condition, context)
        text = _CAST.sub(lambda match: _cast(match.group(1), global_map.get(match.group(2))), text)
        text = _GLOBAL.sub(lambda match: _literal(global_map.get(match.group(1))), text)
        return bool(eval(_python_operators(text), dict(_NAMES), {}))  # noqa: S307 -- names are restricted
    except Exception as exc:  # noqa: BLE001 -- anything wrong with the text is one kind of problem
        reason = " ".join(str(exc).split()) or type(exc).__name__
        raise ConfigurationError(f"RunIf condition cannot be evaluated: {reason} (in: {condition})") from exc


def _context_values(text: str, context: Mapping[str, Any]) -> str:
    def value(match: "re.Match[str]") -> str:
        name = match.group(1)
        return repr(context[name]) if name in context else match.group(0)

    return _BARE.sub(value, _TEMPLATE.sub(value, text))


def _cast(type_name: str, raw: Any) -> str:
    convert = _CASTS.get(type_name)
    if convert is None:
        return repr(raw)
    empty = "0" if convert in (int, float) else "False" if convert is bool else '"None"'
    if raw is None:
        return empty
    try:
        return repr(convert(raw))
    except (ValueError, TypeError):
        return empty if convert is not str else repr(str(raw))


def _literal(value: Any) -> str:
    return "None" if value is None else repr(value)


def _python_operators(text: str) -> str:
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"!(?!=)", " not ", text)
    text = re.sub(r"\bnull\b", "None", text)
    text = re.sub(r"\btrue\b", "True", text)
    return re.sub(r"\bfalse\b", "False", text)
