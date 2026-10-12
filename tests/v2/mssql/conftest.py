"""A real SQL Server, for the tests marked ``mssql``.

They are run by themselves, and are no part of the coverage gate::

    python -m pytest tests/v2/mssql -m mssql -o addopts="" -n 0

The server is one that is there already when three variables say so
(``V2_MSSQL_SERVER`` as ``host,port``, ``V2_MSSQL_USER`` and
``V2_MSSQL_PASSWORD``; the user has to be allowed to make a database).
Otherwise a container is started for the run, when ``V2_MSSQL_ACCEPT_EULA``
is ``Y``: whoever sets it accepts Microsoft's licence for the image, and
nothing here accepts it for them. It needs Docker and the
``testcontainers`` package. The image is built for Intel only: elsewhere
it runs under emulation, which Microsoft does not support.

The tests work in a database of their own, made for the run and dropped
after it. Without ``-m mssql`` no test here runs and nothing is started.
"""
import os
import secrets
import time

import pytest

IMAGE = "mcr.microsoft.com/mssql/server:2022-latest"


class Database:
    """Where the server is, who to be on it, and the database the tests work in."""

    def __init__(self, host: str, port: int, user: str, password: str, name: str = "master") -> None:
        self.host, self.port, self.user, self.password, self.name = host, port, user, password, name

    def block(self, **more):
        """A connection block for a component. The server of the tests has a certificate of its own making."""
        return {"host": self.host, "port": str(self.port), "dbname": self.name, "user": self.user,
                "password": self.password, "trust_server_certificate": True, **more}

    def connect(self, name=None):
        """A session of the plain driver: what a test looks at the database with, beside the engine."""
        import mssql_python

        if not mssql_python.PoolingManager.is_initialized():
            mssql_python.pooling(enabled=False)
        return mssql_python.connect("", autocommit=True, server=f"{self.host},{self.port}", database=name or self.name,
                                    uid=self.user, pwd=self.password, encrypt="yes", trust_server_certificate="yes")

    def rows(self, statement, *values):
        held = self.connect()
        try:
            cursor = held.cursor()
            cursor.execute(statement, list(values)) if values else cursor.execute(statement)
            return [tuple(row) for row in cursor.fetchall()]
        finally:
            held.close()

    def run(self, *statements, name=None):
        held = self.connect(name)
        try:
            for statement in statements:
                held.cursor().execute(statement)
        finally:
            held.close()


def _asked_for(config) -> bool:
    asked = config.getoption("markexpr") or ""
    return "mssql" in asked and "not mssql" not in asked


@pytest.fixture(scope="session")
def mssql_db(request):
    if not _asked_for(request.config):
        pytest.skip("a real SQL Server is used only when asked for: -m mssql")
    pytest.importorskip("mssql_python", reason="mssql-python is not installed")
    where = os.environ.get("V2_MSSQL_SERVER")
    container = None
    if where:
        host, _, port = where.partition(",")
        server = Database(host, int(port or 1433), os.environ["V2_MSSQL_USER"], os.environ["V2_MSSQL_PASSWORD"])
    elif os.environ.get("V2_MSSQL_ACCEPT_EULA") == "Y":
        container, server = _started()
    else:
        pytest.skip("no SQL Server is named (V2_MSSQL_SERVER, V2_MSSQL_USER, V2_MSSQL_PASSWORD), and none is started "
                    "unless V2_MSSQL_ACCEPT_EULA=Y says that Microsoft's licence for its image is accepted")
    try:
        _wait(server)
        made = Database(server.host, server.port, server.user, server.password, f"v2test_{secrets.token_hex(5)}")
        server.run(f"create database {made.name}")
        try:
            yield made
        finally:
            server.run(f"alter database {made.name} set single_user with rollback immediate", f"drop database {made.name}")
    finally:
        if container is not None:
            container.stop()


def _started():
    """A container of SQL Server's free edition for developers, and where it is. It is gone after the run, and its
    password with it."""
    containers = pytest.importorskip("testcontainers.core.container", reason="testcontainers is not installed")
    password = f"V2_{secrets.token_hex(8)}_a"
    try:
        container = (containers.DockerContainer(IMAGE, platform="linux/amd64", mem_limit="3g")
                     .with_env("ACCEPT_EULA", "Y").with_env("MSSQL_SA_PASSWORD", password)
                     .with_env("MSSQL_PID", "Developer").with_env("MSSQL_MEMORY_LIMIT_MB", "2048")
                     .with_exposed_ports(1433))
        container.start()
    except Exception as fault:  # noqa: BLE001 -- no Docker, no image: the tests cannot run here
        pytest.skip(f"no SQL Server container could be started: {fault}")
    return container, Database(container.get_container_host_ip(), int(container.get_exposed_port(1433)), "sa", password)


def _wait(server: Database, seconds: float = 240.0) -> None:
    """Wait until the server takes a session: a container says it is up a good while before that."""
    until, last = time.monotonic() + seconds, None
    while time.monotonic() < until:
        try:
            server.rows("select 1")
            return
        except Exception as fault:  # noqa: BLE001 -- whatever it says while it starts
            last = fault
            time.sleep(2.0)
    raise RuntimeError(f"the SQL Server took no session in {seconds:.0f}s: {last}")
