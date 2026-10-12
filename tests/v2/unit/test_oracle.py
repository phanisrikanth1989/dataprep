"""Oracle without a database: what a connection block becomes, what is wrong with one, and what the session
asks of its driver.

The driver here is a stand-in that notes what it is asked and answers as
the real one was seen to answer (python-oracledb 26.0.1 against Oracle
23.26.3, on 2026-10-12). What the real one does is tried in the tests
marked ``oracle``.
"""
import sys
import types

import pytest

from src.v2 import oracle
from src.v2.errors import DatabaseError
from src.v2.job.keys import normalize_config


def block(**given):
    """A connection block as a component hands it on: checked against the declared keys."""
    config, refusals = normalize_config(given, oracle.CONNECTION_KEYS, "component c (tOracleConnection)")
    assert not refusals, [f"{refusal.key}: {refusal.reason}" for refusal in refusals]
    return config


def refused(**given):
    _, refusals = normalize_config(given, oracle.CONNECTION_KEYS, "component c (tOracleConnection)")
    return [f"{refusal.key}: {refusal.reason}" for refusal in refusals]


SERVICE = dict(connection_type="ORACLE_SERVICE_NAME", host="db.example", port="1521", dbname="SALES", user="app",
               password="s3cret")


# ------------------------------------------------------------------
# What the driver is given
# ------------------------------------------------------------------

def test_a_service_name():
    assert oracle.arguments(block(**SERVICE)) == {
        "user": "app", "password": "s3cret", "host": "db.example", "port": 1521, "service_name": "SALES",
    }


def test_a_sid_is_the_type_a_block_has_when_it_names_none():
    given = oracle.arguments(block(host="db.example", dbname="ORCL", user="app", password="x"))
    assert given == {"user": "app", "password": "x", "host": "db.example", "port": 1521, "sid": "ORCL"}


@pytest.mark.parametrize("url, given", [
    ("jdbc:oracle:thin:@//scan.example:1522/SALES", {"dsn": "//scan.example:1522/SALES"}),
    ("jdbc:oracle:thin:@(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=a)(PORT=1521))(CONNECT_DATA=(SERVICE_NAME=S)))",
     {"dsn": "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=a)(PORT=1521))(CONNECT_DATA=(SERVICE_NAME=S)))"}),
    ("JDBC:Oracle:OCI8:@SALES_ALIAS", {"dsn": "SALES_ALIAS"}),
    ("  scan.example:1522/SALES ", {"dsn": "scan.example:1522/SALES"}),
    # Oracle's old way of writing a SID in a JDBC URL, which the driver does not read.
    ("jdbc:oracle:thin:@db.example:1521:ORCL", {"host": "db.example", "port": 1521, "sid": "ORCL"}),
])
def test_a_url_of_its_own_is_handed_on_without_what_makes_it_a_jdbc_url(url, given):
    made = oracle.arguments(block(connection_type="ORACLE_RAC", rac_url=url, user="app", password="x"))
    assert made == {"user": "app", "password": "x", **given}


def test_a_name_of_tnsnames_is_looked_up_in_the_folder_of_the_file_named():
    made = oracle.arguments(block(connection_type="ORACLE_OCI", local_service_name="SALES", user="app", password="x",
                                  use_tns_file=True, tns_file="/etc/oracle/tnsnames.ora"))
    assert made == {"user": "app", "password": "x", "dsn": "SALES", "config_dir": "/etc/oracle"}


def test_a_name_of_tnsnames_with_no_file_named_is_left_to_the_driver_to_find():
    made = oracle.arguments(block(connection_type="ORACLE_OCI", local_service_name="SALES", user="app", password="x",
                                  tns_file="/etc/oracle/tnsnames.ora"))
    assert made == {"user": "app", "password": "x", "dsn": "SALES"}


def test_a_port_may_be_written_as_text_or_as_a_number():
    assert oracle.arguments(block(**{**SERVICE, "port": 1522}))["port"] == 1522
    assert oracle.arguments(block(**{**SERVICE, "port": " 1522 "}))["port"] == 1522


def test_an_empty_port_is_oracles_usual_one():
    assert oracle.arguments(block(**{**SERVICE, "port": ""}))["port"] == 1521


@pytest.mark.parametrize("port", ["fifteen", "0", "70000", "-1", 1.5, True])
def test_a_port_that_is_none_is_refused(port):
    assert refused(**{**SERVICE, "port": port}) == [f"port: {port!r} is no port: give a whole number from 1 to 65535"]


# ------------------------------------------------------------------
# What is wrong with a block
# ------------------------------------------------------------------

def test_a_whole_block_has_no_problem():
    assert oracle.problems(block(**SERVICE)) == []


@pytest.mark.parametrize("left_out, said", [
    ("host", "host: is empty; a session is opened with a host and a service name"),
    ("dbname", "dbname: is empty; a session is opened with a host and a service name"),
    ("user", "user: is empty"),
])
def test_what_a_block_cannot_do_without(left_out, said):
    assert oracle.problems(block(**{**SERVICE, left_out: ""})) == [said]


def test_a_host_of_blanks_is_no_host():
    assert oracle.problems(block(**{**SERVICE, "host": "   "})) == [
        "host: is empty; a session is opened with a host and a service name"
    ]


def test_a_sid_is_asked_for_by_that_name():
    assert oracle.problems(block(host="h", user="app", password="x")) == [
        "dbname: is empty; a session is opened with a host and a SID"
    ]


def test_a_url_and_a_name_of_tnsnames_are_asked_for_where_the_type_needs_them():
    assert oracle.problems(block(connection_type="ORACLE_RAC", user="app", password="x")) == [
        "rac_url: is empty; `connection_type` ORACLE_RAC opens a session with it"
    ]
    assert oracle.problems(block(connection_type="ORACLE_OCI", user="app", password="x")) == [
        "local_service_name: is empty; `connection_type` ORACLE_OCI opens a session with it"
    ]


