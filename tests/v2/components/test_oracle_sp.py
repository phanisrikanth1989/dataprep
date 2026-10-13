"""Oracle stored procedure: a procedure or a function called once or for each row. On a stand-in for the calls."""
import decimal
import logging

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, reader, writer
from tests.v2.components.test_oracle_connection import BLOCK, after, connection
from tests.v2.database import WITH_DOES, SqliteSession, on_sqlite  # noqa: F401 -- a fixture

ROWS = "id:int, name:str, twice:Decimal#2, said:str"
CONN = "tDBConnection_1"


@pytest.fixture
def procedures(on_sqlite, monkeypatch):
    """What the procedures of the stand-in do: the values handed in, by place, to the values out, by place."""
    calls = []

    def twice(a, name, out, said):
        calls.append((a, name, out, said))
        if a == 13:
            raise ValueError("ORA-20001: thirteen is not taken")
        return {2: decimal.Decimal(a) * 2 + decimal.Decimal("0.005"), 3: f"{said}-{name}"}

    def plus_one(out, a):
        calls.append((out, a))
        return {0: None if a is None else a + 1}

    def stores(*values):
        calls.append(values)
        return {}

    monkeypatch.setattr(SqliteSession, "procedures", {"pkg.twice": twice, "plus_one": plus_one, "stores": stores})
    on_sqlite.calls = calls
    return on_sqlite


def arguments(*given):
    return [{"column": column, "type": way, "dbtype": "AUTOMAPPING", "is_custom": "false", "custom_type": "STRUCT",
             "custom_name": ""} for column, way in given]


TWICE = arguments(("id", "IN"), ("name", "IN"), ("twice", "OUT"), ("said", "INOUT"))


def sp(component_id="p", inputs=(), outputs=(), schema=ROWS, **config):
    made = {"use_existing_connection": True, "connection": CONN, "sp_name": "pkg.twice", "sp_args": TWICE, **config}
    return {"id": component_id, "type": "tOracleSP", "config": made, "inputs": list(inputs), "outputs": list(outputs),
            "schema": {"input": columns(schema), "output": columns(schema)}}


def for_rows(tmp_path, rows, commit=True, **config):
    """connection -> a file -> the procedure for each row -> a file."""
    (tmp_path / "in.csv").write_text(rows)
    components = [connection(schema_db=""), reader(ROWS, path=str(tmp_path / "in.csv")),
                  sp(inputs=("row1",), outputs=("row2",), **config), writer(ROWS, path=str(tmp_path / "out.csv"))]
    if commit:
        components.append({"id": "c", "type": "tOracleCommit", "config": {"connection": CONN}, "inputs": [], "outputs": []})
    return job(components, [flow("row1", "in", "p"), flow("row2", "p", "out")],
               triggers=after(CONN, "in", *(["c"] if commit else [])))


def run(made, **more):
    return run_job(made, registry=WITH_DOES, **more)


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made, registry=WITH_DOES)
    return [f"{refusal.key}: {refusal.reason}" for refusal in refused.value.report]


# ------------------------------------------------------------------
# For each row
# ------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["oracle_sp", "OracleSP", "tOracleSP"])
def test_it_is_called_for_each_row_and_what_comes_out_goes_into_the_rows(procedures, tmp_path, kind):
    made = for_rows(tmp_path, "1;ann;;a\n2;bob;9.99;\n")
    made["components"][2]["type"] = kind
    result = run(made)
    assert result.status == "success", result.error
    assert (tmp_path / "out.csv").read_text() == "id;name;twice;said\n1;ann;2.01;a-ann\n2;bob;4.01;-bob\n"
    # What goes in: the row's values where a value goes in, and nothing where one only comes out.
    assert procedures.calls == [(1, "ann", None, "a"), (2, "bob", None, "")]
    session = procedures.sessions[0]
    assert ("call", "begin pkg.twice(:1, :2, :3, :4); end;", 2) in session.did


def test_what_it_did_waits_for_a_commit_and_is_the_jobs_failure_without_one(procedures, tmp_path):
    # What a procedure changed cannot be seen from outside: a call counts as work that waits.
    result = run(for_rows(tmp_path, "1;ann;;a\n", commit=False))
    assert (result.status, result.failed_component) == ("failed", CONN)
    assert "what p did on the session" in result.error


