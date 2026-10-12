"""A session with a real Oracle, and the connection, commit, rollback and close on it."""
import pytest

from src.v2 import oracle, run_job
from src.v2.errors import DatabaseError
from src.v2.job.keys import normalize_config
from src.v2.sessions import Sessions
from tests.v2.components.kit import job
from tests.v2.database import WITH_DOES

pytestmark = pytest.mark.oracle


def block(oracle_db, **more):
    config, refusals = normalize_config(oracle_db.block(**more), oracle.CONNECTION_KEYS, "test")
    assert not refusals and not oracle.problems(config)
    return config


@pytest.fixture
def session(oracle_db):
    made = oracle.opened(block(oracle_db), "tDBConnection_1", "a job of the tests")
    yield made
    if made.alive():
        made.close()


def asked(session, statement):
    """What the session itself sees."""
    with session._held.cursor() as cursor:
        cursor.execute(statement)
        return cursor.fetchall()


# ------------------------------------------------------------------
# The session
# ------------------------------------------------------------------

def test_a_session_is_opened_and_says_in_the_database_who_it_is(oracle_db, session):
    assert session.what == f"{oracle_db.user}@{oracle_db.host}:{oracle_db.port}/{oracle_db.service}"
    assert asked(session, "select sys_context('userenv', 'module'), sys_context('userenv', 'action') from dual") == [
        ("dataprep-v2", "a job of the tests")
    ]
    assert (session.alive(), session.in_transaction()) == (True, False)


@pytest.mark.parametrize("url", ["jdbc:oracle:thin:@//{host}:{port}/{service}", "{host}:{port}/{service}",
                                 "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={host})(PORT={port}))"
                                 "(CONNECT_DATA=(SERVICE_NAME={service})))"])
def test_a_connect_string_of_its_own_opens_a_session(oracle_db, url):
    made = url.format(host=oracle_db.host, port=oracle_db.port, service=oracle_db.service)
    config = block(oracle_db, connection_type="ORACLE_RAC", rac_url=made)
    session = oracle.opened(config, "c", "j")
    try:
        assert asked(session, "select 1 from dual") == [(1,)]
    finally:
        session.close()


def test_a_name_of_tnsnames_is_looked_up_in_the_file_the_job_names(oracle_db, tmp_path):
    """In either mode. Found when the tests were first run in thick mode: Oracle's own client looks in its own
    folder and passes over the file a connection names, so such a job opened a session in thin mode and failed in
    thick (ORA-12154)."""
    there = (f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={oracle_db.host})(PORT={oracle_db.port}))"
             f"(CONNECT_DATA=(SERVICE_NAME={oracle_db.service})))")
    (tmp_path / "tnsnames.ora").write_text(
        "# the names of the tests\nOTHER = (DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=elsewhere.invalid)(PORT=1521))"
        f"(CONNECT_DATA=(SERVICE_NAME=X)))\nV2_HERE, v2_too =\n  {there}\n")
    config = block(oracle_db, connection_type="ORACLE_OCI", local_service_name="v2_here", use_tns_file=True,
                   tns_file=str(tmp_path / "tnsnames.ora"))
    session = oracle.opened(config, "c", "j")
    try:
        assert asked(session, "select 1 from dual") == [(1,)]
        assert session.what == f"{oracle_db.user}@v2_here"
    finally:
        session.close()
    with pytest.raises(DatabaseError) as failed:
        oracle.opened({**config, "local_service_name": "NO_SUCH_NAME"}, "c", "j")
    assert str(failed.value).startswith(f"no session was opened as {oracle_db.user}@NO_SUCH_NAME: ")
    assert "NO_SUCH_NAME" in str(failed.value).split(": ", 1)[1] and "\n" not in str(failed.value)


def test_a_wrong_password_is_said_without_the_password(oracle_db):
    with pytest.raises(DatabaseError) as failed:
        oracle.opened(block(oracle_db, password="not_the_password_7"), "c", "j")
    said = str(failed.value)
    assert said.startswith(f"no session was opened as {oracle_db.user}@{oracle_db.host}:{oracle_db.port}/"
                           f"{oracle_db.service}: ORA-01017:")
    assert "not_the_password_7" not in said and "\n" not in said and "Help:" not in said


def test_a_service_that_is_not_there_is_said_in_one_line(oracle_db):
    with pytest.raises(DatabaseError) as failed:
        oracle.opened(block(oracle_db, dbname="NO_SUCH_SERVICE"), "c", "j")
    assert "NO_SUCH_SERVICE" in str(failed.value) and "\n" not in str(failed.value)


def test_what_is_done_waits_until_it_is_stored(oracle_db, session, table):
    assert session.run(f"insert into {table} values (:n, :v)", {"n": 1, "v": "a"}) == 1
    assert session.in_transaction() is True
    assert oracle_db.rows(f"select n from {table}") == []
    session.commit()
    assert session.in_transaction() is False
    assert oracle_db.rows(f"select n, v from {table}") == [(1, "a")]


