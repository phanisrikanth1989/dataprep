"""Oracle row against a real Oracle: statements once and for each row, PL/SQL, and what Oracle stores by itself."""
import copy
import json
import logging
from pathlib import Path

import pytest

from src.v2 import run_job
from tests.v2.components.kit import columns, flow, job, reader

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
