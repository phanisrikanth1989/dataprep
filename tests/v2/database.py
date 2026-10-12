"""A real database with no server, behind the seam every database component stands on: SQLite.

What is true of a transaction anywhere is true here: a commit stores, a
rollback takes back, a place that was marked can be gone back to, and a
second session sees only what is stored. What is Oracle's alone is not
here; that is tried against a real Oracle (the tests marked ``oracle``).
"""
import sqlite3
from typing import Any, List, Mapping, Optional, Tuple

from src.v2.errors import DatabaseError
from src.v2.sessions import Session

# What SQLite runs without a transaction of its own being opened for it first.
_NO_TRANSACTION = ("select", "begin", "commit", "rollback", "pragma")


class SqliteSession(Session):
    """A session with a SQLite file. It opens a transaction with the first change, as Oracle does."""

    def __init__(self, path: str, opened_by: str, **more: Any) -> None:
        super().__init__(opened_by, f"SQLite session of '{opened_by}'", **more)
        self.path = path
        self._held = sqlite3.connect(path, isolation_level=None, timeout=0.5)
        self.closed = False
        # Everything it was asked to do, in order: what the engine did with it can be read here.
        self.did: List[str] = []

    def run(self, statement: str, binds: Optional[Mapping[str, Any]] = None) -> int:
        first = statement.lstrip().split(None, 1)[0].lower()
        try:
            if first not in _NO_TRANSACTION and not self._held.in_transaction:
                self._held.execute("begin")
            done = self._held.execute(statement, dict(binds or {}))
        except sqlite3.Error as fault:
            raise DatabaseError(str(fault)) from None
        self.did.append(statement)
        return done.rowcount

    def commit(self) -> None:
        self.did.append("commit")
        if self._held.in_transaction:
            self._held.execute("commit")

    def rollback(self) -> None:
        self.did.append("rollback")
        if self._held.in_transaction:
            self._held.execute("rollback")

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
