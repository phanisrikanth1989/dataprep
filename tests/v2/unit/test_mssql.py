"""SQL Server without a database: what a connection block becomes, what is wrong with one, what the session asks
of its driver, and how it hands a value on as the job declares it.

The driver here is a stand-in that notes what it is asked and answers as
the real one was seen to answer (mssql-python 1.15.0 against SQL Server
2022, 16.0.4295, on 2026-10-12). The tables it hands out have the Arrow
types the real one hands out. What the real one does is tried in the
tests marked ``mssql``.
"""
import datetime
import decimal
import random
import sys
import types
from decimal import Decimal

import pyarrow
import pytest

from src.v2 import mssql, statements
from src.v2.errors import ConfigurationError, DatabaseError
from src.v2.job.keys import normalize_config
from src.v2.job.model import Column
from src.v2.sessions import DATE, NUMBER, OTHER, TEXT, Field, Sessions, taken


def block(**given):
    """A connection block as a component hands it on: checked against the declared keys."""
    config, refusals = normalize_config(given, mssql.CONNECTION_KEYS, "component c (tMSSqlConnection)")
    assert not refusals, [f"{refusal.key}: {refusal.reason}" for refusal in refusals]
    return config


def refused(**given):
    _, refusals = normalize_config(given, mssql.CONNECTION_KEYS, "component c (tMSSqlConnection)")
    return [f"{refusal.key}: {refusal.reason}" for refusal in refusals]


SALES = dict(host="db.example", port="1433", dbname="sales", user="app", password="s3cret")
GIVEN = {"server": "db.example,1433", "database": "sales", "uid": "app", "pwd": "s3cret", "encrypt": "yes",
         "trust_server_certificate": "no"}


# ------------------------------------------------------------------
# What the driver is given
# ------------------------------------------------------------------

def test_a_host_a_port_a_database_a_user_and_a_password():
    assert mssql.arguments(block(**SALES)) == GIVEN


def test_a_port_may_be_written_as_text_or_as_a_number():
    assert mssql.arguments(block(**{**SALES, "port": 1444}))["server"] == "db.example,1444"
    assert mssql.arguments(block(**{**SALES, "port": " 1444 "}))["server"] == "db.example,1444"


def test_with_no_port_said_it_is_sql_servers_usual_one():
    given = dict(SALES)
    del given["port"]
    assert mssql.arguments(block(**given))["server"] == "db.example,1433"


def test_an_empty_port_leaves_the_port_to_the_driver_which_finds_the_one_of_an_instance_named_in_the_host():
    assert mssql.arguments(block(**{**SALES, "port": ""}))["server"] == "db.example"
    assert mssql.arguments(block(**{**SALES, "host": " db.example\\FINANCE ", "port": "  "}))["server"] == "db.example\\FINANCE"


@pytest.mark.parametrize("port", ["fifteen", "0", "70000", "-1", 1.5, True])
def test_a_port_that_is_none_is_refused(port):
    assert refused(**{**SALES, "port": port}) == [f"port: {port!r} is no port: give a whole number from 1 to 65535"]


def test_with_no_database_named_the_user_has_the_one_it_has_by_default():
    assert "database" not in mssql.arguments(block(**{**SALES, "dbname": " "}))


@pytest.mark.parametrize("said, given", [("no", "no"), ("STRICT", "strict"), (" Yes ", "yes"), (True, "yes"), (False, "no"),
                                         ("true", "yes"), ("false", "no"), ("mandatory", "yes"), ("optional", "no")])
def test_whether_what_is_sent_is_encrypted_is_the_jobs_to_say(said, given):
    assert mssql.arguments(block(**SALES, encrypt=said))["encrypt"] == given


def test_what_is_no_way_to_encrypt_is_refused():
    assert refused(**SALES, encrypt="maybe") == ["encrypt: 'maybe' is none of yes, no, strict"]


@pytest.mark.parametrize("said, given", [(True, "yes"), (False, "no"), ("true", "yes"), (" NO ", "no")])
def test_whether_the_servers_certificate_is_taken_unchecked_is_the_jobs_to_say(said, given):
    assert mssql.arguments(block(**SALES, trust_server_certificate=said))["trust_server_certificate"] == given


def test_what_is_no_switch_is_refused():
    assert refused(**SALES, trust_server_certificate="perhaps") == ["trust_server_certificate: 'perhaps' is neither true nor false"]


# ------------------------------------------------------------------
# Talend's JDBC parameters
# ------------------------------------------------------------------

def test_the_parameters_that_mean_something_here_are_read():
    made = mssql.arguments(block(**SALES, properties=(
        "encrypt=false;trustServerCertificate=TRUE;hostNameInCertificate=*.db.example;applicationIntent=ReadOnly;"
        "multiSubnetFailover=true;loginTimeout=30")))
    assert made == {**GIVEN, "encrypt": "no", "trust_server_certificate": "yes", "hostnameincertificate": "*.db.example",
                    "applicationintent": "ReadOnly", "multisubnetfailover": "yes", "timeout": 30}


def test_their_names_are_read_whatever_their_case_and_blanks_and_empty_parts_are_passed_over():
    made = mssql.arguments(block(**SALES, properties=" ; ENCRYPT = strict ;; trustservercertificate=false ; "))
    assert (made["encrypt"], made["trust_server_certificate"]) == ("strict", "no")


def test_a_key_of_v2s_own_goes_before_what_the_parameters_say():
    made = mssql.arguments(block(**SALES, encrypt="yes", trust_server_certificate=False,
                                 properties="encrypt=false;trustServerCertificate=true"))
    assert (made["encrypt"], made["trust_server_certificate"]) == ("yes", "no")


@pytest.mark.parametrize("properties", [
    "noDatetimeStringSync=true",   # What Talend's own input carries when nothing was said.
    "sendStringParametersAsUnicode=false;selectMethod=cursor;responseBuffering=adaptive;applicationName=nightly;appName=x",
    "",
])
def test_the_parameters_that_say_how_a_jdbc_driver_works_are_passed_over(properties):
    config = block(**SALES, properties=properties)
    assert mssql.problems(config) == []
    assert mssql.arguments(config) == GIVEN


def test_any_other_parameter_refuses_the_job_by_its_name_and_never_shows_what_it_holds():
    found = mssql.problems(block(**SALES, properties="integratedSecurity=true;password=hunter2;encrypt=true"))
    assert found == [
        "properties: `integratedSecurity` and `password` are parameters of a JDBC driver that v2 has no reading for; "
        "take them out. It reads encrypt, trustServerCertificate, hostNameInCertificate, applicationIntent, "
        "multiSubnetFailover and loginTimeout"
    ]
    one = mssql.problems(block(**SALES, properties="domain=CORP"))
    assert one[0].startswith("properties: `domain` is a parameter of a JDBC driver that v2 has no reading for; take it out.")


@pytest.mark.parametrize("properties, said", [
    ("encrypt=maybe", "properties: `encrypt` holds what is none of yes, no, strict"),
    ("trustServerCertificate=perhaps", "properties: `trustServerCertificate` holds what is neither true nor false"),
    ("multiSubnetFailover=2", "properties: `multiSubnetFailover` holds what is neither true nor false"),
    ("loginTimeout=soon", "properties: `loginTimeout` holds no whole number of seconds"),
    ("loginTimeout=-1", "properties: `loginTimeout` holds no whole number of seconds"),
    ("encrypt", "properties: holds a part that is no `name=value`"),
    ("=true", "properties: holds a part that is no `name=value`"),
    ("hostNameInCertificate=", "properties: `hostNameInCertificate` holds nothing"),
    ("applicationIntent=", "properties: `applicationIntent` holds nothing"),
])
def test_a_parameter_that_holds_what_it_cannot_is_said_without_showing_it(properties, said):
    assert mssql.problems(block(**SALES, properties=properties)) == [said]


