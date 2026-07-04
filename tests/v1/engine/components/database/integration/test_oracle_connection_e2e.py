"""End-to-end integration tests for tOracleConnection / OracleConnectionManager.

Phase 11-07. @pytest.mark.oracle: requires gvenzl/oracle-free:23-slim-faststart
testcontainer. Per D-D3 / D-F4: mocks lie -- this is the verification gate.

Covers VR-04: in-scope CONNECTION_TYPE values (SID, SERVICE_NAME, RAC) open
against a real Oracle instance; OCI / WALLET raise ConfigurationError without
attempting a connection.

Notes on gvenzl/oracle-free:
    - CDB SID is "FREE"
    - PDB service name is "FREEPDB1"
    - Default credentials are "test"/"test" (from container.username / .password)
"""
import pytest

from src.v1.engine.components.database.oracle_connection import OracleConnection
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.oracle_connection_manager import OracleConnectionManager


pytestmark = pytest.mark.oracle


# ----------------------------------------------------------------------
# VR-04: in-scope CONNECTION_TYPE values open against real DB
# ----------------------------------------------------------------------


class TestRealConnectionOpen:
    """VR-04: SID / SERVICE_NAME / RAC each open against a live container."""

    def test_sid(self, oracle_dsn):
        """ORACLE_SID via gvenzl/oracle-free CDB SID 'FREE'."""
        mgr = OracleConnectionManager()
        mgr.start()
        try:
            conn = mgr.open_ad_hoc("c1", {
                "connection_type": "ORACLE_SID",
                "host": oracle_dsn["host"],
                "port": str(oracle_dsn["port"]),
                "dbname": "FREE",  # CDB SID for gvenzl/oracle-free
                "user": oracle_dsn["user"],
                "password": oracle_dsn["password"],
            })
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT 1 FROM dual")
                assert cursor.fetchone()[0] == 1
            finally:
                cursor.close()
        finally:
            mgr.stop()

    def test_service_name(self, oracle_dsn):
        """ORACLE_SERVICE_NAME via FREEPDB1 PDB."""
        mgr = OracleConnectionManager()
        mgr.start()
        try:
            conn = mgr.open_ad_hoc("c1", {
                "connection_type": "ORACLE_SERVICE_NAME",
                "host": oracle_dsn["host"],
                "port": str(oracle_dsn["port"]),
                "dbname": oracle_dsn["service_name"],
                "user": oracle_dsn["user"],
                "password": oracle_dsn["password"],
            })
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT 1 FROM dual")
                assert cursor.fetchone()[0] == 1
            finally:
                cursor.close()
        finally:
            mgr.stop()

    def test_rac(self, oracle_dsn):
        """ORACLE_RAC with a single-host TNS descriptor pointing at the testcontainer."""
        tns = (
            "(DESCRIPTION="
            f"(ADDRESS=(PROTOCOL=TCP)(HOST={oracle_dsn['host']})(PORT={oracle_dsn['port']}))"
            f"(CONNECT_DATA=(SERVICE_NAME={oracle_dsn['service_name']}))"
            ")"
        )
        mgr = OracleConnectionManager()
        mgr.start()
        try:
            conn = mgr.open_ad_hoc("c1", {
                "connection_type": "ORACLE_RAC",
                "rac_url": tns,
                "user": oracle_dsn["user"],
                "password": oracle_dsn["password"],
            })
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT 1 FROM dual")
                assert cursor.fetchone()[0] == 1
            finally:
                cursor.close()
        finally:
            mgr.stop()

    def test_oci_raises_configuration_error(self):
        """ORACLE_OCI is refused with a thick-mode hint (D-A3)."""
        mgr = OracleConnectionManager()
        # Bypass start() -- we never reach a real DB call.
        mgr.is_running = True
        with pytest.raises(ConfigurationError) as exc:
            mgr.open_ad_hoc("c1", {
                "connection_type": "ORACLE_OCI",
                "user": "u", "password": "p",
                "host": "h", "dbname": "x",
            })
        msg = str(exc.value)
        assert "thick" in msg.lower()
        assert "Instant Client" in msg

    def test_wallet_raises_configuration_error(self):
        """ORACLE_WALLET is refused with a thick-mode hint (D-A3)."""
        mgr = OracleConnectionManager()
        mgr.is_running = True
        with pytest.raises(ConfigurationError) as exc:
            mgr.open_ad_hoc("c1", {
                "connection_type": "ORACLE_WALLET",
                "user": "u", "password": "p",
                "host": "h", "dbname": "x",
            })
        msg = str(exc.value)
        assert "thick" in msg.lower()


# ----------------------------------------------------------------------
# Component-level E2E (tOracleConnection -> manager.get round trip)
# ----------------------------------------------------------------------


