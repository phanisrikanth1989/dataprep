"""Replicate: hand the same rows to every flow that leaves."""
from __future__ import annotations

from typing import Dict

import polars as pl

from ...job.keys import Key
from ..base import Transform
from ..registry import REGISTRY


def _count(value: int) -> int:
    if not 1 <= value <= 10:
        raise ValueError(f"{value} is not from 1 to 10")
    return value


@REGISTRY.register
class Replicate(Transform):
    """Hand every row, unchanged, to each flow that leaves the component.

    The rows are read once however many flows take them: the engine runs
    the whole subjob in one pass.
    """

    names = ("replicate", "Replicate", "tReplicate")
    keys = (
        Key("output_count", type=int, default=2, convert=_count,
            doc="v1's count of copies, from 1 to 10. It is checked as v1 checks it and changes nothing: "
                "the flows that leave decide how many copies there are."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a missing value in a column the schema declares not nullable fails the job; "
                "when off, the row is dropped."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        return {"main": frame}
