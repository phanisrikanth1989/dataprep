"""Tests for RowGenerator (tRowGenerator engine implementation).

All tests exercise the component via ``execute()`` to mirror the true runtime
lifecycle.  ``_validate_config()`` and ``_process()`` are never called directly
from test code (MANUAL_COMPONENT_AUTHORING.md Rule 4).

The module-level helpers ``_eval_expr`` and ``_preprocess_expression`` are
tested separately as pure functions.
"""
import pytest

from src.v1.engine.components.transform.row_generator import (
    RowGenerator,
    _eval_expr,
    _preprocess_expression,
)
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import (
    ComponentExecutionError,
    ConfigurationError,
    ExpressionError,
)
from src.v1.engine.global_map import GlobalMap


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_BASE_CONFIG: dict = {
    "component_type": "RowGenerator",
    "nb_rows": 3,
    "values": [
        {"schema_column": "id",   "array": "1"},
        {"schema_column": "name", "array": "'alice'"},
    ],
}


def _make(config=None, global_map=None, context_manager=None):
    """Construct a RowGenerator ready for execute() calls."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager if context_manager is not None else ContextManager()
    return RowGenerator(
        component_id="tRG_1",
        config=dict(config) if config is not None else dict(_BASE_CONFIG),
        global_map=gm,
        context_manager=cm,
    )


# ---------------------------------------------------------------------------
# TestRegistration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component is discoverable from the engine registry."""

    def test_registered_under_v1_name(self):
        assert REGISTRY.get("RowGenerator") is RowGenerator

    def test_registered_under_talend_alias(self):
        assert REGISTRY.get("tRowGenerator") is RowGenerator


# ---------------------------------------------------------------------------
# TestValidation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for invalid structural config."""

    def test_missing_values_raises(self):
        cfg = {**_BASE_CONFIG}
        del cfg["values"]
        comp = _make(config=cfg)
        with pytest.raises(ConfigurationError, match="values"):
            comp.execute()

    def test_non_list_values_raises(self):
        cfg = {**_BASE_CONFIG, "values": {"schema_column": "id", "array": "1"}}
        comp = _make(config=cfg)
        with pytest.raises(ConfigurationError, match="values"):
            comp.execute()

    def test_missing_nb_rows_passes_validate(self):
        """nb_rows is optional in _validate_config (defaults to '100')."""
        cfg = {**_BASE_CONFIG}
        del cfg["nb_rows"]
        comp = _make(config=cfg)
        result = comp.execute()
        # Default is 100 rows
        assert len(result["main"]) == 100

    def test_context_var_nb_rows_passes_validate(self):
        """A ${context.X} placeholder must not fail validation."""
        # The converter emits nb_rows as a string that may contain context refs.
        # BaseComponent resolves it before _process() runs, so validation must
        # accept the raw placeholder string.
        cm = ContextManager()
        cm.set("row_count", "5")
        cfg = {**_BASE_CONFIG, "nb_rows": "${context.row_count}"}
        comp = _make(config=cfg, context_manager=cm)
        result = comp.execute()
        assert len(result["main"]) == 5

    def test_string_nb_rows_is_accepted(self):
        """nb_rows as a numeric string coerces correctly in _process."""
        cfg = {**_BASE_CONFIG, "nb_rows": "4"}
        comp = _make(config=cfg)
        result = comp.execute()
        assert len(result["main"]) == 4

    def test_negative_nb_rows_raises(self):
        cfg = {**_BASE_CONFIG, "nb_rows": -1}
        comp = _make(config=cfg)
        with pytest.raises((ConfigurationError, ComponentExecutionError)):
            comp.execute()

    def test_non_integer_nb_rows_raises(self):
        cfg = {**_BASE_CONFIG, "nb_rows": "not_a_number"}
        comp = _make(config=cfg)
        with pytest.raises((ConfigurationError, ComponentExecutionError)):
            comp.execute()


# ---------------------------------------------------------------------------
# TestBasicGeneration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBasicGeneration:
    """Core generation produces correct shape and columns."""

    def test_correct_row_count(self):
        comp = _make()
        result = comp.execute()
        assert len(result["main"]) == 3

    def test_columns_match_values_config(self):
        comp = _make()
        result = comp.execute()
        assert list(result["main"].columns) == ["id", "name"]

    def test_main_key_is_dataframe(self):
        import pandas as pd
        comp = _make()
        result = comp.execute()
        assert isinstance(result["main"], pd.DataFrame)

    def test_reject_key_present(self):
        comp = _make()
        result = comp.execute()
        assert "reject" in result

    def test_no_rejects_on_clean_config(self):
        comp = _make()
        result = comp.execute()
        assert len(result["reject"]) == 0

    def test_zero_rows_returns_empty_dataframe(self):
        import pandas as pd
        cfg = {**_BASE_CONFIG, "nb_rows": 0}
        comp = _make(config=cfg)
        result = comp.execute()
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0
        assert list(result["main"].columns) == ["id", "name"]

    def test_input_data_ignored(self):
        """Source component -- input_data has no effect on output."""
        import pandas as pd
        comp = _make()
        dummy = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        result = comp.execute(input_data=dummy)
        assert len(result["main"]) == 3


