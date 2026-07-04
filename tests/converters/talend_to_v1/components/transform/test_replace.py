"""Tests for ReplaceConverter (tReplace -> v1 tReplace config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.replace import (
    ReplaceConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="rp_1",
               component_type="tReplace"):
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


def _make_subst_data(rows):
    """Generate SUBSTITUTIONS TABLE data with stride-7 per row.

    rows: list of tuples (input_column, search_pattern, replace_string,
          whole_word, case_sensitive, use_glob, comment)
    """
    result = []
    fields = ("INPUT_COLUMN", "SEARCH_PATTERN", "REPLACE_STRING",
              "WHOLE_WORD", "CASE_SENSITIVE", "USE_GLOB", "COMMENT")
    for row_values in rows:
        for field_name, value in zip(fields, row_values):
            result.append({"elementRef": field_name, "value": value})
    return result


def _make_adv_subst_data(rows):
    """Generate ADVANCED_SUBST TABLE data with stride-4 per row.

    rows: list of tuples (input_column, search_column, replace_column, comment)
    """
    result = []
    fields = ("INPUT_COLUMN", "SEARCH_COLUMN", "REPLACE_COLUMN", "COMMENT")
    for row_values in rows:
        for field_name, value in zip(fields, row_values):
            result.append({"elementRef": field_name, "value": value})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tReplace") is ReplaceConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_simple_mode_default_true(self):
        node = _make_node()
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["simple_mode"] is True

    def test_substitutions_default_empty(self):
        node = _make_node()
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["substitutions"] == []

    def test_strict_match_default_true(self):
        node = _make_node()
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["strict_match"] is True

    def test_advanced_mode_default_false(self):
        node = _make_node()
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["advanced_mode"] is False

    def test_advanced_subst_default_empty(self):
        node = _make_node()
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["advanced_subst"] == []

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestSubstitutionsTable:
    """Verify SUBSTITUTIONS TABLE stride-7 parsing."""

    def test_substitutions_single(self):
        """Single 7-element group parsed into one substitution dict."""
        data = _make_subst_data([
            ("col_a", '"foo"', '"bar"', "true", "false", "false", "swap foo"),
        ])
        node = _make_node(params={"SUBSTITUTIONS": data})
        result = ReplaceConverter().convert(node, [], {})
        subs = result.component["config"]["substitutions"]
        assert len(subs) == 1
        assert subs[0]["input_column"] == "col_a"
        assert subs[0]["search_pattern"] == "foo"
        assert subs[0]["replace_string"] == "bar"
        assert subs[0]["whole_word"] is True
        assert subs[0]["case_sensitive"] is False
        assert subs[0]["use_glob"] is False
        assert subs[0]["comment"] == "swap foo"

    def test_substitutions_multiple(self):
        """14 elements -> 2 substitution dicts."""
        data = _make_subst_data([
            ("city", '"NYC"', '"New York"', "false", "false", "false", ""),
            ("state", '"CA"', '"California"', "true", "true", "false", "state fix"),
        ])
        node = _make_node(params={"SUBSTITUTIONS": data})
        result = ReplaceConverter().convert(node, [], {})
        subs = result.component["config"]["substitutions"]
        assert len(subs) == 2
        assert subs[0]["input_column"] == "city"
        assert subs[1]["input_column"] == "state"

    def test_whole_word_default_true(self):
        """CRITICAL FIX: Missing WHOLE_WORD defaults to True per _java.xml."""
        data = [
            {"elementRef": "INPUT_COLUMN", "value": "col_a"},
            {"elementRef": "SEARCH_PATTERN", "value": '"x"'},
            {"elementRef": "REPLACE_STRING", "value": '"y"'},
            # WHOLE_WORD omitted -- should default to True
            {"elementRef": "CASE_SENSITIVE", "value": "false"},
            {"elementRef": "USE_GLOB", "value": "false"},
            {"elementRef": "COMMENT", "value": ""},
        ]
        # Need exactly 7 entries for stride-7; add a placeholder
        # Actually we test with the full 7 but without WHOLE_WORD having explicit value
        # Better: test via a full stride where WHOLE_WORD entry is missing entirely
        # Use the parser defaults -- a stride-7 row where WHOLE_WORD val is empty string
        data_full = _make_subst_data([
            ("col_a", '"x"', '"y"', "", "false", "false", ""),
        ])
        node = _make_node(params={"SUBSTITUTIONS": data_full})
        result = ReplaceConverter().convert(node, [], {})
        subs = result.component["config"]["substitutions"]
        assert len(subs) == 1
        assert subs[0]["whole_word"] is True

    def test_case_sensitive_default_false(self):
        """Missing CASE_SENSITIVE defaults to False per _java.xml."""
        data_full = _make_subst_data([
            ("col_a", '"x"', '"y"', "true", "", "false", ""),
        ])
        node = _make_node(params={"SUBSTITUTIONS": data_full})
        result = ReplaceConverter().convert(node, [], {})
        subs = result.component["config"]["substitutions"]
        assert len(subs) == 1
        assert subs[0]["case_sensitive"] is False

    def test_use_glob_default_false(self):
        """Missing USE_GLOB defaults to False per _java.xml."""
        data_full = _make_subst_data([
            ("col_a", '"x"', '"y"', "true", "false", "", ""),
        ])
        node = _make_node(params={"SUBSTITUTIONS": data_full})
        result = ReplaceConverter().convert(node, [], {})
        subs = result.component["config"]["substitutions"]
        assert len(subs) == 1
        assert subs[0]["use_glob"] is False

    def test_search_pattern_default(self):
        """Missing SEARCH_PATTERN defaults to 'default' per _java.xml."""
        data_full = _make_subst_data([
            ("col_a", "", "", "true", "false", "false", ""),
        ])
        node = _make_node(params={"SUBSTITUTIONS": data_full})
        result = ReplaceConverter().convert(node, [], {})
        subs = result.component["config"]["substitutions"]
        assert len(subs) == 1
        assert subs[0]["search_pattern"] == "default"

    def test_replace_string_default(self):
        """Missing REPLACE_STRING defaults to 'default' per _java.xml."""
        data_full = _make_subst_data([
            ("col_a", '"find"', "", "true", "false", "false", ""),
        ])
        node = _make_node(params={"SUBSTITUTIONS": data_full})
        result = ReplaceConverter().convert(node, [], {})
        subs = result.component["config"]["substitutions"]
        assert len(subs) == 1
        assert subs[0]["replace_string"] == "default"


class TestAdvancedSubstTable:
    """Verify ADVANCED_SUBST TABLE stride-4 parsing."""

    def test_advanced_subst_single(self):
        """Single 4-element group parsed into one advanced subst dict."""
        data = _make_adv_subst_data([
            ("col_a", "search_col", "replace_col", "my comment"),
        ])
        node = _make_node(params={"ADVANCED_SUBST": data})
        result = ReplaceConverter().convert(node, [], {})
        adv = result.component["config"]["advanced_subst"]
        assert len(adv) == 1
        assert adv[0]["input_column"] == "col_a"
        assert adv[0]["search_column"] == "search_col"
        assert adv[0]["replace_column"] == "replace_col"
        assert adv[0]["comment"] == "my comment"

    def test_advanced_subst_empty(self):
        """Empty ADVANCED_SUBST raw -> []."""
        node = _make_node()
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["advanced_subst"] == []


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_simple_mode_false(self):
        node = _make_node(params={"SIMPLE_MODE": "false"})
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["simple_mode"] is False

    def test_advanced_mode_true(self):
        node = _make_node(params={"ADVANCED_MODE": "true"})
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["advanced_mode"] is True

    def test_strict_match_false(self):
        node = _make_node(params={"STRICT_MATCH": "false"})
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["strict_match"] is False


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema passthrough for transform component."""

    def test_schema_passthrough(self):
        node = _make_node(schema=_make_schema_columns())
        result = ReplaceConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][1]["name"] == "name"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review per D-27 (no engine)."""
        node = _make_node()
        result = ReplaceConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_no_engine(self):
        """needs_review mentions no engine implementation."""
        node = _make_node()
        result = ReplaceConverter().convert(node, [], {})
        assert "No v1 engine implementation" in result.needs_review[0]["issue"]

    def test_needs_review_severity(self):
        node = _make_node()
        result = ReplaceConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = ReplaceConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"


class TestPhantomParams:
    """Verify phantom params NOT in _java.xml are NOT extracted."""

    def test_connection_format_not_in_config(self):
        """CONNECTION_FORMAT is phantom -- must NOT appear in config."""
        node = _make_node(params={"CONNECTION_FORMAT": "row"})
        result = ReplaceConverter().convert(node, [], {})
        assert "connection_format" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = ReplaceConverter().convert(node, [], {})
        expected_keys = {
            "simple_mode", "substitutions", "strict_match",
            "advanced_mode", "advanced_subst",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify component dict structure."""

    def test_has_type(self):
        """type_name is 'tReplace' (no-engine) per D-43."""
        node = _make_node()
        result = ReplaceConverter().convert(node, [], {})
        assert result.component["type"] == "tReplace"


