"""Functions, methods and attributes an expression may use.

Each entry maps one Python spelling to the Polars expression that gives the
same result. A handler receives the translator and the syntax node (and, for
a method or attribute, the already translated value it applies to) and
returns a Polars expression.
"""
from __future__ import annotations

import ast
import datetime as _datetime
import math as _math
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import polars as pl

from .translate import NOT_CONSTANT

if TYPE_CHECKING:
    from .translate import Translator

Handler = Callable[..., pl.Expr]

_MICROSECONDS_PER_DAY = 86_400_000_000
_REGEX_META = set(".^$*+?{}[]\\|()")
_REGEX_TESTS = ("re.search", "re.match", "re.fullmatch")
_RE_FLAGS = {
    "I": "i", "IGNORECASE": "i",
    "M": "m", "MULTILINE": "m",
    "S": "s", "DOTALL": "s",
    "X": "x", "VERBOSE": "x",
}

# What a Java habit should become in Python, appended to "unknown method".
_METHOD_HINTS = {
    "equals": "; compare with ==",
    "equalsIgnoreCase": "; compare .lower() on both sides with ==",
    "length": "; use len(...)",
    "toUpperCase": "; use .upper()",
    "toLowerCase": "; use .lower()",
    "trim": "; use .strip()",
    "substring": "; use a slice, as in text[0:3]",
    "contains": "; use `part in text`",
    "isEmpty": "; compare with ''",
    "indexOf": "; use .find(...)",
    "startsWith": "; use .startswith(...)",
    "endsWith": "; use .endswith(...)",
    "replaceAll": "; use re.sub(pattern, replacement, text)",
}


def method_hint(name: str) -> str:
    """A suggestion for a method that is Java, not Python."""
    return _METHOD_HINTS.get(name, "")


