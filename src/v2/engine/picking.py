"""A run for a few picked rows of one reader (``run.only``): what may be asked, and which rows it comes to.

Rows are picked by the value a column holds, read as the column's type, or
by their place as a failure names it. The reader that is named then hands
on those rows and no others; the rest of the job runs as in any run.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Sequence

import polars as pl

from ..components.base import Source
from ..job.model import Column, ComponentSpec, Job, Only
from ..job.refusal import Refusal
from ..rows import shown
from ..types import from_text, polars_type

if TYPE_CHECKING:
    from ..components.base import Component

# The most rows a run can be picked for: what a person can still look at, component by component.
MOST = 5
# A place on the command line, and the kind of place it is in a `run.only` block.
PLACE_WORDS = {"line": "lines", "record": "records", "row": "rows"}


def as_written(value: Any) -> str:
    """A value a row is picked by, as the text a file would hold for it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def wanted_values(column: Column, values: Sequence[Any]) -> pl.Series:
    """The values rows are picked by, read as their column's type the way the column's own values are read.

    Raises:
        ValueError: When a value cannot be read as the column's type.
    """
    texts = pl.DataFrame({"v": [as_written(value) for value in values]}, schema={"v": pl.String})
    if column.type == "str":
        return texts["v"]
    value, wrong = from_text(pl.col("v"), column)
    read = texts.select(value.alias("v"), (wrong | value.is_null()).alias("wrong"))
    for given, unreadable in zip(values, read["wrong"]):
        if unreadable:
            raise ValueError(f"column '{column.name}' is {column.type}; '{shown(as_written(given))}' cannot be read as that")
    return read["v"]


def holds(frame: pl.LazyFrame, schema: Sequence[Column], where: Mapping[str, Sequence[Any]]) -> pl.Expr:
    """True for a row of a source's output that holds, in every column named, one of the values wanted of it.

    A reject output holds its columns as text; there the text is read as the
    column's type first, so that a row the source turns away is found too.
    """
    types = frame.collect_schema()
    declared = {column.name: column for column in schema}
    conditions = []
    for name, values in where.items():
        column, held = declared[name], pl.col(name)
        if types[name] == pl.String and column.type != "str":
            held = from_text(held.fill_null(""), column)[0]
        elif types[name] != polars_type(column):
            held = held.cast(polars_type(column), strict=False)
        conditions.append(held.is_in(wanted_values(column, values).implode()))
    return pl.all_horizontal(conditions)


def in_words(where: Mapping[str, Sequence[Any]]) -> str:
    """What rows are picked by, for a message: ``id=3`` or ``id=1 and amount=20,30``."""
    return " and ".join(
        f"{name}={','.join(shown(as_written(value)) for value in values)}" for name, values in where.items()
    )


def check_only(job: Job, only: Only, instance: "Component") -> List[Refusal]:
    """What is wrong with the rows a run is asked to be for, found before anything runs.

    Args:
        job: The loaded job.
        only: What is asked.
        instance: The component named as the source, built with its config.
    """
    spec = job.components[only.source]
    names = [column.name for column in spec.schema]
    found: List[Refusal] = []
    if only.places is not None:
        kind, places = only.places
        if not isinstance(instance, Source) or kind != instance.place_kind:
            found.append(Refusal(
                "job", f"run.only.{kind}",
                f"'{only.source}' {instance.place_why}: pick its rows with `{instance.place_kind}`",
            ))
        elif len(places) > MOST:
            found.append(Refusal(
                "job", f"run.only.{kind}", f"{len(places)} rows are named; a run can be for {MOST} rows at most"
            ))
        return found
    for name, values in only.where.items():
        if name not in names:
            found.append(Refusal(
                "job", "run.only.where",
                f"'{only.source}' has no column '{name}'; its columns are: {', '.join(names) or 'none'}",
            ))
            continue
        try:
            wanted_values(next(column for column in spec.schema if column.name == name), values)
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
    columns) is said as the block itself, in JSON.

    Raises:
        ValueError: When the text is neither.
    """
    text = text.strip()
    if text.startswith("{"):
        try:
            block = json.loads(text)
        except ValueError as exc:
            raise ValueError(f"not JSON ({exc})") from None
        if not isinstance(block, dict):
            raise ValueError("expected an object")
        return block
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
