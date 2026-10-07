"""Filter rows: keep the rows that match, send the rest to reject.

A condition tests one column: an optional function is applied to the column,
then an operator compares the result with a value. Whether a comparison is
made on numbers or on text is decided by the value, as in v1: a value that
reads as a number compares numbers, any other value compares text.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ...errors import ConfigurationError
from ...expressions import translate_condition
from ...job.keys import EXPRESSION, Key, Kind
from ...types import to_text
from ..base import Transform, is_on
from ..registry import REGISTRY

_COMPARISONS = {"==": "eq", "!=": "ne", ">": "gt", "<": "lt", ">=": "ge", "<=": "le"}
_TEXT_TESTS = ("MATCHES", "CONTAINS", "NOT_CONTAINS", "STARTS_WITH", "ENDS_WITH", "LENGTH_LT", "LENGTH_GT")
_OPERATORS = tuple(_COMPARISONS) + _TEXT_TESTS + ("IS_NULL", "IS_NOT_NULL")
_AND = ("&&", "AND")
_NUMBER_FUNCTIONS = ("LENGTH", "ABS")
_SIDE = re.compile(r"(LEFT|RIGHT)\((\d+)\)")
_KEEP = "__keep"

# What Python's str.strip() removes, which is what v1's TRIM removes: the code points Python calls blank.
_BLANKS = "".join(map(chr, (
    *range(0x09, 0x0E), *range(0x1C, 0x21), 0x85, 0xA0, 0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F,
    0x3000,
)))
# What v1 skips around a number written as text.
_NUMBER_BLANKS = " \t\n\r\x0b\x0c"
# Regex shorthands as v1's regex engine reads them: ASCII only, and \Z for the end of the text.
_SHORTHANDS = {
    "d": "[0-9]", "D": "[^0-9]", "w": "[0-9A-Za-z_]", "W": "[^0-9A-Za-z_]",
    "s": r"[\t\n\f\r ]", "S": r"[^\t\n\f\r ]", "Z": r"\z",
}


def _first(text: pl.Expr) -> pl.Expr:
    """The first character; missing for empty text, as in v1."""
    return pl.when(text.str.len_chars() > 0).then(text.str.head(1))


_TEXT_FUNCTIONS = {
    "LOWER": lambda text: text.str.to_lowercase(),
    "UPPER": lambda text: text.str.to_uppercase(),
    "LOWER_FIRST": lambda text: _first(text).str.to_lowercase(),
    "UPPER_FIRST": lambda text: _first(text).str.to_uppercase(),
    "TRIM": lambda text: text.str.strip_chars(_BLANKS),
    "LTRIM": lambda text: text.str.strip_chars_start(_BLANKS),
    "RTRIM": lambda text: text.str.strip_chars_end(_BLANKS),
}
_FUNCTIONS = tuple(_TEXT_FUNCTIONS) + _NUMBER_FUNCTIONS


def _function(value: str) -> str:
    name = value.upper().strip()
    if name and name not in _FUNCTIONS and not _SIDE.fullmatch(name):
        raise ValueError(f"{value!r} is not a function; use one of {', '.join(_FUNCTIONS)}, LEFT(n), RIGHT(n)")
    return name


_CONDITION = (
    Key("column", required=True, doc="The column the condition tests."),
    Key("operator", required=True, choices=_OPERATORS,
        doc="The test. ==, !=, >, <, >= and <= compare numbers when `value` reads as a number and text otherwise; "
            "MATCHES takes a regular expression the whole text must match; LENGTH_LT and LENGTH_GT compare the "
            "text's length with a whole number."),
    Key("function", default="", convert=_function,
        doc="Applied to the column before the test, in any letter case: LOWER, UPPER, LOWER_FIRST, UPPER_FIRST, "
            "LENGTH, TRIM, LTRIM, RTRIM, ABS, LEFT(n) or RIGHT(n)."),
    Key("value", type=object, default="", nullable=True,
        doc="What the column is tested against. IS_NULL and IS_NOT_NULL do not read it."),
)


@REGISTRY.register
class FilterRows(Transform):
    """Keep the rows that match; the others leave by the reject output.

    A row matches when its conditions hold, combined by ``logical_op``, and,
    with ``use_advanced``, when ``condition`` holds as well. A missing value
    fails every test except ``!=``, ``NOT_CONTAINS`` and ``IS_NULL``. Each
    rejected row carries an ``errorMessage`` naming the filter it failed.
    """

    names = ("filter_rows", "FilterRows", "FilterRow", "tFilterRow", "tFilterRows")
    outputs = {"main": ("flow", "main", "filter"), "reject": ("reject",)}
    keys = (
        Key("conditions", type=list, default=[], items=_CONDITION, doc="Tests on single columns."),
        Key("logical_op", default="&&", choices=("&&", "||", "AND", "OR"),
            doc="How the conditions combine: all of them (&&, AND) or any of them (||, OR)."),
        Key("use_advanced", type=bool, default=False, doc="Whether `condition` must hold as well."),
        Key("condition", type=EXPRESSION, default="", aliases=("advanced_cond",),
            doc="A Python expression the row must satisfy as well. A column is written bare, or after the name of "
                "the incoming flow or `input_row`. Read only when `use_advanced` is on."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a missing value in a column the schema declares not nullable fails the job; "
                "when off, the row leaves by reject."),
        Key("reject_output", kind=Kind.IGNORED, type=object, doc="Old v2 flag; a reject flow is enough."),
    )

    @classmethod
    def unread_paths(cls, raw_config: Dict[str, Any]) -> List[str]:
        """The condition is not read while ``use_advanced`` is off."""
        return [] if is_on(raw_config.get("use_advanced")) else ["condition", "advanced_cond"]

    def problems(self) -> List[str]:
        found = []
        if self.config["use_advanced"] and not self.config["condition"].strip():
            found.append("condition: use_advanced is on but there is no condition")
        for index, condition in enumerate(self.config["conditions"]):
            found += [f"conditions[{index}]{problem}" for problem in _problems(condition)]
        return found

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        ((name, frame),) = inputs.items()
        types = frame.collect_schema()
        config = self.config
        tests = [self._condition(index, condition, types) for index, condition in enumerate(config["conditions"])]
        if not tests:
            keep = pl.lit(True)
        elif config["logical_op"] in _AND:
            keep = pl.all_horizontal(tests)
        else:
            keep = pl.any_horizontal(tests)
        if config["use_advanced"]:
            scope = self.row_scope(types, name, "input_row")
            keep = keep & translate_condition(config["condition"], scope)
            self.check_conversions(frame, scope, "condition")

        flagged = frame.with_columns(keep.alias(_KEEP))
        return {
            "main": flagged.filter(pl.col(_KEEP)).drop(_KEEP),
            "reject": flagged.filter(~pl.col(_KEEP)).drop(_KEEP).with_columns(
                pl.lit(self._message()).alias("errorMessage")
            ),
        }

    def _condition(self, index: int, condition: Dict[str, Any], types: pl.Schema) -> pl.Expr:
        name = condition["column"]
        if name not in types:
            raise ConfigurationError(f"conditions[{index}]: there is no column '{name}' to test")
        try:
            return _test(condition, types[name])
        except ValueError as exc:
            raise ConfigurationError(f"conditions[{index}]: column '{name}' {exc}") from None

    def _message(self) -> str:
        """Why a row was rejected, in v1's words."""
        config = self.config
        joiner = " && " if config["logical_op"] in _AND else " || "
        simple = joiner.join(
            f"{condition['column']} {condition['operator']} {condition['value']}".strip()
            for condition in config["conditions"]
        )
        parts = [config["condition"] if config["use_advanced"] else "", simple]
        return "The row does not match the filter: " + " && ".join(part for part in parts if part)


