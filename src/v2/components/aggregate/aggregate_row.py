"""Aggregate row: group rows and compute one value per group."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ...job.model import Column
from ...types import to_text
from ..base import Transform
from ..registry import REGISTRY

_FUNCTIONS = (
    "count", "min", "max", "avg", "sum", "first", "last", "list", "list_object", "count_distinct", "std",
    "population_std_dev", "median", "variance", "union",
)
_SPREAD = ("std", "population_std_dev", "variance")
_ADD = ("sum", "avg") + _SPREAD
_NEED_NUMBERS = _ADD + ("median",)
_WHOLE = "__whole"

# A float is added as the decimal it prints as, held to this many places.
_EXACT = pl.Decimal(38, 18)
# Floats from here up are added as plain floats: none of their decimal places is exact any more.
_EXACT_LIMIT = 1e15
# Places a quotient is tried at, most first; the first that can hold the total and the count is used.
_QUOTIENT_PLACES = (36, 30, 24, 18, 12, 6, 0)
# Distances from the mean are squared exactly when none has more places than this, so that a square fits the
# 18 places, and when the squares are sure to add up to less than the limit: 18 places leave room for 1.7e20.
_SQUARED_PLACES = 9
_SQUARES_LIMIT = 1e19


def _column(value: str) -> str:
    if not value:
        raise ValueError("must not be empty")
    return value


def _lower(value: str) -> str:
    return value.lower()


_GROUP = (
    Key("input_column", required=True, convert=_column, doc="The column to group by."),
    Key("output_column", doc="Its name in the output; the same name when left out."),
)
_OPERATION = (
    Key("function", required=True, convert=_lower, choices=_FUNCTIONS,
        doc="What is computed over the group's rows. Upper and lower case are the same."),
    Key("input_column", required=True, convert=_column, doc="The column the function reads."),
    Key("output_column", doc="The column the result goes to; named after the input column when left out."),
    Key("ignore_null", type=bool, default=True,
        doc="Whether missing values are skipped. When false, a group holding one has no min, max, sum, avg or "
            "spread, and its lists show it as `null`. count, count_distinct, first and last always skip them."),
    Key("delimiter", kind=Kind.IGNORED, type=object, doc="Written by the converter; `list_delimiter` is the one read."),
)


@dataclass(frozen=True)
class _Input:
    """The column an operation reads.

    Attributes:
        column: The column.
        dtype: Its type.
        decimal: The column as a Decimal of 18 places, for a column of
            numbers. A float is the decimal it prints as, and missing from a
            quadrillion up.
    """

    column: pl.Expr
    dtype: pl.DataType
    decimal: Optional[pl.Expr] = None


class _Parts:
    """The aggregates one operation needs, named so that operations do not collide."""

    def __init__(self, index: int) -> None:
        self.prefix = f"__{index}_"
        self.aggregates: List[pl.Expr] = []

    def add(self, name: str, aggregate: pl.Expr) -> pl.Expr:
        """Ask for an aggregate; returns the column that will hold it."""
        self.aggregates.append(aggregate.alias(self.prefix + name))
        return pl.col(self.prefix + name)


@REGISTRY.register
class AggregateRow(Transform):
    """Group rows and compute one value per group.

    Groups come out in the order their first row arrives. A row with a
    missing value in a group column belongs to no group. No input rows give
    no output rows, also without group columns.

    Numbers are always added exactly, a float as the decimal it prints as, so
    a sum does not depend on the order of the rows. With
    ``use_financial_precision`` (the default) sum, avg, min and max stay
    decimals: the result is a Decimal where the output column is declared
    Decimal and the nearest float where it is declared float; undeclared, the
    sum, min or max of whole numbers or Decimals is a Decimal and everything
    else a float. An average kept as a Decimal holds 18 decimal places.
    Without it, sum, min and max have the type of their column and an average
    is the sum divided as a float.

    A median and a standard deviation are floats either way; a variance is a
    float, or a Decimal in a column declared Decimal.
    """

    names = ("aggregate_row", "AggregateRow", "tAggregateRow")
    keys = (
        Key("groupbys", type=list, default=[], items=_GROUP,
            doc="The columns to group by. Without any, the whole input is one group."),
        Key("operations", type=list, default=[], items=_OPERATION,
            doc="The values to compute per group. Of two that name one output column, the last counts."),
        Key("list_delimiter", default=",", doc="What separates the values of `list` and `union`."),
        Key("use_financial_precision", type=bool, default=True,
            doc="Whether sum, avg, min and max of numbers are decimals, or have the type of their column."),
        Key("check_type_overflow", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("check_ulp", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
    )

    def problems(self) -> List[str]:
        config, found = self.config, []
        if not config["groupbys"] and not config["operations"]:
            found.append("operations: nothing to aggregate: give groupbys, operations or both")
        groups = [output for _, output in self._groups()]
        for index, name in enumerate(groups):
            if name in groups[:index]:
                found.append(f"groupbys: two group columns are named '{name}'")
        for output in self._operations():
            if output in groups:
                found.append(f"operations: '{output}' is also a group column")
        return found

    def _groups(self) -> List[Tuple[str, str]]:
        """Each group column as (input name, output name)."""
        return [
            (entry["input_column"], entry["output_column"] or entry["input_column"])
            for entry in self.config["groupbys"]
        ]

    def _operations(self) -> Dict[str, Dict[str, Any]]:
        """The operations by output column, in the order the columns are first named."""
        return {entry["output_column"] or entry["input_column"]: entry for entry in self.config["operations"]}

    # ------------------------------------------------------------------
    # The plan
    # ------------------------------------------------------------------

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        types = frame.collect_schema()
        groups, operations = self._groups(), self._operations()
        read = [entry["input_column"] for entry in operations.values()]
        used = list(dict.fromkeys([name for name, _ in groups] + read))
        for name in used:
            if name not in types:
                raise ConfigurationError(f"there is no column '{name}' to aggregate")

        # NaN is a missing value here as everywhere else in a job.
        floats = [name for name in used if types[name].is_float()]
        if floats:
            frame = frame.with_columns([pl.col(name).fill_nan(None) for name in floats])
        # A float's decimal is worked out row by row before the rows are grouped: inside a group it is far slower.
        added = {entry["input_column"] for entry in operations.values() if entry["function"] in _ADD}
        decimals = {name: f"__decimal_{index}" for index, name in enumerate(floats) if name in added}
        if decimals:
            frame = frame.with_columns([_decimal_of_float(pl.col(name)).alias(held) for name, held in decimals.items()])

        aggregates: List[pl.Expr] = []
        results: List[pl.Expr] = []
        for index, (output, operation) in enumerate(operations.items()):
            name = operation["input_column"]
            decimal = None
            if types[name].is_numeric():
                decimal = pl.col(decimals[name]) if name in decimals else pl.col(name).cast(_EXACT, strict=False)
            parts = _Parts(index)
            value = self._value(operation, _Input(pl.col(name), types[name], decimal), parts, output)
            aggregates += parts.aggregates
            results.append(value.alias(output))

        keys = list(dict.fromkeys(name for name, _ in groups))
        if keys:
            frame = frame.filter(pl.all_horizontal([pl.col(name).is_not_null() for name in keys]))
        else:
            # The whole input is one group, grouped on a constant like any other: no rows then give no group,
            # and a plain select of aggregates comes out one row per input row on Polars' in-memory engine
            # when two of them share a part.
            frame, keys = frame.with_columns(pl.lit(True).alias(_WHOLE)), [_WHOLE]
        aggregated = frame.group_by(keys, maintain_order=True).agg(aggregates)
        made = aggregated.select([pl.col(name).alias(output) for name, output in groups] + results)
        return {"main": self._as_declared(made)}

    def _as_declared(self, frame: pl.LazyFrame) -> pl.LazyFrame:
        """Hand floats over as Decimals, and Decimals as floats, where the output columns are declared so.

        v1 turns a float into the Decimal it prints as, and a Decimal into
        the float nearest to it. Polars' own casts between the two are not
        that exact, so both go through the digits here.
        """
        types = frame.collect_schema()
        exprs = []
        for column in self.schema:
            dtype = types.get(column.name)
            if dtype is None:
                continue
            if column.type == "Decimal" and dtype.is_float():
                exprs.append(_decimal_of(pl.col(column.name)))
            elif column.type == "float" and dtype.is_decimal():
                exprs.append(_float_of(pl.col(column.name)))
        return frame.with_columns(exprs) if exprs else frame

    # ------------------------------------------------------------------
    # One operation
    # ------------------------------------------------------------------

    def _value(self, operation: Dict[str, Any], source: _Input, parts: _Parts, output: str) -> pl.Expr:
        """The result of one operation, as an expression over its aggregates."""
        function, column = operation["function"], source.column
        if function in _NEED_NUMBERS and not source.dtype.is_numeric():
            raise ConfigurationError(
                f"operations: {function} needs a column of numbers, and '{operation['input_column']}' is not one"
            )
        declared: Optional[Column] = next((entry for entry in self.schema if entry.name == output), None)

        if function == "count":
            return parts.add("n", column.count()).cast(pl.Int64)
        if function == "count_distinct":
            return parts.add("n", column.drop_nulls().n_unique()).cast(pl.Int64)
        if function == "first":
            return parts.add("v", column.drop_nulls().first())
        if function == "last":
            return parts.add("v", column.drop_nulls().last())
        if function in ("list", "list_object", "union"):
            return self._listed(function, source, parts, operation["ignore_null"])
        if function == "median":
            # v1's median skips missing values whatever ignore_null says, unless use_financial_precision is off.
            skip = operation["ignore_null"] or self.config["use_financial_precision"]
            number = _as_float(column, source.dtype)
            low = parts.add("low", number.quantile(0.5, "lower"))
            high = parts.add("high", number.quantile(0.5, "higher"))
            return _unless_missing((low + high) / 2, column, parts, skip)
        if function in _SPREAD:
            value = _spread(function, source, parts, declared)
        elif self.config["use_financial_precision"] and source.dtype.is_numeric():
            value = _decimal(function, source, parts, declared)
        else:
            value = _plain(function, source, parts)
        return _unless_missing(value, column, parts, operation["ignore_null"])

    def _listed(self, function: str, source: _Input, parts: _Parts, ignore_null: bool) -> pl.Expr:
        text = _as_text(source.column, source.dtype)
        text = text.drop_nulls() if ignore_null else text.fill_null("null")
        if function == "union":
            text = text.unique().sort()
        if function == "list_object":
            return pl.format("[{}]", parts.add("v", text.str.join(", ")))
        return parts.add("v", text.str.join(self.config["list_delimiter"]))


# ------------------------------------------------------------------
# sum, avg, min and max
# ------------------------------------------------------------------

def _decimal(function: str, source: _Input, parts: _Parts, declared: Optional[Column]) -> pl.Expr:
    """sum, avg, min or max of numbers with use_financial_precision: a Decimal, or the float nearest to it."""
    if function in ("min", "max"):
        found = parts.add("v", source.column.min() if function == "min" else source.column.max())
        return found.cast(pl.Decimal(38, 0)) if source.dtype.is_integer() else found

    exact, fallback = _decimal_sum(source)
    total = parts.add("total", exact)
    plain = None if fallback is None else parts.add("plain", fallback)
    as_decimal = declared is not None and declared.type == "Decimal"
    if function == "sum":
        if plain is None:
            return total
        return pl.coalesce(total, _decimal_of(plain)) if as_decimal else pl.coalesce(_float_of(total), plain)

    count = parts.add("n", source.column.count()).cast(pl.Int64)
    count = pl.when(count > 0).then(count)
    if as_decimal:
        quotient = _decimal_quotient(total, count, _places(declared))
        return quotient if plain is None else pl.coalesce(quotient, _decimal_of(plain / count, _places(declared)))
    quotient = _float_quotient(total, count)
    return quotient if plain is None else pl.coalesce(quotient, plain / count)


def _plain(function: str, source: _Input, parts: _Parts) -> pl.Expr:
    """sum, avg, min or max without use_financial_precision: in the column's own type, an average as a float."""
    if function == "min":
        return parts.add("v", source.column.min())
    if function == "max":
        return parts.add("v", source.column.max())
    if function == "sum":
        return parts.add("total", _float_sum(source) if source.dtype.is_float() else source.column.sum())
    count = parts.add("n", source.column.count()).cast(pl.Int64)
    return parts.add("total", _float_sum(source)) / pl.when(count > 0).then(count)


