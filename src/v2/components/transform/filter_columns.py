"""Filter columns: keep the columns the output schema declares, drop the rest."""
from __future__ import annotations

from typing import Dict

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key
from ...rows import hidden
from ..base import Transform
from ..registry import REGISTRY


@REGISTRY.register
class FilterColumns(Transform):
    """Keep the columns the output schema declares; every row passes.

    The declared schema is the whole configuration: its columns leave in
    declared order, and one the input lacks is added by the engine, as for
    any component. With no declared columns every input column passes.
    """

    names = ("filter_columns", "FilterColumns", "tFilterColumns")
    keys = (
        Key("die_on_error", type=bool, default=True,
            doc="Whether a missing value in a column the schema declares not nullable fails the job; "
                "when off, the row is dropped."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        if not self.schema:
            return {"main": frame}
        have = frame.collect_schema()
        declared = [column.name for column in self.schema]
        kept = [name for name in declared if name in have]
        if not kept:
            raise ConfigurationError(
                f"schema: none of the declared columns ({', '.join(declared)}) is among the input's columns"
            )
        return {"main": frame.select(kept + hidden(have.names()))}
