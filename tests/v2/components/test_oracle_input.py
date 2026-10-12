"""Oracle input: the rows of a query. On SQLite, behind the seam, for what is no database's own."""
import logging
import sqlite3

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, writer
from tests.v2.components.test_oracle_connection import BLOCK, after, connection
from tests.v2.database import WITH_DOES, on_sqlite  # noqa: F401 -- a fixture

ROWS = "id:int, name:str, amt:Decimal#2"
QUERY = "select id, name, amt from emp order by id"


@pytest.fixture
def emp(on_sqlite):
    held = sqlite3.connect(on_sqlite.path)
    held.execute("create table emp (id, name, amt, joined, flag)")
    held.executemany("insert into emp values (?, ?, ?, ?, ?)", [
        (1, "ann ", 1.5, "2024-01-31", 1), (2, None, 2.255, "2024-02-01", 0), (3, " bob", None, "not a day", None)])
    held.commit()
    held.close()
    return on_sqlite


def reads(schema=ROWS, component_id="in", outputs=("row1",), kind="tOracleInput", **config):
    made = {"use_existing_connection": True, "connection": "tDBConnection_1", "query": QUERY, **config}
    return {"id": component_id, "type": kind, "config": made, "schema": {"input": [], "output": columns(schema)},
            "inputs": [], "outputs": list(outputs)}


def to_file(tmp_path, schema=ROWS, **config):
    """connection -> a query -> a file."""
    out = str(tmp_path / "out.csv")
    components = [connection(), reads(schema, **config), writer(schema, path=out, inputs=("row1",))]
    return out, job(components, [flow("row1", "in", "out")], triggers=after("tDBConnection_1", "in"))


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

@pytest.mark.parametrize("kind", ["oracle_input", "OracleInput", "tOracleInput"])
def test_the_rows_of_the_query_as_the_columns_the_job_declares(emp, tmp_path, kind):
    out, made = to_file(tmp_path, kind=kind)
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out) == ["id;name;amt", "1;ann ;1.50", "2;;2.26", "3; bob;"]
    assert result.rows == {"out": 3}


def scratch_files(monkeypatch):
    """Each scratch file a database input hands to Polars, as it is then: what Polars was asked beside it, its
    rows, how many rows each of its groups holds, and how each column is packed."""
    import polars as pl
    from pyarrow import parquet

    from src.v2.components.database import reading

    seen = []

    def scanned(path, **asked):
        described = parquet.ParquetFile(path).metadata
        # How each column of the first group is packed, by the column's name.
        packed = {described.row_group(0).column(at).path_in_schema: described.row_group(0).column(at).encodings
                  for at in range(described.num_columns)} if described.num_row_groups else {}
        seen.append((asked, parquet.read_table(path), [described.row_group(at).num_rows for at in range(described.num_row_groups)],
                     packed))
        return scan(path, **asked)

    scan = pl.scan_parquet
    monkeypatch.setattr(reading.pl, "scan_parquet", scanned)
    return seen


def test_each_rows_number_rests_in_the_scratch_file_and_polars_is_not_asked_to_number_them(emp, tmp_path, monkeypatch, caplog):
    """Polars 1.44 holds about twice as much when it numbers the rows of a Parquet file as it scans one: 1.1 GB
    for ten million rows where 0.5 GB does without. Measured on 2026-10-12."""
    from src.v2.rows import row_column

    seen = scratch_files(monkeypatch)
    # A row a round trip: the numbers go on from one batch to the next.
    out, made = to_file(tmp_path, use_cursor=True, cursor_size=1)
    with caplog.at_level(logging.DEBUG, logger="src.v2"):
        result = run(made)
    assert result.status == "success", result.error
    assert lines(out) == ["id;name;amt", "1;ann ;1.50", "2;;2.26", "3; bob;"]
    asked, held, groups, packed = seen[0]
    assert asked == {}
    # Neither as it scans the file nor after: the plan Polars runs numbers no row.
    (plan,) = [record.getMessage() for record in caplog.records if "plan of output out" in record.getMessage()]
    assert "Parquet SCAN" in plan and "ROW_INDEX" not in plan and "ROW INDEX" not in plan
    assert held.schema.names == [row_column("in"), "id", "name", "amt"]
    assert (str(held.schema.types[0]), held.column(0).to_pylist()) == ("uint32", [1, 2, 3])
    # The numbers are packed as steps, which takes next to nothing; the other columns keep their dictionaries.
    assert "DELTA_BINARY_PACKED" in packed[row_column("in")] and "RLE_DICTIONARY" not in packed[row_column("in")]
    assert "RLE_DICTIONARY" in packed["name"] and "RLE_DICTIONARY" in packed["id"]


