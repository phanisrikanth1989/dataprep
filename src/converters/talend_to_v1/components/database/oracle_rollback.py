"""Converter for Talend tOracleRollback component.

Rolls back the current transaction on a named Oracle connection.

Config mapping (4 params total):
  CONNECTION         -> connection (str, default "")
  CLOSE              -> close (bool, default True)
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label (str, default "")

Removed phantom params:
  CONNECTION_FORMAT  -- not in _java.xml, was extracted by old converter
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tOracleRollback")
class OracleRollbackConverter(ComponentConverter):
    """Convert Talend tOracleRollback to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["connection"] = self._get_str(node, "CONNECTION", "")
        config["close"] = self._get_bool(node, "CLOSE", True)

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Engine gap needs_review entries ----
        needs_review.append({
            "issue": (
                "No concrete engine implementation for tOracleRollback. "
                "All config keys are extracted for future engine support."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 4. Build component dict ----
        component = self._build_component_dict(
            node=node,
            type_name="tOracleRollback",
            config=config,
            schema={"input": [], "output": []},
        )

        # ---- 5. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