def dotted(node: ast.AST) -> Optional[str]:
    """``a.b.c`` for a chain of plain names, else None."""
    parts: List[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------

def as_text(tr: "Translator", node: ast.AST) -> pl.Expr:
    """A value as Python's ``str()`` would print it. Missing stays missing."""
    value = tr.value(node)
    dtype = tr.dtype(value, node)
    if dtype == pl.String:
        return value
    if dtype == pl.Boolean:
        return pl.when(value).then(pl.lit("True")).when(~value).then(pl.lit("False")).otherwise(None)
    return value.cast(pl.String)


def _need_text(tr: "Translator", node: ast.Call, target: pl.Expr) -> None:
    owner = node.func.value
    dtype = tr.dtype(target, owner)
    if dtype != pl.String:
        tr.fail(node, f"'.{node.func.attr}()' is a text method; this value is {dtype}")


def _need_date(tr: "Translator", node: ast.AST, owner: ast.AST, target: pl.Expr, name: str) -> pl.DataType:
    dtype = tr.dtype(target, owner)
    if not dtype.is_temporal():
        tr.fail(node, f"'{name}' needs a date or time; this value is {dtype}")
    return dtype


def _const_text(tr: "Translator", node: ast.AST, what: str) -> str:
    found = tr.need_const(node, what)
    if not isinstance(found, str):
        tr.fail(node, f"{what} must be text")
    return found


def _const_int(tr: "Translator", node: ast.AST, what: str) -> int:
    found = tr.need_const(node, what)
    if isinstance(found, bool) or not isinstance(found, int):
        tr.fail(node, f"{what} must be a whole number")
    return found


def _value_or_const(tr: "Translator", node: ast.AST) -> Any:
    """A Python constant when the node is one, else its translated expression."""
    found = tr.const(node)
    return tr.value(node) if found is NOT_CONSTANT else found


# ------------------------------------------------------------------
# Builtin functions
# ------------------------------------------------------------------

def _len(tr: "Translator", node: ast.Call) -> pl.Expr:
    (arg,) = tr.args(node, 1, 1)
    value = tr.value(arg)
    dtype = tr.dtype(value, arg)
    if dtype == pl.String:
        return value.str.len_chars()
    if isinstance(dtype, pl.List):
        return value.list.len()
    tr.fail(node, f"len() needs text or a list; this value is {dtype}")


def _str(tr: "Translator", node: ast.Call) -> pl.Expr:
    (arg,) = tr.args(node, 1, 1)
    return as_text(tr, arg)


def _int(tr: "Translator", node: ast.Call) -> pl.Expr:
    (arg,) = tr.args(node, 1, 1)
    value = tr.value(arg)
    dtype = tr.dtype(value, arg)
    if dtype == pl.String:
        text = value.str.strip_chars()
        return tr.fallible("int()", text, text.cast(pl.Int64, strict=False))
    if dtype.is_decimal():
        return value.truncate(0).cast(pl.Int64)
    if dtype.is_float():
        # Not a number, or a number no whole number can hold.
        return tr.fallible("int()", value, value.cast(pl.Int64, strict=False))
    return value.cast(pl.Int64)


def _float(tr: "Translator", node: ast.Call) -> pl.Expr:
    (arg,) = tr.args(node, 1, 1)
    value = tr.value(arg)
    if tr.dtype(value, arg) == pl.String:
        text = value.str.strip_chars()
        return tr.fallible("float()", text, text.cast(pl.Float64, strict=False))
    return value.cast(pl.Float64)


def _bool(tr: "Translator", node: ast.Call) -> pl.Expr:
    (arg,) = tr.args(node, 1, 1)
    return tr.truth(arg)


def _round(tr: "Translator", node: ast.Call) -> pl.Expr:
    args = tr.args(node, 1, 2)
    value = tr.value(args[0])
    dtype = tr.dtype(value, args[0])
    if not dtype.is_numeric():
        tr.fail(node, f"round() needs a number; this value is {dtype}")
    if len(args) == 1:
        return value if dtype.is_integer() else value.round(0).cast(pl.Int64)
    digits = _const_int(tr, args[1], "the number of digits")
    if digits < 0:
        tr.fail(node, "rounding to tens or hundreds is not supported")
    return value.round(digits)


def _abs(tr: "Translator", node: ast.Call) -> pl.Expr:
    (arg,) = tr.args(node, 1, 1)
    return tr.value(arg).abs()


def _horizontal(function: Callable[..., pl.Expr], name: str) -> Handler:
    def handler(tr: "Translator", node: ast.Call) -> pl.Expr:
        args = tr.args(node, 1, 255)
        if len(args) < 2:
            tr.fail(node, f"{name}() needs two or more values to compare")
        return tr._checked(function(*[tr.value(arg) for arg in args]), node)

    return handler


def _decimal(tr: "Translator", node: ast.Call) -> pl.Expr:
    (arg,) = tr.args(node, 1, 1)
    found = tr.need_const(arg, "the value")
    try:
        return pl.lit(Decimal(str(found)))
    except InvalidOperation:
        tr.fail(node, "not a decimal number")


BUILTINS: Dict[str, Handler] = {
    "len": _len,
    "str": _str,
    "int": _int,
    "float": _float,
    "bool": _bool,
    "round": _round,
    "abs": _abs,
    "min": _horizontal(pl.min_horizontal, "min"),
    "max": _horizontal(pl.max_horizontal, "max"),
    "Decimal": _decimal,
}


# ------------------------------------------------------------------
# Text methods
# ------------------------------------------------------------------

def _simple_text(build: Callable[[pl.Expr], pl.Expr]) -> Handler:
    def handler(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
        tr.args(node, 0, 0)
        _need_text(tr, node, target)
        return build(target)

    return handler


def _strip(method: str) -> Handler:
    def handler(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
        args = tr.args(node, 0, 1)
        _need_text(tr, node, target)
        chars = _const_text(tr, args[0], "the characters to strip") if args else None
        return getattr(target.str, method)(chars)

    return handler


def _starts_or_ends(method: str) -> Handler:
    def handler(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
        (arg,) = tr.args(node, 1, 1)
        _need_text(tr, node, target)
        test = getattr(target.str, method)
        found = tr.const(arg)
        if found is NOT_CONSTANT:
            return test(tr.value(arg))
        choices = found if isinstance(found, list) else [found]
        if not choices or not all(isinstance(choice, str) for choice in choices):
            tr.fail(arg, "must be text, or a tuple of texts")
        result = test(choices[0])
        for choice in choices[1:]:
            result = result | test(choice)
        return result

    return handler


def _replace(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
    args = tr.args(node, 2, 3)
    _need_text(tr, node, target)
    old = _const_text(tr, args[0], "the text to replace")
    new = _const_text(tr, args[1], "the replacement")
    if len(args) == 3:
        return target.str.replace(old, new, literal=True, n=_const_int(tr, args[2], "the count"))
    return target.str.replace_all(old, new, literal=True)


def _split(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
    args = tr.args(node, 0, 1)
    _need_text(tr, node, target)
    if not args:
        return target.str.extract_all(r"\S+")
    return target.str.split(_const_text(tr, args[0], "the separator"))


def _zfill(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
    (arg,) = tr.args(node, 1, 1)
    _need_text(tr, node, target)
    return target.str.zfill(_const_int(tr, arg, "the width"))


def _pad(method: str) -> Handler:
    def handler(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
        args = tr.args(node, 1, 2)
        _need_text(tr, node, target)
        width = _const_int(tr, args[0], "the width")
        fill = _const_text(tr, args[1], "the fill character") if len(args) == 2 else " "
        return getattr(target.str, method)(width, fill)

    return handler


def _capitalize(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
    tr.args(node, 0, 0)
    _need_text(tr, node, target)
    return target.str.head(1).str.to_uppercase() + target.str.slice(1).str.to_lowercase()


def _count(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
    (arg,) = tr.args(node, 1, 1)
    _need_text(tr, node, target)
    return target.str.count_matches(_const_text(tr, arg, "the text to count"), literal=True)


def _find(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
    (arg,) = tr.args(node, 1, 1)
    _need_text(tr, node, target)
    found = target.str.find(_const_text(tr, arg, "the text to find"), literal=True).cast(pl.Int64)
    return pl.when(target.is_null()).then(None).otherwise(found.fill_null(-1))


def _matches(pattern: str) -> Handler:
    return _simple_text(lambda target: target.str.contains(pattern))


def _join(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
    (arg,) = tr.args(node, 1, 1)
    separator = tr.const(node.func.value)
    if not isinstance(separator, str):
        tr.fail(node, "the separator of .join() must be a text constant")
    if not isinstance(arg, (ast.List, ast.Tuple)):
        tr.fail(arg, ".join() needs a list written out in the expression")
    return pl.concat_str([as_text(tr, item) for item in arg.elts], separator=separator)


def _format(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
    template = tr.const(node.func.value)
    if not isinstance(template, str):
        tr.fail(node, ".format() needs a text constant as its template")
    args = tr.args(node, 0, 255)
    if template.replace("{}", "").count("{") or template.count("{}") != len(args):
        tr.fail(node, "only plain {} placeholders are supported, one per argument")
    return pl.format(template, *[as_text(tr, arg) for arg in args])


# ------------------------------------------------------------------
# Date and time methods and attributes
# ------------------------------------------------------------------

def _strftime(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
    (arg,) = tr.args(node, 1, 1)
    _need_date(tr, node, node.func.value, target, ".strftime()")
    pattern = _const_text(tr, arg, "the date format").replace(".%f", "%.6f")
    return target.dt.strftime(pattern)


def _date_method(build: Callable[[pl.Expr], pl.Expr], name: str) -> Handler:
    def handler(tr: "Translator", node: ast.Call, target: pl.Expr) -> pl.Expr:
        tr.args(node, 0, 0)
        _need_date(tr, node, node.func.value, target, name)
        return build(target)

    return handler


def _date_part(part: str) -> Handler:
    def handler(tr: "Translator", node: ast.Attribute, target: pl.Expr) -> pl.Expr:
        _need_date(tr, node, node.value, target, f".{part}")
        return getattr(target.dt, part)()

    return handler


def _days(tr: "Translator", node: ast.Attribute, target: pl.Expr) -> pl.Expr:
    dtype = tr.dtype(target, node.value)
    if not isinstance(dtype, pl.Duration):
        tr.fail(node, f"'.days' needs the difference of two dates; this value is {dtype}")
    return target.dt.total_microseconds() // _MICROSECONDS_PER_DAY


METHODS: Dict[str, Handler] = {
    "upper": _simple_text(lambda t: t.str.to_uppercase()),
    "lower": _simple_text(lambda t: t.str.to_lowercase()),
    "title": _simple_text(lambda t: t.str.to_titlecase()),
    "capitalize": _capitalize,
    "strip": _strip("strip_chars"),
    "lstrip": _strip("strip_chars_start"),
    "rstrip": _strip("strip_chars_end"),
    "startswith": _starts_or_ends("starts_with"),
    "endswith": _starts_or_ends("ends_with"),
    "replace": _replace,
    "split": _split,
    "zfill": _zfill,
    "rjust": _pad("pad_start"),
    "ljust": _pad("pad_end"),
    "count": _count,
    "find": _find,
    "isdigit": _matches(r"^\d+$"),
    "isdecimal": _matches(r"^\d+$"),
    "isalpha": _matches(r"^\p{L}+$"),
    "isalnum": _matches(r"^[\p{L}\p{N}]+$"),
    "isspace": _matches(r"^\s+$"),
    "join": _join,
    "format": _format,
    "strftime": _strftime,
    "date": _date_method(lambda t: t.dt.date(), ".date()"),
    "time": _date_method(lambda t: t.dt.time(), ".time()"),
    "weekday": _date_method(lambda t: t.dt.weekday() - 1, ".weekday()"),
    "isoweekday": _date_method(lambda t: t.dt.weekday(), ".isoweekday()"),
    "total_seconds": lambda tr, node, target: target.dt.total_seconds(fractional=True),
}

ATTRIBUTES: Dict[str, Handler] = {
    "year": _date_part("year"),
    "month": _date_part("month"),
    "day": _date_part("day"),
    "hour": _date_part("hour"),
    "minute": _date_part("minute"),
    "second": _date_part("second"),
    "microsecond": _date_part("microsecond"),
    "days": _days,
}

CONSTANTS: Dict[str, Any] = {
    "math.pi": _math.pi,
    "math.e": _math.e,
    "math.tau": _math.tau,
    "math.inf": _math.inf,
    "math.nan": _math.nan,
    "np.nan": _math.nan,
    "np.inf": _math.inf,
    "np.pi": _math.pi,
    "np.e": _math.e,
}


# ------------------------------------------------------------------
# Indexing and slicing
# ------------------------------------------------------------------

def subscript(tr: "Translator", node: ast.Subscript) -> pl.Expr:
    """Translate indexing and slicing of text or of a list."""
    target = tr.value(node.value)
    dtype = tr.dtype(target, node.value)
    index = node.slice
    if isinstance(dtype, pl.List):
        if isinstance(index, ast.Slice):
            tr.fail(node, "slicing a list is not supported")
        return target.list.get(_const_int(tr, index, "the position"), null_on_oob=True)
    if dtype != pl.String:
        tr.fail(node, f"only text and lists can be indexed; this value is {dtype}")
    if not isinstance(index, ast.Slice):
        return target.str.slice(_const_int(tr, index, "the position"), 1)

    start = None if index.lower is None else _const_int(tr, index.lower, "the start of the slice")
    stop = None if index.upper is None else _const_int(tr, index.upper, "the end of the slice")
    step = None if index.step is None else _const_int(tr, index.step, "the step of the slice")
    if step == -1 and start is None and stop is None:
        return target.str.reverse()
    if step not in (None, 1):
        tr.fail(node, "a slice step is not supported, except [::-1] to reverse")
    if start is None and stop is None:
        return target
    if start is None:
        return target.str.head(stop)
    if stop is None:
        return target.str.slice(start) if start >= 0 else target.str.tail(-start)
    if 0 <= start <= stop:
        return target.str.slice(start, stop - start)
    tr.fail(node, "this mix of negative slice bounds is not supported")


# ------------------------------------------------------------------
# re
# ------------------------------------------------------------------

def _regex_flags(tr: "Translator", node: Optional[ast.AST]) -> str:
    if node is None:
        return ""
    parts = [node]
    letters = ""
    while parts:
        part = parts.pop()
        if isinstance(part, ast.BinOp) and isinstance(part.op, ast.BitOr):
            parts += [part.left, part.right]
            continue
        name = dotted(part) or ""
        letter = _RE_FLAGS.get(name[3:]) if name.startswith("re.") else None
        if letter is None:
            tr.fail(node, "only re.I, re.M, re.S and re.X are supported as flags")
        letters += letter
    return f"(?{letters})" if letters else ""


def _regex_pattern(tr: "Translator", node: ast.AST, flags: str = "") -> str:
    pattern = flags + _const_text(tr, node, "the pattern")
    try:
        pl.select(pl.lit("").str.contains(pattern))
    except Exception as exc:  # noqa: BLE001 -- Polars decides what a valid pattern is
        detail = " ".join(str(exc).split())[:160]
        tr.fail(node, f"this pattern is not supported (no lookaround and no backreferences): {detail}")
    return pattern


def _is_literal(pattern: str) -> bool:
    return not (set(pattern) & _REGEX_META)


def _python_replacement(text: str, literal: bool) -> str:
    """Rewrite a Python replacement template for Polars."""
    out: List[str] = []
    position = 0
    while position < len(text):
        char = text[position]
        nxt = text[position + 1] if position + 1 < len(text) else ""
        if char == "\\" and nxt.isdigit() and not literal:
            out.append("${" + nxt + "}")
            position += 2
        elif char == "\\" and nxt == "g" and text[position + 2:position + 3] == "<" and not literal:
            end = text.index(">", position)
            out.append("${" + text[position + 3:end] + "}")
            position = end + 1
        elif char == "\\" and nxt:
            out.append({"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt))
            position += 2
        elif char == "$" and not literal:
            out.append("$$")
            position += 1
        else:
            out.append(char)
            position += 1
    return "".join(out)


def _keywords(tr: "Translator", node: ast.Call, allowed: tuple) -> Dict[str, ast.AST]:
    found: Dict[str, ast.AST] = {}
    for keyword in node.keywords:
        if keyword.arg not in allowed:
            tr.fail(node, f"unknown argument '{keyword.arg}'")
        found[keyword.arg] = keyword.value
    return found


def _re_sub(tr: "Translator", node: ast.Call) -> pl.Expr:
    named = _keywords(tr, node, ("count", "flags"))
    args = list(node.args)
    if not 3 <= len(args) <= 5:
        tr.fail(node, "re.sub() takes a pattern, a replacement and the text")
    count_node = args[3] if len(args) > 3 else named.get("count")
    flags = _regex_flags(tr, args[4] if len(args) > 4 else named.get("flags"))
    pattern = _regex_pattern(tr, args[0], flags)
    replacement = _const_text(tr, args[1], "the replacement")
    target = tr.value(args[2])
    if tr.dtype(target, args[2]) != pl.String:
        tr.fail(args[2], "re.sub() needs text to work on")
    count = 0 if count_node is None else _const_int(tr, count_node, "the count")

    if _is_literal(pattern):
        new = _python_replacement(replacement, literal=True)
        if count:
            return target.str.replace(pattern, new, literal=True, n=count)
        return target.str.replace_all(pattern, new, literal=True)
    new = _python_replacement(replacement, literal=False)
    if count == 0:
        return target.str.replace_all(pattern, new)
    if count == 1:
        return target.str.replace(pattern, new, n=1)
    tr.fail(node, "with a pattern, only count=1 or no count is supported")


def regex_test(tr: "Translator", node: ast.AST) -> Optional[pl.Expr]:
    """``re.search`` / ``re.match`` / ``re.fullmatch`` as a true-or-false test."""
    parts = _regex_parts(tr, node)
    if parts is None:
        return None
    pattern, target = parts
    return target.str.contains(pattern, literal=_is_literal(pattern))


def regex_group(tr: "Translator", node: ast.Call) -> Optional[pl.Expr]:
    """``re.search(pattern, text).group(n)``."""
    parts = _regex_parts(tr, node.func.value)
    if parts is None:
        return None
    pattern, target = parts
    args = tr.args(node, 0, 1)
    group = _const_int(tr, args[0], "the group") if args else 0
    return target.str.extract(pattern, group)


def _regex_parts(tr: "Translator", node: ast.AST):
    if not isinstance(node, ast.Call) or dotted(node.func) not in _REGEX_TESTS:
        return None
    named = _keywords(tr, node, ("flags",))
    args = list(node.args)
    if not 2 <= len(args) <= 3:
        tr.fail(node, "takes a pattern and the text")
    flags = _regex_flags(tr, args[2] if len(args) == 3 else named.get("flags"))
    pattern = _regex_pattern(tr, args[0], flags)
    target = tr.value(args[1])
    if tr.dtype(target, args[1]) != pl.String:
        tr.fail(args[1], "needs text to search in")
    kind = dotted(node.func)
    if kind == "re.match":
        pattern = f"^(?:{pattern})"
    elif kind == "re.fullmatch":
        pattern = f"^(?:{pattern})$"
    return pattern, target


def _regex_as_value(tr: "Translator", node: ast.Call) -> pl.Expr:
    return regex_test(tr, node)


# ------------------------------------------------------------------
# math
# ------------------------------------------------------------------

def _math_one(build: Callable[[pl.Expr], pl.Expr]) -> Handler:
    def handler(tr: "Translator", node: ast.Call) -> pl.Expr:
        (arg,) = tr.args(node, 1, 1)
        value = tr.value(arg)
        if not tr.dtype(value, arg).is_numeric():
            tr.fail(node, "needs a number")
        return build(value)

    return handler


def _math_log(tr: "Translator", node: ast.Call) -> pl.Expr:
    args = tr.args(node, 1, 2)
    value = tr.value(args[0])
    if len(args) == 2:
        return value.log(tr.need_const(args[1], "the base"))
    return value.log()


def _math_pow(tr: "Translator", node: ast.Call) -> pl.Expr:
    base, exponent = tr.args(node, 2, 2)
    return tr._checked(tr.value(base).cast(pl.Float64).pow(tr.value(exponent)), node)


# ------------------------------------------------------------------
# datetime
# ------------------------------------------------------------------

def _strptime(tr: "Translator", node: ast.Call) -> pl.Expr:
    text, pattern = tr.args(node, 2, 2)
    value = tr.value(text)
    if tr.dtype(value, text) != pl.String:
        tr.fail(text, "strptime() needs text to parse")
    fmt = _const_text(tr, pattern, "the date format").replace(".%f", "%.f")
    return tr.fallible("strptime()", value, value.str.to_datetime(fmt, strict=False))


def _now(tr: "Translator", node: ast.Call) -> pl.Expr:
    tr.args(node, 0, 0)
    return pl.lit(_datetime.datetime.now())


def _today(tr: "Translator", node: ast.Call) -> pl.Expr:
    tr.args(node, 0, 0)
    return pl.lit(_datetime.date.today())


def _build_date(python_type: type, polars_function: Callable[..., pl.Expr], low: int, high: int) -> Handler:
    def handler(tr: "Translator", node: ast.Call) -> pl.Expr:
        args = tr.args(node, low, high)
        parts = [_value_or_const(tr, arg) for arg in args]
        if all(isinstance(part, int) for part in parts):
            try:
                return pl.lit(python_type(*parts))
            except ValueError as exc:
                tr.fail(node, str(exc))
        return tr._checked(polars_function(*parts), node)

    return handler


def _timedelta(tr: "Translator", node: ast.Call) -> pl.Expr:
    names = ("days", "seconds", "microseconds", "milliseconds", "minutes", "hours", "weeks")
    parts = {name: _value_or_const(tr, value) for name, value in _keywords(tr, node, names).items()}
    for name, arg in zip(names, node.args):
        if name in parts:
            tr.fail(node, f"'{name}' is given twice")
        parts[name] = _value_or_const(tr, arg)
    if len(node.args) > 3:
        tr.fail(node, "takes at most days, seconds and microseconds without names")
    return pl.duration(**parts)


# ------------------------------------------------------------------
# Missing-value tests, pandas style
# ------------------------------------------------------------------

def _np_round(tr: "Translator", node: ast.Call) -> pl.Expr:
    """numpy's round: a float stays a float, halves go to the even neighbour."""
    args = tr.args(node, 1, 2)
    value = tr.value(args[0])
    dtype = tr.dtype(value, args[0])
    if not dtype.is_numeric():
        tr.fail(node, f"np.round() needs a number; this value is {dtype}")
    digits = _const_int(tr, args[1], "the number of digits") if len(args) == 2 else 0
    if digits < 0:
        tr.fail(node, "rounding to tens or hundreds is not supported")
    return value if dtype.is_integer() else value.round(digits)


def _np_where(tr: "Translator", node: ast.Call) -> pl.Expr:
    """numpy's three-argument where: one value where the condition holds, another where it does not."""
    test, then, otherwise = tr.args(node, 3, 3)
    return tr.value(ast.copy_location(ast.IfExp(test=test, body=then, orelse=otherwise), node))


def _is_missing(negate: bool) -> Handler:
    def handler(tr: "Translator", node: ast.Call) -> pl.Expr:
        (arg,) = tr.args(node, 1, 1)
        value = tr.value(arg)
        missing = value.is_null()
        if tr.dtype(value, arg).is_float():
            missing = missing | value.is_nan().fill_null(False)
        return ~missing if negate else missing

    return handler


FUNCTIONS: Dict[str, Handler] = {
    "re.sub": _re_sub,
    "re.search": _regex_as_value,
    "re.match": _regex_as_value,
    "re.fullmatch": _regex_as_value,
    "math.floor": _math_one(lambda x: x.floor().cast(pl.Int64)),
    "math.ceil": _math_one(lambda x: x.ceil().cast(pl.Int64)),
    "math.trunc": _math_one(lambda x: x.cast(pl.Int64)),
    "math.sqrt": _math_one(lambda x: x.cast(pl.Float64).sqrt()),
    "math.exp": _math_one(lambda x: x.cast(pl.Float64).exp()),
    "math.log10": _math_one(lambda x: x.cast(pl.Float64).log10()),
    "math.fabs": _math_one(lambda x: x.abs().cast(pl.Float64)),
    "math.isnan": _math_one(lambda x: x.is_nan()),
    "math.log": _math_log,
    "math.pow": _math_pow,
    "datetime.datetime.strptime": _strptime,
    "datetime.strptime": _strptime,
    "datetime.datetime.now": _now,
    "datetime.now": _now,
    "datetime.date.today": _today,
    "date.today": _today,
    "datetime.datetime": _build_date(_datetime.datetime, pl.datetime, 3, 7),
    "datetime": _build_date(_datetime.datetime, pl.datetime, 3, 7),
    "datetime.date": _build_date(_datetime.date, pl.date, 3, 3),
    "date": _build_date(_datetime.date, pl.date, 3, 3),
    "datetime.timedelta": _timedelta,
    "timedelta": _timedelta,
    "decimal.Decimal": _decimal,
    "np.round": _np_round,
    "np.around": _np_round,
    "np.abs": _abs,
    "np.absolute": _abs,
    "np.fabs": _math_one(lambda x: x.abs().cast(pl.Float64)),
    "np.floor": _math_one(lambda x: x.cast(pl.Float64).floor()),
    "np.ceil": _math_one(lambda x: x.cast(pl.Float64).ceil()),
    "np.sqrt": _math_one(lambda x: x.cast(pl.Float64).sqrt()),
    "np.exp": _math_one(lambda x: x.cast(pl.Float64).exp()),
    "np.log": _math_one(lambda x: x.cast(pl.Float64).log()),
    "np.log10": _math_one(lambda x: x.cast(pl.Float64).log10()),
    "np.isnan": _math_one(lambda x: x.is_nan()),
    "np.where": _np_where,
    "np.maximum": BUILTINS["max"],
    "np.minimum": BUILTINS["min"],
    "pd.isna": _is_missing(False),
    "pd.isnull": _is_missing(False),
    "pd.notna": _is_missing(True),
    "pd.notnull": _is_missing(True),
}
