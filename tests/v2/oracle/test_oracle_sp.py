"""Oracle stored procedure against a real Oracle: values in and out for many rows, a function, a call that fails."""
import secrets

import pytest

from src.v2 import run_job
from tests.v2.components.kit import columns, flow, job, reader, writer

pytestmark = pytest.mark.oracle

ROWS = "ID:int, NAME:str, TWICE:Decimal#3, SAID:str, DAY:date@%Y-%m-%d, AT:datetime@%Y-%m-%d %H:%M:%S.%f, BIG:str"


@pytest.fixture
def made(oracle_db, table):
    """A procedure, a function and a procedure that stores a row, each of this test's own name."""
    tag = secrets.token_hex(4).upper()
    names = {"p": f"V2P_{tag}", "f": f"V2F_{tag}", "s": f"V2S_{tag}"}
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"""create or replace procedure {names['p']} (a in number, b in varchar2, c out number,
                           d in out varchar2, e out date, f out timestamp, g out clob) as
            begin
              if a = 13 then raise_application_error(-20001, 'thirteen is not taken'); end if;
              c := a * 1.005; d := d || '-' || b; e := date '2024-03-04' + a;
              f := timestamp '2024-03-04 05:06:07.123456'; g := rpad(to_clob('x'), 40000, 'x');
            end;""")
        cursor.execute(f"create or replace function {names['f']} (a in number) return number as begin return a + 0.1234; end;")
        cursor.execute(f"create or replace procedure {names['s']} (a in number, b in varchar2) as begin "
                       f"insert into {table} values (a, b); end;")
    yield names
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"drop procedure {names['p']}")
        cursor.execute(f"drop function {names['f']}")
        cursor.execute(f"drop procedure {names['s']}")


def arguments(*given):
    return [{"column": column, "type": way, "dbtype": kind, "is_custom": "false"} for column, way, kind in given]


def calling(oracle_db, tmp_path, rows, **config):
    (tmp_path / "in.csv").write_text(rows)
    sp = {"id": "p", "type": "tOracleSP", "inputs": ["row1"], "outputs": ["row2"],
          "schema": {"input": columns(ROWS), "output": columns(ROWS)},
          "config": {**oracle_db.block(), "use_existing_connection": False, **config}}
    result = run_job(job([reader(ROWS, path=str(tmp_path / "in.csv")), sp, writer(ROWS, path=str(tmp_path / "out.csv"))],
                         [flow("row1", "in", "p"), flow("row2", "p", "out")]))
    try:
        return result, (tmp_path / "out.csv").read_text().splitlines()[1:]
    except FileNotFoundError:
        return result, None


def test_values_go_in_and_come_out_for_each_row(oracle_db, made, tmp_path):
    args = arguments(("ID", "IN", "AUTOMAPPING"), ("NAME", "IN", "AUTOMAPPING"), ("TWICE", "OUT", "AUTOMAPPING"),
                     ("SAID", "INOUT", "AUTOMAPPING"), ("DAY", "OUT", "AUTOMAPPING"), ("AT", "OUT", "TIMESTAMP"),
                     ("BIG", "OUT", "CLOB"))
    result, lines = calling(oracle_db, tmp_path, "1;ann;;a;;;\n2;;;;;;\n", sp_name=made["p"], sp_args=args)
    assert result.status == "success", result.error
    big = "x" * 40000
    assert lines == [f"1;ann;1.005;a-ann;2024-03-05;2024-03-04 05:06:07.123456;{big}",
                     f"2;;2.010;-;2024-03-06;2024-03-04 05:06:07.123456;{big}"]


def test_a_function_returns_every_digit(oracle_db, made, tmp_path):
    result, lines = calling(oracle_db, tmp_path, "1;;;;;;\n2;;;;;;\n", sp_name=made["f"], is_function=True,
                            return_column="TWICE", sp_args=arguments(("ID", "IN", "AUTOMAPPING")))
    assert result.status == "success", result.error
    assert [line.split(";")[2] for line in lines] == ["1.123", "2.123"]


def test_a_call_that_fails_names_the_row_and_what_the_others_changed_is_taken_back(oracle_db, made, table, tmp_path):
    args = arguments(("ID", "IN", "AUTOMAPPING"), ("NAME", "IN", "AUTOMAPPING"))
    result, _ = calling(oracle_db, tmp_path, "1;a;;;;;\n2;much too long a text for it;;;;;\n3;c;;;;;\n", sp_name=made["s"], sp_args=args)
    assert (result.status, result.failed_component) == ("failed", "p")
    assert result.error.startswith("the call failed: ORA-12899:")
    assert result.error.endswith(f"the row is line 2 of {tmp_path / 'in.csv'}")
    assert oracle_db.rows(f"select n from {table}") == []
    result, _ = calling(oracle_db, tmp_path, "1;a;;;;;\n3;c;;;;;\n", sp_name=made["s"], sp_args=args)
    assert result.status == "success", result.error
    assert oracle_db.rows(f"select n, v from {table} order by n") == [(1, "a"), (3, "c")]


def test_a_procedure_that_is_not_there_is_said_in_one_line(oracle_db, made, tmp_path):
    result, _ = calling(oracle_db, tmp_path, "1;a;;;;;\n", sp_name="NO_SUCH_PROC_OF_V2", sp_args=[])
    assert result.status == "failed"
    assert "NO_SUCH_PROC_OF_V2" in result.error and "\n" not in result.error and "Help:" not in result.error


def test_the_language_of_the_session_is_set(oracle_db, made, tmp_path):
    result, lines = calling(oracle_db, tmp_path, "1;a;;;;;\n", sp_name=made["f"], is_function=True, return_column="TWICE",
                            sp_args=arguments(("ID", "IN", "AUTOMAPPING")), nls_language="FRENCH", nls_territory="FRANCE")
    assert result.status == "success", result.error
    result, _ = calling(oracle_db, tmp_path, "1;a;;;;;\n", sp_name=made["f"], is_function=True, return_column="TWICE",
                        sp_args=arguments(("ID", "IN", "AUTOMAPPING")), nls_language="NO SUCH LANGUAGE")
    assert result.status == "failed" and "ORA-12705" in result.error
