"""Maps Talend trigger connections to V2 TriggerConnection format."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .components.base import TalendConnection

logger = logging.getLogger(__name__)

# Talend connectorName values that represent triggers (not data flows)
_TRIGGER_TYPE_MAP: Dict[str, str] = {
    "SUBJOB_OK": "on_success",
    "SUBJOB_ERROR": "on_failure",
    "COMPONENT_OK": "on_success",
    "COMPONENT_ERROR": "on_failure",
    "RUN_IF": "conditional",
}


@dataclass
class TriggerMapperResult:
    """Result of mapping Talend trigger connections."""

    triggers: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    needs_review: List[Dict[str, Any]] = field(default_factory=list)


def map_triggers(connections: List[TalendConnection]) -> TriggerMapperResult:
    """Extract and map Talend trigger connections to V2 trigger format.

    Filters connections for trigger types (SUBJOB_OK, SUBJOB_ERROR,
    COMPONENT_OK, COMPONENT_ERROR, RUN_IF) and maps each to a V2
    trigger dict. RunIf conditions are included as-is and flagged
    for manual review.

    Args:
        connections: All parsed Talend connections (data + triggers).

    Returns:
        TriggerMapperResult with triggers, warnings, and needs_review items.
    """
    triggers: List[Dict[str, Any]] = []
    warnings: List[str] = []
    needs_review: List[Dict[str, Any]] = []

    for conn in connections:
        v2_type = _TRIGGER_TYPE_MAP.get(conn.connector_type)
        if v2_type is None:
            continue

        trigger: Dict[str, Any] = {
            "source": conn.source,
            "target": conn.target,
            "type": v2_type,
        }

        if v2_type == "conditional":
            trigger["condition"] = conn.condition

            if conn.condition:
                needs_review.append({
                    "component": "trigger",
                    "source": conn.source,
                    "target": conn.target,
                    "reason": "RunIf condition requires manual translation to V2 syntax",
                    "raw_condition": conn.condition,
                })
            else:
                warnings.append(
                    f"RUN_IF trigger from '{conn.source}' to '{conn.target}' "
                    f"has no condition expression"
                )

        triggers.append(trigger)

    return TriggerMapperResult(
        triggers=triggers,
        warnings=warnings,
        needs_review=needs_review,
    )
