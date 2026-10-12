"""Oracle input against a real Oracle: every type, values bound, and what the database refuses."""
import decimal
import secrets

import pytest

from src.v2 import run_job
from tests.v2.components.kit import columns, flow, job, writer

pytestmark = pytest.mark.oracle


@pytest.fixture
def wide(oracle_db):
    """A table with a column of every kind, and three rows that hurt."""
    name = f"V2W_{secrets.token_hex(5).upper()}"
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"""create table {name} (id number(20), amt number(10,3), ratio binary_double, flag number(1),
            free number, d date, ts timestamp(9), tz timestamp with time zone, v varchar2(20), c char(5), big clob,
            r raw(4), num_text varchar2(10), day_text varchar2(10))""")
        cursor.execute(f"""insert into {name} values (12345678901234567890, 1234.565, 0.1, 1, 0.5,
            timestamp '2024-01-31 13:14:15', timestamp '2024-01-31 13:14:15.123456789',
            timestamp '2024-01-31 13:14:15.5 +05:30', 'o''brien', 'ab', rpad(to_clob('x'), 40000, 'x'),
            hextoraw('DEADBEEF'), '42', '2024-02-01')""")
        cursor.execute(f"insert into {name} (id, amt, free, flag, v, num_text) values (2, -0.0005, -0.25, 0, ' pad ', ' 7 ')")
        cursor.execute(f"insert into {name} (id) values (3)")
        held.commit()
    yield name
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"drop table {name} purge")


def reading(oracle_db, tmp_path, schema, query, context=None, **config):
    out = str(tmp_path / "out.csv")
    source = {"id": "in", "type": "tOracleInput", "inputs": [], "outputs": ["row1"],
              "schema": {"input": [], "output": columns(schema)},
              "config": {**oracle_db.block(), "use_existing_connection": False, "query": query, **config}}
    made = job([source, writer(schema, path=out, inputs=("row1",))], [flow("row1", "in", "out")])
    if context:
        made["context"] = context
    result = run_job(made)
    try:
        with open(out) as held:
            return result, held.read().splitlines()
    except FileNotFoundError:
        return result, None


def test_every_kind_of_column_as_the_job_declares_it(oracle_db, wide, tmp_path):
    schema = ("id:Decimal#0, amt:Decimal#2, ratio:float, flag:bool, free:str, d:datetime@%Y-%m-%d %H:%M:%S, day:date@%Y-%m-%d, "
              "d_text:str, ts:datetime@%Y-%m-%d %H:%M:%S.%f, ts_text:str, tz:str, v:str, c:str, num:int, day2:date@%Y-%m-%d")
    query = f"select id, amt, ratio, flag, free, d, d, d, ts, ts, tz, v, c, num_text, day_text from {wide} order by id"
    result, lines = reading(oracle_db, tmp_path, schema, query)
    assert result.status == "success", result.error
    assert lines[1:] == [
        "2;0.00;;false;-0.25;;;;;;; pad ;;7;",
        ";".join(["3"] + [""] * 14),
        "12345678901234567890;1234.57;0.1;true;0.5;2024-01-31 13:14:15;2024-01-31;2024-01-31 13:14:15;"
        "2024-01-31 13:14:15.123457;2024-01-31 13:14:15.123457;2024-01-31 13:14:15.500000 +05:30;o'brien;ab   ;42;2024-02-01",
    ]


def test_a_large_text_arrives_whole(oracle_db, wide, tmp_path):
    result, lines = reading(oracle_db, tmp_path, "big:str", f"select big from {wide} where id > 3")
    assert result.status == "success", result.error
    assert lines[1] == "x" * 40000


def test_a_number_keeps_every_digit_and_is_rounded_as_oracle_rounds(oracle_db, tmp_path):
    query = ("select 12345678901234567890123456789012345678, 2.345, 2.355, -2.345, 0.5 from dual union all "
             "select 1, 2.344999, 2.3549, -2.3449, 1.5 from dual")
    result, lines = reading(oracle_db, tmp_path, "big:Decimal#0, a:Decimal#2, b:Decimal#2, c:Decimal#2, whole:int", query)
    assert result.status == "success", result.error
    assert sorted(lines[1:], key=len) == ["1;2.34;2.35;-2.34;1", "12345678901234567890123456789012345678;2.35;2.36;-2.35;0"]


@pytest.mark.parametrize("schema, query, said", [
    ("n:int", "select 12345678901234567890 from dual", "DPY-4036"),
    ("n:Decimal#35", "select 1234.5 from dual", "ORA-01438"),
])
def test_a_number_too_large_for_its_column_fails_the_job_and_is_never_another_number(oracle_db, tmp_path, schema, query, said):
    result, lines = reading(oracle_db, tmp_path, schema, query)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert said in result.error and "\n" not in result.error
    assert lines is None


def test_values_are_bound_and_names_written_in(oracle_db, wide, tmp_path):
    written = ('"select id, v from " + context.t + " where v = \'" + context.who + "\' and id < " + context.most '
               '+ " and v like \'%" + context.part + "%\'"')
    result, lines = reading(oracle_db, tmp_path, "id:Decimal#0, v:str", written,
                            context={"t": wide, "who": "o'brien", "most": "99999999999999999999", "part": "'br"})
    assert result.status == "success", result.error
    assert lines[1:] == ["12345678901234567890;o'brien"]
    assert result.global_map["in_QUERY"] == (
        f"select id, v from {wide} where v = :context_who and id < 99999999999999999999 and v like '%' || "
        ":context_part || '%'")


