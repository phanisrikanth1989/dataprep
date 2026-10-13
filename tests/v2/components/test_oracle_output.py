"""Oracle output: rows stored in a table. On SQLite, behind the seam, for what is no database's own."""
import logging
import sqlite3

import pytest

from src.v2 import load_job, run_job
from src.v2.components.database import oracle_output
from src.v2.errors import JobRefusedError
from src.v2.job.model import Column
from tests.v2.components.kit import columns, flow, job, reader, writer
from tests.v2.components.test_oracle_connection import BLOCK, after, connection
from tests.v2.database import WITH_DOES, on_sqlite  # noqa: F401 -- a fixture

ROWS = "id:int, name:str, amt:float"
EMP = "select id, name, amt from emp order by id"


@pytest.fixture
def emp(on_sqlite):
    held = sqlite3.connect(on_sqlite.path)
    held.execute("create table emp (id integer primary key, name text check (length(name) < 8), amt real)")
    held.executemany("insert into emp values (?, ?, ?)", [(1, "ann", 1.5), (2, "bob", 2.5)])
    held.commit()
    held.close()
    return on_sqlite


def keyed(schema=ROWS, key="id"):
    made = columns(schema)
    for column in made:
        column["key"] = column["name"] in key.split(",")
    return made


def stores(schema=ROWS, key="id", component_id="db", kind="tOracleOutput", **config):
    made = {"use_existing_connection": True, "connection": "tDBConnection_1", "table": "emp", **config}
    return {"id": component_id, "type": kind, "config": made, "schema": {"input": keyed(schema, key), "output": []},
            "inputs": ["row1"], "outputs": []}


def loading(tmp_path, rows, schema=ROWS, commit=True, own=False, **config):
    """a file -> the table, on the session of a connection that a commit stores; or on a session of its own."""
    (tmp_path / "in.csv").write_text(rows)
    source = reader(schema, path=str(tmp_path / "in.csv"), die_on_error=True)
    if own:
        return job([source, stores(schema, use_existing_connection=False, connection="", **{**BLOCK, "schema_db": ""},
                                   **config)], [flow("row1", "in", "db")])
    components = [connection(schema_db=""), source, stores(schema, **config)]
    ids = ["tDBConnection_1", "in"]
    if commit:
        components.append({"id": "c", "type": "tOracleCommit", "config": {"connection": "tDBConnection_1"},
                           "inputs": [], "outputs": []})
        ids.append("c")
    return job(components, [flow("row1", "in", "db")], triggers=after(*ids))


def run(made, **more):
    return run_job(made, registry=WITH_DOES, **more)


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made, registry=WITH_DOES)
    return [f"{refusal.key}: {refusal.reason}" for refusal in refused.value.report]


# ------------------------------------------------------------------
# What each row does
# ------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["oracle_output", "OracleOutput", "tOracleOutput"])
def test_rows_are_inserted_and_wait_for_the_commit(emp, tmp_path, kind):
    made = loading(tmp_path, "3;cy;3.5\n4;di;\n", commit=False)
    made["components"][2]["type"] = kind
    result = run(made)
    # Loaded and never stored: the job has failed, and the table is as it was.
    assert (result.status, result.failed_component) == ("failed", "tDBConnection_1")
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bob", 2.5)]
    result = run(loading(tmp_path, "3;cy;3.5\n4;di;\n"))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bob", 2.5), (3, "cy", 3.5), (4, "di", None)]
    assert result.rows == {"db": 2}


def test_with_a_session_of_its_own_the_rows_are_stored_when_the_subjob_is_done(emp, tmp_path):
    result = run(loading(tmp_path, "3;cy;3.5\n", own=True))
    assert result.status == "success", result.error
    assert emp.stored(EMP)[-1] == (3, "cy", 3.5)
    session, = emp.sessions
    assert session.opened_by == "db" and session.did[-2:] == ["commit", "close"]


def test_what_it_sends_is_one_statement_for_a_batch_with_its_values_by_place(emp, tmp_path):
    run(loading(tmp_path, "3;cy;3.5\n4;di;4.5\n5;ed;5.5\n", batch_size=2))
    sent = [did[1:] for did in emp.sessions[0].did if isinstance(did, tuple) and did[0] == "many"]
    assert sent == [("insert into emp (id, name, amt) values (:1, :2, :3)", 2),
                    ("insert into emp (id, name, amt) values (:1, :2, :3)", 1)]


