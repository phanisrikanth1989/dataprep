"""Filter rows: keep the rows that match, send the rest to reject."""
from __future__ import annotations

import re
from typing import Any, Dict, List

import polars as pl

from ...errors import ConfigurationError
from ...expressions import translate
from ...job.keys import EXPRESSION, Key, Kind
from ..base import Transform
from ..registry import REGISTRY

_OPERATORS = (
    "==", "!=", ">", "<", ">=", "<=", "MATCHES", "CONTAINS", "NOT_CONTAINS", "STARTS_WITH",
    "ENDS_WITH", "IS_NULL", "IS_NOT_NULL", "LENGTH_LT", "LENGTH_GT",
)
_LOGICAL = {"&&": "and", "||": "or", "AND": "and", "OR": "or", "and": "and", "or": "or"}
_SIDE = re.compile(r"(LEFT|RIGHT)\((\d+)\)")

_CONDITION = (
    Key("column", required=True, doc="The column the condition tests."),
    Key("operator", default="==", choices=_OPERATORS, doc="The test."),
    Key("function", default="", doc="Applied to the column before the test: LOWER, TRIM, LEFT(n)..."),
    Key("value", type=object, default="", doc="What the column is tested against."),
)


def _logical(value: str) -> str:
    if value not in _LOGICAL:
        raise ValueError(f"{value!r} is not allowed; use one of '&&', '||', 'AND', 'OR'")
    return _LOGICAL[value]


@REGISTRY.register
class FilterRows(Transform):
    """Keep the rows that match; the others leave by the reject output."""

    names = ("filter_rows", "FilterRows", "FilterRow", "tFilterRow", "tFilterRows")
    outputs = {"main": ("flow", "main", "filter"), "reject": ("reject",)}
    keys = (
        Key("conditions", type=list, default=[], items=_CONDITION, doc="Tests on single columns."),
        Key("logical_op", default="&&", convert=_logical, doc="How the conditions combine: && or ||."),
        Key("condition", type=EXPRESSION, default="", aliases=("advanced_cond",),
            doc="A Python expression a row must also satisfy."),
        Key("use_advanced", type=bool, nullable=True,
            doc="Set to false to switch the expression off without deleting it."),
        Key("reject_output", kind=Kind.IGNORED, type=object, doc="Old v2 flag; a reject flow is enough."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (name, frame), = inputs.items()
        types = frame.collect_schema()
        keep = self._conditions(types)
        expression = self._expression()
        if expression:
            matches = translate(expression, self.row_scope(types, name, "input_row"))
            keep = keep & matches.cast(pl.Boolean).fill_null(False)

        flagged = frame.with_columns(keep.alias("__keep"))
        return {
            "main": flagged.filter(pl.col("__keep")).drop("__keep"),
            "reject": flagged.filter(~pl.col("__keep")).drop("__keep").with_columns(
                pl.lit(self._message(expression)).alias("errorMessage")
            ),
        }

    def _expression(self) -> str:
        if self.config["use_advanced"] is False:
            return ""
        expression = (self.config["condition"] or "").strip()
        if self.config["use_advanced"] and not expression:
            raise ConfigurationError("condition: use_advanced is set but there is no expression")
        return expression

    def _conditions(self, types: pl.Schema) -> pl.Expr:
        tests: List[pl.Expr] = []
        for condition in self.config["conditions"]:
            if condition["column"] not in types:
                raise ConfigurationError(f"conditions: there is no column '{condition['column']}' to test")
            tests.append(_test(condition, types[condition["column"]]))
        if not tests:
            return pl.lit(True)
        keep = tests[0]
        for test in tests[1:]:
            keep = (keep & test) if self.config["logical_op"] == "and" else (keep | test)
        return keep

    def _message(self, expression: str) -> str:
        joiner = " && " if self.config["logical_op"] == "and" else " || "
        simple = joiner.join(
            f"{c['column']} {c['operator']} {c['value']}".strip() for c in self.config["conditions"]
        )
        parts = [part for part in (expression, simple) if part]
        return "The row does not match the filter: " + (" && ".join(parts) or "filter condition")


def _as_text(column: pl.Expr, dtype: pl.DataType) -> pl.Expr:
    return column if dtype == pl.String else column.cast(pl.String)


def _apply_function(column: pl.Expr, dtype: pl.DataType, function: str):
    """Apply a condition's function. Returns the new column and its type."""
    name = (function or "").upper().strip()
    if not name:
        return column, dtype
    text = _as_text(column, dtype)
    simple = {
        "LOWER": lambda: text.str.to_lowercase(),
        "UPPER": lambda: text.str.to_uppercase(),
        "LOWER_FIRST": lambda: text.str.slice(0, 1).str.to_lowercase(),
        "UPPER_FIRST": lambda: text.str.slice(0, 1).str.to_uppercase(),
        "TRIM": lambda: text.str.strip_chars(),
        "LTRIM": lambda: text.str.strip_chars_start(),
        "RTRIM": lambda: text.str.strip_chars_end(),
    }
    if name in simple:
        return simple[name](), pl.String
    if name == "LENGTH":
        return text.str.len_chars().cast(pl.Int64), pl.Int64
    if name == "ABS":
        return _as_number(column, dtype).abs(), pl.Float64
    side = _SIDE.fullmatch(name)
    if side:
        count = int(side.group(2))
        return (text.str.head(count) if side.group(1) == "LEFT" else text.str.tail(count)), pl.String
    raise ConfigurationError(f"conditions: unknown function '{function}'")


def _as_number(column: pl.Expr, dtype: pl.DataType) -> pl.Expr:
    if dtype.is_numeric():
        return column.cast(pl.Float64)
    return column.cast(pl.String).str.strip_chars().cast(pl.Float64, strict=False)


def _number(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compare(left: pl.Expr, operator: str, right: Any) -> pl.Expr:
    if operator == "==":
        return (left == right).fill_null(False)
    if operator == "!=":
        return (left != right).fill_null(True)
    if operator == ">":
        return (left > right).fill_null(False)
    if operator == "<":
        return (left < right).fill_null(False)
    if operator == ">=":
        return (left >= right).fill_null(False)
    return (left <= right).fill_null(False)


def _test(condition: Dict[str, Any], dtype: pl.DataType) -> pl.Expr:
    """One condition as a true-or-false expression that is never missing."""
    operator, value = condition["operator"], condition["value"]
    column, dtype = _apply_function(pl.col(condition["column"]), dtype, condition["function"])
    if operator == "IS_NULL":
        return column.is_null()
    if operator == "IS_NOT_NULL":
        return column.is_not_null()
    if operator in ("==", "!=", ">", "<", ">=", "<="):
        number = _number(value)
        if number is not None:
            return _compare(_as_number(column, dtype), operator, number)
        return _compare(_as_text(column, dtype), operator, str(value))

    text = _as_text(column, dtype)
    if operator == "MATCHES":
        return text.str.contains(f"^(?:{value})$").fill_null(False)
    if operator == "CONTAINS":
        return text.str.contains(str(value), literal=True).fill_null(False)
    if operator == "NOT_CONTAINS":
        return ~text.str.contains(str(value), literal=True).fill_null(False)
    if operator == "STARTS_WITH":
        return text.str.starts_with(str(value)).fill_null(False)
    if operator == "ENDS_WITH":
        return text.str.ends_with(str(value)).fill_null(False)
    length = text.str.len_chars()
    if operator == "LENGTH_LT":
        return (length < int(value)).fill_null(False)
    return (length > int(value)).fill_null(False)
