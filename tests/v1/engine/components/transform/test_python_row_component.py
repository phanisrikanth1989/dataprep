"""Tests for PythonRowComponent (tPythonRow engine implementation -- per-row).

Phase 8 Plan 04 Task 1 (D-09 mixin-first MRO; D-11 namespace whitelist;
D-14/D-16 revision 2 errorMessage-only REJECT; D-17/D-18 compile-once;
D-15/D-28 die_on_error semantics; AP-7 -- no _validate_output_row helper).

No ``@pytest.mark.java`` here -- PythonRowComponent does NOT touch the Java
bridge. Pure Python unit tests; 26 tests organized into the test classes
listed in the plan body.

Fixture pattern: Phase 7.2 (D-22) -- manually populate
``comp.config = dict(config)`` before any direct ``_validate_config`` /
``_process`` call because ``BaseComponent.__init__`` only sets
``_original_config``.
"""
import builtins as _builtins_module
from unittest.mock import patch

import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.transform._code_component_mixin import (
    CodeComponentMixin,
)
from src.v1.engine.components.transform.python_row_component import (
    PythonRowComponent,
)
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import (
    ComponentExecutionError,
    ConfigurationError,
)
from src.v1.engine.global_map import GlobalMap


# ----------------------------------------------------------------
# Fixture / helpers (Phase 7.2 D-22 pattern)
# ----------------------------------------------------------------


_DEFAULT_CONFIG = {
    "component_type": "PythonRowComponent",
    "python_code": 'output_row["a"] = input_row["a"]',
}


def _make_component(config=None, global_map=None, context_manager=None):
    """Build a PythonRowComponent with stock defaults.

    Manually populates ``comp.config`` with a fresh dict view of the input
    config so direct ``_validate_config`` / ``_process`` calls work without
    going through ``execute()`` (Phase 7.2 D-22 fixture pattern).
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager if context_manager is not None else ContextManager()
    cfg = config or _DEFAULT_CONFIG
    comp = PythonRowComponent(
        component_id="tPythonRow_1",
        config=dict(cfg),
        global_map=gm,
        context_manager=cm,
    )
    # Mirror what BaseComponent.execute() Step 1 would do, so direct
    # _process calls in unit tests have the same self.config view as a
    # real run.
    comp.config = dict(cfg)
    # Default to die_on_error=False so REJECT-flow tests are the natural
    # path; tests that need die_on_error=True flip the flag explicitly.
    comp.die_on_error = False
    return comp


# ----------------------------------------------------------------
# TestRegistration -- AP-12 / Rule 9
# ----------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """REGISTRY decorator wires the V1 name and the Talend alias."""

    def test_registry_resolves_v1_name(self):
        """Test 1: REGISTRY.get('PythonRowComponent') resolves."""
        assert REGISTRY.get("PythonRowComponent") is PythonRowComponent

    def test_registry_resolves_talend_name(self):
        """Test 2: REGISTRY.get('tPythonRow') resolves."""
        assert REGISTRY.get("tPythonRow") is PythonRowComponent


# ----------------------------------------------------------------
# TestValidation -- Rule 12 minimal _validate_config
# ----------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """``_validate_config`` checks key presence + container shape only."""

    def test_missing_python_code_raises(self):
        """Test 3: config without 'python_code' -> ConfigurationError."""
        config = dict(_DEFAULT_CONFIG)
        config.pop("python_code")
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        msg = str(ei.value)
        assert "[tPythonRow_1]" in msg
        assert "python_code" in msg

    def test_validate_accepts_context_var_literal(self):
        """Test 4: python_code with a ${context.X} literal passes (Rule 12).

        SKIP_RESOLUTION_KEYS keeps the literal verbatim, so it would
        NameError at exec time. The test only verifies _validate_config
        does NOT pre-empt this.
        """
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'x = "${context.VAR}"'
        comp = _make_component(config=config)
        # No raise -- shape is str-and-non-empty, content checks deferred.
        comp._validate_config()

    def test_output_schema_invalid_shape_raises(self):
        """Test 5: output_schema=42 -> ConfigurationError (Rule 12 shape check)."""
        config = dict(_DEFAULT_CONFIG)
        config["output_schema"] = 42
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        msg = str(ei.value)
        assert "[tPythonRow_1]" in msg
        assert "output_schema" in msg


# ----------------------------------------------------------------
# TestEdgeCases -- empty / None input, syntax error, AP-7 absence
# ----------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Empty / None / syntax-error edge cases plus the AP-7 absence check."""

    def test_empty_input_returns_empty_main(self):
        """Test 6: empty df -> {'main': empty df, 'reject': None}; compile NOT called."""
        df = pd.DataFrame()
        comp = _make_component()

        with patch.object(_builtins_module, "compile", wraps=_builtins_module.compile) as mock_compile:
            result = comp._process(input_data=df)

        # Compile is intentionally skipped for empty input -- nothing to run.
        mock_compile.assert_not_called()
        assert result["main"] is df  # passthrough (object identity)
        assert result["reject"] is None

    def test_none_input_returns_none_main(self):
        """Test 7: None -> {'main': None, 'reject': None}; compile NOT called."""
        comp = _make_component()

        with patch.object(_builtins_module, "compile", wraps=_builtins_module.compile) as mock_compile:
            result = comp._process(input_data=None)

        mock_compile.assert_not_called()
        assert result["main"] is None
        assert result["reject"] is None

    def test_user_syntax_error_raises_configuration_error(self):
        """Test 8: python_code='x =' -> ConfigurationError (D-27 -- syntax is config-time)."""
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = "x ="
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": [1, 2, 3]})

        with pytest.raises(ConfigurationError) as ei:
            comp._process(input_data=df)

        msg = str(ei.value)
        assert "[tPythonRow_1]" in msg
        assert "Syntax error" in msg
        # Original SyntaxError preserved as cause.
        assert isinstance(ei.value.__cause__, SyntaxError)

    def test_no_validate_output_row_method(self):
        """Test 26 (AP-7 fix): _validate_output_row is NOT defined on this class.

        BaseComponent step 7c handles output schema validation per Rule 11;
        the legacy 50-line per-row helper has been deleted.
        """
        assert "_validate_output_row" not in PythonRowComponent.__dict__


