"""Oracle commit, rollback and close: what ends the work on a shared session, and the session."""
from __future__ import annotations

import logging
from typing import ClassVar, Dict, List

import polars as pl

from ...errors import DatabaseError
from ...job.keys import Key
from ..base import Action, Transform
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

CONNECTION = Key("connection", default="",
                 doc="The id of the connection component whose session it ends. It has to be one of the job.")
CLOSE = Key("close", type=bool, default=True, doc="Whether the session is closed afterwards.")
_NUMBER = "__v2_reached"


def _work(component_ids: List[str]) -> str:
    """Whose work was stored or taken back, in the words a log line ends with."""
    if not component_ids:
        return "nothing waited on it"
    named = component_ids[0] if len(component_ids) == 1 else f"{', '.join(component_ids[:-1])} and {component_ids[-1]}"
    return f"the work of {named}"


class _Ends(Action, Transform):
    """What a commit and a rollback share: set off by a trigger they act; in a flow they act when a row came."""

    min_inputs = 0
    max_inputs = 1
    outputs = {"main": ("flow", "main")}
    conforms = False
    uses_session = "Oracle"
    keys = (CONNECTION, CLOSE)
    # ``commit`` or ``rollback``, and the word a log line says it was done with.
    does: ClassVar[str] = ""
    did: ClassVar[str] = ""

    def problems(self) -> List[str]:
        return self.unfed()

    def act(self) -> None:
        self._end()

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        config, sessions = self.config, self.run_context.sessions

        def came(found: pl.DataFrame) -> None:
            if found.item():
                sessions.when_done(config["connection"], self.does, config["close"], self.id)
            else:
                logger.info(f"[{self.id}] no row reached it: the session of '{config['connection']}' is left as it is")

        # Every row is drawn through, as a flow that ends here would have them: what fails a row before it fails
        # the subjob. They are counted by their numbers: a count asked for outright is wrong on Polars 1.44 for
        # frames put one after another and cut.
        numbered = frame.with_row_index(_NUMBER)
        self.tap(numbered.select(pl.col(_NUMBER).count()), came)
        return {"main": frame} if "main" in self.wired else {}

    def _end(self) -> None:
        raise NotImplementedError

    def _said(self, work: List[str]) -> None:
        closed = " and closed it" if self.config["close"] else ""
        logger.info(f"[{self.id}] {self.did} the session of '{self.config['connection']}' ({_work(work)}){closed}")


@REGISTRY.register
class OracleCommit(_Ends):
    """Store what was done on the session of an Oracle connection, and close the session unless `close` is off.

    Set off by a trigger, it commits when its turn comes. With a flow
    leading to it, it commits once, when its subjob has succeeded and a
    row reached it; the rows go on as they came. (Talend commits at the
    first row, while the others are still on their way.)

    A session that is not open fails it: a commit that stores nothing is
    a job that stored nothing.
    """

    names = ("oracle_commit", "OracleCommit", "tOracleCommit")
    does, did = "commit", "committed"

    def _end(self) -> None:
        sessions, connection = self.run_context.sessions, self.config["connection"]
        waiting = list(sessions.shared(connection).pending)
        sessions.commit(connection, self.config["close"])
        self._said(waiting)


@REGISTRY.register
class OracleRollback(_Ends):
    """Take back what was done on the session of an Oracle connection and not stored, and close the session unless
    `close` is off.

    Set off by a trigger, it rolls back when its turn comes. With a flow
    leading to it, it rolls back once, when its subjob has succeeded and
    a row reached it; the rows go on as they came.

    A session that is not open has nothing to take back, and is no fault.
    """

    names = ("oracle_rollback", "OracleRollback", "tOracleRollback")
    does, did = "rollback", "rolled back"

    def _end(self) -> None:
        sessions, connection = self.run_context.sessions, self.config["connection"]
        try:
            waiting = list(sessions.shared(connection).pending)
        except DatabaseError:
            logger.info(f"[{self.id}] '{connection}' has no open session: there is nothing to roll back")
            return
        sessions.rollback(connection, self.config["close"])
        self._said(waiting)


def _choice(value: str) -> str:
    return value.strip().lower()


@REGISTRY.register
class OracleClose(Action):
    """Close the session of an Oracle connection.

    Work that waits on the session, done and never stored, fails the job
    and is rolled back: a close is no commit. (Talend's close stores such
    work, so a close in a clean-up stores the half of a job that
    failed.) `uncommitted` says otherwise.

    A session that is not open is no fault.
    """

    names = ("oracle_close", "OracleClose", "tOracleClose")
    uses_session = "Oracle"
    keys = (
        CONNECTION,
        Key("uncommitted", default="fail", convert=_choice, choices=("fail", "commit", "rollback"),
            doc="What becomes of work that was done on the session and never stored: `fail` rolls it back and "
                "fails the job, `commit` stores it, `rollback` takes it back and goes on."),
    )

    def act(self) -> None:
        connection = self.config["connection"]
        if self.run_context.sessions.close(connection, self.config["uncommitted"]):
            logger.info(f"[{self.id}] closed the session of '{connection}'")
        else:
            logger.info(f"[{self.id}] '{connection}' has no open session: there is nothing to close")
