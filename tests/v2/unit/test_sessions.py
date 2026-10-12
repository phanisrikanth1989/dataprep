"""The database sessions of a run: who ends a transaction, and when. On a real database (SQLite)."""
import pytest

from src.v2.errors import DatabaseError
from src.v2.sessions import Session, Sessions, Unstored
from tests.v2.database import SqliteSession, database, stored

ROWS = "select n from t order by n"


@pytest.fixture
def path(tmp_path):
    return database(tmp_path, "t(n)")


def worked(sessions, session, component_id, value):
    """A component changes something through a session, having said so first."""
    sessions.working(session, component_id)
    session.run("insert into t values (:n)", {"n": value})


class Broken(Session):
    """A session whose database says no where it is told to: for what a real one does only when it breaks."""

    def __init__(self, opened_by, fails=(), dead=False, **more):
        super().__init__(opened_by, f"session of '{opened_by}'", **more)
        self.fails, self.dead, self.did, self.busy = set(fails), dead, [], False

    def _do(self, what):
        self.did.append(what)
        if what.split()[0] in self.fails:
            raise DatabaseError(f"the database refused the {what.split()[0]}")

    def run(self, statement, binds=None):
        self._do("run")
        self.busy = True
        return 1

    def commit(self):
        self._do("commit")
        self.busy = False

    def rollback(self):
        self._do("rollback")
        self.busy = False

    def savepoint(self, name):
        self._do(f"savepoint {name}")

    def rollback_to(self, name):
        self._do(f"rollback_to {name}")

    def in_transaction(self):
        return self.busy

    def alive(self):
        return not self.dead

    def close(self):
        self._do("close")


# ------------------------------------------------------------------
# A session a component opened for itself
# ------------------------------------------------------------------

def test_a_session_of_a_components_own_is_stored_when_the_subjob_has_succeeded(path):
    sessions = Sessions()
    session = sessions.own(SqliteSession(path, "out"))
    worked(sessions, session, "out", 1)
    assert stored(path, ROWS) == []

    assert sessions.subjob_succeeded() == ["out"]

    assert stored(path, ROWS) == [(1,)]
    assert session.closed


def test_a_session_of_a_components_own_is_rolled_back_when_the_subjob_has_failed(path):
    sessions = Sessions()
    session = sessions.own(SqliteSession(path, "out"))
    worked(sessions, session, "out", 1)

    sessions.subjob_failed()

    assert stored(path, ROWS) == []
    assert session.did[-2:] == ["rollback", "close"]
    # Nothing of it is left for the next subjob to end.
    assert sessions.subjob_succeeded() == []


def test_sessions_of_their_own_are_stored_in_the_order_they_were_opened(path):
    sessions, did = Sessions(), []
    for name in ("first", "second"):
        session = sessions.own(Broken(name))
        session.did = did
        sessions.working(session, name)
    assert sessions.subjob_succeeded() == ["first", "second"]
    assert did == ["commit", "close", "commit", "close"]


def test_a_commit_that_fails_names_its_component_and_what_was_stored_before_it(path):
    sessions = Sessions()
    first, second, third = (sessions.own(Broken(name, fails)) for name, fails in
                            (("a", ()), ("b", ("commit",)), ("c", ())))
    for session in (first, second, third):
        sessions.working(session, session.opened_by)
        session.run("x")

    with pytest.raises(Unstored) as failed:
        sessions.subjob_succeeded()

    assert failed.value.component_id == "b"
    assert str(failed.value) == ("what it did could not be stored: the database refused the commit; "
                                 "what a did is stored already")
    # The failed one and the one after it are still the subjob's to take back.
    sessions.subjob_failed()
    assert second.did[-2:] == ["rollback", "close"]
    assert third.did == ["run", "rollback", "close"]
    assert first.did == ["run", "commit", "close"]


def test_a_session_the_database_has_closed_is_not_asked_to_roll_back(path):
    sessions = Sessions()
    session = sessions.own(Broken("out", dead=True))
    sessions.working(session, "out")
    sessions.subjob_failed()
    assert session.did == ["close"]


