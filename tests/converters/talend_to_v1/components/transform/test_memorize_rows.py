"""Tests for MemorizeRowsConverter (tMemorizeRows -> tMemorizeRows)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.memorize_rows import (
    MemorizeRowsConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="tMemorizeRows_1",
               component_type="tMemorizeRows"):
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


def _make_specify_cols_data(rows):
    """Generate SPECIFY_COLS TABLE data with stride-1 per row.

    rows: list of str values for MEMORIZE_IT (e.g., ["true", "false"])
    """
    result = []
    for value in rows:
        result.append({"elementRef": "MEMORIZE_IT", "value": value})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tMemorizeRows") is MemorizeRowsConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_row_count_default(self):
        """ROW_COUNT defaults to '1' (str per TEXT type in _java.xml)."""
        node = _make_node()
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["row_count"] == "1"

    def test_specify_cols_default_empty(self):
        """SPECIFY_COLS defaults to empty list when not provided."""
        node = _make_node()
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["specify_cols"] == []

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_row_count_custom(self):
        """ROW_COUNT='"5"' -> '5' (str, not int)."""
        node = _make_node(params={"ROW_COUNT": '"5"'})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["row_count"] == "5"

    def test_row_count_expression(self):
        """ROW_COUNT='"context.rowCount"' -> 'context.rowCount' (expression support)."""
        node = _make_node(params={"ROW_COUNT": '"context.rowCount"'})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["row_count"] == "context.rowCount"

    def test_row_count_unquoted(self):
        """ROW_COUNT='3' -> '3' (unquoted numeric str)."""
        node = _make_node(params={"ROW_COUNT": "3"})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["row_count"] == "3"

    def test_specify_cols_parsing(self):
        """SPECIFY_COLS TABLE with MEMORIZE_IT boolean entries."""
        table_data = _make_specify_cols_data(["true", "false", "true"])
        node = _make_node(params={"SPECIFY_COLS": table_data})
        result = MemorizeRowsConverter().convert(node, [], {})
        cols = result.component["config"]["specify_cols"]
        assert len(cols) == 3
        assert cols[0] == {"memorize_it": True}
        assert cols[1] == {"memorize_it": False}
        assert cols[2] == {"memorize_it": True}

    def test_specify_cols_empty_list(self):
        """Empty SPECIFY_COLS TABLE returns empty list."""
        node = _make_node(params={"SPECIFY_COLS": []})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["specify_cols"] == []


class TestTableParsing:
    """Verify SPECIFY_COLS TABLE parsing edge cases."""

    def test_specify_cols_non_list_returns_empty(self):
        """Non-list value for SPECIFY_COLS returns empty list."""
        node = _make_node(params={"SPECIFY_COLS": "not_a_list"})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["specify_cols"] == []

    def test_specify_cols_non_dict_entries_skipped(self):
        """Non-dict entries in SPECIFY_COLS are skipped."""
        node = _make_node(params={"SPECIFY_COLS": ["not_a_dict", 42]})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["specify_cols"] == []

    def test_specify_cols_missing_elementref_skipped(self):
        """Entries without elementRef are skipped."""
        node = _make_node(params={"SPECIFY_COLS": [{"value": "true"}]})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["specify_cols"] == []

    def test_specify_cols_wrong_elementref_skipped(self):
        """Entries with wrong elementRef are skipped."""
        node = _make_node(params={"SPECIFY_COLS": [{"elementRef": "WRONG", "value": "true"}]})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["specify_cols"] == []

    def test_specify_cols_mixed_case_bool(self):
        """Boolean parsing handles various case formats."""
        table_data = [
            {"elementRef": "MEMORIZE_IT", "value": "True"},
            {"elementRef": "MEMORIZE_IT", "value": "FALSE"},
            {"elementRef": "MEMORIZE_IT", "value": "1"},
            {"elementRef": "MEMORIZE_IT", "value": "0"},
        ]
        node = _make_node(params={"SPECIFY_COLS": table_data})
        result = MemorizeRowsConverter().convert(node, [], {})
        cols = result.component["config"]["specify_cols"]
        assert len(cols) == 4
        assert cols[0]["memorize_it"] is True
        assert cols[1]["memorize_it"] is False
        assert cols[2]["memorize_it"] is True
        assert cols[3]["memorize_it"] is False


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction (passthrough: input == output)."""

    def test_schema_passthrough(self):
        """tMemorizeRows is passthrough: input schema == output schema."""
        node = _make_node(schema=_make_schema_columns())
        result = MemorizeRowsConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 2

    def test_schema_column_details(self):
        node = _make_node(schema=_make_schema_columns())
        result = MemorizeRowsConverter().convert(node, [], {})
        cols = result.component["schema"]["input"]
        assert cols[0]["name"] == "id"
        assert cols[0]["nullable"] is False
        assert cols[0]["key"] is True
        assert cols[1]["name"] == "name"
        assert cols[1]["nullable"] is True

    def test_empty_schema(self):
        node = _make_node(schema={})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review per D-27 (no engine)."""
        node = _make_node()
        result = MemorizeRowsConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_severity(self):
        node = _make_node()
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = MemorizeRowsConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_reset_on_condition_not_in_config(self):
        """RESET_ON_CONDITION is phantom -- must NOT appear in config."""
        node = _make_node(params={"RESET_ON_CONDITION": "true"})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert "reset_on_condition" not in result.component["config"]

    def test_condition_not_in_config(self):
        """CONDITION is phantom -- must NOT appear in config."""
        node = _make_node(params={"CONDITION": '"row.id == 0"'})
        result = MemorizeRowsConverter().convert(node, [], {})
        assert "condition" not in result.component["config"]

    def test_phantoms_ignored_even_when_present(self):
        """Both phantom params present -- neither appears in config."""
        node = _make_node(params={
            "RESET_ON_CONDITION": "true",
            "CONDITION": '"row.id == 0"',
            "ROW_COUNT": '"5"',
        })
        result = MemorizeRowsConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert "reset_on_condition" not in cfg
        assert "condition" not in cfg
        assert cfg["row_count"] == "5"


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = MemorizeRowsConverter().convert(node, [], {})
        expected_keys = {
            "row_count", "specify_cols",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_no_extra_config_keys(self):
        """Only expected keys present -- no phantom or unexpected keys."""
        node = _make_node(schema=_make_schema_columns())
        result = MemorizeRowsConverter().convert(node, [], {})
        expected_keys = {
            "row_count", "specify_cols",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        extra = actual_keys - expected_keys
        assert not extra, f"Extra config keys: {extra}"


class TestComponentStructure:
    """Verify the component wrapper structure."""

    def test_component_has_required_keys(self):
        node = _make_node(schema=_make_schema_columns())
        result = MemorizeRowsConverter().convert(node, [], {})
        comp = result.component
        assert set(comp.keys()) == {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }

    def test_type_name_is_tMemorizeRows(self):
        """type_name='tMemorizeRows' per D-43 (no-engine)."""
        node = _make_node()
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["type"] == "tMemorizeRows"

    def test_original_type(self):
        node = _make_node()
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["original_type"] == "tMemorizeRows"

    def test_inputs_outputs_empty(self):
        node = _make_node()
        result = MemorizeRowsConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_result_type(self):
        node = _make_node()
        result = MemorizeRowsConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
