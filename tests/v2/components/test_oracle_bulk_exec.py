"""Oracle bulk exec: the rows of a file, or of a flow, stored in a table. On SQLite, behind the seam."""
import logging
import sqlite3

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, reader
from tests.v2.components.test_oracle_connection import BLOCK, after, connection
from tests.v2.database import WITH_DOES, on_sqlite  # noqa: F401 -- a fixture

ROWS = "id:int, name:str, amt:float, day:datetime@%Y-%m-%d"
EMP = "select id, name, amt, day from emp order by id"
CONN = "tDBConnection_1"


@pytest.fixture
def emp(on_sqlite):
    held = sqlite3.connect(on_sqlite.path)
    held.execute("create table emp (id integer primary key, name text check (length(name) < 8), amt real, day)")
    held.commit()
    held.close()
    return on_sqlite


def before(emp, *rows):
    held = sqlite3.connect(emp.path)
    held.executemany("insert into emp values (?, ?, ?, ?)", rows)
    held.commit()
    held.close()


def bulk(component_id="b", inputs=(), schema=ROWS, **config):
    made = {"use_existing_connection": True, "connection": CONN, "table": "emp", **config}
    return {"id": component_id, "type": "tOracleBulkExec", "config": made, "inputs": list(inputs), "outputs": [],
            "schema": {"input": columns(schema), "output": []}}


def loading(tmp_path, text, with_commit=True, **config):
    """connection -> the load of a file -> a commit."""
    (tmp_path / "load.dat").write_text(text, encoding=config.pop("written_in", "utf-8"))
    components = [connection(schema_db=""), bulk(data=str(tmp_path / "load.dat"), **config)]
    if with_commit:
        components.append({"id": "c", "type": "tOracleCommit", "config": {"connection": CONN}, "inputs": [], "outputs": []})
    return job(components, [], triggers=after(*(component["id"] for component in components)))


def run(made, **more):
    return run_job(made, registry=WITH_DOES, **more)


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made, registry=WITH_DOES)
    return [f"{refusal.key}: {refusal.reason}" for refusal in refused.value.report]


# ------------------------------------------------------------------
# A file, with no flow leading to it
# ------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["oracle_bulk_exec", "OracleBulkExec", "tOracleBulkExec"])
def test_the_rows_of_the_file_are_stored_when_the_subjob_has_succeeded(emp, tmp_path, kind):
    made = loading(tmp_path, "1;ann;1.5;2024-01-31\n2;bob;;\n")
    made["components"][1]["type"] = kind
    result = run(made)
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann", 1.5, "2024-01-31 00:00:00"), (2, "bob", None, None)]
    held = result.global_map
    assert (held["b_NB_LINE_DATA"], held["b_NB_LINE_INSERTED"], held["b_NB_LINE_BAD"], held["b_RETURN_CODE"]) == (2, 2, 0, 0)
    assert result.rows == {"b": 2}


def test_without_a_commit_the_rows_wait_and_the_job_has_failed(emp, tmp_path):
    result = run(loading(tmp_path, "1;ann;1.5;2024-01-31\n", with_commit=False))
    assert (result.status, result.failed_component) == ("failed", CONN)
    assert emp.stored(EMP) == []


def test_a_line_that_cannot_be_read_fails_the_job_names_its_line_and_stores_nothing(emp, tmp_path):
    result = run(loading(tmp_path, "1;ann;1.5;2024-01-31\n2;bob;not a number;2024-02-01\n"))
    assert (result.status, result.failed_component) == ("failed", "b")
    assert "not a number" in result.error and f"line 2 of {tmp_path / 'load.dat'}" in result.error
    assert emp.stored(EMP) == []
    assert emp.sessions[0].asked == []


def test_a_file_that_is_not_there_fails_the_job(emp, tmp_path):
    made = loading(tmp_path, "")
    made["components"][1]["config"]["data"] = str(tmp_path / "nope.dat")
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "b")
    assert "nope.dat" in result.error


def test_the_terminator_the_enclosure_and_the_encoding_of_the_file(emp, tmp_path):
    made = loading(tmp_path, '1|"a|b"|1.5|2024-01-31\n2|caf\u00e9|2.5|\n', terminator_value="|", use_fields_enclosure=True,
                   encoding="WE8ISO8859P15", written_in="iso-8859-15")
    result = run(made)
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "a|b", 1.5, "2024-01-31 00:00:00"), (2, "caf\u00e9", 2.5, None)]