def test_a_rollback_that_fails_does_not_stop_the_others_from_being_taken_back(path):
    sessions = Sessions()
    first, second = sessions.own(Broken("a", ("rollback",))), sessions.own(Broken("b"))
    sessions.subjob_failed()
    assert first.did == ["rollback", "close"]
    assert second.did == ["rollback", "close"]


# ------------------------------------------------------------------
# A shared session
# ------------------------------------------------------------------

def test_a_shared_session_is_found_by_the_id_of_the_component_that_opened_it(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    assert sessions.shared("conn") is session
    assert session.shared


def test_a_session_nobody_opened_is_said_by_its_id(path):
    with pytest.raises(DatabaseError) as failed:
        Sessions().shared("tDBConnection_1")
    assert str(failed.value) == ("'tDBConnection_1' has no open session: it has not run, or its session was closed")


def test_work_on_a_shared_session_waits_for_a_commit(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "out", 1)

    assert sessions.subjob_succeeded() == []
    assert stored(path, ROWS) == []
    assert session.pending == ["out"]

    sessions.commit("conn")
    assert stored(path, ROWS) == [(1,)]
    assert session.pending == []
    assert not session.closed


def test_a_commit_may_close_the_session(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "out", 1)
    sessions.commit("conn", close=True)
    assert stored(path, ROWS) == [(1,)]
    assert session.closed
    with pytest.raises(DatabaseError):
        sessions.shared("conn")


def test_a_rollback_takes_back_everything_that_waits(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "out", 1)
    sessions.subjob_succeeded()
    worked(sessions, session, "more", 2)

    sessions.rollback("conn")

    assert session.pending == []
    assert not session.closed
    sessions.commit("conn")
    assert stored(path, ROWS) == []


def test_a_rollback_may_close_the_session(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "out", 1)
    sessions.rollback("conn", close=True)
    assert session.did[-2:] == ["rollback", "close"]
    with pytest.raises(DatabaseError):
        sessions.shared("conn")


def test_a_place_is_marked_again_after_a_commit_in_the_middle_of_a_subjob(path):
    """What follows a commit in the same subjob is taken back by a failure; what the commit stored is not."""
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "a", 1)
    sessions.commit("conn")
    worked(sessions, session, "b", 2)
    sessions.subjob_failed()
    assert session.pending == []
    sessions.commit("conn")
    assert stored(path, ROWS) == [(1,)]


def test_a_subjob_that_fails_on_a_shared_session_loses_its_own_work_and_no_other(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "first", 1)
    sessions.subjob_succeeded()

    worked(sessions, session, "second", 2)
    worked(sessions, session, "third", 3)
    sessions.subjob_failed()

    assert session.pending == ["first"]
    sessions.commit("conn")
    assert stored(path, ROWS) == [(1,)]


def test_the_place_to_go_back_to_is_marked_once_for_a_subjob_and_again_for_the_next(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "a", 1)
    worked(sessions, session, "b", 2)
    sessions.subjob_succeeded()
    worked(sessions, session, "c", 3)
    assert [did for did in session.did if did.startswith("savepoint")] == ["savepoint v2_subjob"] * 2


def test_a_component_that_works_again_in_a_later_pass_keeps_its_earlier_work_when_that_pass_fails(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "out", 1)
    sessions.subjob_succeeded()
    worked(sessions, session, "out", 2)
    sessions.subjob_failed()
    assert session.pending == ["out"]
    sessions.commit("conn")
    assert stored(path, ROWS) == [(1,)]


