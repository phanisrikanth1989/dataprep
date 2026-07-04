"""Oracle Connection Manager - Manages oracledb.Connection lifecycle per job.

Mirrors JavaBridgeManager / PythonRoutineManager. Live oracledb.Connection
objects MUST NOT enter globalMap (non-Arrow-serializable per Phase 2 sync
contract); they live here keyed by the registering component id (e.g.
"tOracleConnection_1") plus optional ad-hoc connections opened by tOracleRow /
tOracleOutput when use_existing_connection=False.

Per D-A4b: stop() is idempotent and called from ETLEngine._cleanup() (success,
exception, __del__ paths). Connection leaks are impossible.

ASCII-only logging (D-H7). No password ever logged (T-11-02 mitigation).
"""
import logging
from typing import Any, Dict

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class OracleConnectionManager:
    """Owns lifecycle of all live oracledb.Connection objects for a job.

    Mirrors the JavaBridgeManager shape: start/stop are idempotent, public
    API is small and deterministic, lazy import of oracledb keeps the
    `oracle` extra optional.

    Attributes:
        thick_mode: Whether thick mode is enabled (read from
            job_config['oracle_config']['thick_mode']).
        connections: Dict mapping component_id -> oracledb.Connection.
        is_running: True after start() and before stop().
    """

    # Class-level guard: oracledb.init_oracle_client() is process-global;
    # calling it twice raises. Track init across all instances in this process.
    _thick_initialized: bool = False

    def __init__(self, thick_mode: bool = False) -> None:
        """Initialize the manager.

        Args:
            thick_mode: If True, start() will call oracledb.init_oracle_client()
                once per process via the class-level _thick_initialized guard.
        """
        self.thick_mode: bool = bool(thick_mode)
        self.connections: Dict[str, Any] = {}  # cid -> oracledb.Connection
        self.is_running: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialize driver mode. Idempotent.

        - Sets oracledb.defaults.fetch_lobs = False (D-B1) so CLOB/BLOB read
          as str/bytes.
        - If thick_mode True and not yet initialized in this process, calls
          oracledb.init_oracle_client().
        - Marks is_running True.
        """
        if self.is_running:
            return
        import oracledb  # lazy: keeps the oracle extra optional
        oracledb.defaults.fetch_lobs = False  # D-B1
        if self.thick_mode and not OracleConnectionManager._thick_initialized:
            try:
                oracledb.init_oracle_client()
                OracleConnectionManager._thick_initialized = True
                logger.info("[OK] Oracle thick mode initialized")
            except Exception as e:
                logger.error("[ERROR] oracledb.init_oracle_client() failed: %s", e)
                raise
        self.is_running = True
        logger.info("[OK] OracleConnectionManager started (thick_mode=%s)", self.thick_mode)

    def stop(self) -> None:
        """Close all live connections. Idempotent. Called from ETLEngine._cleanup.

        Iterates self.connections and closes each in try/except so one bad close
        does not block the rest. Clears the dict. Sets is_running False.
        """
        if not self.is_running and not self.connections:
            return
        for cid, conn in list(self.connections.items()):
            try:
                conn.close()
                logger.info("[OK] Closed Oracle connection (cid=%s)", cid)
            except Exception as e:
                logger.error("[ERROR] Failed to close Oracle connection cid=%s: %s", cid, e)
        self.connections.clear()
        self.is_running = False

    # ------------------------------------------------------------------
    # Registry: registered (tOracleConnection-owned) connections
    # ------------------------------------------------------------------

    def register(self, cid: str, conn: Any) -> None:
        """Register a connection opened by tOracleConnection under its component id.

        Args:
            cid: Component id of the upstream tOracleConnection.
            conn: Live oracledb.Connection object.

        Raises:
            ValueError: If cid already registered (component executed twice).
        """
        if cid in self.connections:
            raise ValueError(f"Connection already registered for cid={cid}")
        self.connections[cid] = conn
        logger.info("[OK] Registered Oracle connection (cid=%s)", cid)

    def get(self, cid_ref: str) -> Any:
        """Look up a registered connection by the cid the downstream component refs.

        Args:
            cid_ref: Component id referenced by use_existing_connection=true
                downstream component (tOracleRow/tOracleOutput).

        Returns:
            The registered oracledb.Connection.

        Raises:
            ConfigurationError: If cid_ref is not registered (upstream
                tOracleConnection did not run, or connection_ref typo in
                job config).
        """
        conn = self.connections.get(cid_ref)
        if conn is None:
            raise ConfigurationError(
                f"No registered Oracle connection for reference {cid_ref!r}. "
                f"Available: {sorted(self.connections.keys())}"
            )
        return conn

    # ------------------------------------------------------------------
    # Ad-hoc: open connections for components that don't reference a tOracleConnection
    # ------------------------------------------------------------------

    def open_ad_hoc(self, cid: str, oracle_config: Dict[str, Any]) -> Any:
        """Open an ad-hoc connection for a component that didn't refer to a
        tOracleConnection.

        The component is expected to call self.oracle_manager.close(cid) in its
        finalize step (or rely on stop() safety net at engine cleanup).

        Args:
            cid: Component id of the component opening the ad-hoc connection.
            oracle_config: Dict with keys: connection_type, host, port, dbname,
                local_service_name, rac_url, user, password, auto_commit.

        Returns:
            The newly opened oracledb.Connection (also stored in self.connections).

        Raises:
            ConfigurationError: For unsupported connection types (OCI, Wallet)
                per D-A3, or for unknown connection_type.
            ValueError: If cid already has an open connection.
        """
        import oracledb
        if cid in self.connections:
            raise ValueError(f"cid {cid!r} already has an open connection")
        ct = oracle_config.get("connection_type", "ORACLE_SID")
        if ct in ("ORACLE_OCI", "ORACLE_WALLET"):
            # T-11-05 mitigation: do NOT include any wallet path or auth detail
            # in the message; the wording below is locked to D-A3.
            raise ConfigurationError(
                f"CONNECTION_TYPE {ct!r} requires oracledb thick mode + Oracle "
                f"Instant Client. Set oracle_config.thick_mode=true in job config "
                f"and install Instant Client on the host. Tracked in deferred items."
            )
        if ct == "ORACLE_SID":
            kwargs = self._build_sid_kwargs(oracle_config)
        elif ct == "ORACLE_SERVICE_NAME":
            kwargs = self._build_service_name_kwargs(oracle_config)
        elif ct == "ORACLE_RAC":
            kwargs = self._build_rac_kwargs(oracle_config)
        else:
            # WR-07: list ONLY the values open_ad_hoc actually accepts. The
            # branch above already refuses ORACLE_OCI / ORACLE_WALLET with a
            # dedicated ConfigurationError; including them in this "must be
            # one of" message misled operators into thinking those types
            # were valid alternatives to try.
            raise ConfigurationError(
                f"Unknown connection_type {ct!r}. Must be one of: "
                f"{{'ORACLE_SID', 'ORACLE_SERVICE_NAME', 'ORACLE_RAC'}} "
                f"(OCI/WALLET require thick mode + Oracle Instant Client; "
                f"tracked in deferred items)"
            )
        conn = oracledb.connect(**kwargs)
        if oracle_config.get("auto_commit", False):
            conn.autocommit = True
        self.connections[cid] = conn
        # T-11-02 mitigation: log only cid + connection_type, NEVER kwargs (PASS leaks)
        logger.info("[OK] Opened ad-hoc Oracle connection cid=%s type=%s", cid, ct)
        return conn

    # ------------------------------------------------------------------
    # Connection-type kwargs builders (T-11-02: kwargs dict NEVER logged)
    # ------------------------------------------------------------------

    def _build_sid_kwargs(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Build oracledb.connect kwargs for ORACLE_SID connection type."""
        return {
            "user": cfg["user"],
            "password": cfg["password"],
            "host": cfg["host"],
            "port": int(cfg.get("port") or 1521),
            "sid": cfg["dbname"],
        }

    def _build_service_name_kwargs(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Build oracledb.connect kwargs for ORACLE_SERVICE_NAME connection type."""
        return {
            "user": cfg["user"],
            "password": cfg["password"],
            "host": cfg["host"],
            "port": int(cfg.get("port") or 1521),
            "service_name": cfg["dbname"],
        }

    def _build_rac_kwargs(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Build oracledb.connect kwargs for ORACLE_RAC connection type.

        Talend XML embeds the RAC URL with leading/trailing whitespace and
        possible newlines; .strip() normalizes before passing as dsn=.
        """
        rac_url = (cfg.get("rac_url") or "").strip()
        if not rac_url:
            raise ConfigurationError("ORACLE_RAC requires rac_url to be set")
        return {
            "user": cfg["user"],
            "password": cfg["password"],
            "dsn": rac_url,
        }

    # ------------------------------------------------------------------
    # Per-connection control
    # ------------------------------------------------------------------

    def close(self, cid: str) -> None:
        """Explicit close. Removes from dict. Silent no-op for missing cid.

        Used by tOracleClose (future) and as the explicit-finalize hook for
        ad-hoc connections opened by tOracleRow/tOracleOutput.
        """
        conn = self.connections.pop(cid, None)
        if conn is None:
            return
        try:
            conn.close()
            logger.info("[OK] Closed Oracle connection cid=%s", cid)
        except Exception as e:
            logger.error("[ERROR] Error closing connection cid=%s: %s", cid, e)

    def commit(self, cid: str) -> None:
        """Commit a registered connection. Used by future tOracleCommit.

        Raises:
            ConfigurationError: If cid is not registered.
        """
        self.get(cid).commit()

    def rollback(self, cid: str) -> None:
        """Rollback a registered connection. Used by future tOracleRollback.

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

    def __enter__(self) -> "OracleConnectionManager":
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
            f"OracleConnectionManager(status={status}, "
            f"connections={len(self.connections)}, thick={self.thick_mode})"
        )
