"""A session with a real SQL Server: what the stand-in driver of the unit tests is a model of."""
import secrets
import time
from decimal import Decimal

import pytest

from src.v2 import mssql, statements
from src.v2.errors import ConfigurationError, DatabaseError
from src.v2.job.keys import normalize_config
from src.v2.job.model import Column
from src.v2.sessions import DATE, NUMBER, OTHER, TEXT, taken

pytestmark = pytest.mark.mssql


def block(mssql_db, **more):
    config, refusals = normalize_config(mssql_db.block(**more), mssql.CONNECTION_KEYS, "test")
    assert not refusals and not mssql.problems(config)
    return config


@pytest.fixture
def session(mssql_db):
    made = mssql.opened(block(mssql_db), "tDBConnection_1")
    yield made
    made.close()


@pytest.fixture
def table(mssql_db):
    """The name of a table of this test's own, ``(n int primary key, s varchar(20))`` with five rows, dropped
    afterwards."""
    name = f"dbo.v2t_{secrets.token_hex(5)}"
    mssql_db.run(f"create table {name} (n int primary key, s varchar(20))",
                 f"insert into {name} values (1, 'a'), (2, 'b'), (3, 'c'), (4, 'd'), (5, 'e')")
    yield name
    mssql_db.run(f"drop table {name}")


def declared(*columns):
    made = []
    for at, column in enumerate(columns, start=1):
        kind, _, places = column.partition("#")
        made.append(Column(name=f"c{at}", type=kind, precision=int(places) if places else None))
    return made


def read(session, query, schema, context=None, size=50000):
    """The rows of a query as a database input takes them: its values bound, its columns as declared."""
    text, values = session.bound(statements.read(query, context or {}, {}, dialect=statements.TSQL))
    columns = declared(*schema)
    fields = session.fields(text, values)
    taken(columns, fields, session.advice)
    statement, kinds = session.typed(text, columns, fields)
    rows = []
    for made in session.batches(statement, values, kinds, size):
        rows += list(zip(*[made.column(at).to_pylist() for at in range(made.num_columns)]))
    return rows


# ------------------------------------------------------------------
# The session
# ------------------------------------------------------------------

def test_a_session_is_opened_and_every_statement_on_it_is_stored_by_itself(mssql_db, session):
    assert session.what == f"{mssql_db.user}@{mssql_db.host},{mssql_db.port}/{mssql_db.name}"
    assert read(session, "select @@trancount, db_name()", ["int", "str"]) == [(0, mssql_db.name)]


def test_the_program_a_session_shows_is_the_drivers_and_no_other_can_be_given(session):
    rows = read(session, "select program_name from sys.dm_exec_sessions where session_id = @@spid", ["str"])
    assert rows == [("MSSQL-Python",)]


def test_a_closed_session_is_gone_from_the_server(mssql_db):
    # Left to itself the driver keeps a closed session for whoever opens the next, for ten minutes.
    watching = mssql_db.connect()

    def sessions_with(spid):
        return watching.cursor().execute("select count(*) from sys.dm_exec_sessions where session_id = ?", [spid]).fetchone()[0]

    try:
        made = mssql.opened(block(mssql_db), "c")
        (spid,), = read(made, "select @@spid", ["int"])
        assert sessions_with(spid) == 1
        made.close()
        # The server takes a session down in a few milliseconds, and shows it until it has.
        until = time.monotonic() + 5
        while sessions_with(spid) and time.monotonic() < until:
            time.sleep(0.05)
        assert sessions_with(spid) == 0
    finally:
        watching.close()


def test_a_wrong_password_is_said_without_the_password(mssql_db):
    with pytest.raises(DatabaseError) as failed:
        mssql.opened(block(mssql_db, password="not-the-Passw0rd"), "c")
    assert str(failed.value) == (f"no session was opened as {mssql_db.user}@{mssql_db.host},{mssql_db.port}/"
                                 f"{mssql_db.name}: Login failed for user '{mssql_db.user}'.")


def test_a_certificate_of_the_servers_own_making_is_not_trusted_unless_the_job_says_so(mssql_db):
    with pytest.raises(DatabaseError) as failed:
        mssql.opened(block(mssql_db, trust_server_certificate=False), "c")
    assert "certificate verify failed" in str(failed.value)
    assert str(failed.value).endswith("what is sent is still encrypted but the server is not checked")
    # What Talend's JDBC parameters say is read the same way.
    made = mssql.opened(block(mssql_db, trust_server_certificate=None, properties="trustServerCertificate=true"), "c")
    made.close()