def _decimal_sum(source: _Input) -> Tuple[pl.Expr, Optional[pl.Expr]]:
    """A group's sum as a Decimal and, for a float column, the float sum to use when there is none.

    The Decimal is missing when a float of the group cannot be held as one:
    a quadrillion or more, or infinite.
    """
    if source.dtype.is_integer():
        return source.column.cast(pl.Decimal(38, 0)).sum(), None
    if source.dtype.is_decimal():
        return source.column.sum(), None
    held = (source.column.is_null() | source.decimal.is_not_null()).all()
    return pl.when(held).then(source.decimal.sum()), source.column.sum()


def _float_sum(source: _Input) -> pl.Expr:
    """A group's sum as the float nearest to it, whatever order its rows come in."""
    if source.dtype.is_integer():
        return source.column.sum().cast(pl.Float64)
    exact, fallback = _decimal_sum(source)
    return _float_of(exact) if fallback is None else pl.coalesce(_float_of(exact), fallback)


# ------------------------------------------------------------------
# std, population_std_dev and variance
# ------------------------------------------------------------------

def _spread(function: str, source: _Input, parts: _Parts, declared: Optional[Column]) -> pl.Expr:
    """Variance or standard deviation: the squared distances from the mean, averaged.

    The distances are taken as decimals. Where they can be squared and added
    without losing a digit, the variance is exact: a Decimal in a column
    declared Decimal, else the float nearest to it. Otherwise the squares are
    floats, added one by one, smallest first: that sum depends on the values
    only, where a plain float sum depends on the order rows arrive in and, on
    the streaming engine, on the run. The running sum keeps Polars from
    dropping the sort. A standard deviation is the float root of the float
    variance.
    """
    column = source.column
    count = column.count().cast(pl.Int64)
    total, _ = _decimal_sum(source)
    distance = source.decimal - total.cast(_EXACT, strict=False) / pl.when(count > 0).then(count)
    apart = pl.coalesce(distance.cast(pl.Float64), _as_float(column, source.dtype) - _float_sum(source) / count)
    floats = parts.add("floats", (apart * apart).drop_nulls().sort().cum_sum().last())

    short = distance.cast(pl.Decimal(38, _SQUARED_PLACES), strict=False)
    short_enough = (column.is_null() | (distance == short).fill_null(False)).all()
    small_enough = distance.abs().max().cast(pl.Float64).pow(2) * count < _SQUARES_LIMIT
    short = pl.when(short_enough & small_enough).then(short)
    exact = (short.cast(_EXACT, strict=False) * short).sum()
    squares = parts.add("squares", pl.when(short_enough & small_enough).then(exact))

    freedom = 0 if function == "population_std_dev" else 1
    spare = parts.add("n", count) - freedom
    spare = pl.when(spare > 0).then(spare)
    if function == "variance" and declared is not None and declared.type == "Decimal":
        places = _places(declared)
        return pl.coalesce(_decimal_quotient(squares, spare, places), _decimal_of(floats / spare, places))
    variance = pl.coalesce(_float_quotient(squares, spare), floats / spare)
    return variance if function == "variance" else variance.sqrt()


# ------------------------------------------------------------------
# Building blocks
# ------------------------------------------------------------------

def _unless_missing(value: pl.Expr, column: pl.Expr, parts: _Parts, ignore_null: bool) -> pl.Expr:
    """The value, or nothing when missing values count and the group holds one."""
    if ignore_null:
        return value
    return pl.when(parts.add("nulls", column.null_count()) == 0).then(value)


def _float_of(decimal: pl.Expr) -> pl.Expr:
    """The float nearest to a Decimal. Polars' own cast can be one step off; reading the digits is not."""
    return decimal.cast(pl.String).cast(pl.Float64)


def _decimal_of(number: pl.Expr, places: int = _EXACT.scale) -> pl.Expr:
    """The Decimal a float prints as, missing when it has 20 digits or more before the point."""
    return number.cast(pl.String).cast(pl.Decimal(38, places), strict=False)


def _decimal_of_float(column: pl.Expr) -> pl.Expr:
    """A float that takes part in exact arithmetic: the Decimal it prints as, missing from a quadrillion up."""
    return _decimal_of(pl.when(column.abs() < _EXACT_LIMIT).then(column))


def _places(declared: Column) -> int:
    """The places a quotient is kept to in a column declared Decimal."""
    return max(_EXACT.scale, declared.precision or 0)


def _float_quotient(total: pl.Expr, count: pl.Expr) -> pl.Expr:
    """A Decimal total divided by a whole number, as the float nearest to the quotient."""
    tried = [total.cast(pl.Decimal(38, places), strict=False) / count for places in _QUOTIENT_PLACES]
    return pl.coalesce([_float_of(quotient) for quotient in tried])


def _decimal_quotient(total: pl.Expr, count: pl.Expr, places: int) -> pl.Expr:
    """A Decimal total divided by a whole number, as a Decimal of so many places."""
    held = pl.Decimal(38, places)
    tried = [
        total.cast(pl.Decimal(38, fewer), strict=False) / count
        for fewer in (places,) + tuple(fewer for fewer in _QUOTIENT_PLACES if fewer < places)
    ]
    return pl.coalesce([quotient.cast(held, strict=False) for quotient in tried])


def _as_float(column: pl.Expr, dtype: pl.DataType) -> pl.Expr:
    if dtype.is_float():
        return column
    return _float_of(column) if dtype.is_decimal() else column.cast(pl.Float64)


def _as_text(column: pl.Expr, dtype: pl.DataType) -> pl.Expr:
    """A value as it stands in a list: as a file output writes it, a date with no more of its time than it has.

    Midnight is written as the day alone and whole milliseconds with three
    digits, which is what v1 writes for a group whose dates are all alike.
    """
    if dtype == pl.String:
        return column
    text = to_text(column, dtype)
    if not isinstance(dtype, pl.Datetime):
        return text
    thousandths = (column.dt.microsecond() % 1000 == 0) & (column.dt.microsecond() != 0)
    return (
        pl.when(column == column.dt.truncate("1d")).then(column.dt.strftime("%Y-%m-%d"))
        .when(thousandths).then(column.dt.strftime("%Y-%m-%d %H:%M:%S%.3f"))
        .otherwise(text)
    )
