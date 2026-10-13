"""Oracle output against a real Oracle: every kind of value, each action, and what the database refuses."""
import datetime
import secrets

import pytest

from src.v2 import run_job
from tests.v2.components.kit import columns, flow, job, reader

pytestmark = pytest.mark.oracle

ROWS = "ID:int, NAME:str, AMT:Decimal#2"


@pytest.fixture
def name(oracle_db):
    """The name of a table of this test's own; whatever is there under it afterwards is dropped."""
    made = f"V2O_{secrets.token_hex(5).upper()}"
    yield made
    with oracle_db.connect() as held, held.cursor() as cursor:
        try:
            cursor.execute(f"drop table {made} purge")
        except Exception:  # noqa: BLE001 -- it was never made, or the test dropped it
            pass


@pytest.fixture
def emp(oracle_db, name):
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"create table {name} (id number(10) primary key, name varchar2(8), amt number(12,2))")
        cursor.executemany(f"insert into {name} values (:1, :2, :3)", [(1, "ann", 1.5), (2, "bob", 2.5)])
        held.commit()
    return name


def keyed(schema, key="ID"):
    made = columns(schema)
    for column in made:
        column["key"] = column["name"] in key.split(",")
    return made


def loading(oracle_db, tmp_path, table, rows, schema=ROWS, key="ID", **config):
    """a file -> the table, with a session of the output's own."""
    (tmp_path / "in.csv").write_text(rows)
    sink = {"id": "db", "type": "tOracleOutput", "inputs": ["row1"], "outputs": [],
            "schema": {"input": keyed(schema, key), "output": []},
            "config": {**oracle_db.block(), "use_existing_connection": False, "table": table, **config}}
    return run_job(job([reader(schema, path=str(tmp_path / "in.csv"), die_on_error=True), sink], [flow("row1", "in", "db")]))


def held_in(oracle_db, table, what="id, name, amt"):
    return oracle_db.rows(f"select {what} from {table} order by 1")


def test_rows_are_inserted_and_stored_when_the_subjob_is_done(oracle_db, emp, tmp_path):
    result = loading(oracle_db, tmp_path, emp, "3;cy;3.456\n4;;\n")
    assert result.status == "success", result.error
    assert held_in(oracle_db, emp) == [(1, "ann", 1.5), (2, "bob", 2.5), (3, "cy", 3.46), (4, None, None)]
    assert result.global_map["db_NB_LINE_INSERTED"] == 2 and result.rows == {"db": 2}


def test_every_kind_of_value_arrives_as_it_is(oracle_db, name, tmp_path):
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"""create table {name} (id number(20), amt number(38, 4), f binary_double, ok number(1), d date,
                           ts timestamp(6), day date, v varchar2(20), big clob)""")
    schema = ("ID:Decimal#0, AMT:Decimal#4, F:float, OK:bool, D:datetime@%Y-%m-%d %H:%M:%S.%f, "
              "TS:datetime@%Y-%m-%d %H:%M:%S.%f, DAY:date@%Y-%m-%d, V:str, BIG:str")
    big = "x" * 100_000
    rows = (f"12345678901234567890;123456789012345678.1234;0.1;true;2024-01-31 13:14:15.999999;"
            f"2024-01-31 13:14:15.123456;2024-03-04;o'brien;{big}\n2;;;false;;;;;\n")
    result = loading(oracle_db, tmp_path, name, rows, schema=schema, key="")
    assert result.status == "success", result.error
    # Numbers are asked for as their digits: the plain driver would hand a wide one back as a float.
    got = oracle_db.rows(f"""select to_char(id), to_char(amt), f, ok, to_char(d, 'YYYY-MM-DD HH24:MI:SS'),
                             to_char(ts, 'YYYY-MM-DD HH24:MI:SS.FF6'), to_char(day, 'YYYY-MM-DD HH24:MI:SS'), v, length(big),
                             case when dbms_lob.compare(big, rpad(to_clob('x'), 100000, 'x')) = 0 then 'whole' end
                             from {name} order by id""")
    assert got == [
        ("2", None, None, 0, None, None, None, None, None, None),
        ("12345678901234567890", "123456789012345678.1234", 0.1, 1, "2024-01-31 13:14:15", "2024-01-31 13:14:15.123456",
         "2024-03-04 00:00:00", "o'brien", 100000, "whole"),
    ]


