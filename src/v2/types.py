"""Column types: from a declared schema to Polars."""
from __future__ import annotations

from typing import Dict, Iterable

import polars as pl

from .job.model import Column

_POLARS_TYPES = {
    "str": pl.String,
    "int": pl.Int64,
    "float": pl.Float64,
    "bool": pl.Boolean,
    "datetime": pl.Datetime("us"),
    "date": pl.Date,
}


def polars_type(column: Column) -> pl.DataType:
    """The Polars type a declared column is held as."""
    if column.type == "Decimal":
        return pl.Decimal(38, column.precision or 0)
    return _POLARS_TYPES[column.type]


def polars_schema(columns: Iterable[Column]) -> Dict[str, pl.DataType]:
    """A declared schema as Polars reads it: column name to type, in order."""
    return {column.name: polars_type(column) for column in columns}