def test_a_host_nobody_knows_is_said_in_words(mssql_db):
    with pytest.raises(DatabaseError) as failed:
        mssql.opened(block(mssql_db, host="no-such-host.invalid", properties="loginTimeout=3"), "c")
    assert str(failed.value).endswith("TCP Provider: Error code 0x2AF9 (no such host is known)")


# ------------------------------------------------------------------
# What the driver hands each type out as
# ------------------------------------------------------------------

TYPES = [
    ("bigint", NUMBER, "BIGINT"), ("int", NUMBER, "INT"), ("smallint", NUMBER, "SMALLINT"), ("tinyint", NUMBER, "TINYINT"),
    ("bit", NUMBER, "BIT"), ("decimal(38, 10)", NUMBER, "DECIMAL(38,10)"), ("numeric(5, 0)", NUMBER, "DECIMAL(5,0)"),
    ("money", NUMBER, "DECIMAL(19,4)"), ("smallmoney", NUMBER, "DECIMAL(10,4)"), ("float", NUMBER, "FLOAT"),
    ("real", NUMBER, "REAL"), ("date", DATE, "DATE"), ("datetime", DATE, "DATETIME"), ("datetime2(7)", DATE, "DATETIME"),
    ("smalldatetime", DATE, "DATETIME"), ("time(7)", TEXT, "TIME"), ("char(6)", TEXT, "text"), ("varchar(50)", TEXT, "text"),
    ("varchar(max)", TEXT, "text"), ("nchar(6)", TEXT, "text"), ("nvarchar(50)", TEXT, "text"),
    ("nvarchar(max)", TEXT, "text"), ("text", TEXT, "text"), ("ntext", TEXT, "text"), ("xml", TEXT, "text"),
    ("uniqueidentifier", TEXT, "text"), ("sysname", TEXT, "text"),
    ("datetimeoffset(7)", OTHER, "a date with a time zone (DATETIMEOFFSET)"), ("binary(4)", OTHER, "binary data"),
    ("varbinary(20)", OTHER, "binary data"), ("varbinary(max)", OTHER, "binary data"), ("image", OTHER, "binary data"),
    ("rowversion", OTHER, "binary data"), ("hierarchyid", OTHER, "binary data"), ("geography", OTHER, "binary data"),
]


def test_what_kind_each_type_of_sql_servers_is_to_a_job(mssql_db, session):
    name = f"dbo.v2k_{secrets.token_hex(5)}"
    mssql_db.run(f"create table {name} ({', '.join(f'c{at} {kind} null' if kind != 'rowversion' else f'c{at} {kind}' for at, (kind, _, _) in enumerate(TYPES))})")
    try:
        fields = session.fields(f"select * from {name}")
        assert [(field.family, field.said) for field in fields] == [(family, said) for _, family, said in TYPES]
    finally:
        mssql_db.run(f"drop table {name}")


def test_a_sql_variant_stops_the_drivers_way_to_arrow_and_is_said_with_what_to_do(session):
    with pytest.raises(ConfigurationError) as failed:
        session.fields("select cast(1 as sql_variant) v")
    assert str(failed.value).startswith("the driver cannot hand on a column of the query (Unsupported data type")
    assert str(failed.value).endswith("a sql_variant is cast to the type it holds")
    assert read(session, "select 1", ["int"]) == [(1,)]


# ------------------------------------------------------------------
# Each conversion beside SQL Server's own
# ------------------------------------------------------------------

@pytest.fixture
def numbers(mssql_db):
    name = f"dbo.v2n_{secrets.token_hex(5)}"
    mssql_db.run(f"create table {name} (id int identity primary key, d decimal(38, 10), f float, r real, b bigint)")
    values = [
        ("2.675", "2.675", "2.675", "5"), ("-2.675", "-2.675", "-2.675", "-5"), ("2.665", "0.125", "0.125", "0"),
        ("0.125", "-0.125", "-0.125", "9223372036854775807"), ("-0.125", "0.375", "0.375", "-9223372036854775808"),
        ("0.5", "0.5", "0.5", "9007199254740993"), ("1.5", "1.5", "2.5", "1"), ("-0.5", "-2.5", "-0.5", "2"),
        ("1234567.8915", "123456789.123456789", "1234567.891", "3"), ("0.0000000005", "0.1", "0.1", "4"),
        ("99999999999999999.9999999999", "1e15 + 0.3", "16777217", "6"), ("0", "0", "0", "7"),
        ("-0.005", "1e-10", "1e-10", "8"), ("7.7", "7.7", "7.7", "9"), ("-7.7", "-7.7", "-7.7", "10"),
    ]
    for d, f, r, b in values:
        mssql_db.run(f"insert into {name} (d, f, r, b) values ({d}, cast({f} as float), cast({r} as real), {b})")
    mssql_db.run(f"insert into {name} (d, f, r, b) values (null, null, null, null)")
    yield name
    mssql_db.run(f"drop table {name}")