def test_a_password_talend_encrypted_is_refused_without_being_shown():
    secret = "enc:system.encryption.key.v1:qnMXbrbd5e7MfkpKYf1amObekiqe7olrTRAbfeDX5XuOpxSwczvzMaHQmQ=="
    found = oracle.problems(block(**{**SERVICE, "password": secret}))
    assert found == [
        "password: is text Talend encrypted with a key of its own, which v2 cannot read; give the password "
        "itself, from a context variable (`${context.db_password}`)"
    ]
    assert "qnMX" not in found[0]


@pytest.mark.parametrize("url", [
    "jdbc:oracle:thin:app/s3cret@//db.example:1521/SALES",
    "app/s3cret@db.example:1521/SALES",
    "jdbc:oracle:thin:app/s3cret@(DESCRIPTION=(ADDRESS=(HOST=a)))",
])
def test_a_url_that_carries_a_password_is_refused_without_being_shown(url):
    found = oracle.problems(block(connection_type="ORACLE_RAC", rac_url=url, user="app", password="x"))
    assert found == [
        "rac_url: carries a user and a password; give them in `user` and `password`, and the URL from the `@` on"
    ]
    assert "s3cret" not in found[0]


def test_a_url_with_a_slash_after_the_at_carries_no_password():
    assert oracle.problems(block(connection_type="ORACLE_RAC", rac_url="jdbc:oracle:thin:@//h:1521/S", user="app",
                                 password="x")) == []


def test_a_wallet_that_holds_the_password_is_refused():
    assert oracle.problems(block(connection_type="ORACLE_WALLET", jdbc_url="jdbc:oracle:thin:/@SALES")) == [
        "connection_type: ORACLE_WALLET keeps the user and the password in a wallet only Oracle's own client reads, "
        "and v2 opens no session that way; give `user` and `password` and one of the other types"
    ]


def test_jdbc_parameters_are_refused_by_name():
    found = oracle.problems(block(**{**SERVICE, "properties": "oracle.net.CONNECT_TIMEOUT=5000&&defaultRowPrefetch=50"}))
    assert found == [
        "properties: `oracle.net.CONNECT_TIMEOUT` and `defaultRowPrefetch` are parameters of Oracle's JDBC driver, "
        "which v2 does not use; take them out"
    ]


@pytest.mark.parametrize("key, why", [
    ("use_ssl", "Java key stores are not read; a `rac_url` that says `tcps` opens a session over TLS, with the "
                "server's certificate in the system's store"),
    ("use_shared_connection", "a session is not shared between a job and the jobs it runs: each opens its own"),
])
def test_what_v2_does_not_do_is_refused_when_it_is_switched_on(key, why):
    assert refused(**{**SERVICE, key: True}) == [f"{key}: {why}"]
    assert refused(**{**SERVICE, key: False}) == []


def test_what_talend_writes_and_changes_nothing_here_is_taken():
    assert refused(**SERVICE, db_version="ORACLE_18", encoding="ISO-8859-15", support_nls=False, jdbc_url="x",
                   specify_datasource_alias=False, datasource_alias="", ssl_trustserver_truststore="",
                   need_client_auth=False, ssl_keystore="", disable_cbc_protection=True, shared_connection_name="") == []


def test_the_schema_goes_by_three_names():
    for spelling in ("schema_db", "table_schema", "dbschema"):
        assert block(**{**SERVICE, spelling: "HR"})["schema_db"] == "HR"


# ------------------------------------------------------------------
# The driver: a stand-in that notes what it is asked
# ------------------------------------------------------------------

class Refused(Exception):
    """The driver's own error, as python-oracledb raises one: its message has a second line of help."""


class Held:
    """A connection of the stand-in driver."""

    version, thin = "23.26.3.0.0", True

    def __init__(self, driver):
        self.driver, self.did, self.busy, self.healthy = driver, [], False, True
        self.module = self.action = None

    @property
    def transaction_in_progress(self):
        return self.busy

    def is_healthy(self):
        return self.healthy

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self._do("commit")
        self.busy = False

    def rollback(self):
        self._do("rollback")
        self.busy = False

    def close(self):
        self._do("close")

    def _do(self, what):
        self.did.append(what)
        if what in self.driver.fails:
            raise Refused(self.driver.fails[what])


class Cursor:
    def __init__(self, held):
        self.held, self.rowcount = held, 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.held.did.append("cursor closed")

    def execute(self, statement, binds):
        self.held.did.append((statement, binds))
        if statement in self.held.driver.fails:
            raise Refused(self.held.driver.fails[statement])
        self.held.busy = True
        self.rowcount = 3


def stand_in(version="26.0.1", **fails):
    driver = types.ModuleType("oracledb")
    driver.__version__ = version
    driver.Error = Refused
    driver.fails = fails
    driver.asked, driver.clients, driver.opened = [], [], []

    def connect(**given):
        driver.asked.append(given)
        if "connect" in fails:
            raise fails["connect"] if isinstance(fails["connect"], Exception) else Refused(fails["connect"])
        driver.opened.append(Held(driver))
        return driver.opened[-1]

    def init_oracle_client(**given):
        driver.clients.append(given)
        if "client" in fails:
            raise Refused(fails["client"])

    driver.connect, driver.init_oracle_client = connect, init_oracle_client
    return driver


@pytest.fixture
def driver(monkeypatch):
    made = stand_in()
    monkeypatch.setitem(sys.modules, "oracledb", made)
    return made


def test_a_session_is_opened_with_what_the_block_says_and_tagged_with_the_job(driver, caplog):
    with caplog.at_level("INFO", logger="src.v2"):
        session = oracle.opened(block(**SERVICE, schema_db="HR"), "tDBConnection_1", "nightly_load")
    assert driver.asked == [{"user": "app", "password": "s3cret", "host": "db.example", "port": 1521,
                             "service_name": "SALES"}]
    held = driver.opened[0]
    assert (held.module, held.action) == ("dataprep-v2", "nightly_load")
    assert (session.opened_by, session.schema, session.shared, session.auto_commit) == ("tDBConnection_1", "HR", False, False)
    assert session.what == "app@db.example:1521/SALES"
    assert "[tDBConnection_1] session opened: app@db.example:1521/SALES (Oracle 23.26.3.0.0)" in caplog.text
    assert "s3cret" not in caplog.text