def test_rows_update_delete_and_upsert_by_their_key(oracle_db, emp, tmp_path):
    result = loading(oracle_db, tmp_path, emp, "2;bo;9.5\n7;nobody;1\n", data_action="UPDATE")
    assert result.status == "success", result.error
    assert held_in(oracle_db, emp) == [(1, "ann", 1.5), (2, "bo", 9.5)]
    assert result.global_map["db_NB_LINE_UPDATED"] == 1
    rows = "5;first;1\n2;b2;8\n5;second;2\n6;six;6\n5;third;3\n"
    result = loading(oracle_db, tmp_path, emp, rows, data_action="UPDATE_OR_INSERT")
    assert result.status == "success", result.error
    assert held_in(oracle_db, emp) == [(1, "ann", 1.5), (2, "b2", 8), (5, "third", 3), (6, "six", 6)]
    assert (result.global_map["db_NB_LINE_UPDATED"], result.global_map["db_NB_LINE_INSERTED"]) == (3, 2)
    result = loading(oracle_db, tmp_path, emp, "5;x;0\n9;y;0\n", data_action="DELETE")
    assert result.status == "success" and result.global_map["db_NB_LINE_DELETED"] == 1
    assert [row[0] for row in held_in(oracle_db, emp)] == [1, 2, 6]


def test_a_row_the_database_refuses_fails_the_job_and_nothing_is_stored(oracle_db, emp, tmp_path):
    result = loading(oracle_db, tmp_path, emp, "3;cy;3.5\n1;again;0\n")
    assert (result.status, result.failed_component) == ("failed", "db")
    assert result.error.startswith("the database refused row 2 of the rows it was handed (ID=1): ORA-00001:")
    assert "\n" not in result.error and "Help:" not in result.error
    assert held_in(oracle_db, emp) == [(1, "ann", 1.5), (2, "bob", 2.5)]


def test_with_die_on_error_off_the_refused_rows_are_left_out_and_counted(oracle_db, emp, tmp_path):
    rows = "3;cy;3.5\n1;again;0\n5;much too long;0\n6;ok;6.5\n7;;12345678901\n"
    result = loading(oracle_db, tmp_path, emp, rows, die_on_error=False, batch_size=2)
    assert result.status == "success", result.error
    assert [row[0] for row in held_in(oracle_db, emp)] == [1, 2, 3, 6]
    held = result.global_map
    assert (held["db_NB_LINE"], held["db_NB_LINE_INSERTED"], held["db_NB_LINE_REJECTED"]) == (5, 2, 3)
    assert held["db_ERROR_MESSAGE"].startswith(
        "the database refused 3 of the 5 rows it was handed, and they are left out; the first: row 2 of the rows it "
        "was handed (ID=1): ORA-00001:")


def test_clear_is_taken_back_with_the_rows_and_truncate_is_not(oracle_db, emp, tmp_path):
    result = loading(oracle_db, tmp_path, emp, "3;much too long;1\n", table_action="CLEAR")
    assert result.status == "failed"
    assert held_in(oracle_db, emp) == [(1, "ann", 1.5), (2, "bob", 2.5)]
    result = loading(oracle_db, tmp_path, emp, "3;much too long;1\n", table_action="TRUNCATE")
    assert result.status == "failed"
    assert held_in(oracle_db, emp) == []
    result = loading(oracle_db, tmp_path, emp, "3;cy;1\n", table_action="TRUNCATE_REUSE_STORAGE")
    assert result.status == "success" and held_in(oracle_db, emp) == [(3, "cy", 1)]


def test_a_table_is_made_and_made_again(oracle_db, name, tmp_path):
    schema = "ID:int!, NAME:str, AMT:Decimal#2, D:datetime@%Y-%m-%d, OK:bool, F:float, DAY:date@%Y-%m-%d"
    row = "1;ann;1.5;2024-01-31;true;0.5;2024-02-01\n"
    result = loading(oracle_db, tmp_path, name, row, schema=schema, table_action="DROP_IF_EXISTS_AND_CREATE")
    assert result.status == "success", result.error
    made = oracle_db.rows("select column_name, data_type, nullable from user_tab_columns where table_name = :n order by column_id",
                          n=name)
    assert made == [("ID", "NUMBER", "N"), ("NAME", "VARCHAR2", "Y"), ("AMT", "NUMBER", "Y"), ("D", "TIMESTAMP(6)", "Y"),
                    ("OK", "NUMBER", "Y"), ("F", "BINARY_DOUBLE", "Y"), ("DAY", "DATE", "Y")]
    assert oracle_db.rows("select count(*) from user_constraints where table_name = :n and constraint_type = 'P'", n=name) == [(1,)]
    assert loading(oracle_db, tmp_path, name, row, schema=schema, table_action="CREATE").error.startswith("ORA-00955")
    assert loading(oracle_db, tmp_path, name, "2" + row[1:], schema=schema, table_action="CREATE_IF_NOT_EXISTS").status == "success"
    assert oracle_db.rows(f"select id from {name} order by id") == [(1,), (2,)]
    assert loading(oracle_db, tmp_path, name, row, schema=schema, table_action="DROP_CREATE").status == "success"
    assert loading(oracle_db, tmp_path, name, row, schema=schema, table_action="DROP_IF_EXISTS_AND_CREATE").status == "success"
    assert oracle_db.rows(f"select id, name, amt, ok, f from {name}") == [(1, "ann", 1.5, 1, 0.5)]