def test_rows_update_the_row_with_their_key(emp, tmp_path):
    result = run(loading(tmp_path, "2;bo;9.5\n7;nobody;1.0\n", data_action="UPDATE"))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bo", 9.5)]
    assert emp.sessions[0].asked.count("update emp set name = :1, amt = :2 where id = :3") == 1
    assert (result.global_map["db_NB_LINE_UPDATED"], result.global_map["db_NB_LINE_INSERTED"]) == (1, 0)


def test_rows_delete_the_row_with_their_key(emp, tmp_path):
    result = run(loading(tmp_path, "2;x;0\n7;y;0\n", data_action="DELETE"))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann", 1.5)]
    assert "delete from emp where id = :1" in emp.sessions[0].asked
    assert result.global_map["db_NB_LINE_DELETED"] == 1


@pytest.mark.parametrize("action", ["UPDATE_OR_INSERT", "INSERT_OR_UPDATE"])
def test_a_row_updates_the_row_with_its_key_or_is_inserted_when_there_is_none(emp, tmp_path, action):
    result = run(loading(tmp_path, "2;bo;9.5\n3;cy;3.5\n", data_action=action))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bo", 9.5), (3, "cy", 3.5)]
    assert (result.global_map["db_NB_LINE_UPDATED"], result.global_map["db_NB_LINE_INSERTED"]) == (1, 1)


def test_a_key_that_comes_twice_is_inserted_once_and_then_updated_in_the_order_of_the_rows(emp, tmp_path):
    rows = "5;first;1.0\n2;bo;9.5\n5;second;2.0\n6;six;6.0\n5;third;3.0\n"
    result = run(loading(tmp_path, rows, data_action="UPDATE_OR_INSERT"))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bo", 9.5), (5, "third", 3.0), (6, "six", 6.0)]
    assert (result.global_map["db_NB_LINE_UPDATED"], result.global_map["db_NB_LINE_INSERTED"]) == (3, 2)


def test_a_key_of_several_columns(emp, tmp_path):
    held = sqlite3.connect(emp.path)
    held.execute("create table pay (who, day, amt)")
    held.executemany("insert into pay values (?, ?, ?)", [("ann", "mon", 1.0), ("ann", "tue", 2.0)])
    held.commit()
    held.close()
    made = loading(tmp_path, "ann;tue;9.0\nbob;mon;5.0\n", schema="who:str, day:str, amt:float", table="pay",
                   data_action="UPDATE_OR_INSERT")
    made["components"][2]["schema"]["input"] = keyed("who:str, day:str, amt:float", "who,day")
    assert run(made).status == "success"
    assert emp.stored("select who, day, amt from pay order by who, day") == [
        ("ann", "mon", 1.0), ("ann", "tue", 9.0), ("bob", "mon", 5.0)]
    assert "update pay set amt = :1 where who = :2 and day = :3" in emp.sessions[0].asked


# ------------------------------------------------------------------
# Nothing touches the table for a subjob that fails
# ------------------------------------------------------------------

def test_a_row_that_fails_the_subjob_leaves_the_table_as_it_was(emp, tmp_path):
    result = run(loading(tmp_path, "3;cy;3.5\n4;di;not a number\n", table_action="CLEAR"))
    assert (result.status, result.failed_component) == ("failed", "in")
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bob", 2.5)]
    # No statement was sent: the rows were known not to be whole before the table was touched.
    assert emp.sessions[0].asked == []


def test_another_output_of_the_subjob_that_fails_takes_this_ones_rows_back(emp, tmp_path):
    made = loading(tmp_path, "3;cy;3.5\n", own=True)
    made["components"].append(stores(component_id="db2", table="no_such_table", use_existing_connection=False,
                                     connection="", **{**BLOCK, "schema_db": ""}))
    made["flows"].append(flow("row2", "in", "db2"))
    made["components"][2]["inputs"] = ["row2"]
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "db2")
    assert "no such table" in result.error
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bob", 2.5)]
    assert emp.sessions[0].did[-2:] == ["rollback", "close"]


