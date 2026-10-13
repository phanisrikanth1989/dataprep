"""The database sessions of a run.

A component does its work on a session and never ends a transaction. The
engine does. When a subjob has succeeded, every session a component opened
for itself is committed, before any file of the subjob is put in place;
when it has not, the session is rolled back. A session a connection
component opened is shared: other components work on it, a commit
component stores what they did, and a subjob that fails on it loses its
own work and no other.

Every call to a driver is made on the engine's own thread, when a subjob
is built or when its pass has run. Rows cross between a plan and a
database through scratch files, never in the pass, so no session is ever
asked two things at once.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Mapping, Optional, Tuple

from .errors import ConfigurationError, DatabaseError
from .job.keys import Key

if TYPE_CHECKING:
    from .job.model import Column
    from .statements import Statement

logger = logging.getLogger(__name__)

# The place a shared session is marked at when a subjob first changes something through it.
_MARK = "v2_subjob"

# On every component that works in a database, beside its connection block: whose session it works on.
WORKING_KEYS: Tuple[Key, ...] = (
    Key("use_existing_connection", type=bool, default=False,
        doc="Whether it works on the session of the connection component `connection` names. Without it, it "
            "opens a session of its own with its connection block."),
    Key("connection", default="", doc="The id of that connection component. It has to be one of the job."),
)


# The kinds of column a query hands back, as far as a job's declared types care.
NUMBER, TEXT, DATE, ZONED, OTHER = "number", "text", "date", "date with a time zone", "other"
_NUMBERS = ("int", "float", "Decimal", "bool")
_DATES = ("datetime", "date")
_A = {"int": "a whole number", "float": "a float", "Decimal": "a Decimal", "bool": "a true/false", "datetime": "a datetime",
      "date": "a date", "str": "text"}


@dataclass(frozen=True)
class Field:
    """One column of what a query hands back, as the database describes it before the query runs.

    Attributes:
        name: Its name there.
        family: ``NUMBER``, ``TEXT``, ``DATE``, ``ZONED`` or ``OTHER``.
        said: The database's own name for its type, for a message.
        advice: For a column of a kind that cannot be taken: what to write
            in the query for this kind, when that is more than the
            session says of every such kind.
    """

    name: str
    family: str
    said: str
    advice: str = ""


def taken(columns: List["Column"], fields: List[Field], advice: Mapping[str, str]) -> List[bool]:
    """How each declared column gets its value from what a query hands back, column by place.

    The database converts within a kind: a number to any number or to
    text, a date to a date or to text, text to text. Text that the job
    declares as anything else is handed on as text and read by the engine,
    as the text of a file is. A number is no date, and a date no number.

    Args:
        columns: The declared columns.
        fields: What the query hands back.
        advice: For a kind that cannot be taken (``ZONED``, ``OTHER``):
            what to write in the query instead, in the database's own words.

    Returns:
        For each column, whether the engine reads it from text.

    Raises:
        ConfigurationError: When the query and the declared columns do not
            go together. Every such column is named.
    """
    if len(fields) != len(columns):
        raise ConfigurationError(
            f"the query hands back {len(fields)} column(s) and the job declares {len(columns)}: they are taken by "
            "their place, so there have to be as many")
    wrong: List[str] = []
    from_text: List[bool] = []
    for column, field in zip(columns, fields):
        declared, family = column.type, field.family
        from_text.append(family == TEXT and declared != "str")
        why = ""
        if family == NUMBER and declared in _DATES:
            why = f"a number ({field.said}), and the job declares {_A[declared]}"
        elif family == DATE and declared in _NUMBERS:
            why = f"a date ({field.said}), and the job declares {_A[declared]}"
        elif family == ZONED and declared != "str":
            why = f"a date with a time zone ({field.said}), and {_A[declared]} has none: {advice[ZONED]}"
        elif family == OTHER:
            why = f"{field.said}, which v2 does not read: {field.advice or advice[OTHER]}"
        if why:
            wrong.append(f"column '{column.name}': the query hands back {why}")
    if wrong:
        raise ConfigurationError("; ".join(wrong))
    return from_text


# ------------------------------------------------------------------
# What is said of every database's connection block the same way
# ------------------------------------------------------------------

# How Talend writes a password it has encrypted with a key of its own.
_ENCRYPTED = "enc:system.encryption.key.v1:"


def password_problems(password: Any) -> List[str]:
    """What is wrong with a password that no database can be given: text Talend encrypted. It is not shown."""
    if isinstance(password, str) and password.startswith(_ENCRYPTED):
        return ["password: is text Talend encrypted with a key of its own, which v2 cannot read; give the "
                "password itself, from a context variable (`${context.db_password}`)"]
    return []


def filled(value: Any) -> bool:
    """Whether a key of a connection block holds anything: text that is more than blanks."""
    return isinstance(value, str) and bool(value.strip())


def listed(names: List[str]) -> str:
    """Names as a message lists them, each between backticks: ``a``, ``a and b``, ``a, b and c``."""
    quoted = [f"`{name}`" for name in names]
    return quoted[0] if len(quoted) == 1 else f"{', '.join(quoted[:-1])} and {quoted[-1]}"


def in_ascii(text: str) -> str:
    """A text as plain ASCII, for a log line or a failure: what is beyond ASCII is written as an escape."""
    return text.encode("ascii", "backslashreplace").decode("ascii")


class CallFailed(DatabaseError):
    """One call of several that were sent together failed.

    Attributes:
        at: Which of them, from 0.
    """

    def __init__(self, at: int, reason: str) -> None:
        super().__init__(reason)
        self.at = at


class Unstored(Exception):
    """What a component did could not be stored when its subjob had succeeded.

    Attributes:
        component_id: The component whose work it was.
    """

    def __init__(self, component_id: str, reason: str) -> None:
        super().__init__(reason)
        self.component_id = component_id


class Session:
    """One session with a database. Each kind of database has a kind of its own.

    What it cannot do it says with ``DatabaseError``, in the database's
    words on one line.

    Attributes:
        opened_by: The id of the component that opened it.
        what: The words a log line names it by.
        shared: Whether a connection component opened it, for others to
            work on.
        auto_commit: For a shared session: whether what a subjob did on it
            is stored when that subjob has succeeded, with no commit
            component.
        schema: The schema its connection block names, where a table is
            looked for.
        pending: The ids of the components whose work on it is not stored.
        lost: The ids of the components whose work waited on it when the
            database closed it: never stored, and gone.
    """

    def __init__(
        self, opened_by: str, what: str, shared: bool = False, auto_commit: bool = False, schema: str = ""
    ) -> None:
        self.opened_by = opened_by
        self.what = what
        self.shared = shared
        self.auto_commit = auto_commit
        self.schema = schema
        self.pending: List[str] = []
        self.lost: List[str] = []
        # In the subjob being run: who changed something through it, and what was pending before the first did.
        self.in_subjob: List[str] = []
        self.before_subjob: List[str] = []

    # For a column of a kind that cannot be taken as the job declares it: what to write in the query instead.
    advice: Mapping[str, str] = {}
    # How many rows a round trip brings best when the job does not say; None where the reader's own number does.
    rows_a_round_trip: Optional[int] = None

    def run(self, statement: str, binds: Optional[Mapping[str, Any]] = None) -> int:
        """Run one statement with its bound values. Returns how many rows it changed."""
        raise NotImplementedError

    def bound(self, statement: "Statement") -> Tuple[str, Any]:
        """A statement as this database takes it: its text, and its values the way they are handed over."""
        raise NotImplementedError

    def fields(self, statement: str, binds: Any = None) -> List[Field]:
        """What a query hands back, column by column, before any of its rows is taken.

        Where the database can say so, the query is not run for it. Where
        it cannot (SQL Server says what a statement hands back only when it
        runs it), the query is run, and its rows wait for ``batches``.
        """
        raise NotImplementedError

    def typed(self, statement: str, columns: List["Column"], fields: List[Field]) -> Tuple[str, List[Any]]:
        """The query that hands each column on as the job declares it, and the Arrow type each is asked for in.

        The database does the converting: a driver's own may lose digits.
        A column of text is handed on as text, whatever the job declares.
        """
        raise NotImplementedError

    def batches(self, statement: str, binds: Any, types: List[Any], size: int) -> Iterator[Any]:
        """Run a query and hand its rows back a batch at a time, as Arrow tables of the types asked for."""
        raise NotImplementedError

    def many(self, statement: str, rows: Any, counts: bool = False) -> Tuple[List[Tuple[int, str]], List[int]]:
        """Run a statement once for each row of an Arrow batch, in one round trip; its values go by place.

        A row the database refuses does not stop the others. A statement
        that changes no rows by itself (a block, a call, a query) may take
        more round trips: one more for each row that is refused, or one
        for each row.

        Args:
            statement: The statement, with `:1`, `:2`... where the columns
                of a row go, in their order.
            rows: The batch; or, for a statement that takes no value, how
                many times it is run.
            counts: Whether to say how many rows each row changed.

        Returns:
            The rows that were refused, each as its place in the batch and
            what the database said; and, when asked for, how many rows of
            the table each row of the batch changed.
        """
        raise NotImplementedError

    def call(
        self, block: str, rows: List[Tuple[Any, ...]], outs: Mapping[int, str], ins: Optional[Mapping[int, str]] = None
    ) -> Dict[int, List[Any]]:
        """Run a block that calls a procedure once for each row of values, in one round trip.

        Args:
            block: The block, with `:1`, `:2`... where the values of a row
                go, in their order.
            rows: For each call, its values by place; None at a place that
                only hands a value out.
            outs: Each place that hands a value out, from 0, and the kind
                of value it hands out: ``number``, ``text``, ``date``,
                ``datetime`` or ``large text``.
            ins: The places that only take a value in whose kind has to
                be said for it, and that kind: ``datetime`` for a moment,
                which a driver may otherwise take for a date.

        Returns:
            For each such place, the value every call handed out.

        Raises:
            CallFailed: A call failed; the ones before it are done.
        """
        raise NotImplementedError

    def is_missing(self, fault: DatabaseError) -> bool:
        """Whether a fault says that a table is not there."""
        raise NotImplementedError

    def is_there_already(self, fault: DatabaseError) -> bool:
        """Whether a fault says that a name is taken by something that is there."""
        raise NotImplementedError

    def commit(self) -> None:
        """Store what was done."""
        raise NotImplementedError

    def rollback(self) -> None:
        """Take back what was done and not stored."""
        raise NotImplementedError

    def savepoint(self, name: str) -> None:
        """Mark the place the transaction is at."""
        raise NotImplementedError

    def rollback_to(self, name: str) -> None:
        """Take back what was done since a place was marked. The transaction stays open."""
        raise NotImplementedError

    def in_transaction(self) -> bool:
        """Whether anything was done that is neither stored nor taken back."""
        raise NotImplementedError

    def alive(self) -> bool:
        """Whether the database still holds the session. Asking costs no round trip."""
        raise NotImplementedError

    def close(self) -> None:
        """End the session. What was not stored is lost."""
        raise NotImplementedError


class Sessions:
    """The sessions of one run: the shared ones, and the ones components opened for the subjob being run."""

    def __init__(self) -> None:
        # By the id of the connection component that opened each.
        self._shared: Dict[str, Session] = {}
        # In the order they were opened.
        self._own: List[Session] = []
        # The commits and rollbacks that wait for the subjob to succeed: connection, which, whether it closes,
        # and the component that asked.
        self._waiting: List[Tuple[str, str, bool, str]] = []

    # ------------------------------------------------------------------
    # What a component asks
    # ------------------------------------------------------------------

    def share(self, session: Session) -> None:
        """Hold a session a connection component opened, for other components to work on.

        Raises:
            DatabaseError: When the session that component opened before is
                still open with work nothing stored. The new one is closed.
        """
        earlier = self._shared.get(session.opened_by)
        if earlier is not None:
            waiting = self._unstored(earlier)
            if waiting:
                _closed(session)
                raise DatabaseError(
                    f"the session it opened before is still open, and what {_named(waiting)} did on it was never "
                    "stored: commit it or roll it back before the session is opened again"
                )
            _closed(earlier)
        session.shared = True
        self._shared[session.opened_by] = session

    def shared(self, connection_id: str) -> Session:
        """The open session of a connection component.

        Raises:
            DatabaseError: When it has none.
        """
        session = self._shared.get(connection_id)
        if session is None:
            raise DatabaseError(f"'{connection_id}' has no open session: it has not run, or its session was closed")
        return session

    def own(self, session: Session) -> Session:
        """Hold a session a component opened for itself: the engine ends it with the subjob."""
        self._own.append(session)
        return session

    def working(self, session: Session, component_id: str) -> None:
        """Say that a component is about to change something through a session.

        A shared session is marked where it stands, the first time in a
        subjob: that is where a failure of the subjob takes it back to.
        """
        if not session.in_subjob:
            session.before_subjob = list(session.pending)
            if session.shared:
                session.savepoint(_MARK)
        for held in (session.in_subjob, session.pending):
            if component_id not in held:
                held.append(component_id)

    def changed_nothing(self, session: Session, component_id: str) -> None:
        """Take back the word that a component changed something: its statement turned out to change no row.

        A database counts the place that was marked for it as an open
        transaction all the same. Without this a query, or an update that
        found no row, would be work that waits for a commit.
        """
        if component_id in session.in_subjob:
            session.in_subjob.remove(component_id)
        if component_id in session.pending and component_id not in session.before_subjob:
            session.pending.remove(component_id)

    def commit(self, connection_id: str, close: bool = False) -> List[str]:
        """Store what was done on a shared session. Returns the ids of the components whose work it was."""
        session = self.shared(connection_id)
        session.commit()
        stored, session.pending, session.in_subjob = session.pending, [], []
        if close:
            self._let_go(connection_id)
        return stored

    def rollback(self, connection_id: str, close: bool = False) -> None:
        """Take back what was done on a shared session and not stored."""
        session = self.shared(connection_id)
        session.rollback()
        session.pending, session.in_subjob = [], []
        if close:
            self._let_go(connection_id)

    def close(self, connection_id: str, uncommitted: str = "fail") -> bool:
        """Close a shared session. Returns whether there was one to close.

        Args:
            connection_id: The connection component that opened it.
            uncommitted: What becomes of work nothing stored: ``commit``
                stores it, ``rollback`` takes it back, and ``fail`` takes
                it back and fails.

        Raises:
            DatabaseError: When work was waiting and the close was to fail
                on it; or when work was lost with a session the database
                closed, and the close was not to take it back anyway. The
                session is closed all the same.
        """
        session = self._shared.get(connection_id)
        if session is None:
            return False
        waiting = self._unstored(session)
        lost = list(session.lost)
        try:
            if waiting and uncommitted == "commit":
                session.commit()
            elif waiting:
                session.rollback()
        finally:
            self._let_go(connection_id)
        if lost and uncommitted != "rollback":
            raise DatabaseError(_lost(connection_id, lost))
        if waiting and uncommitted == "fail":
            raise DatabaseError(
                f"what {_named(waiting)} did on the session of '{connection_id}' was never stored, and is rolled "
                "back: put a commit before the close, or say with `uncommitted` what a close does with such work "
                "(`commit` or `rollback`)"
            )
        return True

    def waiting(self, session: Session) -> List[str]:
        """The ids of the components whose work on a session is not stored yet; none when nothing waits there."""
        return self._unstored(session)

    def when_done(self, connection_id: str, act: str, close: bool, component_id: str) -> None:
        """Have a shared session committed or rolled back when the subjob being run has succeeded.

        Args:
            connection_id: The connection component that opened it.
            act: ``commit`` or ``rollback``.
            close: Whether the session is closed after it.
            component_id: The component that asks: a failure is its own.
        """
        self._waiting.append((connection_id, act, close, component_id))

    # ------------------------------------------------------------------
    # What the engine tells
    # ------------------------------------------------------------------

    def subjob_succeeded(self) -> List[str]:
        """Store what the subjob did on the sessions that are its own to end.

        Called when every row of the subjob is where it can be stored from
        and before any of its files is put in place: a commit can fail,
        and what follows it must not have happened then.

        Returns:
            The ids of the components whose work was stored.

        Raises:
            Unstored: When a commit failed. What was stored before it stays
                stored; the rest waits for ``subjob_failed``.
        """
        stored: List[str] = []
        while self._own:
            session = self._own[0]
            try:
                session.commit()
            except DatabaseError as fault:
                before = f"; what {_named(stored)} did is stored already" if stored else ""
                raise Unstored(session.opened_by, f"what it did could not be stored: {fault}{before}") from fault
            stored.append(self._own.pop(0).opened_by)
            _closed(session)
        while self._waiting:
            connection_id, act, close, component_id = self._waiting.pop(0)
            try:
                if act == "commit":
                    stored += self.commit(connection_id, close)
                else:
                    self.rollback(connection_id, close)
            except DatabaseError as fault:
                raise Unstored(component_id, str(fault)) from fault
        for connection_id, session in list(self._shared.items()):
            if session.auto_commit and session.in_subjob:
                try:
                    stored += self.commit(connection_id)
                except DatabaseError as fault:
                    raise Unstored(session.in_subjob[0], f"what it did could not be stored: {fault}") from fault
            session.in_subjob = []
        return stored

    def subjob_failed(self) -> None:
        """Take back what the subjob did. Nothing here fails: a subjob that failed has its reason already."""
        own, self._own, self._waiting = self._own, [], []
        for session in own:
            if session.alive():
                _quietly(session.rollback)
            _closed(session)
        for connection_id, session in list(self._shared.items()):
            if not session.in_subjob:
                continue
            did, session.in_subjob = session.in_subjob, []
            if not session.alive():
                gone = session.lost + [held for held in session.pending if held not in session.lost]
                logger.error(f"[{connection_id}] the database has closed its session: what {_named(gone)} "
                             "did on it is lost")
                self._let_go(connection_id)
                continue
            try:
                if session.in_transaction():
                    session.rollback_to(_MARK)
                session.pending = session.before_subjob
            except DatabaseError as fault:
                logger.error(f"[{connection_id}] what {_named(did)} did before its subjob failed could not be taken "
                             f"back: {fault}")

    def job_ends(self) -> List[Tuple[str, str]]:
        """Close every session that is still open.

        Work that waits on one is rolled back, and is a failure of the
        job: rows that were loaded and never stored. So is work that was
        lost with a session the database closed.

        Returns:
            Each such failure: the connection component, and what to say.
        """
        self.subjob_failed()
        told: List[Tuple[str, str]] = []
        for connection_id, session in list(self._shared.items()):
            waiting = self._unstored(session)
            if session.lost:
                told.append((connection_id, _lost(connection_id, session.lost)))
            if waiting:
                _quietly(session.rollback)
                told.append((connection_id, (
                    f"the job ended with work that was never stored: what {_named(waiting)} did on the session of "
                    f"'{connection_id}' is rolled back, since no commit followed it"
                )))
            self._let_go(connection_id)
        return told

    # ------------------------------------------------------------------

    def _unstored(self, session: Session) -> List[str]:
        """The components whose work waits on a session; none when the database holds nothing unstored.

        Work that waited on a session the database has closed waits no
        more: it is kept as lost, for whoever ends the session to say.
        """
        if session.pending and not session.in_transaction():
            # Something stored it without the engine: a statement that commits by itself.
            session.pending = []
        elif session.pending and not session.alive():
            session.lost += [held for held in session.pending if held not in session.lost]
            session.pending = []
        return list(session.pending)

    def _let_go(self, connection_id: str) -> None:
        _closed(self._shared.pop(connection_id))


def _lost(connection_id: str, component_ids: List[str]) -> str:
    return (f"the database has closed the session of '{connection_id}': what {_named(component_ids)} did on it was "
            "never stored, and is lost")


def _named(component_ids: List[str]) -> str:
    """Component ids as words: ``a``, ``a and b``, ``a, b and c``."""
    if len(component_ids) < 2:
        return "".join(component_ids)
    return f"{', '.join(component_ids[:-1])} and {component_ids[-1]}"


def _quietly(act: Any) -> None:
    """Do what ends or undoes something, where a failure of it changes nothing: the database lets go by itself."""
    try:
        act()
    except DatabaseError:
        pass


def _closed(session: Session) -> None:
    _quietly(session.close)
