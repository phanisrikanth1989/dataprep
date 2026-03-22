"""Parses Talend .item XML files into structured data objects."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .components.base import SchemaColumn, TalendConnection, TalendNode
from .type_mapping import convert_type

logger = logging.getLogger(__name__)


@dataclass
class TalendJob:
    """Structured representation of a parsed Talend job."""

    job_name: str
    job_type: str
    default_context: str
    context: Dict[str, Dict[str, Any]]
    nodes: List[TalendNode]
    connections: List[TalendConnection]
    routines: List[str]
    libraries: List[str]


# Fields that should be skipped entirely during parameter extraction.
_SKIP_FIELDS = frozenset({"EXTERNAL"})


def _safe_int(value: str | None, default: int = 0) -> int:
    """Convert a string to int safely, returning default on failure."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class XmlParser:
    """Parses a Talend ``.item`` XML file into a :class:`TalendJob`."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, filepath: str) -> TalendJob:
        """Parse *filepath* and return a :class:`TalendJob`.

        Parameters
        ----------
        filepath:
            Path to a Talend ``.item`` XML file.
        """
        path = Path(filepath)
        tree = ET.parse(path)
        root = tree.getroot()

        job_name = path.stem
        job_type = root.get("jobType", "Standard")
        default_context = root.get("defaultContext", "Default")

        context = self._parse_context(root)
        nodes = self._parse_nodes(root)
        connections = self._parse_connections(root)
        routines = self._parse_routines(root)
        libraries = self._parse_libraries(root)

        return TalendJob(
            job_name=job_name,
            job_type=job_type,
            default_context=default_context,
            context=context,
            nodes=nodes,
            connections=connections,
            routines=routines,
            libraries=libraries,
        )

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def _parse_context(self, root: ET.Element) -> Dict[str, Dict[str, Any]]:
        """Parse all context groups and their parameters.

        Returns a dict keyed by context name (e.g. ``"Default"``), where each
        value is a dict of parameter dicts with ``value`` and ``type`` keys.
        """
        context: Dict[str, Dict[str, Any]] = {}

        for ctx_elem in root.iter("context"):
            ctx_name = ctx_elem.get("name", "Default")
            context[ctx_name] = {}

            for cp in ctx_elem.iter("contextParameter"):
                param_name = cp.get("name")
                if not param_name:
                    continue

                param_value = cp.get("value", "")
                param_type = cp.get("type", "id_String")
                python_type = convert_type(param_type)

                # Strip surrounding quotes from string values
                if python_type == "str" and isinstance(param_value, str):
                    param_value = self._strip_quotes(param_value)

                context[ctx_name][param_name] = {
                    "value": param_value,
                    "type": python_type,
                }

        return context

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def _parse_nodes(self, root: ET.Element) -> List[TalendNode]:
        """Parse all ``<node>`` elements, skipping ``tLibraryLoad`` nodes."""
        nodes: List[TalendNode] = []
        for node_elem in root.iter("node"):
            component_type = node_elem.get("componentName", "")

            # Skip tLibraryLoad — libraries are extracted separately
            if component_type == "tLibraryLoad":
                logger.debug("Skipping tLibraryLoad node")
                continue

            node = self._parse_node(node_elem)
            if node is not None:
                nodes.append(node)

        return nodes

    def _parse_node(self, node_elem: ET.Element) -> TalendNode:
        """Parse a single ``<node>`` element into a :class:`TalendNode`."""
        component_type = node_elem.get("componentName", "")

        # Extract all elementParameters
        params = self._parse_element_params(node_elem)

        # Pull UNIQUE_NAME out of params — it becomes the component_id
        component_id = params.pop("UNIQUE_NAME", "")

        # Parse schema from metadata sections
        schema = self._parse_schema(node_elem)

        # Position
        position = {
            "x": _safe_int(node_elem.get("posX", "0")),
            "y": _safe_int(node_elem.get("posY", "0")),
        }

        return TalendNode(
            component_id=component_id,
            component_type=component_type,
            params=params,
            schema=schema,
            position=position,
            raw_xml=node_elem,
        )

    def _parse_element_params(self, node_elem: ET.Element) -> Dict[str, Any]:
        """Extract all ``<elementParameter>`` children into a flat dict.

        * ``field="CHECK"`` values are converted to Python booleans.
        * String values have surrounding quotes stripped.
        * ``field="TABLE"`` values are collected as lists of elementValue dicts.
        * ``field="EXTERNAL"`` entries are skipped.
        """
        params: Dict[str, Any] = {}

        for ep in node_elem.findall("elementParameter"):
            field_type = ep.get("field", "")
            name = ep.get("name", "")
            if not name:
                continue

            # Skip fields that need special handling (e.g. tMap mapping data)
            if field_type in _SKIP_FIELDS:
                continue

            if field_type == "CHECK":
                params[name] = ep.get("value", "false").lower() == "true"
            elif field_type == "TABLE":
                values = [
                    {
                        "elementRef": ev.get("elementRef", ""),
                        "value": ev.get("value", ""),
                    }
                    for ev in ep.findall("elementValue")
                ]
                params[name] = values
            else:
                # Strip surrounding quotes from all other string values
                params[name] = self._strip_quotes(ep.get("value", ""))

        return params

    def _parse_schema(
        self, node_elem: ET.Element
    ) -> Dict[str, List[SchemaColumn]]:
        """Parse ``<metadata>`` sections into :class:`SchemaColumn` lists keyed by connector."""
        schema: Dict[str, List[SchemaColumn]] = {}

        for meta in node_elem.findall("metadata"):
            connector = meta.get("connector", "FLOW")
            columns: List[SchemaColumn] = []

            for col in meta.findall("column"):
                raw_pattern = self._strip_quotes(col.get("pattern", ""))
                columns.append(
                    SchemaColumn(
                        name=col.get("name", ""),
                        type=col.get("type", "id_String"),
                        nullable=col.get("nullable", "true").lower() == "true",
                        key=col.get("key", "false").lower() == "true",
                        length=_safe_int(col.get("length"), -1),
                        precision=_safe_int(col.get("precision"), -1),
                        date_pattern=raw_pattern if raw_pattern else "",
                    )
                )

            schema[connector] = columns

        return schema

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------

    def _parse_connections(self, root: ET.Element) -> List[TalendConnection]:
        """Parse all ``<connection>`` elements."""
        connections: List[TalendConnection] = []

        for conn_elem in root.iter("connection"):
            source = conn_elem.get("source", "")
            target = conn_elem.get("target", "")
            if not source or not target:
                continue

            connector_type = conn_elem.get("connectorName", "")
            label = conn_elem.get("label", "")

            # Extract UNIQUE_NAME and CONDITION from elementParameters
            name = label
            condition = None
            for ep in conn_elem.findall("elementParameter"):
                ep_name = ep.get("name", "")
                if ep_name == "UNIQUE_NAME":
                    name = self._strip_quotes(ep.get("value", label))
                elif ep_name == "CONDITION":
                    raw = ep.get("value", "")
                    if raw:
                        condition = raw

            connections.append(
                TalendConnection(
                    name=name,
                    source=source,
                    target=target,
                    connector_type=connector_type,
                    condition=condition,
                )
            )

        return connections

    # ------------------------------------------------------------------
    # Routines
    # ------------------------------------------------------------------

    def _parse_routines(self, root: ET.Element) -> List[str]:
        """Extract routine dependencies from ``<routinesParameter>`` elements.

        Returns a deduplicated, order-preserving list of routine names
        (prefixed with ``routines.`` if not already).
        """
        routines: List[str] = []

        for rp in root.findall(".//routinesParameter"):
            routine_name = rp.get("name")
            if not routine_name:
                continue
            if not routine_name.startswith("routines."):
                routine_name = f"routines.{routine_name}"
            routines.append(routine_name)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: List[str] = []
        for r in routines:
            if r not in seen:
                seen.add(r)
                unique.append(r)

        logger.info("Found %d routine dependencies: %s", len(unique), unique)
        return unique

    # ------------------------------------------------------------------
    # Libraries
    # ------------------------------------------------------------------

    def _parse_libraries(self, root: ET.Element) -> List[str]:
        """Extract library JARs from ``tLibraryLoad`` nodes' LIBRARY param.

        Returns a deduplicated, order-preserving list of JAR filenames.
        """
        libraries: List[str] = []

        for node_elem in root.findall('.//node[@componentName="tLibraryLoad"]'):
            for param in node_elem.findall('.//elementParameter[@name="LIBRARY"]'):
                value = param.get("value", "")
                if value:
                    # Strip XML-escaped and literal quotes
                    value = value.replace("&quot;", "").strip('"')
                    if value and value.endswith(".jar"):
                        libraries.append(value)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: List[str] = []
        for lib in libraries:
            if lib not in seen:
                seen.add(lib)
                unique.append(lib)

        logger.info("Found %d library dependencies: %s", len(unique), unique)
        return unique

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_quotes(value: str) -> str:
        """Strip surrounding double-quotes from a value.

        ``'"data.csv"'`` becomes ``'data.csv'``;
        ``'context.x'`` stays unchanged.
        """
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            return value[1:-1]
        return value