# ------------------------------------------------------------------
# What is done to the table first
# ------------------------------------------------------------------

def test_clear_deletes_every_row_in_the_same_transaction(emp, tmp_path):
    result = run(loading(tmp_path, "3;cy;3.5\n", table_action="CLEAR"))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(3, "cy", 3.5)]
    assert emp.sessions[0].asked[:3] == ["savepoint v2_subjob", "savepoint v2_output", "delete from emp"]


def test_clear_is_taken_back_with_the_rows(emp, tmp_path):
    result = run(loading(tmp_path, "3;much too long a name;3.5\n", table_action="CLEAR"))
    assert (result.status, result.failed_component) == ("failed", "db")
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bob", 2.5)]


@pytest.mark.parametrize("action, asked", [("TRUNCATE", "truncate table emp"),
                                           ("TRUNCATE_REUSE_STORAGE", "truncate table emp reuse storage")])
def test_truncate_empties_the_table_before_the_rows_go_in(emp, tmp_path, action, asked, caplog):
    with caplog.at_level(logging.INFO, logger="src.v2"):
        result = run(loading(tmp_path, "3;cy;3.5\n", table_action=action))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(3, "cy", 3.5)]
    assert emp.sessions[0].asked[0] == asked
    assert f"[db] {action} on emp is done, and is not taken back if what follows fails" in caplog.text


@pytest.mark.parametrize("action, there, asked", [
    ("CREATE", False, ["create"]), ("CREATE_IF_NOT_EXISTS", False, ["create"]), ("CREATE_IF_NOT_EXISTS", True, ["create"]),
    ("DROP_CREATE", True, ["drop", "create"]), ("DROP_IF_EXISTS_AND_CREATE", True, ["drop", "create"]),
    ("DROP_IF_EXISTS_AND_CREATE", False, ["drop", "create"]),
])
def test_a_table_is_made_from_the_declared_columns(emp, tmp_path, action, there, asked):
    made = loading(tmp_path, "3;cy;3.5\n", table="emp" if there else "fresh", table_action=action)
    result = run(made)
    assert result.status == "success", result.error
    table = "emp" if there else "fresh"
    kept = action == "CREATE_IF_NOT_EXISTS" and there
    assert emp.stored(f"select id, name, amt from {table} order by id") == (
        [(1, "ann", 1.5), (2, "bob", 2.5), (3, "cy", 3.5)] if kept else [(3, "cy", 3.5)])
    defining = [statement.split()[0] for statement in emp.sessions[0].asked if statement.split()[0] in ("drop", "create")]
    assert defining == asked
    create = f"create table {table} (id NUMBER(19), name VARCHAR2(4000 CHAR), amt BINARY_DOUBLE, primary key (id))"
    assert create in emp.sessions[0].asked


@pytest.mark.parametrize("action, said", [("CREATE", "already exists"), ("DROP_CREATE", "no such table")])
def test_a_table_that_is_not_as_the_action_needs_it_fails(emp, tmp_path, action, said):
    made = loading(tmp_path, "3;cy;3.5\n", table="emp" if action == "CREATE" else "fresh", table_action=action)
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "db")
    assert said in result.error


@pytest.mark.parametrize("action", ["CREATE_IF_NOT_EXISTS", "DROP_IF_EXISTS_AND_CREATE"])
def test_only_the_fault_the_action_allows_for_is_let_pass(emp, tmp_path, action):
    # A table that cannot be made for another reason: `order` is a word of the database's own.
    made = loading(tmp_path, "3;cy\n", schema="order:int, name:str", table="fresh", table_action=action)
    made["components"][2]["schema"]["input"] = keyed("order:int, name:str", "")
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "db")
    assert "syntax error" in result.error
    # The table was not made, and nothing was sent to it.
    assert emp.sessions[0].asked[-1].startswith("create table fresh")