# ------------------------------------------------------------------
# Plan 14-11: TABLE-parser branch coverage (lines 71, 83, 129, 138, 148-149)
# ------------------------------------------------------------------


class TestSubstitutionsParserBranches:
    """Cover lines 71 (incomplete trailing group break) and 83 (entry not dict)."""

    def test_incomplete_trailing_group_skipped(self):
        """Trailing group with < 7 entries is dropped (line 71)."""
        from src.converters.talend_to_v1.components.transform.replace import (
            _parse_substitutions,
        )
        # 1 full row (7 entries) + 3 trailing entries -> trailing trimmed
        full = _make_subst_data([
            ("col_a", "x", "y", "true", "false", "false", ""),
        ])
        trailing = [
            {"elementRef": "INPUT_COLUMN", "value": "col_b"},
            {"elementRef": "SEARCH_PATTERN", "value": "z"},
            {"elementRef": "REPLACE_STRING", "value": "w"},
        ]
        result = _parse_substitutions(full + trailing)
        assert len(result) == 1
        assert result[0]["input_column"] == "col_a"

    def test_non_dict_entry_in_group_skipped(self):
        """A non-dict entry inside an otherwise-valid group is silently skipped (line 83)."""
        from src.converters.talend_to_v1.components.transform.replace import (
            _parse_substitutions,
        )
        # Build a full 7-entry group where one entry is a string (not dict)
        raw = [
            {"elementRef": "INPUT_COLUMN", "value": "col_a"},
            "not_a_dict",  # <-- skipped
            {"elementRef": "REPLACE_STRING", "value": "y"},
            {"elementRef": "WHOLE_WORD", "value": "true"},
            {"elementRef": "CASE_SENSITIVE", "value": "false"},
            {"elementRef": "USE_GLOB", "value": "false"},
            {"elementRef": "COMMENT", "value": ""},
        ]
        result = _parse_substitutions(raw)
        # Row still emitted with defaults for the missing SEARCH_PATTERN
        assert len(result) == 1
        assert result[0]["input_column"] == "col_a"
        assert result[0]["search_pattern"] == "default"
        assert result[0]["replace_string"] == "y"


