"""Map joins: one lookup joined to the rows gathered so far.

Every lookup is a left join that keeps the order of the main rows. A key that
is missing on either side never matches. An inner join drops nothing either:
it marks the main rows that found no match, so that the outputs can tell them
apart and the reject outputs can take them.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ...errors import ConfigurationError

# Working column: whether an inner join found no match for the row. Outputs read it.
MISSED = "__map_missed"
# Working columns used while one lookup is joined: the key values, and a mark on every lookup row.
_KEY = "__map_key_"
_FOUND = "__map_found"


def joined_with(
    joined: pl.LazyFrame,
    lookup: pl.LazyFrame,
    settings: Dict[str, Any],
    keys: List[Tuple[pl.Expr, pl.DataType]],
    missed: bool,
    auto_convert: bool,
    where: str,
) -> pl.LazyFrame:
    """Join one lookup to the rows gathered so far.

    The lookup's columns arrive named ``<lookup>.<column>`` and are missing
    on the rows that found no match. After an inner join the MISSED column
    says which rows those are. A row an earlier inner join missed is matched
    with nothing more.

    Args:
        joined: The main rows with the lookups joined before this one.
        lookup: The lookup's rows, already filtered.
        settings: The lookup's config.
        keys: The value of each join key on the main side and its type, in
            the order of the lookup's ``join_keys``.
        missed: Whether ``joined`` holds the MISSED column already.
        auto_convert: Whether a key that is text on one side and a number on
            the other is compared as numbers.
        where: The lookup's place in the config, for messages.
    """
    name = settings["name"]
    types = lookup.collect_schema()
    columns = [key["lookup_column"] for key in settings["join_keys"]]
    left: List[pl.Expr] = []
    right: List[pl.Expr] = []
    for index, ((value, dtype), column) in enumerate(zip(keys, columns)):
        place = f"{where}.join_keys[{index}]"
        if column not in types:
            raise ConfigurationError(
                f"{place}.lookup_column: {name} has no column '{column}'; it has: {', '.join(types.names())}"
            )
        common = _common_type(dtype, types[column], auto_convert)
        if common is None:
            raise ConfigurationError(
                f"{place}: the key is {_kind(dtype)} on the main side and {_kind(types[column])} in "
                f"{name}.{column}; convert one side in the expression" + _auto_convert_hint(dtype, types[column])
            )
        left.append(_as_key(value, dtype, common))
        right.append(_as_key(pl.col(column), types[column], common))

    several = not columns or settings["matching_mode"] == "ALL_MATCHES"
    if not columns:
        # Without keys every lookup row goes with every main row: a join on a constant.
        left, right = [pl.lit(0, dtype=pl.Int8)], [pl.lit(0, dtype=pl.Int8)]
    if missed:
        left = [pl.when(~pl.col(MISSED)).then(key) for key in left]
    inner = settings["join_mode"] == "INNER_JOIN"
    names = [f"{_KEY}{index}" for index in range(len(left))]
    matches = lookup.select(
        [pl.col(column).alias(f"{name}.{column}") for column in types.names()]
        + [key.alias(alias) for key, alias in zip(right, names)]
        + ([pl.lit(True).alias(_FOUND)] if inner else [])
    )
    if not several:
        # Duplicates are judged on the keys as they are compared, so a main row gets one lookup row at most.
        keep = "first" if settings["matching_mode"] == "FIRST_MATCH" else "last"
        matches = matches.unique(subset=names, keep=keep, maintain_order=True)
    result = (
        joined.with_columns([key.alias(alias) for key, alias in zip(left, names)])
        .join(matches, on=names, how="left", maintain_order="left_right" if several else "left")
        .drop(names)
    )
    if inner:
        unmatched = pl.col(_FOUND).is_null()
        result = result.with_columns((pl.col(MISSED) | unmatched if missed else unmatched).alias(MISSED)).drop(_FOUND)
    return result


def _common_type(left: pl.DataType, right: pl.DataType, auto_convert: bool) -> Optional[pl.DataType]:
    """The type both sides of a key are compared as, or None when they cannot be compared."""
    if left == right or left == pl.Null:
        return right
    if left.is_numeric() and right.is_numeric():
        if left.is_float() or right.is_float():
            return pl.Float64
        if left.is_decimal() or right.is_decimal():
            return pl.Decimal(38, max(dtype.scale for dtype in (left, right) if dtype.is_decimal()))
        return pl.Int64
    if _is_date(left) and _is_date(right):
        return pl.Datetime("us")
    if auto_convert and _text_and_number(left, right):
        return pl.Float64
    return None


def _kind(dtype: pl.DataType) -> str:
    """A type in the words of a message."""
    if dtype == pl.String:
        return "text"
    if dtype == pl.Boolean:
        return "true or false"
    if dtype.is_numeric():
        return "a number"
    return "a date" if _is_date(dtype) else str(dtype)


def _is_date(dtype: pl.DataType) -> bool:
    return dtype == pl.Date or isinstance(dtype, pl.Datetime)


def _text_and_number(left: pl.DataType, right: pl.DataType) -> bool:
    return (left == pl.String and right.is_numeric()) or (right == pl.String and left.is_numeric())


def _auto_convert_hint(left: pl.DataType, right: pl.DataType) -> str:
    if _text_and_number(left, right):
        return ", or set enable_auto_convert_type to compare them as numbers"
    return ""


def _as_key(value: pl.Expr, dtype: pl.DataType, common: pl.DataType) -> pl.Expr:
    """A key value as the type it is compared as; what does not fit is missing and matches nothing."""
    if dtype != common:
        if dtype == pl.String:
            value = value.str.strip_chars()
        value = value.cast(common, strict=False)
    return value.fill_nan(None) if common.is_float() else value