def test_an_action_that_defines_is_refused_over_work_that_waits(emp, tmp_path):
    made = loading(tmp_path, "3;cy;3.5\n", table_action="TRUNCATE")
    made["components"].insert(1, {"id": "d", "type": "does", "inputs": [], "outputs": [],
                                  "config": {"connection": "tDBConnection_1", "statement": "insert into t values (1)"}})
    made["triggers"] = after("tDBConnection_1", "d", "in")
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "db")
    assert result.failures["db"] == (
        "`table_action` TRUNCATE is a statement that defines, and Oracle stores what waits on a session before one: "
        "the work of d would be stored with it. Put a commit before this output, or use CLEAR, which is taken back "
        "with the rows")
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bob", 2.5)]
    assert "truncate table emp" not in emp.sessions[0].asked


# ------------------------------------------------------------------
# A row the database refuses
# ------------------------------------------------------------------

def test_a_row_the_database_refuses_fails_the_job_and_is_named(emp, tmp_path):
    result = run(loading(tmp_path, "3;cy;3.5\n1;again;0\n5;much too long;0\n"))
    assert (result.status, result.failed_component) == ("failed", "db")
    assert result.failures["db"] == ("the database refused row 2 of the rows it was handed (id=1): UNIQUE constraint "
                                     "failed: emp.id")
    # The row before it was sent, and is taken back with the subjob.
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bob", 2.5)]


def test_with_die_on_error_off_such_a_row_is_left_out_and_the_others_are_stored(emp, tmp_path, caplog):
    rows = "3;cy;3.5\n1;again;0\n5;much too long;0\n6;ok;6.5\n"
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result = run(loading(tmp_path, rows, die_on_error=False, batch_size=1))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bob", 2.5), (3, "cy", 3.5), (6, "ok", 6.5)]
    told = ("the database refused 2 of the 4 rows it was handed, and they are left out; the first: row 2 of the rows "
            "it was handed (id=1): UNIQUE constraint failed: emp.id")
    assert f"[db] {told}" in caplog.text
    held = result.global_map
    assert held["db_ERROR_MESSAGE"] == told
    assert (held["db_NB_LINE"], held["db_NB_LINE_INSERTED"], held["db_NB_LINE_REJECTED"]) == (4, 2, 2)
    assert result.rows == {"db": 2}


def test_with_die_on_error_off_a_table_that_is_not_there_stores_nothing_and_the_job_goes_on(emp, tmp_path, caplog):
    made = loading(tmp_path, "3;cy;3.5\n", table="no_such_table", die_on_error=False, commit=False)
    made["components"].insert(1, {"id": "d", "type": "does", "inputs": [], "outputs": [],
                                  "config": {"connection": "tDBConnection_1", "statement": "insert into t values (1)"}})
    made["components"].append({"id": "c", "type": "tOracleCommit", "config": {"connection": "tDBConnection_1"},
                               "inputs": [], "outputs": []})
    made["triggers"] = after("tDBConnection_1", "d", "in", "c")
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result = run(made)
    assert result.status == "success", result.error
    assert "[db] no such table: no_such_table; the job goes on with nothing stored by it" in caplog.text
    assert result.global_map["db_NB_LINE_REJECTED"] == 1 and result.rows == {"db": 0}
    # What an earlier subjob did on the session is still there, and is stored.
    assert emp.stored() == [(1,)]


def test_with_die_on_error_off_what_it_did_before_it_could_not_go_on_is_taken_back(emp, tmp_path):
    """The table was cleared, and then the rows could not be sent at all: the clearing is taken back with them."""
    made = loading(tmp_path, "3;cy;3.5\n", schema="id:int, name:str, nope:float", table_action="CLEAR", die_on_error=False)
    result = run(made)
    assert result.status == "success", result.error
    assert "nope" in result.global_map["db_ERROR_MESSAGE"]
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bob", 2.5)]
    assert "rollback to savepoint v2_output" in emp.sessions[0].asked


def test_with_die_on_error_off_what_was_taken_back_does_not_wait_for_a_commit(emp, tmp_path):
    """Found by the review of the group, in the row: the job went on, and failed when it ended for work it had
    itself taken back."""
    made = loading(tmp_path, "3;cy;3.5\n", schema="id:int, name:str, nope:float", table_action="CLEAR",
                   die_on_error=False, commit=False)
    result = run(made)
    assert result.status == "success", result.error
    assert emp.sessions[0].pending == []
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bob", 2.5)]