@pytest.mark.parametrize("sizes, size, groups", [
    ([3], 2, [2, 1]), ([1, 1, 1], 2, [2, 1]), ([5], 2, [2, 2, 1]), ([3, 1, 0, 5], 2, [2, 2, 2, 2, 1]), ([2, 2], 2, [2, 2]),
    ([7], 1, [1] * 7), ([1, 2], 10, [3]), ([], 2, []), ([0, 0], 2, []),
])
def test_rows_that_come_in_batches_of_any_size_are_handed_on_in_groups_of_one_size_and_in_their_order(sizes, size, groups):
    import pyarrow

    from src.v2.components.database.reading import _groups

    numbers = iter(range(1, 1000))
    batches = [pyarrow.table({"n": pyarrow.array([next(numbers) for _ in range(rows)], type=pyarrow.int64())}) for rows in sizes]
    made = list(_groups(iter(batches), size))
    assert [group.num_rows for group in made] == groups
    assert [value for group in made for value in group.column("n").to_pylist()] == list(range(1, sum(sizes) + 1))


def test_a_group_that_is_full_is_handed_on_before_more_rows_are_asked_for():
    import pyarrow

    from src.v2.components.database.reading import _groups

    asked = []

    def batches():
        for at in range(3):
            asked.append(at)
            yield pyarrow.table({"n": pyarrow.array([at, at], type=pyarrow.int64())})

    made = _groups(batches(), 2)
    assert next(made).num_rows == 2 and asked == [0]


def test_a_query_that_hands_back_no_row_leaves_a_scratch_file_of_no_group_that_reads_as_no_rows(emp, tmp_path, monkeypatch):
    seen = scratch_files(monkeypatch)
    out, made = to_file(tmp_path, query="select id, name, amt from emp where id > 99")
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out) == ["id;name;amt"] and result.rows == {"out": 0}
    _, held, groups, _ = seen[0]
    assert groups == [] and held.num_rows == 0


@pytest.mark.parametrize("a_round_trip", [1, 2, 3, 50])
def test_the_scratch_file_is_laid_out_the_engines_way_whatever_a_round_trip_brings(emp, tmp_path, monkeypatch, a_round_trip):
    """A thousand rows a round trip, as Talend has it, made a group of the file for every thousand rows, and writing
    ten million rows took 24 seconds where 14 do. Many rows a round trip made groups of that many, and the engine's
    pass holds several groups at a time: 1.5 GB for thirty million rows where 0.6 GB does. Measured on 2026-10-12."""
    from src.v2.components.database import reading

    monkeypatch.setattr(reading, "_GROUP", 2)
    seen = scratch_files(monkeypatch)
    out, made = to_file(tmp_path, use_cursor=True, cursor_size=a_round_trip)
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out) == ["id;name;amt", "1;ann ;1.50", "2;;2.26", "3; bob;"]
    _, held, groups, _ = seen[0]
    assert groups == [2, 1] and held.column(0).to_pylist() == [1, 2, 3]


def test_a_row_far_into_the_result_is_named_by_its_own_number(on_sqlite, tmp_path, monkeypatch):
    """The numbers are written packed (each as its step from the one before) and read back by Polars: held here
    across twelve groups of the file, of ten thousand rows each. (With fifty thousand the engine's pass over thirty
    million rows held 1.5 GB where it holds 0.6 GB; measured on 2026-10-12.)"""
    seen = scratch_files(monkeypatch)
    held = sqlite3.connect(on_sqlite.path)
    held.execute("create table long (id, joined)")
    held.executemany("insert into long values (?, ?)", [(at, "not a day" if at == 100_001 else "2024-01-31")
                                                         for at in range(1, 120_001)])
    held.commit()
    held.close()
    out, made = to_file(tmp_path, "id:int, joined:datetime@%Y-%m-%d", query="select id, joined from long order by id")
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert "not a day" in result.error and result.error.endswith("row 100001 of the result of in")
    assert seen[0][2] == [10_000] * 12
    made["components"][1]["config"]["die_on_error"] = False
    result = run(made)
    assert result.status == "success", result.error
    assert len(lines(out)) == 120_000 and lines(out)[100_000] == "100000;2024-01-31" and lines(out)[100_001] == "100002;2024-01-31"


