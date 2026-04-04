"""Tests for PivotToColumnsDelimitedConverter (tPivotToColumnsDelimited -> PivotToColumnsDelimited)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.registry import REGISTRY
from src.converters.talend_to_v1.components.transform.pivot_to_columns_delimited import (
    PivotToColumnsDelimitedConverter,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="pivot_1",
               component_type="tPivotToColumnsDelimited"):
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
            SchemaColumn(name="region", type="id_String", nullable=False, key=True),
            SchemaColumn(name="product", type="id_String", nullable=True),
            SchemaColumn(name="sales", type="id_Double", nullable=True),
        ]
    }


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tPivotToColumnsDelimited") is PivotToColumnsDelimitedConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_pivot_column_default_empty(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["pivot_column"] == ""

    def test_aggregation_column_default_empty(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["aggregation_column"] == ""

    def test_aggregation_function_default_sum(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["aggregation_function"] == "sum"

    def test_groupbys_default_empty(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["groupbys"] == []

    def test_filename_default(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_create_default_true(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["create"] is True

    def test_rowseparator_default(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["rowseparator"] == "\\n"

    def test_fieldseparator_default(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["fieldseparator"] == ";"

    def test_advanced_separator_default_false(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    def test_csv_option_default_false(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["csv_option"] is False

    def test_escape_char_default(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["escape_char"] == "\""

    def test_text_enclosure_default(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["text_enclosure"] == "\""

    def test_encoding_default(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_delete_emptyfile_default_false(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["delete_emptyfile"] is False

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_pivot_column_extracted(self):
        node = _make_node(params={"PIVOT_COLUMN": '"product"'})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["pivot_column"] == "product"

    def test_aggregation_column_extracted(self):
        node = _make_node(params={"AGGREGATION_COLUMN": '"sales"'})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["aggregation_column"] == "sales"

    def test_aggregation_function_custom(self):
        node = _make_node(params={"AGGREGATION_FUNCTION": '"avg"'})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["aggregation_function"] == "avg"

    def test_groupbys_parsing(self):
        """GROUPBYS TABLE stride-1 -> list of column names."""
        node = _make_node(params={
            "GROUPBYS": [
                {"value": '"region"'},
                {"value": '"quarter"'},
            ],
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["groupbys"] == ["region", "quarter"]

    def test_groupbys_single(self):
        node = _make_node(params={
            "GROUPBYS": [{"value": '"region"'}],
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["groupbys"] == ["region"]

    def test_groupbys_empty_values_skipped(self):
        """Entries with empty string values after quote-stripping are skipped."""
        node = _make_node(params={
            "GROUPBYS": [
                {"value": '"region"'},
                {"value": '""'},
                {"value": '"year"'},
            ],
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["groupbys"] == ["region", "year"]

    def test_groupbys_not_a_list_warns(self):
        """If GROUPBYS is not a list, produce a warning and return empty list."""
        node = _make_node(params={"GROUPBYS": "bad_data"})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["groupbys"] == []
        assert any("not a list" in w for w in result.warnings)

    def test_filename_extracted(self):
        node = _make_node(params={"FILENAME": '"/tmp/output.csv"'})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "/tmp/output.csv"

    def test_create_false(self):
        node = _make_node(params={"CREATE": "false"})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["create"] is False

    def test_encoding_custom(self):
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_advanced_separator_true(self):
        node = _make_node(params={"ADVANCED_SEPARATOR": "true"})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is True

    def test_csv_option_true(self):
        node = _make_node(params={"CSV_OPTION": "true"})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["csv_option"] is True

    def test_delete_emptyfile_true(self):
        node = _make_node(params={"DELETE_EMPTYFILE": "true"})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["delete_emptyfile"] is True

    def test_custom_separators(self):
        node = _make_node(params={
            "THOUSANDS_SEPARATOR": '"."',
            "DECIMAL_SEPARATOR": '","',
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["thousands_separator"] == "."
        assert cfg["decimal_separator"] == ","

    def test_escape_and_enclosure(self):
        node = _make_node(params={
            "ESCAPE_CHAR": '"\'"',
            "TEXT_ENCLOSURE": '"\'"',
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["escape_char"] == "'"
        assert cfg["text_enclosure"] == "'"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_pivot"'})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_pivot"

    def test_label_default_empty(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestSchema:
    """Verify schema extraction."""

    def test_schema_passthrough(self):
        """PivotToColumnsDelimited passes the schema through: input == output."""
        node = _make_node(schema=_make_schema_columns())
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "region"

    def test_empty_schema(self):
        """When no FLOW schema is present, input and output are empty lists."""
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Minimal conversion produces exactly 7 engine_gap needs_review entries."""
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert len(result.needs_review) == 7

    def test_needs_review_severity(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_needs_review_covers_all_engine_gaps(self):
        """All 7 engine gap keys are mentioned in needs_review issues."""
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        engine_gap_keys = {
            "advanced_separator", "thousands_separator", "decimal_separator",
            "csv_option", "escape_char", "text_enclosure", "delete_emptyfile",
        }
        mentioned_keys = set()
        for entry in result.needs_review:
            for key in engine_gap_keys:
                if key in entry["issue"]:
                    mentioned_keys.add(key)
        assert mentioned_keys == engine_gap_keys

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node(params={
            "TSTATCATCHER_STATS": "true",
            "LABEL": '"my_label"',
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        expected_keys = {
            "pivot_column", "aggregation_column", "aggregation_function",
            "groupbys", "filename", "create", "rowseparator", "fieldseparator",
            "advanced_separator", "thousands_separator", "decimal_separator",
            "csv_option", "escape_char", "text_enclosure", "encoding",
            "delete_emptyfile", "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_no_extra_keys(self):
        """No unexpected keys in config."""
        node = _make_node(schema=_make_schema_columns())
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        expected_keys = {
            "pivot_column", "aggregation_column", "aggregation_function",
            "groupbys", "filename", "create", "rowseparator", "fieldseparator",
            "advanced_separator", "thousands_separator", "decimal_separator",
            "csv_option", "escape_char", "text_enclosure", "encoding",
            "delete_emptyfile", "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        extra = actual_keys - expected_keys
        assert not extra, f"Extra config keys: {extra}"


class TestComponentStructure:
    """Verify _build_component_dict wrapper structure."""

    def test_component_has_required_keys(self):
        node = _make_node(params={
            "PIVOT_COLUMN": '"product"',
            "AGGREGATION_COLUMN": '"sales"',
            "FILENAME": '"/tmp/output.csv"',
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        comp = result.component
        assert comp["id"] == "pivot_1"
        assert comp["type"] == "PivotToColumnsDelimited"
        assert comp["original_type"] == "tPivotToColumnsDelimited"
        assert comp["position"] == {"x": 100, "y": 200}
        assert "config" in comp
        assert "schema" in comp
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_returns_component_result(self):
        node = _make_node()
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_warnings_for_empty_required_fields(self):
        """Empty pivot_column, aggregation_column, and filename trigger warnings."""
        node = _make_node(params={})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        assert any("PIVOT_COLUMN" in w for w in result.warnings)
        assert any("AGGREGATION_COLUMN" in w for w in result.warnings)
        assert any("FILENAME" in w for w in result.warnings)

    def test_full_config_no_warnings(self):
        """All parameters supplied -- no warnings expected for required fields."""
        node = _make_node(params={
            "PIVOT_COLUMN": '"product"',
            "AGGREGATION_COLUMN": '"sales"',
            "AGGREGATION_FUNCTION": '"sum"',
            "GROUPBYS": [{"value": '"region"'}, {"value": '"quarter"'}],
            "FILENAME": '"/tmp/output.csv"',
            "ROWSEPARATOR": '"\\n"',
            "FIELDSEPARATOR": '","',
            "ENCODING": '"UTF-8"',
            "CREATE": "true",
            "ADVANCED_SEPARATOR": "true",
            "THOUSANDS_SEPARATOR": '"."',
            "DECIMAL_SEPARATOR": '","',
            "CSV_OPTION": "true",
            "ESCAPE_CHAR": '"\'"',
            "TEXT_ENCLOSURE": '"\'"',
            "DELETE_EMPTYFILE": "true",
            "TSTATCATCHER_STATS": "true",
            "LABEL": '"my_pivot"',
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})
        # Should NOT warn about PIVOT_COLUMN, AGGREGATION_COLUMN, or FILENAME
        assert not any("PIVOT_COLUMN" in w for w in result.warnings)
        assert not any("AGGREGATION_COLUMN" in w for w in result.warnings)
        assert not any("FILENAME" in w for w in result.warnings)
