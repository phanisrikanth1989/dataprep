"""Tests for tExtractXMLField -> ExtractXMLField converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.extract_xml_fields import (
    ExtractXMLFieldConverter,
    _parse_mapping,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tExtractXMLField_1",
        component_type="tExtractXMLField",
        params=params or {},
        schema=schema or {},
        position={"x": 400, "y": 200},
    )


def _make_mapping_entries(*rows):
    """Build a flat MAPPING list from tuples of (schema_column, query, nodecheck)."""
    entries = []
    for schema_col, query, nodecheck in rows:
        entries.append({"elementRef": "SCHEMA_COLUMN", "value": schema_col})
        entries.append({"elementRef": "QUERY", "value": query})
        entries.append({"elementRef": "NODECHECK", "value": nodecheck})
    return entries


class TestExtractXMLFieldConverter:
    """Tests for ExtractXMLFieldConverter."""

    def test_basic_config(self):
        """All config params are extracted correctly with explicit values."""
        node = _make_node(params={
            "XMLFIELD": '"payload"',
            "LOOP_QUERY": '"/root/record"',
            "LIMIT": "10",
            "DIE_ON_ERROR": "true",
            "IGNORE_NS": "true",
            "MAPPING": _make_mapping_entries(
                ('"name"', '"name/text()"', "false"),
                ('"age"', '"age/text()"', "true"),
            ),
        })
        result = ExtractXMLFieldConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "ExtractXMLField"
        assert comp["original_type"] == "tExtractXMLField"
        assert comp["id"] == "tExtractXMLField_1"
        assert comp["position"] == {"x": 400, "y": 200}

        cfg = comp["config"]
        assert cfg["xml_field"] == "payload"
        assert cfg["loop_query"] == "/root/record"
        assert cfg["limit"] == "10"
        assert cfg["die_on_error"] is True
        assert cfg["ignore_ns"] is True
        assert len(cfg["mapping"]) == 2
        assert cfg["mapping"][0] == {
            "schema_column": "name",
            "query": "name/text()",
            "nodecheck": "false",
        }
        assert cfg["mapping"][1] == {
            "schema_column": "age",
            "query": "age/text()",
            "nodecheck": "true",
        }
        assert not result.warnings

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["xml_field"] == "line"
        assert cfg["loop_query"] == ""
        assert cfg["limit"] == "0"
        assert cfg["die_on_error"] is False
        assert cfg["ignore_ns"] is False
        assert cfg["mapping"] == []
        # Should warn about empty loop_query and empty mapping
        assert any("LOOP_QUERY" in w for w in result.warnings)
        assert any("MAPPING" in w for w in result.warnings)

    def test_boolean_params_are_bool_not_string(self):
        """Boolean params must be Python bools, not strings."""
        node = _make_node(params={
            "DIE_ON_ERROR": "false",
            "IGNORE_NS": "false",
            "LOOP_QUERY": '"/"',
            "MAPPING": _make_mapping_entries(
                ('"col"', '"."', "false"),
            ),
        })
        result = ExtractXMLFieldConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["die_on_error"] is False
        assert isinstance(cfg["die_on_error"], bool)
        assert cfg["ignore_ns"] is False
        assert isinstance(cfg["ignore_ns"], bool)

    def test_schema_passthrough(self):
        """Both input and output schema must match FLOW schema."""
        node = _make_node(
            params={
                "LOOP_QUERY": '"/root"',
                "MAPPING": _make_mapping_entries(
                    ('"col1"', '"col1/text()"', "false"),
                ),
            },
            schema={
                "FLOW": [
                    SchemaColumn(
                        name="xml_payload", type="id_String",
                        key=False, nullable=True, length=2000,
                    ),
                    SchemaColumn(
                        name="col1", type="id_String",
                        key=False, nullable=True, length=100,
                    ),
                ]
            },
        )
        result = ExtractXMLFieldConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "xml_payload"
        assert schema["output"][0]["length"] == 2000
        assert schema["output"][1]["name"] == "col1"

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registration(self):
        """The converter is registered under 'tExtractXMLField'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tExtractXMLField")
        assert cls is ExtractXMLFieldConverter

    def test_empty_loop_query_warning(self):
        """An empty LOOP_QUERY produces a warning."""
        node = _make_node(params={
            "LOOP_QUERY": '""',
            "MAPPING": _make_mapping_entries(
                ('"col1"', '"."', "false"),
            ),
        })
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert any("LOOP_QUERY" in w for w in result.warnings)
        assert result.component["config"]["loop_query"] == ""

    def test_empty_mapping_warning(self):
        """No MAPPING entries produces a warning."""
        node = _make_node(params={
            "LOOP_QUERY": '"/root"',
        })
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert any("MAPPING" in w for w in result.warnings)
        assert result.component["config"]["mapping"] == []

    def test_mapping_with_multiple_rows(self):
        """MAPPING table with 3 rows is parsed correctly."""
        node = _make_node(params={
            "LOOP_QUERY": '"/root/item"',
            "MAPPING": _make_mapping_entries(
                ('"id"', '"@id"', "false"),
                ('"name"', '"name/text()"', "false"),
                ('"value"', '"value/text()"', "true"),
            ),
        })
        result = ExtractXMLFieldConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        assert len(mapping) == 3
        assert mapping[0]["schema_column"] == "id"
        assert mapping[0]["query"] == "@id"
        assert mapping[0]["nodecheck"] == "false"
        assert mapping[1]["schema_column"] == "name"
        assert mapping[2]["schema_column"] == "value"
        assert mapping[2]["nodecheck"] == "true"


class TestParseMapping:
    """Unit tests for the _parse_mapping helper."""

    def test_none_input(self):
        assert _parse_mapping(None) == []

    def test_empty_list(self):
        assert _parse_mapping([]) == []

    def test_non_list_input(self):
        assert _parse_mapping("not a list") == []

    def test_incomplete_group_ignored(self):
        """A trailing incomplete group (fewer than 3 entries) is skipped."""
        entries = [
            {"elementRef": "SCHEMA_COLUMN", "value": "col1"},
            {"elementRef": "QUERY", "value": "xpath1"},
            # Missing NODECHECK -> incomplete group
        ]
        assert _parse_mapping(entries) == []

    def test_non_dict_entries_skipped(self):
        """Non-dict entries within a group are skipped gracefully."""
        entries = [
            "bad_entry",
            {"elementRef": "QUERY", "value": "xpath"},
            {"elementRef": "NODECHECK", "value": "false"},
        ]
        # schema_column is missing -> row dropped (no schema_column)
        assert _parse_mapping(entries) == []

    def test_valid_single_row(self):
        entries = _make_mapping_entries(("col1", "xpath1", "false"))
        result = _parse_mapping(entries)
        assert len(result) == 1
        assert result[0] == {
            "schema_column": "col1",
            "query": "xpath1",
            "nodecheck": "false",
        }