# ----------------------------------------------------------------
# TestRowExecution -- happy path; per-row mutations + context dict
# ----------------------------------------------------------------


@pytest.mark.unit
class TestRowExecution:
    """User code reads ``input_row``, mutates ``output_row``, reads ``context``."""

    def test_output_row_mutations_land_in_main(self):
        """Test 9: output_row['doubled'] = input_row['a'] * 2 across [1,2,3]."""
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'output_row["doubled"] = input_row["a"] * 2'
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": [1, 2, 3]})

        result = comp._process(input_data=df)

        main_df = result["main"]
        assert list(main_df["doubled"]) == [2, 4, 6]
        assert result["reject"] is None

    def test_input_row_reflects_current_row(self):
        """Test 10: each iteration sees its own input_row['a'] value (no stale binding).

        Use globalMap as a side-effect channel to capture per-iteration
        values. After a 3-row run we expect all three values captured.
        """
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = (
            'captured = globalMap.get("captured") or []; '
            'captured.append(input_row["a"]); '
            'globalMap.put("captured", captured); '
            'output_row["a"] = input_row["a"]'
        )
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": [10, 20, 30]})

        comp._process(input_data=df)

        assert comp.global_map.get("captured") == [10, 20, 30]

    def test_context_dict_readable(self):
        """Test 11: seeded context VAR1 is readable as context['VAR1'] in user code."""
        cm = ContextManager()
        cm.set("VAR1", "hello")
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'output_row["greet"] = context["VAR1"]'
        comp = _make_component(config=config, context_manager=cm)
        df = pd.DataFrame({"a": [1, 2]})

        result = comp._process(input_data=df)

        assert list(result["main"]["greet"]) == ["hello", "hello"]


# ----------------------------------------------------------------
# TestCompileOnce -- D-17 / D-18 / PERF-02 (compile invoked exactly once)
# ----------------------------------------------------------------


@pytest.mark.unit
class TestCompileOnce:
    """Compile is invoked ONCE per execute() invocation, not per row (PERF-02)."""

    def test_compile_called_once(self):
        """Test 12: 100-row DataFrame -> compile() called exactly once.

        Monkeypatch ``builtins.compile`` to count invocations and delegate
        to the real compile so the component still runs. The compile-once
        contract is the deterministic gate against AP-6 regressions.
        """
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'output_row["x"] = input_row["a"] * 2'
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": list(range(100))})

        calls = {"n": 0}
        real_compile = _builtins_module.compile

        def counting_compile(*args, **kwargs):
            calls["n"] += 1
            return real_compile(*args, **kwargs)

        with patch.object(_builtins_module, "compile", side_effect=counting_compile):
            result = comp._process(input_data=df)

        # PERF-02 / D-17: exactly one compile across the whole run.
        assert calls["n"] == 1
        # Sanity: the run actually produced 100 output rows.
        assert len(result["main"]) == 100

    def test_compile_filename_includes_component_id(self):
        """Test 13: compile() filename arg matches '<python_row_component:{id}>'."""
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'output_row["x"] = input_row["a"]'
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": [1]})

        captured = {"filename": None}
        real_compile = _builtins_module.compile

        def capturing_compile(source, filename, mode, *args, **kwargs):
            captured["filename"] = filename
            return real_compile(source, filename, mode, *args, **kwargs)

        with patch.object(_builtins_module, "compile", side_effect=capturing_compile):
            comp._process(input_data=df)

        assert captured["filename"] == "<python_row_component:tPythonRow_1>"


# ----------------------------------------------------------------
# TestRejectFlow -- revision 2 D-14/D-16 errorMessage-only REJECT
# ----------------------------------------------------------------


@pytest.mark.unit
class TestRejectFlow:
    """Per-row error routes the input row to reject with one errorMessage column."""

    def test_per_row_exception_routes_to_reject(self):
        """Test 14: row with a==2 triggers ZeroDivisionError -> main 2 rows, reject 1.

        Uses a natural exception (division by zero) rather than ``raise
        ValueError(...)`` because the D-11 whitelist does NOT expose
        exception class names like ``ValueError`` to user code -- they
        would themselves raise ``NameError`` if referenced.
        """
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = (
            'if input_row["a"] == 2: bad = 1 / 0\n'
            'output_row["a"] = input_row["a"]'
        )
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": [1, 2, 3]})

        result = comp._process(input_data=df)

        main_df = result["main"]
        reject_df = result["reject"]
        assert list(main_df["a"]) == [1, 3]
        assert reject_df is not None
        assert len(reject_df) == 1
        # errorMessage carries 'ZeroDivisionError: division by zero'.
        assert "ZeroDivisionError" in str(reject_df.iloc[0]["errorMessage"])
        assert "division by zero" in str(reject_df.iloc[0]["errorMessage"])

    def test_reject_schema_is_errorMessage_only(self):
        """Test 15 (revision 2 D-16): reject has 'errorMessage' but NO 'errorCode'.

        Catches both the legacy AP-5 string-errorCode bug and any
        revision-1-era integer-errorCode design.
        """
        config = dict(_DEFAULT_CONFIG)
        # KeyError on a missing column -- no exception class name needed.
        config["python_code"] = 'output_row["x"] = input_row["NOT_THERE"]'
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": [1]})

        result = comp._process(input_data=df)

        reject_df = result["reject"]
        assert reject_df is not None
        cols = reject_df.columns.tolist()
        assert "errorMessage" in cols, (
            f"Expected 'errorMessage' column in reject; got {cols}"
        )
        assert "errorCode" not in cols, (
            f"errorCode column is FORBIDDEN under revision 2 D-16; got {cols}"
        )
        # errorMessage must be the LAST (appended) column.
        assert cols[-1] == "errorMessage"

    def test_reject_none_when_all_rows_succeed(self):
        """Test 16: all rows pass -> reject is None (not an empty DataFrame)."""
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'output_row["a"] = input_row["a"] + 1'
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": [1, 2, 3]})

        result = comp._process(input_data=df)

        assert result["reject"] is None
        assert list(result["main"]["a"]) == [2, 3, 4]

    def test_reject_includes_original_input_columns(self):
        """Test 17: reject preserves original input cols, then appends errorMessage.

        Input cols ['a', 'b']; failing row -> reject cols ['a', 'b', 'errorMessage']
        in that exact order. NO 'errorCode' column anywhere.

        Uses a natural exception (missing-key dict access) rather than
        ``raise ...`` because the D-11 whitelist does not expose exception
        class names to user code.
        """
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'output_row["x"] = input_row["NOPE"]'
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": [1], "b": ["x"]})

        result = comp._process(input_data=df)

        reject_df = result["reject"]
        assert reject_df is not None
        assert reject_df.columns.tolist() == ["a", "b", "errorMessage"]
        # Original input data preserved verbatim.
        assert reject_df.iloc[0]["a"] == 1
        assert reject_df.iloc[0]["b"] == "x"
        assert "KeyError" in str(reject_df.iloc[0]["errorMessage"])
        assert "errorCode" not in reject_df.columns


