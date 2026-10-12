"""Oracle bulk exec against a real Oracle: a file loaded as SQL*Loader's actions mean it."""
import secrets

import pytest

from src.v2 import run_job
from tests.v2.components.kit import columns, job

pytestmark = pytest.mark.oracle

ROWS = "ID:int, NAME:str, AMT:Decimal#2, DAY:datetime@%Y-%m-%d"


@pytest.fixture
def emp(oracle_db):
    name = f"V2B_{secrets.token_hex(5).upper()}"
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"create table {name} (id number(10) primary key, name varchar2(8), amt number(12,2), day date)")
    yield name
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"drop table {name} purge")


def loading(oracle_db, tmp_path, table, text, **config):
    (tmp_path / "load.dat").write_text(text)
    bulk = {"id": "b", "type": "tOracleBulkExec", "inputs": [], "outputs": [], "schema": {"input": columns(ROWS), "output": []},
            "config": {**oracle_db.block(), "use_existing_connection": False, "table": table, "data": str(tmp_path / "load.dat"),
                       **config}}
    return run_job(job([bulk], []))


def held_in(oracle_db, table):
    return oracle_db.rows(f"select id, name, to_char(amt), to_char(day, 'YYYY-MM-DD') from {table} order by id")


def test_a_file_is_loaded_and_stored_when_the_load_is_done(oracle_db, emp, tmp_path):
    result = loading(oracle_db, tmp_path, emp, "1;ann;1.5;2024-01-31\n2;bob;;\n")
    assert result.status == "success", result.error
    assert held_in(oracle_db, emp) == [(1, "ann", "1.5", "2024-01-31"), (2, "bob", None, None)]
    held = result.global_map
    assert (held["b_NB_LINE_DATA"], held["b_NB_LINE_INSERTED"], held["b_NB_LINE_BAD"], held["b_RETURN_CODE"]) == (2, 2, 0, 0)


def test_what_each_action_does_to_the_rows_the_table_holds(oracle_db, emp, tmp_path):
    assert loading(oracle_db, tmp_path, emp, "1;ann;;\n").status == "success"
    result = loading(oracle_db, tmp_path, emp, "2;bob;;\n")
    assert result.status == "failed" and "the table has to be empty" in result.error
    assert loading(oracle_db, tmp_path, emp, "2;bob;;\n", data_action="APPEND").status == "success"
    assert [row[0] for row in held_in(oracle_db, emp)] == [1, 2]
    # REPLACE is taken back with the rows; TRUNCATE is not.
    assert loading(oracle_db, tmp_path, emp, "3;much too long a name;;\n", data_action="REPLACE").status == "failed"
    assert [row[0] for row in held_in(oracle_db, emp)] == [1, 2]
    assert loading(oracle_db, tmp_path, emp, "3;cy;;\n", data_action="REPLACE").status == "success"
    assert [row[0] for row in held_in(oracle_db, emp)] == [3]
    assert loading(oracle_db, tmp_path, emp, "4;much too long a name;;\n", data_action="TRUNCATE").status == "failed"
    assert held_in(oracle_db, emp) == []


def test_rows_the_database_refuses_up_to_the_number_the_load_allows(oracle_db, emp, tmp_path):
    text = "1;ann;;\n1;again;;\n2;much too long;;\n3;cy;;\n"
    result = loading(oracle_db, tmp_path, emp, text)
    assert result.status == "failed" and result.error.startswith("the database refused row 2 of the rows it was handed: ORA-00001")
    assert held_in(oracle_db, emp) == []
    result = loading(oracle_db, tmp_path, emp, text, options=["ERRORS", "2", "ROWS", "3"])
    assert result.status == "success", result.error
    assert [row[0] for row in held_in(oracle_db, emp)] == [1, 3]
    assert (result.global_map["b_NB_LINE_BAD"], result.global_map["b_RETURN_CODE"]) == (2, 2)


def test_a_line_that_cannot_be_read_never_reaches_the_database(oracle_db, emp, tmp_path):
    result = loading(oracle_db, tmp_path, emp, "1;ann;1.5;2024-01-31\n2;bob;x;\n")
    assert result.status == "failed" and f"line 2 of {tmp_path / 'load.dat'}" in result.error
    assert held_in(oracle_db, emp) == []
