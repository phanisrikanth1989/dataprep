"""Denormalize: the rows that agree in every other column become one row."""
from __future__ import annotations

from typing import Dict

import polars as pl

from ...column_types import to_text
from ...errors import ConfigurationError
from ...job.keys import Key
from ...rows import combined, visible
from ..base import Transform
from ..registry import REGISTRY

_COLUMN = (
    Key("input_column", required=True, doc="The column whose values are put together."),
    Key("delimiter", default=";", doc="What is put between the values."),
    Key("merge", type=bool, default=False, doc="Whether a value that came before in the same group is left out."),
)


@REGISTRY.register
class Denormalize(Transform):
    """Put the values of the named columns together, for the rows that agree in every other column.

    Every column that is not named is a key. The rows of one key become one
    row, where its first row arrives; each named column holds the texts of
    its values, in the order they came, with its delimiter between them. A
    missing value is left out, or stands as nothing between two delimiters
    under `null_as_empty`. Rows that miss a key value are a group of their
    own, as in Talend and in v1.

    A row made of several carries the lowest row number among them.
    """

    names = ("denormalize", "Denormalize", "tDenormalize")
    keys = (
        Key("denormalize_columns", type=list, default=[], items=_COLUMN,
            doc="The columns to put together; without any, every row is handed on as it is."),
        Key("null_as_empty", type=bool, default=False,
            doc="Whether a missing value stands as nothing between two delimiters; off, it is left out."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a missing value in a column the schema declares not nullable fails the job; "
                "when off, the row is dropped."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        wanted = {entry["input_column"]: entry for entry in self.config["denormalize_columns"]}
        if not wanted:
            return {"main": frame}
        types = frame.collect_schema()
        names = visible(types.names())
        for name in wanted:
            if name not in names:
                raise ConfigurationError(f"denormalize_columns: there is no column '{name}' to put together")
        keys = [name for name in names if name not in wanted]
        if not keys:
            raise ConfigurationError("denormalize_columns: every column is named, so none is left to group the rows by")

        together = []
        for name, entry in wanted.items():
            text = to_text(pl.col(name), types[name])
            text = text.fill_null("") if self.config["null_as_empty"] else text.drop_nulls()
            if entry["merge"]:
                text = text.unique(maintain_order=True)
            together.append(text.str.join(entry["delimiter"]).alias(name))
        carried = combined(types.names())
        made = frame.group_by(keys, maintain_order=True).agg(together + carried)
        return {"main": made.select(keys + list(wanted) + [expr.meta.output_name() for expr in carried])}
