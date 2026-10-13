"""Oracle row against a real Oracle: statements once and for each row, PL/SQL, and what Oracle stores by itself."""
import copy
import json
import logging
import secrets
from pathlib import Path

import pytest

from src.v2 import run_job
from tests.v2.components.kit import columns, flow, job, reader  # noqa: F401

pytestmark = pytest.mark.oracle

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tOracleRow_0.1.json"


def row(oracle_db, query, component_id="r", own=True, inputs=(), **config):
    block = oracle_db.block() if own else {"use_existing_connection": True, "connection": "conn"}
    return {"id": component_id, "type": "tOracleRow", "inputs": list(inputs), "outputs": [],
            "schema": {"input": columns("ID:int, V:str") if inputs else [], "output": []},
            "config": {"use_existing_connection": False, **block, "query": query, **config}}


def held_in(oracle_db, table):
    return oracle_db.rows(f"select n, v from {table} order by n")


def test_a_statement_is_run_once_with_its_values_bound_and_stored_when_it_is_done(oracle_db, table):
    query = '"insert into " + context.t + " (n, v) values (" + context.n + ", \'" + context.who + "\')"'
    made = job([row(oracle_db, query, use_nb_line="NB_LINE_INSERTED")], [])
    made["context"] = {"t": table, "n": 7, "who": "o'brien"}
    result = run_job(made)
    assert result.status == "success", result.error
    assert held_in(oracle_db, table) == [(7, "o'brien")]
    assert result.global_map["r_QUERY"] == f"insert into {table} (n, v) values (7, :context_who)"
    assert result.global_map["r_NB_LINE_INSERTED"] == 1


def test_a_statement_for_each_row_of_a_flow(oracle_db, table, tmp_path):
    (tmp_path / "in.csv").write_text("1;a\n2;b\n3;much too long a text for the column\n4;d\n")
    query = f'"insert into {table} (n, v) values (" + row1.ID + ", \'" + row1.V + "\')"'
    made = job([reader("ID:int, V:str", path=str(tmp_path / "in.csv")), row(oracle_db, query, inputs=("row1",))],
               [flow("row1", "in", "r")])
    result = run_job(made)
    assert (result.status, result.failed_component) == ("failed", "r")
    assert result.error.startswith("the database refused the statement for a row: ORA-12899:")
    assert result.error.endswith(f"the row is line 3 of {tmp_path / 'in.csv'}")
    assert held_in(oracle_db, table) == []
    made["components"][1]["config"]["die_on_error"] = False
    result = run_job(made)
    assert result.status == "success", result.error
    assert held_in(oracle_db, table) == [(1, "a"), (2, "b"), (4, "d")]


def test_a_prepared_statement_for_each_row(oracle_db, table, tmp_path):
    (tmp_path / "in.csv").write_text("1;a\n2;b\n")
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"insert into {table} values (1, 'old')")
        cursor.execute(f"insert into {table} values (2, 'old')")
        held.commit()
    given = [{"parameter_index": "1", "parameter_type": "String", "parameter_value": "row1.V"},
             {"parameter_index": "2", "parameter_type": "String", "parameter_value": "context.tag"},
             {"parameter_index": "3", "parameter_type": "Int", "parameter_value": "row1.ID"}]
    made = job([reader("ID:int, V:str", path=str(tmp_path / "in.csv")),
                row(oracle_db, f"update {table} set v = ? || ? where n = ?", inputs=("row1",), use_nb_line="NB_LINE_UPDATED",
                    use_preparedstatement=True, set_preparedstatement_parameters=given)], [flow("row1", "in", "r")])
    made["context"] = {"tag": "!"}
    result = run_job(made)
    assert result.status == "success", result.error
    assert held_in(oracle_db, table) == [(1, "a!"), (2, "b!")]
    assert result.global_map["r_NB_LINE_UPDATED"] == 2


def test_a_statement_that_defines_takes_its_value_as_text(oracle_db, table):
    made = job([row(oracle_db, f"comment on table {table} is 'loaded by ${{context.who}}'")], [])
    made["context"] = {"who": "o'brien"}
    result = run_job(made)
    assert result.status == "success", result.error
    assert oracle_db.rows("select comments from user_tab_comments where table_name = :n", n=table) == [("loaded by o'brien",)]
    assert result.global_map["r_QUERY"] == f"comment on table {table} is 'loaded by ' || :context_who"


