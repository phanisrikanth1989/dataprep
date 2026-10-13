"""Oracle commit, rollback and close: what ends a shared session's work, and the session."""
import logging

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, reader, writer
from tests.v2.components.test_oracle_connection import after, connection, does
from tests.v2.database import WITH_DOES, on_sqlite  # noqa: F401 -- a fixture

CONN = "tDBConnection_1"


def ends(kind, component_id="e", inputs=(), outputs=(), **config):
    schema = {"input": columns("n:int") if inputs else [], "output": columns("n:int") if outputs else []}
    return {"id": component_id, "type": kind, "config": {"connection": CONN, **config}, "schema": schema,
            "inputs": list(inputs), "outputs": list(outputs)}


def run(components, triggers=(), flows=(), **more):
    return run_job(job(components, list(flows), triggers=list(triggers), **more), registry=WITH_DOES)


def refusals(components, flows=()):
    with pytest.raises(JobRefusedError) as refused:
        load_job(job(components, list(flows)), registry=WITH_DOES)
    return [f"{refusal.where} / {refusal.key}: {refusal.reason}" for refusal in refused.value.report]


def worked(*then, triggers=None):
    """connection -> a component that inserts 1 -> what follows, each set off by the one before."""
    components = [connection(), does(1), *then]
    return components, triggers if triggers is not None else after(*(component["id"] for component in components))


# ------------------------------------------------------------------
# Commit
# ------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["oracle_commit", "OracleCommit", "tOracleCommit"])
def test_a_commit_stores_what_was_done_and_closes_the_session(on_sqlite, kind, caplog):
    with caplog.at_level(logging.INFO, logger="src.v2"):
        result = run(*worked(ends(kind)))
    assert result.status == "success"
    assert on_sqlite.stored() == [(1,)]
    assert on_sqlite.sessions[0].did[-2:] == ["commit", "close"]
    assert f"[e] committed the session of '{CONN}' (the work of d) and closed it" in caplog.text


def test_a_commit_may_leave_the_session_open_for_more(on_sqlite, caplog):
    more = does(2, component_id="d2")
    with caplog.at_level(logging.INFO, logger="src.v2"):
        result = run(*worked(ends("tOracleCommit", close=False), more, ends("tOracleCommit", component_id="e2")))
    assert result.status == "success"
    assert on_sqlite.stored() == [(1,), (2,)]
    assert len(on_sqlite.sessions) == 1
    assert f"[e] committed the session of '{CONN}' (the work of d)\n" in caplog.text + "\n"


def test_a_commit_with_nothing_to_store_says_so(on_sqlite, caplog):
    with caplog.at_level(logging.INFO, logger="src.v2"):
        result = run([connection(), ends("tOracleCommit")], after(CONN, "e"))
    assert result.status == "success"
    assert f"[e] committed the session of '{CONN}' (nothing waited on it) and closed it" in caplog.text


def test_a_commit_of_a_session_that_is_not_open_fails(on_sqlite):
    components, triggers = worked(ends("tOracleCommit"), ends("tOracleCommit", component_id="again"))
    result = run(components, triggers)
    assert (result.status, result.failed_component) == ("failed", "again")
    assert result.error == f"'{CONN}' has no open session: it has not run, or its session was closed"


def test_a_commit_in_a_flow_is_made_when_a_row_reached_it_and_the_subjob_has_succeeded(on_sqlite, tmp_path):
    (tmp_path / "in.csv").write_text("1\n2\n")
    components = [connection(), does(1), reader("n:int", path=str(tmp_path / "in.csv")),
                  ends("tOracleCommit", inputs=("row1",), outputs=("row2",)),
                  writer("n:int", path=str(tmp_path / "out.csv"))]
    result = run(components, after(CONN, "d", "in"), [flow("row1", "in", "e"), flow("row2", "e", "out")])
    assert result.status == "success"
    assert on_sqlite.stored() == [(1,)]
    # The rows go on as they came.
    assert (tmp_path / "out.csv").read_text() == "n\n1\n2\n"
    assert on_sqlite.sessions[0].did[-2:] == ["commit", "close"]


