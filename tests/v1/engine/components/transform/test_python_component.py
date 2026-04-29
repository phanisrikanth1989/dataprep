"""Tests for PythonComponent (tPython / tPythonComponent engine implementation -- one-shot).

Phase 8 Plan 02 Task 1 (D-09 mixin-first MRO; D-11 namespace whitelist;
D-12 breaking-change vs legacy os/sys exposure; D-29 passthrough).

No ``@pytest.mark.java`` here -- PythonComponent does NOT touch the Java
bridge. Pure Python unit tests; ~21 tests organized into the test classes
listed in the plan body.

Fixture pattern: Phase 7.2 (D-22) -- manually populate
``comp.config = dict(config)`` before any direct ``_validate_config`` /
``_process`` call because ``BaseComponent.__init__`` only sets
``_original_config``.
"""
from unittest.mock import patch

import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.transform._code_component_mixin import (
    CodeComponentMixin,
)
from src.v1.engine.components.transform.python_component import PythonComponent
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
    "component_type": "PythonComponent",
    "python_code": 'globalMap.put("hello", "world")',
}


def _make_component(config=None, global_map=None, context_manager=None):
    """Build a PythonComponent with stock defaults.

    Manually populates ``comp.config`` with a deepcopy of the input config so
    direct ``_validate_config`` / ``_process`` calls work without going through
    ``execute()`` (Phase 7.2 D-22 fixture pattern).
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager if context_manager is not None else ContextManager()
    comp = PythonComponent(
        component_id="tPython_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    # Mirror what BaseComponent.execute() Step 1 would do, so direct _process
    # calls in unit tests have the same self.config view as a real run.
    comp.config = dict(config or _DEFAULT_CONFIG)
    return comp


# ----------------------------------------------------------------
# TestRegistration -- AP-12 / Rule 9
# ----------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """REGISTRY decorator wires the V1 name and both Talend aliases (AP-12 fix)."""

    def test_registry_resolves_v1_name(self):
        """Test 1: REGISTRY.get('PythonComponent') returns PythonComponent class."""
        assert REGISTRY.get("PythonComponent") is PythonComponent

    def test_registry_resolves_talend_aliases(self):
        """Test 2: REGISTRY.get('tPython') and 'tPythonComponent' both return PythonComponent."""
        assert REGISTRY.get("tPython") is PythonComponent
        assert REGISTRY.get("tPythonComponent") is PythonComponent


# ----------------------------------------------------------------
# TestValidation -- Rule 12 minimal _validate_config
# ----------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """``_validate_config`` checks key presence only (Rule 12)."""

    def test_missing_python_code_raises_configuration_error(self):
        """Test 3: config without 'python_code' -> ConfigurationError."""
        config = dict(_DEFAULT_CONFIG)
        config.pop("python_code")
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        msg = str(ei.value)
        assert "[tPython_1]" in msg
        assert "python_code" in msg

    def test_validate_accepts_context_var_literal(self):
        """Test 4: python_code with a ${context.X} literal passes validate (Rule 12 -- defer content).

        Note: SKIP_RESOLUTION_KEYS keeps the literal verbatim, so it will
        NameError at exec time. The test verifies _validate_config does
        NOT pre-empt this.
        """
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'x = "${context.VAR}"'
        comp = _make_component(config=config)
        # No raise -- shape is str-and-non-empty, content check happens later.
        comp._validate_config()


# ----------------------------------------------------------------
# TestExecution -- happy path; round-trip globalMap and context
# ----------------------------------------------------------------


@pytest.mark.unit
class TestExecution:
    """User code reads/writes ``globalMap`` and reads ``context`` correctly."""

    def test_globalmap_write_visible_after_execute(self):
        """Test 5: globalMap.put in user code is visible after _process()."""
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'globalMap.put("k", "v")'
        comp = _make_component(config=config)

        comp._process(input_data=None)

        assert comp.global_map.get("k") == "v"

    def test_context_dict_readable_in_user_code(self):
        """Test 6: context['VAR1'] resolves to the seeded context value."""
        cm = ContextManager()
        cm.set("VAR1", "hello")
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'globalMap.put("got", context["VAR1"])'
        comp = _make_component(config=config, context_manager=cm)

        comp._process(input_data=None)

        assert comp.global_map.get("got") == "hello"


# ----------------------------------------------------------------
# TestNamespaceWhitelist -- D-11 / D-12 breaking change
# ----------------------------------------------------------------


@pytest.mark.unit
class TestNamespaceWhitelist:
    """D-11 / D-12: ``os``, ``sys``, ``subprocess``, ``__import__``, ``open``,
    ``exec``, ``eval``, ``compile`` are NOT exposed; user code referencing
    them raises ``NameError`` at exec time, which is wrapped as
    ``ComponentExecutionError``.
    """

    @staticmethod
    def _assert_blocked(name: str, code: str):
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = code
        comp = _make_component(config=config)
        with pytest.raises(ComponentExecutionError) as ei:
            comp._process(input_data=None)
        msg = str(ei.value)
        # Wrapper preserves the underlying exception class + message.
        assert "NameError" in msg, (
            f"Expected wrapped NameError for blocked name {name!r}, got: {msg}"
        )
        assert name in msg, (
            f"Expected blocked name {name!r} to appear in the error, got: {msg}"
        )
        assert "[tPython_1]" in msg

    def test_os_access_blocked(self):
        """Test 7: 'os.getcwd()' -> NameError -> ComponentExecutionError."""
        self._assert_blocked("os", "os.getcwd()")

    def test_sys_access_blocked(self):
        """Test 8: 'sys.exit(0)' -> NameError -> ComponentExecutionError."""
        self._assert_blocked("sys", "sys.exit(0)")

    def test_subprocess_access_blocked(self):
        """Test 9: 'subprocess.run(...)' -> NameError -> ComponentExecutionError."""
        self._assert_blocked("subprocess", 'subprocess.run(["ls"])')

    def test_dunder_import_blocked(self):
        """Test 10: '__import__("os")' -> NameError -> ComponentExecutionError."""
        self._assert_blocked("__import__", '__import__("os")')

    def test_open_blocked(self):
        """Test 11: 'f = open("x.txt")' -> NameError -> ComponentExecutionError."""
        self._assert_blocked("open", 'f = open("x.txt")')

    def test_exec_blocked(self):
        """Test 12: 'exec("1+1")' -> NameError -> ComponentExecutionError."""
        self._assert_blocked("exec", 'exec("1+1")')

    def test_eval_blocked(self):
        """Test 13: 'eval("1+1")' -> NameError -> ComponentExecutionError."""
        self._assert_blocked("eval", 'eval("1+1")')

    def test_compile_blocked(self):
        """Test 14: 'compile("1+1","<x>","eval")' -> NameError -> ComponentExecutionError."""
        self._assert_blocked("compile", 'compile("1+1","<x>","eval")')


# ----------------------------------------------------------------
# TestImports -- whitelisted modules accessible
# ----------------------------------------------------------------


@pytest.mark.unit
class TestImports:
    """D-11 whitelist: pd, np, datetime, json, re, math, Decimal are accessible."""

    def test_safe_modules_accessible(self):
        """Test 15: datetime.datetime.now() and math.pi succeed in user code."""
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = (
            'globalMap.put("now", datetime.datetime.now()); '
            'globalMap.put("pi", math.pi)'
        )
        comp = _make_component(config=config)

        comp._process(input_data=None)

        assert comp.global_map.get("now") is not None
        # math.pi is approximately 3.14159; just check it's a float close to it.
        pi_value = comp.global_map.get("pi")
        assert isinstance(pi_value, float)
        assert 3.14 < pi_value < 3.15

    def test_pandas_numpy_decimal_accessible(self):
        """Test 16: Decimal('1.5') and np.array([1,2]).sum() succeed."""
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = (
            'globalMap.put("d", Decimal("1.5")); '
            'globalMap.put("a", int(np.array([1,2]).sum()))'
        )
        comp = _make_component(config=config)

        comp._process(input_data=None)

        from decimal import Decimal as _DecimalCls
        assert comp.global_map.get("d") == _DecimalCls("1.5")
        assert comp.global_map.get("a") == 3


# ----------------------------------------------------------------
# TestEdgeCases -- D-29 passthrough + None input + syntax error wrapping
# ----------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Passthrough semantics (D-29) and syntax-error wrapping."""

    def test_passthrough_returns_input_unchanged(self):
        """Test 17: input DataFrame -> result['main'] is input_data; reject is None (D-29)."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'globalMap.put("ran", True)'
        comp = _make_component(config=config)

        result = comp._process(input_data=df)

        # Same object reference (passthrough, not copy).
        assert result["main"] is df
        assert result["reject"] is None

    def test_no_input_returns_main_none(self):
        """Test 18: input=None -> {'main': None, 'reject': None}; user code still ran."""
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'globalMap.put("ran", True)'
        comp = _make_component(config=config)

        result = comp._process(input_data=None)

        assert result["main"] is None
        assert result["reject"] is None
        assert comp.global_map.get("ran") is True

    def test_user_syntax_error_wraps_to_component_execution_error(self):
        """Test 19: invalid python_code -> ComponentExecutionError wrapping SyntaxError."""
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = "x ="  # syntax error
        comp = _make_component(config=config)

        with pytest.raises(ComponentExecutionError) as ei:
            comp._process(input_data=None)

        msg = str(ei.value)
        assert "[tPython_1]" in msg
        assert "SyntaxError" in msg
        # Original exception preserved as cause (raise ... from e).
        assert isinstance(ei.value.__cause__, SyntaxError)


# ----------------------------------------------------------------
# TestStats -- AP-3 (no manual _update_stats)
# ----------------------------------------------------------------


@pytest.mark.unit
class TestStats:
    """BaseComponent counts NB_LINE from result['main']; component never calls _update_stats (AP-3)."""

    def test_no_manual_update_stats(self):
        """Test 20: _update_stats is NEVER invoked from _process (manual stats path is forbidden)."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = 'globalMap.put("ran", True)'
        comp = _make_component(config=config)

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
        """Test 21: comp is-a CodeComponentMixin AND PythonComponent does not redefine _get_context_dict."""
        comp = _make_component()
        # Inherits from mixin (D-09 mixin-first MRO).
        assert isinstance(comp, CodeComponentMixin)
        # Method is reachable on the class (via inheritance).
        assert hasattr(PythonComponent, "_get_context_dict")
        # But NOT defined directly on PythonComponent itself (no copy).
        assert "_get_context_dict" not in PythonComponent.__dict__
