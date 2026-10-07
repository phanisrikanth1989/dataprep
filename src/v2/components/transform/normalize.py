"""Normalize: one row whose cell holds several values becomes one row for each value."""
from __future__ import annotations

from typing import Dict

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ...types import BLANKS, to_text
from ..base import Transform
from ..registry import REGISTRY


def _separator(value: str) -> str:
    if value == "":
        raise ValueError("a separator of nothing cannot split a value")
    return value


@REGISTRY.register
class Normalize(Transform):
    """Split one column's values at a separator, and hand on one row for each piece.

    The other columns are repeated on every row a cell gives. A cell with
    nothing in it gives one row with an empty value. A cell that is not
    text is split as the text Python writes for it. The pieces are text;
    the engine turns them into the type the output declares for the column.

    In this order, as in v1: the empty pieces a cell ends on are discarded,
    each piece is trimmed, and a piece that came before in the same cell is
    left out. So a piece of blanks is kept by the first step and comes out
    empty after the second.

    Each row carries the row number of the row it was split from.
    """

    names = ("normalize", "Normalize", "tNormalize")
    keys = (
        Key("normalize_column", required=True, doc="The column whose values are split."),
        Key("item_separator", default=",", aliases=("itemseparator",), convert=_separator,
            doc="What separates the values in a cell, taken as it is written: no pattern."),
        Key("trim", type=bool, default=False, doc="Whether blanks around each piece are dropped."),
        Key("discard_trailing_empty_str", type=bool, default=False,
            doc="Whether the empty pieces a cell ends on are left out. A cell of nothing else gives no row."),
        Key("deduplicate", type=bool, default=False,
            doc="Whether a piece that came before in the same cell is left out."),
        Key("csv_option", kind=Kind.IGNORED, type=object, doc="Never read by v1: an enclosure does not keep a value whole."),
        Key("text_enclosure", kind=Kind.IGNORED, type=object, doc="Only read with `csv_option`."),
        Key("escape_char", kind=Kind.IGNORED, type=object, doc="Only read with `csv_option`."),
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="Nothing here can fail on a row."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        config = self.config
        column, separator = config["normalize_column"], config["item_separator"]
        types = frame.collect_schema()
        if column not in types:
            raise ConfigurationError(f"normalize_column: there is no column '{column}' to normalize")
        if types[column].is_temporal():
            raise ConfigurationError(
                f"normalize_column: '{column}' holds dates; v2 splits text and numbers, written as text"
            )

        frame = frame.with_columns(to_text(pl.col(column), types[column]).fill_null("").str.split(separator))
        pieces = pl.col(column)
        if config["discard_trailing_empty_str"]:
            # The pieces up to the last one that is not empty; a cell with no such piece has none left.
            filled = pieces.list.eval(pl.element() != "")
            kept = pl.when(filled.list.any()).then(pieces.list.len() - filled.list.reverse().list.arg_max())
            frame = frame.with_columns(pieces.list.head(kept.otherwise(0))).filter(pieces.list.len() > 0)
        if config["trim"]:
            # v1 trims with Python's str.strip().
            pieces = pieces.list.eval(pl.element().str.strip_chars(BLANKS))
        if config["deduplicate"]:
            pieces = pieces.list.unique(maintain_order=True)
        # No cell is without a piece by now; said outright, a list of none would give no row.
        return {"main": frame.with_columns(pieces.alias(column)).explode(column, empty_as_null=False)}