# ----------------------------------------------------------------
# TestDieOnError -- D-15 / D-28 fatal mode
# ----------------------------------------------------------------


@pytest.mark.unit
class TestDieOnError:
    """``die_on_error=True`` raises on first per-row failure with row index."""

    def test_die_on_error_true_raises_on_first_failure(self):
        """Test 18: die_on_error=True; row 1 fails -> ComponentExecutionError raised.

        Uses ZeroDivisionError (1 / 0) -- D-11 namespace does not expose
        exception class names so we provoke the failure naturally.
        """
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = (
            'if input_row["a"] == 2: bad = 1 / 0\n'
            'output_row["a"] = input_row["a"]'
        )
        comp = _make_component(config=config)
        comp.die_on_error = True
        df = pd.DataFrame({"a": [1, 2, 3]})

        with pytest.raises(ComponentExecutionError):
            comp._process(input_data=df)

    def test_die_on_error_message_includes_row_index(self):
        """Test 19: error message names the offending row index ('row index 1')."""
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = (
            'if input_row["a"] == 2: bad = 1 / 0\n'
            'output_row["a"] = input_row["a"]'
        )
        comp = _make_component(config=config)
        comp.die_on_error = True
        df = pd.DataFrame({"a": [1, 2, 3]})

        with pytest.raises(ComponentExecutionError) as ei:
            comp._process(input_data=df)

        msg = str(ei.value)
        assert "[tPythonRow_1]" in msg
        # row index 1 is the second row (where a == 2).
        assert "row index 1" in msg or "row 1" in msg
        assert "ZeroDivisionError" in msg


# ----------------------------------------------------------------
# TestNamespaceWhitelist -- D-11 / D-12 blocked names route to reject
# ----------------------------------------------------------------


@pytest.mark.unit
class TestNamespaceWhitelist:
    """``os``, ``sys``, ``subprocess``, ``__import__``, ``open``, ``exec``,
    ``eval``, ``compile`` are NOT exposed; user code referencing them raises
    ``NameError`` which routes to reject (die_on_error=False default).
    """

    @staticmethod
    def _assert_blocked(name: str, code: str):
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = code
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": [1]})

        result = comp._process(input_data=df)

        reject_df = result["reject"]
        assert reject_df is not None, (
            f"Expected reject row for blocked name {name!r}, got None"
        )
        assert len(reject_df) == 1
        msg = str(reject_df.iloc[0]["errorMessage"])
        assert "NameError" in msg, (
            f"Expected NameError for blocked name {name!r}, got: {msg}"
        )
        assert name in msg, (
            f"Expected blocked name {name!r} in errorMessage, got: {msg}"
        )

    def test_os_blocked(self):
        """Test 20: 'os.getcwd()' -> NameError row routed to reject."""
        self._assert_blocked("os", "os.getcwd()")

    def test_subprocess_blocked(self):
        """Test 21: 'subprocess.run(...)' -> NameError row routed to reject."""
        self._assert_blocked("subprocess", 'subprocess.run(["ls"])')

    def test_open_blocked(self):
        """Test 22: 'open(...)' -> NameError row routed to reject."""
        self._assert_blocked("open", 'f = open("x.txt")')

    def test_eval_blocked(self):
        """Test 23: 'eval(...)' -> NameError row routed to reject."""
        self._assert_blocked("eval", 'eval("1+1")')


