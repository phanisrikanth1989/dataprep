"""Where a row came from: the hidden columns that travel with it.

Every source numbers its rows as it reads them, from 1. The number stays
with the row through the job as a column the job never sees, so that a
failure the engine finds can say which row of which source it was: a line
of a file, a row of a sheet, a record of a document. Beside the number go
copies of the columns the source's schema marks as key.

The engine keeps these columns out of every file it writes and out of every
frame it hands to code it cannot see into. A component that picks the
columns it hands on picks these as well (see
``docs/v2/writing-a-component.md``).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, List, Mapping

import polars as pl

if TYPE_CHECKING:
    from .components.base import Source

# No column of a job's own may start this way.
HIDDEN = "__v2_"
# Followed by a source's id: the row's number in that source, from 1.
ROW = HIDDEN + "row:"
# Followed by a source's id, a colon and a column name: a copy of a key column of that source.
KEY = HIDDEN + "key:"
# Followed by a source's id: how many rows of that source were combined into this one.
ROWS = HIDDEN + "rows:"
# The most characters of a value that a message shows.
SHOWN = 100


def row_column(source_id: str) -> str:
    """The name of the column holding a source's row numbers."""
    return ROW + source_id


def key_column(source_id: str, column: str) -> str:
    """The name of the hidden copy of one key column of a source."""
    return f"{KEY}{source_id}:{column}"


def rows_column(source_id: str) -> str:
    """The name of the column holding how many rows of a source went into each row."""
    return ROWS + source_id


def hidden(names: Iterable[str]) -> List[str]:
    """The names among these that are hidden columns, in their order."""
    return [name for name in names if name.startswith(HIDDEN)]


def visible(names: Iterable[str]) -> List[str]:
    """The names among these that are a job's own columns, in their order."""
    return [name for name in names if not name.startswith(HIDDEN)]


def without(frame: pl.LazyFrame) -> pl.LazyFrame:
    """A frame without its hidden columns: what a file or foreign code may see."""
    held = hidden(frame.collect_schema().names())
    return frame.drop(held) if held else frame


def first_of(frame: pl.LazyFrame) -> List[pl.Expr]:
    """The hidden columns of a frame's first row, for a check that counts failing rows to ask for too."""
    return [pl.col(name).first().alias(name) for name in hidden(frame.collect_schema().names())]


def shown(value: Any) -> str:
    """A value as a message shows it: as text, and cut where it is long."""
    text = str(value)
    return text if len(text) <= SHOWN else text[:SHOWN] + "..."


def described(row: Mapping[str, Any], sources: Mapping[str, "Source"]) -> str:
    """The words that say where a row came from, to end a failure's message with.

    Args:
        row: Column name to value; only the hidden columns are read.
        sources: The sources of the subjob, by id.

    Returns:
        ``"; the row is line 7 of in.csv (id=42)"``, or nothing when the row
        carries no number of a known source.
    """
    places: List[str] = []
    for name, number in row.items():
        if not name.startswith(ROW) or number is None:
            continue
        source_id = name[len(ROW):]
        source = sources.get(source_id)
        if source is None:
            continue
        place = source.locate(int(number))
        combined = row.get(rows_column(source_id))
        if combined is not None and combined > 1:
            place += f", the first of {combined} rows that were combined"
        prefix = key_column(source_id, "")
        keys = [
            f"{column[len(prefix):]}={shown(value)}"
            for column, value in row.items() if column.startswith(prefix) and value is not None
        ]
        places.append(f"{place} ({', '.join(keys)})" if keys else place)
    return "; the row is " + " and ".join(places) if places else ""