def test_a_shared_session_that_commits_by_itself_is_stored_after_each_subjob_that_worked_on_it(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn", auto_commit=True)
    sessions.share(session)
    worked(sessions, session, "out", 1)
    assert sessions.subjob_succeeded() == ["out"]
    assert stored(path, ROWS) == [(1,)]
    assert session.pending == []
    # A subjob that did nothing on it costs it nothing.
    before = list(session.did)
    assert sessions.subjob_succeeded() == []
    assert session.did == before


def test_a_shared_session_the_database_closed_is_let_go_when_a_subjob_fails_on_it(path, caplog):
    sessions = Sessions()
    session = Broken("conn")
    sessions.share(session)
    sessions.working(session, "out")
    session.dead = True
    with caplog.at_level("ERROR", logger="src.v2"):
        sessions.subjob_failed()
    assert session.did == ["savepoint v2_subjob", "close"]
    assert "[conn] the database has closed its session: what out did on it is lost" in caplog.text
    with pytest.raises(DatabaseError):
        sessions.shared("conn")


def test_work_that_cannot_be_taken_back_is_said_and_stops_nothing(path, caplog):
    sessions = Sessions()
    session = Broken("conn", fails=("rollback_to",))
    sessions.share(session)
    sessions.working(session, "out")
    session.run("x")
    with caplog.at_level("ERROR", logger="src.v2"):
        sessions.subjob_failed()
    assert ("[conn] what out did before its subjob failed could not be taken back: "
            "the database refused the rollback_to") in caplog.text
    # It may be there still: it is kept as waiting, so that the end of the job does not pass over it.
    assert session.pending == ["out"]


def test_a_component_may_take_back_the_word_that_it_changed_something(path):
    """Its statement changed no row. The place marked for it is an open transaction to the database all the same."""
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    sessions.working(session, "reads")
    session.run("select n from t")
    sessions.changed_nothing(session, "reads")
    assert session.in_transaction() and session.pending == [] and session.in_subjob == []
    sessions.subjob_succeeded()
    assert sessions.close("conn") is True


def test_taking_the_word_back_leaves_what_others_did_and_what_the_same_component_did_before(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "out", 1)
    sessions.working(session, "reads")
    sessions.changed_nothing(session, "reads")
    assert session.pending == ["out"] and session.in_subjob == ["out"]
    sessions.subjob_succeeded()
    # In a later subjob the one that did store-worthy work says it changed nothing this time: its earlier work waits.
    sessions.working(session, "out")
    sessions.changed_nothing(session, "out")
    assert session.pending == ["out"] and session.in_subjob == []
    sessions.changed_nothing(session, "never worked")
    assert session.pending == ["out"]


# ------------------------------------------------------------------
# Opening a shared session again
# ------------------------------------------------------------------

def test_a_session_opened_again_replaces_one_with_nothing_waiting(path):
    sessions = Sessions()
    earlier, later = SqliteSession(path, "conn"), SqliteSession(path, "conn")
    sessions.share(earlier)
    sessions.share(later)
    assert earlier.closed
    assert sessions.shared("conn") is later


def test_a_session_is_not_opened_again_over_work_that_waits(path):
    sessions = Sessions()
    earlier, later = SqliteSession(path, "conn"), SqliteSession(path, "conn")
    sessions.share(earlier)
    worked(sessions, earlier, "out", 1)
    sessions.subjob_succeeded()
    with pytest.raises(DatabaseError) as failed:
        sessions.share(later)
    assert str(failed.value) == ("the session it opened before is still open, and what out did on it was never "
                                 "stored: commit it or roll it back before the session is opened again")
    assert later.closed
    assert sessions.shared("conn") is earlier


# ------------------------------------------------------------------
# Closing
# ------------------------------------------------------------------

def test_closing_with_nothing_waiting_closes(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    assert sessions.close("conn") is True
    assert session.closed


def test_closing_what_is_not_open_is_no_fault(path):
    assert Sessions().close("conn") is False


def test_closing_with_work_waiting_fails_and_rolls_back(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "tDBOutput_1", 1)
    worked(sessions, session, "tDBRow_1", 2)
    sessions.subjob_succeeded()

    with pytest.raises(DatabaseError) as failed:
        sessions.close("conn")

    assert str(failed.value) == (
        "what tDBOutput_1 and tDBRow_1 did on the session of 'conn' was never stored, and is rolled back: put a "
        "commit before the close, or say with `uncommitted` what a close does with such work (`commit` or `rollback`)"
    )
    assert stored(path, ROWS) == []
    # Said, and not left to what a driver does with a session that is closed over work: Talend's stores it.
    assert session.did[-2:] == ["rollback", "close"]


def test_work_on_a_session_the_database_closed_does_not_wait(path):
    """It is lost. A close has nothing to fail on, and a session that is dead is asked nothing about its work."""
    sessions = Sessions()
    session = Broken("conn")
    sessions.share(session)
    sessions.working(session, "out")
    session.run("x")
    sessions.subjob_succeeded()
    session.dead = True
    assert sessions.close("conn") is True
    assert session.did[-1] == "close" and "rollback" not in session.did


@pytest.mark.parametrize("uncommitted, left", [("commit", [(1,)]), ("rollback", [])])
def test_a_close_may_say_what_becomes_of_work_that_waits(path, uncommitted, left):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "out", 1)
    sessions.subjob_succeeded()
    assert sessions.close("conn", uncommitted) is True
    assert stored(path, ROWS) == left
    assert session.closed


def test_work_the_database_stored_by_itself_does_not_wait(path):
    """A statement that commits (DDL in Oracle) leaves nothing pending, whatever the engine noted."""
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "out", 1)
    session.commit()
    assert sessions.close("conn") is True
    assert stored(path, ROWS) == [(1,)]


