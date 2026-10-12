"""Oracle row: one statement, run once, or once for each row of a flow."""
from __future__ import annotations

import datetime
import decimal
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

import polars as pl

from ... import oracle, statements
from ...column_types import polars_schema
from ...engine.references import parsed
from ...errors import ConfigurationError, DatabaseError
from ...job.keys import CODE, Key, Kind
from ...rows import HIDDEN, visible
from ..base import DIE_ON_ERROR, FAULTS, Action, Transform, one_line
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_COUNTERS = ("NB_LINE_INSERTED", "NB_LINE_UPDATED", "NB_LINE_DELETED")
# The place this component's work on a session is marked at.
_MARK = "v2_row"
# Rows a round trip, where the statement is run for each row of a flow.
_BATCH = 10_000
_TEXT = re.compile(r'"((?:[^"\\]|\\.)*)"')
_NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)")
# A statement whose doing cannot be told from the number of rows it says it changed: a block of PL/SQL, a call.
_BLOCK = re.compile(r"(?:\s+|--[^\n]*\n?|/\*.*?\*/)*(?:begin|declare|call)\b", re.IGNORECASE | re.DOTALL)


def _true(text: str) -> bool:
    if text.strip().lower() not in ("true", "false", "1", "0"):
        raise ValueError(text)
    return text.strip().lower() in ("true", "1")


