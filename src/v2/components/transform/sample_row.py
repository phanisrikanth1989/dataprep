"""Sample row: pick rows by their place in the flow."""
from __future__ import annotations

from typing import Dict, List, Tuple

import polars as pl

from ...job.keys import Key
from ..base import Transform
from ..registry import REGISTRY

_PLACE = "__sample_place"


def _ranges(value: str) -> List[Tuple[int, int]]:
    """A range as written (``1,5,10..20``) as the first and last place of each part."""
    found: List[Tuple[int, int]] = []
    for part in (piece.strip() for piece in value.split(",")):
        if not part:
            continue
        ends = [end.strip() for end in part.split("..")]
        if len(ends) > 2 or not all(end.isdigit() for end in ends):
            raise ValueError(f"'{part}' is not a row's place: write a number, or first..last")
        first, last = int(ends[0]), int(ends[-1])
        if first > last:
            raise ValueError(f"{part} runs backwards")
        if first < 1:
            raise ValueError(f"'{part}': rows are counted from 1")
        found.append((first, last))
    if not found:
        raise ValueError("names no row")
    return found


@REGISTRY.register
class SampleRow(Transform):
    """Hand on the rows at the places named, and the others by the reject output.

    Places are counted from 1. A place past the last row picks nothing.
    Both outputs keep the rows in the order they arrive.
    """

    names = ("sample_row", "SampleRow", "tSampleRow")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    keys = (
        Key("range", required=True, convert=_ranges,
            doc="The places to pick: numbers and first..last ranges, separated by commas (`1,5,10..20`)."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        place = pl.col(_PLACE)
        picked = pl.any_horizontal([place.is_between(first, last) for first, last in self.config["range"]])
        numbered = frame.with_row_index(_PLACE, offset=1)
        return {
            "main": numbered.filter(picked).drop(_PLACE),
            "reject": numbered.filter(~picked).drop(_PLACE),
        }
