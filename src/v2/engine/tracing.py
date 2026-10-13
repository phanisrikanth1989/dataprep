"""What every component did with the picked rows (``run.trace``): how rows get into the result and the log.

A traced flow is one whose every row comes from the picked rows. The engine
holds such a flow's rows in hand between two components, which is how it
can list them. The result holds every column of every such output; the log
says, for each picked row, what a component added or changed.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import polars as pl

from ..column_types import to_text
from ..job.model import Column
from ..rows import ROW, described, hidden, shown, visible

# The most rows of one output that a trace lists; the output's real count is always given.
ROWS_SHOWN = 50
# What is said of a component the trace does not list row by row.
NOT_PICKED = "its rows do not come from the picked rows"
# The most columns the log names for one row; the result holds them all.
NAMED = 12
_PLACE = len("; the row is ")
_MISSING = "(nothing)"
# The kinds of column a job config can declare, and a time of day: what a file output has a way to write.
_WRITTEN = ("str", "bool", "int", "float", "Decimal", "date", "datetime", "Time")


def type_name(dtype: pl.DataType) -> str:
    """A Polars type by the name a job config has for it."""
    if dtype == pl.String:
        return "str"
    if dtype == pl.Boolean:
        return "bool"
    if dtype.is_integer():
        return "int"
    if dtype.is_float():
        return "float"
    if dtype.is_decimal():
        return "Decimal"
    if dtype == pl.Date:
        return "date"
    if isinstance(dtype, pl.Datetime):
        return "datetime"
    return str(dtype)


def as_text(rows: pl.DataFrame, declared: Sequence[Column] = ()) -> pl.DataFrame:
    """The job's own columns of some rows as the text a file output would write for them.

    Args:
        rows: The rows.
        declared: The columns as the component that holds the rows declares
            them: a file output that declared the same would write a date
            by its pattern and a Decimal to its places.
    """
    types = rows.schema
    by_name = {column.name: column for column in declared}
    written: List[Any] = []
    for name in visible(rows.columns):
        dtype = types[name]
        if type_name(dtype) in _WRITTEN:
            written.append(to_text(pl.col(name), dtype, by_name.get(name)).alias(name))
        else:
            # A kind of column only code can make (a list, a duration, bytes): each value as Python prints it.
            values = [None if value is None else str(value) for value in rows[name].to_list()]
            written.append(pl.Series(name, values, dtype=pl.String))
    return rows.select(written)


def came_from(rows: pl.DataFrame, sources: Mapping[str, Any]) -> List[Optional[str]]:
    """For each row, where the picked row it came from is; None for a row that carries no number."""
    held = hidden(rows.columns)
    if not held:
        return [None] * rows.height
    return [(described(row, sources)[_PLACE:] or None) for row in rows.select(held).iter_rows(named=True)]


def captured(
    rows: pl.DataFrame,
    sources: Mapping[str, Any],
    declared: Sequence[Column] = (),
    file_text: Optional[Callable[[pl.DataFrame], pl.DataFrame]] = None,
) -> Dict[str, Any]:
    """An output's rows as a trace holds them: how many, the columns, the first rows as text, and where each came from.

    Args:
        rows: The rows, with the hidden columns they came with.
        sources: The run's sources, by id.
        declared: The columns as the component declares them.
        file_text: For a file output: gives rows as the text its file holds
            for each column (``Write.as_text``).
    """
    listed = rows.head(ROWS_SHOWN)
    types = rows.schema
    own = visible(rows.columns)
    text = file_text(listed.select(own)) if file_text is not None else as_text(listed, declared)
    return {
        "rows": rows.height,
        "columns": [{"name": name, "type": type_name(types[name])} for name in own],
        "data": [list(row) for row in text.iter_rows()],
        "from": came_from(listed, sources),
    }


def counted(rows: int) -> str:
    return "1 row" if rows == 1 else f"{rows} rows"


def changes(
    before: Optional[pl.DataFrame], after: pl.DataFrame, sources: Mapping[str, Any], declared: Sequence[Column] = ()
) -> List[str]:
    """What a component added to each picked row and what it changed in it, for the log.

    Rows are paired by the number they carry. Nothing is said where they
    cannot be: a row made of several, several made of one, or rows that
    carry no number. Both sides are written the way the component declares
    its columns, so that a value it left alone does not read as changed.
    """
    if before is None or not after.height or after.height > ROWS_SHOWN:
        return []
    key = next((name for name in after.columns if name.startswith(ROW) and name in before.columns), None)
    if key is None or after[key].n_unique() != after.height or before[key].n_unique() != before.height:
        return []
    was = {number: row for number, row in zip(before[key], as_text(before, declared).iter_rows(named=True))}
    places = came_from(after, sources)
    said: List[str] = []
    for number, row, place in zip(after[key], as_text(after, declared).iter_rows(named=True), places):
        old = was.get(number)
        if old is None:
            continue
        added = [f"{name}={_said(value)}" for name, value in row.items() if name not in old]
        changed = [f"{name}: {_said(old[name])} -> {_said(value)}" for name, value in row.items()
                   if name in old and old[name] != value]
        parts = (["added " + _some(added)] if added else []) + (["changed " + _some(changed)] if changed else [])
        if parts:
            said.append("; ".join(parts) if after.height == 1 else f"{place}: {'; '.join(parts)}")
    return said


def _some(items: List[str]) -> str:
    """The first of a list, and how many more there are."""
    more = len(items) - NAMED
    return ", ".join(items[:NAMED]) + (f" and {more} more" if more > 0 else "")


def _said(value: Optional[str]) -> str:
    return _MISSING if value is None else shown(value)