def test_a_long_job_name_is_cut_to_what_the_database_keeps(driver):
    oracle.opened(block(**SERVICE), "c", "j" * 80)
    assert driver.opened[0].action == "j" * 64


def test_a_session_is_named_by_what_it_was_opened_with(driver):
    assert oracle.opened(block(host="h", dbname="ORCL", user="app", password="x"), "c", "j").what == "app@h:1521:ORCL"
    assert oracle.opened(block(connection_type="ORACLE_RAC", rac_url="jdbc:oracle:thin:@//scan:1522/S", user="app",
                               password="x"), "c", "j").what == "app@//scan:1522/S"


def test_a_long_connect_string_is_cut_where_a_session_is_named(driver):
    long = "(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)(HOST=node-one.example)(PORT=1521))(ADDRESS=(PROTOCOL=TCP)(HOST=two)))"
    session = oracle.opened(block(connection_type="ORACLE_RAC", rac_url=long, user="app", password="x"), "c", "j")
    assert session.what == f"app@{long[:80]}..."
    assert driver.asked[0]["dsn"] == long
    exact = "//" + "h" * 78
    assert oracle.opened(block(connection_type="ORACLE_RAC", rac_url=exact, user="app", password="x"), "c", "j").what == f"app@{exact}"


def test_a_session_that_is_not_opened_says_where_and_as_whom_and_never_the_password(monkeypatch):
    monkeypatch.setitem(sys.modules, "oracledb", stand_in(
        connect="ORA-01017: invalid credential or not authorized; logon denied\nHelp: https://docs.oracle.com/error-help/db/ora-01017/"
    ))
    with pytest.raises(DatabaseError) as failed:
        oracle.opened(block(**SERVICE), "c", "j")
    assert str(failed.value) == ("no session was opened as app@db.example:1521/SALES: ORA-01017: invalid credential "
                                 "or not authorized; logon denied")


def test_a_host_that_cannot_be_found_is_said_as_any_other_session_that_was_not_opened(monkeypatch):
    """Found by the review of the group: of a name no one knows, the driver hands on what the system said, and no
    error of its own."""
    import socket
    monkeypatch.setitem(sys.modules, "oracledb", stand_in(
        connect=socket.gaierror(8, "nodename nor servname provided, or not known")))
    with pytest.raises(DatabaseError) as failed:
        oracle.opened(block(**SERVICE), "c", "j")
    assert str(failed.value) == ("no session was opened as app@db.example:1521/SALES: [Errno 8] nodename nor servname "
                                 "provided, or not known")


def test_no_driver_is_said_with_how_to_get_one(monkeypatch):
    monkeypatch.setitem(sys.modules, "oracledb", None)
    with pytest.raises(DatabaseError) as failed:
        oracle.opened(block(**SERVICE), "c", "j")
    assert str(failed.value) == ("python-oracledb is not installed, and an Oracle component needs it: "
                                 "pip install 'dataprep[v2-oracle]'")


@pytest.mark.parametrize("version", ["3.4.2", "4.0.2", "26.0.0"])
def test_a_driver_too_old_to_be_trusted_with_rows_is_refused(monkeypatch, version):
    monkeypatch.setitem(sys.modules, "oracledb", stand_in(version=version))
    with pytest.raises(DatabaseError) as failed:
        oracle.opened(block(**SERVICE), "c", "j")
    assert str(failed.value) == (f"python-oracledb {version} is installed, and 26.0.1 or later is needed: earlier "
                                 "ones hand on wrong numbers and lose dates")


@pytest.mark.parametrize("version", ["26.0.1", "26.1.0", "27.0.0b1"])
def test_a_driver_new_enough_is_taken(monkeypatch, version):
    made = stand_in(version=version)
    monkeypatch.setitem(sys.modules, "oracledb", made)
    oracle.opened(block(**SERVICE), "c", "j")
    assert len(made.opened) == 1


def test_oracles_own_client_is_loaded_when_the_job_asks_for_it(driver, caplog):
    with caplog.at_level("INFO", logger="src.v2"):
        oracle.opened(block(**SERVICE), "c", "j", {"thick_mode": True, "lib_dir": "/opt/oracle/instantclient"})
        driver.opened[0].thin = False
    assert driver.clients == [{"lib_dir": "/opt/oracle/instantclient"}]
    oracle.opened(block(**SERVICE), "c", "j", {"thick_mode": True, "lib_dir": None})
    assert driver.clients[1] == {}
    oracle.opened(block(**SERVICE), "c", "j", {"thick_mode": False})
    oracle.opened(block(**SERVICE), "c", "j", None)
    assert len(driver.clients) == 2


def test_a_session_says_when_it_is_one_of_oracles_own_client(monkeypatch, caplog):
    made = stand_in()
    monkeypatch.setitem(sys.modules, "oracledb", made)
    monkeypatch.setattr(Held, "thin", False)
    with caplog.at_level("INFO", logger="src.v2"):
        oracle.opened(block(**SERVICE), "c", "j", {"thick_mode": True})
    assert "(Oracle 23.26.3.0.0, with Oracle's own client)" in caplog.text


def test_a_client_that_cannot_be_loaded_is_said(monkeypatch):
    monkeypatch.setitem(sys.modules, "oracledb", stand_in(
        client='DPI-1047: Cannot locate a 64-bit Oracle Client library: "dlopen(libclntsh.dylib): image not found"'
    ))
    with pytest.raises(DatabaseError) as failed:
        oracle.opened(block(**SERVICE), "c", "j", {"thick_mode": True})
    assert str(failed.value).startswith("Oracle's own client, which `oracle_config.thick_mode` asks for, could not "
                                        "be loaded: DPI-1047: Cannot locate a 64-bit Oracle Client library")


# ------------------------------------------------------------------
# What a session asks of its driver
# ------------------------------------------------------------------

@pytest.fixture
def session(driver):
    return oracle.opened(block(**SERVICE), "c", "j")


def test_a_statement_is_run_with_its_values_bound_and_its_cursor_closed(driver, session):
    assert session.run("delete from t where d = :context_d", {"context_d": "2024-01-31"}) == 3
    assert driver.opened[0].did == [("delete from t where d = :context_d", {"context_d": "2024-01-31"}), "cursor closed"]
    assert session.run("truncate table t") == 3
    assert driver.opened[0].did[2] == ("truncate table t", {})