def test_a_commit_in_a_flow_is_not_made_when_no_row_reached_it(on_sqlite, tmp_path, caplog):
    (tmp_path / "in.csv").write_text("")
    components = [connection(), does(1), reader("n:int", path=str(tmp_path / "in.csv")),
                  ends("tOracleCommit", inputs=("row1",))]
    with caplog.at_level(logging.INFO, logger="src.v2"):
        result = run(components, after(CONN, "d", "in"), [flow("row1", "in", "e")])
    assert on_sqlite.stored() == []
    assert f"[e] no row reached it: the session of '{CONN}' is left as it is" in caplog.text
    # So the work still waited when the job ended.
    assert (result.status, result.failed_component) == ("failed", CONN)


def test_a_commit_in_a_flow_is_not_made_when_its_subjob_fails(on_sqlite, tmp_path):
    (tmp_path / "in.csv").write_text("1\nx\n")
    components = [connection(), does(1), reader("n:int", path=str(tmp_path / "in.csv"), die_on_error=True),
                  ends("tOracleCommit", inputs=("row1",))]
    result = run(components, after(CONN, "d", "in"), [flow("row1", "in", "e")])
    assert result.failed_component == "in"
    assert on_sqlite.stored() == []
    assert "commit" not in on_sqlite.sessions[0].did


# ------------------------------------------------------------------
# Rollback
# ------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["oracle_rollback", "OracleRollback", "tOracleRollback"])
def test_a_rollback_takes_back_what_was_done_and_closes_the_session(on_sqlite, kind, caplog):
    with caplog.at_level(logging.INFO, logger="src.v2"):
        result = run(*worked(ends(kind)))
    assert result.status == "success"
    assert on_sqlite.stored() == []
    assert on_sqlite.sessions[0].did[-2:] == ["rollback", "close"]
    assert f"[e] rolled back the session of '{CONN}' (the work of d) and closed it" in caplog.text


def test_a_rollback_may_leave_the_session_open(on_sqlite):
    result = run(*worked(ends("tOracleRollback", close=False), does(2, component_id="d2"),
                         ends("tOracleCommit", component_id="e2")))
    assert result.status == "success"
    assert on_sqlite.stored() == [(2,)]


def test_a_rollback_of_a_session_that_is_not_open_is_no_fault(on_sqlite, caplog):
    components, triggers = worked(ends("tOracleCommit"), ends("tOracleRollback", component_id="r"))
    with caplog.at_level(logging.INFO, logger="src.v2"):
        result = run(components, triggers)
    assert result.status == "success"
    assert f"[r] '{CONN}' has no open session: there is nothing to roll back" in caplog.text


def test_a_rollback_in_a_flow_is_made_when_a_row_reached_it(on_sqlite, tmp_path):
    (tmp_path / "in.csv").write_text("7\n")
    components = [connection(), does(1), reader("n:int", path=str(tmp_path / "in.csv")),
                  ends("tOracleRollback", inputs=("row1",), close=False), ends("tOracleCommit", component_id="c")]
    result = run(components, after(CONN, "d", "in") + after("in", "c"), [flow("row1", "in", "e")])
    assert result.status == "success"
    assert on_sqlite.stored() == []


def test_a_rollback_in_a_flow_is_not_made_when_no_row_reached_it(on_sqlite, tmp_path):
    (tmp_path / "in.csv").write_text("")
    components = [connection(), does(1), reader("n:int", path=str(tmp_path / "in.csv")),
                  ends("tOracleRollback", inputs=("row1",)), ends("tOracleCommit", component_id="c")]
    result = run(components, after(CONN, "d", "in") + after("in", "c"), [flow("row1", "in", "e")])
    assert result.status == "success"
    assert on_sqlite.stored() == [(1,)]


# ------------------------------------------------------------------
# Close
# ------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["oracle_close", "OracleClose", "tOracleClose"])
def test_a_close_closes_a_session_nothing_waits_on(on_sqlite, kind, caplog):
    with caplog.at_level(logging.INFO, logger="src.v2"):
        result = run([connection(), ends(kind)], after(CONN, "e"))
    assert result.status == "success"
    assert on_sqlite.sessions[0].did == ["close"]
    assert f"[e] closed the session of '{CONN}'" in caplog.text