def _moment(text: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(text.strip())


# What a value written as text becomes, by the type Talend names for its place.
_AS: Dict[str, Callable[[str], Any]] = {
    "String": str, "Object": str,
    "Int": int, "Integer": int, "Long": int, "Short": int, "Byte": int, "BigInteger": int,
    "Double": float, "Float": float, "BigDecimal": decimal.Decimal,
    "Boolean": _true, "Date": _moment, "Timestamp": _moment,
}
_NOT_BOUND = ("Blob", "Clob", "Bytes", "Time")

_PARAMETER = (
    Key("parameter_index", type=object, required=True, doc="Which mark it is for, from 1."),
    Key("parameter_type", default="String",
        doc="What the value is: `String`, `Int`, `Long`, `Double`, `Float`, `BigDecimal`, `Boolean`, `Date`, "
            "`Timestamp`, `Null`. A column of the row is bound as it is, whatever this says."),
    Key("parameter_value", type=CODE, default="",
        doc="The value: text or a number, a context variable, an entry of globalMap, or a column of the row "
            "(`row1.id`)."),
)


@REGISTRY.register
class OracleRow(Action, Transform):
    """Run one statement in an Oracle database.

    Set off by a trigger, it runs `query` once. With a flow leading to
    it, it runs the statement once for each row, in batches of one round
    trip, with the row's values bound: `"... where id = " + row1.id`
    names a column of the row where the statement is joined, and a
    prepared statement (`use_preparedstatement`) has a mark (`?`) for
    each value `set_preparedstatement_parameters` gives. The rows go on
    as they came. They are held in memory while the statement runs.

    A context variable or an entry of globalMap in the statement is a
    value: one in quotes is bound, one outside quotes has to be a name, a
    number or a list of those. A value of a row is always bound.

    What it does waits on the session of its connection for a commit
    component, or is stored when its subjob is done where it has a
    session of its own. A statement that defines (`CREATE`, `TRUNCATE`
    and the like) is stored by Oracle at once, with whatever waited on
    the session: it is refused on a session with work that waits.

    With no flow to it and one from it, it hands on one row with nothing
    in it, as Talend does: what follows runs once.

    It leaves the statement in `<id>_QUERY` as it was sent, with the
    names of its values and no value, and with `use_nb_line` the rows it
    changed in `<id>_NB_LINE_INSERTED`, `_UPDATED` or `_DELETED`.
    """

    names = ("oracle_row", "OracleRow", "tOracleRow")
    uses_session = "Oracle"
    min_inputs = 0
    max_inputs = 1
    outputs = {"main": ("flow", "main")}
    conforms = False
    may_need_rows = True
    keys = (
        Key("query", type=CODE, required=True, doc="The statement."),
        Key("use_nb_line", default="NONE", choices=("NONE",) + _COUNTERS,
            doc="Which entry of globalMap takes the number of rows the statement changed."),
        DIE_ON_ERROR,
        Key("use_preparedstatement", type=bool, default=False,
            doc="Whether the statement has marks (`?`) that `set_preparedstatement_parameters` gives values for."),
        Key("set_preparedstatement_parameters", type=list, default=[], items=_PARAMETER,
            doc="A value for each mark of the statement."),
        Key("propagate_record_set", kind=Kind.REFUSED, type=object,
            reason="a query's rows are not handed on in a column; read them with an input"),
        Key("record_set_column", kind=Kind.IGNORED, type=object, doc="See `propagate_record_set`."),
        Key("commit_every", kind=Kind.IGNORED, type=object, doc="Talend's rows between commits. The engine ends the transaction."),
        Key("table", kind=Kind.IGNORED, type=object, doc="For Talend's query builder."),
    ) + oracle.WORKING_KEYS + oracle.CONNECTION_KEYS

    def needs_rows(self) -> bool:
        return bool(self.fed)

    def problems(self) -> List[str]:
        config = self.config
        found = oracle.working_problems(config)
        wrong = statements.unreadable(config["query"] or "", self._row())
        if wrong:
            found.append(f"query: {wrong}")
        if not config["use_preparedstatement"]:
            return found
        given = config["set_preparedstatement_parameters"]
        places = [str(entry["parameter_index"]).strip() for entry in given]
        if places != [str(at) for at in range(1, len(given) + 1)]:
            found.append("set_preparedstatement_parameters: the places are to be 1, 2, 3... in their order; they are "
                         f"{', '.join(places) or 'none'}")
        for at, entry in enumerate(given):
            where = f"set_preparedstatement_parameters[{at}]"
            kind = entry["parameter_type"]
            if kind in _NOT_BOUND:
                found.append(f"{where}.parameter_type: a {kind} is not bound; give text, a number or a date")
            elif kind not in _AS and kind != "Null":
                found.append(f"{where}.parameter_type: '{kind}' is no type; the types are {', '.join(_AS)}, Null")
            elif self._column(entry["parameter_value"]) is None and _is_java(entry["parameter_value"]):
                found.append(f"{where}.parameter_value: is Java, and v2 runs none; give a value, a context variable, "
                             "an entry of globalMap or a column of the row")
        return found

    def declared_outputs(self) -> Dict[str, pl.LazyFrame]:
        return {"main": pl.LazyFrame(schema=polars_schema(self.schema))}

    # ------------------------------------------------------------------
    # Once
    # ------------------------------------------------------------------

    def act(self) -> Optional[Dict[str, pl.LazyFrame]]:
        try:
            self._once()
        except FAULTS as fault:
            self.fail_or_go_on(fault, " with its statement not run")
        if "main" not in self.wired:
            return None
        # One row with nothing in it, as Talend hands on: what follows the flow runs once. The column that
        # makes it a row is the engine's own, and is written nowhere.
        row = pl.DataFrame({HIDDEN + "made:" + self.id: [True]})
        return {"main": row.with_columns([pl.lit(None, dtype=kind).alias(name)
                                          for name, kind in polars_schema(self.schema).items()]).lazy()}

    def _once(self) -> None:
        made = statements.read(self.config["query"], self.context, self.global_map, parameters=self._given())
        sessions = self.run_context.sessions
        session, own = oracle.session_of(self)
        if own:
            sessions.own(session)
        waited = sessions.waiting(session)
        if made.defines and waited:
            raise DatabaseError(
                "the statement is one that defines, and Oracle stores what waits on a session before one: the work "
                f"of {', '.join(waited)} would be stored with it. Put a commit before it")
        if not made.defines:
            sessions.working(session, self.id)
        text, binds = session.bound(made)
        try:
            changed = session.run(text, binds)
        except FAULTS:
            if not made.defines and session.alive():
                # A statement the database refused has changed nothing: nothing of it waits to be stored.
                sessions.changed_nothing(session, self.id)
            raise
        if not changed and not made.defines and not _BLOCK.match(text):
            # A query, or a statement that found no row: nothing of it waits to be stored. What a block of
            # PL/SQL changed cannot be seen, and counts.
            sessions.changed_nothing(session, self.id)
        if waited and not session.in_transaction():
            logger.warning(one_line(
                f"[{self.id}] the statement stored what waited on the session by itself: the work of "
                f"{', '.join(waited)} is stored now, with no commit of the job's"))
        self._left(made, changed)

    # ------------------------------------------------------------------
    # For each row
    # ------------------------------------------------------------------

    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        (frame,) = inputs.values()
        try:
            self._for_each(frame)
        except FAULTS as fault:
            self.fail_or_go_on(fault, " with what it did taken back")
        return {"main": frame}

    def _for_each(self, frame: pl.DataFrame) -> None:
        made = statements.read(self.config["query"], self.context, self.global_map, row=self._row(frame),
                               parameters=self._given(frame))
        if made.defines:
            raise ConfigurationError("a statement that defines is run once, and not for each row of a flow: set it off "
                                     "with a trigger")
        text, bound = made.by_place()
        values = frame.select([
            (pl.col(part.column) if part.column is not None else pl.lit(part.value)).alias(f"v{at}")
            for at, part in enumerate(bound)
        ]) if bound else None
        sessions = self.run_context.sessions
        session, own = oracle.session_of(self)
        if own:
            sessions.own(session)
        sessions.working(session, self.id)
        session.savepoint(_MARK)
        changed, refused, first = 0, 0, ""
        try:
            for start in range(0, frame.height, _BATCH):
                # With nothing of the row in the statement, it is sent as it is, for as many times as there are rows.
                batch = values.slice(start, _BATCH).to_arrow() if values is not None else min(_BATCH, frame.height - start)
                turned_away, counts = session.many(text, batch, counts=True)
                changed += sum(counts)
                if turned_away:
                    at, why = turned_away[0]
                    told = f"{why}{self.where(frame.slice(start + at, 1))}"
                    if self.config["die_on_error"]:
                        raise DatabaseError(f"the database refused the statement for a row: {told}")
                    refused += len(turned_away)
                    first = first or told
        except FAULTS:
            if session.alive():
                # What it did is taken back, and with it the word that it waits to be stored.
                session.rollback_to(_MARK)
                sessions.changed_nothing(session, self.id)
            raise
        if not changed and not _BLOCK.match(text):
            # As when it is run once: a query, or a statement that found no row for any of them, leaves nothing
            # waiting.
            sessions.changed_nothing(session, self.id)
        if refused:
            said = (f"the database refused the statement for {refused} of the {frame.height} rows; the first: {first}")
            self.global_map[f"{self.id}_ERROR_MESSAGE"] = said
            logger.warning(one_line(f"[{self.id}] {said}"))
        self._left(made, changed)

    # ------------------------------------------------------------------

    def _left(self, made: statements.Statement, changed: int) -> None:
        """Leave in globalMap the statement as it was sent, and how many rows it changed."""
        held = self.global_map
        held[f"{self.id}_QUERY"] = made.shown()
        for counter in _COUNTERS:
            held[f"{self.id}_{counter}"] = max(changed, 0) if counter == self.config["use_nb_line"] else 0
        logger.info(one_line(f"[{self.id}] ran: {made.shown()}"))

    def _row(self, frame: Optional[pl.DataFrame] = None) -> Optional[Tuple[str, List[str]]]:
        """The flow whose rows the statement is run for, and their columns; None when no flow leads to it."""
        if not self.arriving:
            return None
        columns = visible(frame.columns) if frame is not None else [column.name for column in self.input_schema]
        return self.arriving[0], columns

    def _column(self, written: Any) -> Optional[str]:
        """The column of the row a parameter's value names (`row1.id`), or None."""
        if not self.arriving or not isinstance(written, str):
            return None
        named = re.fullmatch(rf"\s*{re.escape(self.arriving[0])}\.(\w+)\s*", written)
        return named.group(1) if named else None

    def _given(self, frame: Optional[pl.DataFrame] = None) -> Optional[List[statements.Given]]:
        """What each mark of a prepared statement stands for; None when the statement is no prepared one."""
        if not self.config["use_preparedstatement"]:
            return None
        given: List[statements.Given] = []
        for at, entry in enumerate(self.config["set_preparedstatement_parameters"], start=1):
            column = self._column(entry["parameter_value"])
            if column is not None:
                if frame is not None and column not in frame.columns:
                    raise ConfigurationError(f"the value for mark {at} is the column '{column}', which the rows of "
                                             f"{self.arriving[0]} do not have")
                given.append(statements.Given(column=column))
                continue
            given.append(statements.Given(value=self._value(at, entry)))
        return given

    def _value(self, at: int, entry: Dict[str, Any]) -> Any:
        """The value for a mark: what is written, or what it names, as the type its place is given."""
        kind, written = entry["parameter_type"], entry["parameter_value"]
        if kind == "Null":
            return None
        held: Any = written
        if isinstance(written, str):
            named = self.run_context.named(written)
            quoted = _TEXT.fullmatch(written.strip())
            if named is not None:
                held = named.value
            elif quoted:
                held = quoted.group(1)
        if held is None:
            return None
        try:
            # Whatever kind what was looked up is of: it is made the kind its place names.
            return _AS[kind](held if isinstance(held, str) else str(held))
        except (ValueError, decimal.InvalidOperation):
            raise ConfigurationError(f"the value for mark {at} is no {kind}") from None


def _is_java(written: Any) -> bool:
    """Whether a parameter's value is Java that is more than a value: not text in quotes, not a number, not a
    reference that can be looked up."""
    if not isinstance(written, str) or not written.strip():
        return False
    text = written.strip()
    if _TEXT.fullmatch(text) or _NUMBER.fullmatch(text):
        return False
    stripped = text[len("{{java}}"):] if text.startswith("{{java}}") else text
    return parsed(stripped) is None and bool(re.search(r"[()+]", stripped))
