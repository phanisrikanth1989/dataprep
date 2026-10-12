"""SQL Server connection: a session opened for the SQL Server inputs of a job to read on."""
import logging

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import job
from tests.v2.database import WITH_DOES, mssql_on_sqlite  # noqa: F401 -- a fixture

BLOCK = {"host": "db.example", "port": "1433", "dbname": "sales", "schema_db": "dbo", "user": "app",
         "password": "s3cret"}
# What Talend's converter writes beside the block, with nothing changed in the Studio.
AS_CONVERTED = {"driver": "MSSQL_PROP", "encoding": "ISO-8859-15", "properties": "", "use_shared_connection": False,
                "shared_connection_name": "", "specify_datasource_alias": False, "datasource_alias": "",
                "active_dir_auth": False, "auto_commit": False, "share_identity_setting": False,
                "tstatcatcher_stats": False, "label": ""}


def connection(kind="tMSSqlConnection", component_id="tDBConnection_1", **config):
    return {"id": component_id, "type": kind, "config": {**BLOCK, **config}, "schema": {"input": [], "output": []},
            "inputs": [], "outputs": []}


def after(*ids):
    """Each component set off by the one before it."""
    return [{"type": "OnSubjobOk", "from": source, "to": target} for source, target in zip(ids, ids[1:])]


def run(components, triggers=(), **more):
    return run_job(job(components, [], triggers=list(triggers), **more), registry=WITH_DOES)


def refusals(components, flows=(), **more):
    with pytest.raises(JobRefusedError) as refused:
        load_job(job(components, list(flows), **more), registry=WITH_DOES)
    return [f"{refusal.where} / {refusal.key}: {refusal.reason}" for refusal in refused.value.report]


@pytest.mark.parametrize("kind", ["mssql_connection", "MSSqlConnection", "tMSSqlConnection"])
def test_it_opens_a_session_with_its_block_and_the_job_closes_it(mssql_on_sqlite, kind):
    result = run([connection(kind)])
    assert result.status == "success", result.error
    (config, opened_by, more), = mssql_on_sqlite.asked
    assert (opened_by, more) == ("tDBConnection_1", {})
    assert {key: config[key] for key in BLOCK} == {**BLOCK, "port": 1433}
    session, = mssql_on_sqlite.sessions
    assert session.shared and session.schema == "dbo"
    assert session.did == ["close"]


def test_what_talend_leaves_in_globalmap_is_there_and_no_password(mssql_on_sqlite):
    result = run([connection()])
    assert {key: value for key, value in result.global_map.items() if "tDBConnection_1" in key and "NB_LINE" not in key} == {
        "dbschema_tDBConnection_1": "dbo", "db_tDBConnection_1": "sales"}
    assert "s3cret" not in repr(result.global_map)


def test_the_password_is_in_no_log_line(mssql_on_sqlite, caplog):
    with caplog.at_level(logging.DEBUG, logger="src.v2"):
        run([connection()], run={"log_level": "DEBUG"})
    assert '"password": "***"' in caplog.text
    assert "s3cret" not in caplog.text


def test_a_session_that_cannot_be_opened_fails_the_job_at_the_connection(mssql_on_sqlite):
    mssql_on_sqlite.refuses = "no session was opened as app@db.example,1433/sales: Login failed for user 'app'."
    result = run([connection()])
    assert (result.status, result.failed_component, result.error) == ("failed", "tDBConnection_1", mssql_on_sqlite.refuses)


def test_a_connection_as_talends_converter_writes_one_is_taken(mssql_on_sqlite):
    result = run([connection(**AS_CONVERTED)])
    assert result.status == "success", result.error
    # Whether each statement is stored by itself is not the job's to say here: it always is.
    assert mssql_on_sqlite.asked[0][2] == {}
    assert run([connection(**{**AS_CONVERTED, "auto_commit": True, "share_identity_setting": True})]).status == "success"


def test_what_is_wrong_with_its_block_refuses_the_job_before_it_runs(mssql_on_sqlite):
    where = "component tDBConnection_1 (tMSSqlConnection)"
    assert refusals([connection(host="", password="enc:system.encryption.key.v1:AbCd", properties="domain=CORP")]) == [
        f"{where} / host: is empty; a session is opened with a host",
        f"{where} / password: is text Talend encrypted with a key of its own, which v2 cannot read; give the "
        "password itself, from a context variable (`${context.db_password}`)",
        f"{where} / properties: `domain` is a parameter of a JDBC driver that v2 has no reading for; take it out. It "
        "reads encrypt, trustServerCertificate, hostNameInCertificate, applicationIntent, multiSubnetFailover and "
        "loginTimeout",
    ]
    assert refusals([connection(active_dir_auth=True, use_shared_connection=True)]) == [
        f"{where} / active_dir_auth: v2 signs in to SQL Server with a user and a password of the database's own; "
        "signing in through Microsoft Entra was not at hand to be tried, and is not built",
        f"{where} / use_shared_connection: a session is not shared between a job and the jobs it runs: each opens "
        "its own",
    ]
    assert refusals([connection(encrypt="maybe")]) == [f"{where} / encrypt: 'maybe' is none of yes, no, strict"]
    assert mssql_on_sqlite.asked == []


def test_a_block_that_waits_for_the_context_is_judged_with_what_the_context_holds(mssql_on_sqlite):
    made = [connection(host="${context.db_host}", password="${context.db_password}", encrypt="${context.enc}")]
    context = {"Default": {"db_host": {"value": "db7", "type": "id_String"},
                           "db_password": {"value": "pw", "type": "id_Password"},
                           "enc": {"value": "no", "type": "id_String"}}}
    result = run(made, context=context)
    assert result.status == "success", result.error
    config = mssql_on_sqlite.asked[0][0]
    assert (config["host"], config["password"], config["encrypt"]) == ("db7", "pw", "no")


def test_it_takes_no_flow(mssql_on_sqlite):
    reader = {"id": "in", "type": "FixedFlowInputComponent", "config": {"nb_rows": 1, "values_config": []},
              "schema": {"input": [], "output": [{"name": "n", "type": "int"}]}, "inputs": [], "outputs": ["r"]}
    found = refusals([reader, connection()], flows=[{"name": "r", "from": "in", "to": "tDBConnection_1", "type": "flow"}])
    assert found == ["component tDBConnection_1 (tMSSqlConnection) / inputs: takes no input, but 1 flow arrives"]


def test_a_component_of_oracles_cannot_work_on_its_session(mssql_on_sqlite):
    commit = {"id": "c", "type": "tOracleCommit", "config": {"connection": "tDBConnection_1"}, "inputs": [], "outputs": []}
    assert refusals([connection(), commit]) == [
        "component c (tOracleCommit) / connection: 'tDBConnection_1' (tMSSqlConnection) is no Oracle connection; the "
        "job has none"]


def test_what_v1_says_of_sql_server_at_the_top_of_a_job_is_read_and_changes_nothing(mssql_on_sqlite):
    assert run([connection()], mssql_config={"enabled": True}).status == "success"
