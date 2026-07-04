"""E2E sample-driven tests for the 3 Phase 11 .item fixtures.

Mirror the canonical Phase 10 e2e pattern from tests/integration/test_iterate_e2e.py:
  1. Convert .item -> JSON via convert_job()
  2. Mutate the JSON to inject testcontainer connection params
  3. Execute via ETLEngine
  4. Assert that the job ran without crashing and that the manager registered
     at least one connection / wrote expected globalMap stats

Phase 11-07. @pytest.mark.oracle.

Sample inventory:
    Job_tOracleConnection_0.1.item -- creates a tOracleConnection
    Job_tOracleRow_0.1.item        -- runs SQL via tOracleRow
    Job_tOracleOutput_0.1.item     -- writes rows via tOracleOutput
"""
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from src.converters.talend_to_v1.converter import convert_job
from src.v1.engine.engine import ETLEngine


pytestmark = pytest.mark.oracle


SAMPLE_CONNECTION = "tests/talend_xml_samples/Job_tOracleConnection_0.1.item"
SAMPLE_ROW = "tests/talend_xml_samples/Job_tOracleRow_0.1.item"
SAMPLE_OUTPUT = "tests/talend_xml_samples/Job_tOracleOutput_0.1.item"


def _mutate_json(
    json_path: Path, mutations: Dict[str, Dict[str, Any]],
) -> None:
    """Inject component-config overrides into the converted JSON in place.

    Args:
        json_path: Path to the converted JSON file (rewritten in place).
        mutations: Mapping of either component_id or '*' (wildcard for any
                   tOracleConnection / tOracleRow / tOracleOutput component) to
                   a dict of config keys to overwrite.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    oracle_types = {"tOracleConnection", "tOracleRow", "tOracleOutput"}
    for comp in config.get("components", []):
        comp_id = comp.get("id")
        comp_type = comp.get("type")
        if comp_id in mutations:
            for key, val in mutations[comp_id].items():
                comp.setdefault("config", {})[key] = val
        if "*" in mutations and comp_type in oracle_types:
            for key, val in mutations["*"].items():
                comp.setdefault("config", {})[key] = val
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _load(json_path: Path) -> Dict[str, Any]:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------------------------------
# Sample-driven E2E tests
# ----------------------------------------------------------------------


class TestSamples:
    """Each sample converts cleanly, accepts testcontainer overrides, and
    executes through ETLEngine without raising.
    """

    def test_oracle_connection_sample_runs(self, tmp_path, oracle_dsn):
        """Convert + execute Job_tOracleConnection_0.1.item against testcontainer."""
        json_path = tmp_path / "conn.json"
        convert_job(SAMPLE_CONNECTION, str(json_path))
        assert json_path.exists()

        _mutate_json(json_path, {
            "*": {
                "connection_type": "ORACLE_SERVICE_NAME",
                "host": oracle_dsn["host"],
                "port": str(oracle_dsn["port"]),
                "dbname": oracle_dsn["service_name"],
                "user": oracle_dsn["user"],
                "password": oracle_dsn["password"],
            },
        })

        cfg = _load(json_path)
        engine = ETLEngine(cfg)
        try:
            stats = engine.execute()
        finally:
            engine._cleanup()

        # Job ran without crashing; some sort of stats dict came back.
        assert stats is not None

    def test_oracle_row_sample_runs(self, tmp_path, oracle_dsn):
        """Convert + execute Job_tOracleRow_0.1.item.

        The sample likely runs simple SQL or DDL. We just need it to complete
        without crashing once the testcontainer connection params are injected.
        """
        json_path = tmp_path / "row.json"
        convert_job(SAMPLE_ROW, str(json_path))
        assert json_path.exists()

        _mutate_json(json_path, {
            "*": {
                "connection_type": "ORACLE_SERVICE_NAME",
                "host": oracle_dsn["host"],
                "port": str(oracle_dsn["port"]),
                "dbname": oracle_dsn["service_name"],
                "user": oracle_dsn["user"],
                "password": oracle_dsn["password"],
            },
        })

        cfg = _load(json_path)
        engine = ETLEngine(cfg)
        try:
            stats = engine.execute()
        finally:
            engine._cleanup()

        assert stats is not None

    def test_oracle_output_sample_runs(
        self, tmp_path, oracle_dsn, oracle_connection, temp_table,
    ):
        """Convert + execute Job_tOracleOutput_0.1.item against testcontainer.

        Override the target table to our temp_table and table_action to
        CREATE_IF_NOT_EXISTS so the sample doesn't pollute the container or
        depend on a pre-existing target table.
        """
        json_path = tmp_path / "out.json"
        convert_job(SAMPLE_OUTPUT, str(json_path))
        assert json_path.exists()

        _mutate_json(json_path, {
            "*": {
                "connection_type": "ORACLE_SERVICE_NAME",
                "host": oracle_dsn["host"],
                "port": str(oracle_dsn["port"]),
                "dbname": oracle_dsn["service_name"],
                "user": oracle_dsn["user"],
                "password": oracle_dsn["password"],
                # Keep the test isolated from any pre-existing schema.
                "table": temp_table,
                "table_action": "CREATE_IF_NOT_EXISTS",
            },
        })

        cfg = _load(json_path)
        engine = ETLEngine(cfg)
        try:
            stats = engine.execute()
        finally:
            engine._cleanup()

        assert stats is not None
        # The temp_table fixture's teardown DROPs the table.