@pytest.mark.parametrize("options, kept", [
    (["SKIP", "1"], [2, 3]), (["LOAD", "2"], [1, 2]), (["SKIP", "1", "LOAD", "1"], [2]), (["skip", " 2 "], [3]),
    (["DIRECT", "true", "BINDSIZE", "256000", "PARALLEL", "true"], [1, 2, 3]),
])
def test_lines_left_out_at_the_start_and_the_most_rows_read(emp, tmp_path, options, kept):
    result = run(loading(tmp_path, "1;a;;\n2;b;;\n3;c;;\n", options=options))
    assert result.status == "success", result.error
    assert [row[0] for row in emp.stored(EMP)] == kept


def test_rows_a_round_trip_takes(emp, tmp_path):
    run(loading(tmp_path, "1;a;;\n2;b;;\n3;c;;\n", options=["ROWS", "2"]))
    assert [did[2] for did in emp.sessions[0].did if isinstance(did, tuple) and did[0] == "many"] == [2, 1]
    run(loading(tmp_path, "4;a;;\n5;b;;\n6;c;;\n", data_action="APPEND"))
    assert [did[2] for did in emp.sessions[1].did if isinstance(did, tuple) and did[0] == "many"] == [3]


# ------------------------------------------------------------------
# What the load does to the rows the table holds
# ------------------------------------------------------------------

def test_insert_needs_the_table_to_be_empty(emp, tmp_path):
    before(emp, (9, "old", None, None))
    result = run(loading(tmp_path, "1;ann;;\n"))
    assert (result.status, result.failed_component) == ("failed", "b")
    assert result.failures["b"] == ("`data_action` INSERT has SQL*Loader's meaning: the table has to be empty, and it "
                                    "holds rows. APPEND adds to them, REPLACE deletes them first")
    assert emp.stored(EMP) == [(9, "old", None, None)]


def test_append_adds_to_what_the_table_holds(emp, tmp_path):
    before(emp, (9, "old", None, None))
    assert run(loading(tmp_path, "1;ann;;\n", data_action="APPEND")).status == "success"
    assert [row[0] for row in emp.stored(EMP)] == [1, 9]


def test_replace_deletes_every_row_first_and_is_taken_back_with_the_rows(emp, tmp_path):
    before(emp, (9, "old", None, None))
    result = run(loading(tmp_path, "1;much too long a name;;\n", data_action="REPLACE"))
    assert result.status == "failed" and emp.stored(EMP) == [(9, "old", None, None)]
    assert run(loading(tmp_path, "1;ann;;\n", data_action="REPLACE")).status == "success"
    assert [row[0] for row in emp.stored(EMP)] == [1]
    assert "delete from emp" in emp.sessions[1].asked


def test_truncate_empties_the_table_first(emp, tmp_path):
    before(emp, (9, "old", None, None))
    assert run(loading(tmp_path, "1;ann;;\n", data_action="TRUNCATE")).status == "success"
    assert [row[0] for row in emp.stored(EMP)] == [1]
    assert emp.sessions[0].asked[0] == "truncate table emp"


def test_an_action_on_the_table_comes_before_what_the_load_does_to_its_rows(emp, tmp_path):
    before(emp, (9, "old", None, None))
    made = loading(tmp_path, "1;ann;;\n", table_action="CLEAR", data_action="INSERT")
    assert run(made).status == "success"
    assert [row[0] for row in emp.stored(EMP)] == [1]
    # A table that is made is empty: the load's own emptying is not asked for as well.
    made = loading(tmp_path, "2;bob;;\n", table="fresh", table_action="CREATE", data_action="TRUNCATE")
    assert run(made).status == "success"
    assert [statement.split()[0] for statement in emp.sessions[1].asked if statement.split()[0] in ("truncate", "create", "delete")] == ["create"]


# ------------------------------------------------------------------
# Rows the database refuses
# ------------------------------------------------------------------

def test_a_row_the_database_refuses_fails_the_job(emp, tmp_path):
    result = run(loading(tmp_path, "1;ann;;\n1;again;;\n"))
    assert (result.status, result.failed_component) == ("failed", "b")
    assert result.failures["b"] == "the database refused row 2 of the rows it was handed: UNIQUE constraint failed: emp.id"
    assert emp.stored(EMP) == []


def test_as_many_rows_may_be_refused_as_the_load_allows(emp, tmp_path, caplog):
    text = "1;ann;;\n1;again;;\n2;much too long;;\n3;cy;;\n"
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result = run(loading(tmp_path, text, options=["ERRORS", "2"]))
    assert result.status == "success", result.error
    assert [row[0] for row in emp.stored(EMP)] == [1, 3]
    held = result.global_map
    assert (held["b_NB_LINE_DATA"], held["b_NB_LINE_INSERTED"], held["b_NB_LINE_BAD"], held["b_RETURN_CODE"]) == (4, 2, 2, 2)
    assert "the database refused 2 of the 4 rows" in caplog.text


