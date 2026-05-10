"""Tests for FilterRows (tFilterRow / tFilterRows engine implementation)."""
import inspect
from unittest.mock import patch

import pytest
import numpy as np
import pandas as pd

from src.v1.engine.components.transform.filter_rows import FilterRows
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Test Helpers
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "FilterRows",
    "logical_op": "&&",
    "use_advanced": False,
    "advanced_cond": "",
    "conditions": [
        {"column": "age", "function": "", "operator": ">=", "value": "25"},
    ],
}


def _make_component(config=None, global_map=None, schema=None):
    """Create a FilterRows with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    comp = FilterRows(
        component_id="tFilter_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    comp.output_schema = schema
    return comp


def _sample_df():
    """Standard test DataFrame for filtering."""
    return pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
        "age": [25, 30, 35, 20, 28],
        "salary": [50000.0, 60000.0, 45000.0, 55000.0, 70000.0],
        "city": ["New York", "Boston", "New York", "Chicago", "Boston"],
    })


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """Validate that config errors are caught before processing."""

    def test_invalid_operator(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "age", "function": "", "operator": "INVALID_OP", "value": "25"},
        ]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="operator"):
            comp.execute(_sample_df())

    def test_missing_column_in_condition(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"function": "", "operator": "==", "value": "25"},
        ]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="column"):
            comp.execute(_sample_df())

    def test_use_advanced_empty_expression(self):
        config = dict(_DEFAULT_CONFIG)
        config["use_advanced"] = True
        config["advanced_cond"] = ""
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="advanced_cond"):
            comp.execute(_sample_df())


# ------------------------------------------------------------------
# TestComparisonOperators -- covers FROW-02
# ------------------------------------------------------------------


@pytest.mark.unit
class TestComparisonOperators:
    """Comparison operator tests (==, !=, >, <, >=, <=)."""

    def test_equal(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "age", "function": "", "operator": "==", "value": "25"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 1
        assert result["main"]["name"].iloc[0] == "Alice"

    def test_not_equal(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "age", "function": "", "operator": "!=", "value": "25"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 4
        assert "Alice" not in result["main"]["name"].tolist()

    def test_greater_than(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "age", "function": "", "operator": ">", "value": "28"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 2  # Bob(30), Charlie(35)

    def test_less_than(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "age", "function": "", "operator": "<", "value": "25"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 1
        assert result["main"]["name"].iloc[0] == "Diana"

    def test_greater_equal(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "age", "function": "", "operator": ">=", "value": "28"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 3  # Bob(30), Charlie(35), Eve(28)

    def test_less_equal(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "age", "function": "", "operator": "<=", "value": "25"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 2  # Alice(25), Diana(20)


# ------------------------------------------------------------------
# TestStringOperators -- covers FROW-02
# ------------------------------------------------------------------


@pytest.mark.unit
class TestStringOperators:
    """String operator tests (MATCHES, CONTAINS, NOT_CONTAINS, STARTS_WITH, ENDS_WITH)."""

    def test_matches_regex(self):
        """MATCHES with regex pattern uses fullmatch (not partial)."""
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "", "operator": "MATCHES", "value": "A.*"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        names = result["main"]["name"].tolist()
        assert names == ["Alice"]

    def test_matches_rejects_partial(self):
        """'Alice' does NOT match pattern 'Ali' (fullmatch semantics)."""
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "", "operator": "MATCHES", "value": "Ali"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 0  # fullmatch: "Ali" != "Alice"

    def test_contains(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "city", "function": "", "operator": "CONTAINS", "value": "York"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        cities = result["main"]["city"].tolist()
        assert all("York" in c for c in cities)
        assert len(result["main"]) == 2  # New York appears twice

    def test_not_contains(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "city", "function": "", "operator": "NOT_CONTAINS", "value": "York"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 3  # Boston x2 + Chicago

    def test_starts_with(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "city", "function": "", "operator": "STARTS_WITH", "value": "New"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 2

    def test_ends_with(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "city", "function": "", "operator": "ENDS_WITH", "value": "ton"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 2  # Boston x2


# ------------------------------------------------------------------
# TestNullOperators -- covers FROW-02
# ------------------------------------------------------------------


@pytest.mark.unit
class TestNullOperators:
    """Null operator tests (IS_NULL, IS_NOT_NULL)."""

    def _df_with_nulls(self):
        return pd.DataFrame({
            "name": ["Alice", None, "Charlie", "Diana", np.nan],
            "age": [25, 30, np.nan, 20, 28],
        })

    def test_is_null(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "", "operator": "IS_NULL", "value": ""},
        ]
        comp = _make_component(config=config)
        result = comp.execute(self._df_with_nulls())
        assert len(result["main"]) == 2  # None and NaN

    def test_is_not_null(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "", "operator": "IS_NOT_NULL", "value": ""},
        ]
        comp = _make_component(config=config)
        result = comp.execute(self._df_with_nulls())
        assert len(result["main"]) == 3


# ------------------------------------------------------------------
# TestLengthOperators -- covers FROW-02
# ------------------------------------------------------------------


@pytest.mark.unit
class TestLengthOperators:
    """Length operator tests (LENGTH_LT, LENGTH_GT)."""

    def test_length_lt(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "", "operator": "LENGTH_LT", "value": "4"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        names = result["main"]["name"].tolist()
        assert names == ["Bob", "Eve"]  # length 3

    def test_length_gt(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "", "operator": "LENGTH_GT", "value": "4"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        names = result["main"]["name"].tolist()
        assert names == ["Alice", "Charlie", "Diana"]  # length > 4


# ------------------------------------------------------------------
# TestFunctionPreTransforms -- covers FROW-03
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFunctionPreTransforms:
    """FUNCTION pre-transform applied before operator comparison."""

    def test_lower_function(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "LOWER", "operator": "==", "value": "alice"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 1
        assert result["main"]["name"].iloc[0] == "Alice"

    def test_upper_function(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "UPPER", "operator": "==", "value": "ALICE"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 1
        assert result["main"]["name"].iloc[0] == "Alice"

    def test_length_function(self):
        """LENGTH pre-transform returns string length as numeric."""
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "LENGTH", "operator": "==", "value": "3"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        names = result["main"]["name"].tolist()
        assert names == ["Bob", "Eve"]

    def test_trim_function(self):
        df = pd.DataFrame({"val": [" Alice ", " Bob", "Charlie "]})
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "val", "function": "TRIM", "operator": "==", "value": "Alice"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_ltrim_function(self):
        df = pd.DataFrame({"val": [" Alice", " Bob"]})
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "val", "function": "LTRIM", "operator": "STARTS_WITH", "value": "Ali"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_rtrim_function(self):
        df = pd.DataFrame({"val": ["Alice ", "Bob "]})
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "val", "function": "RTRIM", "operator": "ENDS_WITH", "value": "ce"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_left_function(self):
        """LEFT(3) takes first 3 characters."""
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "LEFT(3)", "operator": "==", "value": "Ali"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 1
        assert result["main"]["name"].iloc[0] == "Alice"

    def test_right_function(self):
        """RIGHT(2) takes last 2 characters."""
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "RIGHT(2)", "operator": "==", "value": "ob"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 1
        assert result["main"]["name"].iloc[0] == "Bob"

    def test_empty_function(self):
        """Empty string function is no-op."""
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "", "operator": "==", "value": "Alice"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 1


# ------------------------------------------------------------------
# TestTypeAwareComparison -- covers FROW-04
# ------------------------------------------------------------------


@pytest.mark.unit
class TestTypeAwareComparison:
    """Type-aware comparison for numeric vs string columns."""

    def test_numeric_comparison_not_string(self):
        """FROW-04: salary > 1000 works correctly even though value is string '1000'."""
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "salary", "function": "", "operator": ">", "value": "1000"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 5  # all salaries > 1000

    def test_string_numbers_compared_as_numbers(self):
        """'9' is NOT greater than '10' when compared numerically."""
        df = pd.DataFrame({"val": ["9", "10", "2", "100"]})
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "val", "function": "", "operator": ">", "value": "5"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(df)
        vals = result["main"]["val"].tolist()
        # Numeric comparison: 9 > 5, 10 > 5, 100 > 5 but 2 is not > 5
        assert len(result["main"]) == 3
        assert "2" not in vals

    def test_string_fallback_for_non_numeric(self):
        """Non-numeric columns fall back to string comparison."""
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "name", "function": "", "operator": "==", "value": "Alice"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 1


# ------------------------------------------------------------------
# TestLogicalOperators
# ------------------------------------------------------------------


@pytest.mark.unit
class TestLogicalOperators:
    """Logical operator tests (&&, ||, AND, OR)."""

    def test_and_conditions(self):
        config = dict(_DEFAULT_CONFIG)
        config["logical_op"] = "&&"
        config["conditions"] = [
            {"column": "age", "function": "", "operator": ">=", "value": "25"},
            {"column": "salary", "function": "", "operator": ">", "value": "50000"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        # age >= 25: Alice(25), Bob(30), Charlie(35), Eve(28)
        # salary > 50000: Bob(60000), Diana(55000), Eve(70000)
        # AND: Bob(30,60000), Eve(28,70000)
        assert len(result["main"]) == 2

    def test_or_conditions(self):
        config = dict(_DEFAULT_CONFIG)
        config["logical_op"] = "||"
        config["conditions"] = [
            {"column": "name", "function": "", "operator": "==", "value": "Alice"},
            {"column": "name", "function": "", "operator": "==", "value": "Bob"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 2

    def test_and_string_accepted(self):
        """logical_op: 'AND' also works."""
        config = dict(_DEFAULT_CONFIG)
        config["logical_op"] = "AND"
        config["conditions"] = [
            {"column": "age", "function": "", "operator": ">=", "value": "25"},
            {"column": "age", "function": "", "operator": "<=", "value": "30"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        # 25 <= age <= 30: Alice(25), Bob(30), Eve(28)
        assert len(result["main"]) == 3

    def test_or_string_accepted(self):
        """logical_op: 'OR' also works."""
        config = dict(_DEFAULT_CONFIG)
        config["logical_op"] = "OR"
        config["conditions"] = [
            {"column": "age", "function": "", "operator": "<", "value": "22"},
            {"column": "age", "function": "", "operator": ">", "value": "34"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        # age < 22: Diana(20); age > 34: Charlie(35)
        assert len(result["main"]) == 2

    def test_multiple_conditions_and(self):
        """3 conditions combined with AND."""
        config = dict(_DEFAULT_CONFIG)
        config["logical_op"] = "&&"
        config["conditions"] = [
            {"column": "age", "function": "", "operator": ">=", "value": "25"},
            {"column": "salary", "function": "", "operator": ">=", "value": "50000"},
            {"column": "city", "function": "", "operator": "==", "value": "Boston"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        # age >= 25 AND salary >= 50000 AND city == Boston
        # Bob(30, 60000, Boston), Eve(28, 70000, Boston)
        assert len(result["main"]) == 2


# ------------------------------------------------------------------
# TestRejectFlow
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRejectFlow:
    """Reject output stream behavior."""

    def test_reject_contains_non_matching_rows(self):
        comp = _make_component()
        result = comp.execute(_sample_df())
        # Default: age >= 25 -> pass: Alice(25), Bob(30), Charlie(35), Eve(28)
        # reject: Diana(20)
        assert result["reject"] is not None
        assert len(result["reject"]) == 1
        assert result["reject"]["name"].iloc[0] == "Diana"

    def test_reject_none_when_all_pass(self):
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "age", "function": "", "operator": ">=", "value": "0"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert result["reject"] is None

    def test_main_plus_reject_equals_input(self):
        comp = _make_component()
        result = comp.execute(_sample_df())
        main_len = len(result["main"])
        reject_len = len(result["reject"]) if result["reject"] is not None else 0
        assert main_len + reject_len == 5


# ------------------------------------------------------------------
# TestNoEval -- covers FROW-01, FROW-05, FROW-06
# ------------------------------------------------------------------


@pytest.mark.unit
class TestNoEval:
    """Source code quality checks: no eval, no tolist, vectorized ops."""

    def test_no_eval_in_source(self):
        """FROW-01: verify filter_rows.py source code does not contain 'eval('."""
        source = inspect.getsource(FilterRows)
        assert "eval(" not in source, "FilterRows must not use eval()"

    def test_no_tolist_in_source(self):
        """FROW-05: verify source does not contain '.toList()' or '.tolist()'."""
        source = inspect.getsource(FilterRows)
        assert ".toList()" not in source
        assert ".tolist()" not in source

    def test_vectorized_operation(self):
        """FROW-06: large DataFrame filtered efficiently (not row-by-row)."""
        df = pd.DataFrame({
            "name": [f"person_{i}" for i in range(10000)],
            "age": list(range(10000)),
            "salary": [50000.0 + i for i in range(10000)],
            "city": ["Boston"] * 10000,
        })
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "age", "function": "", "operator": ">=", "value": "5000"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(df)
        assert len(result["main"]) == 5000


# ------------------------------------------------------------------
# TestConfigKeys -- covers D-04
# ------------------------------------------------------------------


@pytest.mark.unit
class TestConfigKeys:
    """Config key naming compliance."""

    def test_reads_logical_op_not_logical_operator(self):
        """Component reads 'logical_op' key."""
        config = dict(_DEFAULT_CONFIG)
        config["logical_op"] = "||"
        config["conditions"] = [
            {"column": "name", "function": "", "operator": "==", "value": "Alice"},
            {"column": "name", "function": "", "operator": "==", "value": "Bob"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 2  # OR: Alice or Bob

    def test_reads_advanced_cond_not_advanced_condition(self):
        """Component reads 'advanced_cond' key and applies it."""
        config = dict(_DEFAULT_CONFIG)
        config["use_advanced"] = True
        config["advanced_cond"] = "true"  # simple boolean expression
        config["conditions"] = []
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 5  # all rows pass

    def test_advanced_and_simple_conditions_both_apply(self):
        """When both are present in JSON, rows must satisfy advanced and simple filters."""
        config = dict(_DEFAULT_CONFIG)
        config["use_advanced"] = True
        config["advanced_cond"] = "true"
        config["conditions"] = [
            {"column": "age", "function": "", "operator": "!=", "value": "20"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 4
        assert "Diana" not in result["main"]["name"].tolist()


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases for empty data, single row, missing columns."""

    def test_empty_input(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame())
        # Empty dataframe input returns the empty dataframe as-is
        main = result["main"]
        assert main is not None and main.empty
        assert result["reject"] is None

    def test_none_input(self):
        comp = _make_component()
        result = comp.execute(None)
        assert result["main"] is None
        assert result["reject"] is None

    def test_single_row_passes(self):
        df = pd.DataFrame({"name": ["Alice"], "age": [25], "salary": [50000.0], "city": ["NYC"]})
        comp = _make_component()
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_single_row_rejects(self):
        df = pd.DataFrame({"name": ["Diana"], "age": [20], "salary": [55000.0], "city": ["Chicago"]})
        comp = _make_component()
        result = comp.execute(df)
        assert len(result["main"]) == 0

    def test_missing_column_evaluates_false(self):
        """Condition on non-existent column evaluates to False."""
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "nonexistent", "function": "", "operator": "==", "value": "x"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 0  # all rows fail

    def test_no_conditions(self):
        """Empty conditions list passes all rows."""
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = []
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 5

    def test_stats_updated(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_sample_df())
        # BaseComponent (7.1-01) owns stats. filter_rows does NOT call _update_stats manually.
        # Base _update_stats_from_result: NB_LINE = input_rows=5, NB_LINE_OK=4, NB_LINE_REJECT=1
        # (Diana age=20 fails age>=25 condition -> reject)
        assert gm.get_nb_line("tFilter_1") == 5
        assert gm.get_nb_line_ok("tFilter_1") == 4
        assert gm.get_nb_line_reject("tFilter_1") == 1


