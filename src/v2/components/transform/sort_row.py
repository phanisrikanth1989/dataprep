"""Sort row: order rows by one or more columns."""
from __future__ import annotations

from typing import Dict, Tuple

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ...job.model import Column
from ...types import from_text
from ..base import Transform
from ..registry import REGISTRY

# What v1 skips around a number written as text.
_NUMBER_BLANKS = " \t\n\r\x0b\x0c"

_CRITERION = (
    Key("column", required=True, aliases=("name",), doc="The column to sort by."),
    Key("sort_type", default="alpha", choices=("alpha", "num", "date"),
        doc="How a text column is compared: as text (alpha), read as numbers (num) or read as dates (date). "
            "A column of any other type is always compared by its own values."),
    Key("order", default="asc", choices=("asc", "desc"), doc="Ascending or descending."),
)


def _some(value: list) -> list:
    if not value:
        raise ValueError("at least one column to sort by is needed")
    return value


@REGISTRY.register
class SortRow(Transform):
    """Order rows by one or more columns.

    The sort is stable: rows that compare equal keep their input order.
    Text is compared character by character, capitals before small letters.
    Missing values come last whichever way the column is ordered, and so
    does text that cannot be read as the number or the date asked for. One
    case differs, as in v1: in a date column sorted as ``num`` a missing
    date is the smallest value.
    """

    names = ("sort_row", "SortRow", "tSortRow")
    keys = (
        Key("criteria", type=list, required=True, aliases=("columns",), items=_CRITERION, convert=_some,
            doc="The columns to sort by, most significant first."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a missing value in a column the schema declares not nullable fails the job; "
                "when off, the row is dropped."),
        Key("external", kind=Kind.IGNORED, type=object, doc="Talend's sort-on-disk switch; Polars decides."),
        Key("tempfile", kind=Kind.IGNORED, type=object, doc="Talend's sort-on-disk folder."),
        Key("createdir", kind=Kind.IGNORED, type=object, doc="Talend's sort-on-disk folder flag."),
        Key("external_sort_buffersize", kind=Kind.IGNORED, type=object, doc="Talend's sort-on-disk buffer."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        types = frame.collect_schema()
        criteria = self.config["criteria"]
        # As in v1, a column listed twice is read by the sort type it is given last.
        sort_types = {criterion["column"]: criterion["sort_type"] for criterion in criteria}
        keys, descending, nulls_last = [], [], []
        for index, criterion in enumerate(criteria):
            name = criterion["column"]
            if name not in types:
                raise ConfigurationError(f"criteria[{index}]: there is no column '{name}' to sort by")
            try:
                key, missing_is_smallest = _sort_key(name, types[name], sort_types[name])
            except ValueError as exc:
                raise ConfigurationError(f"criteria[{index}]: column '{name}' {exc}") from None
            keys.append(key)
            descending.append(criterion["order"] == "desc")
            nulls_last.append(descending[-1] if missing_is_smallest else True)
        return {"main": frame.sort(keys, descending=descending, nulls_last=nulls_last, maintain_order=True)}


def _sort_key(name: str, dtype: pl.DataType, sort_type: str) -> Tuple[pl.Expr, bool]:
    """The value rows are ordered by for one criterion, and whether a missing one counts as the smallest.

    Raises:
        ValueError: When the column's type cannot be sorted that way; the
            message completes "column 'x' ...".
    """
    column = pl.col(name)
    if dtype.is_float():
        column = column.fill_nan(None)
    if sort_type == "num":
        if dtype == pl.String:
            return column.str.strip_chars(_NUMBER_BLANKS).cast(pl.Float64, strict=False).fill_nan(None), False
        if dtype.is_decimal():
            # v1 sorts the nearest number, which the text gives and the direct cast can miss by one step.
            return column.cast(pl.String).cast(pl.Float64), False
        # v1 sorts a date by its count of microseconds, among which a missing date is the smallest number.
        return column, dtype.is_temporal()
    if sort_type == "date":
        if dtype == pl.String:
            return from_text(column.fill_null(""), Column(name, "datetime"))[0], False
        if dtype.is_numeric() or dtype == pl.Boolean:
            kind = "a number" if dtype.is_numeric() else "a true/false value"
            raise ValueError(f"is {kind} and cannot be sorted as a date")
    return column, False