@pytest.mark.parametrize("column, cast, kind", [
    ("d", "decimal(38, 2)", "Decimal#2"), ("d", "decimal(38, 0)", "Decimal#0"), ("d", "bigint", "int"),
    ("d", "float", "float"),
    ("f", "decimal(38, 2)", "Decimal#2"), ("f", "decimal(38, 0)", "Decimal#0"), ("f", "decimal(38, 10)", "Decimal#10"),
    ("f", "decimal(38, 20)", "Decimal#20"), ("f", "bigint", "int"),
    ("r", "decimal(38, 2)", "Decimal#2"), ("r", "decimal(38, 10)", "Decimal#10"), ("r", "bigint", "int"),
    ("r", "float", "float"),
    ("b", "decimal(38, 2)", "Decimal#2"), ("b", "float", "float"),
])
def test_a_number_is_made_what_the_job_declares_as_sql_servers_own_cast_makes_it(session, numbers, column, cast, kind):
    rows = read(session, f"select {column}, cast({column} as {cast}) from {numbers} order by id", [kind, kind])
    assert len(rows) == 16
    assert [mine for mine, _ in rows] == [the_servers for _, the_servers in rows]
    assert rows[-1] == (None, None)


def test_a_decimal_as_a_float_is_the_nearest_float_there_is_as_sql_servers_own_cast_is(session):
    # Arrow's own cast of the first is a step off the nearest float: 9.138185270471748e+20.
    wide = ("913818527047174782727", "12345678901234567890.5", "0.1", "99999999999999999999999999.99")
    query = " union all ".join(f"select {at}, cast({one} as decimal(38, 2)), cast(cast({one} as decimal(38, 2)) as float)"
                               for at, one in enumerate(wide)) + " order by 1"
    rows = read(session, query, ["int", "float", "float"])
    assert [mine for _, mine, _ in rows] == [the_servers for _, _, the_servers in rows]
    assert rows[0][1] == 9.138185270471747e+20


def test_a_number_as_true_or_false_and_as_text(session, numbers):
    rows = read(session, f"select d, f, cast(d as bit), cast(1.50 as decimal(9, 2)), cast(1 as bit), cast(7 as tinyint) "
                         f"from {numbers} where id in (1, 12) order by id", ["bool", "bool", "str", "str", "str", "str"])
    assert rows == [(1, 1, "1", "1.50", "1", "7"), (0, 0, "0", "1.50", "1", "7")]


def test_a_number_too_large_for_what_is_declared_fails_where_sql_servers_own_cast_fails(session, numbers):
    with pytest.raises(DatabaseError) as failed:
        read(session, f"select cast(f * 1e30 as float) from {numbers} order by id", ["int"])
    assert str(failed.value).startswith("row 1 of the result: column 1 holds 2.675e+30, which does not fit a whole number")
    with pytest.raises(DatabaseError, match="Arithmetic overflow"):
        read(session, f"select cast(cast(f * 1e30 as float) as bigint) from {numbers} order by id", ["int"])


def test_dates_and_times_as_declared_and_as_text(session):
    query = ("select cast('2026-10-12' as date), cast('2026-10-12' as date), cast('2026-10-12' as date), "
             "cast('2026-10-12 14:03:05.997' as datetime), cast('2026-10-12 14:03:05.997' as datetime), "
             "cast('2026-10-12 14:03:05.1234567' as datetime2(7)), cast('2026-10-12 14:03:05.1234567' as datetime2(7)), "
             "cast('1969-12-31 23:59:59.9999999' as datetime2(7)), cast('2026-10-12 14:03:05' as datetime2(0)), "
             "cast('2026-10-12 14:03' as smalldatetime), cast('14:03:05.1234567' as time(7)), cast('14:03:05' as time(0)), "
             "cast('2026-10-12 14:03:05.12' as datetime2(2))")
    import datetime
    (row,) = read(session, query, ["date", "datetime", "str", "datetime", "str", "datetime", "str", "date", "str", "str",
                                   "str", "str", "str"])
    assert row == (
        datetime.date(2026, 10, 12), datetime.datetime(2026, 10, 12), "2026-10-12",
        datetime.datetime(2026, 10, 12, 14, 3, 5, 997000), "2026-10-12 14:03:05.997",
        # Cut to the millionth, and not rounded.
        datetime.datetime(2026, 10, 12, 14, 3, 5, 123456), "2026-10-12 14:03:05.123456",
        datetime.date(1969, 12, 31), "2026-10-12 14:03:05", "2026-10-12 14:03:00", "14:03:05.1234567", "14:03:05",
        "2026-10-12 14:03:05.12",
    )


