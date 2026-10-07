"""Map outputs: which joined rows each output takes, and its columns, computed and typed.

The rows are shared out with flag columns on the one joined frame, so that
every output is a filter of the same plan and the inputs are read once.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import polars as pl

from ...errors import ExpressionError
from ...expressions import Scope, translate, translate_condition
from ...job.model import TYPE_NAMES, Column
from ...rows import hidden, shown
from ...types import conform, from_text, polars_type
from .map_joins import MISSED

# Working columns: whether an output takes the row, and whether no ordinary output took it.
_TAKEN = "__map_taken_"
_REJECTED = "__map_rejected"
# In the frame a check computes: how many rows hold text that cannot be read as its column's type.
_ROWS = "__map_rows"

Check = Callable[[pl.LazyFrame, Callable[[pl.DataFrame], Optional[str]]], None]
# Given a check's result, the words that name the row it found (``Component.where``).
Where = Callable[[pl.DataFrame], str]


def translated(text: str, scope: Scope, where: str, guard: Optional[pl.Expr] = None) -> pl.Expr:
    """Translate an expression; a refusal, and a conversion that fails in it, say which config key holds it.

    Args:
        text: The expression.
        scope: What it may refer to.
        where: The config key that holds it.
        guard: True for the rows the expression is worked out for at all; None for every row.
    """
    return _placed(translate, text, scope, where, guard)


def condition(text: str, scope: Scope, where: str, guard: Optional[pl.Expr] = None) -> pl.Expr:
    """A filter as a true-or-false value that is never missing, by Python's rules of truth."""
    return _placed(translate_condition, text, scope, where, guard)


def _placed(
    translator: Callable[[str, Scope], pl.Expr], text: str, scope: Scope, where: str, guard: Optional[pl.Expr]
) -> pl.Expr:
    noted = len(scope.failures)
    try:
        made = translator(text, scope)
    except ExpressionError as exc:
        raise ExpressionError(exc.expression, f"{where}: {exc.reason}") from None
    for failure in scope.failures[noted:]:
        failure.where = where
        if guard is not None:
            failure.failed = guard & failure.failed
    return made


def type_of(value: pl.Expr, scope: Scope) -> pl.DataType:
    """The type an expression has on the joined rows."""
    return pl.LazyFrame(schema=dict(scope.columns)).select(value.alias("_")).collect_schema()["_"]


def _own_filter(output: Dict[str, Any], scope: Scope, where: str, guard: Optional[pl.Expr]) -> Optional[pl.Expr]:
    """An output's filter; it is worked out only for the rows the output is offered (``guard``)."""
    text = output["filter"].strip()
    if not output["activate_filter"] or not text:
        return None
    return condition(text, scope, f"{where}.filter", guard)


def _both(first: Optional[pl.Expr], second: Optional[pl.Expr]) -> Optional[pl.Expr]:
    """Two conditions that must both hold; None stands for one that always does."""
    if first is None or second is None:
        return second if first is None else first
    return first & second


def routed(joined: pl.LazyFrame, outputs: List[Dict[str, Any]], scope: Scope, missed: bool) -> List[pl.LazyFrame]:
    """Share the joined rows out among the outputs.

    An ordinary output takes the rows that came through every inner join and
    meet its filter. An ``is_reject`` output takes the rows that came through
    and that no ordinary output took; its own filter is not read, as in v1.
    An ``inner_join_reject`` output takes the rows an inner join found no
    match for, if they meet its filter. An output that is both takes both.

    Args:
        joined: The joined rows, with the MISSED column when ``missed``.
        outputs: The outputs' configs.
        scope: What their filters may refer to.
        missed: Whether any lookup is an inner join.

    Returns:
        The rows of each output, in the order of ``outputs``.
    """
    came_through = ~pl.col(MISSED) if missed else None
    taken: Dict[int, Optional[pl.Expr]] = {}
    ordinary: List[int] = []
    for index, output in enumerate(outputs):
        if output["inner_join_reject"]:
            own = _own_filter(output, scope, f"outputs[{index}]", pl.col(MISSED) if missed else pl.lit(False))
            taken[index] = _both(pl.col(MISSED), own) if missed else pl.lit(False)
        elif not output["is_reject"]:
            taken[index] = _both(came_through, _own_filter(output, scope, f"outputs[{index}]", came_through))
            ordinary.append(index)

    flags = [which.alias(f"{_TAKEN}{index}") for index, which in taken.items() if which is not None]
    flagged = joined.with_columns(flags) if flags else joined

    if any(taken[index] is None for index in ordinary):
        rejected: Optional[pl.Expr] = pl.lit(False)
    elif ordinary:
        rejected = ~pl.any_horizontal([pl.col(f"{_TAKEN}{index}") for index in ordinary])
        rejected = _both(came_through, rejected)
    else:
        rejected = came_through
    if rejected is not None and any(output["is_reject"] for output in outputs):
        flagged = flagged.with_columns(rejected.alias(_REJECTED))

    rows: List[pl.LazyFrame] = []
    for index, output in enumerate(outputs):
        which: List[Optional[pl.Expr]] = []
        if index in taken:
            which.append(None if taken[index] is None else pl.col(f"{_TAKEN}{index}"))
        if output["is_reject"]:
            which.append(None if rejected is None else pl.col(_REJECTED))
        everything = any(part is None for part in which)
        rows.append(flagged if everything else flagged.filter(pl.any_horizontal(which)))
    return rows


