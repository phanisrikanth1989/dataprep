"""Tests for Replace (tReplace engine implementation)."""
import pytest
import pandas as pd

from src.v1.engine.components.transform.replace import Replace
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "tReplace",
    "simple_mode": True,
    "substitutions": [
        {
            "input_column": "name",
            "search_pattern": "Alice",
            "replace_string": "Alicia",
            "whole_word": False,
            "case_sensitive": True,
            "use_glob": False,
            "comment": "",
        }
    ],
    "strict_match": False,
    "advanced_mode": False,
    "advanced_subst": [],
}


def _make_component(config=None, global_map=None):
    """Create a Replace with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    return Replace(
        component_id="tReplace_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )


def _make_input_df(rows=None):
    """Create a standard test input DataFrame."""
    if rows is None:
        rows = [
            {"id": 1, "name": "Alice", "city": "New York"},
            {"id": 2, "name": "Bob", "city": "alice springs"},
            {"id": 3, "name": "Charlie", "city": "Boston"},
        ]
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Both V1 and Talend alias are registered in REGISTRY."""

    def test_v1_name_registered(self):
        assert REGISTRY.get("Replace") is Replace

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tReplace") is Replace

    def test_both_aliases_resolve_same_class(self):
        assert REGISTRY.get("Replace") is REGISTRY.get("tReplace")


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for invalid config."""

    def test_simple_mode_not_bool_raises(self):
        config = {**_DEFAULT_CONFIG, "simple_mode": "yes"}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="simple_mode"):
            comp.execute(_make_input_df())

    def test_substitutions_not_list_raises(self):
        config = {**_DEFAULT_CONFIG, "substitutions": "bad"}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="substitutions"):
            comp.execute(_make_input_df())

    def test_substitution_row_not_dict_raises(self):
        config = {**_DEFAULT_CONFIG, "substitutions": ["not_a_dict"]}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match=r"substitutions\[0\]"):
            comp.execute(_make_input_df())

    def test_substitution_row_missing_input_column_raises(self):
        bad_row = {
            "search_pattern": "foo",
            "replace_string": "bar",
        }
        config = {**_DEFAULT_CONFIG, "substitutions": [bad_row]}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="input_column"):
            comp.execute(_make_input_df())

    def test_substitution_row_missing_search_pattern_raises(self):
        bad_row = {"input_column": "name", "replace_string": "bar"}
        config = {**_DEFAULT_CONFIG, "substitutions": [bad_row]}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="search_pattern"):
            comp.execute(_make_input_df())

    def test_advanced_subst_not_list_raises(self):
        config = {
            **_DEFAULT_CONFIG,
            "simple_mode": False,
            "advanced_subst": "bad",
        }
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="advanced_subst"):
            comp.execute(_make_input_df())

    def test_advanced_subst_row_missing_key_raises(self):
        bad_row = {"input_column": "name", "search_column": "s"}
        # missing replace_column
        config = {
            **_DEFAULT_CONFIG,
            "simple_mode": False,
            "advanced_subst": [bad_row],
        }
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="replace_column"):
            comp.execute(_make_input_df())

    def test_valid_config_does_not_raise(self):
        comp = _make_component()
        result = comp.execute(_make_input_df())
        assert result["main"] is not None


# ------------------------------------------------------------------
# TestSimpleModeFlow
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSimpleModeFlow:
    """Simple mode: substitution rules applied correctly."""

    def test_basic_replacement(self):
        """Exact match replaced in the target column."""
        comp = _make_component()
        df = _make_input_df([{"id": 1, "name": "Alice", "city": "X"}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["name"] == "Alicia"

    def test_non_matching_rows_unchanged(self):
        comp = _make_component()
        df = _make_input_df([{"id": 2, "name": "Bob", "city": "X"}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["name"] == "Bob"

    def test_case_insensitive_replacement(self):
        subst = [
            {
                "input_column": "name",
                "search_pattern": "alice",
                "replace_string": "Alicia",
                "whole_word": False,
                "case_sensitive": False,
                "use_glob": False,
                "comment": "",
            }
        ]
        config = {**_DEFAULT_CONFIG, "substitutions": subst}
        comp = _make_component(config=config)
        df = _make_input_df([{"id": 1, "name": "ALICE", "city": "X"}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["name"] == "Alicia"

    def test_case_sensitive_no_match_on_wrong_case(self):
        comp = _make_component()  # case_sensitive=True, pattern="Alice"
        df = _make_input_df([{"id": 1, "name": "ALICE", "city": "X"}])
        result = comp.execute(df)
        # Pattern "Alice" case-sensitive won't match "ALICE"
        assert result["main"].iloc[0]["name"] == "ALICE"

    def test_substring_replacement_when_strict_match_false(self):
        subst = [
            {
                "input_column": "name",
                "search_pattern": "Ali",
                "replace_string": "***",
                "whole_word": False,
                "case_sensitive": True,
                "use_glob": False,
                "comment": "",
            }
        ]
        config = {**_DEFAULT_CONFIG, "strict_match": False, "substitutions": subst}
        comp = _make_component(config=config)
        df = _make_input_df([{"id": 1, "name": "AliceAli", "city": "X"}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["name"] == "***ce***"

    def test_strict_match_true_only_replaces_exact_value(self):
        subst = [
            {
                "input_column": "name",
                "search_pattern": "Alice",
                "replace_string": "Alicia",
                "whole_word": False,
                "case_sensitive": True,
                "use_glob": False,
                "comment": "",
            }
        ]
        config = {**_DEFAULT_CONFIG, "strict_match": True, "substitutions": subst}
        comp = _make_component(config=config)
        df = _make_input_df([
            {"id": 1, "name": "Alice", "city": "X"},     # exact match -- replaced
            {"id": 2, "name": "AliceB", "city": "X"},    # not exact match -- unchanged
        ])
        result = comp.execute(df)
        assert result["main"].iloc[0]["name"] == "Alicia"
        assert result["main"].iloc[1]["name"] == "AliceB"

    def test_glob_pattern_wildcard(self):
        subst = [
            {
                "input_column": "name",
                "search_pattern": "Ali*",
                "replace_string": "A",
                "whole_word": False,
                "case_sensitive": True,
                "use_glob": True,
                "comment": "",
            }
        ]
        config = {**_DEFAULT_CONFIG, "strict_match": True, "substitutions": subst}
        comp = _make_component(config=config)
        df = _make_input_df([
            {"id": 1, "name": "Alice", "city": "X"},
            {"id": 2, "name": "Bob", "city": "X"},
        ])
        result = comp.execute(df)
        assert result["main"].iloc[0]["name"] == "A"
        assert result["main"].iloc[1]["name"] == "Bob"

    def test_missing_column_skipped_gracefully(self):
        """Substitution targeting non-existent column is skipped; no error."""
        subst = [
            {
                "input_column": "nonexistent",
                "search_pattern": "x",
                "replace_string": "y",
                "whole_word": False,
                "case_sensitive": True,
                "use_glob": False,
                "comment": "",
            }
        ]
        config = {**_DEFAULT_CONFIG, "substitutions": subst}
        comp = _make_component(config=config)
        df = _make_input_df([{"id": 1, "name": "Alice", "city": "X"}])
        result = comp.execute(df)
        # No error; other columns unchanged
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_empty_substitutions_passthrough(self):
        config = {**_DEFAULT_CONFIG, "substitutions": []}
        comp = _make_component(config=config)
        df = _make_input_df()
        result = comp.execute(df)
        assert len(result["main"]) == len(df)

    def test_row_count_preserved(self):
        comp = _make_component()
        df = _make_input_df()
        result = comp.execute(df)
        assert len(result["main"]) == len(df)

    def test_reject_is_none(self):
        comp = _make_component()
        result = comp.execute(_make_input_df())
        assert result.get("reject") is None


# ------------------------------------------------------------------
# TestAdvancedModeFlow
# ------------------------------------------------------------------


@pytest.mark.unit
class TestAdvancedModeFlow:
    """Advanced mode: regex-based replacement using literal pattern + replacement.

    Talend tReplace advanced mode parameters SEARCH_COLUMN and REPLACE_COLUMN are
    legacy XML tag names; despite the names, they hold a literal regex pattern and a
    literal replacement string respectively (verified against Talaxie tReplace_java.xml
    where both are FIELD="String", and tReplace_main.javajet which emits them as
    bareword Java string expressions). They are NOT references to other columns.
    Only input_column refers to an actual DataFrame column.
    """

    def test_basic_advanced_regex_replacement(self):
        """Regex pattern \\d+ is applied uniformly to every row of input_column."""
        config = {
            **_DEFAULT_CONFIG,
            "simple_mode": False,
            "advanced_subst": [
                {
                    "input_column": "name",
                    "search_column": "\\d+",   # regex pattern literal, NOT a column
                    "replace_column": "X",      # replacement string literal, NOT a column
                    "comment": "",
                }
            ],
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([
            {"id": 1, "name": "abc123"},
            {"id": 2, "name": "def456"},
            {"id": 3, "name": "ghi"},
        ])
        result = comp.execute(df)
        # Same regex applied to every row: digits replaced by X; rows without digits unchanged.
        assert result["main"].iloc[0]["name"] == "abcX"
        assert result["main"].iloc[1]["name"] == "defX"
        assert result["main"].iloc[2]["name"] == "ghi"

    def test_advanced_input_column_missing_skipped(self):
        """If input_column does not exist on the DataFrame, the rule is skipped (no exception)."""
        config = {
            **_DEFAULT_CONFIG,
            "simple_mode": False,
            "advanced_subst": [
                {
                    "input_column": "nonexistent",
                    "search_column": "\\d+",
                    "replace_column": "X",
                    "comment": "",
                }
            ],
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([
            {"id": 1, "name": "abc123"},
            {"id": 2, "name": "def456"},
        ])
        result = comp.execute(df)
        # Rule was skipped; df is otherwise unchanged.
        assert list(result["main"]["name"]) == ["abc123", "def456"]
        assert len(result["main"]) == 2

    def test_advanced_invalid_regex_raises(self):
        """An invalid regex in search_column raises ConfigurationError."""
        config = {
            **_DEFAULT_CONFIG,
            "simple_mode": False,
            "advanced_subst": [
                {
                    "input_column": "name",
                    "search_column": "[invalid(",   # malformed regex
                    "replace_column": "X",
                    "comment": "",
                }
            ],
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": 1, "name": "abc"}])
        with pytest.raises(ConfigurationError, match="invalid regex"):
            comp.execute(df)

    def test_advanced_multiple_rules_applied_in_order(self):
        """When multiple rules are listed, the second sees the output of the first."""
        config = {
            **_DEFAULT_CONFIG,
            "simple_mode": False,
            "advanced_subst": [
                {
                    "input_column": "name",
                    "search_column": "\\d+",
                    "replace_column": "X",
                    "comment": "",
                },
                {
                    "input_column": "name",
                    "search_column": "X",
                    "replace_column": "Y",
                    "comment": "",
                },
            ],
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([
            {"id": 1, "name": "abc123"},
            {"id": 2, "name": "def"},
        ])
        result = comp.execute(df)
        # First rule turns "abc123" -> "abcX"; second rule turns "abcX" -> "abcY".
        # "def" has no digits and no X, so it is unchanged.
        assert result["main"].iloc[0]["name"] == "abcY"
        assert result["main"].iloc[1]["name"] == "def"

    def test_advanced_row_count_preserved(self):
        """The number of output rows equals the number of input rows."""
        config = {
            **_DEFAULT_CONFIG,
            "simple_mode": False,
            "advanced_subst": [
                {
                    "input_column": "name",
                    "search_column": "\\d+",
                    "replace_column": "X",
                    "comment": "",
                }
            ],
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([
            {"id": i, "name": f"row{i}"} for i in range(7)
        ])
        result = comp.execute(df)
        assert len(result["main"]) == 7

    def test_advanced_unicode_escape_handling(self):
        """The literal escape '\\w+' from JSON is decoded to the regex \\w+ at runtime."""
        config = {
            **_DEFAULT_CONFIG,
            "simple_mode": False,
            "advanced_subst": [
                {
                    "input_column": "name",
                    # When written by a JSON converter, "\w+" round-trips as the
                    # 3-char Python string "\\w+". The engine unicode-escape-decodes
                    # it back to the regex "\w+" before compiling.
                    "search_column": "\\w+",
                    "replace_column": "*",
                    "comment": "",
                }
            ],
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([
            {"id": 1, "name": "abc 123"},   # two word tokens separated by space
            {"id": 2, "name": "x"},
        ])
        result = comp.execute(df)
        # \w+ matches each word run; both runs replaced by '*'. Space between them
        # is not a word char and is not consumed.
        assert result["main"].iloc[0]["name"] == "* *"
        assert result["main"].iloc[1]["name"] == "*"


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """None input, empty DataFrame, single row, NaN values."""

    def test_none_input_returns_empty_main(self):
        comp = _make_component()
        result = comp.execute(None)
        assert "main" in result
        assert result["main"].empty

    def test_empty_dataframe_returns_empty_main(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty

    def test_single_row_processed(self):
        comp = _make_component()
        df = _make_input_df([{"id": 1, "name": "Alice", "city": "X"}])
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_nan_in_non_target_column_preserved(self):
        """NaN values in columns not targeted by substitution are untouched."""
        comp = _make_component()
        df = pd.DataFrame([{"id": None, "name": "Alice", "city": "X"}])
        result = comp.execute(df)
        assert result["main"] is not None
        assert pd.isna(result["main"].iloc[0]["id"])

    def test_large_input(self):
        comp = _make_component()
        rows = [{"id": i, "name": "Alice" if i % 2 == 0 else "Bob", "city": "X"} for i in range(500)]
        df = pd.DataFrame(rows)
        result = comp.execute(df)
        assert len(result["main"]) == 500


# ------------------------------------------------------------------
# TestGlobalMapVariables
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    """Stats pushed to GlobalMap correctly after execute()."""

    def test_nb_line_equals_input_row_count(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        df = _make_input_df()
        comp.execute(df)
        assert gm.get_component_stat("tReplace_1", "NB_LINE") == len(df)

    def test_nb_line_ok_equals_input_row_count(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        df = _make_input_df()
        comp.execute(df)
        assert gm.get_component_stat("tReplace_1", "NB_LINE_OK") == len(df)

    def test_nb_line_reject_is_zero(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_make_input_df())
        assert gm.get_component_stat("tReplace_1", "NB_LINE_REJECT") == 0

    def test_works_without_global_map(self):
        """Component must not raise when global_map is None."""
        comp = _make_component(global_map=None)
        comp.global_map = None
        result = comp.execute(_make_input_df())
        assert result["main"] is not None


# ------------------------------------------------------------------
# TestIterateReexecution
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIterateReexecution:
    """execute() + reset() + execute() gives consistent results."""

    def test_second_execute_produces_same_result(self):
        comp = _make_component()
        df = _make_input_df()
        result1 = comp.execute(df)
        comp.reset()
        result2 = comp.execute(df)
        pd.testing.assert_frame_equal(
            result1["main"].reset_index(drop=True),
            result2["main"].reset_index(drop=True),
        )

    def test_config_not_mutated_across_executions(self):
        comp = _make_component()
        df = _make_input_df()
        comp.execute(df)
        snapshot = comp._original_config.copy()
        comp.reset()
        comp.execute(df)
        assert comp._original_config == snapshot