def test_what_the_database_refuses_is_said_on_one_line_without_the_link_to_its_help(monkeypatch):
    made = stand_in(**{"select 1": 'ORA-00942: table or view "V2TEST"."NO_SUCH_TABLE" does not exist\n'
                                   "Help: https://docs.oracle.com/error-help/db/ora-00942/"})
    monkeypatch.setitem(sys.modules, "oracledb", made)
    session = oracle.opened(block(**SERVICE), "c", "j")
    with pytest.raises(DatabaseError) as failed:
        session.run("select 1")
    assert str(failed.value) == 'ORA-00942: table or view "V2TEST"."NO_SUCH_TABLE" does not exist'
    assert made.opened[0].did[-1] == "cursor closed"


def test_the_words_of_a_failure_are_one_line_of_ascii():
    assert oracle.said(Refused("ORA-12899: value too large\n  for column \"A\"\u00a0(actual: 7)\nHelp: https://x")) == (
        'ORA-12899: value too large for column "A"\\xa0(actual: 7)'
    )
    assert oracle.said(Refused("")) == "Refused"


def test_a_transaction_is_ended_and_a_place_marked_as_the_engine_asks(driver, session):
    held = driver.opened[0]
    session.savepoint("v2_subjob")
    session.rollback_to("v2_subjob")
    session.commit()
    session.rollback()
    session.close()
    assert [did for did in held.did if did != "cursor closed"] == [
        ("savepoint v2_subjob", {}), ("rollback to savepoint v2_subjob", {}), "commit", "rollback", "close",
    ]


def test_whether_work_waits_and_whether_the_session_lives_are_asked_of_the_driver(driver, session):
    held = driver.opened[0]
    assert (session.in_transaction(), session.alive()) == (False, True)
    session.run("insert into t values (1)")
    assert session.in_transaction() is True
    held.healthy = False
    assert session.alive() is False


@pytest.mark.parametrize("what", ["commit", "rollback", "close"])
def test_an_end_the_database_refuses_is_said_in_its_words(monkeypatch, what):
    made = stand_in(**{what: "DPY-1001: not connected to database"})
    monkeypatch.setitem(sys.modules, "oracledb", made)
    session = oracle.opened(block(**SERVICE), "c", "j")
    with pytest.raises(DatabaseError) as failed:
        getattr(session, what)()
    assert str(failed.value) == "DPY-1001: not connected to database"


# ------------------------------------------------------------------
# Reading: the query that has Oracle convert each column
# ------------------------------------------------------------------

import pyarrow  # noqa: E402

from src.v2 import statements  # noqa: E402
from src.v2.job.model import Column  # noqa: E402
from src.v2.sessions import DATE, NUMBER, OTHER, TEXT, ZONED, Field  # noqa: E402


def read_as(kind, family, said="NUMBER", **column):
    text, types = oracle.reading("select x from t", [Column("c", kind, **column)], [Field("X", family, said)])
    start, end = 'with v2q ("C1") as (\nselect x from t\n) select ', ' "C1" from v2q'
    assert text.startswith(start) and text.endswith(end)
    return text[len(start):-len(end)], types[0]


@pytest.mark.parametrize("kind, family, said, made, asked", [
    ("int", NUMBER, "NUMBER", 'trunc("C1")', pyarrow.int64()),
    ("float", NUMBER, "NUMBER", 'cast("C1" as binary_double)', pyarrow.float64()),
    ("bool", NUMBER, "NUMBER", 'case when "C1" is null then null when "C1" = 0 then 0 else 1 end', pyarrow.int8()),
    ("str", NUMBER, "NUMBER",
     """regexp_replace(to_char("C1", 'TM9', 'nls_numeric_characters=''.,'''), '^(-?)[.]', '\\10.')""", pyarrow.large_string()),
    ("datetime", DATE, "DATE", 'cast("C1" as timestamp(6))', pyarrow.timestamp("us")),
    ("date", DATE, "TIMESTAMP", 'trunc(cast("C1" as date))', pyarrow.date32()),
    ("str", DATE, "DATE", """to_char("C1", 'YYYY-MM-DD HH24:MI:SS')""", pyarrow.large_string()),
    ("str", DATE, "TIMESTAMP", """to_char(cast("C1" as timestamp(6)), 'YYYY-MM-DD HH24:MI:SS.FF6')""", pyarrow.large_string()),
    ("str", ZONED, "TIMESTAMP_TZ", """to_char("C1", 'YYYY-MM-DD HH24:MI:SS.FF6 TZH:TZM')""", pyarrow.large_string()),
    ("str", TEXT, "VARCHAR", '"C1"', pyarrow.large_string()),
    # Text is handed on as text whatever the job declares: the engine reads it.
    ("int", TEXT, "VARCHAR", '"C1"', pyarrow.large_string()),
    ("datetime", TEXT, "CLOB", '"C1"', pyarrow.large_string()),
])
def test_each_column_is_converted_by_the_database_to_what_the_job_declares(kind, family, said, made, asked):
    assert read_as(kind, family, said) == (made, asked)


def test_a_decimal_is_rounded_by_the_database_to_its_declared_places():
    assert read_as("Decimal", NUMBER, precision=2) == ('cast("C1" as number(38, 2))', pyarrow.decimal128(38, 2))
    assert read_as("Decimal", NUMBER, precision=0) == ('cast("C1" as number(38, 0))', pyarrow.decimal128(38, 0))
    assert read_as("Decimal", NUMBER) == ('cast("C1" as number(38, 10))', pyarrow.decimal128(38, 10))


def test_the_query_stands_as_it_is_written_inside_the_one_that_converts():
    columns, fields = [Column("a", "int"), Column("b", "str")], [Field("ID", NUMBER, "NUMBER"), Field("ID", TEXT, "VARCHAR")]
    written = "with a as (select 1 id from dual)\nselect /*+ full(a) */ id, 'x' id from a where id = :context_n order by 1 -- done"
    text, types = oracle.reading(written + " ;\n ", columns, fields)
    assert text == ('with v2q ("C1", "C2") as (\n' + written + ' \n) select trunc("C1") "C1", "C2" "C2" from v2q')
    assert types == [pyarrow.int64(), pyarrow.large_string()]


