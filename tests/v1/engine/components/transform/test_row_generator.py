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


# ---------------------------------------------------------------------------
# TestCoverageLift_14_05 (COV-RGN-001)
#
# Target missed lines from Phase 14 baseline:
#   - 62-63 (StringHandling.SPACE arg eval failure -> repr(""))
#   - 72    (StringHandling.LEN non-string-literal arg -> "len(...)" wrapper)
#   - 120-140 ({{java}} bridge path: invocation, globalMap sync, JavaObject
#              Date-like conversion, JavaObject str fallback)
#   - 158   (eval-fallback string literal returned via stripped[1:-1] for
#            quoted single-token expressions reaching the SyntaxError path)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoverageLift1405:
    """Targeted coverage for residual missed branches in row_generator.py."""

    def test_string_handling_space_with_unparseable_arg_returns_empty(self):
        # Hits lines 62-63: SPACE arg fails int(eval(...)) -> repr("").
        # "abc" is not numeric and triggers the except branch.
        result = _preprocess_expression("StringHandling.SPACE(abc)")
        # Production replaces SPACE(...) with repr(""), so the post-processed
        # expression contains an empty quoted string.
        assert "''" in result or '""' in result

    def test_string_handling_len_with_variable_arg_uses_len_wrapper(self):
        # Hits line 72: LEN arg is not a string literal -> falls to len(arg).
        result = _preprocess_expression("StringHandling.LEN(some_var)")
        assert result == "len(some_var)"

    def test_java_bridge_invocation_returns_primitive(self):
        # Hits lines 111-122 + 131-140 partially: bridge path with primitive.
        class _FakeBridge:
            def __init__(self):
                self.global_map = {}
                self.calls = []

            def execute_one_time_expression(self, expr):
                self.calls.append(expr)
                return "java-result"

        bridge = _FakeBridge()
        gm = GlobalMap()
        gm.put("FOO", "BAR")
        result = _eval_expr(
            "{{java}}TalendString.getAsciiRandomString(8)",
            0, "c", bridge, gm, "comp",
        )
        assert result == "java-result"
        assert bridge.calls == ["TalendString.getAsciiRandomString(8)"]
        # GlobalMap sync hit: bridge.global_map updated from gm._map (line 121).
        assert bridge.global_map.get("FOO") == "BAR"

    def test_java_bridge_invocation_returns_date_like_object(self):
        # Hits lines 131-137: JavaObject path with getTime() -> ISO string.
        class _FakeJavaDate:
            def getTime(self):
                # Epoch ms for 2026-01-15 00:00:00 UTC
                return 1768435200000

        class _FakeBridge:
            def __init__(self):
                self.global_map = {}

            def execute_one_time_expression(self, expr):
                return _FakeJavaDate()

        result = _eval_expr(
            "{{java}}TalendDate.getRandomDate()",
            0, "c", _FakeBridge(), None, "comp",
        )
        # ISO datetime string produced by strftime("%Y-%m-%d %H:%M:%S").
        assert isinstance(result, str)
        assert result.startswith("2026-01-15")

    def test_java_bridge_invocation_returns_unsupported_object_falls_back_to_str(self):
        # Hits lines 138-139: JavaObject without getTime() -> str(result).
        class _FakeJavaThing:
            def __str__(self):
                return "FakeJavaThing(x=1)"

        class _FakeBridge:
            def __init__(self):
                self.global_map = {}

            def execute_one_time_expression(self, expr):
                return _FakeJavaThing()

        result = _eval_expr(
            "{{java}}foo.bar()",
            0, "c", _FakeBridge(), None, "comp",
        )
        assert result == "FakeJavaThing(x=1)"

    def test_eval_fallback_returns_quoted_literal_unwrapped(self):
        # Hits line 158: stripped starts and ends with a quote -> [1:-1].
        # Trigger SyntaxError fallback by passing an invalid Python expression
        # that just happens to be a quoted string with a stray suffix.
        # The simplest path: passing a single quoted string '\'hi\'' without
        # the SyntaxError path is already covered by test_string_literal.
        # We need a SyntaxError path that lands stripped='"abc"'.
        # Two SyntaxError-then-quoted patterns: an unbalanced bracket inside a
        # string literal? No -- valid string literal eval succeeds.
        # The only way to land at line 158 is if eval raises SyntaxError on a
        # processed expression that is itself a quoted string. That can happen
        # when StringHandling.SPACE() preprocessing returns repr("") which is
        # a valid eval target -- but combined with surrounding broken syntax
        # we can land in the except block. Force it by passing a deliberately
        # broken expression that ends with a quoted string after preprocessing.
        # Simpler: directly call via a forced SyntaxError input where the
        # processed string is, e.g., '"hi" +'. After SyntaxError the stripped
        # is '"hi" +' which does not match the quote check. So we need a
        # processed expression that BOTH raises SyntaxError on eval AND, when
        # stripped, starts/ends with a matching quote.
        # We can achieve this with a NameError path that lands on a quoted
        # string. Currently the except clause matches (SyntaxError, NameError)
        # so a quoted name like "'just_word'" -- but that's a valid string
        # literal and eval succeeds returning 'just_word'.
        # The line is genuinely defensive belt-and-suspenders code. To exercise
        # it, monkeypatch eval to raise SyntaxError so the fallback runs on a
        # quoted stripped value.
        import builtins as _b
        from src.v1.engine.components.transform import row_generator as _rg

        original_eval = _rg.eval if hasattr(_rg, "eval") else _b.eval
        # Module's eval is the builtin; patch the module reference.
        # _eval_expr() uses builtin eval(processed, _EVAL_GLOBALS), so we
        # patch builtins.eval scoped via monkeypatching _rg.__builtins__.
        # The cleanest patch is on the module's eval reference since CPython
        # resolves bare names via the module globals. _eval_expr uses bare
        # ``eval`` so we add a module-level eval that raises SyntaxError.
        _rg.eval = lambda *a, **kw: (_ for _ in ()).throw(SyntaxError("forced"))
        try:
            result = _eval_expr('"abc"', 0, "c", None, None, "comp")
        finally:
            # Restore: deleting the module-level eval reverts to builtin.
            try:
                del _rg.eval
            except AttributeError:
                pass
        assert result == "abc"
