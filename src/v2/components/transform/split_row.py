"""Split row: one row becomes several, each made from the row's own columns."""
from __future__ import annotations

import re
from typing import Any, Dict, List

import polars as pl

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
    """

    names = ("split_row", "SplitRow", "tSplitRow")
    keys = (
        Key("col_mapping", type=list, required=True, convert=_groups,
            doc="The groups: each a mapping of output column to a column of the input, a quoted text or a number."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        names = frame.collect_schema().names()
        groups = self.config["col_mapping"]
        if not groups:
            return {"main": frame.clear().select(hidden(names))}
        numbered = frame.with_row_index(_PLACE)
        carried = hidden(names)
        made = [
            numbered.select(
                [self._held(written, names).alias(name) for name, written in group.items()]
                + [pl.col(_PLACE), pl.lit(index, dtype=pl.Int32).alias(_GROUP)] + [pl.col(name) for name in carried]
            )
            for index, group in enumerate(groups)
        ]
        together = pl.concat(made, how="diagonal_relaxed").sort(_PLACE, _GROUP, maintain_order=True)
        return {"main": together.drop(_PLACE, _GROUP)}

    @staticmethod
    def _held(written: str, names: List[str]) -> pl.Expr:
        """What a group writes for a column, as v1 reads it."""
        column = _COLUMN.match(written)
        if column and column.group(1) in names:
            return pl.col(column.group(1))
        if len(written) >= 2 and written[0] == written[-1] and written[0] in "\"'":
            return pl.lit(written[1:-1])
        for number in (int, float):
            try:
                return pl.lit(number(written))
            except ValueError:
                pass
        return pl.lit(written)
