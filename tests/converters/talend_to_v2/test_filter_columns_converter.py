"""Tests for talend_to_v2 FilterColumns converter."""
import pytest
from xml.etree.ElementTree import parse as xml_parse
from pathlib import Path

from src.converters.talend_to_v2.components.base import TalendNode, TalendConnection
from src.converters.talend_to_v2.components.transform.filter_columns_converter import (
    FilterColumnsConverter,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestFilterColumnsConverter:
    """Round-trip tests for tFilterColumns converter (D-28)."""

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

    def test_keep_mode(self):
        """tFilterColumns with default keep mode produces correct v2 config."""
        node = self._parse_fixture("tFilterColumns_keep.xml")
        converter = FilterColumnsConverter()
        result = converter.convert(node, [], {})

        assert result.component["type"] == "filter_columns"
        assert result.component["config"]["columns"] == ["id", "name", "amount"]
        assert "mode" not in result.component["config"]  # keep is default, omitted
        assert result.warnings == [] or all(
            "NOT_PLANNED" in w or "UNSUPPORTED" in w for w in result.warnings
        )

    def test_remove_mode(self):
        """tFilterColumns with remove mode produces mode='remove' in config."""
        node = self._parse_fixture("tFilterColumns_remove.xml")
        converter = FilterColumnsConverter()
        result = converter.convert(node, [], {})

        assert result.component["type"] == "filter_columns"
        assert result.component["config"]["columns"] == ["temp_col"]
        assert result.component["config"]["mode"] == "remove"

    def test_flows_passthrough(self):
        """Converter builds simple flows from connections."""
        node = self._parse_fixture("tFilterColumns_keep.xml")
        connections = [
            TalendConnection(
                name="row1",
                source="tInput_1",
                target="tFilterColumns_1",
                connector_type="FLOW",
            ),
            TalendConnection(
                name="row2",
                source="tFilterColumns_1",
                target="tOutput_1",
                connector_type="FLOW",
            ),
        ]
        converter = FilterColumnsConverter()
        result = converter.convert(node, connections, {})

        assert len(result.flows) == 2
        sources = [f["source"] for f in result.flows]
        targets = [f["target"] for f in result.flows]
        assert "tInput_1" in sources
        assert "tFilterColumns_1" in sources
        assert "tFilterColumns_1" in targets
        assert "tOutput_1" in targets