def test_a_block_that_defines_stores_what_waited_and_the_log_says_so(oracle_db, table, caplog):
    components = [
        {"id": "conn", "type": "tOracleConnection", "config": oracle_db.block(), "inputs": [], "outputs": []},
        row(oracle_db, f"insert into {table} values (1, 'waits')", component_id="first", own=False),
        row(oracle_db, f"begin execute immediate 'comment on table {table} is ''x'''; end;", own=False),
    ]
    made = job(components, [], triggers=[{"type": "OnSubjobOk", "from": a, "to": b} for a, b in (("conn", "first"), ("first", "r"))])
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result = run_job(made)
    # Nothing waits when the job ends, so it has not failed; and it says what the block did.
    assert result.status == "success", result.error
    assert held_in(oracle_db, table) == [(1, "waits")]
    assert "[r] the statement stored what waited on the session by itself: the work of first is stored now" in caplog.text


@pytest.mark.parametrize("die_on_error", [True, False])
def test_a_block_that_commits_and_then_fails_has_stored_what_waited_and_the_log_says_so(oracle_db, table, caplog, die_on_error):
    components = [
        {"id": "conn", "type": "tOracleConnection", "config": oracle_db.block(), "inputs": [], "outputs": []},
        row(oracle_db, f"insert into {table} values (1, 'waits')", component_id="first", own=False),
        row(oracle_db, "begin commit; raise_application_error(-20001, 'no'); end;", own=False, die_on_error=die_on_error),
    ]
    made = job(components, [], triggers=[{"type": "OnSubjobOk", "from": a, "to": b} for a, b in (("conn", "first"), ("first", "r"))])
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result = run_job(made)
    assert result.status == ("failed" if die_on_error else "success")
    # Stored, though the statement failed; said; and the job does not end saying it was never stored.
    assert held_in(oracle_db, table) == [(1, "waits")]
    assert "[r] the statement stored what waited on the session by itself: the work of first is stored now" in caplog.text
    assert list(result.failures) == (["r"] if die_on_error else [])


def test_a_statement_that_defines_is_refused_over_work_that_waits(oracle_db, table):
    components = [
        {"id": "conn", "type": "tOracleConnection", "config": oracle_db.block(), "inputs": [], "outputs": []},
        row(oracle_db, f"insert into {table} values (1, 'waits')", component_id="first", own=False),
        row(oracle_db, f"truncate table {table}", own=False),
    ]
    made = job(components, [], triggers=[{"type": "OnSubjobOk", "from": a, "to": b} for a, b in (("conn", "first"), ("first", "r"))])
    result = run_job(made)
    assert result.failed_component == "r" and "the work of first would be stored with it" in result.failures["r"]
    assert held_in(oracle_db, table) == []


def test_the_converted_sample_runs_as_it_is_but_for_its_password(oracle_db):
    """connection -> a block that makes a table unless it is there -> a commit that follows by a flow."""
    made = json.loads(SAMPLE.read_text())
    for component in made["components"]:
        if component["type"] == "tOracleConnection":
            component["config"].update(oracle_db.block(schema_db=""))
    try:
        for _ in range(2):
            result = run_job(copy.deepcopy(made))
            assert result.status == "success", result.error
        assert oracle_db.rows("select count(*) from user_tables where table_name = 'TALEND_TEST'") == [(1,)]
    finally:
        with oracle_db.connect() as held, held.cursor() as cursor:
            cursor.execute("begin execute immediate 'drop table TALEND_TEST purge'; exception when others then null; end;")


def test_a_value_in_a_remark_of_the_statement_cannot_end_the_remark(oracle_db, table):
    # Found by the review of the group: sent as it was, this deleted every row of the table.
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.executemany(f"insert into {table} values (:1, :2)", [(1, "a"), (2, "b"), (3, "c")])
        held.commit()
    made = job([row(oracle_db, f"delete from {table} where n = 2 -- asked by ${{context.why}}\n")], [])
    made["context"] = {"why": "'\n or 1=1 --'"}
    result = run_job(made)
    assert (result.status, result.failed_component) == ("failed", "r")
    assert result.error.startswith("what context.why holds is written into the statement")
    assert held_in(oracle_db, table) == [(1, "a"), (2, "b"), (3, "c")]
    made["context"] = {"why": "the_cleanup"}
    assert run_job(made).status == "success"
    assert held_in(oracle_db, table) == [(1, "a"), (3, "c")]


# ------------------------------------------------------------------
# For each row: what is no insert, update, delete or merge. Found while the review's findings were looked into: the
# driver takes only those four for many rows the way they were all sent, and the stand-in of the other tests
# takes anything.
# ------------------------------------------------------------------

CONNECTION = {"id": "conn", "type": "tOracleConnection", "inputs": [], "outputs": []}


def for_rows(oracle_db, tmp_path, lines, query, own=True, **config):
    (tmp_path / "in.csv").write_text(lines)
    components = [reader("ID:int, V:str", path=str(tmp_path / "in.csv")), row(oracle_db, query, own=own, inputs=("row1",), **config)]
    if own:
        return job(components, [flow("row1", "in", "r")])
    connection = {**CONNECTION, "config": oracle_db.block()}
    return job([connection] + components, [flow("row1", "in", "r")], triggers=[{"type": "OnSubjobOk", "from": "conn", "to": "in"}])


