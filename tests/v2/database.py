"""A real database with no server, behind the seam every database component stands on: SQLite.

What is true of a transaction anywhere is true here: a commit stores, a
rollback takes back, a place that was marked can be gone back to, and a
second session sees only what is stored. What is Oracle's alone is not
here; that is tried against a real Oracle (the tests marked ``oracle``).
"""
import datetime
import decimal
import re
import sqlite3
from typing import Any, List, Mapping, Optional, Tuple

from src.v2.errors import DatabaseError
from src.v2.sessions import NUMBER, OTHER, TEXT, ZONED, CallFailed, Field, Session
from src.v2.statements import DEFINES

# What SQLite runs without a transaction of its own being opened for it first.
_NO_TRANSACTION = ("select", "begin", "commit", "rollback", "pragma")


def _for_sqlite(value: Any) -> Any:
    """A value as SQLite holds it: it has no Decimal and no date of its own."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime.datetime) else value.isoformat()
    return value


def _as_sqlite(statement: str) -> str:
    """A statement in Oracle's words as SQLite takes it: three spellings differ, and nothing else is changed."""
    statement = re.sub(r"^\s*truncate table (\S+)( reuse storage)?\s*$", r"delete from \1", statement, flags=re.I)
    statement = re.sub(r"\((\d+) CHAR\)", r"(\1)", statement)
    statement = re.sub(r"cast\((:\d+) as date\)", r"\1", statement)
    return re.sub(r":(\d+)", r"?\1", statement)


