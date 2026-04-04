"""Tests for DenormalizeConverter (tDenormalize -> v1 Denormalize config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.denormalize import (
    DenormalizeConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="dn_1",
               component_type="tDenormalize"):
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
            SchemaColumn(name="group_key", type="id_String", nullable=False, key=True, length=50),
            SchemaColumn(name="value", type="id_String", nullable=True, length=100),
            SchemaColumn(name="count", type="id_Integer", nullable=True, length=10),
        ]
    }


def _make_denormalize_table(*rows):
    """Generate DENORMALIZE_COLUMNS TABLE data with stride-3 per row.

    rows: list of tuples (input_column, delimiter, merge)
    """
    result = []
    for col, delim, merge in rows:
        result.append({"elementRef": "INPUT_COLUMN", "value": col})
        result.append({"elementRef": "DELIMITER", "value": delim})
        result.append({"elementRef": "MERGE", "value": str(merge).lower()})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tDenormalize") is DenormalizeConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_denormalize_columns_default_empty(self):
        node = _make_node()
        result = DenormalizeConverter().convert(node, [], {})
        assert result.component["config"]["denormalize_columns"] == []

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = DenormalizeConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = DenormalizeConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_denormalize_columns_single(self):
        """1 group -> [{input_column: 'col1', delimiter: ';', merge: False}]."""
        table = _make_denormalize_table(("col1", ";", False))
        node = _make_node(params={"DENORMALIZE_COLUMNS": table})
        result = DenormalizeConverter().convert(node, [], {})
        cols = result.component["config"]["denormalize_columns"]
        assert len(cols) == 1
        assert cols[0] == {"input_column": "col1", "delimiter": ";", "merge": False}

    def test_denormalize_columns_multiple(self):
        """2 groups parsed correctly."""
        table = _make_denormalize_table(
            ("col_a", ",", False),
            ("col_b", "|", True),
        )
        node = _make_node(params={"DENORMALIZE_COLUMNS": table})
        result = DenormalizeConverter().convert(node, [], {})
        cols = result.component["config"]["denormalize_columns"]
        assert len(cols) == 2
        assert cols[0] == {"input_column": "col_a", "delimiter": ",", "merge": False}
        assert cols[1] == {"input_column": "col_b", "delimiter": "|", "merge": True}

    def test_denormalize_columns_custom_delimiter(self):
        """delimiter='|' extracted."""
        table = _make_denormalize_table(("col1", "|", False))
        node = _make_node(params={"DENORMALIZE_COLUMNS": table})
        result = DenormalizeConverter().convert(node, [], {})
        cols = result.component["config"]["denormalize_columns"]
        assert cols[0]["delimiter"] == "|"

    def test_denormalize_columns_merge_true(self):
        """merge='true' -> True."""
        table = _make_denormalize_table(("col1", ";", True))
        node = _make_node(params={"DENORMALIZE_COLUMNS": table})
        result = DenormalizeConverter().convert(node, [], {})
        cols = result.component["config"]["denormalize_columns"]
        assert cols[0]["merge"] is True

    def test_input_column_quotes_stripped(self):
        """INPUT_COLUMN values with surrounding quotes should be stripped."""
        table = [
            {"elementRef": "INPUT_COLUMN", "value": '"my_col"'},
            {"elementRef": "DELIMITER", "value": ";"},
            {"elementRef": "MERGE", "value": "false"},
        ]
        node = _make_node(params={"DENORMALIZE_COLUMNS": table})
        result = DenormalizeConverter().convert(node, [], {})
        cols = result.component["config"]["denormalize_columns"]
        assert cols[0]["input_column"] == "my_col"


class TestDenormalizeColumnsDefaults:
    """Verify defaults for individual fields within DENORMALIZE_COLUMNS entries."""

    def test_delimiter_default_semicolon(self):
        """Missing DELIMITER -> ';' per _java.xml."""
        table = [
            {"elementRef": "INPUT_COLUMN", "value": "col1"},
            {"elementRef": "UNKNOWN", "value": "x"},
            {"elementRef": "MERGE", "value": "false"},
        ]
        node = _make_node(params={"DENORMALIZE_COLUMNS": table})
        result = DenormalizeConverter().convert(node, [], {})
        cols = result.component["config"]["denormalize_columns"]
        assert cols[0]["delimiter"] == ";"

    def test_merge_default_false(self):
        """Missing MERGE -> False per _java.xml."""
        table = [
            {"elementRef": "INPUT_COLUMN", "value": "col1"},
            {"elementRef": "DELIMITER", "value": ";"},
            {"elementRef": "UNKNOWN", "value": "x"},
        ]
        node = _make_node(params={"DENORMALIZE_COLUMNS": table})
        result = DenormalizeConverter().convert(node, [], {})
        cols = result.component["config"]["denormalize_columns"]
        assert cols[0]["merge"] is False


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = DenormalizeConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = DenormalizeConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction (passthrough for transform)."""

    def test_schema_passthrough(self):
        node = _make_node(schema=_make_schema_columns())
        result = DenormalizeConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3

    def test_schema_columns_populated(self):
        node = _make_node(schema=_make_schema_columns())
        result = DenormalizeConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"][0]["name"] == "group_key"
        assert schema["input"][1]["name"] == "value"
        assert schema["input"][2]["name"] == "count"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Per-feature needs_review for engine gaps."""
        node = _make_node()
        result = DenormalizeConverter().convert(node, [], {})
        # Should have entries for engine gaps (delimiter default mismatch, null_as_empty engine-only)
        assert len(result.needs_review) >= 1

    def test_needs_review_engine_gap_severity(self):
        node = _make_node()
        result = DenormalizeConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"
            assert "component" in entry
            assert "issue" in entry

    def test_needs_review_merge_conditional(self):
        """merge=True triggers additional needs_review entry."""
        table = _make_denormalize_table(("col1", ";", True))
        node = _make_node(params={"DENORMALIZE_COLUMNS": table})
        result = DenormalizeConverter().convert(node, [], {})
        merge_entries = [e for e in result.needs_review if "merge" in e["issue"].lower()]
        assert len(merge_entries) == 1

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = DenormalizeConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_connection_format_not_in_config(self):
        """CONNECTION_FORMAT is phantom -- NOT in config keys."""
        node = _make_node(params={"CONNECTION_FORMAT": '"row"'})
        result = DenormalizeConverter().convert(node, [], {})
        assert "connection_format" not in result.component["config"]

    def test_null_as_empty_not_in_config(self):
        """NULL_AS_EMPTY is not in _java.xml -- should not be in config keys."""
        node = _make_node(params={"NULL_AS_EMPTY": "true"})
        result = DenormalizeConverter().convert(node, [], {})
        assert "null_as_empty" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """denormalize_columns + 2 framework keys."""
        node = _make_node(schema=_make_schema_columns())
        result = DenormalizeConverter().convert(node, [], {})
        expected_keys = {
            "denormalize_columns",
            "tstatcatcher_stats",
            "label",
        }
        actual_config_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_config_keys
        assert not missing, f"Missing config keys: {missing}"
        # No extra keys beyond expected
        extra = actual_config_keys - expected_keys
        assert not extra, f"Extra config keys (possible phantoms?): {extra}"


class TestComponentStructure:
    """Verify component wrapper structure."""

    def test_has_type(self):
        node = _make_node()
        result = DenormalizeConverter().convert(node, [], {})
        assert result.component["type"] == "Denormalize"

    def test_has_original_type(self):
        node = _make_node()
        result = DenormalizeConverter().convert(node, [], {})
        assert result.component["original_type"] == "tDenormalize"

    def test_has_all_wrapper_keys(self):
        node = _make_node()
        result = DenormalizeConverter().convert(node, [], {})
        expected = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected

    def test_result_is_component_result(self):
        node = _make_node()
        result = DenormalizeConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
