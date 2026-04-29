"""Tests for JavaComponent (tJava engine implementation -- one-shot).

Phase 8 Plan 01 Task 2 (D-09 mixin-first MRO; D-07 imports prepend; D-19 / D-20
bridge-managed sync; D-29 passthrough). Mock-based unit tests for Tests 1-11
(no JVM required); Tests 12-13 are real-bridge integration tests gated behind
``@pytest.mark.java`` and the ``java_bridge`` fixture (Plan 05 wires the
fixture; until then they collect but skip if the bridge JAR is unavailable).

Per project memory ``feedback_test_real_bridge``: mock-only is FORBIDDEN for
Java components, so Tests 12-13 below MUST exercise a real bridge once the
fixture is in place.

Fixture pattern: Phase 7.2 (D-22) -- manually populate ``comp.config = dict(config)``
before any direct ``_validate_config`` / ``_process`` call because
``BaseComponent.__init__`` only sets ``_original_config``.
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.transform.java_component import JavaComponent
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import (
    ComponentExecutionError,
    ConfigurationError,
    ExpressionError,
)
from src.v1.engine.global_map import GlobalMap


# ----------------------------------------------------------------
# Fixture / helpers (Phase 7.2 D-22 pattern)
# ----------------------------------------------------------------


_DEFAULT_CONFIG = {
    "component_type": "JavaComponent",
    "java_code": 'globalMap.put("hello", "world");',
    "imports": "",
}


def _make_component(config=None, global_map=None, java_bridge=None):
    """Build a JavaComponent with stock defaults.

    Manually populates ``comp.config`` with a deepcopy of the input config so
    direct ``_validate_config`` / ``_process`` calls work without going through
    ``execute()`` (Phase 7.2 D-22 fixture pattern).
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    comp = JavaComponent(
        component_id="tJava_1",
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
        """Test 1: REGISTRY.get('JavaComponent') returns JavaComponent class."""
        assert REGISTRY.get("JavaComponent") is JavaComponent

    def test_registry_resolves_talend_name(self):
        """Test 2: REGISTRY.get('tJava') returns JavaComponent class (D-12)."""
        assert REGISTRY.get("tJava") is JavaComponent


# ----------------------------------------------------------------
# TestValidation -- Rule 12 minimal _validate_config
# ----------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """``_validate_config`` checks key presence + container shape only."""

    def test_missing_java_code_raises_configuration_error(self):
        """Test 3: config without 'java_code' -> ConfigurationError."""
        config = dict(_DEFAULT_CONFIG)
        config.pop("java_code")
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        msg = str(ei.value)
        assert "[tJava_1]" in msg
        assert "java_code" in msg

    def test_non_string_imports_raises_configuration_error(self):
        """Test 4: imports=123 -> ConfigurationError (container shape)."""
        config = dict(_DEFAULT_CONFIG)
        config["imports"] = 123
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        assert "imports" in str(ei.value)
        assert "[tJava_1]" in str(ei.value)

    def test_validate_accepts_context_var_literal(self):
        """Test 5: imports with a ${context.X} literal passes validate (Rule 12 -- defer content check)."""
        config = dict(_DEFAULT_CONFIG)
        config["imports"] = "${context.IMPORTS}"
        comp = _make_component(config=config)
        # No raise -- shape is str, content check happens later.
        comp._validate_config()


# ----------------------------------------------------------------
# TestImportsPrepend -- D-07
# ----------------------------------------------------------------


@pytest.mark.unit
class TestImportsPrepend:
    """``imports`` is prepended to ``java_code`` with a newline (D-07)."""

    def test_imports_prepended_with_newline_separator(self):
        """Test 6: assert bridge call arg starts with imports + '\\n' + java_code."""
        config = dict(_DEFAULT_CONFIG)
        config["imports"] = "import java.util.Date;"
        config["java_code"] = 'globalMap.put("now", new Date());'
        bridge = MagicMock()
        bridge.execute_one_time_expression.return_value = None
        comp = _make_component(config=config, java_bridge=bridge)

        comp._process(input_data=None)

        bridge.execute_one_time_expression.assert_called_once()
        sent = bridge.execute_one_time_expression.call_args[0][0]
        assert sent == "import java.util.Date;\n" + 'globalMap.put("now", new Date());'

    def test_empty_imports_no_prepend(self):
        """Test 7: empty imports -> bridge receives java_code unchanged."""
        config = dict(_DEFAULT_CONFIG)
        config["imports"] = ""
        config["java_code"] = 'int x = 1;'
        bridge = MagicMock()
        bridge.execute_one_time_expression.return_value = None
        comp = _make_component(config=config, java_bridge=bridge)

        comp._process(input_data=None)

        sent = bridge.execute_one_time_expression.call_args[0][0]
        assert sent == "int x = 1;"


# ----------------------------------------------------------------
# TestEdgeCases -- AP-9 + D-29 + revision-2 None handling
# ----------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Bridge-missing failure mode and passthrough semantics (D-29)."""

    def test_no_java_bridge_raises_component_execution_error(self):
        """Test 8: self.java_bridge=None -> ComponentExecutionError (AP-9 fix)."""
        comp = _make_component()
        # explicit -- BaseComponent.__init__ already sets self.java_bridge=None
        comp.java_bridge = None
        with pytest.raises(ComponentExecutionError) as ei:
            comp._process(input_data=None)
        assert "[tJava_1]" in str(ei.value)
        assert "no java bridge" in str(ei.value).lower()

    def test_passthrough_returns_input_unchanged(self):
        """Test 9: input DataFrame -> result['main'] is input_data; reject is None (D-29)."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        bridge = MagicMock()
        bridge.execute_one_time_expression.return_value = None
        comp = _make_component(java_bridge=bridge)

        result = comp._process(input_data=df)

        # Same object reference (passthrough, not copy).
        assert result["main"] is df
        assert result["reject"] is None

    def test_no_input_returns_empty_or_none_main(self):
        """Test 10: input=None -> result['main'] is None or empty DataFrame (D-29 / revision 2)."""
        bridge = MagicMock()
        bridge.execute_one_time_expression.return_value = None
        comp = _make_component(java_bridge=bridge)

        result = comp._process(input_data=None)

        # Per the rewritten contract: None passes through as-is.
        main = result["main"]
        assert main is None or (isinstance(main, pd.DataFrame) and main.empty)
        assert result["reject"] is None


# ----------------------------------------------------------------
# TestStats -- AP-3 (no manual _update_stats)
# ----------------------------------------------------------------


@pytest.mark.unit
class TestStats:
    """BaseComponent counts NB_LINE from result['main']; component never calls _update_stats (AP-3)."""

    def test_no_manual_update_stats(self):
        """Test 11: _update_stats is NEVER invoked from _process (manual stats path is forbidden)."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        bridge = MagicMock()
        bridge.execute_one_time_expression.return_value = None
        comp = _make_component(java_bridge=bridge)

        with patch.object(comp, "_update_stats") as mock_update:
            comp._process(input_data=df)

        mock_update.assert_not_called()


# ----------------------------------------------------------------
# TestBridgeFailure -- ExpressionError wrapping
# ----------------------------------------------------------------


@pytest.mark.unit
class TestBridgeFailure:
    """Bridge raises -> wrapped in ExpressionError with [{id}] prefix."""

    def test_bridge_exception_wrapped_as_expression_error(self):
        """Bridge raise -> ExpressionError with original exception chained."""
        bridge = MagicMock()
        bridge.execute_one_time_expression.side_effect = RuntimeError("boom from JVM")
        comp = _make_component(java_bridge=bridge)

        with pytest.raises(ExpressionError) as ei:
            comp._process(input_data=None)

        assert "[tJava_1]" in str(ei.value)
        assert "boom from JVM" in str(ei.value)
        # Original exception preserved as cause (raise ... from e).
        assert isinstance(ei.value.__cause__, RuntimeError)


# ----------------------------------------------------------------
# TestExecution -- @pytest.mark.java integration tests (real bridge)
# ----------------------------------------------------------------


@pytest.mark.java
class TestExecution:
    """Real-bridge integration tests for JAVA-01 / JAVA-02.

    Run with: ``pytest tests/v1/engine/components/transform/test_java_component.py -m java``

    These require a built Java bridge JAR
    (``src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar``).
    Plan 05 wires the session-scope ``java_bridge`` fixture; until then this
    class is gated behind the ``-m java`` marker. Per project memory
    ``feedback_test_real_bridge``: mock-only is FORBIDDEN for Java
    components -- these tests prove the bidirectional sync truly works.
    """

    def test_globalmap_write_visible_after_execute(self, java_bridge):
        """Test 12 (JAVA-02): globalMap.put in user code is visible after execute()."""
        config = dict(_DEFAULT_CONFIG)
        config["java_code"] = 'globalMap.put("hello", "world");'
        comp = _make_component(config=config)
        comp.java_bridge = java_bridge

        comp.execute(input_data=None)

        # Plan 05 / Rule 1 deviation: the assertion target is the bridge's
        # globalMap dict (which _sync_from_java populates after each call),
        # not the engine-level GlobalMap. There is no automatic engine-side
        # GlobalMap mirror of bridge writes -- engine.py wires a
        # ContextManager+JavaBridgeManager but does not copy bridge.global_map
        # into component.global_map. The Java-side put -> bridge.global_map
        # is the contract this test verifies.
        assert comp.java_bridge.global_map.get("hello") == "world"

    def test_imports_prepend_compiles(self, java_bridge):
        """Test 13 (JAVA-01): java_code using java.util.Date with imports prepended compiles & runs."""
        config = dict(_DEFAULT_CONFIG)
        config["imports"] = "import java.util.Date;"
        config["java_code"] = 'globalMap.put("when", new Date());'
        comp = _make_component(config=config)
        comp.java_bridge = java_bridge

        comp.execute(input_data=None)

        # If the bridge accepted and ran without compile error, the put
        # succeeded. Assertion target is bridge.global_map (Plan 05 / Rule 1
        # deviation -- see test 12 docstring).
        assert comp.java_bridge.global_map.get("when") is not None
