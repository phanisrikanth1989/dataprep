"""Converter for Talend tLoop component.

Supports For-loop (counter) and While-loop (condition) modes
via mutually exclusive FORLOOP/WHILELOOP radio buttons.

Config mapping (11 params total):
  FORLOOP            -> for_loop (bool, default True)
  WHILELOOP          -> while_loop (bool, default False)
  FROM               -> from_value (str, default "1")
  TO                 -> to_value (str, default "10")
  STEP               -> step (str, default "1")
  INCREASE           -> increase (bool, default True)
  DECLARATION        -> declaration (str, default "int i=0")
  CONDITION          -> condition (str, default "i<10")
  ITERATION          -> iteration (str, default "i++")
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tLoop")
class LoopConverter(ComponentConverter):
    """Convert Talend tLoop to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Config parameters ----
        config: Dict[str, Any] = {}

        # ---- 2. RADIO parameters (mutually exclusive) ----
        config["for_loop"] = self._get_bool(node, "FORLOOP", True)
        config["while_loop"] = self._get_bool(node, "WHILELOOP", False)

        # ---- 3. For-loop parameters (FROM, TO, STEP, INCREASE) ----
        config["from_value"] = self._get_str(node, "FROM", "1")
        config["to_value"] = self._get_str(node, "TO", "10")
        config["step"] = self._get_str(node, "STEP", "1")
        config["increase"] = self._get_bool(node, "INCREASE", True)

        # ---- 4. While-loop parameters (DECLARATION, CONDITION, ITERATION) ----
        config["declaration"] = self._get_str(node, "DECLARATION", "int i=0")
        config["condition"] = self._get_str(node, "CONDITION", "i<10")
        config["iteration"] = self._get_str(node, "ITERATION", "i++")

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Engine gap needs_review entries ----
        needs_review.append({
            "issue": "No concrete engine implementation for tLoop. All config keys are extracted for future engine support.",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 7. Build component dict and return ----
        component = self._build_component_dict(
            node=node,
            type_name="tLoop",
            config=config,
            schema={"input": [], "output": []},
        )
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