def test_a_function_puts_what_it_returns_into_its_column(procedures, tmp_path):
    made = for_rows(tmp_path, "1;ann;;a\n;bob;;b\n", sp_name="plus_one", is_function=True, return_column="twice",
                    sp_args=arguments(("id", "IN")))
    result = run(made)
    assert result.status == "success", result.error
    assert (tmp_path / "out.csv").read_text() == "id;name;twice;said\n1;ann;2.00;a\n;bob;;b\n"
    assert procedures.calls == [(None, 1), (None, None)]
    assert "begin :1 := plus_one(:2); end;" in procedures.sessions[0].asked


def test_a_call_that_fails_fails_the_job_and_names_the_row(procedures, tmp_path):
    result = run(for_rows(tmp_path, "1;ann;;a\n13;bad;;b\n3;cy;;c\n"))
    assert (result.status, result.failed_component) == ("failed", "p")
    assert result.failures["p"] == f"the call failed: ORA-20001: thirteen is not taken; the row is line 2 of {tmp_path / 'in.csv'}"


def test_a_true_or_false_goes_in_as_one_or_nought(procedures, tmp_path):
    (tmp_path / "in.csv").write_text("true;x\nfalse;x\n")
    components = [connection(schema_db=""), reader("ok:bool, x:str", path=str(tmp_path / "in.csv")),
                  sp(inputs=("row1",), schema="ok:bool, x:str", sp_name="stores", sp_args=arguments(("ok", "IN")))]
    run(job(components, [flow("row1", "in", "p")], triggers=after(CONN, "in")))
    assert procedures.calls == [(1,), (0,)]
    # As numbers: PL/SQL's own true/false is no number, and the driver would hand a true/false over as that.
    assert [type(call[0]) for call in procedures.calls] == [int, int]


def test_with_a_session_of_its_own_what_it_did_is_stored_when_the_subjob_is_done(procedures, tmp_path):
    (tmp_path / "in.csv").write_text("1;ann;;a\n")
    components = [reader(ROWS, path=str(tmp_path / "in.csv")),
                  sp(inputs=("row1",), use_existing_connection=False, connection="", **{**BLOCK, "schema_db": ""})]
    result = run(job(components, [flow("row1", "in", "p")]))
    assert result.status == "success", result.error
    assert procedures.sessions[0].did[-2:] == ["commit", "close"]


def test_a_moment_that_only_goes_in_is_said_to_be_one(procedures, tmp_path, monkeypatch):
    """Found on 2026-10-13 against the real database: a procedure handed 13:14:15.123456 got 13:14:15. A driver
    takes a moment for a date unless it is told."""
    told = []
    plain = SqliteSession.call

    def noting(self, block, rows, outs, ins=None):
        told.append((dict(outs), dict(ins or {})))
        return plain(self, block, rows, outs, ins)

    monkeypatch.setattr(SqliteSession, "call", noting)
    monkeypatch.setitem(SqliteSession.procedures, "takes", lambda at, name, back, day: {2: at})
    rows = "at:datetime@%Y-%m-%d %H:%M:%S.%f, name:str, back:datetime@%Y-%m-%d %H:%M:%S.%f, day:date@%Y-%m-%d"
    (tmp_path / "in.csv").write_text("2024-01-31 13:14:15.123456;ann;;2024-01-31\n")
    components = [connection(schema_db=""), reader(rows, path=str(tmp_path / "in.csv")),
                  sp(inputs=("row1",), outputs=("row2",), schema=rows, sp_name="takes",
                     sp_args=arguments(("at", "IN"), ("name", "IN"), ("back", "INOUT"), ("day", "IN"))),
                  writer(rows, path=str(tmp_path / "out.csv")),
                  {"id": "c", "type": "tOracleCommit", "config": {"connection": CONN}, "inputs": [], "outputs": []}]
    result = run(job(components, [flow("row1", "in", "p"), flow("row2", "p", "out")], triggers=after(CONN, "in", "c")))
    assert result.status == "success", result.error
    # The moment that goes in is said; the one that also comes out is said with what comes out; a text and a day
    # are what a driver takes them for.
    assert told == [({2: "datetime"}, {0: "datetime"})]


