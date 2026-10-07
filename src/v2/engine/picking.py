"""A run for a few picked rows of one reader (``run.only``): what may be asked, and which rows it comes to.

Rows are picked by the value a column holds, read as the column's type, or
by their place as a failure names it. The reader that is named then hands
on those rows and no others; the rest of the job runs as in any run.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence

import polars as pl

from ..column_types import from_text
from ..components.base import Source
from ..job.model import Column, ComponentSpec, Job, Only
from ..job.refusal import Refusal
from ..rows import shown, visible

# The most rows a run can be picked for: what a person can still look at, component by component.
MOST = 5
# A place on the command line, and the kind of place it is in a `run.only` block.
PLACE_WORDS = {"line": "lines", "record": "records", "row": "rows"}


def columns_of(spec: ComponentSpec, reader: Optional[Source]) -> Optional[List[Column]]:
    """The columns a reader's rows can be picked by.

    They are the columns it declares. A reader that declares none hands on
    columns all the same (every line as ``line``, a document's values under
    their paths' names), as text, and is picked by those.

    Args:
        spec: The reader as the job has it.
        reader: The reader built with its config; None while its config
            waits for a value the job sets as it runs.

    Returns:
        The columns; None when the reader declares none and is not built
        yet, so that they are not known.
    """
    if spec.schema:
        return list(spec.schema)
    if reader is None:
        return None
    main = reader.declared_outputs().get("main")
    names = visible(main.collect_schema().names()) if main is not None else []
    return [Column(name=name) for name in names]


def as_written(value: Any) -> str:
    """A value a row is picked by, as the text a file would hold for it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def wanted_values(column: Column, values: Sequence[Any], reader: Optional[Source] = None) -> pl.Series:
    """The values rows are picked by, read as their column's type the way the column's own values are read.

    A value given as text is read as the reader reads the column's text in
    its file, so that what a failure shows of a row can be asked for as it
    is shown. A number or a true or false is the value itself.

    Args:
        column: The column.
        values: The values asked for.
        reader: The reader the rows are picked from, built with its config.

    Raises:
        ValueError: When a value cannot be read as the column's type.
    """
    texts = pl.DataFrame(
        {"v": [as_written(value) for value in values], "text": [isinstance(value, str) for value in values]},
        schema={"v": pl.String, "text": pl.Boolean},
    )
    if column.type == "str":
        return texts["v"]
    text = pl.col("v")
    if reader is not None:
        text = pl.when(pl.col("text")).then(reader.as_read(column, text)).otherwise(text)
    value, wrong = from_text(text, column)
    read = texts.select(value.alias("v"), (wrong | value.is_null()).alias("wrong"))
    for given, unreadable in zip(values, read["wrong"]):
        if unreadable:
            raise ValueError(f"column '{column.name}' is {column.type}; '{shown(as_written(given))}' cannot be read as that")
    return read["v"]


def holds(
    frame: pl.LazyFrame, columns: Sequence[Column], where: Mapping[str, Sequence[Any]], reader: Source
) -> pl.Expr:
    """True for a row of a reader's output that holds, in every column named, one of the values wanted of it.

    A reject output holds its columns as text; there the text is read as the
    column's type first, the way the reader reads it, so that a row the
    reader turns away is found too.

    Args:
        frame: The output.
        columns: The columns the reader's rows can be picked by.
        where: Column name to the values asked for.
        reader: The reader, built with its config.
    """
    types = frame.collect_schema()
    declared = {column.name: column for column in columns}
    conditions = []
    for name, values in where.items():
        column, held = declared[name], pl.col(name)
        if types[name] == pl.String and column.type != "str":
            held = from_text(reader.as_read(column, held.fill_null("")), column)[0]
        conditions.append(held.is_in(wanted_values(column, values, reader).implode()))
    return pl.all_horizontal(conditions)


def in_words(where: Mapping[str, Sequence[Any]]) -> str:
    """What rows are picked by, for a message: ``id=3`` or ``id=1 and amount=20,30``."""
    return " and ".join(
        f"{name}={','.join(shown(as_written(value)) for value in values)}" for name, values in where.items()
    )


def check_only(job: Job, only: Only, reader: Optional[Source] = None) -> List[Refusal]:
    """What is wrong with the rows a run is asked to be for.

    Asked before anything runs, and once more when the reader is built:
    what only the built reader can tell (its kind of place, the columns of
    a reader that declares none, a way of its own to read a number) waits
    for that when the reader's config waits for a value the job sets as it
    runs.

    Args:
        job: The loaded job.
        only: What is asked.
        reader: The component named as the source, built with its config;
            None when it cannot be built yet.
    """
    spec = job.components[only.source]
    found: List[Refusal] = []
    if only.places is not None:
        kind, places = only.places
        if reader is not None and kind != reader.place_kind:
            found.append(Refusal(
                "job", f"run.only.{kind}", f"'{only.source}' {reader.place_why}: pick its rows with `{reader.place_kind}`"
            ))
        elif len(places) > MOST:
            found.append(Refusal(
                "job", f"run.only.{kind}", f"{len(places)} rows are named; a run can be for {MOST} rows at most"
            ))
        return found
    columns = columns_of(spec, reader)
    if columns is None:
        return found
    # A reader that reads a column's text in a way of its own says how once it is built: its values wait.
    values_wait = reader is None and spec.cls.as_read is not Source.as_read
    for name, values in only.where.items():
        column = next((column for column in columns if column.name == name), None)
        if column is None:
            names = ", ".join(column.name for column in columns) or "none"
            found.append(Refusal("job", "run.only.where", f"'{only.source}' has no column '{name}'; its columns are: {names}"))
        elif not values_wait:
            try:
                wanted_values(column, values, reader)
            except ValueError as exc:
                found.append(Refusal("job", "run.only.where", str(exc)))
    return found


def source_problem(job: Job, only: Only) -> List[Refusal]:
    """A refusal when the component a run is to pick rows from is not a reader of the job."""
    readers = [component_id for component_id, spec in job.components.items() if _reads(spec)]
    listed = f"the job's readers are: {', '.join(readers) or 'none'}"
    spec = job.components.get(only.source)
    if spec is None:
        return [Refusal("job", "run.only.source", f"there is no component '{only.source}'; {listed}")]
    if not _reads(spec):
        return [Refusal("job", "run.only.source", f"'{only.source}' is not a reader; {listed}")]
    return []


def _reads(spec: ComponentSpec) -> bool:
    return isinstance(spec.cls, type) and issubclass(spec.cls, Source)


def only_from_text(text: str, job: Job) -> Dict[str, Any]:
    """A ``run.only`` block from what the command line says after ``--only``.

    The short form is ``READER:COLUMN=VALUE[,VALUE]`` for rows by the value
    a column holds, and ``READER:line=NUMBER[,NUMBER]`` (or ``record=``,
    ``row=``) for rows by their place. Anything it cannot say (a sheet, two
    columns, a value with a comma in it) is said as the block itself, in
    JSON.

    Raises:
        ValueError: When the text is neither.
    """
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except ValueError as exc:
            raise ValueError(f"not JSON ({exc})") from None
    source, colon, rest = text.partition(":")
    name, equals, values = rest.partition("=")
    if not colon or not equals or not source.strip() or not name.strip() or not values.strip():
        raise ValueError("expected READER:COLUMN=VALUE, READER:line=NUMBER, or a `run.only` block in JSON")
    source, name, listed = source.strip(), name.strip(), [value.strip() for value in values.split(",")]
    if name not in PLACE_WORDS:
        return {"source": source, "where": {name: listed}}
    spec = job.components.get(source)
    if spec is not None and name in [column.name for column in spec.schema]:
        raise ValueError(
            f"'{name}' is a column of '{source}' and a place as well; say which with a block in JSON: "
            f'{{"source": "{source}", "where": {{"{name}": ...}}}} or {{"source": "{source}", "{PLACE_WORDS[name]}": [...]}}'
        )
    try:
        return {"source": source, PLACE_WORDS[name]: [int(value) for value in listed]}
    except ValueError:
        raise ValueError(f"a {name} is a whole number, counted from 1") from None