# ----------------------------------------------------------------
# TestStats -- AP-3 (no manual _update_stats)
# ----------------------------------------------------------------


@pytest.mark.unit
class TestStats:
    """BaseComponent step 8 counts NB_LINE; component never calls _update_stats."""

    def test_no_manual_update_stats(self):
        """Test 24: _update_stats is NEVER invoked from _process."""
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'output_row["a"] = input_row["a"]'
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": [1, 2, 3]})

        with patch.object(comp, "_update_stats") as mock_update:
            comp._process(input_data=df)

        mock_update.assert_not_called()


# ----------------------------------------------------------------
# TestContextMixin -- AP-4 (inherited from CodeComponentMixin)
# ----------------------------------------------------------------


@pytest.mark.unit
class TestContextMixin:
    """``_get_context_dict`` is INHERITED from CodeComponentMixin (D-09 / AP-4 fix)."""

    def test_get_context_dict_inherited_from_mixin(self):
        """Test 25: comp is-a CodeComponentMixin AND not redefined locally."""
        comp = _make_component()
        assert isinstance(comp, CodeComponentMixin)
        # Method reachable via inheritance.
        assert hasattr(PythonRowComponent, "_get_context_dict")
        # NOT defined directly on the subclass (no copy).
        assert "_get_context_dict" not in PythonRowComponent.__dict__


# ----------------------------------------------------------------
# TestCoverageLift_14_05 (COV-PRC-001)
#
# Target missed lines:
#   - 224-225 (_build_row_namespace: routines spread + nested mapping)
#   - 281     (python_code is not a string -> ConfigurationError)
#   - 285     (python_code empty after resolution -> ConfigurationError)
# ----------------------------------------------------------------


@pytest.mark.unit
class TestCoverageLift1405:
    """Targeted coverage for residual missed branches in python_row_component.py."""

    def test_routines_dict_is_spread_and_namespaced_in_namespace(self):
        # Hits lines 224-225: ns["routines"] = routines + ns.update(routines).
        # Inject a fake python_routine_manager that returns a non-empty mapping
        # so the conditional branch fires.
        config = dict(_DEFAULT_CONFIG)
        # User code reads BOTH the bare-name and the namespaced view, asserting
        # via output_row that both wires landed.
        config["python_code"] = (
            'output_row["bare"] = my_helper(input_row["a"])\n'
            'output_row["nested"] = routines["my_helper"](input_row["a"])'
        )
        comp = _make_component(config=config)

        class _FakeRoutineMgr:
            def get_all_routines(self):
                return {"my_helper": lambda x: x * 10}

        comp.python_routine_manager = _FakeRoutineMgr()

        df = pd.DataFrame({"a": [3]})
        result = comp._process(input_data=df)
        main = result["main"]
        assert result["reject"] is None
        assert main.iloc[0]["bare"] == 30
        assert main.iloc[0]["nested"] == 30

    def test_python_code_not_a_string_raises_configuration_error(self):
        # Hits line 281: isinstance(python_code, str) is False.
        config = {
            "component_type": "PythonRowComponent",
            "python_code": 42,  # int -- type mismatch (passes _validate_config truthy check)
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": [1, 2]})
        with pytest.raises(ConfigurationError) as excinfo:
            comp._process(input_data=df)
        assert "must be a string" in str(excinfo.value)
        assert "tPythonRow_1" in str(excinfo.value)

    def test_python_code_whitespace_only_raises_configuration_error(self):
        # Hits line 285: python_code.strip() is empty after resolution.
        config = {
            "component_type": "PythonRowComponent",
            "python_code": "   \n\t  ",  # truthy (passes _validate_config)
                                          # but empty after strip()
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({"a": [1, 2]})
        with pytest.raises(ConfigurationError) as excinfo:
            comp._process(input_data=df)
        assert "non-empty after resolution" in str(excinfo.value)
        assert "tPythonRow_1" in str(excinfo.value)