def test_text_arrives_as_the_database_holds_it(session):
    letters = "N'" + "".join(f"' + nchar({ord(one)}) + N'" for one in "\u65e5\u672c") + "'"
    query = (f"select cast('ab' as char(6)), cast('caf' + char(233) as varchar(10)), {letters} + nchar(55357) + nchar(56832), "
             "len(replicate(cast('x' as varchar(max)), 100000)), replicate(cast(N'y' as nvarchar(max)), 70000), "
             "cast('6f9619ff-8b86-d011-b42d-00c04fc964ff' as uniqueidentifier), cast('<a b=\"1\">t</a>' as xml), '', "
             "cast(null as varchar(5))")
    (row,) = read(session, query, ["str", "str", "str", "int", "str", "str", "str", "str", "str"])
    assert row == ("ab    ", "caf\xe9", "\u65e5\u672c\U0001f600", 100000, "y" * 70000,
                   "6F9619FF-8B86-D011-B42D-00C04FC964FF", '<a b="1">t</a>', "", None)


@pytest.mark.parametrize("column, said", [
    ("cast('2026-10-12 14:03:05.1234567 +05:30' as datetimeoffset(7))", "a date with a time zone (DATETIMEOFFSET)"),
    ("0xDEADBEEF", "binary data"),
])
def test_what_is_not_read_says_what_to_write_in_the_query_and_that_works(session, column, said):
    with pytest.raises(ConfigurationError) as failed:
        read(session, f"select {column}", ["str"])
    assert f"the query hands back {said}, which v2 does not read" in str(failed.value)


def test_the_ways_the_failures_name_to_read_such_a_column_do_read_it(session):
    at = "cast('2026-10-12 14:03:05.1234567 +05:30' as datetimeoffset(7))"
    (row,) = read(session, f"select convert(varchar(34), {at}, 121), cast({at} at time zone 'UTC' as datetime2), "
                           f"cast({at} as datetime2), convert(varchar(max), 0xDEADBEEF, 2)", ["str", "str", "str", "str"])
    assert row == ("2026-10-12 14:03:05.1234567 +05:30", "2026-10-12 08:33:05.123456", "2026-10-12 14:03:05.123456",
                   "DEADBEEF")


# ------------------------------------------------------------------
# Values bound, and what a statement hands back
# ------------------------------------------------------------------

def test_a_value_of_plain_ascii_is_bound_as_varchar_and_any_other_as_nvarchar(session):
    query = ("select cast(sql_variant_property('${context.plain}', 'BaseType') as varchar(20)), "
             "cast(sql_variant_property('${context.other}', 'BaseType') as varchar(20)), N'<${context.other}>', "
             "'<' + '${context.plain}' + '>'")
    rows = read(session, query, ["str", "str", "str", "str"], context={"plain": "o'brien", "other": "\u65e5\u672c"})
    assert rows == [("varchar", "nvarchar", "<\u65e5\u672c>", "<o'brien>")]


def test_a_value_bound_against_a_varchar_key_seeks_its_index_as_a_text_in_quotes_does(mssql_db, session):
    name = f"dbo.v2s_{secrets.token_hex(5)}"
    mssql_db.run(f"create table {name} (s varchar(20) collate SQL_Latin1_General_CP1_CI_AS not null primary key, n int)",
                 f"insert into {name} select top 20000 'k' + right('0000000' + cast(row_number() over (order by (select 1)) "
                 "as varchar(8)), 8), 1 from sys.all_columns a cross join sys.all_columns b")
    used = ("select isnull(sum(user_seeks), 0), isnull(sum(user_scans), 0) from sys.dm_db_index_usage_stats "
            f"where database_id = db_id() and object_id = object_id('{name}')")
    try:
        assert read(session, f"select n from {name} where s = '${{context.v}}'", ["int"], context={"v": "k00010000"}) == [(1,)]
        assert mssql_db.rows(used) == [(1, 0)]
        assert read(session, f"select n from {name} where s = '${{context.v}}'", ["int"], context={"v": "k0001000\xe9"}) == []
        assert mssql_db.rows(used) == [(1, 1)]
    finally:
        mssql_db.run(f"drop table {name}")


def test_a_query_is_run_as_it_is_written_and_read_a_few_rows_at_a_time(session, table):
    rows = read(session, f"with x as (select n from {table}) select n, cast(n * 1.5 as decimal(9, 3)) from x order by n desc",
                ["int", "Decimal#1"], size=2)
    assert rows == [(5, Decimal("7.5")), (4, Decimal("6.0")), (3, Decimal("4.5")), (2, Decimal("3.0")), (1, Decimal("1.5"))]