def test_a_block_for_each_row_with_the_rows_values_bound(oracle_db, table, tmp_path, caplog):
    query = f'"begin insert into {table} (n, v) values (" + row1.ID + ", \'" + row1.V + "\'); end;"'
    lines = "1;a\n2;b\n3;much too long a text for the column\n4;d\n5;also much too long a text for it\n"
    result = run_job(for_rows(oracle_db, tmp_path, lines, query))
    assert (result.status, result.failed_component) == ("failed", "r")
    assert result.error.startswith("the database refused the statement for a row: ORA-12899:")
    assert result.error.endswith(f"the row is line 3 of {tmp_path / 'in.csv'}")
    assert held_in(oracle_db, table) == []
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result = run_job(for_rows(oracle_db, tmp_path, lines, query, die_on_error=False))
    assert result.status == "success", result.error
    assert held_in(oracle_db, table) == [(1, "a"), (2, "b"), (4, "d")]
    assert "[r] the database refused the statement for 2 of the 5 rows; the first: ORA-12899:" in caplog.text


def test_a_block_for_each_row_that_commits_and_fails_for_a_row_says_why_and_what_stays(oracle_db, table, tmp_path):
    # Found on the second pass: the job was told only ORA-01086, that the place marked before the statement was
    # gone, and nothing of the row or of what stayed stored.
    query = f'"begin insert into {table} (n, v) values (" + row1.ID + ", \'" + row1.V + "\'); commit; end;"'
    result = run_job(for_rows(oracle_db, tmp_path, "1;a\n2;b\n3;much too long a text for the column\n4;d\n", query))
    assert (result.status, result.failed_component) == ("failed", "r")
    assert result.error.startswith("the database refused the statement for a row: ORA-12899:")
    assert f"the row is line 3 of {tmp_path / 'in.csv'}" in result.error
    assert "; what the statement did before that could not be taken back (ORA-01086:" in result.error
    assert result.error.endswith("a statement that stores by itself leaves no place to go back to")
    assert held_in(oracle_db, table) == [(1, "a"), (2, "b"), (4, "d")]


@pytest.mark.parametrize("statement, left", [
    # A query, which is run row by row with the row's values as plain values.
    ('"select 1 / (select count(*) from {t} where at = " + row1.AT + " and amt = " + row1.AMT + ") from dual"', [1, 2]),
    # An update and a block, which go for all the rows at once.
    ('"update {t} set id = id + 10 where at = " + row1.AT + " and amt = " + row1.AMT', [11, 12]),
    ('"begin update {t} set id = id + 10 where at = " + row1.AT + " and amt = " + row1.AMT + "; end;"', [11, 12]),
])
def test_a_statement_for_each_row_finds_a_row_by_a_moment_with_a_fraction_of_a_second(oracle_db, tmp_path, statement, left):
    """Found on 2026-10-13, in either mode: the query found no row. A driver takes a moment for a date unless it is
    told, and a date has no fraction of a second. (With Oracle's own client the rows of the other two go as plain
    values too.)"""
    name = f"V2K_{secrets.token_hex(5).upper()}"
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"create table {name} (id number, at timestamp(6), amt number(10,3))")
        cursor.execute(f"insert into {name} values (1, timestamp '2024-01-31 13:14:15.123456', 0.125)")
        cursor.execute(f"insert into {name} values (2, timestamp '2024-01-31 13:14:15.000001', 2.5)")
        held.commit()
    rows = "ID:int, AT:datetime@%Y-%m-%d %H:%M:%S.%f, AMT:float"
    (tmp_path / "in.csv").write_text("1;2024-01-31 13:14:15.123456;0.125\n2;2024-01-31 13:14:15.000001;2.5\n")
    made = {"id": "r", "type": "tOracleRow", "inputs": ["row1"], "outputs": [],
            "schema": {"input": columns(rows), "output": []},
            "config": {**oracle_db.block(), "use_existing_connection": False, "query": statement.format(t=name)}}
    try:
        result = run_job(job([reader(rows, path=str(tmp_path / "in.csv")), made], [flow("row1", "in", "r")]))
        assert result.status == "success", result.error
        assert [found for (found,) in oracle_db.rows(f"select id from {name} order by id")] == left
    finally:
        with oracle_db.connect() as held, held.cursor() as cursor:
            cursor.execute(f"drop table {name} purge")