def test_the_query_is_run_once_and_the_session_is_left_as_it_was(emp, tmp_path):
    out, made = to_file(tmp_path)
    run(made)
    session, = emp.sessions
    assert [did[0] for did in session.did if isinstance(did, tuple)] == ["fields", "query"]
    # It changed nothing, so nothing waits: the job closes the session and has not failed.
    assert session.did[-1] == "close" and "commit" not in session.did and "rollback" not in session.did
    assert session.did.count("close") == 1


def test_the_session_of_a_connection_is_there_for_what_comes_after_the_reading(emp, tmp_path):
    out, made = to_file(tmp_path)
    made["components"] += [
        {"id": "d", "type": "does", "config": {"connection": "tDBConnection_1", "statement": "insert into t values (9)"},
         "inputs": [], "outputs": []},
        {"id": "c", "type": "tOracleCommit", "config": {"connection": "tDBConnection_1"}, "inputs": [], "outputs": []}]
    made["triggers"] += after("in", "d", "c")
    result = run(made)
    assert result.status == "success", result.error
    assert emp.stored() == [(9,)]


def test_columns_are_taken_by_their_place_whatever_the_query_calls_them(emp, tmp_path):
    out, made = to_file(tmp_path, schema="a:int, a2:int, c:str",
                        query="select id, id, name as id from emp where id = 1")
    assert run(made).status == "success"
    assert lines(out) == ["a;a2;c", "1;1;ann "]


def test_a_query_with_no_row_gives_no_row(emp, tmp_path):
    out, made = to_file(tmp_path, query="select id, name, amt from emp where id > 99")
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out) == ["id;name;amt"]


def test_it_reads_with_a_session_of_its_own_and_closes_it_when_the_rows_are_in(emp, tmp_path):
    out = str(tmp_path / "out.csv")
    made = job([reads(use_existing_connection=False, connection="", **BLOCK), writer(ROWS, path=out, inputs=("row1",))],
               [flow("row1", "in", "out")])
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out)[1:] == ["1;ann ;1.50", "2;;2.26", "3; bob;"]
    (config, opened_by, _, _, _), = emp.asked
    assert (opened_by, config["host"]) == ("in", "db.example")
    assert emp.sessions[0].did[-1] == "close"
    assert emp.sessions[0].did.index("close") < len(emp.sessions[0].did)


def test_a_session_of_its_own_is_closed_when_the_query_fails(emp, tmp_path):
    out, made = to_file(tmp_path, query="select nope from emp")
    made["components"][1]["config"].update(use_existing_connection=False, **BLOCK)
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert "no such column: nope" in result.error
    assert emp.sessions[-1].closed


# ------------------------------------------------------------------
# Values in the query
# ------------------------------------------------------------------

def test_a_value_in_quotes_is_bound_and_one_outside_quotes_is_a_name_or_a_number(emp, tmp_path):
    out, made = to_file(tmp_path, query="select id, name, amt from ${context.t} where name = '${context.who}' and id < ${context.n}")
    made["context"] = {"t": "emp", "who": "ann ", "n": 5}
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out)[1:] == ["1;ann ;1.50"]
    sent = [did for did in emp.sessions[0].did if isinstance(did, tuple) and did[0] == "query"][0]
    assert sent[1:] == ("select id, name, amt from emp where name = :context_who and id < 5", {"context_who": "ann "})
    assert result.global_map["in_QUERY"] == "select id, name, amt from emp where name = :context_who and id < 5"


def test_as_talend_joins_it(emp, tmp_path):
    written = '"select id, name, amt from " + context.t + " where name like \'%" + context.part + "%\' order by id"'
    out, made = to_file(tmp_path, query=written)
    made["context"] = {"t": "emp", "part": "b"}
    assert run(made).status == "success"
    assert lines(out)[1:] == ["3; bob;"]