# ------------------------------------------------------------------
# One condition
# ------------------------------------------------------------------

def _problems(condition: Dict[str, Any]) -> List[str]:
    """What is wrong with a condition whatever its column holds, each as the end of a refusal."""
    operator, value, function = condition["operator"], condition["value"], condition["function"]
    if operator in ("LENGTH_LT", "LENGTH_GT") and _whole_number(value) is None:
        return [f".value: {operator} needs a whole number, not {value!r}"]
    if operator == "MATCHES":
        reason = _pattern_problem(str(value))
        if reason:
            return [f".value: MATCHES cannot use this pattern ({reason})"]
    if function in _NUMBER_FUNCTIONS:
        if operator in _TEXT_TESTS:
            return [f": {function} gives a number; {operator} tests text"]
        if operator in _COMPARISONS and _number(value) is None:
            return [f": {function} gives a number; compare it with a number, not {value!r}"]
    return []


def _test(condition: Dict[str, Any], dtype: pl.DataType) -> pl.Expr:
    """One condition as a true-or-false expression that is never missing.

    Raises:
        ValueError: When the column's type cannot take the test; the message
            completes "column 'x' ...".
    """
    operator, value = condition["operator"], condition["value"]
    column = pl.col(condition["column"])
    if dtype.is_float():
        column = column.fill_nan(None)
    column, dtype = _applied(condition["function"], column, dtype)
    if operator == "IS_NULL":
        return column.is_null()
    if operator == "IS_NOT_NULL":
        return column.is_not_null()
    if operator in _COMPARISONS:
        number = _number(value)
        if number is None:
            text = _as_text(column, dtype, f"cannot be compared with the text {str(value)!r}")
            return _compared(text, operator, str(value))
        if math.isnan(number):
            return pl.lit(operator == "!=")
        return _compared(_as_number(column, dtype, f"cannot be compared with the number {value}"), operator, number)

    text = _as_text(column, dtype, f"cannot be read as text for {operator}")
    if operator == "MATCHES":
        return text.str.contains(_whole_match(str(value))).fill_null(False)
    if operator == "CONTAINS":
        return text.str.contains(str(value), literal=True).fill_null(False)
    if operator == "NOT_CONTAINS":
        return text.str.contains(str(value), literal=True).fill_null(False).not_()
    if operator == "STARTS_WITH":
        return text.str.starts_with(str(value)).fill_null(False)
    if operator == "ENDS_WITH":
        return text.str.ends_with(str(value)).fill_null(False)
    length, limit = text.str.len_chars(), _whole_number(value)
    return (length < limit if operator == "LENGTH_LT" else length > limit).fill_null(False)


