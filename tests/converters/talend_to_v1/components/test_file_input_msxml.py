"""Tests for tFileInputMSXML -> FileInputMSXML converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_msxml import (
    FileInputMSXMLConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tFileInputMSXML_1",
        component_type="tFileInputMSXML",
        params=params or {},
        schema=schema or {},
        position={"x": 160, "y": 320},
    )


class TestFileInputMSXMLConverter:
    """Tests for FileInputMSXMLConverter."""

    def test_basic_config(self):
        """Config params are extracted and quote-stripped correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/input.xml"',
            "ROOT_LOOP_QUERY": '"/root/record"',
            "SCHEMAS": [
                {"elementRef": "id", "value": '"id"'},
                {"elementRef": "name", "value": '"name"'},
                {"elementRef": "email", "value": '"contact/email"'},
            ],
            "DIE_ON_ERROR": "true",
            "TRIMALL": "false",
            "ENCODING": '"ISO-8859-1"',
        })
        result = FileInputMSXMLConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "FileInputMSXMLComponent"
        assert comp["original_type"] == "tFileInputMSXML"
        assert comp["id"] == "tFileInputMSXML_1"
        assert comp["position"] == {"x": 160, "y": 320}

        cfg = comp["config"]
        assert cfg["filename"] == "/data/input.xml"
        assert cfg["root_loop_query"] == "/root/record"
        assert cfg["die_on_error"] is True
        assert cfg["trim_all"] is False
        assert cfg["encoding"] == "ISO-8859-1"

        assert len(cfg["schemas"]) == 3
        assert cfg["schemas"][0] == {"column": "id", "xpath": "id"}
        assert cfg["schemas"][1] == {"column": "name", "xpath": "name"}
        assert cfg["schemas"][2] == {"column": "email", "xpath": "contact/email"}

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={"FILENAME": '"/data/file.xml"'})
        result = FileInputMSXMLConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/file.xml"
        assert cfg["root_loop_query"] == ""
        assert cfg["schemas"] == []
        assert cfg["die_on_error"] is False
        assert cfg["trim_all"] is False
        assert cfg["encoding"] == "UTF-8"

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_empty_root_loop_query_produces_warning(self):
        """An empty ROOT_LOOP_QUERY triggers a warning."""
        node = _make_node(params={"FILENAME": '"/data/file.xml"'})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert any("ROOT_LOOP_QUERY" in w for w in result.warnings)

    def test_schemas_table_parsing(self):
        """SCHEMAS table entries are parsed into column/xpath dicts."""
        node = _make_node(params={
            "FILENAME": '"/data/test.xml"',
            "ROOT_LOOP_QUERY": '"/items/item"',
            "SCHEMAS": [
                {"elementRef": "product_id", "value": '"@id"'},
                {"elementRef": "product_name", "value": '"name/text()"'},
            ],
        })
        result = FileInputMSXMLConverter().convert(node, [], {})
        schemas = result.component["config"]["schemas"]

        assert len(schemas) == 2
        assert schemas[0] == {"column": "product_id", "xpath": "@id"}
        assert schemas[1] == {"column": "product_name", "xpath": "name/text()"}

    def test_schemas_skips_empty_element_ref(self):
        """Entries with empty elementRef are skipped."""
        node = _make_node(params={
            "FILENAME": '"/data/test.xml"',
            "ROOT_LOOP_QUERY": '"/root"',
            "SCHEMAS": [
                {"elementRef": "", "value": '"orphan"'},
                {"elementRef": "valid_col", "value": '"xpath"'},
            ],
        })
        result = FileInputMSXMLConverter().convert(node, [], {})
        schemas = result.component["config"]["schemas"]

        assert len(schemas) == 1
        assert schemas[0]["column"] == "valid_col"

    def test_schema_parsed(self):
        """Schema columns are parsed into output schema dicts."""
        node = _make_node(
            params={
                "FILENAME": '"test.xml"',
                "ROOT_LOOP_QUERY": '"/root"',
            },
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", key=False, length=50),
                    SchemaColumn(
                        name="created",
                        type="id_Date",
                        date_pattern="yyyy-MM-dd HH:mm:ss",
                    ),
                ]
            },
        )
        result = FileInputMSXMLConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 3
        assert output_schema[0]["name"] == "id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 50
        assert output_schema[2]["name"] == "created"
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d %H:%M:%S"

    def test_input_schema_always_empty(self):
        """FileInputMSXML is a source — input schema must be empty."""
        node = _make_node(params={"FILENAME": '"x.xml"'})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"FILENAME": '"f.xml"'})
        result = FileInputMSXMLConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={"FILENAME": '"f.xml"'})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_boolean_params_from_strings(self):
        """Boolean params accept string representations."""
        node = _make_node(params={
            "FILENAME": '"data.xml"',
            "ROOT_LOOP_QUERY": '"/root"',
            "TRIMALL": "1",
            "DIE_ON_ERROR": "false",
        })
        result = FileInputMSXMLConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["trim_all"] is True
        assert cfg["die_on_error"] is False

    def test_registry_lookup(self):
        """The converter is registered under 'tFileInputMSXML'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFileInputMSXML")
        assert cls is FileInputMSXMLConverter