# ------------------------------------------------------------------
# A commit or a rollback that waits for the subjob to succeed
# ------------------------------------------------------------------

def test_a_commit_that_waits_is_made_when_the_subjob_has_succeeded(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "out", 1)
    sessions.when_done("conn", "commit", True, "tDBCommit_1")
    assert stored(path, ROWS) == []
    assert sessions.subjob_succeeded() == ["out"]
    assert stored(path, ROWS) == [(1,)]
    assert session.closed


def test_a_rollback_that_waits_is_made_when_the_subjob_has_succeeded(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "out", 1)
    sessions.when_done("conn", "rollback", False, "tDBRollback_1")
    assert sessions.subjob_succeeded() == []
    sessions.commit("conn")
    assert stored(path, ROWS) == []
    assert not session.closed


def test_a_commit_that_waits_is_not_made_when_the_subjob_has_failed(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "out", 1)
    sessions.when_done("conn", "commit", True, "tDBCommit_1")
    sessions.subjob_failed()
    assert sessions.subjob_succeeded() == []
    assert stored(path, ROWS) == []
    assert not session.closed


def test_a_commit_that_waits_and_fails_is_its_components_failure(path):
    sessions = Sessions()
    sessions.share(Broken("conn", fails=("commit",)))
    sessions.when_done("conn", "commit", False, "tDBCommit_1")
    with pytest.raises(Unstored) as failed:
        sessions.subjob_succeeded()
    assert failed.value.component_id == "tDBCommit_1"
    assert str(failed.value) == "the database refused the commit"


# ------------------------------------------------------------------
# The end of the job
# ------------------------------------------------------------------

def test_a_job_that_ends_with_work_waiting_has_it_rolled_back_and_is_told(path):
    sessions = Sessions()
    session = SqliteSession(path, "tDBConnection_1")
    sessions.share(session)
    worked(sessions, session, "tDBOutput_1", 1)
    sessions.subjob_succeeded()

    assert sessions.job_ends() == [(
        "tDBConnection_1",
        "the job ended with work that was never stored: what tDBOutput_1 did on the session of 'tDBConnection_1' "
        "is rolled back, since no commit followed it",
    )]
    assert stored(path, ROWS) == []
    assert session.did[-2:] == ["rollback", "close"]


def test_a_job_that_ends_with_nothing_waiting_closes_its_sessions_and_says_nothing(path):
    sessions = Sessions()
    session = SqliteSession(path, "conn")
    sessions.share(session)
    worked(sessions, session, "out", 1)
    sessions.commit("conn")
    assert sessions.job_ends() == []
    assert session.closed
    # Asked again, there is nothing left to end.
    assert sessions.job_ends() == []


def test_the_end_of_the_job_goes_through_every_session_whatever_one_of_them_does(path):
    sessions = Sessions()
    broken, fine = Broken("a", fails=("rollback", "close")), Broken("b")
    sessions.share(broken)
    sessions.share(fine)
    sessions.working(broken, "out")
    broken.run("x")
    sessions.subjob_succeeded()
    told = sessions.job_ends()
    assert [component_id for component_id, _ in told] == ["a"]
    assert fine.did == ["close"]