def test_rows_that_were_stored_before_some_were_refused_still_wait_for_a_commit(emp, tmp_path):
    result = run(loading(tmp_path, "3;cy;3.5\n1;again;1\n", die_on_error=False, commit=False))
    assert (result.status, result.failed_component) == ("failed", "tDBConnection_1")
    assert "what db did on the session" in result.error


def test_without_use_batch_size_a_round_trip_takes_ten_thousand_rows(emp, tmp_path):
    run(loading(tmp_path, "3;cy;3.5\n4;di;4.5\n5;ed;5.5\n", use_batch_size=False, batch_size=1))
    assert [did[2] for did in emp.sessions[0].did if isinstance(did, tuple) and did[0] == "many"] == [3]


def test_a_key_the_table_holds_as_a_date_is_compared_as_one(emp, tmp_path, monkeypatch):
    from tests.v2.database import SqliteSession
    from src.v2.sessions import DATE, TEXT, Field

    def fields(self, statement, binds=None):
        self.did.append(("fields", statement))
        return [Field("NAME", TEXT, "VARCHAR"), Field("DAY", DATE, "DATE"), Field("TS", DATE, "TIMESTAMP")]

    monkeypatch.setattr(SqliteSession, "fields", fields)
    held = sqlite3.connect(emp.path)
    held.execute("create table days (name, day, ts, amt)")
    held.commit()
    held.close()
    schema = "name:str, day:str, ts:str, amt:float"
    made = loading(tmp_path, "ann;2024-01-31;2024-01-31;1.5\n", schema=schema, table="days", data_action="UPDATE_OR_INSERT")
    made["components"][2]["schema"]["input"] = keyed(schema, "name,day,ts")
    assert run(made).status == "success"
    session = emp.sessions[0]
    assert ("fields", "select name, day, ts from days") in session.did
    assert "update days set amt = :1 where name = :2 and day = cast(:3 as date) and ts = :4" in session.asked
    # An insert finds no row by a key, and asks nothing about one.
    made = loading(tmp_path, "bob;2024-01-31;2024-01-31;1.5\n", schema=schema, table="days")
    assert run(made).status == "success"
    assert not [did for did in emp.sessions[1].did if isinstance(did, tuple) and did[0] == "fields"]


def test_a_row_refused_in_an_update_and_in_the_insert_that_follows_one(emp, tmp_path):
    rows = "2;much too long;0\n9;also too long;0\n8;ok;8.5\n"
    result = run(loading(tmp_path, rows, data_action="UPDATE_OR_INSERT", die_on_error=False))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann", 1.5), (2, "bob", 2.5), (8, "ok", 8.5)]
    held = result.global_map
    assert (held["db_NB_LINE_UPDATED"], held["db_NB_LINE_INSERTED"], held["db_NB_LINE_REJECTED"]) == (0, 1, 2)
    assert "the first: row 1 of the rows it was handed (id=2)" in held["db_ERROR_MESSAGE"]


# ------------------------------------------------------------------
# The table's name, and the columns
# ------------------------------------------------------------------

def test_the_table_is_looked_for_in_the_schema_the_component_or_its_connection_names(emp, tmp_path):
    made = loading(tmp_path, "3;cy;3.5\n", schema_db="main")
    assert run(made).status == "success"
    assert "insert into main.emp (id, name, amt) values (:1, :2, :3)" in emp.sessions[0].asked
    made = loading(tmp_path, "4;di;4.5\n")
    made["components"][0]["config"]["schema_db"] = "main"
    assert run(made).status == "success"
    assert "insert into main.emp (id, name, amt) values (:1, :2, :3)" in emp.sessions[1].asked
    # With a session of its own, the schema is its own block's.
    made = loading(tmp_path, "5;ed;5.5\n", own=True)
    made["components"][1]["config"]["schema_db"] = "main"
    assert run(made).status == "success"
    assert "insert into main.emp (id, name, amt) values (:1, :2, :3)" in emp.sessions[2].asked


@pytest.mark.parametrize("spelling", ["schema_db", "table_schema", "dbschema"])
def test_the_schema_goes_by_three_names(emp, tmp_path, spelling):
    made = loading(tmp_path, "3;cy;3.5\n", **{spelling: "main"})
    assert run(made).status == "success"
    assert "insert into main.emp (id, name, amt) values (:1, :2, :3)" in emp.sessions[0].asked


