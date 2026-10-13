"""Join: look each row of the main input up in a second input, by key."""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key
from ...column_types import polars_type
from ...rows import hidden, without
from ..base import Transform
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_KEY, _VALUE, _HIT = "__join_key_", "__join_value_", "__join_hit"
# What v1 adds to the name of a lookup column whose name the main input uses too.
_HIDDEN = "_lookup"

_KEY_PAIR = (
    Key("input_column", required=True, doc="The key column of the main input."),
    Key("lookup_column", required=True, doc="The lookup column it has to equal."),
)
_LOOKUP_COLUMN = (
    Key("lookup_column", default="",
        doc="The lookup column to fetch; `<name>_lookup` for one whose name the main input uses too."),
    Key("output_column", default="", doc="The name it takes in the output; its own when empty."),
)


@REGISTRY.register
class Join(Transform):
    """Look each row of the main input up in the lookup input.

    The first input is the main one and the second the lookup, unless the two
    flows are named ``main`` and ``lookup``. A main row matches the first
    lookup row whose key columns equal its own, so the output never has more
    rows than the main input and keeps their order. Text is compared as it
    is, and an empty text is a value like any other; numbers are compared as
    numbers whatever their types. A key that is missing matches nothing.

    A left join keeps every main row, an inner join those with a match.
    Either way the rows with no match also leave by the reject output, with
    the main input's columns, or with those of the declared reject schema.
    """

    names = ("join", "Join", "tJoin")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    min_inputs = 2
    max_inputs = 2
    keys = (
        Key("join_key", type=list, required=True, items=_KEY_PAIR,
            doc="The pairs of columns a main row and a lookup row must agree on to match."),
        Key("use_inner_join", type=bool, default=False,
            doc="Whether main rows with no match are left out of the main output."),
        Key("use_lookup_cols", type=bool, default=False, doc="Whether `lookup_cols` are added to the main output."),
        Key("lookup_cols", type=list, default=[], items=_LOOKUP_COLUMN,
            doc="The lookup columns to add after the main input's, in this order. Each is fetched once."),
        Key("case_sensitive", type=bool, default=True, doc="Whether text keys must be in the same case to match."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a missing value in an output column that may hold none fails the job; "
                "when off the row leaves by reject."),
    )

    def problems(self) -> List[str]:
        if not self.config["join_key"]:
            return ["join_key: at least one pair of key columns is needed"]
        return []

    def line_counts(
        self, inputs: Dict[str, pl.LazyFrame], outputs: Dict[str, pl.LazyFrame]
    ) -> Dict[str, List[pl.LazyFrame]]:
        """v1's join counts the rows of its main input only."""
        counts = super().line_counts(inputs, outputs)
        counts["NB_LINE"] = [_sides(inputs)[0]]
        return counts

    def lookup_inputs(self, names: List[str]) -> List[str]:
        return ["lookup"] if set(names) == {"main", "lookup"} else names[1:]

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        main, lookup = _sides(inputs)
        # The row that goes on is the main input's: a lookup's own row numbers are left behind.
        lookup = without(lookup)
        main_types, lookup_types = main.collect_schema(), lookup.collect_schema()
        keys = self._keys(main_types, lookup_types)
        fetched = self._fetched(main_types, lookup_types)

        names = [f"{_KEY}{index}" for index in range(len(keys))]
        found = lookup.select(
            *[theirs.alias(name) for name, (_, theirs) in zip(names, keys)],
            *[pl.col(column).alias(f"{_VALUE}{index}") for index, (column, _) in enumerate(fetched)],
            pl.lit(True).alias(_HIT),
        ).unique(subset=names, keep="first", maintain_order=True)
        joined = main.with_columns([ours.alias(name) for name, (ours, _) in zip(names, keys)]).join(
            found, on=names, how="left", maintain_order="left"
        )

        matched = pl.col(_HIT).is_not_null()
        own = [pl.col(name) for name in main_types.names()]
        wide = own + [pl.col(f"{_VALUE}{index}").alias(name) for index, (_, name) in enumerate(fetched)]
        if self.config["use_inner_join"]:
            kept = joined.filter(matched).select(wide)
        else:
            kept = joined.select(wide) if fetched else main
        return {"main": kept, "reject": self._rejected(joined.filter(~matched).select(own))}

    def _keys(self, main_types: pl.Schema, lookup_types: pl.Schema) -> List[Tuple[pl.Expr, pl.Expr]]:
        """Each key pair as a main and a lookup expression that are equal exactly when the keys match."""
        any_case = not self.config["case_sensitive"]
        pairs = []
        for pair in self.config["join_key"]:
            ours, theirs = pair["input_column"], pair["lookup_column"]
            if ours not in main_types:
                raise ConfigurationError(f"join_key: there is no column '{ours}' in the main input")
            if theirs not in lookup_types:
                raise ConfigurationError(f"join_key: there is no column '{theirs}' in the lookup input")
            pairs.append(_comparable(ours, main_types[ours], theirs, lookup_types[theirs], any_case))
        return pairs

    def _fetched(self, main_types: pl.Schema, lookup_types: pl.Schema) -> List[Tuple[str, str]]:
        """The lookup columns to add, each with the name it takes in the output, in output order.

        A lookup column is asked for by the name v1 knows it by: its own, or
        ``<name>_lookup`` when the main input uses the name too. A lookup key
        named like its main key is the main column itself and is not fetched.
        An entry that asks for anything else, or for a column fetched
        already, adds nothing.
        """
        if not self.config["use_lookup_cols"]:
            return []
        pairs = self.config["join_key"]
        same_named = {pair["lookup_column"] for pair in pairs if pair["lookup_column"] == pair["input_column"]}
        theirs = [name for name in lookup_types.names() if name not in same_named]
        reachable = {name + _HIDDEN: name for name in theirs if name in main_types}
        reachable.update({name: name for name in theirs if name not in main_types})

        taken = list(main_types.names())
        fetched: List[Tuple[str, str]] = []
        for entry in self.config["lookup_cols"]:
            asked = entry["lookup_column"]
            if asked in taken or asked not in reachable:
                why = (
                    f"the main input's column of that name is kept; the lookup's is '{asked}{_HIDDEN}'"
                    if asked + _HIDDEN in reachable else "there is no such lookup column left to fetch"
                )
                logger.warning(f"[{self.id}] lookup_cols: nothing is fetched for '{asked}': {why}")
                continue
            name = entry["output_column"] or asked
            if name in taken:
                raise ConfigurationError(f"lookup_cols: the output already has a column '{name}'")
            fetched.append((reachable.pop(asked), name))
            taken.append(name)
        return fetched

    def _rejected(self, unmatched: pl.LazyFrame) -> pl.LazyFrame:
        """The reject output: the main rows with no match, as the declared reject schema wants them."""
        declared = self.spec.reject_schema
        if not declared:
            return unmatched
        named = [column.name for column in declared]
        reasons = {"errorCode": "JOIN_REJECT", "errorMessage": "No matching lookup row"}
        unmatched = unmatched.with_columns(
            [pl.lit(text).alias(name) for name, text in reasons.items() if name in named]
        )
        have = unmatched.collect_schema()
        absent = [
            pl.lit(None, dtype=polars_type(column)).alias(column.name) for column in declared if column.name not in have
        ]
        # The row's number goes on with it, as on every output.
        return unmatched.with_columns(absent).select(named + hidden(have.names()))