class Described:
    def __init__(self, name, type_name):
        self.name, self.type_code = name, types.SimpleNamespace(name=type_name)


def reading_driver(monkeypatch, described=(), tables=(), fails=None):
    """A stand-in whose cursor says what a query's columns are and whose connection hands batches back."""
    made = stand_in()

    def parse(self, statement):
        self.held.did.append(("parse", statement))
        if fails:
            raise Refused(fails)
        self.description = list(described) or None

    def fetch_df_batches(self, statement, parameters=None, size=None, requested_schema=None):
        self.did.append(("fetch", statement, parameters, size, requested_schema))
        yield from tables

    monkeypatch.setattr(Cursor, "parse", parse, raising=False)
    monkeypatch.setattr(Held, "fetch_df_batches", fetch_df_batches, raising=False)
    monkeypatch.setitem(sys.modules, "oracledb", made)
    return made


def test_what_a_query_hands_back_is_asked_without_running_it(monkeypatch):
    described = [Described("ID", "DB_TYPE_NUMBER"), Described("F", "DB_TYPE_BINARY_DOUBLE"), Described("V", "DB_TYPE_VARCHAR"),
                 Described("C", "DB_TYPE_CHAR"), Described("N", "DB_TYPE_NVARCHAR"), Described("BIG", "DB_TYPE_CLOB"),
                 Described("D", "DB_TYPE_DATE"), Described("TS", "DB_TYPE_TIMESTAMP"), Described("TZ", "DB_TYPE_TIMESTAMP_TZ"),
                 Described("L", "DB_TYPE_TIMESTAMP_LTZ"), Described("R", "DB_TYPE_RAW"), Described("OLD", "DB_TYPE_LONG"),
                 Described("X", "DB_TYPE_XMLTYPE")]
    driver = reading_driver(monkeypatch, described)
    session = oracle.opened(block(**SERVICE), "c", "j")
    found = session.fields("select * from t where d = :context_d", {"context_d": "2024"})
    assert [(field.name, field.family, field.said) for field in found] == [
        ("ID", NUMBER, "NUMBER"), ("F", NUMBER, "BINARY_DOUBLE"), ("V", TEXT, "VARCHAR"), ("C", TEXT, "CHAR"),
        ("N", TEXT, "NVARCHAR"), ("BIG", TEXT, "CLOB"), ("D", DATE, "DATE"), ("TS", DATE, "TIMESTAMP"),
        ("TZ", ZONED, "TIMESTAMP_TZ"), ("L", ZONED, "TIMESTAMP_LTZ"), ("R", OTHER, "RAW"), ("OLD", OTHER, "LONG"),
        ("X", OTHER, "XMLTYPE")]
    assert driver.opened[0].did == [("parse", "select * from t where d = :context_d"), "cursor closed"]


def test_a_statement_that_hands_nothing_back_has_no_columns(monkeypatch):
    reading_driver(monkeypatch)
    assert oracle.opened(block(**SERVICE), "c", "j").fields("delete from t") == []


def test_a_query_the_database_cannot_read_is_said_in_its_words(monkeypatch):
    reading_driver(monkeypatch, fails='ORA-00942: table or view "A"."T" does not exist\nHelp: https://x')
    with pytest.raises(DatabaseError) as failed:
        oracle.opened(block(**SERVICE), "c", "j").fields("select * from t")
    assert str(failed.value) == 'ORA-00942: table or view "A"."T" does not exist'


def test_rows_are_fetched_in_batches_of_the_types_asked_for_with_the_values_bound(monkeypatch):
    first = pyarrow.table({"C1": pyarrow.array([1, 2], pyarrow.int64()), "C2": pyarrow.array(["a", None], pyarrow.large_string())})
    second = pyarrow.table({"C1": pyarrow.array([3], pyarrow.int64()), "C2": pyarrow.array(["c"], pyarrow.large_string())})
    driver = reading_driver(monkeypatch, tables=[first, second])
    session = oracle.opened(block(**SERVICE), "c", "j")
    asked = [pyarrow.int64(), pyarrow.large_string()]
    got = list(session.batches("select 1", {"context_d": "x"}, asked, 500))
    assert [table.to_pylist() for table in got] == [first.to_pylist(), second.to_pylist()]
    (_, statement, parameters, size, schema), = driver.opened[0].did
    assert (statement, parameters, size) == ("select 1", {"context_d": "x"}, 500)
    assert schema == pyarrow.schema([pyarrow.field("C1", pyarrow.int64()), pyarrow.field("C2", pyarrow.large_string())])
    assert list(session.batches("select 1", None, asked, 5)) and driver.opened[0].did[-1][2] == {}


def test_a_fetch_the_database_refuses_is_said_in_its_words(monkeypatch):
    reading_driver(monkeypatch)

    def refuses(self, statement, **given):
        raise Refused("ORA-01438: value 1234.57 greater than specified precision (38, 35) for column\nHelp: https://x")
        yield  # pragma: no cover

    monkeypatch.setattr(Held, "fetch_df_batches", refuses)
    with pytest.raises(DatabaseError) as failed:
        list(oracle.opened(block(**SERVICE), "c", "j").batches("select 1", {}, [pyarrow.int64()], 5))
    assert str(failed.value) == "ORA-01438: value 1234.57 greater than specified precision (38, 35) for column"


def test_oracle_is_handed_a_statement_with_its_values_by_name(driver):
    made = statements.read("select * from t where d = '${context.d}'", {"d": "2024"}, {})
    assert oracle.opened(block(**SERVICE), "c", "j").bound(made) == ("select * from t where d = :context_d", {"context_d": "2024"})


def test_a_session_converts_as_the_function_of_that_name_does(driver):
    columns, fields = [Column("a", "int")], [Field("A", NUMBER, "NUMBER")]
    assert oracle.opened(block(**SERVICE), "c", "j").typed("select a from t", columns, fields) == oracle.reading(
        "select a from t", columns, fields)
    assert oracle.OracleSession.advice[ZONED].startswith("say in the query which clock is meant, `sys_extract_utc(...)`")


