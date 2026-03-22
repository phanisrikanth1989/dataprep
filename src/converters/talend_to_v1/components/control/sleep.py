"""Converter for Talend tSleep component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tSleep")
class SleepConverter(ComponentConverter):
    """Convert a Talend tSleep node into a v1 SleepComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        raw_pause = self._get_str(node, "PAUSE", default="0")
        try:
            pause_duration = float(raw_pause)
        except (ValueError, TypeError):
            warnings.append(
                f"PAUSE value {raw_pause!r} is not a valid number — defaulting to 0"
            )
            pause_duration = 0.0

        config: Dict[str, Any] = {
            "pause_duration": pause_duration,
        }

        component = self._build_component_dict(
            node=node,
            type_name="SleepComponent",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
