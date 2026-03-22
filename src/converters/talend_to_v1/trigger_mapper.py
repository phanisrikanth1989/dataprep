"""Trigger parsing and mapping for Talend connections."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from .components.base import TalendConnection
from .expression_converter import ExpressionConverter

logger = logging.getLogger(__name__)

# V1 engine uses PascalCase trigger type names
_TRIGGER_TYPE_MAP = {
    "SUBJOB_OK": "OnSubjobOk",
    "SUBJOB_ERROR": "OnSubjobError",
    "COMPONENT_OK": "OnComponentOk",
    "COMPONENT_ERROR": "OnComponentError",
    "RUN_IF": "RunIf",
}

_TRIGGER_CONNECTOR_TYPES = set(_TRIGGER_TYPE_MAP.keys())


@dataclass
class TriggerResult:
    """Result of trigger extraction."""
    triggers: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    needs_review: List[Dict[str, Any]] = field(default_factory=list)


def map_triggers(
    connections: List[TalendConnection],
    component_ids: Set[str],
) -> TriggerResult:
    """Extract and map trigger connections to v1 format.

    Args:
        connections: All parsed connections from the job
        component_ids: Set of valid component IDs (for filtering)

    Returns:
        TriggerResult with mapped triggers, warnings, and review items
    """
    expr_converter = ExpressionConverter()
    result = TriggerResult()

    for conn in connections:
        if conn.connector_type not in _TRIGGER_CONNECTOR_TYPES:
            continue

        if not conn.source or not conn.target:
            continue

        # Filter triggers where both source and target exist
        if conn.source not in component_ids or conn.target not in component_ids:
            logger.debug(
                "Skipping trigger from '%s' to '%s' — one or both components were skipped",
                conn.source, conn.target,
            )
            continue

        # Map trigger type
        mapped_type = _TRIGGER_TYPE_MAP.get(conn.connector_type, conn.connector_type)

        # tPrejob special handling: ALL trigger types from tPrejob are overridden
        # to OnComponentOk to ensure the prejob runs before other subjobs.
        # This matches the original complex_converter behavior (converter.py:428-434).
        if conn.source.startswith("tPrejob"):
            logger.info("Ensuring tPrejob (%s) executes before %s", conn.source, conn.target)
            mapped_type = "OnComponentOk"

        trigger: Dict[str, Any] = {
            "type": mapped_type,
            "from": conn.source,
            "to": conn.target,
        }

        # Extract condition for RunIf triggers
        if conn.connector_type == "RUN_IF":
            if conn.condition:
                trigger["condition"] = expr_converter.convert(conn.condition)
                result.needs_review.append({
                    "component_id": conn.source,
                    "field": "trigger_condition",
                    "reason": "RunIf condition may need manual review",
                    "original_value": conn.condition,
                })
            else:
                result.warnings.append(
                    f"RunIf trigger from '{conn.source}' to '{conn.target}' "
                    f"has no condition"
                )

        result.triggers.append(trigger)

    return result
