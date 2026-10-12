"""Column types: what a declared type is in Polars, how text becomes a value
of that type, and how a value is written back as text.

The rules are v1's, taken from what v1 does with a column of clean values.
v1's answer for one value can change with what else is in its column; v2
gives every value the same answer.
"""
from __future__ import annotations

import dataclasses
import datetime
import re
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

import polars as pl

from .errors import ConfigurationError
from .job.model import Column

# Places a Decimal column holds when its schema declares none.
DEFAULT_DECIMAL_SCALE = 10
# 2**27 + 1: multiplying by it splits a float in two halves (Veltkamp).
_SPLIT = 134217729.0
_FIXED_LIMIT = 9.0e18
# The places a float can be asked for: ten to that power is still a whole number a float holds exactly.
_FIXED_PLACES = 15
_DECIMAL_DIGITS = 38
# Places text is read at before it is rounded to the declared ones.
_WIDE_SCALE = 18

# What Python's str.strip() removes: the code points Python calls blank. Polars' own idea of a blank
# (strip_chars with nothing named) leaves out the four separators from \x1c to \x1f.
BLANKS = "".join(map(chr, (
    *range(0x09, 0x0E), *range(0x1C, 0x21), 0x85, 0xA0, 0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F,
    0x3000,
)))

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
    # Text that is not there at all (a node a document does not have) is missing, and not unreadable. The answer
    # is yes or no, never unknown: a row with an unknown answer is neither read nor turned away, and is lost.
    return wrong.fill_null(False)


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
        return _float_text(value)
    if dtype.is_decimal():
        return _decimal_text(value, dtype, declared)
    if dtype.is_temporal():
        return _date_text(value, dtype, declared)
    return value.cast(pl.String)


def value_text(value: pl.Expr, dtype: pl.DataType, declared: Optional[Column] = None) -> pl.Expr:
    """A column as text, where a component makes text of values inside the job.

    As ``to_text`` with nothing declared (``True``, a date with its time),
    but for a Decimal whose column declares no places: v2 holds it to ten,
    and the padding (``1.5000000000``) is left off, as a file output leaves
    it off.
    """
    if dtype.is_decimal() and declared is not None and declared.type == "Decimal" and declared.precision is None:
        return to_text(value, dtype, declared)
    return to_text(value, dtype)


def plain_text(value: pl.Expr, dtype: pl.DataType, declared: Optional[Column] = None) -> pl.Expr:
    """A column as the text it is searched, converted or put together as.

    As ``value_text``, but for a date: by the pattern its column declares,
    so that the result can be read back by the same pattern; and without a
    pattern a day with no time of day is the day alone, as v1 has it.

    Args:
        value: The column.
        dtype: Its Polars type.
        declared: The column as the component's input declares it
            (``Component.declared``).
    """
    if not dtype.is_temporal() or dtype == pl.Time:
        return value_text(value, dtype, declared)
    if dtype == pl.Date or (declared is not None and declared.date_pattern):
        return to_text(value, dtype, declared)
    midnight = value.dt.time() == pl.time(0, 0, 0)
    return pl.when(midnight).then(value.dt.strftime("%Y-%m-%d")).otherwise(to_text(value, dtype))


def _float_text(value: pl.Expr) -> pl.Expr:
    """A float as Python writes it, which is what v1 writes.

    Polars spells a float the same way except below 0.0001, where Python
    has ``1e-05`` and ``1e-07`` for Polars' ``0.00001`` and ``1e-7``. Only
    those values are respelled; the others cost nothing extra.
    """
    text = value.fill_nan(None).cast(pl.String)
    respelled = (
        text.str.replace(r"e-(\d)$", "e-0${1}")
        .str.replace(r"^(-?)0\.0000([1-9])$", "${1}${2}e-05")
        .str.replace(r"^(-?)0\.0000([1-9])(\d+)$", "${1}${2}.${3}e-05")
    )
    return pl.when((value.abs() < 1e-4) & (value != 0)).then(respelled).otherwise(text)