def test_what_is_wrong_with_the_block_of_a_component_that_works_on_a_connections_session_is_nothing():
    keys = oracle.CONNECTION_KEYS + oracle.WORKING_KEYS
    own, _ = normalize_config({"use_existing_connection": False}, keys, "c")
    shared, _ = normalize_config({"use_existing_connection": True, "connection": "tDBConnection_1"}, keys, "c")
    assert oracle.working_problems(own) == oracle.problems(own) != []
    assert oracle.working_problems(shared) == []


# ------------------------------------------------------------------
# Storing: a statement for each row of a batch
# ------------------------------------------------------------------

class Refusal:
    def __init__(self, offset, message):
        self.offset, self.message = offset, message


def test_a_batch_is_sent_in_one_round_trip_and_what_is_refused_comes_back_with_its_place(monkeypatch):
    made = stand_in()
    sent = []

    def executemany(self, statement, rows, batcherrors=False, arraydmlrowcounts=False):
        sent.append((statement, rows, batcherrors, arraydmlrowcounts))

    monkeypatch.setattr(Cursor, "executemany", executemany, raising=False)
    monkeypatch.setattr(Cursor, "getbatcherrors", lambda self: [
        Refusal(3, 'ORA-12899: value too large for column "A"."T"."V" (actual: 7, maximum: 5)\nHelp: https://x'),
        Refusal(1, "ORA-00001: unique constraint (A.PK) violated")], raising=False)
    monkeypatch.setattr(Cursor, "getarraydmlrowcounts", lambda self: [1, 0, 2, 0], raising=False)
    monkeypatch.setitem(sys.modules, "oracledb", made)
    session = oracle.opened(block(**SERVICE), "c", "j")
    rows = pyarrow.table({"a": [1, 2, 3, 4]})
    refused, changed = session.many("update t set a = :1", rows, counts=True)
    # In the order of the rows, whatever order the database tells them in.
    assert refused == [(1, "ORA-00001: unique constraint (A.PK) violated"),
                       (3, 'ORA-12899: value too large for column "A"."T"."V" (actual: 7, maximum: 5)')]
    assert changed == [1, 0, 2, 0]
    assert sent == [("update t set a = :1", rows, True, True)]
    refused, changed = session.many("insert into t values (:1)", rows)
    assert changed == [] and sent[-1][2:] == (True, False)
    assert made.opened[0].did.count("cursor closed") == 2


def test_a_batch_the_database_cannot_take_at_all_is_said_in_its_words(monkeypatch):
    made = stand_in()

    def executemany(self, statement, rows, **more):
        raise Refused('ORA-00942: table or view "A"."T" does not exist\nHelp: https://x')

    monkeypatch.setattr(Cursor, "executemany", executemany, raising=False)
    monkeypatch.setitem(sys.modules, "oracledb", made)
    with pytest.raises(DatabaseError) as failed:
        oracle.opened(block(**SERVICE), "c", "j").many("insert into t values (:1)", pyarrow.table({"a": [1]}))
    assert str(failed.value) == 'ORA-00942: table or view "A"."T" does not exist'


def test_a_table_that_is_not_there_and_a_name_that_is_taken_are_told_by_oracles_numbers(driver):
    session = oracle.opened(block(**SERVICE), "c", "j")
    missing = DatabaseError('ORA-00942: table or view "A"."T" does not exist')
    taken = DatabaseError("ORA-00955: name is already used by an existing object")
    assert (session.is_missing(missing), session.is_missing(taken)) == (True, False)
    assert (session.is_there_already(taken), session.is_there_already(missing)) == (True, False)


# ------------------------------------------------------------------
# Calling a procedure for many rows
# ------------------------------------------------------------------

class Var:
    def __init__(self, values):
        self.values = values

    def getvalue(self, at):
        return self.values[at]


def calling(monkeypatch, out=None, fails=None):
    made = stand_in()
    made.DB_TYPE_DATE, made.DB_TYPE_TIMESTAMP, made.DB_TYPE_CLOB = "a date", "a timestamp", "a clob"
    seen = {}

    def setinputsizes(self, *sizes):
        seen["sizes"] = sizes

    def executemany(self, block, rows, **more):
        seen["sent"] = (block, rows)
        if fails:
            raise fails
        self.bindvars = [Var(values) for values in (out or [])]

    monkeypatch.setattr(Cursor, "setinputsizes", setinputsizes, raising=False)
    monkeypatch.setattr(Cursor, "executemany", executemany, raising=False)
    monkeypatch.setitem(sys.modules, "oracledb", made)
    return made, seen


def test_a_procedure_is_called_for_each_row_and_what_comes_out_is_read_by_place(monkeypatch):
    import decimal
    made, seen = calling(monkeypatch, out=[[1, 2], ["a", "b"], [decimal.Decimal("2.01"), None], ["x", "y"], [None, None],
                                           [None, None], ["big", "bigger"]])
    session = oracle.opened(block(**SERVICE), "c", "j")
    rows = [(1, "a", None, "x", None, None, None), (2, "b", None, "y", None, None, None)]
    outs = {2: "number", 3: "text", 4: "date", 5: "datetime", 6: "large text"}
    got = session.call("begin p(:1, :2, :3, :4, :5, :6, :7); end;", rows, outs)
    assert got == {2: [decimal.Decimal("2.01"), None], 3: ["x", "y"], 4: [None, None], 5: [None, None], 6: ["big", "bigger"]}
    # A number is asked for with every digit, text with all the room PL/SQL has, and nothing is said of what only goes in.
    assert seen["sizes"] == (None, None, decimal.Decimal, 32767, "a date", "a timestamp", "a clob")
    assert seen["sent"] == ("begin p(:1, :2, :3, :4, :5, :6, :7); end;", rows)
    assert made.opened[0].did[-1] == "cursor closed"


def test_a_procedure_with_no_value_is_called_as_many_times_as_there_are_rows(monkeypatch):
    made, seen = calling(monkeypatch)
    session = oracle.opened(block(**SERVICE), "c", "j")
    assert session.call("begin p; end;", [(), (), ()], {}) == {}
    assert seen == {"sent": ("begin p; end;", 3)}