class SqliteSession(Session):
    """A session with a SQLite file. It opens a transaction with the first change, as Oracle does."""

    def __init__(self, path: str, opened_by: str, **more: Any) -> None:
        super().__init__(opened_by, f"SQLite session of '{opened_by}'", **more)
        self.path = path
        self._held = sqlite3.connect(path, isolation_level=None, timeout=0.5)
        self.closed = False
        # Everything it was asked to do, in order: what the engine did with it can be read here.
        self.did: List[str] = []
        # Every statement as it was asked, in Oracle's words.
        self.asked: List[str] = []

    def run(self, statement: str, binds: Optional[Mapping[str, Any]] = None) -> int:
        self.asked.append(statement)
        defines = statement.lstrip().split(None, 1)[0].upper() in DEFINES
        statement = _as_sqlite(statement)
        first = statement.lstrip().split(None, 1)[0].lower()
        given = {name: float(value) if isinstance(value, decimal.Decimal) else value for name, value in dict(binds or {}).items()}
        try:
            if first not in _NO_TRANSACTION and not self._held.in_transaction:
                self._held.execute("begin")
            done = self._held.execute(statement, given)
            if defines and self._held.in_transaction:
                # As Oracle has it: a statement that defines stores itself, and what waited before it.
                self._held.execute("commit")
        except sqlite3.Error as fault:
            raise DatabaseError(str(fault)) from None
        self.did.append(statement)
        # A query changed no row. (SQLite says -1 of one; Oracle says 0.)
        return max(done.rowcount, 0)

    def commit(self) -> None:
        self.did.append("commit")
        self._connected()
        if self._held.in_transaction:
            self._held.execute("commit")

    def rollback(self) -> None:
        self.did.append("rollback")
        self._connected()
        if self._held.in_transaction:
            self._held.execute("rollback")

    def _connected(self) -> None:
        """A session that is closed ends no transaction: what python-oracledb said of one the database had closed,
        for a commit and for a rollback, on 2026-10-12."""
        if self.closed:
            raise DatabaseError("DPY-1001: not connected to database")

    def savepoint(self, name: str) -> None:
        self.run(f"savepoint {name}")

    def rollback_to(self, name: str) -> None:
        self.run(f"rollback to savepoint {name}")

    def in_transaction(self) -> bool:
        return self._held.in_transaction

    def alive(self) -> bool:
        return not self.closed

    def close(self) -> None:
        self.did.append("close")
        self._held.close()
        self.closed = True

    # ------------------------------------------------------------------
    # Storing: a statement run once for each row of a batch, where a row that is refused stops no other.
    # ------------------------------------------------------------------

    def many(self, statement, rows, counts=False):
        self.asked.append(statement)
        # For a statement that takes no value: how many times it is run.
        given = [{}] * rows if isinstance(rows, int) else rows.to_pylist()
        self.did.append(("many", statement, len(given)))
        if not self._held.in_transaction:
            self._held.execute("begin")
        refused, changed = [], []
        for at, row in enumerate(given):
            values = [_for_sqlite(value) for value in row.values()]
            try:
                done = self._held.execute(_as_sqlite(statement), values)
                # A query changed no row. (SQLite says -1 of one; Oracle says 0.)
                changed.append(max(done.rowcount, 0))
            except sqlite3.IntegrityError as fault:
                # A row the table does not take: the others go on.
                refused.append((at, str(fault)))
                changed.append(0)
            except sqlite3.Error as fault:
                # The statement itself cannot be run (no such table): it fails for every row, as in Oracle.
                raise DatabaseError(str(fault)) from None
        return refused, changed if counts else []

    # SQLite has no procedures: a test says what one of a name does, as a function of the values handed in
    # that hands back the values out, by place.
    procedures: dict = {}

    def call(self, block, rows, outs, ins=None):
        self.asked.append(block)
        self.did.append(("call", block, len(rows)))
        name = re.search(r"([\w.$#]+)\s*(?:\(|;)", block.split(":=")[-1]).group(1)
        handed = {place: [] for place in outs}
        for at, row in enumerate(rows):
            try:
                out = self.procedures[name](*row)
            except KeyError:
                raise CallFailed(at, f"no procedure {name}") from None
            except Exception as fault:  # noqa: BLE001 -- whatever the stand-in procedure raises is its failure
                raise CallFailed(at, str(fault)) from None
            for place in outs:
                handed[place].append(out.get(place))
        return handed

    def is_missing(self, fault):
        return "no such table" in str(fault)

    def is_there_already(self, fault):
        return "already exists" in str(fault)

    # ------------------------------------------------------------------
    # Reading. SQLite has no types of its own for a column of a result: what a column is, is seen in its
    # first row, and the converting is done here, where a real database does it itself.
    # ------------------------------------------------------------------

    advice = {ZONED: "say which clock is meant", OTHER: "turn it into text"}

    def bound(self, statement):
        return statement.named()

    def fields(self, statement, binds=None):
        self.did.append(("fields", statement))
        try:
            found = self._held.execute(f"select * from ({statement.rstrip().rstrip(';')}) limit 1", dict(binds or {}))
        except sqlite3.Error as fault:
            raise DatabaseError(str(fault)) from None
        first = found.fetchone()
        kinds = {int: (NUMBER, "INTEGER"), float: (NUMBER, "REAL"), str: (TEXT, "TEXT"), bytes: (OTHER, "a BLOB")}
        return [Field(described[0], *kinds.get(type(None if first is None else first[at]), (TEXT, "TEXT")))
                for at, described in enumerate(found.description)]

    def typed(self, statement, columns, fields):
        import pyarrow
        kinds = {"int": pyarrow.int64(), "float": pyarrow.float64(), "bool": pyarrow.int8(), "str": pyarrow.large_string()}
        types = []
        for column, field in zip(columns, fields):
            if field.family == TEXT:
                types.append(pyarrow.large_string())
            elif column.type == "Decimal":
                types.append(pyarrow.decimal128(38, 10 if column.precision is None else column.precision))
            else:
                types.append(kinds[column.type])
        return statement.rstrip().rstrip(";"), types

    def batches(self, statement, binds, types, size):
        import pyarrow
        self.did.append(("query", statement, dict(binds or {})))
        try:
            found = self._held.execute(statement, dict(binds or {}))
        except sqlite3.Error as fault:
            raise DatabaseError(str(fault)) from None

        def as_asked(value, kind):
            if value is None:
                return None
            if pyarrow.types.is_decimal(kind):
                return decimal.Decimal(str(value)).quantize(decimal.Decimal(1).scaleb(-kind.scale))
            if pyarrow.types.is_large_string(kind):
                return str(value)
            if pyarrow.types.is_int8(kind):
                return int(value != 0)
            return int(value) if pyarrow.types.is_integer(kind) else float(value)

        names = [f"C{at}" for at in range(1, len(types) + 1)]
        while True:
            rows = found.fetchmany(size)
            if not rows and self.did[-1] != "batch":
                yield pyarrow.table({name: pyarrow.array([], kind) for name, kind in zip(names, types)})
            if not rows:
                return
            self.did.append("batch")
            yield pyarrow.table({name: pyarrow.array([as_asked(row[at], kind) for row in rows], kind)
                                 for at, (name, kind) in enumerate(zip(names, types))})