def test_a_session_that_commits_by_itself_and_cannot_fails_the_component_that_worked_on_it(path):
    sessions = Sessions()
    session = Broken("conn", fails=("commit",), auto_commit=True)
    sessions.share(session)
    sessions.working(session, "out")
    with pytest.raises(Unstored) as failed:
        sessions.subjob_succeeded()
    assert failed.value.component_id == "out"
    assert str(failed.value) == "what it did could not be stored: the database refused the commit"


def test_a_session_of_a_components_own_that_the_job_ends_on_is_rolled_back_and_closed(path):
    """A run that is stopped before its subjob is told to have failed leaves no session open."""
    sessions = Sessions()
    session = sessions.own(SqliteSession(path, "out"))
    worked(sessions, session, "out", 1)
    assert sessions.job_ends() == []
    assert session.did[-2:] == ["rollback", "close"]
    assert stored(path, ROWS) == []


# ------------------------------------------------------------------
# What a query hands back, and what the job declares
# ------------------------------------------------------------------

from src.v2.errors import ConfigurationError  # noqa: E402
from src.v2.job.model import Column  # noqa: E402
from src.v2.sessions import DATE, NUMBER, OTHER, TEXT, ZONED, Field, taken  # noqa: E402

ADVICE = {ZONED: "say which clock is meant", OTHER: "turn it into text"}


def declared(*types):
    return [Column(name=f"c{at}", type=kind) for at, kind in enumerate(types, start=1)]


def handed(*families):
    said = {NUMBER: "NUMBER", TEXT: "VARCHAR", DATE: "DATE", ZONED: "TIMESTAMP_TZ", OTHER: "a BLOB"}
    return [Field(f"C{at}", family, said[family]) for at, family in enumerate(families, start=1)]


@pytest.mark.parametrize("kind", ["int", "float", "Decimal", "bool", "str"])
def test_a_number_is_any_number_or_text_and_the_database_makes_it_so(kind):
    assert taken(declared(kind), handed(NUMBER), ADVICE) == [False]


@pytest.mark.parametrize("kind", ["datetime", "date", "str"])
def test_a_date_is_a_date_or_text_and_the_database_makes_it_so(kind):
    assert taken(declared(kind), handed(DATE), ADVICE) == [False]


def test_text_that_is_declared_as_anything_else_is_read_by_the_engine_as_a_files_text_is():
    kinds = ("str", "int", "float", "Decimal", "bool", "datetime", "date")
    assert taken(declared(*kinds), handed(*[TEXT] * 7), ADVICE) == [False, True, True, True, True, True, True]


def test_a_date_with_a_time_zone_is_text_only():
    assert taken(declared("str"), handed(ZONED), ADVICE) == [False]


def test_what_does_not_go_together_names_every_column_and_says_what_to_do():
    with pytest.raises(ConfigurationError) as failed:
        taken(declared("datetime", "int", "datetime", "str", "date", "Decimal", "str"),
              handed(NUMBER, DATE, ZONED, OTHER, NUMBER, DATE, TEXT), ADVICE)
    assert str(failed.value) == (
        "column 'c1': the query hands back a number (NUMBER), and the job declares a datetime; "
        "column 'c2': the query hands back a date (DATE), and the job declares a whole number; "
        "column 'c3': the query hands back a date with a time zone (TIMESTAMP_TZ), and a datetime has none: say which "
        "clock is meant; "
        "column 'c4': the query hands back a BLOB, which v2 does not read: turn it into text; "
        "column 'c5': the query hands back a number (NUMBER), and the job declares a date; "
        "column 'c6': the query hands back a date (DATE), and the job declares a Decimal"
    )


@pytest.mark.parametrize("kind", ["int", "float", "Decimal", "bool", "date"])
def test_a_date_with_a_time_zone_is_nothing_but_text(kind):
    with pytest.raises(ConfigurationError, match="a date with a time zone"):
        taken(declared(kind), handed(ZONED), ADVICE)


def test_as_many_columns_as_are_declared():
    with pytest.raises(ConfigurationError) as failed:
        taken(declared("int", "str"), handed(NUMBER), ADVICE)
    assert str(failed.value) == ("the query hands back 1 column(s) and the job declares 2: they are taken by their "
                                 "place, so there have to be as many")
    with pytest.raises(ConfigurationError, match="hands back 2 column"):
        taken(declared("int"), handed(NUMBER, TEXT), ADVICE)