def test_what_is_done_is_taken_back(oracle_db, session, table):
    session.run(f"insert into {table} values (1, 'a')")
    session.rollback()
    session.commit()
    assert oracle_db.rows(f"select n from {table}") == []


def test_a_place_that_was_marked_is_gone_back_to_and_the_transaction_stays(oracle_db, session, table):
    session.run(f"insert into {table} values (1, 'a')")
    session.savepoint("v2_subjob")
    session.run(f"insert into {table} values (2, 'b')")
    session.rollback_to("v2_subjob")
    assert session.in_transaction() is True
    session.commit()
    assert oracle_db.rows(f"select n from {table}") == [(1,)]


def test_a_session_closed_with_work_waiting_loses_it(oracle_db, session, table):
    session.run(f"insert into {table} values (1, 'a')")
    session.close()
    assert oracle_db.rows(f"select n from {table}") == []


def test_what_the_database_refuses_is_said_in_its_words_on_one_line(session):
    with pytest.raises(DatabaseError) as failed:
        session.run("select * from no_such_table_of_v2")
    assert str(failed.value).startswith("ORA-00942:") and "Help:" not in str(failed.value)
    # The session is none the worse for it.
    assert asked(session, "select 1 from dual") == [(1,)]


def test_a_statement_that_defines_stores_what_waited_and_the_engine_sees_that_nothing_waits(oracle_db, table):
    """Oracle commits before a statement that defines. A close after it finds nothing to fail on."""
    sessions = Sessions()
    session = oracle.opened(block(oracle_db), "conn", "j")
    sessions.share(session)
    sessions.working(session, "tDBRow_1")
    session.run(f"insert into {table} values (1, 'a')")
    sessions.subjob_succeeded()
    assert session.pending == ["tDBRow_1"]
    session.run(f"truncate table {table}")
    assert sessions.close("conn") is True
    assert session.pending == []


def test_a_subjob_that_fails_on_a_shared_session_loses_its_own_work_and_no_other(oracle_db, table):
    sessions = Sessions()
    session = oracle.opened(block(oracle_db), "conn", "j")
    sessions.share(session)
    sessions.working(session, "first")
    session.run(f"insert into {table} values (1, 'a')")
    sessions.subjob_succeeded()
    sessions.working(session, "second")
    session.run(f"insert into {table} values (2, 'b')")
    sessions.subjob_failed()
    sessions.commit("conn", close=True)
    assert oracle_db.rows(f"select n from {table}") == [(1,)]


# ------------------------------------------------------------------
# The four components, in a job
# ------------------------------------------------------------------

def components(oracle_db, table, *then, **connection):
    made = [{"id": "tDBConnection_1", "type": "tOracleConnection", "config": oracle_db.block(**connection),
             "inputs": [], "outputs": []},
            {"id": "d", "type": "does", "inputs": [], "outputs": [],
             "config": {"connection": "tDBConnection_1", "statement": f"insert into {table} values (1, 'a')"}}]
    made += [{"id": f"e{at}", "type": kind, "config": {"connection": "tDBConnection_1", **config}, "inputs": [],
              "outputs": []} for at, (kind, config) in enumerate(then)]
    ids = [component["id"] for component in made]
    return job(made, [], triggers=[{"type": "OnSubjobOk", "from": a, "to": b} for a, b in zip(ids, ids[1:])])


def test_a_job_stores_what_it_did_with_a_commit(oracle_db, table):
    result = run_job(components(oracle_db, table, ("tOracleCommit", {})), registry=WITH_DOES)
    assert result.status == "success"
    assert oracle_db.rows(f"select n from {table}") == [(1,)]
    assert oracle_db.password not in repr(result.global_map)


def test_a_job_that_ends_without_a_commit_has_failed_and_stored_nothing(oracle_db, table):
    result = run_job(components(oracle_db, table), registry=WITH_DOES)
    assert (result.status, result.failed_component) == ("failed", "tDBConnection_1")
    assert "was never stored" in result.error
    assert oracle_db.rows(f"select n from {table}") == []


def test_a_rollback_takes_it_back(oracle_db, table):
    result = run_job(components(oracle_db, table, ("tOracleRollback", {})), registry=WITH_DOES)
    assert result.status == "success"
    assert oracle_db.rows(f"select n from {table}") == []


def test_a_close_over_work_that_waits_fails_unless_it_says_what_becomes_of_it(oracle_db, table):
    result = run_job(components(oracle_db, table, ("tOracleClose", {})), registry=WITH_DOES)
    assert (result.status, result.failed_component) == ("failed", "e0")
    assert oracle_db.rows(f"select n from {table}") == []
    result = run_job(components(oracle_db, table, ("tOracleClose", {"uncommitted": "commit"})), registry=WITH_DOES)
    assert result.status == "success"
    assert oracle_db.rows(f"select n from {table}") == [(1,)]


def test_a_session_that_commits_by_itself_stores_each_subjob(oracle_db, table):
    result = run_job(components(oracle_db, table, auto_commit=True), registry=WITH_DOES)
    assert result.status == "success"
    assert oracle_db.rows(f"select n from {table}") == [(1,)]
