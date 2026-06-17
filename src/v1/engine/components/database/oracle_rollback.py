"""Engine component for OracleRollback (tOracleRollback).

Rolls back the current transaction on a named Oracle connection registered with
the OracleConnectionManager, then optionally closes that connection.

Talend semantics: tOracleRollback references an upstream tOracleConnection via
its CONNECTION param. ROLLBACK applies to that shared connection; when CLOSE is
true (Talend default) the connection is closed afterwards.

Config keys consumed (mirrors the converter at
src/converters/talend_to_v1/components/database/oracle_rollback.py):
    connection (str, REQUIRED) -- cid of the upstream tOracleConnection
    close      (bool, default True) -- close the connection after rollback
    ... + framework params (tstatcatcher_stats, label)

Returns: {"main": input_data, "reject": None} -- passthrough; tOracleRollback
has no RETURN section (no NB_LINE).

Security: never logs credentials (T-11-02). ASCII-only logging (D-H7).
"""
import logging
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("OracleRollback", "tOracleRollback")
class OracleRollback(BaseComponent):
    """tOracleRollback engine component. See module docstring."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize. ``oracle_manager`` is injected by ETLEngine
        ``_initialize_components``."""
        super().__init__(*args, **kwargs)
        self.oracle_manager = None  # type: ignore  # set by engine

    # ------------------------------------------------------------------
    # Validation (structural only per Rule 12 / D-F3)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Structural validation only. Require the ``connection`` reference key.

        The referenced connection's existence is verified in ``_process`` via
        ``OracleConnectionManager.rollback`` (raises ConfigurationError if the
        ref is not registered).
        """
        if not self.config.get("connection"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'connection' "
                f"(reference to the upstream tOracleConnection)"
            )

    # ------------------------------------------------------------------
    # Process: rollback named connection, optionally close
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Rollback (and optionally close) the referenced connection.

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
        close = self.config.get("close", True)

        self.oracle_manager.rollback(connection_ref)
        logger.info(
            "[%s] Rolled back Oracle connection (ref=%s)", self.id, connection_ref
        )

        if close:
            self.oracle_manager.close(connection_ref)
            logger.info(
                "[%s] Closed Oracle connection after rollback (ref=%s)",
                self.id, connection_ref,
            )

        return {"main": input_data, "reject": None}