def test_a_block_that_cannot_be_compiled_is_no_rows_fault(oracle_db, tmp_path):
    """The place the driver gives for such a fault is one in the block's text: column 7 was taken for row 7."""
    lines = "".join(f"{at};a\n" for at in range(1, 41))
    result = run_job(for_rows(oracle_db, tmp_path, lines, '"begin v2r_no_such_procedure(" + row1.ID + "); end;"'))
    assert (result.status, result.failed_component) == ("failed", "r")
    assert "PLS-00201" in result.error and "the row is" not in result.error
    # With `die_on_error` off the job goes on, and nothing is said to have been refused for a row.
    result = run_job(for_rows(oracle_db, tmp_path, lines, '"begin v2r_no_such_procedure(" + row1.ID + "); end;"',
                              die_on_error=False))
    assert result.status == "success", result.error
    assert "PLS-00201" in result.global_map["r_ERROR_MESSAGE"] and "rows" not in result.global_map["r_ERROR_MESSAGE"]


def test_an_insert_that_reads_the_table_it_writes_sees_for_each_row_what_the_rows_before_it_put_there(oracle_db, table, tmp_path):
    """Found while the review's findings were looked into. Sent for all its rows at once, Oracle gave every row the
    same number, and the job said nothing."""
    query = f'"insert into {table} (n, v) values ((select nvl(max(n), 0) + 1 from {table}), \'" + row1.V + "\')"'
    result = run_job(for_rows(oracle_db, tmp_path, "7;a\n8;b\n9;c\n", query, use_nb_line="NB_LINE_INSERTED"))
    assert result.status == "success", result.error
    assert held_in(oracle_db, table) == [(1, "a"), (2, "b"), (3, "c")]
    assert result.global_map["r_NB_LINE_INSERTED"] == 3


def test_a_query_for_each_row_is_run_and_needs_no_commit(oracle_db, table, tmp_path):
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"insert into {table} values (1, 'a')")
        held.commit()
    query = f'"select count(*) from {table} where n = " + row1.ID + " and v = \'" + row1.V + "\'"'
    result = run_job(for_rows(oracle_db, tmp_path, "1;a\n2;b\n3;c\n", query, own=False))
    assert result.status == "success", result.error
    # A query that fails for one row is that row's fault, and the session is there for the next.
    query = f'"select to_number(v) / (2 - " + row1.ID + ") from {table}"'
    result = run_job(for_rows(oracle_db, tmp_path, "1;a\n2;b\n", query, own=False))
    assert (result.status, result.failed_component) == ("failed", "r")
    assert result.error.endswith(f"the row is line 1 of {tmp_path / 'in.csv'}")


def test_a_statement_with_nothing_of_the_row_in_it_is_run_once_for_each_row(oracle_db, table, tmp_path):
    query = f"insert into {table} (n, v) values ((select nvl(max(n), 0) + 1 from {table}), 'x')"
    result = run_job(for_rows(oracle_db, tmp_path, "7;a\n8;b\n9;c\n", query, use_nb_line="NB_LINE_INSERTED"))
    assert result.status == "success", result.error
    assert held_in(oracle_db, table) == [(1, "x"), (2, "x"), (3, "x")]
    assert result.global_map["r_NB_LINE_INSERTED"] == 3
    result = run_job(for_rows(oracle_db, tmp_path, "7;a\n8;b\n", "begin null; end;"))
    assert result.status == "success", result.error


def test_what_changed_nothing_or_was_refused_leaves_nothing_waiting_on_a_connection(oracle_db, table, tmp_path):
    """Found by the review of the group. A job with no commit that ran nothing to commit has not lost any work."""
    def on_connection(component):
        connection = {**CONNECTION, "config": oracle_db.block()}
        return job([connection, component], [], triggers=[{"type": "OnSubjobOk", "from": "conn", "to": "r"}])

    refused = row(oracle_db, "delete from v2r_no_such_table", own=False, die_on_error=False)
    result = run_job(on_connection(refused))
    assert result.status == "success", result.error
    finds_none = f'"update {table} set v = v where n = 1000 + " + row1.ID'
    result = run_job(for_rows(oracle_db, tmp_path, "1;a\n2;b\n", finds_none, own=False))
    assert result.status == "success", result.error
    every_row_refused = '"insert into v2r_no_such_table values (" + row1.ID + ")"'
    result = run_job(for_rows(oracle_db, tmp_path, "1;a\n2;b\n", every_row_refused, own=False, die_on_error=False))
    assert result.status == "success", result.error
    # What did change something still waits, and a job that ends without a commit has failed.
    changes = f'"insert into {table} (n, v) values (" + row1.ID + ", \'" + row1.V + "\')"'
    result = run_job(for_rows(oracle_db, tmp_path, "1;a\n", changes, own=False))
    assert (result.status, result.failed_component) == ("failed", "conn")
    assert held_in(oracle_db, table) == []