def test_one_refused_row_more_than_the_load_allows_fails_the_job(emp, tmp_path):
    text = "1;ann;;\n1;again;;\n2;much too long;;\n3;cy;;\n"
    result = run(loading(tmp_path, text, options=["ERRORS", "1", "ROWS", "1"]))
    assert (result.status, result.failed_component) == ("failed", "b")
    assert result.failures["b"].startswith("the database refused row 2 of the rows it was handed")
    assert emp.stored(EMP) == []
    assert run(loading(tmp_path, text, options=["ERRORS", "0"])).status == "failed"


def test_with_die_on_error_off_and_no_number_allowed_refused_rows_are_left_out(emp, tmp_path):
    result = run(loading(tmp_path, "1;ann;;\n1;again;;\n", die_on_error=False))
    assert result.status == "success", result.error
    assert result.global_map["b_NB_LINE_BAD"] == 1


# ------------------------------------------------------------------
# A flow leading to it, and a session of its own
# ------------------------------------------------------------------

def test_with_a_flow_leading_to_it_it_stores_that_flows_rows_and_reads_no_file(emp, tmp_path):
    (tmp_path / "in.csv").write_text("5;eve;5.5;2024-03-01\n")
    components = [connection(schema_db=""), reader(ROWS, path=str(tmp_path / "in.csv")),
                  bulk(inputs=("row1",), data=str(tmp_path / "never_read.dat"), fields_terminator="WHITESPACE"),
                  {"id": "c", "type": "tOracleCommit", "config": {"connection": CONN}, "inputs": [], "outputs": []}]
    result = run(job(components, [flow("row1", "in", "b")], triggers=after(CONN, "in", "c")))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(5, "eve", 5.5, "2024-03-01 00:00:00")]


def test_with_a_session_of_its_own_the_rows_are_stored_when_the_load_is_done(emp, tmp_path):
    (tmp_path / "load.dat").write_text("1;ann;;\n")
    made = job([bulk(data=str(tmp_path / "load.dat"), use_existing_connection=False, connection="",
                     **{**BLOCK, "schema_db": ""})], [])
    assert run(made).status == "success"
    assert [row[0] for row in emp.stored(EMP)] == [1]
    assert emp.sessions[0].did[-2:] == ["commit", "close"]


# ------------------------------------------------------------------
# What refuses the job
# ------------------------------------------------------------------

def test_what_refuses_the_job_when_it_loads(emp, tmp_path):
    def of(**config):
        return refusals(job([connection(), bulk(**{"data": "load.dat", **config})], []))

    assert of(data="") == ["data: names no file, and no flow leads to it: it has no rows to store"]
    assert of(data_action="UPDATE") == [
        "data_action: a load updates no rows; use an Oracle output with `data_action` UPDATE"]
    assert of(fields_terminator="WHITESPACE") == [
        "fields_terminator: WHITESPACE is not read; fields end at `terminator_value` (`OTHER`)"]
    assert of(options=["ROWS"]) == [
        "options: the options are a name and then its value, and the list has an odd number of entries"]
    assert of(options=["ERRORS", "few"]) == ["options: ERRORS is to be a whole number"]
    assert of(encoding="KLINGON8") == [
        "encoding: 'KLINGON8' is no encoding v2 knows: give Oracle's name (UTF8, WE8ISO8859P15, WE8MSWIN1252) or Python's"]
    assert of(advanced_separator=True) == [
        "advanced_separator: numbers are read with a point and no thousands separator; write the file so, or read "
        "it with a delimited file input"]
    assert of(use_existing_clt_file=True) == [
        "use_existing_clt_file: a control file of SQL*Loader's is not read: no loader is run"]
    assert of(input_into_table_clause=True) == [
        "input_into_table_clause: a clause of SQL*Loader's control file is not read: no loader is run"]
    assert of(record_format="FIXED") == ["record_format: only the default record format is read: a line a record"]
    assert of(table_action="TRUNCATE_REUSE_STORAGE")[0].startswith("table_action: 'TRUNCATE_REUSE_STORAGE' is not allowed")
    assert of(table="") == ["table: names no table"]
    assert of(terminator_value="") == [
        "data: the file cannot be read as the keys say: fieldseparator: must not be empty"]


def test_what_talend_writes_and_changes_nothing_here_is_taken(emp, tmp_path):
    made = job([connection(), bulk(
        data="load.dat", advanced_separator=False, thousands_separator=",", decimal_separator=".", use_existing_clt_file=False,
        clt_file="", record_format="DEFAULT", input_into_table_clause=False, use_date_pattern=False, preserve_blanks=False,
        trailing_nullcols=False, nls_language="DEFAULT", nls_date_language="DEFAULT", nls_territory="DEFAULT",
        set_nls_territory=True, output="OUTPUT_TO_CONSOLE", convert_column_table_to_uppercase=False, encoding="UTF8",
        options=[])], [])
    load_job(made, registry=WITH_DOES)
