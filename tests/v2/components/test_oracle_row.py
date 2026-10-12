"""Oracle row: one statement, run once or for each row of a flow. On SQLite, behind the seam."""
import copy
import json
import logging
import sqlite3
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, reader, writer
from tests.v2.components.test_oracle_connection import BLOCK, after, connection
from tests.v2.database import WITH_DOES, SqliteSession, on_sqlite  # noqa: F401 -- a fixture

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tOracleRow_0.1.json"
ROWS = "id:int, name:str"
EMP = "select id, name from emp order by id"
CONN = "tDBConnection_1"


@pytest.fixture
def emp(on_sqlite):
    held = sqlite3.connect(on_sqlite.path)
    held.execute("create table emp (id integer primary key, name text check (length(name) < 8))")
    held.executemany("insert into emp values (?, ?)", [(1, "ann"), (2, "bob")])
    held.commit()
    held.close()
    return on_sqlite


def row(query, component_id="r", inputs=(), outputs=(), schema=ROWS, **config):
    made = {"use_existing_connection": True, "connection": CONN, "query": query, **config}
    return {"id": component_id, "type": "tOracleRow", "config": made, "inputs": list(inputs), "outputs": list(outputs),
            "schema": {"input": columns(schema) if inputs else [], "output": columns(schema) if outputs else []}}


def commit(component_id="c", **more):
    return {"id": component_id, "type": "tOracleCommit", "config": {"connection": CONN}, "inputs": [], "outputs": [], **more}


def once(query, with_commit=True, **config):
    """connection -> the statement -> a commit."""
    components = [connection(schema_db=""), row(query, **config)] + ([commit()] if with_commit else [])
    return job(components, [], triggers=after(*(component["id"] for component in components)))


def for_rows(tmp_path, rows, query, **config):
    """connection -> a file -> the statement for each row -> a file, then a commit."""
    (tmp_path / "in.csv").write_text(rows)
    components = [connection(schema_db=""), reader(ROWS, path=str(tmp_path / "in.csv")),
                  row(query, inputs=("row1",), outputs=("row2",), **config), writer(ROWS, path=str(tmp_path / "out.csv")),
                  commit()]
    return job(components, [flow("row1", "in", "r"), flow("row2", "r", "out")], triggers=after(CONN, "in", "c"))


def run(made, **more):
    return run_job(made, registry=WITH_DOES, **more)


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made, registry=WITH_DOES)
    return [f"{refusal.key}: {refusal.reason}" for refusal in refused.value.report]


def parameters(*given):
    return [{"parameter_index": str(at), "parameter_type": kind, "parameter_value": value}
            for at, (kind, value) in enumerate(given, start=1)]


# ------------------------------------------------------------------
# Once
# ------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["oracle_row", "OracleRow", "tOracleRow"])
def test_a_statement_is_run_once_and_waits_for_the_commit(emp, kind):
    made = once("delete from emp where id = 2", with_commit=False)
    made["components"][1]["type"] = kind
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", CONN)
    assert emp.stored(EMP) == [(1, "ann"), (2, "bob")]
    result = run(once("delete from emp where id = 2"))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann")]


def test_with_a_session_of_its_own_what_it_did_is_stored_when_it_is_done(emp):
    made = job([row("delete from emp where id = 2", use_existing_connection=False, connection="", **{**BLOCK, "schema_db": ""})], [])
    assert run(made).status == "success"
    assert emp.stored(EMP) == [(1, "ann")]
    assert emp.sessions[0].did[-2:] == ["commit", "close"]


def test_values_are_bound_and_the_statement_is_left_as_it_was_sent(emp, caplog):
    made = once('"update " + context.t + " set name = \'" + context.who + "\' where id = " + context.n')
    made["context"] = {"t": "emp", "who": "o'brien", "n": 2}
    with caplog.at_level(logging.INFO, logger="src.v2"):
        result = run(made)
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann"), (2, "o'brien")]
    assert result.global_map["r_QUERY"] == "update emp set name = :context_who where id = 2"
    assert "[r] ran: update emp set name = :context_who where id = 2" in caplog.text
    assert "o'brien" not in caplog.text