class TestComponentLevelE2E:
    """Verify tOracleConnection.run() registers a Connection that downstream get()
    returns identically, and that no live Connection leaks into globalMap.
    """

    def test_register_and_get_round_trip(self, oracle_dsn):
        mgr = OracleConnectionManager()
        mgr.start()
        try:
            comp = OracleConnection(
                component_id="tOracleConnection_1",
                config={
                    "connection_type": "ORACLE_SERVICE_NAME",
                    "host": oracle_dsn["host"],
                    "port": str(oracle_dsn["port"]),
                    "dbname": oracle_dsn["service_name"],
                    "user": oracle_dsn["user"],
                    "password": oracle_dsn["password"],
                    "schema_db": "TEST_SCHEMA",
                },
                global_map=GlobalMap(),
                context_manager=ContextManager(),
            )
            # Skip BaseComponent.execute() lifecycle and seed config directly
            # (mirrors tests/v1/engine/components/database/test_oracle_output.py:40-46).
            comp.config = dict(comp._original_config)
            comp.oracle_manager = mgr

            comp._process(None)

            # The downstream get() returns the SAME Connection object that
            # tOracleConnection registered.
            same_conn = mgr.get("tOracleConnection_1")
            cursor = same_conn.cursor()
            try:
                cursor.execute("SELECT 1 FROM dual")
                assert cursor.fetchone()[0] == 1
            finally:
                cursor.close()
        finally:
            mgr.stop()

    def test_globalmap_metadata_strings(self, oracle_dsn):
        """Verify metadata strings are published; live Connection NOT in globalMap (D-A1)."""
        mgr = OracleConnectionManager()
        mgr.start()
        gm = GlobalMap()
        try:
            comp = OracleConnection(
                component_id="cX",
                config={
                    "connection_type": "ORACLE_SERVICE_NAME",
                    "host": oracle_dsn["host"],
                    "port": str(oracle_dsn["port"]),
                    "dbname": oracle_dsn["service_name"],
                    "user": oracle_dsn["user"],
                    "password": oracle_dsn["password"],
                    "schema_db": "TS",
                },
                global_map=gm,
                context_manager=ContextManager(),
            )
            comp.config = dict(comp._original_config)
            comp.oracle_manager = mgr
            comp._process(None)

            assert gm.get("connectionType_cX") == "ORACLE_SERVICE_NAME"
            assert gm.get("dbschema_cX") == "TS"
            assert gm.get("username_cX") == oracle_dsn["user"]

            # Live Connection MUST NOT be in globalMap (D-A1, T-11-02).
            data = gm.get_all()
            for value in data.values():
                assert not hasattr(value, "cursor"), (
                    f"Connection-like object found in globalMap: {value!r}"
                )

            # Also assert the credential is not exposed via globalMap.
            for key, value in data.items():
                if isinstance(value, str):
                    assert oracle_dsn["password"] not in value, (
                        f"Password leaked into globalMap key {key!r}"
                    )
        finally:
            mgr.stop()

    def test_auto_commit_honored_real_db(self, oracle_dsn):
        """auto_commit=True propagates to conn.autocommit on a real Connection."""
        mgr = OracleConnectionManager()
        mgr.start()
        try:
            conn = mgr.open_ad_hoc("c1", {
                "connection_type": "ORACLE_SERVICE_NAME",
                "host": oracle_dsn["host"],
                "port": str(oracle_dsn["port"]),
                "dbname": oracle_dsn["service_name"],
                "user": oracle_dsn["user"],
                "password": oracle_dsn["password"],
                "auto_commit": True,
            })
            assert conn.autocommit is True
        finally:
            mgr.stop()

    def test_engine_cleanup_closes_connection(self, oracle_dsn):
        """After mgr.stop(), the registered cid is no longer accessible via get()."""
        mgr = OracleConnectionManager()
        mgr.start()
        comp = OracleConnection(
            component_id="tOracleConnection_X",
            config={
                "connection_type": "ORACLE_SERVICE_NAME",
                "host": oracle_dsn["host"],
                "port": str(oracle_dsn["port"]),
                "dbname": oracle_dsn["service_name"],
                "user": oracle_dsn["user"],
                "password": oracle_dsn["password"],
                "schema_db": "",
            },
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        comp.config = dict(comp._original_config)
        comp.oracle_manager = mgr
        comp._process(None)

        # Sanity: get() works pre-stop
        live_conn = mgr.get("tOracleConnection_X")
        assert live_conn is not None

        mgr.stop()

        # After stop, the registry is empty and get() raises ConfigurationError.
        with pytest.raises(ConfigurationError):
            mgr.get("tOracleConnection_X")