# ------------------------------------------------------------------
# What is wrong with a block
# ------------------------------------------------------------------

def test_a_whole_block_has_no_problem():
    assert mssql.problems(block(**SALES)) == []


@pytest.mark.parametrize("given, said", [
    ({"host": ""}, "host: is empty; a session is opened with a host"),
    ({"host": "   "}, "host: is empty; a session is opened with a host"),
    ({"host": "db.example,1433"}, "host: holds a comma; give the port in `port`"),
    ({"user": " "}, "user: is empty; v2 signs in to SQL Server with a user and a password"),
])
def test_what_a_block_cannot_do_without(given, said):
    assert mssql.problems(block(**{**SALES, **given})) == [said]


def test_a_password_talend_encrypted_is_no_password():
    found = mssql.problems(block(**{**SALES, "password": "enc:system.encryption.key.v1:Zm9v"}))
    assert found == ["password: is text Talend encrypted with a key of its own, which v2 cannot read; give the "
                     "password itself, from a context variable (`${context.db_password}`)"]
    assert "Zm9v" not in found[0]


def test_every_problem_of_a_block_is_said_at_once():
    found = mssql.problems(block(host="", user="", properties="domain=CORP"))
    assert [said.split(":")[0] for said in found] == ["host", "user", "properties"]


def test_signing_in_through_microsoft_entra_is_refused_and_says_why():
    assert refused(**SALES, active_dir_auth=True) == [
        "active_dir_auth: v2 signs in to SQL Server with a user and a password of the database's own; signing in "
        "through Microsoft Entra was not at hand to be tried, and is not built"
    ]
    assert refused(**SALES, active_dir_auth=False) == []


def test_a_session_shared_with_the_jobs_a_job_runs_is_refused():
    assert refused(**SALES, use_shared_connection=True) == [
        "use_shared_connection: a session is not shared between a job and the jobs it runs: each opens its own"]


def test_what_talend_writes_for_its_own_jdbc_driver_is_read_and_changes_nothing():
    config = block(**SALES, driver="JTDS", encoding="ISO-8859-15", use_shared_connection=False,
                   shared_connection_name="", specify_datasource_alias=False, datasource_alias="",
                   active_dir_auth=False, schema_db="dbo")
    assert mssql.arguments(config) == GIVEN


def test_what_is_wrong_with_the_block_of_a_component_that_works_on_a_connections_session_is_nothing():
    config, _ = normalize_config({"use_existing_connection": True, "connection": "c"},
                                 mssql.CONNECTION_KEYS + mssql.WORKING_KEYS, "component c")
    assert mssql.working_problems(config) == []
    config["use_existing_connection"] = False
    assert [said.split(":")[0] for said in mssql.working_problems(config)] == ["host", "user"]


# ------------------------------------------------------------------
# The driver: a stand-in that notes what it is asked
# ------------------------------------------------------------------

class Refused(Exception):
    """The driver's own error, as mssql-python raises one: what it says itself, and what the database said."""

    def __init__(self, driver_error, ddbc_error="Unknown DDBC error"):
        super().__init__(f"Driver Error: {driver_error}; DDBC Error: {ddbc_error}")
        self.driver_error, self.ddbc_error = driver_error, ddbc_error


# What the real driver says of an error that comes while rows are fetched: nothing.
NO_REASON = ("An error occurred with SQLSTATE code: ",)


def rows(**columns):
    """A batch as the driver hands one out: each column given as its values and its Arrow type."""
    return pyarrow.record_batch([pyarrow.array(values, kind) for values, kind in columns.values()],
                                names=[name.rstrip("_") for name in columns])


class Rows:
    """One result of a statement that has columns.

    Args:
        batch: Its rows.
        scales: For each column, the digits after the point its type has.
        fails_after: How many rows are fetched before ``fault`` is raised.
        unreadable: What the Arrow path says of a column type it does not know.
    """

    def __init__(self, batch, scales=None, fails_after=None, fault=None, unreadable=None):
        self.batch, self.fails_after, self.fault, self.unreadable = batch, fails_after, fault, unreadable
        self.scales = scales or [0] * batch.num_columns


class Pooling:
    def __init__(self, initialized):
        self.initialized = initialized

    def is_initialized(self):
        return self.initialized


class Held:
    """A connection of the stand-in driver."""

    def __init__(self, driver):
        self.driver, self.did, self.timeout = driver, [], 0

    def cursor(self):
        return Cursor(self, self.timeout)

    def close(self):
        self.did.append("close")
        if "close" in self.driver.fails:
            raise Refused(*self.driver.fails["close"])


class Cursor:
    """A cursor of the stand-in driver. It goes through what a statement hands back as the real one does."""

    def __init__(self, held, timeout):
        self.held, self.timeout, self.results, self.at, self.taken = held, timeout, [], 0, 0

    def execute(self, statement, *values):
        self.held.did.append(("execute", statement, list(values[0]) if values else [], self.timeout))
        answer = self.held.driver.answers[statement]
        if isinstance(answer, Exception):
            raise answer
        self.results, self.at, self.taken = list(answer), 0, 0
        self._reached()
        return self

    @property
    def description(self):
        result = self.results[self.at] if self.at < len(self.results) else None
        if not isinstance(result, Rows):
            return None
        return [(field.name, object, None, 0, 0, scale, True) for field, scale in zip(result.batch.schema, result.scales)]

    def nextset(self):
        self.at, self.taken = self.at + 1, 0
        if self.at >= len(self.results):
            return False
        self._reached()
        return True

    def arrow_batch(self, size):
        result = self.results[self.at] if self.at < len(self.results) else None
        if not isinstance(result, Rows):
            raise RuntimeError("No active result set. Cannot fetch Arrow batch.")
        if result.unreadable:
            raise result.unreadable if isinstance(result.unreadable, Exception) else RuntimeError(result.unreadable)
        if result.fails_after is not None and size and self.taken + size > result.fails_after:
            raise result.fault
        batch = result.batch.slice(self.taken, size)
        self.taken += batch.num_rows
        return batch

    def close(self):
        self.held.did.append("cursor closed")
        if "cursor close" in self.held.driver.fails:
            raise Refused(*self.held.driver.fails["cursor close"])

    def _reached(self):
        if isinstance(self.results[self.at], Exception):
            raise self.results[self.at]


def stand_in(version="1.15.0", pooling_set=False, **fails):
    driver = types.ModuleType("mssql_python")
    driver.__version__ = version
    driver.Error = Refused
    driver.fails, driver.answers = fails, {}
    driver.asked, driver.opened, driver.pooling_asked = [], [], []
    driver.PoolingManager = Pooling(pooling_set)

    def pooling(**given):
        driver.pooling_asked.append(given)
        driver.PoolingManager.initialized = True

    def connect(connection_str="", autocommit=False, **given):
        driver.asked.append((connection_str, autocommit, given))
        if "connect" in fails:
            raise fails["connect"] if isinstance(fails["connect"], Exception) else Refused(*fails["connect"])
        driver.opened.append(Held(driver))
        return driver.opened[-1]

    driver.pooling, driver.connect = pooling, connect
    return driver


@pytest.fixture
def driver(monkeypatch):
    made = stand_in()
    monkeypatch.setitem(sys.modules, "mssql_python", made)
    return made


# ------------------------------------------------------------------
# Opening a session
# ------------------------------------------------------------------

