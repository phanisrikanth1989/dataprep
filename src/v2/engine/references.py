"""An item in a config string: a globalMap entry or a context variable, alone or joined to text.

The converter leaves a value Talend computed as Talend wrote it, often
under its ``{{java}}`` mark::

    ((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))
    context.out_dir + "/" + ((String)globalMap.get("tFileList_1_CURRENT_FILE"))

That much is a lookup and a join, and is read here. Anything more (a method
call, arithmetic, a name that is neither) is Java, and is not.
"""
from __future__ import annotations

import re
from typing import Any, List, Mapping, Optional, Tuple

from ..errors import ConfigurationError

# The converter's mark on a value it took for a Java expression.
JAVA_MARK = "{{java}}"

# A term: what kind it is (``entry``, ``variable``, ``text``) and its key, name or text.
Term = Tuple[str, str]

_GET = r"""globalMap\s*\.\s*get\s*\(\s*(['"])(?P<key>[^'"]+)\1\s*\)"""
_ENTRIES = (
    re.compile(r"\(\s*\(\s*\w+\s*\)\s*" + _GET + r"\s*\)"),
    re.compile(r"\(\s*\w+\s*\)\s*" + _GET),
    re.compile(_GET),
)
_VARIABLE = re.compile(r"context\.(\w+)")
_TEXT = re.compile(r'"((?:[^"\\]|\\.)*)"')
_ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "r": "\r", "'": "'"}
_ESCAPE = re.compile(r"\\(.)", re.DOTALL)


def parsed(text: str) -> Optional[List[Term]]:
    """The terms of an item reference, or None when the text is not one.

    An item reference is one or more terms joined by ``+``: an entry of
    globalMap (``globalMap.get("key")``, with or without a cast and the
    brackets Talend writes round it), a context variable (``context.x``),
    or text in double quotes. Brackets round the whole are allowed.
    """
    text = text.strip()
    terms = _terms(text)
    if terms is None and text.startswith("(") and text.endswith(")"):
        terms = _terms(text[1:-1])
    return terms


def value_of(terms: List[Term], context: Mapping[str, Any], global_map: Mapping[str, Any]) -> Any:
    """What an item reference comes to: one term's own value, or the terms joined as text.

    Raises:
        ConfigurationError: When an entry or a variable it names is not there.
    """
    values = [_looked_up(term, context, global_map) for term in terms]
    if len(values) == 1:
        return values[0]
    return "".join("" if value is None else str(value) for value in values)


def _terms(text: str) -> Optional[List[Term]]:
    terms: List[Term] = []
    at = 0
    while True:
        at = _past_blanks(text, at)
        found = _term(text, at)
        if found is None:
            return None
        term, at = found
        terms.append(term)
        at = _past_blanks(text, at)
        if at == len(text):
            return terms
        if text[at] != "+":
            return None
        at += 1


def _term(text: str, at: int) -> Optional[Tuple[Term, int]]:
    for pattern in _ENTRIES:
        entry = pattern.match(text, at)
        if entry:
            return ("entry", entry.group("key")), entry.end()
    variable = _VARIABLE.match(text, at)
    if variable:
        return ("variable", variable.group(1)), variable.end()
    quoted = _TEXT.match(text, at)
    if quoted and all(escape in _ESCAPES for escape in _ESCAPE.findall(quoted.group(1))):
        return ("text", _ESCAPE.sub(lambda match: _ESCAPES[match.group(1)], quoted.group(1))), quoted.end()
    return None


def _past_blanks(text: str, at: int) -> int:
    while at < len(text) and text[at].isspace():
        at += 1
    return at


def _looked_up(term: Term, context: Mapping[str, Any], global_map: Mapping[str, Any]) -> Any:
    kind, named = term
    if kind == "text":
        return named
    if kind == "variable":
        if named not in context:
            raise ConfigurationError(f"context has no variable '{named}'")
        return context[named]
    if named not in global_map:
        raise ConfigurationError(f"globalMap has no entry '{named}'")
    return global_map[named]
