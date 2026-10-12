"""What the engine tells the sessions of a run, and when: on a real database (SQLite), with stand-in components."""
import os

import polars as pl
import pytest

from src.v2.components.base import Action, Sink, Transform, Write
from src.v2.components.registry import Registry
from src.v2.engine import load_job, run_job
from src.v2.engine.runner import Runner
from src.v2.errors import ConfigurationError
from src.v2.job.keys import CODE, Key
from tests.v2.database import SqliteSession, database, stored
from tests.v2.unit import kit
from tests.v2.unit.test_sessions import Broken

ROWS = "select n from t order by n"
HELD = {}


class Opens(Action):
    """Opens a session for others to work on."""

    names = ("opens",)
    keys = (Key("path", default=""), Key("auto_commit", type=bool, default=False), Key("broken", type=list, default=[]))

    def act(self):
        if self.config["broken"]:
            session = Broken(self.id, fails=self.config["broken"])
        else:
            session = SqliteSession(self.config["path"], self.id, auto_commit=self.config["auto_commit"])
        HELD[self.id] = session
        self.run_context.sessions.share(session)


class Does(Action):
    """Runs a statement: on the session of `connection`, or on one it opens for itself."""

    names = ("does",)
    keys = (Key("path", default=""), Key("connection", default=""), Key("statement", type=CODE, required=True),
            Key("then", default=""))

    def act(self):
        sessions, config = self.run_context.sessions, self.config
        if config["connection"]:
            session = sessions.shared(config["connection"])
        else:
            session = HELD[self.id] = sessions.own(SqliteSession(config["path"], self.id))
        sessions.working(session, self.id)
        session.run(config["statement"])
        if config["then"] == "fails":
            raise ConfigurationError("it failed after its work")
        if config["then"] == "is stopped":
            raise KeyboardInterrupt()
        if config["then"] == "breaks":
            raise RuntimeError("the engine broke")


class Commits(Action):
    names = ("commits",)
    keys = (Key("connection", required=True),)

    def act(self):
        self.run_context.sessions.commit(self.config["connection"])


class CommitsWhenDone(Transform):
    """Hands its rows on, and has the session committed when the subjob has succeeded."""

    names = ("commits_when_done",)
    keys = (Key("connection", required=True),)

    def build(self, inputs):
        self.run_context.sessions.when_done(self.config["connection"], "commit", False, self.id)
        return {"main": next(iter(inputs.values()))}


class Unplaceable(Sink):
    """A file that is written and made ready, and cannot be put in place."""

    names = ("unplaceable",)
    keys = (Key("path", required=True),)

    def write(self, frame):
        def place(temp, rows):
            os.remove(temp)
            raise OSError(28, "No space left on device", self.config["path"])

        return Write(path=self.config["path"], sink=lambda path: frame.sink_csv(path, lazy=True), place=place)


REGISTRY = Registry()
for _cls in (kit.Rows, kit.Save, kit.Guard, Opens, Does, Commits, CommitsWhenDone, Unplaceable):
    REGISTRY.register(_cls)


@pytest.fixture
def path(tmp_path):
    HELD.clear()
    return database(tmp_path, "t(n)")


def run(components, flows=(), triggers=()):
    made = kit.job(components, flows)
    made["triggers"] = [{"type": kind, "from": source, "to": target} for kind, source, target in triggers]
    return run_job(made, registry=REGISTRY)


def insert(value):
    return f"insert into t values ({value})"


# ------------------------------------------------------------------
# A session of a component's own
# ------------------------------------------------------------------

def test_what_a_component_did_on_its_own_session_is_stored_when_its_subjob_has_succeeded(path):
    result = run([("d", "does", {"path": path, "statement": insert(1)})])
    assert result.status == "success"
    assert stored(path, ROWS) == [(1,)]
    assert HELD["d"].did[-2:] == ["commit", "close"]