def test_a_procedure_that_stores_by_itself_what_waited_is_told(procedures, tmp_path, monkeypatch, caplog):
    def commits(self, block, rows, outs, ins=None):
        self._held.execute("commit")
        return {}

    monkeypatch.setattr(SqliteSession, "call", commits)
    (tmp_path / "in.csv").write_text("1;ann;;a\n")
    components = [connection(schema_db=""),
                  {"id": "d", "type": "does", "config": {"connection": CONN, "statement": "insert into t values (1)"},
                   "inputs": [], "outputs": []},
                  reader(ROWS, path=str(tmp_path / "in.csv")), sp(inputs=("row1",), sp_name="stores", sp_args=[])]
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result = run(job(components, [flow("row1", "in", "p")], triggers=after(CONN, "d", "in")))
    assert result.status == "success", result.error
    assert ("[p] the procedure stored what waited on the session by itself: the work of d is stored now, with no "
            "commit of the job's") in caplog.text
    assert procedures.stored() == [(1,)]


def test_a_procedure_that_stores_nothing_by_itself_is_not_said_to(procedures, tmp_path, caplog):
    (tmp_path / "in.csv").write_text("1;ann;;a\n")
    components = [connection(schema_db=""),
                  {"id": "d", "type": "does", "config": {"connection": CONN, "statement": "insert into t values (1)"},
                   "inputs": [], "outputs": []},
                  reader(ROWS, path=str(tmp_path / "in.csv")), sp(inputs=("row1",), sp_name="stores", sp_args=[]),
                  {"id": "c", "type": "tOracleCommit", "config": {"connection": CONN}, "inputs": [], "outputs": []}]
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result = run(job(components, [flow("row1", "in", "p")], triggers=after(CONN, "d", "in", "c")))
    assert result.status == "success", result.error
    assert "stored what waited" not in caplog.text


def test_the_language_of_the_session_is_set_before_the_call(procedures, tmp_path, monkeypatch):
    plain = SqliteSession.run
    monkeypatch.setattr(SqliteSession, "run", lambda self, statement, binds=None: (
        self.asked.append(statement) or 0) if statement.startswith("alter session") else plain(self, statement, binds))
    run(for_rows(tmp_path, "1;ann;;a\n", nls_language="FRENCH", nls_territory="NONE"))
    asked = procedures.sessions[0].asked
    assert "alter session set nls_language = 'FRENCH'" in asked
    assert not [statement for statement in asked if "nls_territory" in statement]
    assert asked.index("alter session set nls_language = 'FRENCH'") < asked.index("begin pkg.twice(:1, :2, :3, :4); end;")


def test_what_comes_out_is_made_the_kind_its_column_is_declared(procedures, tmp_path, monkeypatch):
    """Oracle hands out a number with every digit, and a date with a time of day."""
    import datetime

    def out(*values):
        return {0: decimal.Decimal("7.9"), 1: decimal.Decimal("1.5"), 2: decimal.Decimal("0"), 3: decimal.Decimal("42"),
                4: datetime.datetime(2024, 3, 5, 13, 14), 5: datetime.datetime(2024, 3, 5, 13, 14), 6: None,
                7: decimal.Decimal("-0.5"), 8: decimal.Decimal("2.345"), 9: None, 10: None, 11: decimal.Decimal("5")}

    monkeypatch.setattr(SqliteSession, "procedures", {"kinds": out})
    schema = ("i:int, f:float, b:bool, s:str, day:date@%Y-%m-%d, at:datetime@%Y-%m-%d %H:%M, none:int, yes:bool, "
              "m:Decimal#2, nowhen:datetime@%Y-%m-%d, noday:date@%Y-%m-%d, free:Decimal")
    names = [part.split(":")[0].strip() for part in schema.split(",")]
    out_file = str(tmp_path / "out.csv")
    components = [connection(schema_db="", auto_commit=True),
                  sp(outputs=("row1",), schema=schema, sp_name="kinds", sp_args=arguments(*[(name, "OUT") for name in names])),
                  writer(schema, path=out_file, inputs=("row1",))]
    result = run(job(components, [flow("row1", "p", "out")], triggers=after(CONN, "p")))
    assert result.status == "success", result.error
    assert open(out_file).read().splitlines()[1] == "7;1.5;false;42;2024-03-05;2024-03-05 13:14;;true;2.35;;;5"


# ------------------------------------------------------------------
# Once
# ------------------------------------------------------------------