def test_a_call_that_fails_says_which_one_in_the_databases_words(monkeypatch):
    from src.v2.sessions import CallFailed
    fault = Refused("ORA-20001: thirteen is not taken\nORA-06512: at \"A.P\", line 3\nHelp: https://x")
    fault.args = (types.SimpleNamespace(offset=1),)
    monkeypatch.setattr(Refused, "__str__", lambda self: "ORA-20001: thirteen is not taken\nORA-06512: at \"A.P\", line 3\nHelp: https://x")
    calling(monkeypatch, fails=fault)
    session = oracle.opened(block(**SERVICE), "c", "j")
    with pytest.raises(CallFailed) as failed:
        session.call("begin p(:1); end;", [(1,), (13,)], {})
    assert failed.value.at == 1
    assert str(failed.value) == 'ORA-20001: thirteen is not taken ORA-06512: at "A.P", line 3'


# ------------------------------------------------------------------
# For each row: what is no insert, update, delete or merge, and an insert that reads as it writes
# ------------------------------------------------------------------

class Told:
    """What the driver's error holds, as the real one does: its number, a place, and its words when it is printed."""

    def __init__(self, message, offset):
        self.message, self.offset, self.full_code = message, offset, message.split(":")[0]

    def __str__(self):
        return self.message


def failing(message, offset):
    fault = Refused(message)
    fault.args = (Told(message, offset),)
    return fault


# What the driver says, before it sends anything, of a block or a query handed over with the two switches that only a
# statement which changes rows takes.
NOT_FOR_MANY = ('DPY-2040: parameters "batcherrors" and "arraydmlrowcounts" may only be true when used with insert, '
                "update, delete and merge statements")
# What Oracle says of a block that cannot be compiled. The place the driver gives with it is one in the block's text.
NOT_COMPILED = "ORA-06550: line 1, column 7: PLS-00201: identifier 'P' must be declared"


class Batching:
    """A cursor of the stand-in driver that takes a statement for many rows as the real one was seen to.

    Args:
        kind: ``changes`` for an insert, update, delete or merge; ``block`` for PL/SQL; ``query``.
        fails: The rows the statement fails for, by their place in everything that is sent.
        whole: What is wrong with the statement itself: it is said when a query is parsed, and when a block is run.
    """

    def __init__(self, held, kind, fails=(), whole=None):
        self.held, self.kind, self.fails, self.whole, self.description = held, kind, set(fails), whole, None
        self.refused, self.counts = [], []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.held.did.append("cursor closed")

    def parse(self, statement):
        self.held.did.append(("parse", statement))
        if self.whole and self.kind == "query":
            raise self.whole
        self.description = [types.SimpleNamespace(name="C")] if self.kind == "query" else None

    def executemany(self, statement, rows, batcherrors=False, arraydmlrowcounts=False):
        if (batcherrors or arraydmlrowcounts) and self.kind != "changes":
            raise failing(NOT_FOR_MANY, 0)
        if self.kind == "query":
            raise AssertionError("a query sent for many rows loses the session")
        size = rows if isinstance(rows, int) else rows.num_rows
        self.held.did.append(("many", statement, rows if isinstance(rows, int) else rows.column(0).to_pylist(),
                              batcherrors, arraydmlrowcounts))
        if self.whole:
            raise self.whole
        sent = getattr(self.held, "sent", 0)
        wrong = [at for at in range(size) if sent + at in self.fails]
        if wrong and self.kind == "block":
            # The real one stops at the first that fails, and says which it was.
            self.held.sent = sent + wrong[0] + 1
            raise failing('ORA-20001: no\nORA-06512: at "A.P", line 3\nORA-06512: at line 1', wrong[0])
        self.held.sent = sent + size
        self.refused = [Refusal(at, "ORA-00001: unique constraint (A.PK) violated") for at in wrong]
        self.counts = [0 if at in wrong else 1 for at in range(size)]

    def execute(self, statement, binds=None):
        at = getattr(self.held, "sent", 0)
        self.held.sent = at + 1
        self.held.did.append(("execute", statement, binds))
        if at in self.fails:
            raise failing("ORA-01722: invalid number", 0)

    def getbatcherrors(self):
        return self.refused

    def getarraydmlrowcounts(self):
        return self.counts


def batching(monkeypatch, kind, **more):
    made = stand_in()
    monkeypatch.setitem(sys.modules, "oracledb", made)
    session = oracle.opened(block(**SERVICE), "c", "j")
    held = made.opened[0]
    monkeypatch.setattr(Held, "cursor", lambda self: Batching(self, kind, **more))
    return session, held


def sendings(held):
    return [did[2] for did in held.did if did[0] == "many"]


def test_a_block_for_each_row_is_sent_without_the_switches_of_a_batch_and_a_row_that_fails_stops_no_other(monkeypatch):
    session, held = batching(monkeypatch, "block", fails=(1, 3))
    rows = pyarrow.table({"a": [10, 11, 12, 13, 14]})
    refused, changed = session.many("begin p(:1); end;", rows, counts=True)
    said_so = 'ORA-20001: no ORA-06512: at "A.P", line 3 ORA-06512: at line 1'
    assert refused == [(1, said_so), (3, said_so)]
    # What a block changed cannot be counted.
    assert changed == [0, 0, 0, 0, 0]
    # Sent whole; then from the row after each one that failed.
    assert sendings(held) == [[10, 11, 12, 13, 14], [12, 13, 14], [14]]
    assert [did[3:] for did in held.did if did[0] == "many"] == [(False, False)] * 3
    assert held.did[-1] == "cursor closed"


def test_a_block_whose_last_row_fails_is_not_sent_again_for_no_row(monkeypatch):
    session, held = batching(monkeypatch, "block", fails=(2,))
    refused, changed = session.many("begin p(:1); end;", pyarrow.table({"a": [10, 11, 12]}))
    assert [at for at, _ in refused] == [2] and changed == []
    assert sendings(held) == [[10, 11, 12]]


