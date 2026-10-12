"""SQL Server input: the rows of a query. On SQLite, behind the seam, for what is no database's own."""
import logging
import sqlite3

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, writer
from tests.v2.components.test_mssql_connection import BLOCK, after, connection
from tests.v2.database import WITH_DOES, mssql_on_sqlite  # noqa: F401 -- a fixture

ROWS = "id:int, name:str, amt:Decimal#2"
QUERY = "select id, name, amt from emp order by id"
# What Talend's converter writes for an input, with nothing changed in the Studio.
AS_CONVERTED = {"driver": "MSSQL_PROP", "specify_datasource_alias": False, "datasource_alias": "",
                "properties": "noDatetimeStringSync=true", "active_dir_auth": False, "encoding": "ISO-8859-15",
                "trim_all_column": False, "trim_column": [], "set_query_timeout": False,
                "query_timeout_in_seconds": 30, "tstatcatcher_stats": False, "label": ""}


@pytest.fixture
def emp(mssql_on_sqlite):
    held = sqlite3.connect(mssql_on_sqlite.path)
    held.execute("create table emp (id, name, amt, joined, [it's])")
    held.executemany("insert into emp values (?, ?, ?, ?, ?)", [
        (1, "ann ", 1.5, "2024-01-31", "a"), (2, None, 2.255, "2024-02-01", "b"), (3, " bob", None, "not a day", "o'x")])
    held.commit()
    held.close()
    return mssql_on_sqlite


def reads(schema=ROWS, component_id="in", outputs=("row1",), kind="tMSSqlInput", **config):
    made = {"use_existing_connection": True, "connection": "tDBConnection_1", "query": QUERY, **config}
    return {"id": component_id, "type": kind, "config": made, "schema": {"input": [], "output": columns(schema)},
            "inputs": [], "outputs": list(outputs)}


def to_file(tmp_path, schema=ROWS, **config):
    """connection -> a query -> a file."""
    out = str(tmp_path / "out.csv")
    components = [connection(), reads(schema, **config), writer(schema, path=out, inputs=("row1",))]
    return out, job(components, [flow("row1", "in", "out")], triggers=after("tDBConnection_1", "in"))


def alone(tmp_path, schema=ROWS, **config):
    """A query on a session of its own -> a file."""
    out = str(tmp_path / "out.csv")
    components = [reads(schema, **{"use_existing_connection": False, "connection": "", **BLOCK, **config}),
                  writer(schema, path=out, inputs=("row1",))]
    return out, job(components, [flow("row1", "in", "out")])


def run(made, **more):
    return run_job(made, registry=WITH_DOES, **more)


def lines(path):
    with open(path) as held:
        return held.read().splitlines()


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made, registry=WITH_DOES)
    return [f"{refusal.key}: {refusal.reason}" for refusal in refused.value.report]


# ------------------------------------------------------------------
# The rows of a query
# ------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["mssql_input", "MSSqlInput", "tMSSqlInput"])
def test_the_rows_of_the_query_as_the_columns_the_job_declares(emp, tmp_path, kind):
    out, made = to_file(tmp_path, kind=kind)
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out) == ["id;name;amt", "1;ann ;1.50", "2;;2.26", "3; bob;"]
    assert result.rows == {"out": 3}


def test_it_reads_on_the_session_of_the_connection_it_names_and_the_job_closes_that(emp, tmp_path):
    out, made = to_file(tmp_path)
    run(made)
    session, = emp.sessions
    assert [did[0] for did in session.did if isinstance(did, tuple)] == ["fields", "query"]
    assert session.did.count("close") == 1 and session.did[-1] == "close"
    # The session is told who reads on it now, and that the query has all the time it takes.
    assert (session.asking, session.limit) == ("in", 0)


def test_two_inputs_read_on_one_session_one_after_the_other(emp, tmp_path):
    out, second = str(tmp_path / "out.csv"), str(tmp_path / "second.csv")
    components = [connection(), reads(), writer(ROWS, path=out, inputs=("row1",)),
                  reads("id:int", component_id="in2", outputs=("row2",), query="select id from emp where id > 1 order by id"),
                  writer("id:int", component_id="out2", path=second, inputs=("row2",))]
    made = job(components, [flow("row1", "in", "out"), flow("row2", "in2", "out2")],
               triggers=after("tDBConnection_1", "in", "in2"))
    result = run(made)
    assert result.status == "success", result.error
    assert (len(lines(out)), lines(second)) == (4, ["id", "2", "3"])
    assert len(emp.sessions) == 1 and emp.sessions[0].asking == "in2"