def test_set_off_by_a_trigger_it_is_called_once_with_nothing_handed_in(procedures, tmp_path):
    out = str(tmp_path / "out.csv")
    components = [connection(schema_db="", auto_commit=True),
                  sp(outputs=("row1",), sp_name="plus_one", is_function=True, return_column="twice", sp_args=arguments(("id", "IN"))),
                  writer(ROWS, path=out, inputs=("row1",))]
    result = run(job(components, [flow("row1", "p", "out")], triggers=after(CONN, "p")))
    assert result.status == "success", result.error
    assert procedures.calls == [(None, None)]
    assert open(out).read() == "id;name;twice;said\n;;;\n"


def test_a_procedure_with_no_argument_is_called_as_its_name(procedures, tmp_path):
    components = [connection(schema_db=""), sp(sp_name="stores", sp_args=[])]
    run(job(components, [], triggers=after(CONN, "p")))
    assert procedures.calls == [()]
    assert "begin stores; end;" in procedures.sessions[0].asked


# ------------------------------------------------------------------
# What refuses the job
# ------------------------------------------------------------------

def test_what_refuses_the_job_when_it_loads(procedures):
    def of(**config):
        return refusals(job([connection(), sp(**config)], []))

    assert of(sp_name="") == ["sp_name: is no name of a procedure: a name, or names with a dot between"]
    assert of(sp_name="p; drop table x") == ["sp_name: is no name of a procedure: a name, or names with a dot between"]
    assert of(sp_args=arguments(("id", "RECORDSET"))) == [
        "sp_args[0].type: a cursor a procedure hands out is not read; read its rows with an input"]
    assert of(sp_args=arguments(("id", "BOTH"))) == ["sp_args[0].type: 'BOTH' is none of IN, OUT, INOUT"]
    assert of(sp_args=arguments(("nope", "IN"))) == [
        "sp_args[0].column: 'nope' is no column of the schema (id, name, twice, said)"]
    custom = arguments(("id", "IN"))
    custom[0]["is_custom"] = "true"
    assert of(sp_args=custom) == ["sp_args[0].is_custom: a STRUCT or an ARRAY is not handed to a procedure"]
    typed = arguments(("id", "OUT"))
    typed[0]["dbtype"] = "BLOB"
    assert of(sp_args=typed) == ["sp_args[0].dbtype: a BLOB that comes out of a procedure is not read"]
    typed[0]["dbtype"] = "VARCHAR9"
    assert of(sp_args=typed) == [
        "sp_args[0].dbtype: 'VARCHAR9' is no type; the types are AUTOMAPPING, DECIMAL, NUMERIC, DATE, TIMESTAMP, CLOB"]
    assert of(is_function=True, return_column="nope") == [
        "return_column: 'nope' is no column of the schema (id, name, twice, said)"]
    assert of(is_function=True, return_column="twice", return_bdtype="XMLTYPE") == [
        "return_bdtype: a XMLTYPE that comes out of a procedure is not read"]
    assert of(nls_language="x'; drop") == ["nls_language: is no name of a language or a territory"]
    bare = sp()
    bare["schema"] = {"input": [], "output": []}
    assert refusals(job([connection(), bare], [])) == ["schema: a stored procedure needs its columns declared"]
    assert refusals(job([sp(use_existing_connection=False, connection="")], [])) == [
        "host: is empty; a session is opened with a host and a SID", "dbname: is empty; a session is opened with a host and a SID",
        "user: is empty"]


def test_what_goes_in_only_may_be_of_a_type_that_is_not_read_coming_out(procedures):
    typed = arguments(("id", "IN"))
    typed[0]["dbtype"] = "BLOB"
    load_job(job([connection(), sp(sp_args=typed)], []), registry=WITH_DOES)


def test_what_a_value_comes_out_as(procedures, tmp_path):
    typed = arguments(("id", "OUT"), ("name", "OUT"), ("twice", "OUT"), ("said", "OUT"))
    for at, kind in enumerate(("NUMERIC", "CLOB", "DECIMAL", "AUTOMAPPING")):
        typed[at]["dbtype"] = kind
    seen = {}

    def noting(self, block, rows, outs, ins=None):
        seen.update(outs)
        return {place: [None] * len(rows) for place in outs}

    import pytest as _pytest
    patch = _pytest.MonkeyPatch()
    patch.setattr(SqliteSession, "call", noting)
    try:
        run(job([connection(schema_db=""), sp(sp_name="stores", sp_args=typed, schema="id:int, name:str, twice:datetime, said:date")],
                [], triggers=after(CONN, "p")))
    finally:
        patch.undo()
    assert seen == {0: "number", 1: "large text", 2: "number", 3: "date"}