def test_a_session_is_opened_with_what_the_block_says_and_every_statement_stored_by_itself(driver, caplog):
    with caplog.at_level("INFO", logger="src.v2"):
        session = mssql.opened(block(**SALES, schema_db="dbo"), "tDBConnection_1")
    assert driver.asked == [("", True, GIVEN)]
    assert (session.opened_by, session.schema, session.shared, session.asking) == ("tDBConnection_1", "dbo", False,
                                                                                    "tDBConnection_1")
    assert session.what == "app@db.example,1433/sales"
    assert "[tDBConnection_1] session opened: app@db.example,1433/sales" in caplog.text
    assert "s3cret" not in caplog.text


def test_a_session_is_named_by_where_it_is_and_as_whom(driver):
    assert mssql.opened(block(**{**SALES, "dbname": "", "port": ""}), "c").what == "app@db.example"
    assert mssql.opened(block(**SALES), "c", shared=True).shared is True


def test_the_seconds_given_for_signing_in_are_handed_over_by_themselves(driver):
    mssql.opened(block(**SALES, properties="loginTimeout=7"), "c")
    assert driver.asked == [("", True, {**GIVEN, "timeout": 7})]


def test_the_drivers_keeping_of_closed_sessions_is_turned_off_before_the_first_is_opened(driver):
    mssql.opened(block(**SALES), "c")
    mssql.opened(block(**SALES), "c")
    assert driver.pooling_asked == [{"enabled": False}]


def test_a_process_that_has_said_itself_how_sessions_are_kept_is_left_with_what_it_said(monkeypatch):
    made = stand_in(pooling_set=True)
    monkeypatch.setitem(sys.modules, "mssql_python", made)
    mssql.opened(block(**SALES), "c")
    assert made.pooling_asked == []


def test_a_session_that_is_not_opened_says_where_and_as_whom_in_the_databases_words_and_never_the_password(monkeypatch):
    monkeypatch.setitem(sys.modules, "mssql_python", stand_in(
        connect=("Invalid authorization specification", "[Microsoft][SQL Server]Login failed for user 'app'.")))
    with pytest.raises(DatabaseError) as failed:
        mssql.opened(block(**SALES), "c")
    assert str(failed.value) == "no session was opened as app@db.example,1433/sales: Login failed for user 'app'."


def test_a_certificate_this_machine_does_not_trust_is_said_with_what_can_be_done(monkeypatch):
    monkeypatch.setitem(sys.modules, "mssql_python", stand_in(connect=(
        "Client unable to establish connection",
        "[Microsoft]SSL Provider: [error:0A000086:SSL routines::certificate verify failed:self-signed certificate]")))
    with pytest.raises(DatabaseError) as failed:
        mssql.opened(block(**SALES), "c")
    assert str(failed.value) == (
        "no session was opened as app@db.example,1433/sales: SSL Provider: [error:0A000086:SSL routines::certificate "
        "verify failed:self-signed certificate]. The server's certificate is not one this machine trusts: have it "
        "signed by an authority this machine knows, or turn `trust_server_certificate` on, and what is sent is still "
        "encrypted but the server is not checked")


@pytest.mark.parametrize("code, meaning", [
    ("0x2AF9", "no such host is known"), ("0x274D", "the connection was refused"),
    ("0x274C", "nothing answered in time"), ("0x2746", "the other side ended the connection"),
])
def test_a_number_the_driver_gives_for_what_the_network_did_is_said_in_words(monkeypatch, code, meaning):
    monkeypatch.setitem(sys.modules, "mssql_python", stand_in(connect=(
        "Client unable to establish connection", f"[Microsoft]TCP Provider: Error code {code}")))
    with pytest.raises(DatabaseError) as failed:
        mssql.opened(block(**SALES), "c")
    assert str(failed.value) == (f"no session was opened as app@db.example,1433/sales: TCP Provider: Error code {code} "
                                 f"({meaning})")


def test_a_number_that_has_no_words_here_is_left_as_the_driver_gave_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "mssql_python", stand_in(connect=(
        "Client unable to establish connection", "[Microsoft]TCP Provider: Error code 0x2726")))
    with pytest.raises(DatabaseError) as failed:
        mssql.opened(block(**SALES), "c")
    assert str(failed.value).endswith("/sales: TCP Provider: Error code 0x2726")


def test_a_session_that_is_not_opened_for_no_reason_the_driver_gives_says_that(monkeypatch):
    monkeypatch.setitem(sys.modules, "mssql_python", stand_in(connect=NO_REASON))
    with pytest.raises(DatabaseError) as failed:
        mssql.opened(block(**SALES), "c")
    assert str(failed.value) == "no session was opened as app@db.example,1433/sales: the driver gave no reason"


def test_no_driver_is_said_with_how_to_get_one(monkeypatch):
    monkeypatch.setitem(sys.modules, "mssql_python", None)
    with pytest.raises(DatabaseError) as failed:
        mssql.opened(block(**SALES), "c")
    assert str(failed.value) == ("mssql-python is not installed, and a SQL Server component needs it: "
                                 "pip install 'dataprep[v2-mssql]'")


@pytest.mark.parametrize("fault", [
    OSError("libltdl.so.7: cannot open shared object file: No such file or directory"),
    ImportError("libltdl.so.7: cannot open shared object file", name="mssql_python.ddbc_bindings"),
])
def test_a_driver_that_is_there_and_cannot_be_loaded_is_said_in_its_words(monkeypatch, fault):
    def fails(name):
        raise fault

    monkeypatch.setattr(mssql.importlib, "import_module", fails)
    with pytest.raises(DatabaseError) as failed:
        mssql.opened(block(**SALES), "c")
    assert str(failed.value).startswith("mssql-python is installed and could not be loaded: libltdl.so.7: cannot open")


@pytest.mark.parametrize("version", ["1.4.0", "1.14.2", "0.9.0"])
def test_a_driver_older_than_the_one_v2_was_tried_with_is_refused(monkeypatch, version):
    monkeypatch.setitem(sys.modules, "mssql_python", stand_in(version=version))
    with pytest.raises(DatabaseError) as failed:
        mssql.opened(block(**SALES), "c")
    assert str(failed.value) == (f"mssql-python {version} is installed, and 1.15.0 or later is needed: v2 was tried "
                                 "with no earlier one")


@pytest.mark.parametrize("version", ["1.15.0", "1.16.0", "2.0.0b1"])
def test_a_driver_new_enough_is_taken(monkeypatch, version):
    made = stand_in(version=version)
    monkeypatch.setitem(sys.modules, "mssql_python", made)
    mssql.opened(block(**SALES), "c")
    assert len(made.opened) == 1


# ------------------------------------------------------------------
# The words of a failure
# ------------------------------------------------------------------

def test_what_the_database_said_is_said_without_who_passed_it_on():
    fault = Refused("Base table or view not found", "[Microsoft][SQL Server]Invalid object name 'dbo.no_such_table'.")
    assert mssql.said(fault) == "Invalid object name 'dbo.no_such_table'."


def test_what_the_driver_says_itself_is_said_when_the_database_said_nothing():
    assert mssql.said(Refused("Timeout expired", "[Microsoft]Query timeout expired")) == "Query timeout expired"
    assert mssql.said(Refused("Connection parameter 'pwd' must not contain a NUL (\\x00) character.",
                              "Embedded NUL in connection parameter.")) == "Embedded NUL in connection parameter."
    assert mssql.said(Refused("General error")) == "General error"


def test_a_failure_the_driver_has_lost_the_reason_of_has_no_words():
    assert mssql.said(Refused(*NO_REASON)) == ""