def test_it_reads_with_a_session_of_its_own_and_closes_it_when_the_rows_are_in(emp, tmp_path):
    out, made = alone(tmp_path)
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out)[1:] == ["1;ann ;1.50", "2;;2.26", "3; bob;"]
    (config, opened_by, more), = emp.asked
    assert (opened_by, more, config["host"], config["port"]) == ("in", {}, "db.example", 1433)
    session, = emp.sessions
    assert not session.shared and session.did[-1] == "close" and session.did.count("close") == 1


def test_a_session_of_its_own_is_closed_when_the_query_fails(emp, tmp_path):
    out, made = alone(tmp_path, query="select id, name, amt from no_such_table")
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert "no such table" in result.error
    assert emp.sessions[0].did[-1] == "close"


def test_an_input_as_talends_converter_writes_one_is_taken(emp, tmp_path):
    out, made = alone(tmp_path, **AS_CONVERTED)
    result = run(made)
    assert result.status == "success", result.error
    assert len(lines(out)) == 4


# ------------------------------------------------------------------
# The query is read as SQL Server reads one
# ------------------------------------------------------------------

def test_a_name_between_square_brackets_may_hold_a_quote_and_the_value_after_it_is_bound(emp, tmp_path):
    out, made = to_file(tmp_path, "id:int", query="select id from emp where [it's] = '${context.v}' order by id")
    made["context"] = {"v": "o'x"}
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out) == ["id", "3"]
    # What is left for whoever looks: the query as SQL Server is sent it, with a mark where the value goes.
    assert result.global_map["in_QUERY"] == "select id from emp where [it's] = ? order by id"
    assert "o'x" not in repr(result.global_map)


def test_as_talend_joins_it_with_a_name_and_a_number_written_in(emp, tmp_path):
    query = '"select id from " + context.t + " where id > " + context.n + " and name like \'%" + context.s + "%\' order by id"'
    out, made = to_file(tmp_path, "id:int", query=query)
    made["context"] = {"t": "emp", "n": 1, "s": "bo"}
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out) == ["id", "3"]
    assert result.global_map["in_QUERY"] == "select id from emp where id > 1 and name like '%' + ? + '%' order by id"


def test_a_value_that_would_change_the_query_fails_it_and_is_shown_nowhere(emp, tmp_path, caplog):
    out, made = to_file(tmp_path, "id:int", query="select id from emp where id = ${context.v}")
    made["context"] = {"v": "1 or 1 = 1"}
    with caplog.at_level(logging.DEBUG, logger="src.v2"):
        result = run(made)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert result.error.startswith("what context.v holds is written into the statement")
    assert "1 or 1 = 1" not in result.error
    assert not [did for did in emp.sessions[0].did if isinstance(did, tuple)]


# ------------------------------------------------------------------
# What every database input does, and this one too
# ------------------------------------------------------------------

def test_text_that_is_declared_as_something_else_is_read_as_a_files_text_is(emp, tmp_path):
    out, made = to_file(tmp_path, "id:int, joined:date@%Y-%m-%d", query="select id, joined from emp where id < 3 order by id")
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out) == ["id;joined", "1;2024-01-31", "2;2024-02-01"]


def test_text_that_is_none_of_its_type_fails_the_job_and_names_the_row(emp, tmp_path):
    out, made = to_file(tmp_path, "id:int, joined:date@%Y-%m-%d", query="select id, joined from emp order by id")
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert "row 3 of the result of in" in result.error


def test_with_die_on_error_off_such_a_row_leaves_by_the_reject_output(emp, tmp_path):
    schema = "id:int, joined:date@%Y-%m-%d"
    out, rejects = str(tmp_path / "out.csv"), str(tmp_path / "rejects.csv")
    components = [connection(),
                  reads(schema, outputs=("row1", "bad"), query="select id, joined from emp order by id", die_on_error=False),
                  writer(schema, path=out, inputs=("row1",)),
                  writer("id:str, joined:str, errorCode:str, errorMessage:str", component_id="rej", path=rejects, inputs=("bad",))]
    made = job(components, [flow("row1", "in", "out"), flow("bad", "in", "rej", kind="reject")],
               triggers=after("tDBConnection_1", "in"))
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out)[1:] == ["1;2024-01-31", "2;2024-02-01"]
    assert lines(rejects)[1].startswith("3;not a day;TYPE_CONVERSION;")


def test_text_is_stripped_and_missing_text_made_empty_when_asked(emp, tmp_path):
    out, made = to_file(tmp_path, trim_all_column=True, no_null_values=True)
    run(made)
    assert lines(out)[1:] == ["1;ann;1.50", "2;;2.26", "3;bob;"]
    out, made = to_file(tmp_path, trim_column=[{"schema_column": "name"}, {"trim": "true"}])
    run(made)
    assert lines(out)[1:] == ["1;ann;1.50", "2;;2.26", "3;bob;"]


def test_rows_are_fetched_as_many_at_a_time_as_the_job_says(emp, tmp_path):
    out, made = to_file(tmp_path, use_cursor=True, cursor_size=2)
    run(made)
    assert emp.sessions[0].did.count("batch") == 2
    assert lines(out)[1:] == ["1;ann ;1.50", "2;;2.26", "3; bob;"]


def test_a_query_that_does_not_go_with_the_declared_columns_fails(emp, tmp_path):
    out, made = to_file(tmp_path, "id:int, name:str")
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert result.error == ("the query hands back 3 column(s) and the job declares 2: they are taken by their place, "
                            "so there have to be as many")


# ------------------------------------------------------------------
# The time a query is given
# ------------------------------------------------------------------

def test_the_seconds_a_query_is_given_are_told_the_session_before_it_reads(emp, tmp_path):
    out, made = to_file(tmp_path, set_query_timeout=True, query_timeout_in_seconds="45")
    assert run(made).status == "success"
    assert emp.sessions[0].limit == 45


def test_with_the_switch_and_no_seconds_said_a_query_is_given_thirty(emp, tmp_path):
    out, made = to_file(tmp_path, set_query_timeout=True)
    assert run(made).status == "success"
    assert emp.sessions[0].limit == 30


def test_without_the_switch_the_seconds_are_not_told(emp, tmp_path):
    out, made = to_file(tmp_path, set_query_timeout=False, query_timeout_in_seconds=45)
    assert run(made).status == "success"
    assert emp.sessions[0].limit == 0


@pytest.mark.parametrize("seconds", ["soon", 0, -5, 1.5, True])
def test_what_is_no_number_of_seconds_is_refused(emp, tmp_path, seconds):
    out, made = to_file(tmp_path, set_query_timeout=True, query_timeout_in_seconds=seconds)
    assert refusals(made) == [f"query_timeout_in_seconds: {seconds!r} is no number of seconds: give a whole number, "
                              "1 or more"]


# ------------------------------------------------------------------
# What refuses the job
# ------------------------------------------------------------------

def test_what_refuses_the_job_when_it_loads(emp, tmp_path):
    out, made = to_file(tmp_path)
    made["components"][1]["schema"]["output"] = []
    assert refusals(made) == ["schema: a database input needs its columns declared"]
    out, made = to_file(tmp_path, query='"select \'" + TalendDate.getDate("yyyy") + "\' from emp"')
    assert refusals(made)[0].startswith("query: the statement is joined as Java joins text")
    out, made = to_file(tmp_path, connection="nope")
    assert refusals(made) == ["connection: the job has no component 'nope'; its SQL Server connections are: tDBConnection_1"]
    out, made = to_file(tmp_path, connection="")
    assert refusals(made) == ["connection: names no component; give the id of the SQL Server connection whose session "
                              "it works on"]


def test_it_cannot_read_on_the_session_of_an_oracle_connection(emp, tmp_path):
    out = str(tmp_path / "out.csv")
    oracle = {"id": "ora", "type": "tOracleConnection", "inputs": [], "outputs": [], "schema": {"input": [], "output": []},
              "config": {"host": "h", "dbname": "S", "user": "u", "password": "p"}}
    made = job([oracle, reads(connection="ora"), writer(ROWS, path=out, inputs=("row1",))], [flow("row1", "in", "out")],
               triggers=after("ora", "in"))
    assert refusals(made) == ["connection: 'ora' (tOracleConnection) is no SQL Server connection; the job has none"]


def test_what_is_wrong_with_a_block_of_its_own_refuses_the_job(emp, tmp_path):
    out, made = alone(tmp_path, host=" ", user="")
    assert refusals(made) == ["host: is empty; a session is opened with a host",
                              "user: is empty; v2 signs in to SQL Server with a user and a password"]
    # A key that is refused is said first, and by itself.
    out, made = alone(tmp_path, host=" ", active_dir_auth=True)
    assert refusals(made) == [
        "active_dir_auth: v2 signs in to SQL Server with a user and a password of the database's own; signing in "
        "through Microsoft Entra was not at hand to be tried, and is not built"]


def test_a_block_it_does_not_read_is_not_judged(emp, tmp_path):
    out, made = to_file(tmp_path, host="", user="", properties="domain=CORP")
    assert run(made).status == "success"
