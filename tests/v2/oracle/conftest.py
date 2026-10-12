"""A real Oracle, for the tests marked ``oracle``.

They are run by themselves, and are no part of the coverage gate::

    python -m pytest tests/v2/oracle -m oracle -o addopts="" -n 0

The database is one that is there already when three variables say so
(``V2_ORACLE_DSN`` as ``host:port/service``, ``V2_ORACLE_USER`` and
``V2_ORACLE_PASSWORD``), and otherwise a container that is started for the
run (Docker, and the ``testcontainers`` package). Without ``-m oracle`` no
test here runs and nothing is started.

With ``V2_ORACLE_THICK=1`` every session of the run is one of Oracle's own
client (python-oracledb's thick mode), which has to be installed;
``V2_ORACLE_LIB_DIR`` names its folder where it is not found by itself. A
process is in one mode or the other, so the whole run is.
"""
import os
import secrets
import time

import pytest

IMAGE = "gvenzl/oracle-free:23-slim-faststart"


class Database:
    """Where the database is, and who to be in it."""

    def __init__(self, host: str, port: int, service: str, user: str, password: str) -> None:
        self.host, self.port, self.service, self.user, self.password = host, port, service, user, password

    def block(self, **more):
        """A connection block for a component, by service name."""
        return {"connection_type": "ORACLE_SERVICE_NAME", "host": self.host, "port": str(self.port),
                "dbname": self.service, "user": self.user, "password": self.password, **more}

    def connect(self):
        """A session of the plain driver: what a test looks at the database with, beside the engine."""
        import oracledb
        return oracledb.connect(user=self.user, password=self.password, host=self.host, port=self.port,
                                service_name=self.service)

    def rows(self, statement, **binds):
        with self.connect() as held, held.cursor() as cursor:
            cursor.execute(statement, binds)
            return cursor.fetchall()


def _asked_for(config) -> bool:
    asked = config.getoption("markexpr") or ""
    return "oracle" in asked and "not oracle" not in asked


@pytest.fixture(scope="session")
def oracle_db(request):
    if not _asked_for(request.config):
        pytest.skip("a real Oracle is used only when asked for: -m oracle")
    driver = pytest.importorskip("oracledb", reason="python-oracledb is not installed")
    if os.environ.get("V2_ORACLE_THICK"):
        folder = os.environ.get("V2_ORACLE_LIB_DIR")
        driver.init_oracle_client(**({"lib_dir": folder} if folder else {}))
    where = os.environ.get("V2_ORACLE_DSN")
    if where:
        host, _, rest = where.partition(":")
        port, _, service = rest.partition("/")
        yield Database(host, int(port), service, os.environ["V2_ORACLE_USER"], os.environ["V2_ORACLE_PASSWORD"])
        return
    try:
        from testcontainers.community import oracle as containers
    except ImportError:
        # Where the package keeps it in releases before it was moved.
        containers = pytest.importorskip("testcontainers.oracle", reason="testcontainers is not installed")
    try:
        # A user of the tests' own, in the database the image makes (FREEPDB1). The container is gone after the run,
        # and its password with it.
        container = containers.OracleDbContainer(IMAGE, username="v2test", password=f"v2_{secrets.token_hex(8)}")
        container.start()
    except Exception as fault:  # noqa: BLE001 -- no Docker, no image: the tests cannot run here
        pytest.skip(f"no Oracle container could be started: {fault}")
    try:
        made = Database(container.get_container_host_ip(), int(container.get_exposed_port(1521)), "FREEPDB1",
                        container.username, container.password)
        _wait(made)
        yield made
    finally:
        container.stop()


def _wait(database: Database, seconds: float = 180.0) -> None:
    """Wait until the database takes a session: the container says it is up a little before that."""
    until, last = time.monotonic() + seconds, None
    while time.monotonic() < until:
        try:
            database.rows("select 1 from dual")
            return
        except Exception as fault:  # noqa: BLE001 -- whatever it says while it starts
            last = fault
            time.sleep(1.0)
    raise RuntimeError(f"the Oracle container took no session in {seconds:.0f}s: {last}")


@pytest.fixture
def table(oracle_db):
    """The name of a table of this test's own, ``(n number, v varchar2(20))``, dropped afterwards."""
    name = f"V2T_{secrets.token_hex(5).upper()}"
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"create table {name} (n number, v varchar2(20))")
    yield name
    with oracle_db.connect() as held, held.cursor() as cursor:
        cursor.execute(f"drop table {name} purge")