def test_a_value_that_would_change_the_query_fails_it_and_is_shown_nowhere(emp, tmp_path, caplog):
    out, made = to_file(tmp_path, query="select id, name, amt from emp where id = ${context.n}")
    made["context"] = {"n": "1 or 1=1"}
    with caplog.at_level(logging.DEBUG, logger="src.v2"):
        result = run(made)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert result.error.startswith("what context.n holds is written into the statement")
    assert "1 or 1=1" not in result.error
    assert not [did for did in emp.sessions[0].did if isinstance(did, tuple)]


def test_a_value_is_looked_up_when_the_query_runs(emp, tmp_path):
    """So an entry an earlier subjob left is seen."""
    out, made = to_file(tmp_path, query='"select id, name, amt from emp where id = " + ((Integer)globalMap.get("wanted"))')
    made["components"].insert(0, {"id": "set", "type": "SetGlobalVar", "config": {"variables": [{"key": "wanted", "value": 2}]}})
    made["triggers"].append({"type": "OnSubjobOk", "from": "set", "to": "tDBConnection_1"})
    assert run(made).status == "success"
    assert lines(out)[1:] == ["2;;2.26"]


# ------------------------------------------------------------------
# Types
# ------------------------------------------------------------------

def test_text_that_is_declared_as_something_else_is_read_as_a_files_text_is(emp, tmp_path):
    out, made = to_file(tmp_path, schema="id:int, day:datetime@%Y-%m-%d",
                        query="select id, joined from emp where id < 3 order by id")
    assert run(made).status == "success"
    assert lines(out) == ["id;day", "1;2024-01-31", "2;2024-02-01"]


def test_text_that_is_none_of_its_type_fails_the_job_and_names_the_row(emp, tmp_path):
    out, made = to_file(tmp_path, schema="id:int, day:datetime@%Y-%m-%d", query="select id, joined from emp order by id")
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert "not a day" in result.error and "row 3 of the result of in" in result.error


def test_with_die_on_error_off_such_a_row_leaves_by_the_reject_output(emp, tmp_path):
    schema = "id:int, day:datetime@%Y-%m-%d"
    out, rej = str(tmp_path / "out.csv"), str(tmp_path / "rej.csv")
    components = [connection(), reads(schema, outputs=("row1", "bad"), query="select id, joined from emp order by id",
                                      die_on_error=False),
                  writer(schema, path=out, inputs=("row1",)),
                  writer("id:str, day:str, errorCode:str, errorMessage:str", component_id="rej", path=rej, inputs=("bad",))]
    made = job(components, [flow("row1", "in", "out"), flow("bad", "in", "rej", kind="reject")],
               triggers=after("tDBConnection_1", "in"))
    result = run(made)
    assert result.status == "success", result.error
    assert lines(out)[1:] == ["1;2024-01-31", "2;2024-02-01"]
    assert lines(rej)[1].startswith("3;not a day;TYPE_CONVERSION;")


def test_a_true_or_false_comes_from_a_number(emp, tmp_path):
    out, made = to_file(tmp_path, schema="id:int, ok:bool", query="select id, flag from emp order by id")
    assert run(made).status == "success"
    assert lines(out) == ["id;ok", "1;true", "2;false", "3;"]


def test_a_query_that_does_not_go_with_the_declared_columns_fails_before_it_is_run(emp, tmp_path):
    out, made = to_file(tmp_path, query="select id, name from emp")
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert result.error == ("the query hands back 2 column(s) and the job declares 3: they are taken by their place, "
                            "so there have to be as many")
    assert not [did for did in emp.sessions[0].did if isinstance(did, tuple) and did[0] == "query"]


# ------------------------------------------------------------------
# Trims and missing text
# ------------------------------------------------------------------

def test_every_text_column_is_stripped_when_asked(emp, tmp_path):
    out, made = to_file(tmp_path, trim_all_column=True)
    run(made)
    assert lines(out)[1:] == ["1;ann;1.50", "2;;2.26", "3;bob;"]


@pytest.mark.parametrize("written, stripped", [
    # As the converter writes the table: one object a cell.
    ([{"schema_column": "id"}, {"trim": "false"}, {"schema_column": "name"}, {"trim": "true"}], True),
    ([{"schema_column": "id"}, {"trim": "false"}, {"schema_column": "name"}, {"trim": "false"}], False),
    ([{"schema_column": "name", "trim": True}], True),
    ([{"column": "name", "trim": "TRUE"}], True),
    ([{"schema_column": "name"}], False),
    ([], False),
])
def test_a_column_is_stripped_when_its_own_switch_says_so(emp, tmp_path, written, stripped):
    out, made = to_file(tmp_path, trim_column=written)
    run(made)
    assert lines(out)[1] == ("1;ann;1.50" if stripped else "1;ann ;1.50")


