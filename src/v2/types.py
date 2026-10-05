"""Column types: what a declared type is in Polars, how text becomes a value
of that type, and how a value is written back as text.

The rules are v1's, taken from what v1 does with a column of clean values.
v1's answer for one value can change with what else is in its column; v2
gives every value the same answer.
"""
from __future__ import annotations

import dataclasses
import re
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple

import polars as pl

from .errors import ConfigurationError
from .job.model import Column

# Places a Decimal column holds when its schema declares none.
DEFAULT_DECIMAL_SCALE = 10
_DECIMAL_DIGITS = 38
# Places text is read at before it is rounded to the declared ones.
_WIDE_SCALE = 18

_TRUE = ("true", "1", "yes")
_FALSE = ("false", "0", "no")
_NOT_A_DATE = ("NaN", "nan", "NaT")
_ERROR_COLUMNS = ("errorCode", "errorMessage")
_DEFAULT_DATE_PATTERNS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y")
_JAVA_DATE_TOKENS = (
    ("yyyy", "%Y"), ("yy", "%y"), ("MM", "%m"), ("dd", "%d"), ("HH", "%H"), ("hh", "%I"),
    ("mm", "%M"), ("ss", "%S"), ("SSS", "%f"),
)
_JAVA_DATE_TOKEN = re.compile("|".join(token for token, _ in _JAVA_DATE_TOKENS))


def polars_type(column: Column) -> pl.DataType:
    """The Polars type that holds a declared column."""
    if column.type == "Decimal":
        scale = DEFAULT_DECIMAL_SCALE if column.precision is None else column.precision
        return pl.Decimal(_DECIMAL_DIGITS, scale)
    return {
        "str": pl.String,
        "int": pl.Int64,
        "float": pl.Float64,
        "bool": pl.Boolean,
        "datetime": pl.Datetime("us"),
        "date": pl.Date,
    }[column.type]


def polars_schema(columns: Iterable[Column]) -> Dict[str, pl.DataType]:
    """Column name to Polars type, in declared order."""
    return {column.name: polars_type(column) for column in columns}