def test_the_words_of_a_failure_are_one_line_of_ascii():
    fault = Refused("x", "[Microsoft][SQL Server]Conversion failed when converting\r\n the varchar value 'caf\u00e9' ")
    assert mssql.said(fault) == "Conversion failed when converting the varchar value 'caf\\xe9'"
    assert mssql.said(ValueError("no\nwords of the driver's")) == "no words of the driver's"


# ------------------------------------------------------------------
# What a session asks: a query run once
# ------------------------------------------------------------------

def opened(driver, **more):
    session = mssql.opened(block(**SALES), "conn", **more)
    return session, driver.opened[-1]


QUERY = "select n, s from t where s = ?"


def two_columns():
    return rows(n=([1, 2, 3], pyarrow.int32()), s=(["a", "b", "c"], pyarrow.large_string()))


def test_a_query_is_run_once_with_its_values_and_its_rows_wait_for_whoever_takes_them(driver):
    driver.answers[QUERY] = [Rows(two_columns())]
    session, held = opened(driver)
    assert session.fields(QUERY, ["x"]) == [Field("n", NUMBER, "INT"), Field("s", TEXT, "text")]
    tables = list(session.batches(QUERY, ["x"], [pyarrow.int64(), pyarrow.large_string()], 2))
    assert [table.to_pydict() for table in tables] == [{"C1": [1, 2], "C2": ["a", "b"]}, {"C1": [3], "C2": ["c"]}]
    assert [str(kind) for kind in tables[0].schema.types] == ["int64", "large_string"]
    assert held.did == [("execute", QUERY, ["x"], 0), "cursor closed"]


def test_a_statement_with_no_value_is_handed_over_with_none(driver):
    driver.answers["select 1 n"] = [Rows(rows(n=([1], pyarrow.int32())))]
    session, held = opened(driver)
    session.fields("select 1 n")
    assert held.did == [("execute", "select 1 n", [], 0)]


def test_rows_asked_for_with_nothing_waiting_are_asked_of_the_database(driver):
    driver.answers[QUERY] = [Rows(two_columns())]
    session, held = opened(driver)
    tables = list(session.batches(QUERY, ["x"], [pyarrow.int64(), pyarrow.large_string()], 10))
    assert [table.num_rows for table in tables] == [3]
    assert held.did == [("execute", QUERY, ["x"], 0), "cursor closed"]


def test_a_result_nobody_took_is_let_go_before_the_next_statement_is_run(driver):
    driver.answers[QUERY] = [Rows(two_columns())]
    driver.answers["select 1 n"] = [Rows(rows(n=([1], pyarrow.int32())))]
    session, held = opened(driver)
    session.fields(QUERY, ["x"])
    session.fields("select 1 n")
    assert held.did == [("execute", QUERY, ["x"], 0), "cursor closed", ("execute", "select 1 n", [], 0)]


def test_rows_of_another_statement_than_the_one_that_waits_are_asked_for_anew(driver):
    driver.answers[QUERY] = [Rows(two_columns())]
    session, held = opened(driver)
    session.fields(QUERY, ["x"])
    list(session.batches(QUERY, ["y"], [pyarrow.int64(), pyarrow.large_string()], 10))
    assert held.did == [("execute", QUERY, ["x"], 0), "cursor closed", ("execute", QUERY, ["y"], 0), "cursor closed"]


def test_a_query_with_no_rows_hands_on_none(driver):
    driver.answers[QUERY] = [Rows(two_columns().slice(0, 0))]
    session, held = opened(driver)
    assert list(session.batches(QUERY, ["x"], [pyarrow.int64(), pyarrow.large_string()], 10)) == []
    assert held.did[-1] == "cursor closed"


def test_what_comes_before_the_first_rows_of_a_statement_is_passed_over(driver):
    # A procedure that changes something first hands back a count of rows, and a PRINT a result with nothing in it.
    driver.answers["exec p"] = [1, 0, Rows(rows(n=([7], pyarrow.int64())))]
    session, held = opened(driver)
    assert session.fields("exec p") == [Field("n", NUMBER, "BIGINT")]
    assert [table.to_pydict() for table in session.batches("exec p", None, [pyarrow.int64()], 10)] == [{"C1": [7]}]


def test_a_statement_that_hands_back_no_rows_at_all_is_no_query(driver):
    driver.answers["update t set s = s"] = [3]
    session, held = opened(driver)
    with pytest.raises(ConfigurationError) as failed:
        session.fields("update t set s = s")
    assert str(failed.value) == ("the statement was run and handed back no rows to read: an input reads the rows of "
                                 "a query")
    assert held.did[-1] == "cursor closed"


def test_a_statement_the_database_refuses_is_said_in_its_words(driver):
    driver.answers["select * from nope"] = Refused(
        "Base table or view not found", "[Microsoft][SQL Server]Invalid object name 'nope'.")
    session, held = opened(driver)
    with pytest.raises(DatabaseError) as failed:
        session.fields("select * from nope")
    assert str(failed.value) == "Invalid object name 'nope'."
    assert held.did == [("execute", "select * from nope", [], 0), "cursor closed"]


def test_a_statement_that_fails_for_no_reason_the_driver_gives_says_that(driver):
    driver.answers["select 1 n"] = Refused(*NO_REASON)
    session, _ = opened(driver)
    with pytest.raises(DatabaseError, match="^the driver gave no reason$"):
        session.fields("select 1 n")


def test_a_result_whose_columns_the_driver_cannot_tell_is_said_in_its_words(driver):
    driver.answers["q"] = [Rows(rows(n=([1], pyarrow.int32())), unreadable=Refused(
        "Communication link failure", "[Microsoft]Communication link failure"))]
    session, held = opened(driver)
    with pytest.raises(DatabaseError, match="^Communication link failure$"):
        session.fields("q")
    # The result is let go of at once, and does not wait for the next statement to be.
    assert held.did[-1] == "cursor closed"


def test_a_result_the_driver_will_not_let_go_of_stops_nothing(monkeypatch):
    made = stand_in(**{"cursor close": ("Communication link failure", "[Microsoft]Communication link failure")})
    monkeypatch.setitem(sys.modules, "mssql_python", made)
    made.answers["select 1 n"] = [Rows(rows(n=([1], pyarrow.int32())))]
    session = mssql.opened(block(**SALES), "c")
    session.fields("select 1 n")
    assert session.fields("select 1 n") == [Field("n", NUMBER, "INT")]
    assert [did for did in made.opened[0].did if did != "cursor closed"] == [("execute", "select 1 n", [], 0)] * 2


def test_a_failure_after_what_came_first_is_seen_when_the_rows_are_looked_for(driver):
    driver.answers["exec p"] = [1, Refused("Syntax error or access violation", "[Microsoft][SQL Server]it failed early")]
    session, held = opened(driver)
    with pytest.raises(DatabaseError, match="^it failed early$"):
        session.fields("exec p")
    assert held.did[-1] == "cursor closed"


def test_a_statement_the_driver_itself_does_not_take_is_said_in_its_words(driver):
    driver.answers["select 7 %(n)s from t where s = ?"] = TypeError(
        "Parameter style mismatch: query uses named placeholders (%(name)s), but list was provided.")
    session, held = opened(driver)
    with pytest.raises(DatabaseError) as failed:
        session.fields("select 7 %(n)s from t where s = ?", ["x"])
    assert str(failed.value) == ("the driver did not take the statement: Parameter style mismatch: query uses named "
                                 "placeholders (%(name)s), but list was provided.")
    assert held.did[-1] == "cursor closed"


