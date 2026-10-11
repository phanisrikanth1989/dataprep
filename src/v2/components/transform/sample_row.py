"""Sample row: pick rows by their place in the flow."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import polars as pl

from ...job.keys import Key
from ..base import Transform
from ..registry import REGISTRY

_PLACE = "__sample_place"


def _ranges(value: Any) -> List[Tuple[int, int]]:
    """A range as written (``1,5,10..20``) as the first and last place of each part.

    A number is whatever Python's ``int()`` reads as one, as in v1. A range
    of nothing but commas names no row and picks none, as in v1.
    """
    if not isinstance(value, str):
        raise ValueError(f"a range is text such as 1,5,10..20; {value!r} is not")
    if not value.strip():
        raise ValueError("names no row")
    found: List[Tuple[int, int]] = []
    for part in (piece.strip() for piece in value.split(",")):
        if not part:
            continue
        ends = part.split("..")
        try:
            if len(ends) > 2:
                raise ValueError
            first, last = int(ends[0]), int(ends[-1])
        except ValueError:
            raise ValueError(f"'{part}' is not a row's place: write a number, or first..last") from None
        if first > last:
            raise ValueError(f"{part} runs backwards")
        if first < 1:
            raise ValueError(f"'{part}': rows are counted from 1")
        found.append((first, last))
    return found


@REGISTRY.register
class SampleRow(Transform):
    """Hand on the rows at the places named, and the others by the reject output.

    Places are counted from 1, among the rows that arrive: in a run for a
    few picked rows of a reader (`run.only`), among those rows. A place
    past the last row picks nothing. Both outputs keep the rows in the
    order they arrive.
    """

    names = ("sample_row", "SampleRow", "tSampleRow")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    keys = (
        Key("range", type=object, required=True, convert=_ranges,
            doc="The places to pick: numbers and first..last ranges, separated by commas (`1,5,10..20`)."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a missing value in a column the schema declares not nullable fails the job; "
                "when off, the row is dropped."),
    )

    def problems(self) -> List[str]:
        # A range written as null reaches here as none at all.
        return [] if self.config["range"] is not None else ["range: a range is needed, such as 1,5,10..20"]

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        place = pl.col(_PLACE)
        ranges = self.config["range"]
        picked = pl.any_horizontal([place.is_between(first, last) for first, last in ranges]) if ranges else pl.lit(False)
        numbered = frame.with_row_index(_PLACE, offset=1)
        return {
            "main": numbered.filter(picked).drop(_PLACE),
            "reject": numbered.filter(~picked).drop(_PLACE),
        }
