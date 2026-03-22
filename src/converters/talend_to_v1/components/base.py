"""Abstract base class for component converters with shared helpers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from xml.etree.ElementTree import Element

from ..type_mapping import convert_type


@dataclass
class SchemaColumn:
    """Parsed representation of a single schema column."""
    name: str
    type: str
    nullable: bool = True
    key: bool = False
    length: int = -1
    precision: int = -1
    date_pattern: str = ""


@dataclass
class TalendNode:
    """Parsed representation of a single Talend component node."""
    component_id: str
    component_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    schema: Dict[str, List[SchemaColumn]] = field(default_factory=dict)
    position: Dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0})
    raw_xml: Optional[Element] = None


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
    warnings: List[str] = field(default_factory=list)
    needs_review: List[Dict[str, Any]] = field(default_factory=list)


# Java date pattern tokens -> Python strftime, longest first
_DATE_TOKENS = [
    ("yyyy", "%Y"), ("yy", "%y"),
    ("MM", "%m"), ("dd", "%d"),
    ("HH", "%H"), ("hh", "%I"),
    ("mm", "%M"),
    ("SSS", "%f"), ("ss", "%S"),
    ("a", "%p"),
]


class ComponentConverter(ABC):
    """Abstract base for all Talend-to-V1 component converters."""

    @abstractmethod
    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        """Convert a TalendNode into a v1 engine component dict."""

    # ------------------------------------------------------------------
    # Parameter extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_param(node: TalendNode, name: str, default: Any = None) -> Any:
        """Safe parameter extraction — returns default if missing."""
        return node.params.get(name, default)

    @staticmethod
    def _get_str(node: TalendNode, name: str, default: str = "") -> str:
        """Extract string parameter, strip surrounding quotes."""
        value = node.params.get(name)
        if value is None:
            return default
        if not isinstance(value, str):
            return str(value)
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            value = value[1:-1]
        return value

    @staticmethod
    def _get_bool(node: TalendNode, name: str, default: bool = False) -> bool:
        """Extract boolean parameter safely. Handles 'true'/'false' and '1'/'0'."""
        value = node.params.get(name)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1")
        return bool(value)

    @staticmethod
    def _get_int(node: TalendNode, name: str, default: int = 0) -> int:
        """Extract integer parameter safely."""
        value = node.params.get(name)
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            stripped = value.strip().strip('"')
            if stripped.lstrip("-").isdigit():
                return int(stripped)
        return default

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_schema(node: TalendNode, connector: str = "FLOW") -> List[Dict[str, Any]]:
        """Parse schema columns for a given connector into dicts."""
        columns = node.schema.get(connector, [])
        result = []
        for col in columns:
            col_dict: Dict[str, Any] = {
                "name": col.name,
                "type": convert_type(col.type),
                "nullable": col.nullable,
                "key": col.key,
            }
            if col.length >= 0:
                col_dict["length"] = col.length
            if col.precision >= 0:
                col_dict["precision"] = col.precision
            if col.date_pattern:
                col_dict["date_pattern"] = ComponentConverter._convert_date_pattern(
                    col.date_pattern
                )
            result.append(col_dict)
        return result

    @staticmethod
    def _convert_date_pattern(java_pattern: str) -> str:
        """Convert Java SimpleDateFormat pattern to Python strftime.

        Uses placeholder-based replacement to avoid token overlap corruption
        (e.g., 'MM' and 'mm' both containing 'm').
        """
        if not java_pattern:
            return ""
        result = java_pattern
        placeholders = {}
        # Phase 1: replace Java tokens with unique placeholders
        for i, (java_tok, py_tok) in enumerate(_DATE_TOKENS):
            placeholder = f"\x00{i}\x00"
            result = result.replace(java_tok, placeholder)
            placeholders[placeholder] = py_tok
        # Phase 2: replace placeholders with Python tokens
        for placeholder, py_tok in placeholders.items():
            result = result.replace(placeholder, py_tok)
        return result

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _incoming(
        node: TalendNode, connections: List[TalendConnection]
    ) -> List[TalendConnection]:
        """Return connections whose target is this node."""
        return [c for c in connections if c.target == node.component_id]

    @staticmethod
    def _outgoing(
        node: TalendNode, connections: List[TalendConnection]
    ) -> List[TalendConnection]:
        """Return connections whose source is this node."""
        return [c for c in connections if c.source == node.component_id]

    # ------------------------------------------------------------------
    # Component dict builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_component_dict(
        node: TalendNode,
        type_name: str,
        config: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assemble the standard v1 component dict structure."""
        return {
            "id": node.component_id,
            "type": type_name,
            "original_type": node.component_type,
            "position": node.position,
            "config": config,
            "schema": schema,
            "inputs": [],
            "outputs": [],
        }