@pytest.mark.parametrize("counter", ["NONE", "NB_LINE_INSERTED", "NB_LINE_UPDATED", "NB_LINE_DELETED"])
def test_the_rows_it_changed_are_left_under_the_counter_the_job_names(emp, counter):
    result = run(once("update emp set name = 'x'", use_nb_line=counter))
    held = {name: result.global_map[f"r_{name}"] for name in ("NB_LINE_INSERTED", "NB_LINE_UPDATED", "NB_LINE_DELETED")}
    assert held == {name: (2 if name == counter else 0) for name in held}


def test_a_value_that_would_change_the_statement_fails_it(emp):
    made = once("delete from emp where id = ${context.n}")
    made["context"] = {"n": "1 or 1=1"}
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "r")
    assert result.failures["r"].startswith("what context.n holds is written into the statement")
    assert emp.stored(EMP) == [(1, "ann"), (2, "bob")]


def test_a_statement_the_database_refuses_fails_the_job(emp):
    result = run(once("delete from no_such_table"))
    assert (result.status, result.failed_component, result.failures["r"]) == ("failed", "r", "no such table: no_such_table")


def test_with_die_on_error_off_the_job_goes_on(emp, caplog):
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result = run(once("delete from no_such_table", die_on_error=False))
    assert result.status == "success", result.error
    assert result.global_map["r_ERROR_MESSAGE"] == "no such table: no_such_table"
    assert "[r] no such table: no_such_table; the job goes on with its statement not run" in caplog.text


def test_a_statement_after_another_on_one_session_is_not_said_to_have_stored_anything(emp, caplog):
    components = [connection(schema_db=""), row("delete from emp where id = 1", component_id="first"),
                  row("delete from emp where id = 2"), commit()]
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result = run(job(components, [], triggers=after(CONN, "first", "r", "c")))
    assert result.status == "success" and emp.stored(EMP) == []
    assert "stored what waited" not in caplog.text


@pytest.mark.parametrize("query", ["select count(*) from emp", "update emp set name = 'x' where id = 99",
                                   "delete from emp where 1 = 0"])
def test_a_statement_that_changed_no_row_leaves_nothing_waiting(emp, query):
    """The place that was marked for it counts as an open transaction in the database. It is no work to store."""
    result = run(once(query, with_commit=False))
    assert result.status == "success", result.error
    assert emp.sessions[0].pending == []


def test_what_a_block_changed_cannot_be_seen_and_counts_as_work_that_waits(emp, monkeypatch):
    from src.v2.components.database.oracle_row import _BLOCK
    plain = SqliteSession.run
    # The stand-in has no PL/SQL: in place of a block it runs a statement that changes no row.
    monkeypatch.setattr(SqliteSession, "run", lambda self, statement, binds=None: plain(
        self, "delete from emp where 1 = 0" if _BLOCK.match(statement) else statement, binds))
    for block in ("BEGIN do_it; END;", "  declare n number; begin null; end;", "/* a remark */ call do_it()", "-- why\nbegin null; end;"):
        result = run(once(block, with_commit=False))
        assert (result.status, result.failed_component) == ("failed", CONN), block


def test_a_statement_that_changed_no_row_takes_nothing_of_an_earlier_statements_work_with_it(emp):
    components = [connection(schema_db=""), row("delete from emp where id = 1", component_id="first"),
                  row("delete from emp where id = 99")]
    result = run(job(components, [], triggers=after(CONN, "first", "r")))
    assert (result.status, result.failed_component) == ("failed", CONN)
    assert "what first did on the session" in result.error


def test_a_statement_that_defines_is_run_on_a_session_nothing_waits_on(emp):
    result = run(once("create table made (a)", with_commit=False))
    assert result.status == "success", result.error
    assert emp.stored("select count(*) from made") == [(0,)]
    # It asked for no place to go back to: there is none for what a database stores by itself.
    assert emp.sessions[0].asked == ["create table made (a)"]


def test_a_statement_that_defines_is_refused_over_work_that_waits(emp):
    components = [connection(schema_db=""), row("delete from emp where id = 1", component_id="first"),
                  row("truncate table emp"), commit()]
    result = run(job(components, [], triggers=after(CONN, "first", "r", "c")))
    assert (result.status, result.failed_component) == ("failed", "r")
    assert result.failures["r"] == ("the statement is one that defines, and Oracle stores what waits on a session "
                                    "before one: the work of first would be stored with it. Put a commit before it")
    assert emp.stored(EMP) == [(1, "ann"), (2, "bob")]