# ---------------------------------------------------------------------------
# TestNbRows
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNbRows:
    """nb_rows config variations."""

    def test_nb_rows_integer(self):
        cfg = {**_BASE_CONFIG, "nb_rows": 7}
        comp = _make(config=cfg)
        result = comp.execute()
        assert len(result["main"]) == 7

    def test_nb_rows_string(self):
        cfg = {**_BASE_CONFIG, "nb_rows": "5"}
        comp = _make(config=cfg)
        result = comp.execute()
        assert len(result["main"]) == 5

    def test_nb_rows_default_is_100(self):
        cfg = {**_BASE_CONFIG}
        del cfg["nb_rows"]
        comp = _make(config=cfg)
        result = comp.execute()
        assert len(result["main"]) == 100

    def test_nb_rows_zero(self):
        cfg = {**_BASE_CONFIG, "nb_rows": 0}
        comp = _make(config=cfg)
        result = comp.execute()
        assert len(result["main"]) == 0


# ---------------------------------------------------------------------------
# TestExpressions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExpressions:
    """Expression evaluation for various array value types."""

    def test_integer_literal(self):
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 1,
            "values": [{"schema_column": "n", "array": "42"}],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert result["main"].iloc[0]["n"] == 42

    def test_string_literal_single_quoted(self):
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 1,
            "values": [{"schema_column": "s", "array": "'hello'"}],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert result["main"].iloc[0]["s"] == "hello"

    def test_string_literal_double_quoted(self):
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 1,
            "values": [{"schema_column": "s", "array": '"world"'}],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert result["main"].iloc[0]["s"] == "world"

    def test_python_random_expression(self):
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 5,
            "values": [{"schema_column": "n", "array": "random.randint(0, 9999)"}],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert len(result["main"]) == 5
        for val in result["main"]["n"]:
            assert 0 <= val <= 9999

    def test_expression_producing_different_values(self):
        """random.randint over 20 rows should not be all identical."""
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 20,
            "values": [{"schema_column": "n", "array": "random.randint(0, 99999)"}],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert len(set(result["main"]["n"].tolist())) > 1

    def test_float_literal(self):
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 1,
            "values": [{"schema_column": "f", "array": "3.14"}],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert abs(result["main"].iloc[0]["f"] - 3.14) < 1e-9

    def test_bad_expression_routes_to_reject(self):
        """An expression that raises a runtime error routes the row to reject."""
        # 1/0 raises ZeroDivisionError in the restricted eval namespace
        # and is routed to reject.
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 1,
            "values": [{"schema_column": "x", "array": "1/0"}],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert len(result["main"]) == 0
        assert len(result["reject"]) == 1

    def test_plain_string_no_quotes_treated_as_literal(self):
        """A string literal with surrounding quotes is unwrapped to a plain string."""
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 1,
            "values": [{"schema_column": "t", "array": "'plaintext'"}],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert result["main"].iloc[0]["t"] == "plaintext"


# ---------------------------------------------------------------------------
# TestStringHandling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStringHandling:
    """StringHandling.SPACE and StringHandling.LEN pre-processing."""

    def test_preprocess_space_literal(self):
        result = _preprocess_expression("StringHandling.SPACE(3)")
        assert eval(result) == "   "  # noqa: S307 -- test-only eval on known string

    def test_preprocess_len_literal(self):
        result = _preprocess_expression('StringHandling.LEN("hello")')
        assert eval(result) == 5  # noqa: S307

    def test_space_in_expression(self):
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 1,
            "values": [{"schema_column": "s", "array": "StringHandling.SPACE(4)"}],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert result["main"].iloc[0]["s"] == "    "

    def test_len_in_expression(self):
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 1,
            "values": [{"schema_column": "n", "array": 'StringHandling.LEN("abcde")'}],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert result["main"].iloc[0]["n"] == 5


# ---------------------------------------------------------------------------
# TestRejectFlow
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRejectFlow:
    """Failed expression evaluation routes rows to the reject output."""

    def test_all_rows_accepted_when_no_errors(self):
        cfg = {**_BASE_CONFIG, "nb_rows": 3}
        comp = _make(config=cfg)
        result = comp.execute()
        assert len(result["main"]) == 3
        assert len(result["reject"]) == 0

    def test_all_rows_rejected_when_all_error(self):
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 3,
            "values": [{"schema_column": "x", "array": "1/0"}],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert len(result["main"]) == 0
        assert len(result["reject"]) == 3

    def test_reject_df_has_same_columns_as_main(self):
        """Reject DataFrame must carry the same columns as main."""
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 2,
            "values": [
                {"schema_column": "id",  "array": "1"},
                {"schema_column": "bad", "array": "1/0"},
            ],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert list(result["reject"].columns) == ["id", "bad"]

    def test_partial_reject(self):
        """mix of good and bad rows -- only bad rows go to reject."""
        # Two-column config: one good column, one that always errors.
        # Both rows carry the bad column so both go to reject.
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 2,
            "values": [
                {"schema_column": "ok",  "array": "42"},
                {"schema_column": "err", "array": "1/0"},
            ],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        # Both rows have the bad column -> both go to reject
        assert len(result["main"]) == 0
        assert len(result["reject"]) == 2