def projected(
    rows: pl.LazyFrame, output: Dict[str, Any], scope: Scope, where: str, check: Optional[Check] = None,
    row_named: Optional[Where] = None, converted: Optional[Callable[[pl.LazyFrame, Scope], None]] = None,
) -> pl.LazyFrame:
    """One output's columns for the rows it takes, each fitted to its declared type.

    A value of another kind is turned into the declared type, and what does
    not fit goes missing. Text that cannot be read as the declared type is
    the one case reported: with ``check``, it fails the component.

    Args:
        rows: The joined rows the output takes.
        output: The output's config.
        scope: What its expressions may refer to.
        where: The output's place in the config, for messages.
        check: The component's ``check``, when unreadable text is fatal.
        row_named: The component's ``where``, to name the row in the message.
        converted: The component's ``check_conversions``: a conversion in a
            column's expression that fails on a row the output takes fails
            the component, whatever ``check`` says.
    """
    declared: List[Column] = []
    values: List[pl.Expr] = []
    unreadable: Dict[str, pl.Expr] = {}
    for index, column in enumerate(output["columns"]):
        made = Column(name=column["name"], type=TYPE_NAMES[column["type"]])
        text = column["expression"].strip()
        value = translated(text, scope, f"{where}.columns[{index}].expression") if text else pl.lit(None)
        dtype = type_of(value, scope)
        if dtype == pl.Null:
            value = pl.lit(None, dtype=polars_type(made))
        elif dtype == pl.String and made.type != "str":
            unreadable[made.name] = from_text(pl.col(made.name).fill_null(""), made)[1]
        declared.append(made)
        values.append(value.alias(made.name))
    if converted is not None:
        converted(rows, scope)
    # Added to the rows and then picked: an output made of constants alone still has a row for each of them.
    # The hidden columns of the main row go on with it.
    carried = hidden(rows.collect_schema().names())
    computed = rows.with_columns(values).select([column.name for column in declared] + carried)
    if check is not None and unreadable:
        kinds = {column.name: column.type for column in declared if column.name in unreadable}
        any_unreadable = pl.any_horizontal(list(unreadable.values()))
        # The first row that holds any such text gives the value shown and the row named: one and the same row.
        check(
            computed.select(
                any_unreadable.sum().alias(_ROWS),
                *[pl.when(flag).then(pl.col(name)).filter(any_unreadable).first().alias(name)
                  for name, flag in unreadable.items()],
                *[pl.col(name).filter(any_unreadable).first().alias(name) for name in carried],
            ),
            lambda found: _unreadable_problem(found, output["name"], kinds, row_named(found) if row_named else ""),
        )
    frame, _ = conform(computed, declared)
    return frame


def _unreadable_problem(found: pl.DataFrame, output: str, kinds: Dict[str, str], row: str = "") -> Optional[str]:
    """What to say when text could not be read as its column's type; None when all of it could."""
    rows = found[_ROWS].item()
    for name, kind in kinds.items():
        value = found[name].item()
        if rows and value is not None:
            count = "1 row of the output holds" if rows == 1 else f"{rows} rows of the output hold"
            return (
                f"output '{output}' column '{name}': '{shown(value)}' cannot be read as {kind} "
                f"({count} such a value){row}"
            )
    return None