def test_a_statement_that_stores_by_itself_what_waited_is_told(emp, monkeypatch, caplog):
    """A block of PL/SQL may commit, or define, and Oracle then stores what waited. The engine says what it saw."""
    plain = SqliteSession.run

    def run_and_store(self, statement, binds=None):
        changed = plain(self, statement, binds)
        if "-- stores" in statement:
            self._held.execute("commit")
        return changed

    monkeypatch.setattr(SqliteSession, "run", run_and_store)
    components = [connection(schema_db=""), row("delete from emp where id = 1", component_id="first"),
                  row("delete from emp where id = 2 -- stores")]
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result = run(job(components, [], triggers=after(CONN, "first", "r")))
    assert result.status == "success", result.error
    assert ("[r] the statement stored what waited on the session by itself: the work of first is stored now, with no "
            "commit of the job's") in caplog.text
    assert emp.stored(EMP) == []


# ------------------------------------------------------------------
# With a flow from it and none to it
# ------------------------------------------------------------------

def test_it_hands_on_one_row_with_nothing_in_it_so_that_what_follows_runs_once(emp, tmp_path):
    out = str(tmp_path / "out.csv")
    components = [connection(schema_db=""), row("delete from emp where id = 2", outputs=("row1",)),
                  writer(ROWS, path=out, inputs=("row1",))]
    result = run(job(components, [flow("row1", "r", "out")], triggers=after(CONN, "r")))
    assert open(out).read() == "id;name\n;\n"
    assert result.rows == {"out": 1}


def test_as_the_converted_sample_has_it_a_commit_that_follows_by_a_flow_stores_what_the_statement_did(emp):
    components = [connection(schema_db=""), row("delete from emp where id = 2", outputs=("row1",), schema=""),
                  commit(inputs=["row1"])]
    components[1]["schema"] = {"input": [], "output": []}
    result = run(job(components, [flow("row1", "r", "c")], triggers=after(CONN, "r")))
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann")]
    assert emp.sessions[0].did[-2:] == ["commit", "close"]


def test_the_converted_sample_loads_once_its_password_is_one_v2_can_use(emp):
    made = json.loads(SAMPLE.read_text())
    assert refusals(copy.deepcopy(made)) == [
        "password: is text Talend encrypted with a key of its own, which v2 cannot read; give the password itself, "
        "from a context variable (`${context.db_password}`)"]
    made["components"][0]["config"]["password"] = "${context.db_password}"
    made["context"]["Default"]["db_password"] = {"value": "x", "type": "id_Password"}
    loaded = load_job(made, registry=WITH_DOES)
    assert [spec.type for spec in loaded.components.values()] == ["tOracleConnection", "tOracleRow", "tOracleCommit"]


# ------------------------------------------------------------------
# For each row of a flow
# ------------------------------------------------------------------

def test_a_prepared_statement_is_run_for_each_row_with_the_rows_values_bound(emp, tmp_path):
    made = for_rows(tmp_path, "2;bo\n7;new\n", "update emp set name = ? where id = ? and name <> ?", use_nb_line="NB_LINE_UPDATED",
                    use_preparedstatement=True,
                    set_preparedstatement_parameters=parameters(("String", "row1.name"), ("Int", "row1.id"), ("String", "context.not_this")))
    made["context"] = {"not_this": "ann"}
    result = run(made)
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann"), (2, "bo")]
    # The rows go on as they came.
    assert (tmp_path / "out.csv").read_text() == "id;name\n2;bo\n7;new\n"
    session = emp.sessions[0]
    assert ("many", "update emp set name = :1 where id = :2 and name <> :3", 2) in session.did
    assert result.global_map["r_NB_LINE_UPDATED"] == 1
    assert result.global_map["r_QUERY"] == "update emp set name = :p1 where id = :p2 and name <> :p3"


def test_a_joined_statement_names_the_columns_of_the_row(emp, tmp_path):
    query = '"insert into emp (id, name) values (" + row1.id + ", \'" + row1.name + "-" + context.tag + "\')"'
    made = for_rows(tmp_path, "5;ed\n6;flo\n", query, use_nb_line="NB_LINE_INSERTED")
    made["context"] = {"tag": "x"}
    result = run(made)
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann"), (2, "bob"), (5, "ed-x"), (6, "flo-x")]
    assert result.global_map["r_QUERY"] == "insert into emp (id, name) values (:row1_id, :row1_name || '-' || :context_tag)"
    assert result.global_map["r_NB_LINE_INSERTED"] == 2