def test_the_seconds_a_query_is_given_are_set_before_it_is_run_and_none_when_none_are_said(driver):
    driver.answers["select 1 n"] = [Rows(rows(n=([1], pyarrow.int32())))]
    session, held = opened(driver)
    session.limit = 30
    session.fields("select 1 n")
    session.limit = 0
    session.fields("select 1 n")
    assert [did[3] for did in held.did if did != "cursor closed"] == [30, 0]


def test_a_query_that_takes_longer_than_it_is_given_says_how_long_that_was(driver):
    driver.answers["select 1 n"] = Refused("Timeout expired", "[Microsoft]Query timeout expired")
    session, _ = opened(driver)
    session.limit = 2
    with pytest.raises(DatabaseError) as failed:
        session.fields("select 1 n")
    assert str(failed.value) == "Query timeout expired: the query was given 2 second(s) (`query_timeout_in_seconds`)"


# ------------------------------------------------------------------
# What a query hands back, by the type the driver hands it out in
# ------------------------------------------------------------------

@pytest.mark.parametrize("kind, family, said", [
    (pyarrow.int64(), NUMBER, "BIGINT"), (pyarrow.int32(), NUMBER, "INT"), (pyarrow.int16(), NUMBER, "SMALLINT"),
    (pyarrow.uint8(), NUMBER, "TINYINT"), (pyarrow.bool_(), NUMBER, "BIT"),
    (pyarrow.decimal128(18, 2), NUMBER, "DECIMAL(18,2)"), (pyarrow.float64(), NUMBER, "FLOAT"),
    (pyarrow.float32(), NUMBER, "REAL"), (pyarrow.date32(), DATE, "DATE"), (pyarrow.timestamp("us"), DATE, "DATETIME"),
    (pyarrow.large_string(), TEXT, "text"), (pyarrow.string(), TEXT, "text"), (pyarrow.time64("ns"), TEXT, "TIME"),
])
def test_what_kind_each_column_of_a_result_is(driver, kind, family, said):
    driver.answers["q"] = [Rows(rows(c=([None], kind)))]
    session, _ = opened(driver)
    assert session.fields("q") == [Field("c", family, said)]


def test_a_date_with_a_time_zone_is_not_read_and_says_what_to_write_in_the_query(driver):
    driver.answers["q"] = [Rows(rows(at=([None], pyarrow.timestamp("us", tz="+00:00"))))]
    session, _ = opened(driver)
    (field,) = session.fields("q")
    assert (field.family, field.said) == (OTHER, "a date with a time zone (DATETIMEOFFSET)")
    with pytest.raises(ConfigurationError) as failed:
        taken([Column(name="at", type="str")], [field], session.advice)
    assert str(failed.value) == (
        "column 'at': the query hands back a date with a time zone (DATETIMEOFFSET), which v2 does not read: the "
        "driver hands it on without its zone. Write in the query what is wanted: `convert(varchar(34), <column>, 121)` "
        "for its text with the zone, `cast(<column> at time zone 'UTC' as datetime2)` for its clock in UTC, or "
        "`cast(<column> as datetime2)` for the clock of its own zone")


@pytest.mark.parametrize("kind", [pyarrow.large_binary(), pyarrow.binary()])
def test_binary_data_is_not_read_and_says_what_to_write_in_the_query(driver, kind):
    driver.answers["q"] = [Rows(rows(raw=([None], kind)))]
    session, _ = opened(driver)
    (field,) = session.fields("q")
    with pytest.raises(ConfigurationError) as failed:
        taken([Column(name="raw", type="str")], [field], session.advice)
    assert str(failed.value) == (
        "column 'raw': the query hands back binary data, which v2 does not read: write it as text in the query, "
        "`convert(varchar(max), <column>, 2)` for its hexadecimal digits")


def test_a_kind_nothing_is_known_of_is_not_read(driver):
    driver.answers["q"] = [Rows(rows(odd=([None], pyarrow.duration("s"))))]
    session, _ = opened(driver)
    (field,) = session.fields("q")
    with pytest.raises(ConfigurationError) as failed:
        taken([Column(name="odd", type="str")], [field], session.advice)
    assert str(failed.value) == ("column 'odd': the query hands back duration[s], which v2 does not read: turn it "
                                 "into text, a number or a date in the query")


def test_a_column_the_driver_cannot_hand_on_at_all_is_said_with_what_to_do(driver):
    driver.answers["q"] = [Rows(rows(v=([None], pyarrow.int32())), unreadable=(
        "Unsupported data type for Arrow batch fetch for column - v, Type - -150, column ID - 1"))]
    session, held = opened(driver)
    with pytest.raises(ConfigurationError) as failed:
        session.fields("q")
    assert str(failed.value) == (
        "the driver cannot hand on a column of the query (Unsupported data type for Arrow batch fetch for column - v, "
        "Type - -150, column ID - 1): turn it into text, a number or a date in the query; a sql_variant is cast to "
        "the type it holds")
    assert held.did[-1] == "cursor closed"


# ------------------------------------------------------------------
# The type each column is handed on in
# ------------------------------------------------------------------

def declared(*columns):
    made = []
    for at, column in enumerate(columns, start=1):
        kind, _, places = column.partition("#")
        made.append(Column(name=f"c{at}", type=kind, precision=int(places) if places else None))
    return made


def test_the_query_stands_as_it_is_written_and_each_column_is_asked_for_as_the_job_declares_it(driver):
    session, _ = opened(driver)
    numbers = [Field("C", NUMBER, "INT")] * 6
    statement, kinds = session.typed("select 1 order by 1 -- as written;", declared(
        "int", "float", "bool", "Decimal#2", "Decimal", "str"), numbers)
    assert statement == "select 1 order by 1 -- as written;"
    assert [str(kind) for kind in kinds] == ["int64", "double", "int8", "decimal128(38, 2)", "decimal128(38, 10)",
                                             "large_string"]
    dates = [Field("C", DATE, "DATETIME")] * 3
    assert [str(kind) for kind in session.typed("q", declared("datetime", "date", "str"), dates)[1]] == [
        "timestamp[us]", "date32[day]", "large_string"]
    texts = [Field("C", TEXT, "text")] * 4
    assert [str(kind) for kind in session.typed("q", declared("str", "int", "date", "Decimal#2"), texts)[1]] == [
        "large_string"] * 4


def test_sql_server_is_handed_a_statement_with_its_values_by_place(driver):
    made = statements.read("select * from t where d = '${context.d}' and s like N'a${context.s}'",
                           {"d": "2024", "s": "x"}, {}, dialect=statements.TSQL)
    session, _ = opened(driver)
    assert session.bound(made) == ("select * from t where d = ? and s like N'a' + ?", ["2024", "x"])


# ------------------------------------------------------------------
# Rows as they come, and what ends them
# ------------------------------------------------------------------

def test_a_moment_and_a_time_of_day_are_written_with_the_digits_the_database_says_their_types_have(driver):
    batch = rows(at=([datetime.datetime(2026, 10, 12, 14, 3, 5, 997000)], pyarrow.timestamp("us")),
                 small=([datetime.datetime(2026, 10, 12, 14, 3)], pyarrow.timestamp("us")),
                 of_day=([50585120000000], pyarrow.time64("ns")))
    driver.answers["q"] = [Rows(batch, scales=[3, 0, 2])]
    session, _ = opened(driver)
    text = pyarrow.large_string()
    (table,) = session.batches("q", None, [text, text, text], 10)
    assert table.to_pydict() == {"C1": ["2026-10-12 14:03:05.997"], "C2": ["2026-10-12 14:03:00"], "C3": ["14:03:05.12"]}