class TestAdvancedSubstParserBranches:
    """Cover lines 129 (incomplete trailing group break), 138 (entry not dict),
    and 148-149 (UnicodeDecodeError/ValueError fallthrough on SEARCH_COLUMN
    decode)."""

    def test_incomplete_trailing_group_skipped(self):
        """Trailing group with < 4 entries is dropped (line 129)."""
        from src.converters.talend_to_v1.components.transform.replace import (
            _parse_advanced_subst,
        )
        full = _make_adv_subst_data([
            ("col_a", "search_a", "repl_a", "comment_a"),
        ])
        trailing = [
            {"elementRef": "INPUT_COLUMN", "value": "col_b"},
            {"elementRef": "SEARCH_COLUMN", "value": "search_b"},
        ]
        result = _parse_advanced_subst(full + trailing)
        assert len(result) == 1
        assert result[0]["input_column"] == "col_a"

    def test_non_dict_entry_in_group_skipped(self):
        """A non-dict entry inside an otherwise-valid group is skipped (line 138)."""
        from src.converters.talend_to_v1.components.transform.replace import (
            _parse_advanced_subst,
        )
        raw = [
            {"elementRef": "INPUT_COLUMN", "value": "col_a"},
            42,  # <-- skipped
            {"elementRef": "REPLACE_COLUMN", "value": "repl_a"},
            {"elementRef": "COMMENT", "value": ""},
        ]
        result = _parse_advanced_subst(raw)
        assert len(result) == 1
        assert result[0]["input_column"] == "col_a"
        # SEARCH_COLUMN was the 42, so it stays at default ''
        assert result[0]["search_column"] == ""
        assert result[0]["replace_column"] == "repl_a"

    def test_search_column_unicode_escape_decoded(self):
        """A standard backslash sequence decodes via unicode_escape (success path)."""
        from src.converters.talend_to_v1.components.transform.replace import (
            _parse_advanced_subst,
        )
        raw = _make_adv_subst_data([
            ("col_a", "\\\\w+", "repl_a", ""),  # XML-double-escaped becomes \\w+
        ])
        result = _parse_advanced_subst(raw)
        assert len(result) == 1
        # \\w+ in raw -> \w+ after unicode_escape
        assert result[0]["search_column"] == "\\w+"

    def test_search_column_invalid_escape_falls_back(self):
        """An invalid escape sequence raises UnicodeDecodeError -> kept verbatim
        (lines 148-149)."""
        from src.converters.talend_to_v1.components.transform.replace import (
            _parse_advanced_subst,
        )
        # Build a SEARCH_COLUMN value that cannot be unicode-escape-decoded.
        # A trailing backslash (\\ followed by NOTHING) raises:
        #   ValueError: \ at end of string
        raw = _make_adv_subst_data([
            ("col_a", "\\", "repl_a", ""),  # trailing backslash
        ])
        result = _parse_advanced_subst(raw)
        assert len(result) == 1
        # On exception, the value is stored as-is (post-strip-quote, pre-decode)
        assert result[0]["search_column"] == "\\"
