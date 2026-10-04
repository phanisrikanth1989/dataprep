from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from xml.etree.ElementTree import Element


@dataclass
class TalendNode:
    """Parsed representation of a single Talend component node."""

    component_id: str
    component_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    schema: Dict[str, Any] = field(default_factory=dict)
    raw_xml: Element | None = None


@dataclass
class TalendConnection:
    """A connection (edge) between two Talend components."""

    name: str
    source: str
    target: str
    connector_type: str
    condition: Optional[str] = None


@dataclass
class ComponentResult:
    """Output produced by a component converter."""

    component: Dict[str, Any]
    flows: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    needs_review: List[Dict[str, Any]] = field(default_factory=list)


class ComponentConverter(ABC):
    """Abstract base for all Talend-to-V2 component converters."""

    @abstractmethod
    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        """Convert a TalendNode into a V2 component dict plus flows."""

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _incoming(
        node: TalendNode,
        connections: list[TalendConnection],
    ) -> list[TalendConnection]:
        """Return connections whose target is *node*."""
        return [c for c in connections if c.target == node.component_id]

    @staticmethod
    def _outgoing(
        node: TalendNode,
        connections: list[TalendConnection],
    ) -> list[TalendConnection]:
        """Return connections whose source is *node*."""
        return [c for c in connections if c.source == node.component_id]

    @staticmethod
    def _build_simple_flows(
        node: TalendNode,
        connections: list[TalendConnection],
    ) -> list[dict]:
        """Build V2 flow dicts for a straightforward component.

        Only handles FLOW and MAIN connector types for incoming connections.
        ITERATE, SUBJOB_OK, and other trigger types are intentionally excluded.
        Components that need ITERATE handling should build flows manually.

        * Incoming FLOW / MAIN connections become simple flows.
        * Outgoing REJECT connections become flows with ``output="reject"``.
        * Outgoing FLOW / MAIN connections become simple flows.
        """
        _MAIN_TYPES = {"FLOW", "MAIN"}
        flows: list[dict] = []

        for conn in connections:
            if conn.target == node.component_id and conn.connector_type in _MAIN_TYPES:
                flows.append(
                    {
                        "name": conn.name,
                        "source": conn.source,
                        "target": conn.target,
                    }
                )
            elif conn.source == node.component_id:
                if conn.connector_type == "REJECT":
                    flows.append(
                        {
                            "name": conn.name,
                            "source": conn.source,
                            "target": conn.target,
                            "output": "reject",
                        }
                    )
                elif conn.connector_type in _MAIN_TYPES:
                    flows.append(
                        {
                            "name": conn.name,
                            "source": conn.source,
                            "target": conn.target,
                        }
                    )

        return flows