def test_a_query_the_database_ends_while_its_rows_are_read_says_how_far_it_came_and_that_no_reason_came(driver):
    driver.answers[QUERY] = [Rows(two_columns(), fails_after=2, fault=Refused(*NO_REASON))]
    session, held = opened(driver)
    taken_so_far = []
    with pytest.raises(DatabaseError) as failed:
        for table in session.batches(QUERY, ["x"], [pyarrow.int64(), pyarrow.large_string()], 2):
            taken_so_far.append(table.num_rows)
    assert taken_so_far == [2]
    assert str(failed.value) == (
        "the database ended the query after 2 row(s) were read, and the driver hands on no reason for it: run the "
        "query in another client to see what it was")
    assert held.did[-1] == "cursor closed"


def test_a_failure_while_rows_are_read_that_has_a_reason_says_it(driver):
    driver.answers[QUERY] = [Rows(two_columns(), fails_after=0, fault=Refused(
        "Communication link failure", "[Microsoft]Communication link failure"))]
    session, _ = opened(driver)
    with pytest.raises(DatabaseError) as failed:
        list(session.batches(QUERY, ["x"], [pyarrow.int64(), pyarrow.large_string()], 2))
    assert str(failed.value) == "the query failed after 0 row(s) were read: Communication link failure"


def test_what_a_statement_does_after_its_rows_is_drawn_to_its_end_and_a_failure_there_fails_it(driver):
    driver.answers["exec p"] = [Rows(rows(n=([1, 2], pyarrow.int32()))),
                                Refused("Syntax error or access violation",
                                        "[Microsoft][SQL Server]it failed after its rows")]
    session, held = opened(driver)
    with pytest.raises(DatabaseError) as failed:
        list(session.batches("exec p", None, [pyarrow.int64()], 10))
    assert str(failed.value) == "the query failed after 2 row(s) were read: it failed after its rows"
    assert held.did[-1] == "cursor closed"


@pytest.mark.parametrize("more, said", [
    ([Rows(rows(x=([1], pyarrow.int32())))], "2 results: the first is read and the other is passed over"),
    ([3, Rows(rows(x=([1], pyarrow.int32()))), Rows(rows(y=([1], pyarrow.int32())))],
     "3 results: the first is read and the others are passed over"),
])
def test_rows_a_statement_hands_back_after_its_first_are_passed_over_and_said(driver, caplog, more, said):
    driver.answers["exec p"] = [Rows(rows(n=([1, 2], pyarrow.int32())))] + more
    session, _ = opened(driver)
    session.asking = "in"
    with caplog.at_level("INFO", logger="src.v2"):
        tables = list(session.batches("exec p", None, [pyarrow.int64()], 10))
    assert [table.to_pydict() for table in tables] == [{"C1": [1, 2]}]
    assert f"[in] the query handed back {said}" in caplog.text


def test_counts_after_the_rows_are_no_results_to_speak_of(driver, caplog):
    driver.answers["exec p"] = [Rows(rows(n=([1], pyarrow.int32()))), 4, 0]
    session, _ = opened(driver)
    with caplog.at_level("INFO", logger="src.v2"):
        list(session.batches("exec p", None, [pyarrow.int64()], 10))
    assert "handed back" not in caplog.text


def test_whoever_stops_taking_rows_leaves_no_result_waiting(driver):
    driver.answers[QUERY] = [Rows(two_columns())]
    session, held = opened(driver)
    taking = session.batches(QUERY, ["x"], [pyarrow.int64(), pyarrow.large_string()], 1)
    next(taking)
    taking.close()
    assert held.did == [("execute", QUERY, ["x"], 0), "cursor closed"]


# ------------------------------------------------------------------
# Ending a session
# ------------------------------------------------------------------

def test_a_close_lets_go_of_a_result_that_waits_and_of_the_connection_itself(driver):
    driver.answers[QUERY] = [Rows(two_columns())]
    session, held = opened(driver)
    session.fields(QUERY, ["x"])
    session.close()
    session.close()
    assert held.did == [("execute", QUERY, ["x"], 0), "cursor closed", "close"]


def test_a_close_the_driver_refuses_is_said_in_its_words(monkeypatch):
    made = stand_in(close=("Communication link failure", "[Microsoft]Communication link failure"))
    monkeypatch.setitem(sys.modules, "mssql_python", made)
    session = mssql.opened(block(**SALES), "c")
    with pytest.raises(DatabaseError, match="^Communication link failure$"):
        session.close()


# ------------------------------------------------------------------
# Whose session a component works on
# ------------------------------------------------------------------

def component(sessions, **config):
    given, _ = normalize_config({**SALES, **config}, mssql.CONNECTION_KEYS + mssql.WORKING_KEYS, "component in")
    return types.SimpleNamespace(id="in", config=given, run_context=types.SimpleNamespace(sessions=sessions))


def test_a_component_works_on_the_session_of_the_connection_it_names_and_says_who_it_is(driver):
    sessions = Sessions()
    shared, _ = opened(driver)
    sessions.share(shared)
    session, own = mssql.session_of(component(sessions, use_existing_connection=True, connection="conn"))
    assert (session is shared, own, session.asking) == (True, False, "in")


def test_a_component_that_names_none_opens_a_session_of_its_own_with_its_block(driver):
    session, own = mssql.session_of(component(Sessions()))
    assert (own, session.opened_by, session.asking, session.what) == (True, "in", "in", "app@db.example,1433/sales")


# ------------------------------------------------------------------
# A value handed on as the job declares it: as SQL Server itself converts
# ------------------------------------------------------------------

def handed(batch, *kinds, digits=None, before=0):
    made = mssql.as_asked(batch, list(kinds), digits or [0] * batch.num_columns, before)
    assert [str(kind) for kind in made.schema.types] == [str(kind) for kind in kinds]
    assert made.schema.names == [f"C{at}" for at in range(1, batch.num_columns + 1)]
    return [made.column(at).to_pylist() for at in range(made.num_columns)]


def one(values, kind, to, **more):
    return handed(rows(c=(values, kind)), to, **more)[0]


def test_a_whole_number_is_cut_off_at_its_point_and_never_rounded():
    wide = pyarrow.decimal128(38, 10)
    assert one([Decimal("2.7"), Decimal("-2.7"), Decimal("2.5"), Decimal("-0.5"), None], wide, pyarrow.int64()) == [
        2, -2, 2, 0, None]
    assert one([2.7, -2.7, -0.9, 1e15, None], pyarrow.float64(), pyarrow.int64()) == [2, -2, 0, 10 ** 15, None]
    assert one([2.5, -2.5], pyarrow.float32(), pyarrow.int64()) == [2, -2]


@pytest.mark.parametrize("values, kind, made", [
    ([9223372036854775807, -9223372036854775808, None], pyarrow.int64(), [9223372036854775807, -9223372036854775808, None]),
    ([5, None], pyarrow.int32(), [5, None]), ([-7], pyarrow.int16(), [-7]), ([255, 0], pyarrow.uint8(), [255, 0]),
    ([True, False, None], pyarrow.bool_(), [1, 0, None]),
])
def test_a_whole_number_from_every_kind_of_whole_number(values, kind, made):
    assert one(values, kind, pyarrow.int64()) == made


def test_a_float_from_every_kind_of_number_is_the_nearest_one():
    assert one([2 ** 53 + 1, 5, None], pyarrow.int64(), pyarrow.float64()) == [9007199254740992.0, 5.0, None]
    wide = pyarrow.decimal128(38, 10)
    assert one([Decimal("0.1"), Decimal("1234567890123456789012345678.0123456789"), None], wide, pyarrow.float64()) == [
        0.1, 1.2345678901234569e+27, None]
    # Arrow's own cast of this one is a step off (9.138185270471748e+20). SQL Server's own is the nearest, as here.
    assert one([Decimal("913818527047174782727")], pyarrow.decimal128(38, 0), pyarrow.float64()) == [9.138185270471747e+20]
    # The number a short float exactly is, which is not the one it prints as.
    assert one([0.1], pyarrow.float32(), pyarrow.float64()) == [0.10000000149011612]
    assert one([True, False], pyarrow.bool_(), pyarrow.float64()) == [1.0, 0.0]
    assert one([1.5, None], pyarrow.float64(), pyarrow.float64()) == [1.5, None]