def fixed_text(value: pl.Expr, places: int) -> pl.Expr:
    """A float with exactly ``places`` decimal places, as Python's ``'%.2f'`` writes it.

    The float is rounded as the number it exactly is, a tie going to the
    even digit: 2.675 is a little less than it looks and gives 2.67, 0.125
    is exactly halfway and gives 0.12. To know on which side a float lies,
    the part after its point is multiplied by the power of ten together
    with the error that multiplication makes (Dekker's product), which
    float arithmetic gives exactly.
    """
    value = value.fill_nan(None)
    if places > _FIXED_PLACES:
        return _float_text(value)
    power = 10 ** places
    scale = float(power)
    size = value.abs()
    units = size.floor()
    part = size - units
    product = part * scale

    def halves(number: Any) -> Tuple[Any, Any]:
        # Two floats that add up to the number, each short enough for their products to be exact.
        high = number * _SPLIT - (number * _SPLIT - number)
        return high, number - high

    high, low = halves(part)
    scale_high, scale_low = halves(scale)
    error = ((high * scale_high - product) + high * scale_low + low * scale_high) + low * scale_low
    whole = product.floor()
    # What lies beyond the last place, less one half: its sign says which way to round.
    beyond = ((product - whole) - 0.5) + error
    last = (whole if places else units) % 2
    up = (beyond > 0) | ((beyond == 0) & (last == 1))
    digits = (whole + up.cast(pl.Float64)).cast(pl.Int64)
    # Rounded up to a whole one, the part after the point carries into the units.
    carried = digits >= power
    ones = units.cast(pl.Int64, strict=False) + carried.cast(pl.Int64)
    sign = pl.when(value.cast(pl.String).str.starts_with("-")).then(pl.lit("-")).otherwise(pl.lit(""))
    if places:
        rest = pl.when(carried).then(digits - power).otherwise(digits).cast(pl.String).str.zfill(places)
        text = pl.concat_str(sign, ones.cast(pl.String), pl.lit("."), rest)
    else:
        text = pl.concat_str(sign, ones.cast(pl.String))
    # Beyond what a whole number of 64 bits holds, the float is written as it is.
    return pl.when(size < _FIXED_LIMIT).then(text).otherwise(_float_text(value))


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
    if not have.names() and columns:
        # A frame with no columns has no rows; Polars would make one row out of the columns added below.
        return pl.LazyFrame(schema=polars_schema(columns)), None
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
            # Through the digits: Polars' own cast can be one step away from the nearest float.
            return _to_places(value.cast(pl.String).cast(pl.Float64), column)
        return _to_places(value, column) if dtype.is_float() else value
    if kind == "bool":
        return value if dtype == pl.Boolean else (value != 0)
    if kind == "Decimal":
        if dtype.is_decimal():
            if column.precision is None:
                return value
            # Rounded where it stands. Read through the wider places text is read at, one of more than twenty
            # digits before its point would not fit, and would go missing.
            rounded = value.round(column.precision, mode="half_away_from_zero")
            return rounded.cast(polars_type(column), strict=False)
        if dtype.is_float():
            # A float becomes the Decimal it prints as, which is what v1 makes of it.
            value = value.cast(pl.String)
        return _to_places(value.cast(_wide_decimal(column), strict=False), column)
    if kind == "datetime":
        return value.cast(pl.Datetime("us"), strict=False) if dtype != pl.Datetime("us") else value
    return value.cast(pl.Date, strict=False) if dtype != pl.Date else value


def _bool_from_text(value: pl.Expr) -> pl.Expr:
    lower = value.str.strip_chars().str.to_lowercase()
    return pl.when(lower.is_in(_TRUE)).then(True).when(lower.is_in(_FALSE)).then(False)


# ------------------------------------------------------------------
# Values held in Python (rows a source makes from its config)
# ------------------------------------------------------------------

_BIGGEST = 2 ** 63


def _held_column(column: Column, values: List[Any]) -> pl.Series:
    """One column of rows held in Python.

    A column declared a number holds numbers when every value is one. Any
    other column holds each value as its text, which the engine reads as
    the declared type: a date written in digits (20240131) is then a date
    and not a number, and a number too long for 64 bits stays whole.
    """
    name = column.name
    if column.type == "bool":
        # A number is true unless it is zero, as v1 has it.
        values = [bool(value) if isinstance(value, (int, float)) else value for value in values]
    elif column.type == "int":
        values = [int(value) if isinstance(value, bool) else value for value in values]
    elif column.type in ("datetime", "date") and "%" in (column.date_pattern or "%"):
        seen: Dict[str, str] = {}
        values = [seen.setdefault(value, _by_pattern(value, column.date_pattern)) if isinstance(value, str) else value
                  for value in values]
    held = [value for value in values if value is not None]
    numbers = held and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in held)
    if column.type in ("int", "float") and numbers:
        if all(isinstance(value, int) and -_BIGGEST <= value < _BIGGEST for value in held):
            return pl.Series(name, values, dtype=pl.Int64)
        if column.type == "float" or not all(isinstance(value, int) for value in held):
            return pl.Series(name, [None if value is None else float(value) for value in values], dtype=pl.Float64)
    return pl.Series(name, [None if value is None else str(value) for value in values], dtype=pl.String)


# How a date is written when not by its column's pattern: the engine's own three ways, and ISO 8601's with a T.
_USUAL_DATES = _DEFAULT_DATE_PATTERNS + ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f")


def _by_pattern(value: str, pattern: Optional[str]) -> str:
    """A date written one of the usual ways, as the text its column reads; any other text as it is.

    The text is the one the column's pattern writes, or, for a column with
    no pattern, the first of the ways the engine reads such a column by.
    """
    for known in ((pattern,) if pattern else ()) + _USUAL_DATES:
        try:
            read = datetime.datetime.strptime(value.strip(), known)
        except ValueError:
            continue
        if pattern:
            return read.strftime(pattern)
        # A column with no pattern holds no fraction of a second: such a moment is left as it is written.
        return value if read.microsecond else read.strftime("%Y-%m-%d %H:%M:%S")
    return value


def held_frame(columns: List[Column], rows: List[Dict[str, Any]]) -> pl.DataFrame:
    """Rows held in Python, each as column to value, as a frame the engine reads as the declared columns.

    For a source that makes its rows from its config. As for every reader,
    where true or false may be missing, nothing given is false; where it
    may not be missing, empty text is false and a missing value stays one.
    A date may be written by its column's pattern or one of the usual ways
    (2024-01-31, with a time after a blank or a T, or 31/01/2024), as v1
    reads a column none of whose dates is written by the pattern.
    """
    frame = pl.DataFrame([_held_column(column, [row.get(column.name) for row in rows]) for column in columns])
    made = []
    for column in columns:
        if column.type == "bool":
            text = pl.col(column.name)
            nothing = (text.fill_null("") if column.nullable else text) == ""
            made.append(pl.when(nothing).then(False).otherwise(from_text(text, column)[0]).alias(column.name))
    return frame.with_columns(made)