@pytest.fixture
def procedures(mssql_db, table):
    made = f"v2p_{secrets.token_hex(5)}"
    bodies = {
        "rows": f"@from int as begin set nocount on; select n, s from {table} where n >= @from order by n; end",
        "counts": f"as begin update {table} set s = s where n = 1; select n from {table} order by n; end",
        "fails": f"as begin set nocount on; select n from {table} order by n; throw 50001, 'it failed after its rows', 1; end",
        "two": f"as begin set nocount on; select n from {table} where n < 3 order by n; select s from {table} where n > 3; end",
        "prints": f"as begin print 'hello'; select n from {table} where n = 1; end",
    }
    for name, body in bodies.items():
        mssql_db.run(f"create procedure dbo.{made}_{name} {body}")
    yield f"dbo.{made}"
    for name in bodies:
        mssql_db.run(f"drop procedure dbo.{made}_{name}")


def test_a_procedure_is_called_with_a_bound_value(session, procedures):
    assert read(session, f"exec {procedures}_rows '${{context.k}}'", ["int", "str"], context={"k": "4"}) == [(4, "d"), (5, "e")]


def test_what_a_procedure_hands_back_before_its_rows_is_passed_over(session, procedures):
    assert read(session, f"exec {procedures}_counts", ["int"]) == [(1,), (2,), (3,), (4,), (5,)]
    assert read(session, f"exec {procedures}_prints", ["int"]) == [(1,)]


def test_a_failure_after_the_rows_of_a_procedure_fails_the_query(session, procedures):
    with pytest.raises(DatabaseError) as failed:
        read(session, f"exec {procedures}_fails", ["int"])
    assert str(failed.value) == "the query failed after 5 row(s) were read: it failed after its rows"
    assert read(session, "select 1", ["int"]) == [(1,)]


def test_rows_after_the_first_a_procedure_hands_back_are_passed_over_and_said(session, procedures, caplog):
    session.asking = "in"
    with caplog.at_level("INFO", logger="src.v2"):
        assert read(session, f"exec {procedures}_two", ["int"]) == [(1,), (2,)]
    assert "[in] the query handed back 2 results: the first is read and the other is passed over" in caplog.text


def test_a_statement_with_no_rows_to_read_has_been_run_and_fails(session, table):
    with pytest.raises(ConfigurationError, match="was run and handed back no rows to read"):
        read(session, f"update {table} set s = 'z' where n = 5", ["int"])
    assert read(session, f"select s from {table} where n = 5", ["str"]) == [("z",)]


def test_what_the_database_refuses_is_said_in_its_words(session):
    with pytest.raises(DatabaseError, match="^Invalid object name 'dbo.no_such_table'.$"):
        read(session, "select * from dbo.no_such_table", ["int"])


def test_a_failure_that_comes_while_rows_are_read_has_lost_its_reason_in_the_driver(session, table):
    """A fault of the driver's (mssql-python 1.15.0). When this test fails the driver has learned to say it, and
    what v2 says of such a failure can say it too."""
    with pytest.raises(DatabaseError) as failed:
        read(session, f"select n, 10 / (3 - n) from {table} order by n", ["int", "int"], size=2)
    assert str(failed.value) == ("the database ended the query after 2 row(s) were read, and the driver hands on no "
                                 "reason for it: run the query in another client to see what it was")
    assert read(session, "select 1", ["int"]) == [(1,)]


def test_a_query_that_takes_longer_than_it_is_given_fails_and_the_session_goes_on(session):
    session.limit = 1
    with pytest.raises(DatabaseError) as failed:
        read(session, "waitfor delay '00:00:04'; select 1", ["int"])
    assert str(failed.value) == "Query timeout expired: the query was given 1 second(s) (`query_timeout_in_seconds`)"
    session.limit = 0
    assert read(session, "waitfor delay '00:00:02'; select 1", ["int"]) == [(1,)]


def test_a_query_may_say_its_own_isolation_before_its_rows(mssql_db, session, table):
    mssql_db.run(f"alter database {mssql_db.name} set allow_snapshot_isolation on", name="master")
    assert read(session, f"set transaction isolation level snapshot; select count(*) from {table}", ["int"]) == [(5,)]
    # What it set holds for the session: for whoever reads on it afterwards too.
    assert read(session, "select transaction_isolation_level from sys.dm_exec_sessions where session_id = @@spid",
                ["int"]) == [(5,)]