def _applied(function: str, column: pl.Expr, dtype: pl.DataType) -> Tuple[pl.Expr, pl.DataType]:
    """A condition's function applied to its column. Returns the new column and its type."""
    if not function:
        return column, dtype
    if function == "ABS":
        return _as_number(column, dtype, "ABS needs a number").abs(), pl.Float64
    text = _as_text(column, dtype, f"cannot be read as text for {function}")
    if function == "LENGTH":
        return text.str.len_chars().cast(pl.Int64), pl.Int64
    if function in _TEXT_FUNCTIONS:
        return _TEXT_FUNCTIONS[function](text), pl.String
    side, count = _SIDE.fullmatch(function).groups()
    if side == "LEFT":
        return text.str.head(int(count)), pl.String
    # v1 slices [-n:], and [-0:] is the whole text.
    return (text.str.tail(int(count)) if int(count) else text), pl.String


def _compared(left: pl.Expr, operator: str, right: Any) -> pl.Expr:
    """A comparison in which a missing value differs from everything and is otherwise false."""
    return getattr(left, _COMPARISONS[operator])(right).fill_null(operator == "!=")


# ------------------------------------------------------------------
# A column as text and as a number, the way v1 reads it
# ------------------------------------------------------------------

def _as_text(column: pl.Expr, dtype: pl.DataType, otherwise: str) -> pl.Expr:
    """A column as the text v1 tests: its values as Python's str() prints them."""
    if dtype == pl.String:
        return column
    if dtype.is_integer() or dtype == pl.Null:
        return column.cast(pl.String)
    if dtype.is_float():
        return to_text(column, dtype)
    if dtype == pl.Boolean:
        return pl.when(column).then(pl.lit("True")).when(column.not_()).then(pl.lit("False"))
    if dtype == pl.Date:
        return column.dt.strftime("%Y-%m-%d")
    if isinstance(dtype, pl.Datetime):
        # v1 writes a whole column alike; here each value shows the time and the fraction it has.
        micro = column.dt.microsecond()
        return (
            pl.when(column.dt.time() == pl.time(0)).then(column.dt.strftime("%Y-%m-%d"))
            .when(micro == 0).then(column.dt.strftime("%Y-%m-%d %H:%M:%S"))
            .when(micro % 1000 == 0).then(column.dt.strftime("%Y-%m-%d %H:%M:%S%.3f"))
            .otherwise(column.dt.strftime("%Y-%m-%d %H:%M:%S%.6f"))
        )
    raise ValueError(f"is {_kind(dtype)} and {otherwise}")


def _as_number(column: pl.Expr, dtype: pl.DataType, otherwise: str) -> pl.Expr:
    """A column as numbers; text that is not a number is missing."""
    if dtype.is_decimal():
        # Through text, which gives the nearest number; the direct cast can be one step away from it.
        return column.cast(pl.String).cast(pl.Float64)
    if dtype.is_numeric() or dtype in (pl.Boolean, pl.Null):
        return column.cast(pl.Float64)
    if dtype == pl.String:
        return column.str.strip_chars(_NUMBER_BLANKS).cast(pl.Float64, strict=False).fill_nan(None)
    raise ValueError(f"is {_kind(dtype)} and {otherwise}")


def _kind(dtype: pl.DataType) -> str:
    if dtype == pl.Date or isinstance(dtype, pl.Datetime):
        return "a date"
    return "a Decimal" if dtype.is_decimal() else f"of type {dtype}"


def _number(value: Any) -> Optional[float]:
    """The number a condition's value reads as, by v1's rule, or None when it is text."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _whole_number(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


# ------------------------------------------------------------------
# Patterns
# ------------------------------------------------------------------

def _whole_match(pattern: str) -> str:
    """A v1 pattern as one Polars matches against the whole text."""
    out, index = [], 0
    while index < len(pattern):
        if pattern[index] == "\\" and index + 1 < len(pattern):
            out.append(_SHORTHANDS.get(pattern[index + 1], pattern[index:index + 2]))
            index += 2
        else:
            out.append(pattern[index])
            index += 1
    return "^(?:" + "".join(out) + ")$"


def _pattern_problem(pattern: str) -> Optional[str]:
    """Why Polars cannot use a pattern, or None when it can."""
    try:
        pl.select(pl.lit("").str.contains(_whole_match(pattern)))
    except Exception as exc:  # noqa: BLE001 -- Polars decides what a valid pattern is
        return " ".join(str(exc).split()).split(" This error occurred")[0].split("error: ")[-1]
    return None
