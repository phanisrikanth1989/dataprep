"""Unite: the rows of several inputs, one input after another."""
from __future__ import annotations

from typing import Dict, List, Set

import polars as pl

from ...types import to_text
from ..base import Transform
from ..registry import REGISTRY


@REGISTRY.register
class Unite(Transform):
    """Put the rows of every input one after another.

    Inputs come in the order of the component's own ``inputs`` list, and no
    row is dropped or reordered. Columns are matched by name, not by
    position: the output has every column of every input, first those of the
    first input, and a row has no value in a column its input does not have.

    Where inputs disagree on the type of a column, whole numbers and floats
    are united as floats, and dates and date-times as date-times. Any other
    two types are united as text, each value written as a file output with
    no schema writes it; the declared output schema then says what the text
    is read as.
    """

    names = ("unite", "Unite", "tUnite")
    max_inputs = None

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        frames = list(inputs.values())
        if len(frames) == 1:
            return {"main": frames[0]}
        schemas = [frame.collect_schema() for frame in frames]
        as_text = _united_as_text(schemas)
        declared = {column.name: column for column in self.schema}
        prepared: List[pl.LazyFrame] = []
        for frame, types in zip(frames, schemas):
            texts = [
                # A Decimal keeps every digit here: the declared places are applied after, rounding half up.
                to_text(pl.col(name), dtype, None if dtype.is_decimal() else declared.get(name)).alias(name)
                for name, dtype in types.items()
                if name in as_text and dtype != pl.String
            ]
            prepared.append(frame.with_columns(texts) if texts else frame)
        return {"main": pl.concat(prepared, how="diagonal_relaxed")}


def _united_as_text(schemas: List[pl.Schema]) -> Set[str]:
    """The columns whose types across the inputs have nothing in common but their text."""
    found: Dict[str, List[pl.DataType]] = {}
    for types in schemas:
        for name, dtype in types.items():
            if dtype != pl.Null:
                found.setdefault(name, []).append(dtype)
    return {name for name, dtypes in found.items() if not _one_kind(dtypes)}


def _one_kind(dtypes: List[pl.DataType]) -> bool:
    """Whether v1 holds columns of these types as one type once it has put them together.

    It does so for whole numbers with floats. Every other mix it keeps value
    by value, a Decimal beside a whole number included.
    """
    if all(dtype == dtypes[0] for dtype in dtypes):
        return True
    if all(dtype.is_integer() or dtype.is_float() for dtype in dtypes):
        return True
    return all(isinstance(dtype, (pl.Date, pl.Datetime)) for dtype in dtypes)