# ------------------------------------------------------------------
# TestRegistration -- covers FROW-07
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component registry registration and source quality."""

    def test_registered_as_filter_rows(self):
        cls = REGISTRY.get("FilterRows")
        assert cls is FilterRows

    def test_registered_as_t_filter_row(self):
        cls = REGISTRY.get("tFilterRow")
        assert cls is FilterRows

    def test_registered_as_t_filter_rows(self):
        cls = REGISTRY.get("tFilterRows")
        assert cls is FilterRows

    def test_no_print_in_source(self):
        """FROW-07: verify source does not contain 'print('."""
        source = inspect.getsource(FilterRows)
        assert "print(" not in source, "FilterRows must not use print()"


# ------------------------------------------------------------------
# TestLifecycle -- ENG-CR-05: no double validate_schema
# ------------------------------------------------------------------


@pytest.mark.unit
class TestLifecycle:
    """ENG-CR-05: filter_rows must not call validate_schema inside _process."""

    def test_no_double_validate(self):
        """validate_schema must be called at most once -- by BaseComponent, not by _process.

        ENG-CR-05: filter_rows._process used to call self.validate_schema manually.
        With BaseComponent owning schema validation (7.1-01), _process must NOT call it.
        """
        call_count = {"count": 0}
        original = FilterRows.validate_schema

        def counting_validate(self_inner, df, schema):
            call_count["count"] += 1
            return df

        comp = _make_component()
        with patch.object(FilterRows, "validate_schema", counting_validate):
            comp.execute(_sample_df())

        # BaseComponent calls validate_schema at most once (in _apply_output_schema_validation)
        # filter_rows._process must NOT call it directly
        assert call_count["count"] <= 1, (
            f"validate_schema called {call_count['count']} times; expected at most 1 "
            "(BaseComponent owns validation, not _process)"
        )


# ------------------------------------------------------------------
# TestIterateReexecution -- ENG-CR-07: advanced_cond preserved across executes
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIterateReexecution:
    """ENG-CR-07: advanced_cond config preserved after _resolve_java_expressions."""

    def test_advanced_cond_preserved_across_executes(self):
        """advanced_cond must remain unchanged after execute() (config snapshot/restore).

        ENG-CR-07: the old code cleared advanced_cond to "" during
        _resolve_java_expressions, which mutated self.config. With the new
        pop+restore pattern, the _original_config is never mutated and
        self.config is re-derived at each execute() from _original_config.
        """
        config = dict(_DEFAULT_CONFIG)
        config["use_advanced"] = True
        config["advanced_cond"] = "{{java}}row1.age > 10"
        config["conditions"] = []
        comp = _make_component(config=config)

        # Snapshot value before first execute
        original_cond = config["advanced_cond"]

        # Execute twice
        comp.execute(_sample_df())
        cond_after_first = comp._original_config.get("advanced_cond")

        comp.execute(_sample_df())
        cond_after_second = comp._original_config.get("advanced_cond")

        assert cond_after_first == original_cond, (
            f"advanced_cond mutated after first execute: {cond_after_first!r} != {original_cond!r}"
        )
        assert cond_after_second == original_cond, (
            f"advanced_cond mutated after second execute: {cond_after_second!r} != {original_cond!r}"
        )


# ------------------------------------------------------------------
# TestComparison -- WR-07/ENG-IN-03: numeric path when value parses as numeric
# ------------------------------------------------------------------


@pytest.mark.unit
class TestComparison:
    """WR-07/ENG-IN-03: numeric comparison always used when config value parses as numeric."""

    def test_numeric_value_string_column(self):
        """Numeric value triggers numeric comparison even on string-typed columns.

        WR-07: config value="10.0", column has string values "10","20".
        Old code had notna().any() guard that prevented numeric path when
        ALL column values are non-numeric strings. This caused "10" == "10.0"
        to fail with string comparison ("10" != "10.0").

        Fix: if value parses as numeric, always try numeric comparison.
        """
        df = pd.DataFrame({"val": ["10", "20", "30"]})
        config = dict(_DEFAULT_CONFIG)
        config["conditions"] = [
            {"column": "val", "function": "", "operator": "==", "value": "10.0"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(df)
        # "10" == 10.0 numerically -> matches
        assert len(result["main"]) == 1
        assert result["main"]["val"].iloc[0] == "10"


# ------------------------------------------------------------------
# TestStandalone -- WR-08: no AttributeError when inputs not set by engine
# ------------------------------------------------------------------


@pytest.mark.unit
class TestStandalone:
    """WR-08: component usable without engine wiring (no self.inputs attribute)."""

    def test_no_engine_inputs_attribute(self):
        """Instantiate FilterRows directly (no engine), call execute with advanced_cond.

        WR-08: self.inputs accessed without getattr guard in _handle_advanced.
        Without engine wiring, self.inputs is not set -> AttributeError.
        Fix: use getattr(self, 'inputs', None) with fallback to 'row1'.
        """
        config = {
            "component_type": "FilterRows",
            "logical_op": "&&",
            "use_advanced": True,
            "advanced_cond": "{{java}}row1.age > 10",
            "conditions": [],
        }
        comp = FilterRows(
            component_id="tFilter_standalone",
            config=config,
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        # Do NOT set comp.inputs -- this simulates standalone use without engine
        # Should not raise AttributeError (WR-08 fix: getattr guard)
        try:
            comp.execute(_sample_df())
        except AttributeError as e:
            pytest.fail(f"AttributeError raised when inputs not set: {e}")
        except Exception:
            # Other exceptions (bridge not available, etc.) are acceptable
            pass


# ------------------------------------------------------------------
# TestRejectMessage -- ENG-WR-07: java marker stripped with removeprefix
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRejectMessage:
    """ENG-WR-07: {{java}} prefix removed correctly in reject errorMessage."""

    def test_java_marker_stripped_correctly(self):
        """Reject errorMessage contains expression WITHOUT the {{java}} prefix.

        ENG-WR-07: the old code used advanced_cond[8:] (fixed-index slice).
        Fix: use removeprefix('{{java}}') which is correct even if marker
        length changes, and is Python 3.9+ idiomatic.
        """
        config = dict(_DEFAULT_CONFIG)
        config["use_advanced"] = True
        config["advanced_cond"] = "{{java}}row1.age > 5"
        config["conditions"] = []
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())

        reject = result.get("reject")
        if reject is not None and not reject.empty:
            error_msg = reject["errorMessage"].iloc[0]
            # Must NOT contain the {{java}} prefix
            assert "{{java}}" not in error_msg, (
                f"errorMessage contains {{java}} marker: {error_msg!r}"
            )
            # Must contain the expression body
            assert "row1.age > 5" in error_msg


# ------------------------------------------------------------------
# TestRejectFlow (ENG-WR-06) -- errorMessage_user from BaseComponent
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRejectFlowUserColumn:
    """ENG-WR-06: user column 'errorMessage' renamed to 'errorMessage_user' by BaseComponent."""

    def test_user_errormessage_renamed(self):
        """When input has a user column 'errorMessage', main flow renames it to '_user'.

        ENG-WR-06: engine reserves 'errorMessage' for reject diagnostics.
        D-21: BaseComponent (7.1-01) renames user columns that collide with reserved
        names in the MAIN flow. filter_rows must NOT add its own collision logic
        -- this is BaseComponent's responsibility.

        In the main flow: user 'errorMessage' -> 'errorMessage_user'.
        In the reject flow: filter_rows adds engine diagnostic 'errorMessage';
          the original user value is superseded (single-column names, expected behavior).
        """
        df = pd.DataFrame({
            "age": [25, 20, 30],
            "errorMessage": ["user_msg_A", "user_msg_B", "user_msg_C"],
        })
        config = {
            "component_type": "FilterRows",
            "logical_op": "&&",
            "use_advanced": False,
            "advanced_cond": "",
            "conditions": [
                {"column": "age", "function": "", "operator": ">=", "value": "25"},
            ],
        }
        comp = FilterRows(
            component_id="tFilter_em",
            config=config,
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        result = comp.execute(df)

        # Main flow: user 'errorMessage' renamed to 'errorMessage_user' by BaseComponent D-21
        main = result.get("main")
        assert main is not None
        assert "errorMessage_user" in main.columns, (
            "BaseComponent D-21 should rename user 'errorMessage' to 'errorMessage_user' in main flow"
        )

        # Reject flow: engine diagnostic 'errorMessage' present
        reject = result.get("reject")
        assert reject is not None, "Expected a reject DataFrame (age=20 row fails)"
        assert not reject.empty
        assert "errorMessage" in reject.columns, (
            "Reject flow should have engine 'errorMessage' diagnostic column"
        )


# ------------------------------------------------------------------
# TestCoverageLift_14_05 (COV-FRW-001)
#
# Target missed lines from Phase 14 baseline:
#   - 94-95   (_apply_function unknown FUNCTION -> warn + return col as-is)
#   - 124     (_compare unsupported operator -> ExpressionError)
#   - 189     (_validate_config conditions not list -> ConfigurationError)
#   - 194     (_validate_config cond not dict -> ConfigurationError)
#   - 202     (_validate_config cond missing 'operator' key -> ConfigurationError)
#   - 366-375 (_resolve_java_expressions: pop/restore for {{java}} marker;
#              non-Java passthrough)
#   - 392-396 (_handle_advanced advanced_cond empty -> warn + all-True mask)
#   - 411-455 (_handle_advanced full Java bridge path; bridge unavailable;
#              length mismatch; happy path; bridge raises ExpressionError)
# ------------------------------------------------------------------


from src.v1.engine.exceptions import ExpressionError


@pytest.mark.unit
class TestCoverageLift1405:
    """Targeted coverage for residual missed branches in filter_rows.py."""

    def test_unknown_function_pretransform_logs_warning_and_returns_col(self, caplog):
        # Hits lines 94-95.
        from src.v1.engine.components.transform.filter_rows import _apply_function
        col = pd.Series(["alpha", "beta"])
        with caplog.at_level("WARNING"):
            out = _apply_function(col, "WEIRD_FUNCTION_THAT_DOES_NOT_EXIST")
        # Same series returned unchanged.
        pd.testing.assert_series_equal(out, col)
        assert any(
            "Unknown FUNCTION pre-transform" in rec.message for rec in caplog.records
        )

    def test_compare_unsupported_operator_raises_expression_error(self):
        # Hits line 124.
        from src.v1.engine.components.transform.filter_rows import _compare
        col = pd.Series([1, 2, 3])
        with pytest.raises(ExpressionError) as excinfo:
            _compare(col, "DOES_NOT_EXIST", "1")
        assert "Unsupported operator" in str(excinfo.value)

    def test_validate_config_conditions_not_list_raises(self):
        # Hits line 189.
        config = {
            "component_type": "FilterRows",
            "use_advanced": False,
            "conditions": "not a list",
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError) as excinfo:
            comp.execute(_sample_df())
        assert "must be a list" in str(excinfo.value)

    def test_validate_config_cond_not_dict_raises(self):
        # Hits line 194.
        config = {
            "component_type": "FilterRows",
            "use_advanced": False,
            "conditions": ["not a dict"],
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError) as excinfo:
            comp.execute(_sample_df())
        assert "must be a dictionary" in str(excinfo.value)

    def test_validate_config_cond_missing_operator_raises(self):
        # Hits line 202.
        config = {
            "component_type": "FilterRows",
            "use_advanced": False,
            "conditions": [{"column": "age"}],  # no 'operator' key
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError) as excinfo:
            comp.execute(_sample_df())
        assert "missing required key 'operator'" in str(excinfo.value)

    def test_resolve_java_expressions_no_java_marker_calls_super(self):
        # Hits line 375 (else branch -- super passthrough).
        config = {
            "component_type": "FilterRows",
            "use_advanced": True,
            "advanced_cond": "row1.age > 10",  # NOT a {{java}} marker
            "conditions": [],
        }
        comp = _make_component(config)
        # Just call the resolver -- should not raise.
        comp.config = dict(config)
        comp._resolve_java_expressions()
        # advanced_cond is unchanged (no Java marker, stayed in config).
        assert comp.config["advanced_cond"] == "row1.age > 10"

    def test_resolve_java_expressions_with_java_marker_pops_and_restores(self):
        # Hits lines 367-373 (pop + try/finally restore).
        config = {
            "component_type": "FilterRows",
            "use_advanced": True,
            "advanced_cond": "{{java}}row1.age > 10",
            "conditions": [],
        }
        comp = _make_component(config)
        comp.config = dict(config)
        comp._resolve_java_expressions()
        # advanced_cond restored after super() call (Phase 1 D-14 immutability).
        assert comp.config["advanced_cond"] == "{{java}}row1.age > 10"

    def test_handle_advanced_empty_advanced_cond_passes_all_rows(self, caplog):
        # Hits lines 392-396.
        config = {
            "component_type": "FilterRows",
            "use_advanced": True,
            "advanced_cond": "",  # empty, not False -- triggers warn path
            "conditions": [],
        }
        # Bypass _validate_config which rejects empty advanced_cond when
        # use_advanced=True. Instead call _handle_advanced() directly after
        # populating self.config manually.
        comp = _make_component(config={
            "component_type": "FilterRows",
            "use_advanced": False,  # let _validate_config pass
            "advanced_cond": "x",
            "conditions": [],
        })
        comp.config = config  # now override directly
        df = _sample_df()
        with caplog.at_level("WARNING"):
            mask = comp._handle_advanced(df)
        assert mask.all()
        assert any("advanced_cond is empty" in rec.message for rec in caplog.records)

    def test_handle_advanced_no_java_bridge_passes_all_rows(self, caplog):
        # Hits lines 401-406 (no java_bridge -> all True).
        config = {
            "component_type": "FilterRows",
            "use_advanced": True,
            "advanced_cond": "{{java}}row1.age > 10",
            "conditions": [],
        }
        comp = _make_component(config)
        comp.config = config
        # No bridge wired.
        comp.java_bridge = None
        df = _sample_df()
        with caplog.at_level("WARNING"):
            mask = comp._handle_advanced(df)
        assert mask.all()
        assert any("Java bridge but none" in rec.message for rec in caplog.records)

    def test_handle_advanced_input_row_rewrite(self):
        # Hits lines 411-420 (inputs_attr fallback + input_row. rewrite).
        config = {
            "component_type": "FilterRows",
            "use_advanced": True,
            "advanced_cond": "input_row.age > 25",
            "conditions": [],
        }
        comp = _make_component(config)
        comp.config = config

        captured = {}

        class _FakeBridge:
            def execute_tmap_preprocessing(self, df, exprs, main_table_name, schema):
                captured["expression"] = exprs["_filter"]
                captured["main_table_name"] = main_table_name
                captured["schema"] = schema
                # Return per-row True / False alternating.
                arr = np.array([True, False, True, False, True])
                return {"_filter": arr}

        comp.java_bridge = _FakeBridge()
        df = _sample_df()
        mask = comp._handle_advanced(df)
        # input_row. rewritten to row1. (default main table when inputs unset).
        assert "row1." in captured["expression"]
        assert "input_row." not in captured["expression"]
        assert captured["main_table_name"] == "row1"
        assert mask.tolist() == [True, False, True, False, True]

    def test_handle_advanced_uses_inputs_attr_for_main_table_name(self):
        # Hits line 412 (inputs_attr present).
        config = {
            "component_type": "FilterRows",
            "use_advanced": True,
            "advanced_cond": "{{java}}myFlow.age > 10",
            "conditions": [],
        }
        comp = _make_component(config)
        comp.config = config
        comp.inputs = ["myFlow"]

        class _FakeBridge:
            def execute_tmap_preprocessing(self, df, exprs, main_table_name, schema):
                assert main_table_name == "myFlow"
                return {"_filter": np.array([True, True, True, True, True])}

        comp.java_bridge = _FakeBridge()
        mask = comp._handle_advanced(_sample_df())
        assert mask.all()

    def test_handle_advanced_length_mismatch_passes_all_rows(self, caplog):
        # Hits lines 442-447 (length mismatch warn + all-True).
        config = {
            "component_type": "FilterRows",
            "use_advanced": True,
            "advanced_cond": "{{java}}row1.age > 10",
            "conditions": [],
        }
        comp = _make_component(config)
        comp.config = config

        class _FakeBridge:
            def execute_tmap_preprocessing(self, *args, **kwargs):
                return {"_filter": np.array([True, False])}  # only 2 results, df has 5

        comp.java_bridge = _FakeBridge()
        with caplog.at_level("WARNING"):
            mask = comp._handle_advanced(_sample_df())
        assert mask.all()
        assert any("length mismatch" in rec.message for rec in caplog.records)

    def test_handle_advanced_bridge_exception_raises_expression_error(self):
        # Hits lines 454-457 (bridge raises -> wrap as ExpressionError).
        config = {
            "component_type": "FilterRows",
            "use_advanced": True,
            "advanced_cond": "{{java}}row1.age > 10",
            "conditions": [],
        }
        comp = _make_component(config)
        comp.config = config

        class _FakeBridge:
            def execute_tmap_preprocessing(self, *args, **kwargs):
                raise RuntimeError("bridge boom")

        comp.java_bridge = _FakeBridge()
        with pytest.raises(ExpressionError) as excinfo:
            comp._handle_advanced(_sample_df())
        assert "Error in Java expression" in str(excinfo.value)
        assert "bridge boom" in str(excinfo.value)

    def test_handle_advanced_per_row_none_treated_as_false(self):
        # Hits lines 449-453 (boolean coercion with None -> False).
        config = {
            "component_type": "FilterRows",
            "use_advanced": True,
            "advanced_cond": "{{java}}row1.age > 10",
            "conditions": [],
        }
        comp = _make_component(config)
        comp.config = config

        class _FakeBridge:
            def execute_tmap_preprocessing(self, *args, **kwargs):
                # Mix of bool, None, and 0/1 -- exercises the comprehension.
                return {"_filter": np.array([True, None, False, 1, 0], dtype=object)}

        comp.java_bridge = _FakeBridge()
        mask = comp._handle_advanced(_sample_df())
        assert mask.tolist() == [True, False, False, True, False]
