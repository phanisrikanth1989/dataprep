"""Sort row: order rows by one or more columns."""
from __future__ import annotations

from typing import Dict

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ..base import Transform
from ..registry import REGISTRY

_CRITERION = (
    Key("column", required=True, aliases=("name",), doc="The column to sort by."),
    Key("sort_type", default="alpha", choices=("alpha", "num", "date"), doc="How values are compared."),
    Key("order", default="asc", choices=("asc", "desc"), doc="Ascending or descending."),
)


@REGISTRY.register
class SortRow(Transform):
    """Order rows by one or more columns.

    The sort is stable: rows that compare equal keep their input order.
    Missing values come last, whichever way the column is ordered.
    """

    names = ("sort_row", "SortRow", "tSortRow")
    keys = (
        Key("criteria", type=list, required=True, aliases=("columns",), items=_CRITERION,
            doc="The columns to sort by, most significant first."),
        Key("external", kind=Kind.IGNORED, type=object, doc="Talend's sort-on-disk switch; Polars decides."),
        Key("tempfile", kind=Kind.IGNORED, type=object, doc="Talend's sort-on-disk folder."),
        Key("createdir", kind=Kind.IGNORED, type=object, doc="Talend's sort-on-disk folder flag."),
        Key("external_sort_buffersize", kind=Kind.IGNORED, type=object, doc="Talend's sort-on-disk buffer."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        types = frame.collect_schema()
        if not self.config["criteria"]:
            raise ConfigurationError("criteria: at least one column to sort by is needed")
        keys, descending = [], []
        for criterion in self.config["criteria"]:
            name = criterion["column"]
            if name not in types:
                raise ConfigurationError(f"criteria: there is no column '{name}' to sort by")
            keys.append(_sort_key(name, types[name], criterion["sort_type"]))
            descending.append(criterion["order"] == "desc")
        return {"main": frame.sort(keys, descending=descending, nulls_last=True, maintain_order=True)}


def _sort_key(name: str, dtype: pl.DataType, sort_type: str) -> pl.Expr:
    """The value rows are ordered by, for one criterion."""
    column = pl.col(name)
    if sort_type == "num" and not dtype.is_numeric():
        column = column.cast(pl.String).str.strip_chars().cast(pl.Float64, strict=False)
        dtype = pl.Float64
    elif sort_type == "date" and dtype == pl.String:
        column = column.str.to_datetime(strict=False)
    if dtype.is_float():
        column = column.fill_nan(None)
    return column