def test_what_a_component_did_before_it_failed_is_rolled_back(path):
    result = run([("d", "does", {"path": path, "statement": insert(1), "then": "fails"})])
    assert (result.status, result.failed_component, result.error) == ("failed", "d", "it failed after its work")
    assert stored(path, ROWS) == []
    assert HELD["d"].did[-2:] == ["rollback", "close"]


def test_a_run_that_is_stopped_leaves_nothing_half_stored(path):
    with pytest.raises(KeyboardInterrupt):
        run([("d", "does", {"path": path, "statement": insert(1), "then": "is stopped"})])
    assert stored(path, ROWS) == []
    assert HELD["d"].did[-2:] == ["rollback", "close"]


# ------------------------------------------------------------------
# A shared session
# ------------------------------------------------------------------

def shared(path, *more, **opens):
    return [("conn", "opens", {"path": path, **opens}),
            ("d1", "does", {"connection": "conn", "statement": insert(1)}), *more]


def test_work_on_a_shared_session_is_stored_by_a_commit(path):
    result = run(shared(path, ("c", "commits", {"connection": "conn"})),
                 triggers=[("OnSubjobOk", "conn", "d1"), ("OnSubjobOk", "d1", "c")])
    assert result.status == "success"
    assert stored(path, ROWS) == [(1,)]
    # The job closes what it opened.
    assert HELD["conn"].closed


def test_a_job_that_ends_with_work_nothing_stored_has_failed(path, caplog):
    with caplog.at_level("ERROR", logger="src.v2"):
        result = run(shared(path), triggers=[("OnSubjobOk", "conn", "d1")])
    said = ("the job ended with work that was never stored: what d1 did on the session of 'conn' is rolled back, "
            "since no commit followed it")
    assert (result.status, result.failed_component, result.error) == ("failed", "conn", said)
    assert result.failures == {"conn": said}
    assert f"[t] failed at conn: {said}" in caplog.text
    assert stored(path, ROWS) == []
    assert HELD["conn"].closed


def test_a_subjob_that_fails_on_a_shared_session_loses_its_work_and_the_one_before_keeps_its_own(path):
    result = run(
        shared(path, ("d2", "does", {"connection": "conn", "statement": insert(2), "then": "fails"}),
               ("c", "commits", {"connection": "conn"})),
        triggers=[("OnSubjobOk", "conn", "d1"), ("OnSubjobOk", "d1", "d2"), ("OnSubjobError", "d2", "c")],
    )
    assert (result.status, result.failed_component) == ("failed", "d2")
    # Nothing waited when the job ended: that failure is the only one.
    assert list(result.failures) == ["d2"]
    assert stored(path, ROWS) == [(1,)]


def test_a_shared_session_that_commits_by_itself_needs_no_commit_component(path):
    result = run(shared(path, auto_commit=True), triggers=[("OnSubjobOk", "conn", "d1")])
    assert result.status == "success"
    assert stored(path, ROWS) == [(1,)]


def test_the_sessions_are_closed_when_the_engine_itself_breaks(path):
    """A fault no component answers for goes through the run; what the run opened is closed on its way."""
    made = kit.job(shared(path), [])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "conn", "to": "d1"}]
    runner = Runner(load_job(made, registry=REGISTRY))

    def broken(*args, **kwargs):
        raise RuntimeError("the engine broke")

    runner._fired = broken
    with pytest.raises(RuntimeError):
        runner.run()
    assert HELD["conn"].closed


# ------------------------------------------------------------------
# A commit that waits for the subjob, and the files of that subjob
# ------------------------------------------------------------------

def flowing(path, tmp_path, sink="save", **opens):
    out = str(tmp_path / "out.csv")
    components = [
        ("conn", "opens", {"path": path, **opens}),
        ("d1", "does", {"connection": "conn", "statement": insert(1)}),
        ("rows", "rows", {"data": {"n": [1, 2]}}),
        ("c", "commits_when_done", {"connection": "conn"}),
        ("out", sink, {"path": out}),
    ]
    flows = [("r1", "rows", "c", "flow"), ("r2", "c", "out", "flow")]
    triggers = [("OnSubjobOk", "conn", "d1"), ("OnSubjobOk", "d1", "rows")]
    return out, components, flows, triggers