def _sides(inputs: Dict[str, pl.LazyFrame]) -> Tuple[pl.LazyFrame, pl.LazyFrame]:
    """The main and the lookup input."""
    if set(inputs) == {"main", "lookup"}:
        return inputs["main"], inputs["lookup"]
    main, lookup = inputs.values()
    return main, lookup


def _comparable(
    ours: str, our_type: pl.DataType, theirs: str, their_type: pl.DataType, any_case: bool
) -> Tuple[pl.Expr, pl.Expr]:
    """A main and a lookup key column as two expressions of one type, or the reason they cannot be."""
    left, right = pl.col(ours), pl.col(theirs)
    if our_type == pl.String and their_type == pl.String:
        return (left.str.to_lowercase(), right.str.to_lowercase()) if any_case else (left, right)
    if _is_number(our_type) and _is_number(their_type):
        shared = _shared_number(our_type, their_type)
        return _as_number(left, our_type, shared), _as_number(right, their_type, shared)
    if our_type == their_type:
        return left, right
    if _is_date(our_type) and _is_date(their_type):
        return left.cast(pl.Datetime("us"), strict=False), right.cast(pl.Datetime("us"), strict=False)
    raise ConfigurationError(
        f"join_key: '{ours}' of the main input ({_kind(our_type)}) and '{theirs}' of the lookup input "
        f"({_kind(their_type)}) cannot be compared"
    )


def _is_number(dtype: pl.DataType) -> bool:
    return dtype.is_numeric() or dtype == pl.Boolean


def _is_date(dtype: pl.DataType) -> bool:
    return isinstance(dtype, (pl.Date, pl.Datetime))


def _kind(dtype: pl.DataType) -> str:
    if dtype == pl.String:
        return "text"
    if _is_date(dtype):
        return "a date"
    return "a number" if dtype.is_numeric() else str(dtype)


def _shared_number(first: pl.DataType, second: pl.DataType) -> pl.DataType:
    """The type two number columns are compared as: v1 holds true equal to 1 and 10 equal to 10.0."""
    if first == second:
        return first
    if first.is_float() or second.is_float():
        return pl.Float64
    scales = [dtype.scale for dtype in (first, second) if dtype.is_decimal()]
    return pl.Decimal(38, max(scales)) if scales else pl.Int64


def _as_number(column: pl.Expr, dtype: pl.DataType, shared: pl.DataType) -> pl.Expr:
    if dtype != shared:
        if dtype == pl.Boolean and shared.is_decimal():
            column = column.cast(pl.Int64)
        if dtype.is_decimal() and shared.is_float():
            # Through its text: Polars' own cast can land one step from the float the digits read as.
            column = column.cast(pl.String)
        column = column.cast(shared, strict=False)
    return column.fill_nan(None) if shared.is_float() else column
