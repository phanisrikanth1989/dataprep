"""Tests for FixedFlowInputConverter (tFixedFlowInput -> FixedFlowInputComponent).

Covers all 8 unique _java.xml params + 2 framework params. Validates:
- Defaults match _java.xml source of truth
- Param extraction for non-default values
- VALUES TABLE parsing (stride-2: SCHEMA_COLUMN, VALUE)
- INTABLE TABLE parsing (stride-N per schema)
- Framework params (tstatcatcher_stats, label)
- Source schema direction (input=[], output=[...])
- Phantom param exclusion (CONNECTION_FORMAT, DIE_ON_ERROR not in _java.xml)
- Completeness (all expected config keys present)
- needs_review entries for engine gaps
"""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.fixed_flow_input import (
    FixedFlowInputConverter,
    _parse_intable,
    _parse_values,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="tFixedFlowInput_1",
               component_type="tFixedFlowInput"):
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


def _make_values_data(rows):
    """Generate VALUES TABLE data with stride-2 (SCHEMA_COLUMN, VALUE) per row.

    rows: list of tuples (column_name, value)
    """
    result = []
    for col_name, value in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": col_name})
        result.append({"elementRef": "VALUE", "value": value})
    return result


def _make_intable_data(rows, columns):
    """Generate INTABLE TABLE data with stride-N per row.

    rows: list of tuples with values for each column
    columns: list of column names (elementRef names)
    """
    result = []
    for row_values in rows:
        for col_name, value in zip(columns, row_values):
            result.append({"elementRef": col_name, "value": value})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tFixedFlowInput") is FixedFlowInputConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_nb_rows_default(self):
        """NB_ROWS defaults to 1."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["nb_rows"] == 1

    def test_use_singlemode_default(self):
        """USE_SINGLEMODE defaults to True (RADIO)."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["use_singlemode"] is True

    def test_use_intable_default(self):
        """USE_INTABLE defaults to False (RADIO)."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["use_intable"] is False

    def test_use_inlinecontent_default(self):
        """USE_INLINECONTENT defaults to False (RADIO)."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["use_inlinecontent"] is False

    def test_row_separator_default(self):
        """ROWSEPARATOR defaults to '\\n'."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["row_separator"] == "\\n"

    def test_field_separator_default(self):
        """FIELDSEPARATOR defaults to ';'."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["field_separator"] == ";"

    def test_inline_content_default(self):
        """INLINECONTENT defaults to empty string."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["inline_content"] == ""

    def test_values_config_default(self):
        """VALUES defaults to empty list when missing."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["values_config"] == []

    def test_intable_default(self):
        """INTABLE defaults to empty list when missing."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["intable"] == []


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_nb_rows_extracted(self):
        node = _make_node(params={"NB_ROWS": "5"})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["nb_rows"] == 5

    def test_use_singlemode_false(self):
        node = _make_node(params={"USE_SINGLEMODE": "false"})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["use_singlemode"] is False

    def test_use_intable_true(self):
        node = _make_node(params={"USE_INTABLE": "true"})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["use_intable"] is True

    def test_use_inlinecontent_true(self):
        node = _make_node(params={"USE_INLINECONTENT": "true"})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["use_inlinecontent"] is True

    def test_row_separator_custom(self):
        node = _make_node(params={"ROWSEPARATOR": '"|"'})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["row_separator"] == "|"

    def test_field_separator_custom(self):
        node = _make_node(params={"FIELDSEPARATOR": '","'})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["field_separator"] == ","

    def test_inline_content_extracted(self):
        node = _make_node(params={"INLINECONTENT": '"hello;world"'})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["inline_content"] == "hello;world"


class TestValuesTable:
    """Verify VALUES TABLE parsing (stride-2: SCHEMA_COLUMN, VALUE)."""

    def test_values_empty(self):
        """Empty VALUES -> empty list."""
        node = _make_node(params={"VALUES": []})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["values_config"] == []

    def test_values_missing(self):
        """Missing VALUES -> empty list."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["values_config"] == []

    def test_values_parsed(self):
        """VALUES TABLE with column values is parsed correctly."""
        values_data = _make_values_data([
            ("id", '"1"'),
            ("name", '"Alice"'),
        ])
        node = _make_node(params={"VALUES": values_data})
        result = FixedFlowInputConverter().convert(node, [], {})
        values = result.component["config"]["values_config"]
        assert len(values) == 2
        assert values[0] == {"schema_column": "id", "value": "1"}
        assert values[1] == {"schema_column": "name", "value": "Alice"}

    def test_values_incomplete_stride_skipped(self):
        """Incomplete trailing group (< 2 entries) is skipped."""
        values_data = [
            {"elementRef": "SCHEMA_COLUMN", "value": "id"},
            {"elementRef": "VALUE", "value": '"1"'},
            {"elementRef": "SCHEMA_COLUMN", "value": "orphan"},
            # Missing VALUE entry
        ]
        node = _make_node(params={"VALUES": values_data})
        result = FixedFlowInputConverter().convert(node, [], {})
        values = result.component["config"]["values_config"]
        assert len(values) == 1
        assert values[0]["schema_column"] == "id"

    def test_values_quotes_stripped(self):
        """Surrounding quotes in VALUE entries are stripped."""
        values_data = _make_values_data([
            ('"col1"', '"hello"'),
        ])
        node = _make_node(params={"VALUES": values_data})
        result = FixedFlowInputConverter().convert(node, [], {})
        values = result.component["config"]["values_config"]
        assert values[0]["schema_column"] == "col1"
        assert values[0]["value"] == "hello"


