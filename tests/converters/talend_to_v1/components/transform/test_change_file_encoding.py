"""Tests for ChangeFileEncodingConverter (tChangeFileEncoding -> v1 tChangeFileEncoding config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.change_file_encoding import (
    ChangeFileEncodingConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="cfe_1",
               component_type="tChangeFileEncoding"):
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
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
        ]
    }


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tChangeFileEncoding") is ChangeFileEncodingConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_use_inencoding_default_false(self):
        """USE_INENCODING defaults to False per _java.xml."""
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["use_inencoding"] is False

    def test_inencoding_default(self):
        """INENCODING defaults to 'ISO-8859-15' per _java.xml ENCODING_TYPE (FIXED from empty)."""
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["inencoding"] == "ISO-8859-15"

    def test_infile_name_default(self):
        """INFILE_NAME defaults to empty string (file paths are job-specific)."""
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["infile_name"] == ""

    def test_outfile_name_default(self):
        """OUTFILE_NAME defaults to empty string (file paths are job-specific)."""
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["outfile_name"] == ""

    def test_encoding_default(self):
        """ENCODING defaults to 'ISO-8859-15' per _java.xml ENCODING_TYPE (FIXED from empty)."""
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_buffersize_default(self):
        """BUFFERSIZE defaults to '8192' per _java.xml TEXT type (str for expression support)."""
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["buffersize"] == "8192"

    def test_create_default_true(self):
        """CREATE defaults to True per _java.xml CHECK (FIXED from False)."""
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["create"] is True

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_use_inencoding_true(self):
        """USE_INENCODING='true' -> True."""
        node = _make_node(params={"USE_INENCODING": "true"})
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["use_inencoding"] is True

    def test_encoding_custom(self):
        """ENCODING='"UTF-8"' -> 'UTF-8'."""
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_inencoding_custom(self):
        """INENCODING='"Shift_JIS"' -> 'Shift_JIS'."""
        node = _make_node(params={"INENCODING": '"Shift_JIS"'})
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["inencoding"] == "Shift_JIS"

    def test_buffersize_custom(self):
        """BUFFERSIZE='"16384"' -> '16384'."""
        node = _make_node(params={"BUFFERSIZE": '"16384"'})
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["buffersize"] == "16384"

    def test_infile_name_custom(self):
        """INFILE_NAME='"/data/input.txt"' -> '/data/input.txt'."""
        node = _make_node(params={"INFILE_NAME": '"/data/input.txt"'})
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["infile_name"] == "/data/input.txt"

    def test_outfile_name_custom(self):
        """OUTFILE_NAME='"/data/output.txt"' -> '/data/output.txt'."""
        node = _make_node(params={"OUTFILE_NAME": '"/data/output.txt"'})
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["outfile_name"] == "/data/output.txt"

    def test_create_false(self):
        """CREATE='false' -> False."""
        node = _make_node(params={"CREATE": "false"})
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["create"] is False


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction (utility: input=[], output=[])."""

    def test_utility_schema_empty(self):
        """tChangeFileEncoding is a utility component -- no data flow schema."""
        node = _make_node(schema=_make_schema_columns())
        result = ChangeFileEncodingConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == []
        assert schema["output"] == []

    def test_schema_empty_no_schema(self):
        """Schema stays empty even when no schema columns provided."""
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review per D-84/D-27 (no engine)."""
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_engine_gap(self):
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_no_engine(self):
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert "No v1 engine implementation" in result.needs_review[0]["issue"]

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config should have 7 unique + 2 framework keys = 9 total."""
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        expected_keys = {
            "use_inencoding", "inencoding", "infile_name", "outfile_name",
            "encoding", "buffersize", "create",
            "tstatcatcher_stats", "label",
        }
        actual_config_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_config_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify component wrapper structure."""

    def test_has_type(self):
        """No-engine: type_name='tChangeFileEncoding' per D-43."""
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["type"] == "tChangeFileEncoding"

    def test_has_original_type(self):
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert result.component["original_type"] == "tChangeFileEncoding"

    def test_has_config_key(self):
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema_key(self):
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert "schema" in result.component

    def test_result_is_component_result(self):
        node = _make_node()
        result = ChangeFileEncodingConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
