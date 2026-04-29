"""Tests for JavaRowComponent (tJavaRow engine implementation -- per-row).

Phase 8 Plan 03 Task 1 (D-09 mixin-first MRO; D-07/D-08 imports prepend; D-19 / D-20
bridge-managed sync; revision 2 -- NO REJECT for java_row, Talend parity verified
via Talaxie tJavaRow_java.xml + tJavaRow_main.javajet).

Mock-based unit tests for Tests 1-15 (no JVM required). Tests 16-18 are
real-bridge integration tests gated behind ``@pytest.mark.java`` and the
``java_bridge`` fixture (Plan 05 wires the fixture; until then they collect
but skip if the bridge JAR is unavailable).

Per project memory ``feedback_test_real_bridge``: mock-only is FORBIDDEN for
Java components, so Tests 16-18 below MUST exercise a real bridge once the
fixture is in place.

Run instructions:
    Unit-only:    pytest tests/v1/engine/components/transform/test_java_row_component.py -m "not java"
    Real bridge:  pytest tests/v1/engine/components/transform/test_java_row_component.py -m java

Fixture pattern: Phase 7.2 (D-22) -- manually populate ``comp.config = dict(config)``
before any direct ``_validate_config`` / ``_process`` call because
``BaseComponent.__init__`` only sets ``_original_config``.

NO TestRejectFlow class -- revision 2 explicitly drops the prior REJECT
contract; tJavaRow has no reject flow in Talend or in this component.
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.transform._code_component_mixin import CodeComponentMixin
from src.v1.engine.components.transform.java_row_component import JavaRowComponent
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ----------------------------------------------------------------
# Fixture / helpers (Phase 7.2 D-22 pattern)
# ----------------------------------------------------------------


_DEFAULT_CONFIG = {
    "component_type": "JavaRowComponent",
    "java_code": 'output_row.put("a", input_row.get("a"));',
    "imports": "",
    "output_schema": {"a": "int"},
}


def _make_component(config=None, global_map=None, java_bridge=None):
    """Build a JavaRowComponent with stock defaults.

    Manually populates ``comp.config`` with a deepcopy of the input config so
    direct ``_validate_config`` / ``_process`` calls work without going through
    ``execute()`` (Phase 7.2 D-22 fixture pattern).
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    comp = JavaRowComponent(
        component_id="tJavaRow_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    # Mirror what BaseComponent.execute() Step 1 would do, so direct _process
    # calls in unit tests have the same self.config view as a real run.
    comp.config = dict(config or _DEFAULT_CONFIG)
    if java_bridge is not None:
        comp.java_bridge = java_bridge
    return comp


# ----------------------------------------------------------------
# TestRegistration -- AP-12 / Rule 9
# ----------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """REGISTRY decorator wires both V1 and Talend names (AP-12 fix)."""

    def test_registry_resolves_v1_name(self):
        """Test 1: REGISTRY.get('JavaRowComponent') returns JavaRowComponent class."""
        assert REGISTRY.get("JavaRowComponent") is JavaRowComponent

    def test_registry_resolves_talend_name(self):
        """Test 2: REGISTRY.get('tJavaRow') returns JavaRowComponent class."""
        assert REGISTRY.get("tJavaRow") is JavaRowComponent


# ----------------------------------------------------------------
# TestValidation -- Rule 12 minimal _validate_config
# ----------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """``_validate_config`` checks key presence + container shape only."""

    def test_missing_java_code_raises(self):
        """Test 3: config without 'java_code' -> ConfigurationError."""
        config = dict(_DEFAULT_CONFIG)
        config.pop("java_code")
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        msg = str(ei.value)
        assert "[tJavaRow_1]" in msg
        assert "java_code" in msg

    def test_non_string_imports_raises(self):
        """Test 4: imports=123 -> ConfigurationError."""
        config = dict(_DEFAULT_CONFIG)
        config["imports"] = 123
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        assert "imports" in str(ei.value)
        assert "[tJavaRow_1]" in str(ei.value)

    def test_output_schema_invalid_shape_raises(self):
        """Test 5: output_schema=42 (not dict/list) -> ConfigurationError."""
        config = dict(_DEFAULT_CONFIG)
        config["output_schema"] = 42
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        assert "output_schema" in str(ei.value)
        assert "[tJavaRow_1]" in str(ei.value)

    def test_validate_accepts_context_var_literals(self):
        """Test 6: java_code containing literal ${context.X} passes _validate_config (Rule 12 -- defer content check)."""
        config = dict(_DEFAULT_CONFIG)
        config["java_code"] = '// ${context.MY_VAR} -- literal kept; SKIP_RESOLUTION_KEYS protects it'
        comp = _make_component(config=config)
        # No raise -- shape is str, content check happens later.
        comp._validate_config()


# ----------------------------------------------------------------
# TestEdgeCases -- empty input short-circuit + AP-9 bridge guard
# ----------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Empty / None input short-circuits without invoking the bridge."""

    def test_empty_input_returns_main_empty_no_reject(self):
        """Test 7: empty DataFrame -> {'main': empty df, 'reject': None}; bridge NOT called."""
        empty_df = pd.DataFrame()
        bridge = MagicMock()
        comp = _make_component(java_bridge=bridge)

        result = comp._process(input_data=empty_df)

        assert result["main"] is empty_df
        assert result["reject"] is None
        bridge.execute_java_row.assert_not_called()

    def test_none_input_returns_none_main_no_reject(self):
        """Test 8: None input -> {'main': None, 'reject': None}; bridge NOT called."""
        bridge = MagicMock()
        comp = _make_component(java_bridge=bridge)

        result = comp._process(input_data=None)

        assert result["main"] is None
        assert result["reject"] is None
        bridge.execute_java_row.assert_not_called()

    def test_no_java_bridge_raises_component_execution_error(self):
        """Test 9: self.java_bridge=None with non-empty input -> ComponentExecutionError (AP-9 fix)."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        comp = _make_component()
        # explicit -- BaseComponent.__init__ already sets self.java_bridge=None
        comp.java_bridge = None
        with pytest.raises(ComponentExecutionError) as ei:
            comp._process(input_data=df)
        assert "[tJavaRow_1]" in str(ei.value)
        assert "no java bridge" in str(ei.value).lower()


# ----------------------------------------------------------------
# TestImports -- D-07 / D-08
# ----------------------------------------------------------------


@pytest.mark.unit
class TestImports:
    """``imports`` is prepended to ``java_code`` with a newline (D-07/D-08)."""

    def test_imports_prepended_with_newline(self):
        """Test 10: bridge call java_code arg starts with imports + '\\n' + actual_code."""
        config = dict(_DEFAULT_CONFIG)
        config["imports"] = "import java.util.Date;"
        config["java_code"] = 'output_row.put("when", new Date());'
        df = pd.DataFrame({"a": [1]})
        bridge = MagicMock()
        bridge.execute_java_row.return_value = pd.DataFrame({"when": [None]})
        comp = _make_component(config=config, java_bridge=bridge)

        comp._process(input_data=df)

        bridge.execute_java_row.assert_called_once()
        kwargs = bridge.execute_java_row.call_args.kwargs
        sent = kwargs["java_code"]
        assert sent == "import java.util.Date;\n" + 'output_row.put("when", new Date());'

    def test_empty_imports_no_prepend(self):
        """Test 11: imports='' -> bridge receives java_code unchanged."""
        config = dict(_DEFAULT_CONFIG)
        config["imports"] = ""
        config["java_code"] = 'output_row.put("a", input_row.get("a"));'
        df = pd.DataFrame({"a": [1]})
        bridge = MagicMock()
        bridge.execute_java_row.return_value = pd.DataFrame({"a": [1]})
        comp = _make_component(config=config, java_bridge=bridge)

        comp._process(input_data=df)

        kwargs = bridge.execute_java_row.call_args.kwargs
        sent = kwargs["java_code"]
        assert sent == 'output_row.put("a", input_row.get("a"));'


# ----------------------------------------------------------------
# TestErrorPropagation -- revision 2 (NO REJECT, Talend parity)
# ----------------------------------------------------------------


@pytest.mark.unit
class TestErrorPropagation:
    """Bridge errors propagate as ComponentExecutionError; NO reject_df is built.

    Talend parity (revision 2): tJavaRow has no REJECT connector and no
    try/catch around the row body. Errors propagate up the call stack.
    Matches legacy java_row_component.py:96-98 re-raise behavior.
    """

    def test_bridge_exception_propagates(self):
        """Test 12: bridge raises -> ComponentExecutionError carrying original cause; NO reject_df construction."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        bridge = MagicMock()
        original = RuntimeError("Error processing row 2: NPE")
        bridge.execute_java_row.side_effect = original
        comp = _make_component(java_bridge=bridge)

        with pytest.raises(ComponentExecutionError) as ei:
            comp._process(input_data=df)

        # Component id prefix + original message preserved.
        assert "[tJavaRow_1]" in str(ei.value)
        assert "Error processing row 2: NPE" in str(ei.value)
        # Original exception preserved as cause AND as the .cause attribute.
        assert ei.value.__cause__ is original
        assert ei.value.cause is original
        assert isinstance(ei.value.__cause__, RuntimeError)

    def test_no_reject_key_on_success(self):
        """Test 13: success -> {'main': modified_df, 'reject': None}. reject is never produced."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        modified = pd.DataFrame({"a": [1, 2, 3], "doubled": [2, 4, 6]})
        bridge = MagicMock()
        bridge.execute_java_row.return_value = modified
        comp = _make_component(java_bridge=bridge)

        result = comp._process(input_data=df)

        assert result["main"] is modified
        # On success too, reject is explicitly None (never produced by this component).
        assert result["reject"] is None
        assert set(result.keys()) == {"main", "reject"}


# ----------------------------------------------------------------
# TestStats -- AP-3 (no manual _update_stats)
# ----------------------------------------------------------------


@pytest.mark.unit
class TestStats:
    """BaseComponent counts NB_LINE from result['main']; component never calls _update_stats (AP-3)."""

    def test_no_manual_update_stats(self):
        """Test 14: _update_stats is NEVER invoked from _process (manual stats path is forbidden)."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        bridge = MagicMock()
        bridge.execute_java_row.return_value = df
        comp = _make_component(java_bridge=bridge)

        with patch.object(comp, "_update_stats") as mock_update:
            comp._process(input_data=df)

        mock_update.assert_not_called()


# ----------------------------------------------------------------
# TestContextMixin -- D-09 (mixin-first MRO)
# ----------------------------------------------------------------


@pytest.mark.unit
class TestContextMixin:
    """``_get_context_dict`` is inherited from CodeComponentMixin (AP-4 / D-09)."""

    def test_get_context_dict_inherited_from_mixin(self):
        """Test 15: _get_context_dict resolves via the mixin (not redefined on class)."""
        # JavaRowComponent does NOT redefine _get_context_dict in its own __dict__.
        assert "_get_context_dict" not in JavaRowComponent.__dict__
        # And the resolved method comes from the mixin.
        assert JavaRowComponent._get_context_dict is CodeComponentMixin._get_context_dict
        # And mixin precedes BaseComponent in the MRO (D-09 declares mixin first).
        mro_classes = JavaRowComponent.__mro__
        mixin_idx = mro_classes.index(CodeComponentMixin)
        from src.v1.engine.base_component import BaseComponent as _BaseComponent
        base_idx = mro_classes.index(_BaseComponent)
        assert mixin_idx < base_idx


# ----------------------------------------------------------------
# TestRowExecution -- @pytest.mark.java integration (real bridge)
# ----------------------------------------------------------------


@pytest.mark.java
class TestRowExecution:
    """Real-bridge integration tests for JROW-01 / JROW-03.

    Run with: ``pytest tests/v1/engine/components/transform/test_java_row_component.py -m java``

    These require a built Java bridge JAR
    (``src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar``).
    Plan 05 wires the session-scope ``java_bridge`` fixture; until then this
    class is gated behind the ``-m java`` marker. Per project memory
    ``feedback_test_real_bridge``: mock-only is FORBIDDEN for Java
    components -- these tests prove per-row execution truly works end-to-end.
    """

    def test_per_row_transform_round_trip(self, java_bridge):
        """Test 16 (JROW-03): per-row transform doubles 'a' into 'doubled' across the batch."""
        config = dict(_DEFAULT_CONFIG)
        config["java_code"] = (
            'output_row.put("a", input_row.get("a"));\n'
            'output_row.put("doubled", ((Integer) input_row.get("a")) * 2);'
        )
        config["output_schema"] = {"a": "int", "doubled": "int"}
        comp = _make_component(config=config)
        comp.java_bridge = java_bridge

        df = pd.DataFrame({"a": [1, 2, 3]})
        result = comp.execute(input_data=df)

        out = result.get("main")
        assert out is not None
        assert list(out["doubled"]) == [2, 4, 6]


@pytest.mark.java
class TestImportsRealBridge:
    """Real-bridge integration test for JROW-01 + RESEARCH.md A2 verification.

    Run with: ``pytest tests/v1/engine/components/transform/test_java_row_component.py -m java``
    """

    def test_imports_compiles_real_bridge(self, java_bridge):
        """Test 17 (JROW-01 + A2): imports prepended to java_code compile via the real bridge."""
        config = dict(_DEFAULT_CONFIG)
        config["imports"] = "import java.util.Date;"
        config["java_code"] = (
            'output_row.put("a", input_row.get("a"));\n'
            'globalMap.put("now", new Date().getTime());'
        )
        config["output_schema"] = {"a": "int"}
        comp = _make_component(config=config)
        comp.java_bridge = java_bridge

        df = pd.DataFrame({"a": [1]})
        comp.execute(input_data=df)

        # globalMap.put succeeded -> compile + run worked with the prepended import.
        assert comp.global_map.get("now") is not None


@pytest.mark.java
class TestErrorPropagationRealBridge:
    """Real-bridge integration test verifying error propagation under Talend parity.

    Run with: ``pytest tests/v1/engine/components/transform/test_java_row_component.py -m java``
    """

    def test_real_bridge_error_propagates(self, java_bridge):
        """Test 18: real bridge throwing inside the row body propagates -- no silent failure, no reject_df."""
        config = dict(_DEFAULT_CONFIG)
        config["java_code"] = (
            'if (((Integer) input_row.get("a")) == 2) { '
            'throw new RuntimeException("boom on row 2"); } '
            'output_row.put("a", input_row.get("a"));'
        )
        config["output_schema"] = {"a": "int"}
        comp = _make_component(config=config)
        comp.java_bridge = java_bridge

        df = pd.DataFrame({"a": [1, 2, 3]})
        with pytest.raises(ComponentExecutionError):
            comp.execute(input_data=df)
