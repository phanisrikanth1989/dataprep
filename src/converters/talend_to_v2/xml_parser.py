from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.converters.talend_to_v2.components.base import TalendConnection, TalendNode

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ContextParam:
    """A single Talend context parameter."""

    name: str
    value: str
    type: str  # Talend type: "id_String", "id_Integer", etc.


@dataclass
class SchemaColumn:
    """A column in a Talend component schema."""

    name: str
    type: str  # Talend type
    nullable: bool = True
    date_pattern: Optional[str] = None


@dataclass
class TalendJob:
    """Top-level result of parsing a Talend .item XML file."""

    job_name: str
    context: Dict[str, ContextParam]
    nodes: List[TalendNode]
    connections: List[TalendConnection]


# ---------------------------------------------------------------------------
# Fields whose values should have surrounding quotes stripped.
# ---------------------------------------------------------------------------

_QUOTE_STRIP_FIELDS = frozenset(
    {
        "TEXT",
        "FILE",
        "DIRECTORY",
        "ENCODING_TYPE",
        "CLOSED_LIST",
        "MEMO_JAVA",
        "MEMO_IMPORT",
        "LABEL",
    }
)

# Regex to strip a version suffix like _0.1 or _1.2 from a job filename.
_VERSION_SUFFIX_RE = re.compile(r"_\d+\.\d+$")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class XmlParser:
    """Parses a Talend .item XML file into a :class:`TalendJob`."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, xml_path: str) -> TalendJob:
        """Parse *xml_path* and return a :class:`TalendJob`."""
        path = Path(xml_path)
        tree = ET.parse(path)
        root = tree.getroot()

        job_name = self._extract_job_name(path)
        context = self._parse_context(root)
        nodes = self._parse_nodes(root)
        connections = self._parse_connections(root)

        return TalendJob(
            job_name=job_name,
            context=context,
            nodes=nodes,
            connections=connections,
        )

    # ------------------------------------------------------------------
    # Job name
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_job_name(path: Path) -> str:
        stem = path.stem  # e.g. "MyJob_0.1"
        # Strip .item extension handled by stem already.
        return _VERSION_SUFFIX_RE.sub("", stem)

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_context(root: ET.Element) -> Dict[str, ContextParam]:
        default_ctx = root.attrib.get("defaultContext", "Default")

        for ctx_elem in root.iter("context"):
            if ctx_elem.attrib.get("name") == default_ctx:
                params: Dict[str, ContextParam] = {}
                for cp in ctx_elem.iter("contextParameter"):
                    name = cp.attrib["name"]
                    raw_value = cp.attrib.get("value", "")
                    params[name] = ContextParam(
                        name=name,
                        value=XmlParser._strip_quotes(raw_value),
                        type=cp.attrib.get("type", ""),
                    )
                return params

        return {}

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def _parse_nodes(self, root: ET.Element) -> List[TalendNode]:
        nodes: List[TalendNode] = []
        for node_elem in root.iter("node"):
            component_type = node_elem.attrib.get("componentName", "")
            params = self._parse_element_params(node_elem)
            component_id = params.pop("UNIQUE_NAME", "")
            schema = self._parse_schema(node_elem)

            nodes.append(
                TalendNode(
                    component_id=component_id,
                    component_type=component_type,
                    params=params,
                    schema=schema,
                    raw_xml=node_elem,
                )
            )
        return nodes

    def _parse_element_params(self, node_elem: ET.Element) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for ep in node_elem.findall("elementParameter"):
            field_type = ep.attrib.get("field", "")
            name = ep.attrib.get("name", "")

            if field_type == "EXTERNAL":
                continue

            if field_type == "CHECK":
                params[name] = ep.attrib.get("value", "false").lower() == "true"
            elif field_type == "TABLE":
                values = [
                    {
                        "elementRef": ev.attrib.get("elementRef", ""),
                        "value": ev.attrib.get("value", ""),
                    }
                    for ev in ep.findall("elementValue")
                ]
                params[name] = values
            elif field_type in _QUOTE_STRIP_FIELDS:
                params[name] = self._strip_quotes(ep.attrib.get("value", ""))
            else:
                params[name] = ep.attrib.get("value", "")

        return params

    def _parse_schema(
        self, node_elem: ET.Element
    ) -> Dict[str, List[SchemaColumn]]:
        schema: Dict[str, List[SchemaColumn]] = {}
        for meta in node_elem.findall("metadata"):
            connector = meta.attrib.get("connector", "FLOW")
            columns: List[SchemaColumn] = []
            for col in meta.findall("column"):
                raw_pattern = self._strip_quotes(col.attrib.get("pattern", ""))
                columns.append(
                    SchemaColumn(
                        name=col.attrib.get("name", ""),
                        type=col.attrib.get("type", ""),
                        nullable=col.attrib.get("nullable", "true").lower() == "true",
                        date_pattern=raw_pattern if raw_pattern else None,
                    )
                )
            schema[connector] = columns
        return schema

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------

    def _parse_connections(self, root: ET.Element) -> List[TalendConnection]:
        connections: List[TalendConnection] = []
        for conn_elem in root.iter("connection"):
            source = conn_elem.attrib.get("source", "")
            target = conn_elem.attrib.get("target", "")
            if not source or not target:
                continue

            connector_type = conn_elem.attrib.get("connectorName", "")
            label = conn_elem.attrib.get("label", "")

            # Extract elementParameters: UNIQUE_NAME and CONDITION
            name = label
            condition = None
            for ep in conn_elem.findall("elementParameter"):
                ep_name = ep.attrib.get("name", "")
                if ep_name == "UNIQUE_NAME":
                    name = ep.attrib.get("value", label)
                elif ep_name == "CONDITION":
                    raw = ep.attrib.get("value", "")
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
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_quotes(value: str) -> str:
        """Strip surrounding double quotes.

        ``'context.x'`` stays as-is, ``'"data.csv"'`` becomes ``'data.csv'``.
        """
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            return value[1:-1]
        return value