def test_a_block_that_cannot_be_compiled_is_at_fault_as_a_whole_and_for_no_row(monkeypatch):
    """The place the driver gives for such a fault is one in the text of the block (column 7), and no row."""
    session, held = batching(monkeypatch, "block", whole=failing(NOT_COMPILED, 6))
    with pytest.raises(DatabaseError) as failed:
        session.many("begin p(:1); end;", pyarrow.table({"a": list(range(40))}))
    assert str(failed.value) == NOT_COMPILED
    assert len(sendings(held)) == 1


def test_what_cannot_be_compiled_inside_a_block_while_it_runs_is_the_fault_of_the_row_it_ran_for(monkeypatch):
    # Text a block puts together from its row and runs: it has the lines of where it was raised.
    inside = failing(NOT_COMPILED + "\nORA-06512: at line 1", 1)
    session, held = batching(monkeypatch, "block", whole=inside)
    refused, _ = session.many("begin execute immediate :1; end;", pyarrow.table({"a": ["x", "y", "z"]}))
    assert refused[0] == (1, NOT_COMPILED + " ORA-06512: at line 1")


def test_a_query_for_each_row_is_run_row_by_row_since_the_driver_loses_the_session_over_one_sent_for_many(monkeypatch):
    session, held = batching(monkeypatch, "query", fails=(1,))
    rows = pyarrow.table({"a": [10, 11, 12], "b": ["x", "y", "z"]})
    refused, changed = session.many("select f(:1, :2) from dual", rows, counts=True)
    assert refused == [(1, "ORA-01722: invalid number")] and changed == [0, 0, 0]
    assert [did[2] for did in held.did if did[0] == "execute"] == [[10, "x"], [11, "y"], [12, "z"]]
    assert not sendings(held)


def test_a_query_that_cannot_be_read_is_at_fault_as_a_whole_and_is_run_for_no_row(monkeypatch):
    session, held = batching(monkeypatch, "query", whole=failing('ORA-00904: "NOPE": invalid identifier', 7))
    with pytest.raises(DatabaseError, match='^ORA-00904: "NOPE": invalid identifier$'):
        session.many("select nope from dual where 1 = :1", pyarrow.table({"a": [1, 2]}))
    assert not [did for did in held.did if did[0] == "execute"]


def test_a_statement_that_takes_no_value_is_sent_for_as_many_times_as_there_are_rows(monkeypatch):
    session, held = batching(monkeypatch, "changes")
    refused, changed = session.many("insert into log values (sysdate)", 3, counts=True)
    assert (refused, changed) == ([], [1, 1, 1])
    assert held.did[0] == ("many", "insert into log values (sysdate)", 3, True, True)
    session, held = batching(monkeypatch, "block", fails=(0,))
    refused, _ = session.many("begin p; end;", 3)
    assert [at for at, _ in refused] == [0]
    assert sendings(held) == [3, 2]
    session, held = batching(monkeypatch, "query")
    assert session.many("select f from dual", 2) == ([], [])
    assert [did[1:] for did in held.did if did[0] == "execute"] == [("select f from dual", None)] * 2
    session, held = batching(monkeypatch, "block")
    assert session.many("begin p; end;", 2, counts=True) == ([], [0, 0])


def test_an_insert_of_values_that_reads_as_it_writes_is_sent_one_row_at_a_time(monkeypatch):
    """Sent for many rows at once, Oracle works out the query of every row from the table as it was before the first:
    three rows of `max(n) + 1` get one number."""
    statement = "insert into t (n, v) values ((select nvl(max(n), 0) + 1 from t), :1)"
    session, held = batching(monkeypatch, "changes", fails=(1,))
    refused, changed = session.many(statement, pyarrow.table({"a": ["x", "y", "z"]}), counts=True)
    assert sendings(held) == [["x"], ["y"], ["z"]]
    assert refused == [(1, "ORA-00001: unique constraint (A.PK) violated")] and changed == [1, 0, 1]
    assert [did[3:] for did in held.did if did[0] == "many"] == [(True, True)] * 3
    # With no value of the row in it, too; and an insert that only writes goes for all its rows at once.
    session, held = batching(monkeypatch, "changes")
    assert session.many("INSERT INTO t\nVALUES ((SELECT count(*) FROM t))", 2, counts=True) == ([], [1, 1])
    assert sendings(held) == [1, 1]
    session, held = batching(monkeypatch, "changes")
    session.many("insert into t (n) values (:1)", pyarrow.table({"a": [1, 2, 3]}))
    assert sendings(held) == [[1, 2, 3]]


def test_a_batch_of_no_rows_is_not_sent(monkeypatch):
    session, held = batching(monkeypatch, "changes")
    assert session.many("insert into t (n) values (:1)", pyarrow.table({"a": pyarrow.array([], pyarrow.int64())}), counts=True) == ([], [])
    assert not sendings(held)


@pytest.mark.parametrize("said_so", [
    NOT_COMPILED, "ORA-06576: not a valid function or procedure name",
    "ORA-06553: PLS-306: wrong number or types of arguments in call to 'P'",
])
def test_a_call_that_cannot_be_compiled_is_at_fault_as_a_whole_and_names_no_one_call(monkeypatch, said_so):
    """The place the driver gives for such a fault is one in the text of the call (column 7), and no row."""
    from src.v2.sessions import CallFailed
    calling(monkeypatch, fails=failing(said_so, 6))
    session = oracle.opened(block(**SERVICE), "c", "j")
    with pytest.raises(DatabaseError) as failed:
        session.call("begin p(:1); end;", [(at,) for at in range(40)], {})
    assert not isinstance(failed.value, CallFailed)
    assert str(failed.value) == said_so


def test_what_cannot_be_compiled_inside_a_procedure_while_it_runs_is_the_fault_of_its_call(monkeypatch):
    from src.v2.sessions import CallFailed
    calling(monkeypatch, fails=failing(NOT_COMPILED + '\nORA-06512: at "A.P", line 3', 5))
    session = oracle.opened(block(**SERVICE), "c", "j")
    with pytest.raises(CallFailed) as failed:
        session.call("begin p(:1); end;", [(at,) for at in range(40)], {})
    assert failed.value.at == 5