class TestIntable:
    """Verify INTABLE TABLE parsing."""

    def test_intable_empty(self):
        """Empty INTABLE -> empty list."""
        node = _make_node(params={"INTABLE": []})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["intable"] == []

    def test_intable_missing(self):
        """Missing INTABLE -> empty list."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["intable"] == []

    def test_intable_not_list(self):
        """Non-list INTABLE -> empty list."""
        node = _make_node(params={"INTABLE": "invalid"})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["intable"] == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for source component."""

    def test_source_schema_direction(self):
        """Source component: input=[], output=[...]."""
        node = _make_node(schema=_make_schema_columns())
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []
        assert len(result.component["schema"]["output"]) == 2

    def test_schema_column_details(self):
        """Schema columns have correct field details."""
        node = _make_node(schema=_make_schema_columns())
        result = FixedFlowInputConverter().convert(node, [], {})
        output = result.component["schema"]["output"]
        assert output[0]["name"] == "id"
        assert output[0]["key"] is True
        assert output[0]["nullable"] is False
        assert output[1]["name"] == "name"
        assert output[1]["nullable"] is True

    def test_empty_schema(self):
        """No FLOW schema -> empty output list."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []
        assert result.component["schema"]["input"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Engine gap needs_review entries for known mismatches."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        # Should have per-feature needs_review for engine gaps
        assert len(result.needs_review) >= 1

    def test_needs_review_severity(self):
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FixedFlowInputConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """All 8 unique + 2 framework config keys present."""
        node = _make_node(schema=_make_schema_columns())
        result = FixedFlowInputConverter().convert(node, [], {})
        expected_keys = {
            # 8 unique params
            "nb_rows", "use_singlemode", "values_config",
            "use_intable", "intable",
            "use_inlinecontent", "row_separator", "field_separator",
            "inline_content",
            # Framework
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_no_unexpected_keys(self):
        """No phantom or extra keys in config."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        allowed_keys = {
            "nb_rows", "use_singlemode", "values_config",
            "use_intable", "intable",
            "use_inlinecontent", "row_separator", "field_separator",
            "inline_content",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        extra = actual_keys - allowed_keys
        assert not extra, f"Unexpected config keys: {extra}"


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_no_connection_format(self):
        """CONNECTION_FORMAT is not in _java.xml -- must not appear in config."""
        node = _make_node(params={"CONNECTION_FORMAT": "row"})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert "connection_format" not in result.component["config"]

    def test_no_die_on_error(self):
        """DIE_ON_ERROR is not in _java.xml -- must not appear in config."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FixedFlowInputConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]

    def test_no_rows_key(self):
        """rows is a computed key not a direct param -- must not appear in config."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert "rows" not in result.component["config"]

    def test_no_schema_in_config(self):
        """schema should be at component level, not inside config."""
        node = _make_node(schema=_make_schema_columns())
        result = FixedFlowInputConverter().convert(node, [], {})
        assert "schema" not in result.component["config"]


class TestComponentStructure:
    """Verify _build_component_dict output structure."""

    def test_type(self):
        """type_name is 'FixedFlowInputComponent' per D-43."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["type"] == "FixedFlowInputComponent"

    def test_top_level_keys(self):
        """Output dict has all required top-level keys from _build_component_dict."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected_keys

    def test_component_id(self):
        node = _make_node(component_id="ffi_1")
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["id"] == "ffi_1"

    def test_original_type(self):
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFixedFlowInput"

    def test_result_type(self):
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)


class TestModuleLevelParsers:
    """Verify module-level _parse_values and _parse_intable functions directly."""

    def test_parse_values_empty(self):
        assert _parse_values([]) == []

    def test_parse_values_none(self):
        assert _parse_values(None) == []

    def test_parse_values_not_list(self):
        assert _parse_values("invalid") == []

    def test_parse_values_single_pair(self):
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": "col1"},
            {"elementRef": "VALUE", "value": '"val1"'},
        ]
        result = _parse_values(raw)
        assert len(result) == 1
        assert result[0]["schema_column"] == "col1"
        assert result[0]["value"] == "val1"

    def test_parse_values_multiple_pairs(self):
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": "a"},
            {"elementRef": "VALUE", "value": '"1"'},
            {"elementRef": "SCHEMA_COLUMN", "value": "b"},
            {"elementRef": "VALUE", "value": '"2"'},
        ]
        result = _parse_values(raw)
        assert len(result) == 2
        assert result[0] == {"schema_column": "a", "value": "1"}
        assert result[1] == {"schema_column": "b", "value": "2"}

    def test_parse_intable_empty(self):
        assert _parse_intable([]) == []

    def test_parse_intable_none(self):
        assert _parse_intable(None) == []

    def test_parse_intable_not_list(self):
        assert _parse_intable("invalid") == []

    def test_parse_intable_preserves_entries(self):
        """INTABLE entries are preserved as raw elementRef/value dicts."""
        raw = [
            {"elementRef": "col1", "value": '"a"'},
            {"elementRef": "col2", "value": '"b"'},
        ]
        result = _parse_intable(raw)
        assert len(result) == 2
        assert result[0] == {"element_ref": "col1", "value": "a"}
        assert result[1] == {"element_ref": "col2", "value": "b"}
