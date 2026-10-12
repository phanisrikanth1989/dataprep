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
            raise Refused(fails["connect"])
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
