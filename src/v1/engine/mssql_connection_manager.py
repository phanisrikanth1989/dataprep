"""MSSql Connection Manager - manages pyodbc.Connection lifecycle per job.

Structural twin of OracleConnectionManager (see oracle_connection_manager.py).
Live pyodbc.Connection objects MUST NOT enter globalMap (non-Arrow-serializable
per the Phase 2 sync contract); they live here keyed by the registering
component id (e.g. "tMSSqlConnection_1") plus optional ad-hoc connections opened
by tMSSqlInput when use_existing_connection=False.

stop() is idempotent and called from ETLEngine._cleanup() (success, exception,
__del__ paths), so connection leaks are impossible.

pyodbc is imported lazily so the SQL Server dependency stays optional for jobs
that use no MSSql components. ASCII-only logging; no password ever logged
(T-11-02 mitigation).
"""
import logging
from typing import Any, Dict

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Default ODBC driver name. Talend's DRIVER param ("MSSQL_PROP") is a JDBC
# selector, not an ODBC driver, so it is ignored; operators may override the
# real ODBC driver via the component config key 'odbc_driver'.
_DEFAULT_ODBC_DRIVER = "ODBC Driver 17 for SQL Server"


class MSSqlConnectionManager:
    """Owns lifecycle of all live pyodbc.Connection objects for a job.

    Mirrors the OracleConnectionManager shape: start/stop are idempotent, the
    public API is small and deterministic, and the pyodbc import is lazy.

    Attributes:
        connections: Dict mapping component_id -> pyodbc.Connection.
        is_running: True after start() and before stop().
    """

    def __init__(self) -> None:
        """Initialize the manager."""
        self.connections: Dict[str, Any] = {}  # cid -> pyodbc.Connection
        self.is_running: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Verify the pyodbc driver is importable and mark running. Idempotent."""
        if self.is_running:
            return
        import pyodbc  # noqa: F401  lazy: keeps the mssql dependency optional
        self.is_running = True
        logger.info("[OK] MSSqlConnectionManager started")

    def stop(self) -> None:
        """Close all live connections. Idempotent. Called from ETLEngine._cleanup."""
        if not self.is_running and not self.connections:
            return
        for cid, conn in list(self.connections.items()):
            try:
                conn.close()
                logger.info("[OK] Closed MSSql connection (cid=%s)", cid)
            except Exception as e:
                logger.error(
                    "[ERROR] Failed to close MSSql connection cid=%s: %s", cid, e
                )
        self.connections.clear()
        self.is_running = False

    # ------------------------------------------------------------------
    # Registry: registered (tMSSqlConnection-owned) connections
    # ------------------------------------------------------------------

    def register(self, cid: str, conn: Any) -> None:
        """Register a connection opened by tMSSqlConnection under its component id.

        Raises:
            ValueError: If cid already registered (component executed twice).
        """
        if cid in self.connections:
            raise ValueError(f"Connection already registered for cid={cid}")
        self.connections[cid] = conn
        logger.info("[OK] Registered MSSql connection (cid=%s)", cid)

    def get(self, cid_ref: str) -> Any:
        """Look up a registered connection by the cid a downstream component refs.

        Raises:
            ConfigurationError: If cid_ref is not registered (upstream
                tMSSqlConnection did not run, or connection_ref typo).
        """
        conn = self.connections.get(cid_ref)
        if conn is None:
            raise ConfigurationError(
                f"No registered MSSql connection for reference {cid_ref!r}. "
                f"Available: {sorted(self.connections.keys())}"
            )
        return conn

    # ------------------------------------------------------------------
    # Ad-hoc connections
    # ------------------------------------------------------------------

    def open_ad_hoc(self, cid: str, config: Dict[str, Any]) -> Any:
        """Open an ad-hoc connection for a component without a tMSSqlConnection ref.

        Args:
            cid: Component id of the component opening the ad-hoc connection.
            config: Dict with keys host, port, dbname, user, password,
                active_dir_auth, auto_commit, and optional odbc_driver.

        Returns:
            The newly opened pyodbc.Connection (also stored in self.connections).

        Raises:
            ValueError: If cid already has an open connection.
        """
        import pyodbc
        if cid in self.connections:
            raise ValueError(f"cid {cid!r} already has an open connection")
        conn_str = self._build_connection_string(config)
        auto_commit = bool(config.get("auto_commit", False))
        # T-11-02: never log conn_str (embeds password).
        conn = pyodbc.connect(conn_str, autocommit=auto_commit)
        self.connections[cid] = conn
        logger.info("[OK] Opened ad-hoc MSSql connection cid=%s", cid)
        return conn

    # ------------------------------------------------------------------
    # Connection string builder (T-11-02: result NEVER logged)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_connection_string(config: Dict[str, Any]) -> str:
        """Build a pyodbc connection string from component config.

        SERVER uses the ``host,port`` form SQL Server expects. When
        active_dir_auth is set, Azure AD password auth is requested; otherwise
        UID/PWD SQL auth is used.
        """
        driver = config.get("odbc_driver") or _DEFAULT_ODBC_DRIVER
        host = config.get("host", "")
        port = config.get("port", "1433")
        dbname = config.get("dbname", "")
        server = f"{host},{port}" if port else host
        parts = [
            f"DRIVER={{{driver}}}",
            f"SERVER={server}",
            f"DATABASE={dbname}",
        ]
        if config.get("active_dir_auth", False):
            parts.append("Authentication=ActiveDirectoryPassword")
        parts.append(f"UID={config.get('user', '')}")
        parts.append(f"PWD={config.get('password', '')}")
        return ";".join(parts) + ";"

    # ------------------------------------------------------------------
    # Per-connection control
    # ------------------------------------------------------------------

    def close(self, cid: str) -> None:
        """Explicit close. Removes from dict. Silent no-op for missing cid."""
        conn = self.connections.pop(cid, None)
        if conn is None:
            return
        try:
            conn.close()
            logger.info("[OK] Closed MSSql connection cid=%s", cid)
        except Exception as e:
            logger.error("[ERROR] Error closing connection cid=%s: %s", cid, e)

    def commit(self, cid: str) -> None:
        """Commit a registered connection.

        Raises:
            ConfigurationError: If cid is not registered.
        """
        self.get(cid).commit()

    def rollback(self, cid: str) -> None:
        """Rollback a registered connection.

        Raises:
            ConfigurationError: If cid is not registered.
        """
        self.get(cid).rollback()

    # ------------------------------------------------------------------
    # Status + context manager + repr
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if start() has been called and stop() has not."""
        return self.is_running

    def __enter__(self) -> "MSSqlConnectionManager":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit."""
        self.stop()
        return False

    def __repr__(self) -> str:
        """T-11-02: connection count only, never connection details."""
        status = "running" if self.is_running else "stopped"
        return (
            f"MSSqlConnectionManager(status={status}, "
            f"connections={len(self.connections)})"
        )
