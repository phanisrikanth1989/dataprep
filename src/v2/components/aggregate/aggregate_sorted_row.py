"""Aggregate sorted row: an aggregate for rows that arrive sorted by their group columns."""
from __future__ import annotations

from typing import List, Tuple

import polars as pl

from ...job.keys import Key, Kind
from ..registry import REGISTRY
from .aggregate_row import AggregateRow

_RUN = "__sorted_run"


@REGISTRY.register
class AggregateSortedRow(AggregateRow):
    """Compute one value per group, for rows that arrive sorted by their group columns.

    Everything is as in the aggregate row, but for what a group is: a run
    of rows, one after another, that agree in the group columns. That is
    how Talend's component works, comparing each row with the one before
    it. On sorted rows it is the same as grouping the whole input, which is
    what v1 does; on rows that are not sorted, a group value that comes
    back later starts a new group, where v1 writes it once.
    """

    names = ("aggregate_sorted_row", "AggregateSortedRow", "tAggregateSortedRow")
    keys = AggregateRow.keys + (
        Key("row_count", kind=Kind.IGNORED, type=object,
            doc="Talend's count of the rows to expect; v1 does not read it and v2 needs none."),
    )

    def problems(self) -> List[str]:
        found = super().problems()
        if not self.config["operations"] and not found:
            found.append("operations: an aggregate of sorted rows needs at least one, as in v1")
        return found

    def _grouped_by(self, frame: pl.LazyFrame, keys: List[str]) -> Tuple[pl.LazyFrame, List[str]]:
        """A run of rows that agree in the group columns is a group; the run's number keeps runs apart."""
        return frame.with_columns(pl.struct(keys).rle_id().alias(_RUN)), [_RUN] + keys
