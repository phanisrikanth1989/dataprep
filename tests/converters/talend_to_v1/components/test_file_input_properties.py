"""Tests for tFileInputProperties -> FileInputProperties converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_properties import (
    FileInputPropertiesConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="tFileInputProperties_1",
               component_type="tFileInputProperties"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 160, "y": 240},
    )


class TestFileInputPropertiesConverter:
    """Core conversion logic."""

    def test_basic_conversion(self):
        """All config params are extracted and quote-stripped correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/input.properties"',
            "ENCODING": '"ISO-8859-1"',
            "DIE_ON_ERROR": "true",
        })
        result = FileInputPropertiesConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "tFileInputProperties_1"
        assert comp["type"] == "FileInputProperties"
        assert comp["original_type"] == "tFileInputProperties"
        assert comp["position"] == {"x": 160, "y": 240}
        assert comp["config"]["filename"] == "/data/input.properties"
        assert comp["config"]["encoding"] == "ISO-8859-1"
        assert comp["config"]["die_on_error"] is True
        assert result.warnings == []

    def test_defaults_when_params_missing(self):
        """Missing optional params fall back to sensible defaults."""
        node = _make_node(params={"FILENAME": '"/tmp/app.properties"'})
        result = FileInputPropertiesConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/tmp/app.properties"
        assert cfg["encoding"] == "UTF-8"
        assert cfg["die_on_error"] is False
        assert result.warnings == []

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={"FILENAME": ""})
        result = FileInputPropertiesConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == ""
        assert len(result.warnings) == 1
        assert "FILENAME is empty" in result.warnings[0]

    def test_missing_filename_produces_warning(self):
        """A completely missing FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputPropertiesConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == ""
        assert result.component["config"]["encoding"] == "UTF-8"
        assert result.component["config"]["die_on_error"] is False
        assert len(result.warnings) == 1
        assert "FILENAME is empty" in result.warnings[0]

    def test_die_on_error_false_string(self):
        """DIE_ON_ERROR set to 'false' is parsed as False."""
        node = _make_node(params={
            "FILENAME": '"/data/config.properties"',
            "DIE_ON_ERROR": "false",
        })
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_schema_parsed_into_output(self):
        """Schema columns appear in output schema (source component)."""
        node = _make_node(
            params={"FILENAME": '"test.properties"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="key", type="id_String", key=True, nullable=False, length=255),
                    SchemaColumn(name="value", type="id_String", key=False, length=1000),
                ]
            },
        )
        result = FileInputPropertiesConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 2
        assert output_schema[0]["name"] == "key"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[0]["length"] == 255
        assert output_schema[1]["name"] == "value"
        assert output_schema[1]["length"] == 1000

    def test_input_schema_always_empty(self):
        """FileInputProperties is a source -- input schema must be empty."""
        node = _make_node(params={"FILENAME": '"x.properties"'})
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"FILENAME": '"f.properties"'})
        result = FileInputPropertiesConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_filename_without_quotes(self):
        """Filename without surrounding quotes is returned as-is."""
        node = _make_node(params={"FILENAME": "/etc/app.properties"})
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "/etc/app.properties"


class TestFileInputPropertiesRegistry:
    """Verify the converter is properly registered."""

    def test_registered_under_tfileinputproperties(self):
        cls = REGISTRY.get("tFileInputProperties")
        assert cls is FileInputPropertiesConverter

    def test_tfileinputproperties_in_type_list(self):
        assert "tFileInputProperties" in REGISTRY.list_types()