def test_a_key_that_is_a_date_finds_its_row_and_is_compared_as_a_date(oracle_db, name, tmp_path):
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"create table {name} (d date primary key, v varchar2(10))")
        cursor.execute(f"insert into {name} values (timestamp '2024-01-31 13:14:15', 'old')")
        held.commit()
    result = loading(oracle_db, tmp_path, name, "2024-01-31 13:14:15;new\n2024-02-01 00:00:00;fresh\n",
                     schema="D:datetime@%Y-%m-%d %H:%M:%S, V:str", key="D", data_action="UPDATE_OR_INSERT")
    assert result.status == "success", result.error
    assert oracle_db.rows(f"select d, v from {name} order by d") == [
        (datetime.datetime(2024, 1, 31, 13, 14, 15), "new"), (datetime.datetime(2024, 2, 1), "fresh")]


def test_on_a_connections_session_the_rows_wait_and_a_defining_action_is_refused_over_them(oracle_db, emp, tmp_path):
    (tmp_path / "in.csv").write_text("3;cy;3.5\n")

    def made(action, with_commit):
        components = [
            {"id": "conn", "type": "tOracleConnection", "config": oracle_db.block(), "inputs": [], "outputs": []},
            reader(ROWS, path=str(tmp_path / "in.csv")),
            {"id": "db", "type": "tOracleOutput", "inputs": ["row1"], "outputs": [], "schema": {"input": keyed(ROWS), "output": []},
             "config": {"use_existing_connection": True, "connection": "conn", "table": emp}},
            reader(ROWS, component_id="in2", path=str(tmp_path / "in.csv"), outputs=("row2",)),
            {"id": "db2", "type": "tOracleOutput", "inputs": ["row2"], "outputs": [], "schema": {"input": keyed(ROWS), "output": []},
             "config": {"use_existing_connection": True, "connection": "conn", "table": emp, "table_action": action,
                        "data_action": "UPDATE"}},
        ]
        if with_commit:
            components.append({"id": "c", "type": "tOracleCommit", "config": {"connection": "conn"}, "inputs": [], "outputs": []})
        order = ["conn", "in", "in2"] + (["c"] if with_commit else [])
        return job(components, [flow("row1", "in", "db"), flow("row2", "in2", "db2")],
                   triggers=[{"type": "OnSubjobOk", "from": a, "to": b} for a, b in zip(order, order[1:])])

    result = run_job(made("TRUNCATE", True))
    assert result.failed_component == "db2" and "the work of db would be stored with it" in result.failures["db2"]
    assert held_in(oracle_db, emp) == [(1, "ann", 1.5), (2, "bob", 2.5)]
    result = run_job(made("NONE", False))
    assert result.failed_component == "conn" and held_in(oracle_db, emp) == [(1, "ann", 1.5), (2, "bob", 2.5)]
    result = run_job(made("NONE", True))
    assert result.status == "success", result.error
    assert held_in(oracle_db, emp) == [(1, "ann", 1.5), (2, "bob", 2.5), (3, "cy", 3.5)]


def test_many_rows_in_batches(oracle_db, name, tmp_path):
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"create table {name} (id number(10), name varchar2(20), amt number(12,2))")
    rows = "".join(f"{n};row {n};{n}.25\n" for n in range(1, 30001))
    result = loading(oracle_db, tmp_path, name, rows, key="", batch_size=7000)
    assert result.status == "success", result.error
    assert oracle_db.rows(f"select count(*), sum(id), to_char(sum(amt)), min(name) from {name}") == [
        (30000, 450015000, "450022500", "row 1")]