def chrono_format(pattern: str, parsing: bool) -> str:
    """Turn a date pattern into the one Polars wants.

    Job configs carry Python ``strftime`` patterns. Polars reads the same
    letters except for fractions of a second. A pattern with no ``%`` in it
    is taken to be Java style (``yyyy-MM-dd``) and translated first.
    """
    if "%" not in pattern:
        pattern = _JAVA_DATE_TOKEN.sub(lambda match: dict(_JAVA_DATE_TOKENS)[match.group(0)], pattern)
    out: List[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "%" and index + 1 < len(pattern):
            directive = pattern[index + 1]
            if directive == "f":
                if parsing and out and out[-1] == ".":
                    out[-1] = "%.f"
                else:
                    out.append("%6f")
            else:
                out.append("%" + directive)
            index += 2
        else:
            out.append(char)
            index += 1
    return "".join(out)


# ------------------------------------------------------------------
# Text to values
# ------------------------------------------------------------------

def from_text(text: pl.Expr, column: Column) -> Tuple[pl.Expr, pl.Expr]:
    """Read a text column as a declared column.

    Args:
        text: The text, never missing (an empty field is empty text).
        column: The declared column.

    Returns:
        The value, and whether the text was there but could not be read.
        Text that is empty or blank gives a missing value and is not
        unreadable; whether a missing value is allowed is the caller's to
        check.

    This parses the text twice, once for each answer. A reader of a large
    file keeps the parsed column instead: ``parse_text``, then ``unreadable``
    and ``finish_value`` on the column it made.
    """
    parsed = parse_text(text, column)
    return finish_value(parsed, text, column), unreadable(parsed, text, column)


def parse_text(text: pl.Expr, column: Column) -> pl.Expr:
    """Text as the column's type; missing where it is empty or cannot be read."""
    if column.type == "str":
        return text
    stripped = text.str.strip_chars()
    if column.type == "bool":
        lower = stripped.str.to_lowercase()
        return pl.when(lower.is_in(_TRUE)).then(True).when(lower.is_in(_FALSE)).then(False)
    if column.type == "int":
        as_float = stripped.cast(pl.Float64, strict=False)
        whole = pl.when(as_float.is_finite()).then(as_float).cast(pl.Int64, strict=False)
        return pl.coalesce(stripped.cast(pl.Int64, strict=False), whole)
    if column.type == "float":
        return stripped.cast(pl.Float64, strict=False)
    if column.type == "Decimal":
        return stripped.cast(_wide_decimal(column), strict=False)
    target = pl.Datetime("us") if column.type == "datetime" else pl.Date
    patterns = (column.date_pattern,) if column.date_pattern else _DEFAULT_DATE_PATTERNS
    attempts = [
        stripped.str.strptime(target, chrono_format(pattern, parsing=True), strict=False) for pattern in patterns
    ]
    return attempts[0] if len(attempts) == 1 else pl.coalesce(attempts)


def unreadable(parsed: pl.Expr, text: pl.Expr, column: Column) -> pl.Expr:
    """Whether text was there but could not be read, given what ``parse_text`` made of it."""
    if column.type == "str":
        return pl.lit(False)
    stripped = text.str.strip_chars()
    wrong = parsed.is_null() & (stripped != "")
    if column.type in ("datetime", "date"):
        wrong = wrong & ~stripped.is_in(_NOT_A_DATE)
    return wrong


def finish_value(parsed: pl.Expr, text: pl.Expr, column: Column) -> pl.Expr:
    """The value a reader hands on, given what ``parse_text`` made of the text."""
    if column.type == "bool" and column.nullable:
        return pl.when(text.str.strip_chars() == "").then(False).otherwise(parsed)
    if column.type == "float":
        parsed = parsed.fill_nan(None)
    return _to_places(parsed, column)


def _wide_decimal(column: Column) -> pl.DataType:
    if column.precision is None:
        return pl.Decimal(_DECIMAL_DIGITS, DEFAULT_DECIMAL_SCALE)
    return pl.Decimal(_DECIMAL_DIGITS, max(_WIDE_SCALE, column.precision))


def _to_places(value: pl.Expr, column: Column) -> pl.Expr:
    """Round a value to the column's declared decimal places."""
    if column.precision is None:
        return value
    if column.type == "float":
        return value.round(column.precision)
    if column.type == "Decimal":
        return value.round(column.precision, mode="half_away_from_zero").cast(polars_type(column))
    return value


# ------------------------------------------------------------------
# Values to text
# ------------------------------------------------------------------

def to_text(value: pl.Expr, dtype: pl.DataType, declared: Optional[Column] = None) -> pl.Expr:
    """Write a column as text, the way v1's file outputs write it.

    Args:
        value: The column.
        dtype: Its Polars type.
        declared: The column as the writing component declares it, when it
            does. It gives the date pattern and the decimal places.
    """
    if dtype == pl.String:
        return value
    if dtype == pl.Boolean:
        if declared is not None and declared.type == "bool":
            return value.cast(pl.String)
        return value.cast(pl.String).str.to_titlecase()
    if dtype.is_float():
        return value.fill_nan(None).cast(pl.String)
    if dtype.is_decimal():
        return _decimal_text(value, dtype, declared)
    if dtype.is_temporal():
        return _date_text(value, dtype, declared)
    return value.cast(pl.String)


def _decimal_text(value: pl.Expr, dtype: pl.DataType, declared: Optional[Column]) -> pl.Expr:
    if declared is None or declared.type != "Decimal":
        return value.cast(pl.String)
    if declared.precision is not None:
        return value.cast(pl.Decimal(_DECIMAL_DIGITS, declared.precision)).cast(pl.String)
    text = value.cast(pl.String)
    if dtype.scale:
        text = text.str.strip_chars_end("0").str.strip_chars_end(".")
    return text


def _date_text(value: pl.Expr, dtype: pl.DataType, declared: Optional[Column]) -> pl.Expr:
    pattern = declared.date_pattern if declared is not None else None
    if pattern:
        return value.dt.strftime(chrono_format(pattern, parsing=False))
    if dtype == pl.Date:
        return value.dt.strftime("%Y-%m-%d")
    if dtype == pl.Time:
        return value.cast(pl.String)
    plain = value.dt.strftime("%Y-%m-%d %H:%M:%S")
    return pl.when(value.dt.microsecond() == 0).then(plain).otherwise(value.dt.strftime("%Y-%m-%d %H:%M:%S.%6f"))


# ------------------------------------------------------------------
# Matching a declared schema
# ------------------------------------------------------------------

def conform(
    frame: pl.LazyFrame, columns: List[Column], rename_errors: bool = False
) -> Tuple[pl.LazyFrame, Optional[pl.Expr]]:
    """Make a frame match a declared schema, as v1 does after every component.

    Declared columns come first, in declared order; other columns follow.
    A declared column the frame lacks is added: missing, or zero when the
    column may not be missing. Values are turned into the declared type
    where they are of another kind, and rounded to the declared places.

    Args:
        frame: The frame a component produced.
        columns: The component's declared columns.
        rename_errors: Rename ``errorCode`` and ``errorMessage`` columns to
            ``errorCode_user`` and ``errorMessage_user``, which v1 does to
            every component's main output.

    Returns:
        The frame, and an expression over it that says, per row, which
        column holds a missing value it may not hold (None when the schema
        forbids none). The expression must be evaluated on the returned
        frame.
    """
    have = frame.collect_schema()
    # An error column renamed by an earlier component stands in for the name a schema still declares.
    renamed = {
        name: f"{name}_user" for name in _ERROR_COLUMNS
        if rename_errors and name not in have and f"{name}_user" in have
    }
    columns = [dataclasses.replace(column, name=renamed.get(column.name, column.name)) for column in columns]
    exprs: List[pl.Expr] = []
    broken: List[pl.Expr] = []
    for column in columns:
        if column.name not in have:
            exprs.append(_absent(column).alias(column.name))
            continue
        current = pl.col(column.name)
        if not column.nullable:
            broken.append(
                pl.when(current.is_null()).then(pl.lit(f"Column '{column.name}': non-nullable column has null"))
            )
        exprs.append(_coerced(current, have[column.name], column).alias(column.name))
    declared = [column.name for column in columns]
    extras = [name for name in have.names() if name not in set(declared)]

    violation: Optional[pl.Expr] = None
    if broken:
        frame = frame.with_columns(pl.coalesce(broken).alias(VIOLATION))
        extras = [name for name in extras if name != VIOLATION]
        violation = pl.col(VIOLATION)
    selected = exprs + [pl.col(name) for name in extras] + ([pl.col(VIOLATION)] if broken else [])
    frame = frame.select(selected)
    if rename_errors:
        renames = {name: f"{name}_user" for name in _ERROR_COLUMNS if name in declared + extras}
        if renames:
            frame = frame.rename(renames)
    return frame, violation


# Name of the working column `conform` adds when a schema forbids missing values.
VIOLATION = "__violation"


def _absent(column: Column) -> pl.Expr:
    """What a declared column holds when no component produced it."""
    dtype = polars_type(column)
    if column.nullable:
        return pl.lit(None, dtype=dtype)
    zero = {
        "str": "",
        "int": 0,
        "float": 0.0,
        "bool": False,
        "datetime": pl.datetime(1970, 1, 1),
        "date": pl.date(1970, 1, 1),
        "Decimal": Decimal(0),
    }[column.type]
    value = zero if isinstance(zero, pl.Expr) else pl.lit(zero)
    return value.cast(dtype)


def _coerced(value: pl.Expr, dtype: pl.DataType, column: Column) -> pl.Expr:
    """A produced column as its declared type. Values that do not fit go missing."""
    kind = column.type
    if kind == "str":
        return value
    if dtype.is_temporal() != (kind in ("datetime", "date")) and dtype != pl.String:
        raise ConfigurationError(
            f"column '{column.name}' is declared {kind} but holds {dtype}; one cannot be turned into the other"
        )
    if dtype == pl.String:
        return from_text(value.fill_null(""), column)[0] if kind != "bool" else _bool_from_text(value)
    if kind == "int":
        if dtype.is_integer():
            return value
        if dtype.is_float():
            return pl.when(value.is_finite()).then(value).cast(pl.Int64, strict=False)
        return value.cast(pl.Int64, strict=False)
    if kind == "float":
        if dtype.is_decimal():
            return _to_places(value.cast(pl.Float64), column)
        return _to_places(value, column) if dtype.is_float() else value
    if kind == "bool":
        return value if dtype == pl.Boolean else (value != 0)
    if kind == "Decimal":
        if dtype.is_decimal() and column.precision is None:
            return value
        return _to_places(value.cast(_wide_decimal(column), strict=False), column)
    if kind == "datetime":
        return value.cast(pl.Datetime("us"), strict=False) if dtype != pl.Datetime("us") else value
    return value.cast(pl.Date, strict=False) if dtype != pl.Date else value


def _bool_from_text(value: pl.Expr) -> pl.Expr:
    lower = value.str.strip_chars().str.to_lowercase()
    return pl.when(lower.is_in(_TRUE)).then(True).when(lower.is_in(_FALSE)).then(False)
