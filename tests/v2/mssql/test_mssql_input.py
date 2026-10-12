"""SQL Server connection and input against a real SQL Server, as jobs."""
import secrets

import pytest

from src.v2 import run_job
from tests.v2.components.kit import columns, flow, job, writer

pytestmark = pytest.mark.mssql


@pytest.fixture
def emp(mssql_db):
    """A table of this test's own with a column of each kind a job declares, dropped afterwards."""
    name = f"dbo.v2e_{secrets.token_hex(5)}"
    mssql_db.run(
        f"""create table {name} (id bigint primary key, name nvarchar(20), amt decimal(12, 3), ratio float, flag bit,
            joined date, seen datetime2(7), code char(4), [it's] varchar(10), day_text varchar(10))""",
        f"""insert into {name} values
            (1, N'ann ', 1234.565, 0.1, 1, '2024-01-31', '2024-01-31 13:14:15.1234567', 'ab', 'a', '2024-02-01'),
            (2, null, -0.0005, 2.675, 0, null, null, null, 'o''x', 'not a day'),
            (3, N' bob', null, null, null, '0001-01-01', '9999-12-31 23:59:59.9999999', '', '', '')""")
    yield name
    mssql_db.run(f"drop table {name}")


def reads(mssql_db, schema, query, component_id="in", outputs=("row1",), **config):
    made = {**mssql_db.block(), "use_existing_connection": False, "query": query, **config}
    return {"id": component_id, "type": "tMSSqlInput", "inputs": [], "outputs": list(outputs),
            "schema": {"input": [], "output": columns(schema)}, "config": made}


def reading(mssql_db, tmp_path, schema, query, context=None, **config):
    out = str(tmp_path / "out.csv")
    made = job([reads(mssql_db, schema, query, **config), writer(schema, path=out, inputs=("row1",))],
               [flow("row1", "in", "out")])
    if context:
        made["context"] = context
    result = run_job(made)
    try:
        with open(out) as held:
            return result, held.read().splitlines()
    except FileNotFoundError:
        return result, None


def test_every_kind_of_column_as_the_job_declares_it(mssql_db, emp, tmp_path):
    schema = ("id:int, name:str, amt:Decimal#2, amt_whole:int, amt_text:str, ratio:float, ratio_two:Decimal#2, flag:bool, "
              "joined:date@%Y-%m-%d, joined_text:str, seen:datetime@%Y-%m-%d %H:%M:%S.%f, seen_day:date@%Y-%m-%d, "
              "seen_text:str, code:str, day:date@%Y-%m-%d")
    query = (f"select id, name, amt, amt, amt, ratio, ratio, flag, joined, joined, seen, seen, seen, code, "
             f"case when id = 1 then day_text end from {emp} order by id")
    result, lines = reading(mssql_db, tmp_path, schema, query)
    assert result.status == "success", result.error
    assert lines[1:] == [
        "1;ann ;1234.57;1234;1234.565;0.1;0.10;true;2024-01-31;2024-01-31;2024-01-31 13:14:15.123456;2024-01-31;"
        "2024-01-31 13:14:15.123456;ab  ;2024-02-01",
        "2;;0.00;0;-0.001;2.675;2.67;false;;;;;;;",
        "3; bob;;;;;;;0001-01-01;0001-01-01;9999-12-31 23:59:59.999999;9999-12-31;9999-12-31 23:59:59.999999;    ;",
    ]
    assert result.rows == {"out": 3}


def test_a_query_is_run_as_it_is_written_with_its_values_bound(mssql_db, emp, tmp_path):
    query = (f"with picked as (select id, name from [${{context.schema}}].[{emp.split('.')[1]}] where [it's] = '${{context.v}}' "
             f"or id in (${{context.ids}}) or name like N'%${{context.part}}') select id, name from picked order by id desc")
    result, lines = reading(mssql_db, tmp_path, "id:int, name:str", query,
                            context={"schema": "dbo", "v": "o'x", "ids": "3", "part": "nn "})
    assert result.status == "success", result.error
    assert lines[1:] == ["3; bob", "2;", "1;ann "]
    assert result.global_map["in_QUERY"] == (
        f"with picked as (select id, name from [dbo].[{emp.split('.')[1]}] where [it's] = ? or id in (3) or name like "
        "N'%' + ?) select id, name from picked order by id desc")
    assert "o'x" not in repr(result.global_map)


def test_as_talend_joins_a_query(mssql_db, emp, tmp_path):
    query = '"select id from " + context.t + " where name like \'" + context.s + "%\' order by id"'
    result, lines = reading(mssql_db, tmp_path, "id:int", query, context={"t": emp, "s": "ann"})
    assert result.status == "success", result.error
    assert lines[1:] == ["1"]


