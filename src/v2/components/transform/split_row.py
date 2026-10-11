"""Split row: one row becomes several, each made from the row's own columns."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Tuple

import polars as pl

from ...column_types import to_text
from ...job.keys import Key
from ...rows import hidden
from ..base import Transform
from ..registry import REGISTRY

_COLUMN = re.compile(r"^[A-Za-z_]\w*\.([A-Za-z_]\w*)$")
_PLACE, _GROUP = "__split_place", "__split_group"


def _groups(value: List[Any]) -> List[Dict[str, str]]:
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError(f"each group maps column names to what they hold; {entry!r} does not")
    return [{str(name): str(written) for name, written in entry.items()} for entry in value]


@REGISTRY.register
class SplitRow(Transform):
    """Make one row for each group of `col_mapping` out of every row that arrives.

    A group names the columns of the row it makes and says what each holds:
    a column of the input (`row1.amount`, after any flow name), text in
    quotes, or a number. Anything else is handed on as the text it is
    written as, as in v1. A column a group leaves out is missing in its
    rows. The rows of one input row stay together, in the order of the
    groups, and each carries the row number of the row it was made from.

    Where the groups give one column values of several kinds (a date in
    one, text in another), the column holds each as the text it is written
    as, which is what v1 writes; the engine then reads it as the type the
    output declares. Whole and fractional numbers together are floats.
    """

    names = ("split_row", "SplitRow", "tSplitRow")
    keys = (
        Key("col_mapping", type=list, required=True, convert=_groups,
            doc="The groups: each a mapping of output column to a column of the input, a quoted text or a number."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a missing value in a column the schema declares not nullable fails the job; "
                "when off, the row is dropped."),
    )

    def line_counts(
        self, inputs: Dict[str, pl.LazyFrame], outputs: Dict[str, pl.LazyFrame]
    ) -> Dict[str, List[pl.LazyFrame]]:
        """With no groups v1 counts no row at all, not even those that arrived."""
        if not self.config["col_mapping"]:
            return {"NB_LINE": [], "NB_LINE_OK": [], "NB_LINE_REJECT": []}
        return super().line_counts(inputs, outputs)

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        types = frame.collect_schema()
        names = types.names()
        groups = self.config["col_mapping"]
        if not groups:
            return {"main": frame.clear().select(hidden(names))}
        numbered = frame.with_row_index(_PLACE)
        carried = hidden(names)
        held = [{name: self._held(written, types) for name, written in group.items()} for group in groups]
        as_text = self._of_several_kinds(held)
        declared = {column.name: column for column in self.schema}
        made = []
        for index, group in enumerate(held):
            columns = []
            for name, (value, dtype) in group.items():
                if name in as_text:
                    # A date is written by the pattern of the column it goes to, so that it is read back as one.
                    to = declared.get(name) if dtype.is_temporal() and name in declared and \
                        declared[name].type in ("datetime", "date") else None
                    value = to_text(value, dtype, to)
                columns.append(value.alias(name))
            made.append(numbered.select(
                columns + [pl.col(_PLACE), pl.lit(index, dtype=pl.Int32).alias(_GROUP)] + [pl.col(name) for name in carried]
            ))
        together = pl.concat(made, how="diagonal_relaxed").sort(_PLACE, _GROUP, maintain_order=True)
        return {"main": together.drop(_PLACE, _GROUP)}

    @staticmethod
    def _of_several_kinds(held: List[Dict[str, Tuple[pl.Expr, pl.DataType]]]) -> List[str]:
        """The columns the groups give values of several kinds, numbers that differ only in size apart."""
        kinds: Dict[str, List[pl.DataType]] = {}
        for group in held:
            for name, (_, dtype) in group.items():
                kinds.setdefault(name, []).append(dtype)

        def plain_number(dtype: pl.DataType) -> bool:
            return dtype.is_integer() or dtype.is_float()

        return [name for name, found in kinds.items()
                if len(set(found)) > 1 and not all(plain_number(dtype) for dtype in found)]

    @staticmethod
    def _held(written: str, types: Mapping[str, pl.DataType]) -> Tuple[pl.Expr, pl.DataType]:
        """What a group writes for a column, as v1 reads it, and the kind of value it is."""
        column = _COLUMN.match(written)
        if column and column.group(1) in types:
            return pl.col(column.group(1)), types[column.group(1)]
        if len(written) >= 2 and written[0] == written[-1] and written[0] in "\"'":
            return pl.lit(written[1:-1]), pl.String()
        for number, dtype in ((int, pl.Int64()), (float, pl.Float64())):
            try:
                return pl.lit(number(written), dtype=dtype), dtype
            except ValueError:
                pass
        return pl.lit(written), pl.String()