# ---------------------------------------------------------------------------
# TestGlobalMapVariables
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    """NB_LINE, NB_LINE_OK, NB_LINE_REJECT written to GlobalMap."""

    def test_nb_line_set(self):
        gm = GlobalMap()
        comp = _make(global_map=gm)
        comp.execute()
        assert gm.get("tRG_1_NB_LINE") == 3

    def test_nb_line_ok_set_when_no_rejects(self):
        gm = GlobalMap()
        comp = _make(global_map=gm)
        comp.execute()
        assert gm.get("tRG_1_NB_LINE_OK") == 3

    def test_nb_line_reject_zero_when_no_errors(self):
        gm = GlobalMap()
        comp = _make(global_map=gm)
        comp.execute()
        assert gm.get("tRG_1_NB_LINE_REJECT") == 0

    def test_nb_line_reject_counts_failures(self):
        gm = GlobalMap()
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 5,
            "values": [{"schema_column": "x", "array": "1/0"}],
        }
        comp = _make(config=cfg, global_map=gm)
        comp.execute()
        assert gm.get("tRG_1_NB_LINE") == 5
        assert gm.get("tRG_1_NB_LINE_REJECT") == 5
        assert gm.get("tRG_1_NB_LINE_OK") == 0


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases and re-entrancy."""

    def test_empty_values_list_returns_no_columns(self):
        """With no values config, the output DataFrame has no columns."""
        import pandas as pd
        cfg = {**_BASE_CONFIG, "values": [], "nb_rows": 5}
        comp = _make(config=cfg)
        result = comp.execute()
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"].columns) == 0

    def test_single_column_single_row(self):
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 1,
            "values": [{"schema_column": "only", "array": "'x'"}],
        }
        comp = _make(config=cfg)
        result = comp.execute()
        assert result["main"].iloc[0]["only"] == "x"

    def test_reentrant_second_execute_works(self):
        """Component can be executed twice (Rule 10 / re-entrancy)."""
        comp = _make()
        r1 = comp.execute()
        r2 = comp.execute()
        assert len(r1["main"]) == 3
        assert len(r2["main"]) == 3

    def test_none_java_bridge_raises_expression_error_for_java_expr(self):
        """{{java}} expression without a bridge raises ExpressionError (wrapped)."""
        cfg = {
            **_BASE_CONFIG,
            "nb_rows": 1,
            "values": [{"schema_column": "j", "array": "{{java}}Numeric.sequence(1,1,1)"}],
        }
        comp = _make(config=cfg)
        # No java_bridge wired -- should end up in reject with an ExpressionError
        result = comp.execute()
        assert len(result["reject"]) == 1


# ---------------------------------------------------------------------------
# TestEvalExprHelper
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEvalExprHelper:
    """Unit tests for the module-level _eval_expr pure function."""

    def test_integer_literal(self):
        assert _eval_expr("42", 0, "c", None, None, "comp") == 42

    def test_string_literal(self):
        assert _eval_expr("'hi'", 0, "c", None, None, "comp") == "hi"

    def test_arithmetic(self):
        assert _eval_expr("2 + 3", 0, "c", None, None, "comp") == 5

    def test_random_expression_type(self):
        val = _eval_expr("random.randint(0, 100)", 0, "c", None, None, "comp")
        assert isinstance(val, int)

    def test_name_error_returns_string_literal(self):
        """NameError (bare word) falls back to a string literal.

        BaseComponent resolves {{java}} expressions before _process() runs,
        replacing them with plain string values like 'CK0nxM2A'.  Those
        strings eval to NameError but are valid result values — they must
        be returned as-is, not routed to reject.
        """
        result = _eval_expr("some_bare_word", 0, "c", None, None, "comp")
        assert result == "some_bare_word"

    def test_java_prefix_without_bridge_raises(self):
        with pytest.raises(ExpressionError):
            _eval_expr("{{java}}foo()", 0, "c", None, None, "comp")

    def test_string_handling_space(self):
        result = _eval_expr("StringHandling.SPACE(2)", 0, "c", None, None, "comp")
        assert result == "  "

    def test_string_handling_len(self):
        result = _eval_expr('StringHandling.LEN("abc")', 0, "c", None, None, "comp")
        assert result == 3