def test_text_is_stripped_and_missing_text_made_empty_when_asked_and_empty_text_is_empty_text(mssql_db, emp, tmp_path):
    query = f"select name, code from {emp} order by id"
    result, lines = reading(mssql_db, tmp_path, "name:str, code:str", query, trim_all_column=True, no_null_values=True)
    assert result.status == "success", result.error
    assert lines[1:] == ["ann;ab", ";", "bob;"]


def test_text_that_is_none_of_its_declared_type_names_the_row_or_leaves_by_the_reject_output(mssql_db, emp, tmp_path):
    schema, query = "id:int, day:date@%Y-%m-%d", f"select id, day_text from {emp} order by id"
    result, _ = reading(mssql_db, tmp_path, schema, query)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert "row 2 of the result of in" in result.error
    out, rejects = str(tmp_path / "out.csv"), str(tmp_path / "rejects.csv")
    made = job([reads(mssql_db, schema, query, outputs=("row1", "bad"), die_on_error=False),
                writer(schema, path=out, inputs=("row1",)),
                writer("id:str, day:str, errorCode:str, errorMessage:str", component_id="rej", path=rejects, inputs=("bad",))],
               [flow("row1", "in", "out"), flow("bad", "in", "rej", kind="reject")])
    result = run_job(made)
    assert result.status == "success", result.error
    with open(out) as held:
        assert held.read().splitlines()[1:] == ["1;2024-02-01", "3;"]
    with open(rejects) as held:
        assert held.read().splitlines()[1].startswith("2;not a day;TYPE_CONVERSION;")


def test_a_number_too_large_for_what_is_declared_fails_the_job_and_names_the_row(mssql_db, tmp_path):
    query = "select cast(1 as decimal(38, 0)) union all select 12345678901234567890123 order by 1"
    result, _ = reading(mssql_db, tmp_path, "n:int", query)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert result.error == ("row 2 of the result: column 1 holds 12345678901234567890123, which does not fit a whole "
                            "number of 64 bits")


def test_what_is_not_read_fails_the_job_with_what_to_write_in_the_query(mssql_db, tmp_path):
    result, _ = reading(mssql_db, tmp_path, "at:str, raw:str", "select sysdatetimeoffset(), 0x01")
    assert (result.status, result.failed_component) == ("failed", "in")
    assert "column 'at': the query hands back a date with a time zone (DATETIMEOFFSET)" in result.error
    assert "column 'raw': the query hands back binary data" in result.error


def test_many_rows_come_whole_and_in_their_order(mssql_db, tmp_path):
    query = ("select top 120000 row_number() over (order by (select 1)) n, cast(row_number() over (order by (select 1)) "
             "* 1.5 as decimal(18, 1)) d, replicate('x', 30) s from sys.all_columns a cross join sys.all_columns b "
             "order by 1")
    result, lines = reading(mssql_db, tmp_path, "n:int, d:Decimal#1, s:str", query)
    assert result.status == "success", result.error
    assert len(lines) == 120001
    assert (lines[1], lines[50000], lines[50001], lines[120000]) == (
        "1;1.5;" + "x" * 30, "50000;75000.0;" + "x" * 30, "50001;75001.5;" + "x" * 30, "120000;180000.0;" + "x" * 30)
    assert [int(line.split(";")[0]) for line in lines[1:]] == list(range(1, 120001))


def test_a_large_text_arrives_whole(mssql_db, tmp_path):
    query = "select replicate(cast('x' as varchar(max)), 2000000), replicate(cast(N'y' as nvarchar(max)), 50000) + nchar(55357) + nchar(56832)"
    result, lines = reading(mssql_db, tmp_path, "big:str, wide:str", query)
    assert result.status == "success", result.error
    big, wide = lines[1].split(";")
    assert (len(big), set(big), len(wide), wide[:2]) == (2000000, {"x"}, 50001, "yy")


@pytest.fixture
def procedures(mssql_db, emp):
    made = f"v2q_{secrets.token_hex(5)}"
    bodies = {
        "rows": f"@from int as begin update {emp} set flag = flag where id = 1; select id from {emp} where id >= @from order by id; end",
        "fails": f"as begin set nocount on; select id from {emp} order by id; throw 50001, 'it failed after its rows', 1; end",
        "two": f"as begin set nocount on; select id from {emp} where id < 3 order by id; select name from {emp}; end",
        "none": f"as begin update {emp} set code = 'done' where id = 3; end",
    }
    for name, body in bodies.items():
        mssql_db.run(f"create procedure dbo.{made}_{name} {body}")
    yield f"dbo.{made}"
    for name in bodies:
        mssql_db.run(f"drop procedure dbo.{made}_{name}")


def test_the_rows_of_a_procedure_called_with_a_value(mssql_db, procedures, tmp_path):
    result, lines = reading(mssql_db, tmp_path, "id:int", f"exec {procedures}_rows '${{context.k}}'", context={"k": "2"})
    assert result.status == "success", result.error
    assert lines[1:] == ["2", "3"]


