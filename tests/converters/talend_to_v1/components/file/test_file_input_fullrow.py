"""Tests for FileInputFullRowConverter (tFileInputFullRow -> v1 FileInputFullRowComponent config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_fullrow import (
    FileInputFullRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="fifr_1",
               component_type="tFileInputFullRow"):
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
            SchemaColumn(name="line", type="id_String", nullable=True, length=2000),
            SchemaColumn(name="row_num", type="id_Integer", nullable=False, key=True, length=10),
        ]
    }


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        """tFileInputFullRow maps to FileInputFullRowConverter in the registry."""
        assert REGISTRY.get("tFileInputFullRow") is FileInputFullRowConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filename_default(self):
        """FILENAME defaults to empty string."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_row_separator_default(self):
        """ROWSEPARATOR defaults to '\\n'."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["row_separator"] == "\\n"

    def test_header_rows_default(self):
        """HEADER defaults to 0."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["header_rows"] == 0

    def test_footer_rows_default(self):
        """FOOTER defaults to 0."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["footer_rows"] == 0

    def test_limit_default(self):
        """LIMIT defaults to empty string (no limit)."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == ""

    def test_remove_empty_row_default(self):
        """REMOVE_EMPTY_ROW defaults to True per _java.xml."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["remove_empty_row"] is True

    def test_encoding_default(self):
        """ENCODING defaults to 'ISO-8859-15' per _java.xml."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_random_default(self):
        """RANDOM defaults to False per _java.xml."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["random"] is False

    def test_nb_random_default(self):
        """NB_RANDOM defaults to 10 per _java.xml."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["nb_random"] == 10


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filename_extracted(self):
        """Quoted FILENAME value is extracted with quotes stripped."""
        node = _make_node(params={"FILENAME": '"/data/input.txt"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "/data/input.txt"

    def test_row_separator_custom(self):
        """Custom ROWSEPARATOR value is extracted."""
        node = _make_node(params={"ROWSEPARATOR": '"\\r\\n"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["row_separator"] == "\\r\\n"

    def test_header_rows_extracted(self):
        """HEADER integer value is extracted."""
        node = _make_node(params={"HEADER": "5"})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["header_rows"] == 5

    def test_footer_rows_extracted(self):
        """FOOTER integer value is extracted."""
        node = _make_node(params={"FOOTER": "3"})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["footer_rows"] == 3

    def test_limit_extracted(self):
        """Quoted LIMIT value is extracted as string."""
        node = _make_node(params={"LIMIT": '"500"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == "500"
        assert isinstance(result.component["config"]["limit"], str)

    def test_remove_empty_row_false(self):
        """REMOVE_EMPTY_ROW 'false' is extracted as boolean False."""
        node = _make_node(params={"REMOVE_EMPTY_ROW": "false"})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["remove_empty_row"] is False

    def test_encoding_custom(self):
        """Quoted ENCODING value is extracted with quotes stripped."""
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_random_true(self):
        """RANDOM 'true' is extracted as boolean True."""
        node = _make_node(params={"RANDOM": "true"})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["random"] is True

    def test_nb_random_extracted(self):
        """NB_RANDOM integer value is extracted."""
        node = _make_node(params={"NB_RANDOM": "25"})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["nb_random"] == 25

    def test_int_params_from_quoted_strings(self):
        """Integer params handle quoted string values."""
        node = _make_node(params={
            "HEADER": '"3"',
            "FOOTER": '"1"',
            "NB_RANDOM": '"50"',
        })
        result = FileInputFullRowConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["header_rows"] == 3
        assert cfg["footer_rows"] == 1
        assert cfg["nb_random"] == 50


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS defaults to False."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS 'true' is extracted as boolean True."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """LABEL defaults to empty string."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """Quoted LABEL value is extracted with quotes stripped."""
        node = _make_node(params={"LABEL": '"fullrow_step"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "fullrow_step"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_is_dict_with_input_output(self):
        """Schema is a dict with 'input' and 'output' keys per D-41."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputFullRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert isinstance(schema, dict)
        assert "input" in schema
        assert "output" in schema

    def test_schema_input_empty(self):
        """FileInputFullRow is a source component -- input schema is always empty."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_output_populated(self):
        """Output schema is populated when node has FLOW schema columns."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputFullRowConverter().convert(node, [], {})
        output = result.component["schema"]["output"]
        assert len(output) == 2
        assert output[0]["name"] == "line"
        assert output[1]["name"] == "row_num"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps (per D-36: per-feature)."""

    def test_needs_review_header_rows(self):
        """One needs_review entry mentions 'header_rows'."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("header_rows" in i for i in issues)

    def test_needs_review_footer_rows(self):
        """One needs_review entry mentions 'footer_rows'."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("footer_rows" in i for i in issues)

    def test_needs_review_random(self):
        """One needs_review entry mentions 'random'."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("random" in i for i in issues)

    def test_needs_review_nb_random(self):
        """One needs_review entry mentions 'nb_random'."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("nb_random" in i for i in issues)

    def test_all_needs_review_are_engine_gap(self):
        """All needs_review entries have severity 'engine_gap'."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries include the component ID."""
        node = _make_node(component_id="fifr_test")
        result = FileInputFullRowConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "fifr_test"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config dict contains all 10 expected keys (8 unique + 2 framework)."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputFullRowConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "filename", "row_separator", "header_rows", "footer_rows",
            "limit", "remove_empty_row", "encoding", "random", "nb_random",
            "tstatcatcher_stats", "label",
        }
        missing = expected_keys - set(cfg.keys())
        assert not missing, f"Missing config keys: {missing}"

    def test_no_extra_config_keys(self):
        """Config dict does not contain unexpected keys (e.g., phantom die_on_error)."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputFullRowConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "filename", "row_separator", "header_rows", "footer_rows",
            "limit", "remove_empty_row", "encoding", "random", "nb_random",
            "tstatcatcher_stats", "label",
        }
        extra = set(cfg.keys()) - expected_keys
        assert not extra, f"Unexpected config keys: {extra}"


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_die_on_error_not_in_config(self):
        """DIE_ON_ERROR is not in _java.xml for tFileInputFullRow -- must not be in config."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]


class TestComponentStructure:
    """Verify _build_component_dict output structure."""

    def test_has_id(self):
        """Component dict has 'id' matching node.component_id."""
        node = _make_node(component_id="fifr_42")
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["id"] == "fifr_42"

    def test_has_type(self):
        """Component dict has 'type' == 'FileInputFullRowComponent' (engine class name per D-43)."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["type"] == "FileInputFullRowComponent"

    def test_has_original_type(self):
        """Component dict has 'original_type' == 'tFileInputFullRow'."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileInputFullRow"

    def test_has_config(self):
        """Component dict has 'config' key."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema(self):
        """Component dict has 'schema' key."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert "schema" in result.component

    def test_has_position(self):
        """Component dict has 'position' key."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_has_inputs_outputs(self):
        """Component dict has 'inputs' and 'outputs' keys (empty lists)."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node()
        result = FileInputFullRowConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)


class TestWarnings:
    """Verify warning behavior."""

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_no_warnings_with_filename(self):
        """No warnings when FILENAME is provided."""
        node = _make_node(params={"FILENAME": '"/data/file.txt"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert len(result.warnings) == 0