def test_a_row_the_database_refuses_fails_the_job_and_names_the_row(emp, tmp_path):
    made = for_rows(tmp_path, "5;ed\n1;again\n", '"insert into emp (id, name) values (" + row1.id + ", \'" + row1.name + "\')"')
    result = run(made)
    assert (result.status, result.failed_component) == ("failed", "r")
    assert result.failures["r"] == ("the database refused the statement for a row: UNIQUE constraint failed: emp.id; "
                                    f"the row is line 2 of {tmp_path / 'in.csv'}")
    assert emp.stored(EMP) == [(1, "ann"), (2, "bob")]


def test_with_die_on_error_off_such_rows_are_counted_and_the_others_done(emp, tmp_path, caplog):
    query = '"insert into emp (id, name) values (" + row1.id + ", \'" + row1.name + "\')"'
    made = for_rows(tmp_path, "5;ed\n1;again\n6;much too long\n7;gil\n", query, die_on_error=False)
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result = run(made)
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann"), (2, "bob"), (5, "ed"), (7, "gil")]
    said = ("the database refused the statement for 2 of the 4 rows; the first: UNIQUE constraint failed: emp.id; the "
            f"row is line 2 of {tmp_path / 'in.csv'}")
    assert result.global_map["r_ERROR_MESSAGE"] == said and f"[r] {said}" in caplog.text


def test_the_first_refused_row_is_the_one_told_whichever_round_trip_it_went_in(emp, tmp_path, monkeypatch):
    from src.v2.components.database import oracle_row
    monkeypatch.setattr(oracle_row, "_BATCH", 1)
    query = '"insert into emp (id, name) values (" + row1.id + ", \'" + row1.name + "\')"'
    made = for_rows(tmp_path, "5;ed\n1;again\n2;once more\n7;gil\n", query, die_on_error=False)
    result = run(made)
    assert result.status == "success", result.error
    assert result.global_map["r_ERROR_MESSAGE"].startswith("the database refused the statement for 2 of the 4 rows; the first: UNIQUE")
    assert result.global_map["r_ERROR_MESSAGE"].endswith(f"the row is line 2 of {tmp_path / 'in.csv'}")
    assert [did[2] for did in emp.sessions[0].did if isinstance(did, tuple) and did[0] == "many"] == [1, 1, 1, 1]


def test_a_column_the_rows_do_not_have_is_said_with_the_ones_they_have(emp, tmp_path):
    result = run(for_rows(tmp_path, "5;ed\n", '"delete from emp where id = " + row1.nope'))
    assert result.failures["r"] == "the rows of row1 have no column 'nope'; they have: id, name"


def test_a_statement_with_nothing_of_the_row_in_it_is_run_once_for_each_row(emp, tmp_path):
    made = for_rows(tmp_path, "5;ed\n6;flo\n7;gil\n", "update emp set name = name || '!' where id = 1",
                    use_nb_line="NB_LINE_UPDATED")
    result = run(made)
    assert result.status == "success", result.error
    assert emp.stored(EMP) == [(1, "ann!!!"), (2, "bob")]
    assert result.global_map["r_NB_LINE_UPDATED"] == 3


def test_no_row_runs_nothing(emp, tmp_path):
    made = for_rows(tmp_path, "", "delete from emp")
    assert run(made).status == "success"
    assert emp.stored(EMP) == [(1, "ann"), (2, "bob")]


def test_a_fault_of_the_whole_statement_with_die_on_error_off_takes_back_what_it_did(emp, tmp_path):
    query = '"insert into emp (id, name) values (" + row1.id + ", \'" + row1.name + "\')"'
    made = for_rows(tmp_path, "5;ed\n", query, die_on_error=False)
    made["components"][2]["config"]["query"] = '"insert into nope (id) values (" + row1.id + ")"'
    result = run(made)
    assert result.status == "success", result.error
    assert result.global_map["r_ERROR_MESSAGE"] == "no such table: nope"
    assert "rollback to savepoint v2_row" in emp.sessions[0].asked


def test_a_statement_that_defines_is_not_run_for_each_row(emp, tmp_path):
    result = run(for_rows(tmp_path, "5;ed\n", "truncate table emp"))
    assert result.failures["r"] == ("a statement that defines is run once, and not for each row of a flow: set it off "
                                    "with a trigger")


