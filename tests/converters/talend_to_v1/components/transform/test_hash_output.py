"""Tests for HashOutputConverter (tHashOutput -> tHashOutput)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.hash_output import (
    HashOutputConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="hash_output_1",
               component_type="tHashOutput"):
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
# Registration
# ------------------------------------------------------------------

class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tHashOutput") is HashOutputConverter


# ------------------------------------------------------------------
# Defaults (8 unique + 2 framework = 10 total)
# ------------------------------------------------------------------

class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_link_with_default_false(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["link_with"] is False

    def test_list_default_empty(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["list"] == ""

    def test_data_write_model_default_memory(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["data_write_model"] == "MEMORY"

    def test_base_file_path_default(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["base_file_path"] == ""

    def test_memory_heap_max_size_default_2(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["memory_heap_max_size"] == "2"

    def test_keys_management_default_keep_all(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["keys_management"] == "KEEP_ALL"

    def test_append_default_true(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["append"] is True

    def test_hash_key_from_input_connector_default_false(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["hash_key_from_input_connector"] is False

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


# ------------------------------------------------------------------
# Parameter Extraction
# ------------------------------------------------------------------

class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_link_with_true(self):
        node = _make_node(params={"LINK_WITH": "true"})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["link_with"] is True

    def test_list_custom(self):
        node = _make_node(params={"LIST": '"tHashInput_1"'})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["list"] == "tHashInput_1"

    def test_data_write_model_persistent(self):
        node = _make_node(params={"DATA_WRITE_MODEL": '"PERSISTENT"'})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["data_write_model"] == "PERSISTENT"

    def test_data_write_model_memory(self):
        node = _make_node(params={"DATA_WRITE_MODEL": '"MEMORY"'})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["data_write_model"] == "MEMORY"

    def test_base_file_path_custom(self):
        node = _make_node(params={"BASE_FILE_PATH": '"/tmp/hash_data"'})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["base_file_path"] == "/tmp/hash_data"

    def test_memory_heap_max_size_custom(self):
        node = _make_node(params={"MEMORY_HEAP_MAX_SIZE": '"4"'})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["memory_heap_max_size"] == "4"

    def test_keys_management_keep_first(self):
        node = _make_node(params={"KEYS_MANAGEMENT": '"KEEP_FIRST"'})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["keys_management"] == "KEEP_FIRST"

    def test_keys_management_keep_last(self):
        node = _make_node(params={"KEYS_MANAGEMENT": '"KEEP_LAST"'})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["keys_management"] == "KEEP_LAST"

    def test_append_false(self):
        node = _make_node(params={"APPEND": "false"})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["append"] is False

    def test_hash_key_from_input_connector_true(self):
        node = _make_node(params={"HASH_KEY_FROM_INPUT_CONNECTOR": "true"})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["hash_key_from_input_connector"] is True

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"hash_store"'})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "hash_store"


# ------------------------------------------------------------------
# Framework Params
# ------------------------------------------------------------------

class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


# ------------------------------------------------------------------
# Schema (passthrough: input == output)
# ------------------------------------------------------------------

class TestSchema:
    """Verify schema extraction -- passthrough (input == output)."""

    def test_schema_passthrough(self):
        node = _make_node(schema=_make_schema_columns())
        result = HashOutputConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 2

    def test_schema_column_details(self):
        node = _make_node(schema=_make_schema_columns())
        result = HashOutputConverter().convert(node, [], {})
        cols = result.component["schema"]["input"]
        assert cols[0]["name"] == "id"
        assert cols[0]["nullable"] is False
        assert cols[0]["key"] is True
        assert cols[1]["name"] == "name"
        assert cols[1]["nullable"] is True

    def test_empty_schema(self):
        node = _make_node(schema={})
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


# ------------------------------------------------------------------
# Needs Review (1 consolidated per D-84/D-27)
# ------------------------------------------------------------------

class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_severity(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = HashOutputConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


# ------------------------------------------------------------------
# Completeness (10 config keys: 8 unique + 2 framework)
# ------------------------------------------------------------------

class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = HashOutputConverter().convert(node, [], {})
        expected_keys = {
            "link_with", "list", "data_write_model", "base_file_path",
            "memory_heap_max_size", "keys_management", "append",
            "hash_key_from_input_connector",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_no_extra_config_keys(self):
        node = _make_node(schema=_make_schema_columns())
        result = HashOutputConverter().convert(node, [], {})
        expected_keys = {
            "link_with", "list", "data_write_model", "base_file_path",
            "memory_heap_max_size", "keys_management", "append",
            "hash_key_from_input_connector",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        extra = actual_keys - expected_keys
        assert not extra, f"Extra config keys: {extra}"


# ------------------------------------------------------------------
# Component Structure
# ------------------------------------------------------------------

class TestComponentStructure:
    """Verify _build_component_dict wrapper structure."""

    def test_type_name(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["type"] == "tHashOutput"

    def test_original_type(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["original_type"] == "tHashOutput"

    def test_component_id(self):
        node = _make_node(component_id="my_hash_1")
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["id"] == "my_hash_1"

    def test_position(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_inputs_outputs_empty(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_returns_component_result(self):
        node = _make_node()
        result = HashOutputConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