def test_a_commit_that_stands_in_a_flow_is_made_when_its_subjob_has_succeeded(path, tmp_path):
    out, *made = flowing(path, tmp_path)
    result = run(*made)
    assert result.status == "success"
    assert stored(path, ROWS) == [(1,)]
    assert kit.lines(out) == ["n", "1", "2"]


def test_a_commit_is_made_before_any_file_is_put_in_place(path, tmp_path):
    out, *made = flowing(path, tmp_path, broken=["commit"])
    result = run(*made)
    assert (result.status, result.failed_component, result.error) == ("failed", "c", "the database refused the commit")
    # The file was written and made ready, and is not there: the commit came first and failed.
    assert not os.path.exists(out)
    assert os.listdir(tmp_path) == ["db.sqlite"]


def test_a_file_that_cannot_be_put_in_place_after_a_commit_says_what_is_stored(path, tmp_path):
    out, *made = flowing(path, tmp_path, sink="unplaceable")
    result = run(*made)
    assert (result.status, result.failed_component) == ("failed", "out")
    assert result.error == (f"[Errno 28] No space left on device: '{out}'; what d1 did in the database is stored, "
                            "and stays stored")
    assert stored(path, ROWS) == [(1,)]


def test_a_subjob_whose_rows_fail_a_check_commits_nothing(path, tmp_path):
    out, components, flows, triggers = flowing(path, tmp_path)
    components[2] = ("rows", "rows", {"data": {"n": [1, -2]}})
    components.insert(4, ("g", "guard", {}))
    flows = [("r1", "rows", "c", "flow"), ("r2", "c", "g", "flow"), ("r3", "g", "out", "flow")]
    result = run(components, flows, triggers)
    assert (result.failed_component, result.failures["g"]) == ("g", "1 negative value(s)")
    assert stored(path, ROWS) == []
    assert not os.path.exists(out)
    # The commit did not happen, so the work still waited when the job ended, and that is said as well.
    assert list(result.failures) == ["g", "conn"]


# ------------------------------------------------------------------
# A write that is no file: rows that rest in a scratch file and are stored when the subjob has succeeded
# ------------------------------------------------------------------

class Stores(Sink):
    """Stores its rows in the table `t`: all, or all but those with a negative n when it is told to refuse them."""

    names = ("stores",)
    keys = (Key("path", required=True), Key("refuses", type=bool, default=False), Key("fails", type=bool, default=False))
    seen = []

    def write(self, frame):
        scratch = self.run_context.temp_path(".csv")

        def ready(temp, rows):
            Stores.seen.append(("ready", self.id, temp, rows, os.path.exists(temp) and temp == scratch))
            if self.config["fails"]:
                raise ConfigurationError("the table would not take the rows")
            sessions = self.run_context.sessions
            session = HELD[self.id] = sessions.own(SqliteSession(self.config["path"], self.id))
            sessions.working(session, self.id)
            kept = 0
            for n in pl.read_csv(temp)["n"].to_list():
                if n < 0 and self.config["refuses"]:
                    continue
                session.run(insert(n))
                kept += 1
            return kept

        return Write(path="table t", scratch=scratch, sink=lambda path: frame.sink_csv(path, lazy=True), ready=ready)


REGISTRY.register(Stores)


def storing(path, tmp_path, data=(1, 2), sink="save", **stores):
    out = str(tmp_path / "out.csv")
    components = [("rows", "rows", {"data": {"n": list(data)}}), ("db", "stores", {"path": path, **stores}),
                  ("out", sink, {"path": out})]
    return out, components, [("r1", "rows", "db", "flow"), ("r2", "rows", "out", "flow")]


