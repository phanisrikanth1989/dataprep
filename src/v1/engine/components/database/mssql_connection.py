"""Engine component for MSSqlConnection (tMSSqlConnection).

Opens a pyodbc.Connection to SQL Server and registers it with the
MSSqlConnectionManager keyed by component id. Downstream MSSql components
reference this connection via USE_EXISTING_CONNECTION + CONNECTION = self.id.

Live pyodbc.Connection objects MUST NOT enter globalMap (non-Arrow-serializable
per the Phase 2 sync contract); they live in MSSqlConnectionManager keyed by
cid. Talend-parity metadata strings (connectionType_<cid>, dbschema_<cid>,
username_<cid>) are written to globalMap. The credential is NEVER written
(T-11-02).

Config keys consumed (mirrors the converter at
src/converters/talend_to_v1/components/database/mssql_connection.py):
    host, port, dbname, schema_db, user, password  -- connection params
    active_dir_auth (bool, default False)           -- Azure AD password auth
    auto_commit     (bool, default False)           -- connection autocommit
    odbc_driver     (str, optional)                 -- override ODBC driver name
    ... + framework params

Returns: {"main": None, "reject": None} -- orchestration component, no FLOW.
ASCII-only logging (D-H7).
"""
import logging
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("MSSqlConnection", "tMSSqlConnection")
class MSSqlConnection(BaseComponent):
    """tMSSqlConnection engine component. See module docstring."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize. ``mssql_manager`` is injected by ETLEngine
        ``_initialize_components``."""
        super().__init__(*args, **kwargs)
        self.mssql_manager = None  # type: ignore  # set by engine

    # ------------------------------------------------------------------
    # Validation (structural only per Rule 12 / D-F3)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Structural validation only -- require a non-empty ``host``."""
        if not self.config.get("host"):
            raise ConfigurationError(
                f"[{self.id}] connection requires non-empty config key 'host'"
            )

    # ------------------------------------------------------------------
    # Process: open + register connection, publish metadata
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Open the connection via the manager and publish parity metadata.

        Returns:
            ``{"main": None, "reject": None}``.
        """
        if self.mssql_manager is None:
            raise ConfigurationError(
                f"[{self.id}] MSSqlConnectionManager not wired into component. "
                f"This is an engine integration error -- ETLEngine."
                f"_initialize_components must inject self.mssql_manager."
            )

        # The manager owns pyodbc.connect (keeps the dependency lazy and the
        # connection-string build in one place). Storing under self.id makes it
        # retrievable by downstream get(self.id).
        self.mssql_manager.open_ad_hoc(self.id, self.config)
        logger.info("[%s] MSSql connection registered (cid=%s)", self.id, self.id)

        # Talend-parity globalMap metadata strings. SECURITY: credential is
        # NEVER pushed to globalMap (T-11-02).
        if self.global_map is not None:
            self.global_map.put(f"connectionType_{self.id}", "MSSQL")
            self.global_map.put(
                f"dbschema_{self.id}", self.config.get("schema_db", "")
            )
            self.global_map.put(
                f"username_{self.id}", self.config.get("user", "")
            )

        return {"main": None, "reject": None}
