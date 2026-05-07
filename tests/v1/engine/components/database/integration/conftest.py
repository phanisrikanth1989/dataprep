"""Test fixtures for Oracle integration tests (Phase 11-07).

Per CONTEXT.md D-D3 / D-F4: real-DB validation is MANDATORY before Phase 11 is
verified. Mocks of oracledb.Cursor / Connection cannot demonstrate Talend parity
(wire protocol, type round-trip, BatchError offset accuracy, NULL handling, DDL
syntactic validity).

Fixtures:
    oracle_container          -- session-scoped gvenzl/oracle-free:23-slim-faststart
    oracle_dsn                -- per-test dict for oracledb.connect(**dsn)
    oracle_connection         -- per-test live Connection (auto-closed)
    temp_table                -- per-test unique table name with auto-DROP teardown
    job_config_oracle_overrides -- helper dict for sample-driven E2E mutations

Skip behavior:
    - testcontainers not installed -> pytest.skip()
    - SKIP_ORACLE_CONTAINER env var set -> pytest.skip()
    - Docker not running -> testcontainers raises -> pytest.skip()
"""
import os
import secrets
import time

import pytest

# Skip the entire module if testcontainers is not installed (mirror of
# tests/integration/conftest.py:62-66 skip-on-missing-resource pattern).
testcontainers = pytest.importorskip(
    "testcontainers",
    reason="testcontainers not installed; pip install -e '.[dev]'",
)

try:
    from testcontainers.oracle import OracleDbContainer  # type: ignore
except ImportError:
    OracleDbContainer = None


@pytest.fixture(scope="session")
def oracle_container():
    """Session-scoped Oracle Free container.

    Boots once for the whole `pytest -m oracle` run. ~15-30s cold start
    (faststart variant). Skipped when testcontainers / Docker unavailable
    or when SKIP_ORACLE_CONTAINER=1 is set in the environment.
    """
    if OracleDbContainer is None:
        pytest.skip("testcontainers.oracle not available")
    if os.environ.get("SKIP_ORACLE_CONTAINER"):
        pytest.skip("Oracle container disabled via SKIP_ORACLE_CONTAINER env var")

    try:
        container = OracleDbContainer("gvenzl/oracle-free:23-slim-faststart")
        container.start()
    except Exception as e:
        pytest.skip(f"Cannot start Oracle testcontainer (Docker not running?): {e}")

    try:
        # Health probe: poll SELECT 1 FROM dual until success or timeout.
        import oracledb
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(1521))
        user = container.username
        password = container.password
        last_err = None
        healthy = False
        for _attempt in range(60):
            try:
                conn = oracledb.connect(
                    user=user, password=password,
                    host=host, port=port, service_name="FREEPDB1",
                )
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM dual")
                cursor.fetchone()
                cursor.close()
                conn.close()
                healthy = True
                break
            except Exception as e:  # noqa: BLE001 - probing transient errors
                last_err = e
                time.sleep(1)
        if not healthy:
            pytest.fail(
                f"Oracle testcontainer did not become healthy within 60s; "
                f"last error: {last_err!r}"
            )
        yield container
    finally:
        try:
            container.stop()
        except Exception:  # noqa: BLE001 - cleanup must not mask test errors
            pass


@pytest.fixture
def oracle_dsn(oracle_container):
    """Per-test DSN dict for opening connections."""
    return {
        "user": oracle_container.username,
        "password": oracle_container.password,
        "host": oracle_container.get_container_host_ip(),
        "port": int(oracle_container.get_exposed_port(1521)),
        "service_name": "FREEPDB1",
    }


@pytest.fixture
def oracle_connection(oracle_dsn):
    """Per-test live Oracle Connection. Auto-closed."""
    import oracledb
    conn = oracledb.connect(
        user=oracle_dsn["user"],
        password=oracle_dsn["password"],
        host=oracle_dsn["host"],
        port=oracle_dsn["port"],
        service_name=oracle_dsn["service_name"],
    )
    yield conn
    try:
        conn.close()
    except Exception:  # noqa: BLE001 - cleanup must not mask test errors
        pass


@pytest.fixture
def temp_table(oracle_connection):
    """Unique-named test table; DROP on teardown.

    Avoids container-restart-per-test (which would push integration test wall
    time into hours). Uses secrets.token_hex(4) for a unique 8-char suffix.
    """
    name = f"PYTEST_T_{secrets.token_hex(4).upper()}"
    yield name
    cursor = oracle_connection.cursor()
    try:
        cursor.execute(f'DROP TABLE "{name}" PURGE')
    except Exception:  # noqa: BLE001 - table may not exist if test failed early
        pass
    finally:
        try:
            cursor.close()
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
def job_config_oracle_overrides(oracle_dsn):
    """Convenience helper for sample-driven E2E tests.

    Returns a dict suitable for the test_oracle_phase11_samples_e2e mutator to
    inject testcontainer credentials into a converted job config JSON.
    """
    return {
        "host": oracle_dsn["host"],
        "port": str(oracle_dsn["port"]),
        "dbname": oracle_dsn["service_name"],
        "user": oracle_dsn["user"],
        "password": oracle_dsn["password"],
        "connection_type": "ORACLE_SERVICE_NAME",
    }