def test_rows_for_a_table_rest_in_a_scratch_file_and_are_stored_when_the_subjob_has_succeeded(path, tmp_path, caplog,
                                                                                               monkeypatch):
    Stores.seen.clear()
    # Nothing is written or moved where the job runs: `table t` names a table, and no file.
    monkeypatch.chdir(tmp_path)
    out, *made = storing(path, tmp_path)
    with caplog.at_level("INFO", logger="src.v2"):
        result = run(*made)
    assert result.status == "success", result.error
    assert stored(path, ROWS) == [(1,), (2,)]
    (_, _, temp, rows, there), = Stores.seen
    # The scratch file is the run's own, and no file beside a target; it is gone when the subjob is over.
    assert (rows, there) == (2, True) and os.path.dirname(temp) != str(tmp_path) and not os.path.exists(temp)
    assert sorted(os.listdir(tmp_path)) == ["db.sqlite", "out.csv"]
    assert result.rows == {"db": 2, "out": 2}
    assert "[db] stored 2 row(s) in table t" in caplog.text
    assert HELD["db"].did[-2:] == ["commit", "close"]


def test_rows_a_table_did_not_take_are_counted_apart(path, tmp_path, caplog):
    out, components, flows = storing(path, tmp_path, data=(1, -2, 3, -4), refuses=True)
    components.append(("after", "does", {"path": path, "statement": "insert into t values (0)"}))
    made = kit.job(components, flows)
    made["triggers"] = [{"type": "RunIf", "from": "db", "to": "after",
                         "condition": '((Integer)globalMap.get("db_NB_LINE_REJECT")) == 2 and '
                                      '((Integer)globalMap.get("db_NB_LINE_OK")) == 2 and '
                                      '((Integer)globalMap.get("db_NB_LINE")) == 4'}]
    with caplog.at_level("INFO", logger="src.v2"):
        result = run_job(made, registry=REGISTRY)
    assert result.status == "success", result.error
    assert stored(path, ROWS) == [(0,), (1,), (3,)]
    assert result.rows["db"] == 2
    assert "[db] stored 2 row(s) in table t (2 of the 4 it was handed were turned away)" in caplog.text


def test_files_are_made_ready_before_a_table_is_touched(path, tmp_path):
    """What can fail cheaply fails first: a file that cannot be made ready costs no load."""
    Stores.seen.clear()

    class Unready(Sink):
        names = ("unready",)
        keys = (Key("path", required=True),)

        def write(self, frame):
            def ready(temp, rows):
                Stores.seen.append(("file ready",))
                raise ConfigurationError("the file's encoding cannot hold a character")
            return Write(path=self.config["path"], sink=lambda path: frame.sink_csv(path, lazy=True), ready=ready)

    registry = Registry()
    for cls in (*REGISTRY.classes(), Unready):
        registry.register(cls)
    out, components, flows = storing(path, tmp_path, sink="unready")
    result = run_job(kit.job(components, flows), registry=registry)
    assert (result.status, result.failed_component) == ("failed", "out")
    # The table's component stands before the file's, and was not asked.
    assert Stores.seen == [("file ready",)]
    assert stored(path, ROWS) == []


def test_a_load_that_fails_stores_nothing_and_puts_no_file_in_place(path, tmp_path):
    out, *made = storing(path, tmp_path, fails=True)
    result = run(*made)
    assert (result.status, result.failed_component, result.error) == ("failed", "db", "the table would not take the rows")
    assert stored(path, ROWS) == [] and not os.path.exists(out)


def test_a_file_that_cannot_be_put_in_place_after_the_rows_are_stored_says_so(path, tmp_path):
    out, *made = storing(path, tmp_path, sink="unplaceable")
    result = run(*made)
    assert (result.status, result.failed_component) == ("failed", "out")
    assert result.error.endswith("what db did in the database is stored, and stays stored")
    assert stored(path, ROWS) == [(1,), (2,)]
