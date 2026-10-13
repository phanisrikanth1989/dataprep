"""Oracle connection: a session opened for other components to work on."""
import logging

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import job
from tests.v2.database import WITH_DOES, on_sqlite  # noqa: F401 -- a fixture

BLOCK = {"connection_type": "ORACLE_SERVICE_NAME", "host": "db.example", "port": "1521", "dbname": "SALES",
         "schema_db": "HR", "user": "app", "password": "s3cret"}


def connection(kind="tOracleConnection", component_id="tDBConnection_1", **config):
    return {"id": component_id, "type": kind, "config": {**BLOCK, **config}, "schema": {"input": [], "output": []},
            "inputs": [], "outputs": []}


def does(value, component_id="d", **config):
    made = {"connection": "tDBConnection_1", "statement": f"insert into t values ({value})", **config}
    return {"id": component_id, "type": "does", "config": made, "inputs": [], "outputs": []}


def after(*ids):
    """Each component set off by the one before it."""
    return [{"type": "OnSubjobOk", "from": source, "to": target} for source, target in zip(ids, ids[1:])]


def run(components, triggers=(), **more):
    return run_job(job(components, [], triggers=list(triggers), **more), registry=WITH_DOES)


def refusals(components, flows=(), **more):
    with pytest.raises(JobRefusedError) as refused:
        load_job(job(components, list(flows), **more), registry=WITH_DOES)
    return [f"{refusal.where} / {refusal.key}: {refusal.reason}" for refusal in refused.value.report]


@pytest.mark.parametrize("kind", ["oracle_connection", "OracleConnection", "tOracleConnection", "tDBConnection"])
def test_it_opens_a_session_with_its_block_and_the_job_closes_it(on_sqlite, kind):
    result = run([connection(kind)])
    assert result.status == "success"
    (config, opened_by, job_name, settings, more), = on_sqlite.asked
    assert (opened_by, job_name, settings, more) == ("tDBConnection_1", "t", {}, {"auto_commit": False})
    assert {key: config[key] for key in BLOCK} == {**BLOCK, "port": 1521}
    session, = on_sqlite.sessions
    assert session.shared and session.schema == "HR"
    assert session.did == ["close"]


def test_what_talend_leaves_in_globalmap_is_there_and_no_password(on_sqlite):
    result = run([connection()])
    assert {key: value for key, value in result.global_map.items() if "tDBConnection_1" in key and "NB_LINE" not in key} == {
        "connectionType_tDBConnection_1": "ORACLE_SERVICE_NAME", "dbschema_tDBConnection_1": "HR",
        "username_tDBConnection_1": "app", "host_tDBConnection_1": "db.example", "port_tDBConnection_1": "1521",
        "dbname_tDBConnection_1": "SALES",
    }
    assert "s3cret" not in repr(result.global_map)


def test_a_connect_string_and_a_name_of_tnsnames_are_left_in_globalmap_under_talends_names(on_sqlite):
    result = run([connection(connection_type="ORACLE_RAC", rac_url="jdbc:oracle:thin:@//scan:1522/S")])
    assert result.global_map["rac_url_tDBConnection_1"] == "jdbc:oracle:thin:@//scan:1522/S"
    assert "host_tDBConnection_1" not in result.global_map
    result = run([connection(connection_type="ORACLE_OCI", local_service_name="SALES")])
    assert result.global_map["localServiceName_tDBConnection_1"] == "SALES"
    assert "rac_url_tDBConnection_1" not in result.global_map


def test_the_password_is_in_no_log_line(on_sqlite, caplog):
    with caplog.at_level(logging.DEBUG, logger="src.v2"):
        run([connection()], run={"log_level": "DEBUG"})
    assert '"password": "***"' in caplog.text
    assert "s3cret" not in caplog.text


def test_a_session_that_cannot_be_opened_fails_the_job_at_the_connection(on_sqlite):
    on_sqlite.refuses = "no session was opened as app@db.example:1521/SALES: ORA-12541: no listener"
    result = run([connection()])
    assert (result.status, result.failed_component, result.error) == ("failed", "tDBConnection_1", on_sqlite.refuses)


def test_it_may_have_its_session_stored_after_each_subjob(on_sqlite):
    result = run([connection(auto_commit=True), does(1)], after("tDBConnection_1", "d"))
    assert result.status == "success"
    assert on_sqlite.asked[0][4] == {"auto_commit": True}
    assert on_sqlite.stored() == [(1,)]


def test_without_that_its_session_waits_for_a_commit(on_sqlite):
    result = run([connection(), does(1)], after("tDBConnection_1", "d"))
    assert (result.status, result.failed_component) == ("failed", "tDBConnection_1")
    assert on_sqlite.stored() == []


def test_the_job_says_how_oracle_sessions_are_opened(on_sqlite):
    run([connection()], oracle_config={"enabled": True, "thick_mode": True, "lib_dir": "/opt/oracle"})
    assert on_sqlite.asked[0][3] == {"thick_mode": True, "lib_dir": "/opt/oracle"}


def test_a_setting_of_the_job_that_v2_does_not_know_is_refused(on_sqlite):
    assert refusals([connection()], oracle_config={"thick": True}) == [
        "job / oracle_config.thick: unknown config key"
    ]
    assert refusals([connection()], oracle_config={"thick_mode": "yes"}) == [
        "job / oracle_config.thick_mode: expected true or false, got 'yes'"
    ]


def test_what_is_wrong_with_its_block_refuses_the_job_before_it_runs(on_sqlite):
    where = "component tDBConnection_1 (tOracleConnection)"
    assert refusals([connection(host="", password="enc:system.encryption.key.v1:AbCd")]) == [
        f"{where} / host: is empty; a session is opened with a host and a service name",
        f"{where} / password: is text Talend encrypted with a key of its own, which v2 cannot read; give the "
        "password itself, from a context variable (`${context.db_password}`)",
    ]
    assert refusals([connection(use_ssl=True)]) == [
        f"{where} / use_ssl: Java key stores are not read; a `rac_url` that says `tcps` opens a session over TLS, "
        "with the server's certificate in the system's store",
    ]
    assert on_sqlite.asked == []


def test_a_block_that_waits_for_the_context_is_judged_with_what_the_context_holds(on_sqlite):
    made = [connection(host="${context.db_host}", password="${context.db_password}")]
    context = {"Default": {"db_host": {"value": "db7", "type": "id_String"}, "db_password": {"value": "pw", "type": "id_Password"}}}
    result = run(made, context=context)
    assert result.status == "success"
    assert (on_sqlite.asked[0][0]["host"], on_sqlite.asked[0][0]["password"]) == ("db7", "pw")


def test_it_takes_no_flow(on_sqlite):
    reader = {"id": "in", "type": "FixedFlowInputComponent", "config": {"nb_rows": 1, "values_config": []},
              "schema": {"input": [], "output": [{"name": "n", "type": "int"}]}, "inputs": [], "outputs": ["r"]}
    found = refusals([reader, connection()], flows=[{"name": "r", "from": "in", "to": "tDBConnection_1", "type": "flow"}])
    assert found == ["component tDBConnection_1 (tOracleConnection) / inputs: takes no input, but 1 flow arrives"]