def test_a_value_given_for_a_mark_is_made_the_type_of_its_place(emp, tmp_path):
    held = sqlite3.connect(emp.path)
    held.execute("create table kinds (a, b, c, d, e, f, g)")
    held.commit()
    held.close()
    given = parameters(("String", '"it\'s"'), ("Int", "42"), ("BigDecimal", "1.50"), ("Boolean", "true"), ("Null", "x"),
                       ("Double", "context.f"), ("Long", "context.n"))
    made = once("insert into kinds values (?, ?, ?, ?, ?, ?, ?)", use_preparedstatement=True,
                set_preparedstatement_parameters=given)
    made["context"] = {"Default": {"f": {"value": "2.5", "type": "id_String"}, "n": {"value": "7", "type": "id_Integer"}}}
    result = run(made)
    assert result.status == "success", result.error
    sent = [did for did in emp.sessions[0].asked if did.startswith("insert into kinds")]
    assert sent == ["insert into kinds values (:p1, :p2, :p3, :p4, :p5, :p6, :p7)"]


@pytest.mark.parametrize("kind, held", [("Int", "seven"), ("Boolean", "maybe"), ("BigDecimal", "1,5"), ("Date", "tomorrow"),
                                        ("Double", "x")])
def test_a_value_that_is_not_of_its_type_fails_and_is_not_shown(emp, kind, held):
    made = once("delete from emp where id = ?", use_preparedstatement=True,
                set_preparedstatement_parameters=parameters((kind, "context.n")))
    made["context"] = {"n": held}
    result = run(made)
    assert result.failures["r"] == f"the value for mark 1 is no {kind}"
    assert held not in result.failures["r"]


def test_what_a_written_value_is_made_into(emp, monkeypatch):
    seen = []
    plain = SqliteSession.run

    def noting(self, statement, binds=None):
        seen.append(dict(binds or {}))
        return plain(self, "delete from emp where id = 99") if "?" in statement or ":p" in statement else plain(self, statement, binds)

    monkeypatch.setattr(SqliteSession, "run", noting)
    given = parameters(("String", '"it\'s"'), ("Int", "42"), ("BigDecimal", "1.50"), ("Boolean", "true"), ("Boolean", "0"),
                       ("Null", "x"), ("Double", "2.5"), ("Date", "2024-01-31"), ("Timestamp", "2024-01-31 13:14:15"),
                       ("String", "plain"), ("String", ""), ("Long", "context.n"), ("String", 'globalMap.get("k")'),
                       ("String", "context.n"), ("BigDecimal", "context.n"), ("Int", "context.none"), ("Boolean", "context.yes"))
    made = once("select ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? from emp", use_preparedstatement=True,
                set_preparedstatement_parameters=given)
    made["context"] = {"Default": {"n": {"value": "7", "type": "id_Integer"}, "none": {"value": None, "type": "id_String"},
                                   "yes": {"value": "true", "type": "id_Boolean"}}}
    made["components"].insert(0, {"id": "set", "type": "SetGlobalVar", "config": {"variables": [{"key": "k", "value": "00123"}]}})
    made["triggers"].append({"type": "OnSubjobOk", "from": "set", "to": CONN})
    assert run(made).status == "success"
    import datetime
    import decimal
    sent = [binds for binds in seen if "p1" in binds][0]
    assert sent == {"p1": "it's", "p2": 42, "p3": decimal.Decimal("1.50"), "p4": True, "p5": False, "p6": None, "p7": 2.5,
                    "p8": datetime.datetime(2024, 1, 31), "p9": datetime.datetime(2024, 1, 31, 13, 14, 15), "p10": "plain",
                    "p11": "", "p12": 7, "p13": "00123",
                    # What was looked up is made the kind its place names, whatever kind it was.
                    "p14": "7", "p15": decimal.Decimal("7"), "p16": None, "p17": True}


def test_for_each_row_with_a_session_of_its_own_what_it_did_is_stored_when_the_subjob_is_done(emp, tmp_path):
    (tmp_path / "in.csv").write_text("5;ed\n")
    query = '"insert into emp (id, name) values (" + row1.id + ", \'" + row1.name + "\')"'
    made = job([reader(ROWS, path=str(tmp_path / "in.csv")),
                row(query, inputs=("row1",), use_existing_connection=False, connection="", **{**BLOCK, "schema_db": ""})],
               [flow("row1", "in", "r")])
    assert run(made).status == "success"
    assert emp.stored(EMP)[-1] == (5, "ed")
    assert emp.sessions[0].did[-2:] == ["commit", "close"]