def test_the_columns_stored_are_the_declared_ones_whatever_else_the_rows_hold(emp, tmp_path):
    (tmp_path / "in.csv").write_text("3;extra;cy\n")
    components = [connection(schema_db=""), reader("id:int, more:str, name:str", path=str(tmp_path / "in.csv")),
                  stores("name:str, id:int"),
                  {"id": "c", "type": "tOracleCommit", "config": {"connection": "tDBConnection_1"}, "inputs": [], "outputs": []}]
    result = run(job(components, [flow("row1", "in", "db")], triggers=after("tDBConnection_1", "in", "c")))
    assert result.status == "success", result.error
    assert emp.stored(EMP)[-1] == (3, "cy", None)
    assert "insert into emp (name, id) values (:1, :2)" in emp.sessions[0].asked


def test_a_declared_column_the_rows_lack_fails_the_job(emp, tmp_path):
    (tmp_path / "in.csv").write_text("3;cy\n")
    components = [connection(schema_db=""), reader("id:int, name:str", path=str(tmp_path / "in.csv")), stores(ROWS)]
    result = run(job(components, [flow("row1", "in", "db")], triggers=after("tDBConnection_1", "in")))
    assert (result.status, result.failed_component) == ("failed", "db")
    assert result.failures["db"] == "the rows it is handed have no column amt: they have id, name"


def test_no_row_stores_none_and_is_no_fault(emp, tmp_path):
    result = run(loading(tmp_path, "", table_action="CLEAR"))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [] and result.rows == {"db": 0}


def test_a_traced_run_lists_the_rows_handed_to_the_table(emp, tmp_path):
    made = loading(tmp_path, "3;cy;3.5\n4;di;4.5\n")
    result = run(made, run={"only": {"source": "in", "lines": [2]}, "trace": True})
    assert result.status == "success", result.error
    assert emp.stored(EMP)[-1] == (4, "di", 4.5)
    filed = [entry for entry in result.trace if entry["id"] == "db"][0]
    assert (filed["path"], filed["written"], filed["rows"], filed["data"]) == ("table emp", True, 1, [["4", "di", "4.5"]])


# ------------------------------------------------------------------
# The statements, and the table that is made
# ------------------------------------------------------------------

def test_the_statements():
    assert oracle_output.insert_statement("HR.EMP", ["A", "B"]) == "insert into HR.EMP (A, B) values (:1, :2)"
    assert oracle_output.update_statement("T", ["A", "B"], ["K1", "K2"]) == "update T set A = :1, B = :2 where K1 = :3 and K2 = :4"
    assert oracle_output.delete_statement("T", ["K1", "K2"]) == "delete from T where K1 = :1 and K2 = :2"
    # A key the table holds as a DATE is compared as one, so that an index on it is used.
    assert oracle_output.update_statement("T", ["A"], ["D", "K"], ["D"]) == "update T set A = :1 where D = cast(:2 as date) and K = :3"
    assert oracle_output.delete_statement("T", ["D"], ["D"]) == "delete from T where D = cast(:1 as date)"


@pytest.mark.parametrize("column, made", [
    (Column("c", "str"), "VARCHAR2(4000 CHAR)"), (Column("c", "str", length=30), "VARCHAR2(30 CHAR)"),
    (Column("c", "str", length=4000), "VARCHAR2(4000 CHAR)"), (Column("c", "str", length=4001), "CLOB"),
    (Column("c", "int"), "NUMBER(19)"), (Column("c", "int", length=5), "NUMBER(5)"),
    (Column("c", "Decimal"), "NUMBER"), (Column("c", "Decimal", precision=2), "NUMBER(38, 2)"),
    (Column("c", "Decimal", length=12, precision=2), "NUMBER(12, 2)"), (Column("c", "Decimal", length=20), "NUMBER(20, 0)"),
    (Column("c", "float"), "BINARY_DOUBLE"), (Column("c", "bool"), "NUMBER(1)"), (Column("c", "datetime"), "TIMESTAMP(6)"),
    (Column("c", "date"), "DATE"),
])
def test_the_type_a_column_gets_in_a_table_that_is_made(column, made):
    assert oracle_output.column_type(column) == made


def test_the_table_that_is_made():
    made = oracle_output.create_statement("HR.T", [Column("ID", "int", nullable=False, key=True), Column("D", "date", key=True),
                                                    Column("V", "str", length=10)])
    assert made == "create table HR.T (ID NUMBER(19) not null, D DATE, V VARCHAR2(10 CHAR), primary key (ID, D))"
    assert oracle_output.create_statement("T", [Column("V", "str")]) == "create table T (V VARCHAR2(4000 CHAR))"


# ------------------------------------------------------------------
# What refuses the job
# ------------------------------------------------------------------

def test_what_refuses_the_job_when_it_loads(emp, tmp_path):
    def of(**config):
        return refusals(job([connection(schema_db=""), reader(ROWS), stores(**config)], [flow("row1", "in", "db")]))

    assert of(table="") == ["table: names no table"]
    assert of(table="emp; drop table x") == [
        "table: 'emp; drop table x' is no name Oracle takes as it is: letters, digits, `_`, `$` and `#`, a letter first"]
    assert of(schema_db="h r") == [
        "schema_db: 'h r' is no name Oracle takes as it is: letters, digits, `_`, `$` and `#`, a letter first"]
    assert of(data_action="UPSERT")[0].startswith("data_action: 'UPSERT' is not allowed")
    assert of(table_action="WIPE")[0].startswith("table_action: 'WIPE' is not allowed")
    assert of(key="", data_action="UPDATE") == [
        "data_action: UPDATE finds a row by its key, and the schema marks no column as `key`"]
    assert of(key="id,name,amt", data_action="UPDATE_OR_INSERT") == [
        "data_action: UPDATE_OR_INSERT has nothing to set: every column is a key"]
    assert of(use_field_options=True) == [
        "use_field_options: which columns are keys and which are written is said by the schema here (`key`); the "
        "table of field options is not read"]
    assert of(use_hint_options=True) == ["use_hint_options: hints for the statements are not read"]
    assert of(batch_size=0) == ["batch_size: 0 rows cannot be sent at a time; give 1 or more"]
    assert of(batch_size="lots") == ["batch_size: 'lots' is no number of rows"]
    assert of(connection="nope") == ["connection: the job has no component 'nope'; its Oracle connections are: tDBConnection_1"]
    assert of(schema="my col:int") == ["schema: 'my col' is no name Oracle takes as it is"]
    bare = stores()
    bare["schema"] = {"input": [], "output": []}
    assert refusals(job([connection(schema_db=""), reader(ROWS), bare], [flow("row1", "in", "db")])) == [
        "schema: an output needs the columns it stores declared"]
    assert refusals(job([reader(ROWS), stores(use_existing_connection=False, connection="")], [flow("row1", "in", "db")])) == [
        "host: is empty; a session is opened with a host and a SID", "dbname: is empty; a session is opened with a host and a SID",
        "user: is empty"]


def test_a_delete_by_a_key_that_is_every_column_is_no_fault(emp, tmp_path):
    made = job([connection(schema_db=""), reader(ROWS), stores(key="id,name,amt", data_action="DELETE")], [flow("row1", "in", "db")])
    load_job(made, registry=WITH_DOES)


def test_what_talend_writes_and_changes_nothing_here_is_taken(emp, tmp_path):
    made = job([connection(schema_db=""), reader(ROWS), stores(commit_every=10000, enable_debug_mode=False, trim_char=True,
                                                   convert_column_table_to_uppercase=False, use_field_options=False,
                                                   use_timestamp_for_date_type=True, use_hint_options=False)],
               [flow("row1", "in", "db")])
    load_job(made, registry=WITH_DOES)


def test_no_flow_leaves_it(emp, tmp_path):
    made = job([connection(schema_db=""), reader(ROWS), stores(), writer(ROWS, inputs=("bad",))],
               [flow("row1", "in", "db"), flow("bad", "db", "out", kind="reject")])
    with pytest.raises(JobRefusedError) as refused:
        load_job(made, registry=WITH_DOES)
    assert "has no 'reject' output" in refused.value.report.format()
