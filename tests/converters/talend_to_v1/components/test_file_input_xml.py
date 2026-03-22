"""Tests for tFileInputXML -> FileInputXML converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_xml import (
    FileInputXMLConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tFileInputXML_1",
        component_type="tFileInputXML",
        params=params or {},
        schema=schema or {},
        position={"x": 200, "y": 300},
    )


class TestFileInputXMLConverter:
    """Tests for FileInputXMLConverter."""

    def test_basic_config(self):
        """Config params are extracted and quote-stripped correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/input.xml"',
            "LOOP_QUERY": '"/root/record"',
            "LIMIT": '"1000"',
            "DIE_ON_ERROR": "true",
            "ENCODING": '"ISO-8859-1"',
            "IGNORE_NS": "true",
            "MAPPING": [],
        })
        result = FileInputXMLConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "FileInputXML"
        assert comp["original_type"] == "tFileInputXML"
        assert comp["id"] == "tFileInputXML_1"
        assert comp["position"] == {"x": 200, "y": 300}

        cfg = comp["config"]
        assert cfg["filename"] == "/data/input.xml"
        assert cfg["loop_query"] == "/root/record"
        assert cfg["limit"] == 1000
        assert cfg["die_on_error"] is True
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["ignore_ns"] is True
        assert cfg["mapping"] == []

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={
            "FILENAME": '"/data/file.xml"',
            "LOOP_QUERY": '"/root/item"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/file.xml"
        assert cfg["loop_query"] == "/root/item"
        assert cfg["limit"] == 0
        assert cfg["die_on_error"] is False
        assert cfg["encoding"] == "UTF-8"
        assert cfg["ignore_ns"] is False
        assert cfg["mapping"] == []

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={"LOOP_QUERY": '"/root"'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_empty_loop_query_produces_warning(self):
        """An empty LOOP_QUERY triggers a warning (CONV-FIX-001)."""
        node = _make_node(params={"FILENAME": '"/data/test.xml"'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert any("LOOP_QUERY" in w for w in result.warnings)

    def test_mapping_table_parsing(self):
        """MAPPING table entries are parsed with elementRef semantics (CONV-FIX-002)."""
        node = _make_node(params={
            "FILENAME": '"/data/orders.xml"',
            "LOOP_QUERY": '"/orders/order"',
            "MAPPING": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"order_id"'},
                {"elementRef": "QUERY", "value": '"@id"'},
                {"elementRef": "SCHEMA_COLUMN", "value": '"customer"'},
                {"elementRef": "QUERY", "value": '"customer/name"'},
                {"elementRef": "SCHEMA_COLUMN", "value": '"amount"'},
                {"elementRef": "QUERY", "value": '"total/@value"'},
            ],
        })
        result = FileInputXMLConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        assert len(mapping) == 3
        assert mapping[0] == {"column": "order_id", "xpath": "@id"}
        assert mapping[1] == {"column": "customer", "xpath": "customer/name"}
        assert mapping[2] == {"column": "amount", "xpath": "total/@value"}

    def test_schema_parsed(self):
        """Schema columns are parsed into output schema dicts."""
        node = _make_node(
            params={
                "FILENAME": '"test.xml"',
                "LOOP_QUERY": '"/root"',
            },
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", key=False, length=100),
                    SchemaColumn(
                        name="created",
                        type="id_Date",
                        date_pattern="yyyy-MM-dd HH:mm:ss",
                    ),
                ]
            },
        )
        result = FileInputXMLConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 3
        assert output_schema[0]["name"] == "id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 100
        assert output_schema[2]["name"] == "created"
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d %H:%M:%S"

    def test_input_schema_always_empty(self):
        """FileInputXML is a source — input schema must be empty."""
        node = _make_node(params={
            "FILENAME": '"x.xml"',
            "LOOP_QUERY": '"/root"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={
            "FILENAME": '"f.xml"',
            "LOOP_QUERY": '"/root"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={
            "FILENAME": '"f.xml"',
            "LOOP_QUERY": '"/root"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registry_lookup(self):
        """The converter is registered under 'tFileInputXML'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFileInputXML")
        assert cls is FileInputXMLConverter

    def test_boolean_params_from_strings(self):
        """Boolean params accept string representations."""
        node = _make_node(params={
            "FILENAME": '"data.xml"',
            "LOOP_QUERY": '"/root"',
            "DIE_ON_ERROR": "false",
            "IGNORE_NS": "1",
        })
        result = FileInputXMLConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["die_on_error"] is False
        assert cfg["ignore_ns"] is True

    def test_mapping_empty_list(self):
        """MAPPING as empty list produces empty mapping."""
        node = _make_node(params={
            "FILENAME": '"test.xml"',
            "LOOP_QUERY": '"/root"',
            "MAPPING": [],
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    def test_mapping_non_list_ignored(self):
        """If MAPPING is not a list (e.g. a string), mapping defaults to empty."""
        node = _make_node(params={
            "FILENAME": '"test.xml"',
            "LOOP_QUERY": '"/root"',
            "MAPPING": "not_a_list",
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []
