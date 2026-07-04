"""Engine component for OracleConnection (tOracleConnection / tDBConnection).

Opens an oracledb.Connection per CONNECTION_TYPE and registers it with the
OracleConnectionManager keyed by component id. Downstream Oracle components
reference this connection via USE_EXISTING_CONNECTION + CONNECTION = self.id.

Phase 11 scope (D-A3):
  ORACLE_SID, ORACLE_SERVICE_NAME, ORACLE_RAC -- fully implemented
  ORACLE_OCI, ORACLE_WALLET                   -- raise ConfigurationError

Live oracledb.Connection objects MUST NOT enter globalMap (non-Arrow-serializable
per Phase 2 sync contract). They live in OracleConnectionManager keyed by cid.
Talend-parity metadata strings (connectionType_<cid>, dbschema_<cid>,
username_<cid>) are written to globalMap.

Config keys consumed (Talend XML param -> v1 engine config key, mirrors the
converter at src/converters/talend_to_v1/components/database/oracle_connection.py):
    connection_type     (str, default "ORACLE_SID")  -- one of 5 CT values
    host                (str, default "")
    port                (str|int, default "1521")    -- coerced to int
    dbname              (str)                        -- SID for SID, service name
                                                       for SERVICE_NAME
    local_service_name  (str, default "")            -- alias for dbname
                                                       (SERVICE_NAME path)
    rac_url             (str)                        -- raw TNS connect descriptor
                                                       for RAC
    user                (str)                        -- credential
    password            (str)                        -- credential -- NEVER logged
                                                       or stored in globalMap
    schema_db           (str, default "")            -- Oracle schema name
                                                       (NOT engine schema)
    auto_commit         (bool, default False)        -- conn.autocommit = True
    encoding            (str, default "ISO-8859-15") -- not honored in oracledb
                                                       thin mode
    properties          (str, default "")            -- Talend k=v;k=v string;
                                                       logged-and-skipped
    use_tns_file        (bool, default False)        -- deferred (WARNING when True)
    tns_file            (str, default "")            -- deferred (matches
                                                       converter emit name and
                                                       use_tns_file deferred-flag
                                                       loop key check below)
    support_nls         (bool, default False)        -- deferred
    use_ssl             (bool, default False)        -- deferred
    ssl_truststore_*    (str)                        -- deferred SSL params
    tstatcatcher_stats  (bool, default False)        -- framework param
    label               (str, default "")            -- framework param
    ... (remaining converter-emitted keys read but not actively used)

Returns: {"main": None, "reject": None} -- orchestration component, no FLOW.
Side effects: registers self.id -> oracledb.Connection in self.oracle_manager;
              publishes 3 metadata strings to globalMap.

Talend semantics: tOracleConnection has NO RETURN section, hence no _NB_LINE_*
keys per D-C8.
"""
import logging
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("OracleConnection", "tOracleConnection", "tDBConnection")
class OracleConnection(BaseComponent):
    """tOracleConnection engine component. See module docstring."""

    # Class-level constants for validation
    _VALID_CONNECTION_TYPES = frozenset(
        {
            "ORACLE_SID",
            "ORACLE_SERVICE_NAME",
            "ORACLE_OCI",
            "ORACLE_RAC",
            "ORACLE_WALLET",
        }
    )

    def __init__(self, *args, **kwargs) -> None:
        """Initialize component. ``oracle_manager`` is injected by ETLEngine
        ``_initialize_components`` (plan 11-01 wiring)."""
        super().__init__(*args, **kwargs)
        # ETLEngine._initialize_components injects this in plan 11-01:
        self.oracle_manager = None  # type: ignore  # set by engine

    # ------------------------------------------------------------------
    # Validation (structural only per Phase 7.1 Rule 12 / D-F3)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Structural validation only -- does NOT inspect resolved values.

        Per Phase 7.1 Rule 12 (D-F3), content checks (URL syntax, OCI/Wallet
        refusal) belong in ``_process()`` AFTER context resolution.
        ``_validate_config`` only verifies required keys are present and enum
        values are in the closed set.

        WR-06: SID and SERVICE_NAME paths require ``host`` (and ``dbname`` /
        a service-name source) to be non-empty. Without this check, a
        missing ``dbname`` for SID would surface as a low-level KeyError
        from ``self.config["dbname"]`` in _process; SERVICE_NAME would fall
        through to a confusing oracledb.connect error. Catching empty
        required values here gives operators a typed ConfigurationError
        with the cid prefix instead. (Absence-of-key checks count as
        structural per Rule 12's spirit; they do not inspect resolved
        values.)
        """
        ct = self.config.get("connection_type", "ORACLE_SID")
        if ct not in self._VALID_CONNECTION_TYPES:
            raise ConfigurationError(
                f"[{self.id}] Invalid connection_type {ct!r}. "
                f"Must be one of: {sorted(self._VALID_CONNECTION_TYPES)}"
            )
        for required_key in ("user", "password"):
            if required_key not in self.config:
                raise ConfigurationError(
                    f"[{self.id}] Missing required config key {required_key!r}"
                )

        # WR-06: structural required-keys check per connection_type. Skip
        # OCI/WALLET (refused in _process anyway) and RAC (uses rac_url
        # instead of host/port/dbname; rac_url presence is checked in
        # _process where context resolution has already run).
        if ct == "ORACLE_SID":
            for k in ("host", "dbname"):
                if not self.config.get(k):
                    raise ConfigurationError(
                        f"[{self.id}] connection_type={ct} requires non-empty "
                        f"config key {k!r}"
                    )
        elif ct == "ORACLE_SERVICE_NAME":
            if not self.config.get("host"):
                raise ConfigurationError(
                    f"[{self.id}] connection_type={ct} requires non-empty "
                    f"config key 'host'"
                )
            # Either dbname (Talend's primary key for SERVICE_NAME) or
            # local_service_name must be set.
            if not (
                self.config.get("dbname")
                or self.config.get("local_service_name")
            ):
                raise ConfigurationError(
                    f"[{self.id}] connection_type={ct} requires non-empty "
                    f"'dbname' or 'local_service_name'"
                )

    # ------------------------------------------------------------------
    # Process: open connection, register with manager, publish metadata
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Open ``oracledb.Connection`` and register with ``OracleConnectionManager``.

        Note: this is the FIRST call site that needs ``oracledb``. We defer the
        import here so the ``oracle`` extra is optional for jobs that don't use
        Oracle components.
        """
        if self.oracle_manager is None:
            raise ConfigurationError(
                f"[{self.id}] OracleConnectionManager not wired into component. "
                f"This is an engine integration error -- ETLEngine."
                f"_initialize_components must inject self.oracle_manager."
            )

        ct = self.config["connection_type"]

        # D-A3: OCI / Wallet refusal (content check, lives in _process per Rule 12)
        if ct in ("ORACLE_OCI", "ORACLE_WALLET"):
            # T-11-05 mitigation: error text contains NO wallet path, NO auth detail
            raise ConfigurationError(
                f"[{self.id}] CONNECTION_TYPE {ct!r} requires oracledb thick mode "
                f"+ Oracle Instant Client. Set oracle_config.thick_mode=true in "
                f"job config and install Instant Client on the host. Tracked in "
                f"deferred items."
            )

        # Build connect kwargs per CT (defer import; mirror manager pattern)
        import oracledb

        if ct == "ORACLE_SID":
            kwargs = {
                "user": self.config["user"],
                "password": self.config["password"],
                "host": self.config.get("host", ""),
                "port": int(self.config.get("port") or 1521),
                "sid": self.config["dbname"],
            }
        elif ct == "ORACLE_SERVICE_NAME":
            # Talend uses dbname for service_name when CT=SERVICE_NAME
            service = self.config.get("dbname") or self.config.get(
                "local_service_name", ""
            )
            kwargs = {
                "user": self.config["user"],
                "password": self.config["password"],
                "host": self.config.get("host", ""),
                "port": int(self.config.get("port") or 1521),
                "service_name": service,
            }
        elif ct == "ORACLE_RAC":
            rac_url = (self.config.get("rac_url") or "").strip()
            if not rac_url:
                raise ConfigurationError(
                    f"[{self.id}] ORACLE_RAC requires rac_url to be set"
                )
            kwargs = {
                "user": self.config["user"],
                "password": self.config["password"],
                "dsn": rac_url,
            }
        else:
            # Unreachable due to _validate_config but keep defensive
            raise ConfigurationError(
                f"[{self.id}] Unhandled connection_type {ct!r}"
            )

        # T-11-02 mitigation: NEVER log kwargs (contains credential). Log cid + ct only.
        logger.info("[%s] Opening Oracle connection (type=%s)", self.id, ct)

        conn = oracledb.connect(**kwargs)

        # D-A4: AUTO_COMMIT advanced param
        if self.config.get("auto_commit", False):
            conn.autocommit = True
            logger.info("[%s] auto_commit=True; conn.autocommit set", self.id)

        # Register with manager keyed by THIS component's id (D-A1)
        self.oracle_manager.register(self.id, conn)

        # Talend-parity globalMap metadata strings (D-A1, D-C8)
        # SECURITY: credential is NEVER pushed to globalMap (T-11-02)
        if self.global_map is not None:
            self.global_map.put(f"connectionType_{self.id}", ct)
            self.global_map.put(
                f"dbschema_{self.id}", self.config.get("schema_db", "")
            )
            self.global_map.put(
                f"username_{self.id}", self.config.get("user", "")
            )
            # Intentionally NOT pushed: credential, host, port, dbname (host could
            # be PII; downstream consumers can read from oracle_manager if they
            # need it)

        # Log deferred-feature warnings for parameters not yet honored
        for deferred_flag in ("use_tns_file", "support_nls", "use_ssl"):
            if self.config.get(deferred_flag, False):
                logger.warning(
                    "[%s] Config %r=True but not honored in Phase 11 (deferred)",
                    self.id,
                    deferred_flag,
                )

        if (
            self.config.get("encoding")
            and self.config["encoding"] != "ISO-8859-15"
        ):
            logger.info(
                "[%s] encoding=%r is not honored in oracledb thin mode "
                "(driver decodes per server NLS_CHARACTERSET)",
                self.id,
                self.config["encoding"],
            )

        logger.info(
            "[%s] Oracle connection registered (cid=%s)", self.id, self.id
        )
        return {"main": None, "reject": None}