def test_a_value_that_would_change_the_query_never_reaches_the_database(oracle_db, wide, tmp_path):
    result, lines = reading(oracle_db, tmp_path, "id:Decimal#0", f"select id from {wide} where id = ${{context.n}}",
                            context={"n": "2 or 1=1"})
    assert (result.status, result.failed_component) == ("failed", "in")
    assert result.error.startswith("what context.n holds is written into the statement")
    # In quotes the same text is a value, and finds no row.
    result, lines = reading(oracle_db, tmp_path, "v:str", f"select v from {wide} where v = '${{context.n}}'",
                            context={"n": "x' or '1'='1"})
    assert result.status == "success" and lines[1:] == []


def test_the_order_of_the_query_is_kept_through_its_own_with_and_a_union(oracle_db, wide, tmp_path):
    query = (f"with picked as (select id from {wide}) select id from picked union all select 99 from dual "
             "order by 1 desc -- newest first")
    result, lines = reading(oracle_db, tmp_path, "id:Decimal#0", query)
    assert result.status == "success", result.error
    assert lines[1:] == ["12345678901234567890", "99", "3", "2"]


def test_a_date_with_a_time_zone_into_a_datetime_fails_with_the_two_ways_to_say_which_clock(oracle_db, wide, tmp_path):
    result, _ = reading(oracle_db, tmp_path, "tz:datetime@%Y-%m-%d %H:%M:%S", f"select tz from {wide}")
    assert result.status == "failed"
    assert result.error == (
        "column 'tz': the query hands back a date with a time zone (TIMESTAMP_TZ), and a datetime has none: say in "
        "the query which clock is meant, `sys_extract_utc(...)` for UTC or `cast(... as timestamp)` for the clock "
        "of the value's own zone")
    for said, clock in (("sys_extract_utc(tz)", "2024-01-31 07:44:15"), ("cast(tz as timestamp)", "2024-01-31 13:14:15")):
        result, lines = reading(oracle_db, tmp_path, "tz:datetime@%Y-%m-%d %H:%M:%S",
                                f"select {said} from {wide} where tz is not null")
        assert result.status == "success" and lines[1:] == [clock]


def test_what_v2_does_not_read_and_what_the_database_does_not_know_are_said_in_one_line(oracle_db, wide, tmp_path):
    result, _ = reading(oracle_db, tmp_path, "r:str", f"select r from {wide}")
    assert result.error == ("column 'r': the query hands back RAW, which v2 does not read: turn it into text, a "
                            "number or a date in the query")
    result, _ = reading(oracle_db, tmp_path, "r:str", f"select rawtohex(r) from {wide} where r is not null")
    assert result.status == "success"
    result, _ = reading(oracle_db, tmp_path, "n:int", "select n from no_such_table_of_v2")
    assert result.error.startswith("ORA-00942:") and "\n" not in result.error and "Help:" not in result.error
    result, _ = reading(oracle_db, tmp_path, "a:int, b:int", "select 1 from dual")
    assert result.error.startswith("the query hands back 1 column(s) and the job declares 2")


def test_text_is_stripped_when_asked_and_an_empty_text_is_missing_as_oracle_has_it(oracle_db, wide, tmp_path):
    result, lines = reading(oracle_db, tmp_path, "v:str, c:str", f"select v, c from {wide} order by id",
                            trim_all_column=True)
    assert lines[1:] == ["pad;", ";", "o'brien;ab"]


def test_many_rows_in_batches_come_in_the_order_they_were_asked_in(oracle_db, tmp_path):
    query = "select level, 'row ' || level from dual connect by level <= 25000 order by level"
    result, lines = reading(oracle_db, tmp_path, "n:int, v:str", query, use_cursor=True, cursor_size=4000)
    assert result.status == "success", result.error
    assert len(lines) == 25001 and lines[1] == "1;row 1" and lines[-1] == "25000;row 25000"
    assert [line.split(";")[0] for line in lines[1:]] == [str(n) for n in range(1, 25001)]


def test_a_reading_on_the_session_of_a_connection_leaves_nothing_waiting(oracle_db, wide, tmp_path):
    out = str(tmp_path / "out.csv")
    components = [
        {"id": "conn", "type": "tOracleConnection", "config": oracle_db.block(), "inputs": [], "outputs": []},
        {"id": "in", "type": "tOracleInput", "inputs": [], "outputs": ["row1"],
         "schema": {"input": [], "output": columns("id:Decimal#0")},
         "config": {"use_existing_connection": True, "connection": "conn", "query": f"select id from {wide} order by id"}},
        writer("id:Decimal#0", path=out, inputs=("row1",)),
        {"id": "x", "type": "tOracleClose", "config": {"connection": "conn"}, "inputs": [], "outputs": []},
    ]
    made = job(components, [flow("row1", "in", "out")], triggers=[
        {"type": "OnSubjobOk", "from": "conn", "to": "in"}, {"type": "OnSubjobOk", "from": "in", "to": "x"}])
    result = run_job(made)
    assert result.status == "success", result.error
    with open(out) as held:
        assert held.read().splitlines()[1:] == ["2", "3", "12345678901234567890"]
    assert decimal.Decimal(result.global_map.get("in_NB_LINE", 3)) == 3


def test_a_value_in_a_text_of_the_national_set(oracle_db, tmp_path):
    query = "select N'${context.s}' a, N'<${context.s}>' b, N'<<${context.s}' c from dual"
    result, lines = reading(oracle_db, tmp_path, "a:str, b:str, c:str", query, context={"s": "bri"})
    assert result.status == "success", result.error
    assert lines[1] == "bri;<bri>;<<bri"