def test_a_decimal_with_more_places_than_declared_is_rounded_a_half_going_away_from_nought():
    values = [Decimal("2.675"), Decimal("-2.675"), Decimal("2.665"), Decimal("0.004"), None]
    assert one(values, pyarrow.decimal128(18, 3), pyarrow.decimal128(38, 2)) == [
        Decimal("2.68"), Decimal("-2.68"), Decimal("2.67"), Decimal("0.00"), None]


def test_a_decimal_with_fewer_places_than_declared_gets_them():
    assert one([Decimal("1.5"), None], pyarrow.decimal128(18, 2), pyarrow.decimal128(38, 10)) == [
        Decimal("1.5000000000"), None]
    assert one([Decimal("1.50")], pyarrow.decimal128(38, 2), pyarrow.decimal128(38, 2)) == [Decimal("1.50")]


@pytest.mark.parametrize("values, kind", [([5, None], pyarrow.int64()), ([5, None], pyarrow.int32()),
                                          ([5, None], pyarrow.uint8())])
def test_a_decimal_from_a_whole_number(values, kind):
    assert one(values, kind, pyarrow.decimal128(38, 2)) == [Decimal("5.00"), None]
    # More places than a whole number of 64 bits leaves room for: the value counts, and not the kind it came in.
    assert one(values, kind, pyarrow.decimal128(38, 25)) == [Decimal("5").scaleb(0).quantize(Decimal(1).scaleb(-25)), None]


def test_a_decimal_from_a_true_or_false():
    assert one([True, False, None], pyarrow.bool_(), pyarrow.decimal128(38, 2)) == [Decimal("1.00"), Decimal("0.00"), None]


def test_a_decimal_from_a_float_goes_by_the_number_the_float_exactly_is_a_tie_going_away_from_nought():
    # As SQL Server's own cast: 2.675 is a little less than it looks, 0.125 is exactly halfway.
    values = [2.675, -2.675, 0.125, -0.125, 0.375, 1e22, 0.1, 0.0, None]
    assert one(values, pyarrow.float64(), pyarrow.decimal128(38, 2)) == [
        Decimal("2.67"), Decimal("-2.67"), Decimal("0.13"), Decimal("-0.13"), Decimal("0.38"),
        Decimal("10000000000000000000000.00"), Decimal("0.10"), Decimal("0.00"), None]
    assert one([0.1], pyarrow.float64(), pyarrow.decimal128(38, 20)) == [Decimal("0.10000000000000000555")]
    assert one([0.5, 1.5, 2.5, -0.5], pyarrow.float64(), pyarrow.decimal128(38, 0)) == [
        Decimal("1"), Decimal("2"), Decimal("3"), Decimal("-1")]


def test_a_decimal_from_a_short_float_goes_by_the_number_that_one_exactly_is():
    assert one([0.1, 0.125], pyarrow.float32(), pyarrow.decimal128(38, 20)) == [
        Decimal("0.10000000149011611938"), Decimal("0.12500000000000000000")]
    assert one([0.125, -0.375, 2.675, None], pyarrow.float32(), pyarrow.decimal128(38, 2)) == [
        Decimal("0.13"), Decimal("-0.38"), Decimal("2.67"), None]
    assert one([2.5, 8388607.5], pyarrow.float32(), pyarrow.decimal128(38, 0)) == [Decimal("3"), Decimal("8388608")]


@pytest.mark.parametrize("places", [0, 1, 2, 5, 10, 17])
def test_a_decimal_from_any_float_is_what_exact_arithmetic_makes_of_it(places):
    drawn = random.Random(20261012 + places)
    floats = [drawn.uniform(-1000, 1000) for _ in range(300)]
    floats += [drawn.randrange(-10 ** 6, 10 ** 6) / 2 ** drawn.randrange(1, 20) for _ in range(300)]
    floats += [whole + part for whole in (0, 1, -3, 2 ** 40) for part in (0.5, 0.25, 0.125, 0.0625, 0.375, 0.875)]
    floats += [0.0, -0.0, 5e-324, 1e-10, 123456789.123456789, 2 ** 53 + 2.0]
    exact = decimal.Context(prec=400, rounding=decimal.ROUND_HALF_UP)
    step = Decimal(1).scaleb(-places)
    assert one(floats, pyarrow.float64(), pyarrow.decimal128(38, places)) == [
        Decimal(value).quantize(step, context=exact) for value in floats]


def test_a_float_that_lies_halfway_at_the_most_places_a_decimal_has():
    # Two to the power of minus 39 has 39 digits after its point, the last a five.
    exact = decimal.Context(prec=400, rounding=decimal.ROUND_HALF_UP)
    step = Decimal(1).scaleb(-38)
    values = [2.0 ** -39, -(2.0 ** -39), 0.25, None]
    assert one(values, pyarrow.float64(), pyarrow.decimal128(38, 38)) == [
        Decimal(2.0 ** -39).quantize(step, context=exact), Decimal(-(2.0 ** -39)).quantize(step, context=exact),
        Decimal("0.25").quantize(step, context=exact), None]
    assert one(values, pyarrow.float64(), pyarrow.decimal128(38, 38))[0] == Decimal("0." + "0" * 11 + "181898940354585647583007813")
    # Halfway at 31 places with seven digits before the point: one digit more than a Decimal holds, until it is
    # rounded.
    wide = 2097151 + 2.0 ** -32
    assert one([wide, -wide], pyarrow.float64(), pyarrow.decimal128(38, 31)) == [
        Decimal(wide).quantize(Decimal(1).scaleb(-31), context=exact), Decimal(-wide).quantize(Decimal(1).scaleb(-31), context=exact)]


def test_a_true_or_false_is_nought_or_one_and_anything_but_nought_is_one():
    assert one([True, False, None], pyarrow.bool_(), pyarrow.int8()) == [1, 0, None]
    assert one([0, 7, -1, None], pyarrow.int32(), pyarrow.int8()) == [0, 1, 1, None]
    assert one([0, 255], pyarrow.uint8(), pyarrow.int8()) == [0, 1]
    assert one([Decimal("0.00"), Decimal("0.01"), None], pyarrow.decimal128(18, 2), pyarrow.int8()) == [0, 1, None]
    assert one([0.0, -0.0, 0.5, None], pyarrow.float64(), pyarrow.int8()) == [0, 0, 1, None]


def test_a_number_as_text_is_written_as_the_database_holds_it():
    text = pyarrow.large_string()
    assert one([9223372036854775807, -5, None], pyarrow.int64(), text) == ["9223372036854775807", "-5", None]
    assert one([255], pyarrow.uint8(), text) == ["255"]
    assert one([True, False, None], pyarrow.bool_(), text) == ["1", "0", None]
    assert one([Decimal("1.50"), Decimal("-0.01"), None], pyarrow.decimal128(18, 2), text) == ["1.50", "-0.01", None]
    assert one([Decimal("-0.0000000005"), Decimal("1234567890123456789012345678.0123456789")],
               pyarrow.decimal128(38, 10), text) == ["-0.0000000005", "1234567890123456789012345678.0123456789"]
    assert one([Decimal("7")], pyarrow.decimal128(5, 0), text) == ["7"]


