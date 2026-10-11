"""Replicate: hand the same rows to every flow that leaves."""
from __future__ import annotations

from typing import Dict

import polars as pl

from ...job.keys import Key, Kind
from ..base import Transform
from ..registry import REGISTRY


@REGISTRY.register
class Replicate(Transform):
    """Hand every row, unchanged, to each flow that leaves the component.

    The rows are read once however many flows take them: the engine runs
    the whole subjob in one pass.
    """

    names = ("replicate", "Replicate", "tReplicate")
    keys = (
        Key("output_count", kind=Kind.IGNORED, type=object,
            doc="v1's count of copies; the flows that leave decide how many there are."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        return {"main": frame}
