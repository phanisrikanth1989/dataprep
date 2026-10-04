"""Tests for talend_to_v2 Unite converter."""
from xml.etree.ElementTree import parse as xml_parse
from pathlib import Path

from src.converters.talend_to_v2.components.base import TalendNode, TalendConnection
from src.converters.talend_to_v2.components.transform.unite_converter import (
    UniteConverter,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestUniteConverter:
    """Round-trip tests for tUnite converter."""

    def _parse_fixture(self, filename: str) -> TalendNode:
        """Parse an XML fixture into a TalendNode."""
        fixture_path = FIXTURES_DIR / filename
        tree = xml_parse(fixture_path)
        root = tree.getroot()

        # Extract params from elementParameter elements
        params = {}
        for elem in root.findall("elementParameter"):
            name = elem.get("name", "")
            value = elem.get("value", "")
            field_type = elem.get("field", "")
            if field_type == "CHECK":
                params[name] = value.lower() == "true"
            else:
                params[name] = value

        # Extract schema from metadata
        schema = []
        for meta in root.findall("metadata"):
            for col in meta.findall("column"):
                schema.append({
                    "name": col.get("name", ""),
                    "type": col.get("type", "id_String"),
                    "nullable": col.get("nullable", "true") == "true",
                })

        return TalendNode(
            component_id=params.get("UNIQUE_NAME", "unknown"),
            component_type=root.get("componentName", ""),
            params=params,
            schema=schema,
            raw_xml=root,
        )

    def test_basic_conversion(self):
        """tUnite basic conversion produces unite type with empty config."""
        node = self._parse_fixture("tUnite_basic.xml")
        converter = UniteConverter()
        result = converter.convert(node, [], {})
        assert result.component["type"] == "unite"
        assert result.component["config"] == {}  # Zero unique params
        assert result.component["id"] == "tUnite_1"

    def test_multi_input_flows(self):
        """Converter builds flows for multiple incoming connections."""
        node = self._parse_fixture("tUnite_basic.xml")
        connections = [
            TalendConnection(
                name="row1",
                source="tInput_1",
                target="tUnite_1",
                connector_type="FLOW",
            ),
            TalendConnection(
                name="row2",
                source="tInput_2",
                target="tUnite_1",
                connector_type="FLOW",
            ),
            TalendConnection(
                name="row3",
                source="tUnite_1",
                target="tOutput_1",
                connector_type="FLOW",
            ),
        ]
        converter = UniteConverter()
        result = converter.convert(node, connections, {})
        assert len(result.flows) == 3
        incoming = [f for f in result.flows if f["target"] == "tUnite_1"]
        outgoing = [f for f in result.flows if f["source"] == "tUnite_1"]
        assert len(incoming) == 2
        assert len(outgoing) == 1

    def test_no_warnings_on_basic(self):
        """Basic tUnite conversion produces no warnings or needs_review."""
        node = self._parse_fixture("tUnite_basic.xml")
        converter = UniteConverter()
        result = converter.convert(node, [], {})
        # No warnings expected since basic fixture has no UNSUPPORTED params active
        assert result.warnings == [] or all(
            "NOT_PLANNED" in w or "UNSUPPORTED" in w for w in result.warnings
        )
        assert result.needs_review == []

    def test_converter_registry(self):
        """UniteConverter is registered for tUnite in the converter registry."""
        from src.converters.talend_to_v2.components.registry import REGISTRY

        converter_cls = REGISTRY.get("tUnite")
        assert converter_cls is not None
        assert converter_cls is UniteConverter

    def test_single_outgoing_flow(self):
        """Converter handles the typical case of one outgoing flow."""
        node = self._parse_fixture("tUnite_basic.xml")
        connections = [
            TalendConnection(
                name="out",
                source="tUnite_1",
                target="tOutput_1",
                connector_type="FLOW",
            ),
        ]
        converter = UniteConverter()
        result = converter.convert(node, connections, {})
        assert len(result.flows) == 1
        assert result.flows[0]["source"] == "tUnite_1"
        assert result.flows[0]["target"] == "tOutput_1"

    def test_no_connections(self):
        """Converter works with zero connections (isolated component)."""
        node = self._parse_fixture("tUnite_basic.xml")
        converter = UniteConverter()
        result = converter.convert(node, [], {})
        assert result.flows == []
        assert result.component["type"] == "unite"
