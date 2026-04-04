"""Tests for FileInputRawConverter (tFileInputRaw -> v1 FileInputRaw config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_raw import (
    FileInputRawConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="fir_1",
               component_type="tFileInputRaw"):
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
            SchemaColumn(name="content", type="id_String", nullable=True, length=500),
            SchemaColumn(name="line_num", type="id_Integer", nullable=False, key=True, length=10),
        ]
    }


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        """tFileInputRaw maps to FileInputRawConverter in the registry."""
        assert REGISTRY.get("tFileInputRaw") is FileInputRawConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filename_default(self):
        """FILENAME defaults to empty string."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_as_string_default(self):
        """AS_STRING defaults to True per _java.xml."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["as_string"] is True

    def test_as_bytearray_default(self):
        """AS_BYTEARRAY defaults to False per _java.xml."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["as_bytearray"] is False

    def test_as_inputstream_default(self):
        """AS_INPUTSTREAM defaults to False per _java.xml."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["as_inputstream"] is False

    def test_encoding_default(self):
        """ENCODING defaults to 'ISO-8859-15' per _java.xml."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_die_on_error_default(self):
        """DIE_ON_ERROR defaults to False per _java.xml."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filename_extracted(self):
        """Quoted FILENAME value is extracted with quotes stripped."""
        node = _make_node(params={"FILENAME": '"path/to/file.raw"'})
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "path/to/file.raw"

    def test_as_string_false(self):
        """AS_STRING 'false' is extracted as boolean False."""
        node = _make_node(params={"AS_STRING": "false"})
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["as_string"] is False

    def test_as_bytearray_true(self):
        """AS_BYTEARRAY 'true' is extracted as boolean True."""
        node = _make_node(params={"AS_BYTEARRAY": "true"})
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["as_bytearray"] is True

    def test_as_inputstream_true(self):
        """AS_INPUTSTREAM 'true' is extracted as boolean True."""
        node = _make_node(params={"AS_INPUTSTREAM": "true"})
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["as_inputstream"] is True

    def test_encoding_custom(self):
        """Quoted ENCODING value is extracted with quotes stripped."""
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_die_on_error_true(self):
        """DIE_ON_ERROR 'true' is extracted as boolean True."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS defaults to False."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS 'true' is extracted as boolean True."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """LABEL defaults to empty string."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """Quoted LABEL value is extracted with quotes stripped."""
        node = _make_node(params={"LABEL": '"raw_input_step"'})
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "raw_input_step"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_is_dict_with_input_output(self):
        """Schema is a dict with 'input' and 'output' keys per D-41."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputRawConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert isinstance(schema, dict)
        assert "input" in schema
        assert "output" in schema

    def test_schema_input_empty(self):
        """FileInputRaw is a source component -- input schema is always empty."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_output_populated(self):
        """Output schema is populated when node has FLOW schema columns."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputRawConverter().convert(node, [], {})
        output = result.component["schema"]["output"]
        assert len(output) == 2
        assert output[0]["name"] == "content"
        assert output[1]["name"] == "line_num"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps (per D-36: per-feature)."""

    def test_needs_review_count(self):
        """Exactly 2 needs_review entries (as_bytearray + as_inputstream)."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert len(result.needs_review) == 2

    def test_needs_review_as_bytearray(self):
        """One needs_review entry mentions 'as_bytearray'."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("as_bytearray" in i for i in issues)

    def test_needs_review_as_inputstream(self):
        """One needs_review entry mentions 'as_inputstream'."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("as_inputstream" in i for i in issues)

    def test_all_needs_review_are_engine_gap(self):
        """All needs_review entries have severity 'engine_gap'."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries include the component ID."""
        node = _make_node(component_id="fir_test")
        result = FileInputRawConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "fir_test"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config dict contains all 8 expected keys (6 unique + 2 framework)."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputRawConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "filename", "as_string", "as_bytearray", "as_inputstream",
            "encoding", "die_on_error",
            "tstatcatcher_stats", "label",
        }
        missing = expected_keys - set(cfg.keys())
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify _build_component_dict output structure."""

    def test_has_id(self):
        """Component dict has 'id' matching node.component_id."""
        node = _make_node(component_id="fir_42")
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["id"] == "fir_42"

    def test_has_type(self):
        """Component dict has 'type' == 'FileInputRaw' (engine class name)."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["type"] == "FileInputRaw"

    def test_has_original_type(self):
        """Component dict has 'original_type' == 'tFileInputRaw'."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileInputRaw"

    def test_has_config(self):
        """Component dict has 'config' key."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema(self):
        """Component dict has 'schema' key."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert "schema" in result.component

    def test_has_position(self):
        """Component dict has 'position' key."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_has_inputs_outputs(self):
        """Component dict has 'inputs' and 'outputs' keys (empty lists)."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node()
        result = FileInputRawConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