def test_a_procedure_that_fails_after_its_rows_fails_the_job(mssql_db, procedures, tmp_path):
    result, lines = reading(mssql_db, tmp_path, "id:int", f"exec {procedures}_fails")
    assert (result.status, result.failed_component) == ("failed", "in")
    assert result.error == "the query failed after 3 row(s) were read: it failed after its rows"
    assert lines is None


def test_rows_a_procedure_hands_back_after_its_first_are_passed_over_and_said(mssql_db, procedures, tmp_path, caplog):
    with caplog.at_level("INFO", logger="src.v2"):
        result, lines = reading(mssql_db, tmp_path, "id:int", f"exec {procedures}_two")
    assert result.status == "success", result.error
    assert lines[1:] == ["1", "2"]
    assert "[in] the query handed back 2 results: the first is read and the other is passed over" in caplog.text


def test_a_procedure_with_no_rows_to_read_fails_the_job_and_what_it_changed_is_stored(mssql_db, emp, procedures, tmp_path):
    result, _ = reading(mssql_db, tmp_path, "id:int", f"exec {procedures}_none")
    assert (result.status, result.failed_component) == ("failed", "in")
    assert result.error == "the statement was run and handed back no rows to read: an input reads the rows of a query"
    assert mssql_db.rows(f"select code from {emp} where id = 3") == [("done",)]


def test_a_query_that_takes_longer_than_it_is_given_fails_the_job(mssql_db, tmp_path):
    result, _ = reading(mssql_db, tmp_path, "n:int", "waitfor delay '00:00:04'; select 1", set_query_timeout=True,
                        query_timeout_in_seconds=1)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert result.error == "Query timeout expired: the query was given 1 second(s) (`query_timeout_in_seconds`)"


def test_a_wrong_password_fails_the_job_at_the_input_and_shows_no_password(mssql_db, tmp_path, caplog):
    with caplog.at_level("DEBUG", logger="src.v2"):
        result, _ = reading(mssql_db, tmp_path, "n:int", "select 1", password="not-the-Passw0rd")
    assert (result.status, result.failed_component) == ("failed", "in")
    assert result.error.endswith(f"Login failed for user '{mssql_db.user}'.")
    assert "not-the-Passw0rd" not in caplog.text and "not-the-Passw0rd" not in result.error


def test_two_inputs_read_on_the_session_of_one_connection_and_the_job_closes_it(mssql_db, emp, tmp_path):
    first, second = str(tmp_path / "first.csv"), str(tmp_path / "second.csv")
    connection = {"id": "tDBConnection_1", "type": "tMSSqlConnection", "inputs": [], "outputs": [],
                  "schema": {"input": [], "output": []}, "config": {**mssql_db.block(), "schema_db": "dbo"}}
    on_it = {"use_existing_connection": True, "connection": "tDBConnection_1", "host": "", "user": "", "password": ""}
    components = [
        connection,
        reads(mssql_db, "id:int, spid:int", f"select id, @@spid from {emp} order by id", **on_it),
        writer("id:int, spid:int", path=first, inputs=("row1",)),
        reads(mssql_db, "name:str, spid:int", f"select name, @@spid from {emp} where id = 1", component_id="in2",
              outputs=("row2",), **on_it),
        writer("name:str, spid:int", component_id="out2", path=second, inputs=("row2",)),
    ]
    made = job(components, [flow("row1", "in", "out"), flow("row2", "in2", "out2")],
               triggers=[{"type": "OnSubjobOk", "from": "tDBConnection_1", "to": "in"},
                         {"type": "OnSubjobOk", "from": "in", "to": "in2"}])
    result = run_job(made)
    assert result.status == "success", result.error
    with open(first) as held:
        one = held.read().splitlines()[1:]
    with open(second) as held:
        two = held.read().splitlines()[1:]
    assert [line.split(";")[0] for line in one] == ["1", "2", "3"] and two[0].startswith("ann ;")
    # One session for both, and it is gone when the job has ended.
    spids = {line.split(";")[1] for line in one + two}
    assert len(spids) == 1
    assert (result.global_map["dbschema_tDBConnection_1"], result.global_map["db_tDBConnection_1"]) == ("dbo", mssql_db.name)
    assert mssql_db.rows("select count(*) from sys.dm_exec_sessions where session_id = ? and session_id <> @@spid "
                         "and status <> 'dormant'", int(spids.pop())) == [(0,)]


def test_a_clean_run_writes_nothing_to_stderr_and_the_driver_no_line_of_its_own(mssql_db, emp, tmp_path, capfd):
    result, lines = reading(mssql_db, tmp_path, "id:int", f"select id from {emp} order by id")
    assert result.status == "success" and len(lines) == 4
    assert capfd.readouterr().err == ""