def test_a_close_over_work_that_waits_fails_the_job_and_stores_nothing(on_sqlite):
    result = run(*worked(ends("tOracleClose")))
    assert (result.status, result.failed_component) == ("failed", "e")
    assert result.error == (
        f"what d did on the session of '{CONN}' was never stored, and is rolled back: put a commit before the "
        "close, or say with `uncommitted` what a close does with such work (`commit` or `rollback`)"
    )
    assert on_sqlite.stored() == []
    assert on_sqlite.sessions[0].closed
    # The close said it: the end of the job has nothing to add.
    assert list(result.failures) == ["e"]


@pytest.mark.parametrize("uncommitted, left", [("commit", [(1,)]), ("rollback", []), ("COMMIT", [(1,)])])
def test_a_close_may_say_what_becomes_of_work_that_waits(on_sqlite, uncommitted, left):
    result = run(*worked(ends("tOracleClose", uncommitted=uncommitted)))
    assert result.status == "success"
    assert on_sqlite.stored() == left
    assert on_sqlite.sessions[0].closed


def test_a_close_of_a_session_that_is_not_open_is_no_fault(on_sqlite, caplog):
    components, triggers = worked(ends("tOracleCommit"), ends("tOracleClose", component_id="x"))
    with caplog.at_level(logging.INFO, logger="src.v2"):
        result = run(components, triggers)
    assert result.status == "success"
    assert f"[x] '{CONN}' has no open session: there is nothing to close" in caplog.text


# ------------------------------------------------------------------
# What refuses the job
# ------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["tOracleCommit", "tOracleRollback", "tOracleClose"])
def test_the_connection_has_to_be_a_connection_component_of_the_job(on_sqlite, kind):
    where = f"component e ({kind})"
    assert refusals([connection(), ends(kind, connection="")]) == [
        f"{where} / connection: names no component; give the id of the Oracle connection whose session it ends"
    ]
    assert refusals([connection(), ends(kind, connection="tDBConnection_9")]) == [
        f"{where} / connection: the job has no component 'tDBConnection_9'; its Oracle connections are: {CONN}"
    ]
    assert refusals([connection(), does(1), ends(kind, connection="d")]) == [
        f"{where} / connection: 'd' (does) is no Oracle connection; the job's Oracle connections are: {CONN}"
    ]
    assert refusals([does(1), ends(kind, connection="d")]) == [
        f"{where} / connection: 'd' (does) is no Oracle connection; the job has none"
    ]


def test_a_component_that_opens_a_session_of_its_own_names_no_connection():
    """`connection` is read where `use_existing_connection` is on, and where a component has no such switch."""
    from src.v2.components.base import Component

    class Works(Component):
        uses_session = "Oracle"

    assert Works.connection_named({"use_existing_connection": False, "connection": "tDBConnection_1"}) is None
    assert Works.connection_named({"use_existing_connection": True, "connection": " tDBConnection_1 "}) == "tDBConnection_1"
    assert Works.connection_named({"use_existing_connection": "true", "connection": None}) == ""
    assert Works.connection_named({"connection": "c"}) == "c"
    assert Component.connection_named({"connection": "c"}) is None


def test_what_a_close_does_with_waiting_work_is_one_of_three(on_sqlite):
    assert refusals([connection(), ends("tOracleClose", uncommitted="keep")]) == [
        "component e (tOracleClose) / uncommitted: 'keep' is not allowed; use one of 'fail', 'commit', 'rollback'"
    ]


def test_a_close_takes_no_flow(on_sqlite, tmp_path):
    components = [connection(), reader("n:int"), ends("tOracleClose", inputs=("row1",))]
    assert refusals(components, [flow("row1", "in", "e")]) == [
        "component e (tOracleClose) / inputs: takes no input, but 1 flow arrives"
    ]


@pytest.mark.parametrize("kind", ["tOracleCommit", "tOracleRollback"])
def test_a_flow_cannot_leave_one_that_no_flow_leads_to(on_sqlite, kind):
    components = [connection(), ends(kind, outputs=("row2",)), writer("n:int")]
    assert refusals(components, [flow("row2", "e", "out")]) == [
        f"component e ({kind}) / outputs: a flow leaves it and none leads to it: it has no rows to hand on"
    ]