def test_a_float_as_text_is_written_as_v2_writes_a_float():
    text = pyarrow.large_string()
    assert one([1.5, 100.0, 1e22, 1e-05, 0.1, None], pyarrow.float64(), text) == ["1.5", "100.0", "1e+22", "1e-05", "0.1", None]
    assert one([3.4028235e38, 0.1], pyarrow.float32(), text) == ["3.4028235e+38", "0.1"]


def test_a_day_and_a_moment_are_made_one_of_the_other():
    moments = [datetime.datetime(1969, 12, 31, 23, 0), datetime.datetime(1, 1, 1, 0, 0, 1),
               datetime.datetime(2026, 1, 1, 23, 59, 59, 999999), None]
    assert one(moments, pyarrow.timestamp("us"), pyarrow.date32()) == [
        datetime.date(1969, 12, 31), datetime.date(1, 1, 1), datetime.date(2026, 1, 1), None]
    assert one([datetime.date(2026, 10, 12), None], pyarrow.date32(), pyarrow.timestamp("us")) == [
        datetime.datetime(2026, 10, 12), None]
    assert one(moments, pyarrow.timestamp("us"), pyarrow.timestamp("us")) == moments
    assert one([datetime.date(9999, 12, 31)], pyarrow.date32(), pyarrow.date32()) == [datetime.date(9999, 12, 31)]


def test_a_day_as_text():
    assert one([datetime.date(1, 1, 1), datetime.date(2026, 10, 12), None], pyarrow.date32(), pyarrow.large_string()) == [
        "0001-01-01", "2026-10-12", None]


@pytest.mark.parametrize("digits, made", [
    (0, ["2026-10-12 14:03:05", "0001-01-01 00:00:00", None]),
    (3, ["2026-10-12 14:03:05.997", "0001-01-01 00:00:00.000", None]),
    (1, ["2026-10-12 14:03:05.9", "0001-01-01 00:00:00.0", None]),
    (6, ["2026-10-12 14:03:05.997123", "0001-01-01 00:00:00.000000", None]),
    # A millionth of a second is all the driver hands on of the seven digits such a column has.
    (7, ["2026-10-12 14:03:05.997123", "0001-01-01 00:00:00.000000", None]),
])
def test_a_moment_as_text_has_the_digits_after_the_second_that_its_type_has(digits, made):
    moments = [datetime.datetime(2026, 10, 12, 14, 3, 5, 997123), datetime.datetime(1, 1, 1), None]
    assert one(moments, pyarrow.timestamp("us"), pyarrow.large_string(), digits=[digits]) == made


@pytest.mark.parametrize("digits, made", [
    (0, ["14:03:05", "23:59:59", "00:00:00", None]),
    (3, ["14:03:05.120", "23:59:59.999", "00:00:00.000", None]),
    (7, ["14:03:05.1200000", "23:59:59.9999999", "00:00:00.0000001", None]),
])
def test_a_time_of_day_is_text_with_the_digits_after_the_second_that_its_type_has(digits, made):
    times = [50585120000000, 86399999999900, 100, None]
    assert one(times, pyarrow.time64("ns"), pyarrow.large_string(), digits=[digits]) == made


def test_text_is_handed_on_as_it_is_with_the_blanks_a_column_of_fixed_width_has():
    assert one(["ab    ", "", None, "caf\u00e9"], pyarrow.large_string(), pyarrow.large_string()) == ["ab    ", "", None, "caf\u00e9"]
    assert one(["x"], pyarrow.string(), pyarrow.large_string()) == ["x"]


def test_columns_are_taken_by_their_place_whatever_their_names_are():
    batch = pyarrow.record_batch([pyarrow.array([1], pyarrow.int32()), pyarrow.array([2], pyarrow.int32()),
                                  pyarrow.array(["x"], pyarrow.large_string())], names=["n", "n", ""])
    assert handed(batch, pyarrow.int64(), pyarrow.large_string(), pyarrow.large_string()) == [[1], ["2"], ["x"]]


def test_a_table_of_no_rows_keeps_its_types():
    batch = rows(n=([], pyarrow.decimal128(18, 2)), f=([], pyarrow.float64()), t=([], pyarrow.timestamp("us")))
    assert handed(batch, pyarrow.int64(), pyarrow.decimal128(38, 2), pyarrow.large_string(), digits=[0, 0, 3]) == [[], [], []]


# ------------------------------------------------------------------
# A value that does not fit what the job declares
# ------------------------------------------------------------------

@pytest.mark.parametrize("values, kind, to, said", [
    ([Decimal("1"), None, Decimal("12345678901234567890123")], pyarrow.decimal128(38, 0), pyarrow.int64(),
     "row 3 of the result: column 1 holds 12345678901234567890123, which does not fit a whole number of 64 bits"),
    ([1.0, 1e30], pyarrow.float64(), pyarrow.int64(),
     "row 2 of the result: column 1 holds 1e+30, which does not fit a whole number of 64 bits"),
    ([Decimal("123456789012345678901234567890")], pyarrow.decimal128(38, 0), pyarrow.decimal128(38, 10),
     "row 1 of the result: column 1 holds 123456789012345678901234567890, which does not fit a Decimal of 10 places "
     "(it has 38 digits in all)"),
    ([5, 10 ** 18], pyarrow.int64(), pyarrow.decimal128(38, 25),
     "row 2 of the result: column 1 holds 1000000000000000000, which does not fit a Decimal of 25 places (it has 38 "
     "digits in all)"),
    ([0.125, 1e30], pyarrow.float64(), pyarrow.decimal128(38, 10),
     "row 2 of the result: column 1 holds 1e+30, which does not fit a Decimal of 10 places (it has 38 digits in all)"),
])
def test_a_number_too_large_for_what_the_job_declares_fails_and_names_its_row(values, kind, to, said):
    with pytest.raises(DatabaseError) as failed:
        one(values, kind, to)
    assert str(failed.value) == said


def test_a_column_that_cannot_be_made_what_is_asked_for_and_whose_every_value_fits_is_said_as_it_came(monkeypatch):
    def fails(values, to, digits):
        raise pyarrow.ArrowInvalid("it would not\nbe cast")

    monkeypatch.setattr(mssql, "_made", fails)
    with pytest.raises(DatabaseError) as failed:
        mssql.as_asked(rows(a=([1, None], pyarrow.int32())), [pyarrow.int64()], [0], 0)
    assert str(failed.value) == "column 1 of the result could not be made what the job declares: it would not be cast"
    with pytest.raises(DatabaseError, match="^column 1 of the result could not be made"):
        mssql.as_asked(rows(a=([0.5, None], pyarrow.float64())), [pyarrow.decimal128(38, 2)], [0], 0)


def test_the_row_is_counted_from_the_first_of_the_result_and_the_column_by_its_place():
    batch = rows(a=([1], pyarrow.int32()), b=([1e30], pyarrow.float64()))
    with pytest.raises(DatabaseError) as failed:
        mssql.as_asked(batch, [pyarrow.int64(), pyarrow.int64()], [0, 0], 100000)
    assert str(failed.value).startswith("row 100001 of the result: column 2 holds 1e+30")


def test_a_failure_of_the_session_while_rows_are_handed_on_names_the_row_across_batches(driver):
    driver.answers["q"] = [Rows(rows(n=([1.0, 2.0, 1e30], pyarrow.float64())))]
    session, held = opened(driver)
    with pytest.raises(DatabaseError) as failed:
        list(session.batches("q", None, [pyarrow.int64()], 2))
    assert str(failed.value).startswith("row 3 of the result: column 1 holds 1e+30")
    assert held.did[-1] == "cursor closed"
