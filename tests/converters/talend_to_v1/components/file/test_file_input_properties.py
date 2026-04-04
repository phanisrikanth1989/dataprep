"""Tests for FileInputPropertiesConverter (tFileInputProperties -> tFileInputProperties).

No engine implementation exists. Red scorecard per D-37.
"""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_properties import (
    FileInputPropertiesConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="tFileInputProperties_1",
               component_type="tFileInputProperties"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="key", type="id_String", nullable=False, key=True, length=255),
            SchemaColumn(name="value", type="id_String", nullable=True, length=1000),
        ]
    }


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tFileInputProperties") is FileInputPropertiesConverter

    def test_in_type_list(self):
        assert "tFileInputProperties" in REGISTRY.list_types()


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_file_format_default(self):
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["file_format"] == "PROPERTIES_FORMAT"

    def test_retrive_mode_default(self):
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["retrive_mode"] == "RETRIVE_BY_SECTION"

    def test_section_name_default(self):
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["section_name"] == "section"

    def test_filename_default(self):
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_encoding_default(self):
        """Encoding default is ISO-8859-15 per _java.xml, NOT UTF-8."""
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_file_format_xml(self):
        node = _make_node(params={"FILE_FORMAT": '"XML_FORMAT"'})
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["file_format"] == "XML_FORMAT"

    def test_retrive_mode_by_key(self):
        node = _make_node(params={"RETRIVE_MODE": '"RETRIVE_BY_KEY"'})
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["retrive_mode"] == "RETRIVE_BY_KEY"

    def test_section_name_custom(self):
        node = _make_node(params={"SECTION_NAME": '"my_section"'})
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["section_name"] == "my_section"

    def test_filename_extracted(self):
        node = _make_node(params={"FILENAME": '"props.cfg"'})
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "props.cfg"

    def test_encoding_utf8(self):
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_file_format_properties(self):
        node = _make_node(params={"FILE_FORMAT": '"PROPERTIES_FORMAT"'})
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["file_format"] == "PROPERTIES_FORMAT"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_output_populated(self):
        """Source component populates output schema."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputPropertiesConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == []
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "key"
        assert schema["output"][1]["name"] == "value"

    def test_input_schema_always_empty(self):
        """Source component has empty input schema."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_empty_when_no_flow(self):
        """Empty output schema when no FLOW columns defined."""
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_single_consolidated(self):
        """Single consolidated needs_review per D-37 (no engine)."""
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_no_engine_message(self):
        """needs_review mentions missing engine implementation."""
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert "No v1 engine implementation" in result.needs_review[0]["issue"]

    def test_engine_gap_severity(self):
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = FileInputPropertiesConverter().convert(node, [], {})
        expected_keys = {
            "file_format", "retrive_mode", "section_name",
            "filename", "encoding",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_no_extra_keys(self):
        """No unexpected keys beyond the 7 expected."""
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        expected_keys = {
            "file_format", "retrive_mode", "section_name",
            "filename", "encoding",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        extra = actual_keys - expected_keys
        assert not extra, f"Unexpected config keys: {extra}"


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_no_die_on_error(self):
        """DIE_ON_ERROR is phantom -- not in _java.xml."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]


class TestComponentStructure:
    """Verify the component dict structure."""

    def test_type(self):
        """No-engine component uses Talend name per D-43."""
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["type"] == "tFileInputProperties"

    def test_original_type(self):
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileInputProperties"

    def test_id(self):
        node = _make_node(component_id="tFileInputProperties_1")
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["id"] == "tFileInputProperties_1"

    def test_position(self):
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_top_level_keys(self):
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        expected = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected

    def test_inputs_outputs_empty(self):
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_returns_component_result(self):
        node = _make_node()
        result = FileInputPropertiesConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