def test_a_column_named_for_a_mark_that_the_rows_lack(emp, tmp_path):
    made = for_rows(tmp_path, "5;ed\n", "delete from emp where id = ?", use_preparedstatement=True,
                    set_preparedstatement_parameters=parameters(("Int", "row1.nope")))
    result = run(made)
    assert result.failures["r"] == "the value for mark 1 is the column 'nope', which the rows of row1 do not have"


# ------------------------------------------------------------------
# What refuses the job
# ------------------------------------------------------------------

def test_what_refuses_the_job_when_it_loads(emp):
    def of(query="delete from emp", **config):
        return refusals(job([connection(), row(query, **config)], []))

    java = '"delete from emp where d = \'" + TalendDate.getDate("yyyy") + "\'"'
    assert of(java)[0].startswith("query: the statement is joined as Java joins text")
    # With no flow to it, a name like that of a row is Java nobody reads.
    assert of('"delete from emp where id = " + row1.id')[0].startswith("query: the statement is joined as Java joins text")
    assert of(propagate_record_set=True) == [
        "propagate_record_set: a query's rows are not handed on in a column; read them with an input"]
    assert of(use_nb_line="NB_LINE")[0].startswith("use_nb_line: 'NB_LINE' is not allowed")
    marks = dict(use_preparedstatement=True)
    assert of(**marks, set_preparedstatement_parameters=parameters(("Blob", "x"))) == [
        "set_preparedstatement_parameters[0].parameter_type: a Blob is not bound; give text, a number or a date"]
    assert of(**marks, set_preparedstatement_parameters=parameters(("Text", "x"))) == [
        "set_preparedstatement_parameters[0].parameter_type: 'Text' is no type; the types are String, Object, Int, "
        "Integer, Long, Short, Byte, BigInteger, Double, Float, BigDecimal, Boolean, Date, Timestamp, Null"]
    assert of(**marks, set_preparedstatement_parameters=parameters(("String", "TalendDate.getDate(\"yyyy\")"))) == [
        "set_preparedstatement_parameters[0].parameter_value: is Java, and v2 runs none; give a value, a context "
        "variable, an entry of globalMap or a column of the row"]
    wrong = [{"parameter_index": "2", "parameter_type": "String", "parameter_value": "x"}]
    assert of(**marks, set_preparedstatement_parameters=wrong) == [
        "set_preparedstatement_parameters: the places are to be 1, 2, 3... in their order; they are 2"]
    assert refusals(job([row("delete from emp", use_existing_connection=False, connection="")], [])) == [
        "host: is empty; a session is opened with a host and a SID", "dbname: is empty; a session is opened with a host and a SID",
        "user: is empty"]


def test_parameters_that_are_not_used_are_not_judged_and_not_read(emp):
    made = once("delete from emp where id = 2", set_preparedstatement_parameters=parameters(("Blob", "x")))
    load_job(made, registry=WITH_DOES)
    assert run(made).status == "success"
    assert emp.stored(EMP) == [(1, "ann")]


def test_what_follows_the_row_it_hands_on_is_checked_when_the_job_loads(emp, tmp_path):
    keeps = {"id": "f", "type": "FilterRows", "config": {"use_advanced": True, "condition": "row1.nope > 1"},
             "schema": {"input": columns(ROWS), "output": columns(ROWS)}, "inputs": ["row1"], "outputs": ["row2"]}
    made = job([connection(), row("delete from emp", outputs=("row1",)), keeps, writer(ROWS)],
               [flow("row1", "r", "f"), flow("row2", "f", "out")])
    with pytest.raises(JobRefusedError) as refused:
        load_job(made, registry=WITH_DOES)
    assert "row1 has no column 'nope'" in refused.value.report.format()


def test_as_many_marks_as_values(emp):
    made = once("delete from emp where id = ? and name = ?", use_preparedstatement=True,
                set_preparedstatement_parameters=parameters(("Int", "1")))
    assert run(made).failures["r"] == "the statement has 2 marks (?) and 1 value(s) are given for them"
