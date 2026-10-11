"""Extract positional fields: one column's text is cut at fixed widths and the pieces become columns."""
from __future__ import annotations

from typing import Any, List, Tuple

import polars as pl

from ...column_types import BLANKS
from ...job.keys import Key, Kind
from .extract_delimited_fields import ExtractFields, Fault
from ..registry import REGISTRY

_MARK = "\ufeff"
_WIDEST = 2 ** 31 - 1
_UNREAD = ("formats", "advanced_option", "advanced_separator", "thousands_separator", "decimal_separator")


def _widths(value: Any) -> List[int]:
    """The widths of a pattern: whole numbers separated by commas; an empty place between two commas is none."""
    found: List[int] = []
    for written in str(value).split(","):
        if not written.strip():
            continue
        rule = "give whole numbers, 1 or more, separated by commas"
        try:
            width = int(written.strip())
        except ValueError:
            raise ValueError(f"{written.strip()!r} is no width: {rule}") from None
        if width <= 0:
            raise ValueError(f"{width} is no width: {rule}")
        # A width beyond any text is the rest of the text.
        width = min(width, _WIDEST)
        found.append(width)
    if not found:
        raise ValueError("names no width")
    return found


@REGISTRY.register
class ExtractPositionalFields(ExtractFields):
    """Cut the text of the column `field` at the widths of `pattern`, and hand the pieces on as columns.

    The columns the output schema declares and the input does not bring
    take the pieces, the first column the first width. A piece beyond the
    end of the text is empty text; a column beyond the last width is
    missing, and widths beyond the last column are not read. The other
    output columns are handed on as they came. The pieces are text; the
    engine turns them into the types the output declares.

    A width counts characters. A byte order mark at the start of the text
    is no part of it. A source that is not text is cut as the text it is
    written as. With no `field` named, the first column is cut, as in v1.

    A row whose source is missing is left out without a word, or, with
    `ignore_source_null` off, leaves by the reject output (`NULL_SOURCE`).
    With `check_fields_num`, a row whose text is shorter than the widths
    that are read leaves by the reject output (`EXTRACTION_ERROR`), or
    fails the job under `die_on_error`.
    """

    names = ("extract_positional_fields", "ExtractPositionalFields", "tExtractPositionalFields")
    first_when_unnamed = True
    keys = (
        Key("field", default="", doc="The column whose text is cut; the first column when none is named."),
        Key("pattern", type=object, required=True, convert=_widths, doc="The widths, in characters, separated by commas."),
        Key("ignore_source_null", type=bool, default=True,
            doc="Whether a row whose source is missing is left out; when off, it leaves by the reject output."),
        Key("trim", type=bool, default=False, doc="Whether blanks around each piece are dropped."),
        Key("check_fields_num", type=bool, default=False,
            doc="Whether a row is turned away when its text is shorter than the widths that are read."),
        Key("die_on_error", type=bool, default=False,
            doc="Whether a text that is too short (under `check_fields_num`), or a missing value in a column the "
                "schema declares not nullable, fails the job; when off, the row leaves by the reject output."),
    ) + tuple(Key(name, kind=Kind.IGNORED, type=object, doc="Never read by v1.") for name in _UNREAD)

    def problems(self) -> List[str]:
        if self.config["pattern"] is None:
            return ["pattern: names no width"]
        return super().problems()

    def filled(self, names: List[str]) -> List[str]:
        if self.schema:
            return super().filled(names)
        # As in v1: with no output declared, a column for every width, named by its place.
        return names + [f"field_{at}" for at in range(1, len(self.config["pattern"]) + 1)]

    def pieces(self, text: pl.Expr, wanted: int) -> Tuple[pl.Expr, List[Fault]]:
        text = text.str.strip_prefix(_MARK)
        widths = self.config["pattern"][:wanted]
        cut, start = [], 0
        for width in widths:
            piece = text.str.slice(start, width)
            cut.append(piece.str.strip_chars(BLANKS) if self.config["trim"] else piece)
            start += width
        pieces = pl.concat_list(cut) if cut else pl.lit([], dtype=pl.List(pl.String))
        if not self.config["check_fields_num"]:
            return pieces, []
        length = text.str.len_chars()
        said = pl.format(f"Line length {{}} < required total width {start}", length)
        return pieces, [Fault(length < start, "EXTRACTION_ERROR", said, True)]