def database(tmp_path, *tables: str) -> str:
    """A fresh SQLite file with tables in it, each given as ``name(column, ...)``. Returns its path."""
    path = str(tmp_path / "db.sqlite")
    held = sqlite3.connect(path)
    for table in tables:
        held.execute(f"create table {table}")
    held.commit()
    held.close()
    return path


def stored(path: str, statement: str) -> List[Tuple[Any, ...]]:
    """What a session of its own sees: the rows that are stored, and none that only wait to be."""
    held = sqlite3.connect(path, timeout=0.5)
    try:
        return held.execute(statement).fetchall()
    finally:
        held.close()


# ------------------------------------------------------------------
# Oracle components on SQLite
# ------------------------------------------------------------------

import pytest  # noqa: E402

from src.v2 import oracle  # noqa: E402
from src.v2.components.base import Action  # noqa: E402
from src.v2.components.registry import REGISTRY, Registry  # noqa: E402
from src.v2.errors import ConfigurationError  # noqa: E402
from src.v2.job.keys import CODE, Key  # noqa: E402


class Opened:
    """What stands in for ``oracle.opened``: it notes what it was asked, and opens a session with a SQLite file."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.asked: List[Any] = []
        self.sessions: List[SqliteSession] = []
        self.refuses = ""

    def __call__(self, config, opened_by, job_name, settings=None, **more):
        self.asked.append((dict(config), opened_by, job_name, settings, more))
        if self.refuses:
            raise DatabaseError(self.refuses)
        self.sessions.append(SqliteSession(self.path, opened_by, schema=config["schema_db"], **more))
        return self.sessions[-1]

    def stored(self, statement: str = "select n from t order by n") -> List[Tuple[Any, ...]]:
        return stored(self.path, statement)


@pytest.fixture
def on_sqlite(monkeypatch, tmp_path):
    """Oracle components whose sessions are with a SQLite file holding a table ``t(n)``."""
    made = Opened(database(tmp_path, "t(n)"))
    monkeypatch.setattr(oracle, "opened", made)
    return made


class Does(Action):
    """A stand-in for a component that changes something: it runs a statement on the session of `connection`."""

    names = ("does",)
    keys = (Key("connection", required=True), Key("statement", type=CODE, required=True), Key("then", default=""))

    def act(self) -> None:
        sessions = self.run_context.sessions
        session = sessions.shared(self.config["connection"])
        sessions.working(session, self.id)
        session.run(self.config["statement"])
        if self.config["then"] == "fails":
            raise ConfigurationError("it failed after its work")


# Every component of the engine, and the stand-in beside them.
WITH_DOES = Registry()
for _cls in (*REGISTRY.classes(), Does):
    WITH_DOES.register(_cls)


# ------------------------------------------------------------------
# SQL Server components on SQLite
# ------------------------------------------------------------------

from src.v2 import mssql  # noqa: E402


class OpenedMssql(Opened):
    """What stands in for ``mssql.opened``: it notes what it was asked, and opens a session with a SQLite file."""

    def __call__(self, config, opened_by, **more):
        self.asked.append((dict(config), opened_by, more))
        if self.refuses:
            raise DatabaseError(self.refuses)
        self.sessions.append(SqliteSession(self.path, opened_by, schema=config["schema_db"], **more))
        return self.sessions[-1]


@pytest.fixture
def mssql_on_sqlite(monkeypatch, tmp_path):
    """SQL Server components whose sessions are with a SQLite file holding a table ``t(n)``."""
    made = OpenedMssql(database(tmp_path, "t(n)"))
    monkeypatch.setattr(mssql, "opened", made)
    return made