def test_missing_text_is_empty_text_when_asked(emp, tmp_path):
    schema = "id:int, name:str!, amt:Decimal#2"
    out, made = to_file(tmp_path, schema=schema)
    assert "NULL values" in run(made).error
    out, made = to_file(tmp_path, schema=schema, no_null_values=True)
    assert run(made).status == "success"
    assert lines(out)[1:] == ["1;ann ;1.50", "2;;2.26", "3; bob;"]


# ------------------------------------------------------------------
# How many rows a round trip brings, and where a row is
# ------------------------------------------------------------------

def test_rows_are_fetched_as_many_at_a_time_as_the_job_says(emp, tmp_path):
    out, made = to_file(tmp_path, use_cursor=True, cursor_size=2)
    run(made)
    assert emp.sessions[0].did.count("batch") == 2
    assert lines(out)[1:] == ["1;ann ;1.50", "2;;2.26", "3; bob;"]
    out, made = to_file(tmp_path, cursor_size=2)
    run(made)
    assert emp.sessions[1].did.count("batch") == 1


def test_a_run_for_one_row_asks_the_database_once(emp, tmp_path):
    out, made = to_file(tmp_path)
    result = run(made, run={"only": {"source": "in", "rows": [2]}})
    assert result.status == "success", result.error
    assert lines(out)[1:] == ["2;;2.26"]
    assert result.only == {"source": "in", "rows": ["row 2 of the result of in"]}
    assert [did[0] for did in emp.sessions[0].did if isinstance(did, tuple)] == ["fields", "query"]


def test_its_rows_have_no_lines(emp, tmp_path):
    out, made = to_file(tmp_path)
    with pytest.raises(JobRefusedError) as refused:
        run(made, run={"only": {"source": "in", "lines": [2]}})
    assert "reads the rows of a query" in refused.value.report.format()


# ------------------------------------------------------------------
# What refuses the job
# ------------------------------------------------------------------

def test_what_refuses_the_job_when_it_loads(emp, tmp_path):
    bare = reads()
    bare["schema"] = {"input": [], "output": []}
    assert refusals(job([connection(), bare], [])) == ["schema: a database input needs its columns declared"]
    unasked = reads()
    del unasked["config"]["query"]
    assert refusals(job([connection(), unasked], [])) == ["query: required config key is missing"]
    assert refusals(job([reads(connection="nope")], [])) == [
        "connection: the job has no component 'nope', and no Oracle connection"]
    assert refusals(job([reads(use_existing_connection=False, host="", user="app", password="x")], [])) == [
        "host: is empty; a session is opened with a host and a SID", "dbname: is empty; a session is opened with a host and a SID"]
    joined = '"select * from t where d = \'" + TalendDate.getDate("yyyy") + "\'"'
    assert refusals(job([connection(), reads(query=joined)], [])) == [
        "query: the statement is joined as Java joins text, and holds more than text, context variables and entries "
        "of globalMap: v2 runs no Java. Write it as one text, with ${context.name} where a value goes"]
    assert refusals(job([connection(), reads(cursor_size=0)], [])) == [
        "cursor_size: 0 rows cannot be fetched at a time; give 1 or more"]
    assert refusals(job([connection(), reads(cursor_size="many")], [])) == ["cursor_size: 'many' is no number of rows"]
    assert refusals(job([connection(), reads(trim_column=["name"])], [])) == [
        "trim_column: 'name' is no entry: give objects with `schema_column` and `trim`"]
    assert refusals(job([connection(), reads(trim_column=[{"trim": "true"}])], [])) == [
        "trim_column: a `trim` stands before any `schema_column`: say which column it is for"]


def test_a_block_it_does_not_read_is_not_judged(emp, tmp_path):
    # With a connection component named, its own block may hold what Talend left there.
    made = job([connection(), reads(host="", password="enc:system.encryption.key.v1:AbCd")], [])
    load_job(made, registry=WITH_DOES)
