"""Tests for talend_to_v2 UniqRow converter."""
from xml.etree.ElementTree import parse as xml_parse
from pathlib import Path

from src.converters.talend_to_v2.components.base import TalendNode, TalendConnection
from src.converters.talend_to_v2.components.transform.uniq_row_converter import (
    UniqRowConverter,
    _parse_unique_key,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestUniqRowConverter:
    """Round-trip tests for tUniqRow converter."""

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
            elif field_type == "TABLE":
                # Parse TABLE entries as list of {elementRef, value} dicts
                values = [
                    {
                        "elementRef": ev.get("elementRef", ""),
                        "value": ev.get("value", ""),
                    }
                    for ev in elem.findall("elementValue")
                ]
                params[name] = values
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

    # ---- basic conversion ----

    def test_basic_conversion(self):
        """tUniqRow basic conversion produces correct type, key_columns, and keep."""
        node = self._parse_fixture("tUniqRow_basic.xml")
        converter = UniqRowConverter()
        result = converter.convert(node, [], {})

        assert result.component["type"] == "uniq_row"
        assert result.component["id"] == "tUniqRow_1"

        config = result.component["config"]
        assert len(config["key_columns"]) == 2

        # First key: id, case_sensitive=True
        assert config["key_columns"][0]["column"] == "id"
        assert config["key_columns"][0]["case_sensitive"] is True

        # Second key: name, case_sensitive=False
        assert config["key_columns"][1]["column"] == "name"
        assert config["key_columns"][1]["case_sensitive"] is False

        assert config["keep"] == "first"

    # ---- ONLY_ONCE_EACH_DUPLICATED_KEY ----

    def test_only_once_maps_to_keep_last(self):
        """ONLY_ONCE_EACH_DUPLICATED_KEY=True maps to keep='last' and only_once=True."""
        node = TalendNode(
            component_id="tUniqRow_2",
            component_type="tUniqRow",
            params={
                "ONLY_ONCE_EACH_DUPLICATED_KEY": True,
                "UNIQUE_KEY": [
                    {"elementRef": "SCHEMA_COLUMN", "value": '"col_a"'},
                    {"elementRef": "KEY_ATTRIBUTE", "value": "true"},
                    {"elementRef": "CASE_SENSITIVE", "value": "true"},
                ],
            },
        )
        converter = UniqRowConverter()
        result = converter.convert(node, [], {})
        config = result.component["config"]

        assert config["keep"] == "last"
        assert config["only_once"] is True

    # ---- duplicate output connection ----

    def test_duplicate_connection_enables_output(self):
        """DUPLICATE outgoing connection sets duplicate_output=True."""
        node = TalendNode(
            component_id="tUniqRow_3",
            component_type="tUniqRow",
            params={
                "UNIQUE_KEY": [
                    {"elementRef": "SCHEMA_COLUMN", "value": '"id"'},
                    {"elementRef": "KEY_ATTRIBUTE", "value": "true"},
                    {"elementRef": "CASE_SENSITIVE", "value": "true"},
                ],
            },
        )
        connections = [
            TalendConnection(
                name="unique_out",
                source="tUniqRow_3",
                target="tOutput_1",
                connector_type="UNIQUE",
            ),
            TalendConnection(
                name="dup_out",
                source="tUniqRow_3",
                target="tOutput_2",
                connector_type="DUPLICATE",
            ),
        ]
        converter = UniqRowConverter()
        result = converter.convert(node, connections, {})

        assert result.component["config"]["duplicate_output"] is True

    def test_no_duplicate_connection_no_output(self):
        """No DUPLICATE connection means duplicate_output absent from config."""
        node = TalendNode(
            component_id="tUniqRow_4",
            component_type="tUniqRow",
            params={
                "UNIQUE_KEY": [
                    {"elementRef": "SCHEMA_COLUMN", "value": '"id"'},
                    {"elementRef": "KEY_ATTRIBUTE", "value": "true"},
                    {"elementRef": "CASE_SENSITIVE", "value": "true"},
                ],
            },
        )
        connections = [
            TalendConnection(
                name="unique_out",
                source="tUniqRow_4",
                target="tOutput_1",
                connector_type="UNIQUE",
            ),
        ]
        converter = UniqRowConverter()
        result = converter.convert(node, connections, {})

        assert "duplicate_output" not in result.component["config"]

    # ---- flow output mapping ----

    def test_unique_connection_flow_output(self):
        """UNIQUE outgoing connection produces flow with output='unique'."""
        node = TalendNode(
            component_id="tUniqRow_5",
            component_type="tUniqRow",
            params={
                "UNIQUE_KEY": [
                    {"elementRef": "SCHEMA_COLUMN", "value": '"id"'},
                    {"elementRef": "KEY_ATTRIBUTE", "value": "true"},
                    {"elementRef": "CASE_SENSITIVE", "value": "true"},
                ],
            },
        )
        connections = [
            TalendConnection(
                name="row1",
                source="tInput_1",
                target="tUniqRow_5",
                connector_type="FLOW",
            ),
            TalendConnection(
                name="unique_out",
                source="tUniqRow_5",
                target="tOutput_1",
                connector_type="UNIQUE",
            ),
        ]
        converter = UniqRowConverter()
        result = converter.convert(node, connections, {})

        unique_flows = [f for f in result.flows if f.get("output") == "unique"]
        assert len(unique_flows) == 1
        assert unique_flows[0]["target"] == "tOutput_1"

    def test_duplicate_connection_flow_output(self):
        """DUPLICATE outgoing connection produces flow with output='duplicate'."""
        node = TalendNode(
            component_id="tUniqRow_6",
            component_type="tUniqRow",
            params={
                "UNIQUE_KEY": [
                    {"elementRef": "SCHEMA_COLUMN", "value": '"id"'},
                    {"elementRef": "KEY_ATTRIBUTE", "value": "true"},
                    {"elementRef": "CASE_SENSITIVE", "value": "true"},
                ],
            },
        )
        connections = [
            TalendConnection(
                name="dup_out",
                source="tUniqRow_6",
                target="tOutput_2",
                connector_type="DUPLICATE",
            ),
        ]
        converter = UniqRowConverter()
        result = converter.convert(node, connections, {})

        dup_flows = [f for f in result.flows if f.get("output") == "duplicate"]
        assert len(dup_flows) == 1
        assert dup_flows[0]["target"] == "tOutput_2"

    # ---- unsupported / not_planned feature warnings ----

    def test_is_virtual_component_warning(self):
        """IS_VIRTUAL_COMPONENT=True triggers UNSUPPORTED warning."""
        node = TalendNode(
            component_id="tUniqRow_7",
            component_type="tUniqRow",
            params={
                "IS_VIRTUAL_COMPONENT": True,
                "UNIQUE_KEY": [
                    {"elementRef": "SCHEMA_COLUMN", "value": '"id"'},
                    {"elementRef": "KEY_ATTRIBUTE", "value": "true"},
                    {"elementRef": "CASE_SENSITIVE", "value": "true"},
                ],
            },
        )
        converter = UniqRowConverter()
        result = converter.convert(node, [], {})

        assert any("UNSUPPORTED" in w for w in result.warnings)
        assert any("is_virtual_component" in w for w in result.warnings)

    def test_change_hash_warning_and_needs_review(self):
        """CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL=True triggers warning + needs_review."""
        node = TalendNode(
            component_id="tUniqRow_8",
            component_type="tUniqRow",
            params={
                "CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL": True,
                "UNIQUE_KEY": [
                    {"elementRef": "SCHEMA_COLUMN", "value": '"id"'},
                    {"elementRef": "KEY_ATTRIBUTE", "value": "true"},
                    {"elementRef": "CASE_SENSITIVE", "value": "true"},
                ],
            },
        )
        converter = UniqRowConverter()
        result = converter.convert(node, [], {})

        assert any("NOT_PLANNED" in w for w in result.warnings)
        assert len(result.needs_review) >= 1
        assert result.needs_review[0]["severity"] == "engine_gap"

    # ---- no key columns warning ----

    def test_no_key_columns_warning(self):
        """Empty UNIQUE_KEY produces warning about no key columns."""
        node = TalendNode(
            component_id="tUniqRow_9",
            component_type="tUniqRow",
            params={"UNIQUE_KEY": []},
        )
        converter = UniqRowConverter()
        result = converter.convert(node, [], {})

        assert any("No key columns" in w for w in result.warnings)

    # ---- registry ----

    def test_converter_registry(self):
        """UniqRowConverter registered for tUniqRow and tUniqueRow in registry."""
        from src.converters.talend_to_v2.components.registry import REGISTRY

        assert REGISTRY.get("tUniqRow") is UniqRowConverter
        assert REGISTRY.get("tUniqueRow") is UniqRowConverter
        assert REGISTRY.get("tUnqRow") is UniqRowConverter

    # ---- _parse_unique_key direct tests ----

    def test_parse_unique_key_stride3(self):
        """_parse_unique_key correctly parses stride-3 TABLE entries."""
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"col_a"'},
            {"elementRef": "KEY_ATTRIBUTE", "value": "true"},
            {"elementRef": "CASE_SENSITIVE", "value": "true"},
            {"elementRef": "SCHEMA_COLUMN", "value": '"col_b"'},
            {"elementRef": "KEY_ATTRIBUTE", "value": "true"},
            {"elementRef": "CASE_SENSITIVE", "value": "false"},
        ]
        result = _parse_unique_key(raw)
        assert len(result) == 2
        assert result[0] == {"column": "col_a", "case_sensitive": True}
        assert result[1] == {"column": "col_b", "case_sensitive": False}

    def test_parse_unique_key_skips_non_key(self):
        """_parse_unique_key excludes entries where KEY_ATTRIBUTE is false."""
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"col_a"'},
            {"elementRef": "KEY_ATTRIBUTE", "value": "true"},
            {"elementRef": "CASE_SENSITIVE", "value": "true"},
            {"elementRef": "SCHEMA_COLUMN", "value": '"col_b"'},
            {"elementRef": "KEY_ATTRIBUTE", "value": "false"},
            {"elementRef": "CASE_SENSITIVE", "value": "true"},
        ]
        result = _parse_unique_key(raw)
        assert len(result) == 1
        assert result[0]["column"] == "col_a"

    # ---- schema validation ----

    def test_key_column_not_in_schema_warning(self):
        """Key column not in schema metadata triggers a warning."""
        node = TalendNode(
            component_id="tUniqRow_10",
            component_type="tUniqRow",
            params={
                "UNIQUE_KEY": [
                    {"elementRef": "SCHEMA_COLUMN", "value": '"nonexistent"'},
                    {"elementRef": "KEY_ATTRIBUTE", "value": "true"},
                    {"elementRef": "CASE_SENSITIVE", "value": "true"},
                ],
            },
            schema=[
                {"name": "id", "type": "id_Integer"},
                {"name": "name", "type": "id_String"},
                {"name": "value", "type": "id_Float"},
            ],
        )
        converter = UniqRowConverter()
        result = converter.convert(node, [], {})

        schema_warnings = [w for w in result.warnings if "not found in component schema" in w]
        assert len(schema_warnings) == 1
        assert "nonexistent" in schema_warnings[0]
        assert "id" in schema_warnings[0]  # Available columns listed
