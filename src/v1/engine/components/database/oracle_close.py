"""Engine component for OracleClose (tOracleClose).

Closes an existing Oracle database connection registered with the
OracleConnectionManager. Unlike tOracleCommit / tOracleRollback this issues no
COMMIT or ROLLBACK -- it only releases the connection.

Talend semantics: tOracleClose references an upstream tOracleConnection via its
CONNECTION param and closes it. The OracleConnectionManager.close API is a
no-op for an already-closed / unregistered cid (idempotent), matching Talend's
tolerance of a connection that was already closed by a prior commit/rollback
with CLOSE=true.

Config keys consumed (mirrors the converter at
src/converters/talend_to_v1/components/database/oracle_close.py):
    connection (str, REQUIRED) -- cid of the upstream tOracleConnection
    ... + framework params (tstatcatcher_stats, label)

Returns: {"main": input_data, "reject": None} -- passthrough; tOracleClose has
no RETURN section (no NB_LINE).

Security: never logs credentials (T-11-02). ASCII-only logging (D-H7).
"""
import logging
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("OracleClose", "tOracleClose")
class OracleClose(BaseComponent):
    """tOracleClose engine component. See module docstring."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize. ``oracle_manager`` is injected by ETLEngine
        ``_initialize_components``."""
        super().__init__(*args, **kwargs)
        self.oracle_manager = None  # type: ignore  # set by engine

    # ------------------------------------------------------------------
    # Validation (structural only per Rule 12 / D-F3)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Structural validation only. Require the ``connection`` reference key."""
        if not self.config.get("connection"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'connection' "
                f"(reference to the upstream tOracleConnection)"
            )

    # ------------------------------------------------------------------
    # Process: close named connection (idempotent)
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Close the referenced connection.

        Returns:
            ``{"main": input_data, "reject": None}`` -- passthrough.
        """
        if self.oracle_manager is None:
            raise ConfigurationError(
                f"[{self.id}] OracleConnectionManager not wired into component. "
                f"This is an engine integration error -- ETLEngine."
                f"_initialize_components must inject self.oracle_manager."
            )

        connection_ref = self.config["connection"]
        self.oracle_manager.close(connection_ref)
        logger.info("[%s] Closed Oracle connection (ref=%s)", self.id, connection_ref)

        return {"main": input_data, "reject": None}
