"""Tests for Warn (tWarn engine implementation)."""
import logging

import pandas as pd
import pytest

from src.v1.engine.components.control.warn import Warn, _resolve_globalmap_vars
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "tWarn",
    "message": "test warning",
    "code": "42",
    "priority": "4",
}


def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    return Warn(
        component_id="tWarn_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=ContextManager(),
    )


def _make_df():
    return pd.DataFrame({"id": [1, 2, 3], "val": ["a", "b", "c"]})


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    def test_v1_name_registered(self):
        assert REGISTRY.get("Warn") is Warn

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tWarn") is Warn

    def test_both_resolve_same_class(self):
        assert REGISTRY.get("Warn") is REGISTRY.get("tWarn")


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    def test_non_string_message_raises(self):
        config = {**_DEFAULT_CONFIG, "message": 123}
        with pytest.raises(ConfigurationError, match="message"):
            _make_component(config=config).execute(None)

    def test_non_integer_code_raises(self):
        config = {**_DEFAULT_CONFIG, "code": "not-a-number"}
        with pytest.raises(ConfigurationError, match="code"):
            _make_component(config=config).execute(None)

    def test_non_integer_priority_raises(self):
        config = {**_DEFAULT_CONFIG, "priority": "high"}
        with pytest.raises(ConfigurationError, match="priority"):
            _make_component(config=config).execute(None)

    def test_priority_zero_raises(self):
        config = {**_DEFAULT_CONFIG, "priority": "0"}
        with pytest.raises(ConfigurationError, match="priority"):
            _make_component(config=config).execute(None)

    def test_priority_seven_raises(self):
        config = {**_DEFAULT_CONFIG, "priority": "7"}
        with pytest.raises(ConfigurationError, match="priority"):
            _make_component(config=config).execute(None)

    def test_priority_one_is_valid(self):
        config = {**_DEFAULT_CONFIG, "priority": "1"}
        result = _make_component(config=config).execute(None)
        assert result["main"] is not None

    def test_priority_six_is_valid(self):
        config = {**_DEFAULT_CONFIG, "priority": "6"}
        result = _make_component(config=config).execute(None)
        assert result["main"] is not None

    def test_valid_config_does_not_raise(self):
        result = _make_component().execute(None)
        assert result["main"] is not None


# ------------------------------------------------------------------
# TestMainFlow
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMainFlow:
    def test_none_input_returns_empty_dataframe(self):
        result = _make_component().execute(None)
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty

    def test_dataframe_passed_through_unchanged(self):
        df = _make_df()
        result = _make_component().execute(df)
        assert len(result["main"]) == 3
        assert list(result["main"]["id"]) == [1, 2, 3]

    def test_columns_preserved(self):
        df = _make_df()
        result = _make_component().execute(df)
        assert list(result["main"].columns) == list(df.columns)

    def test_reject_is_none(self):
        result = _make_component().execute(_make_df())
        assert result["reject"] is None

    def test_logs_message_at_warn_level(self, caplog):
        with caplog.at_level(logging.WARNING):
            _make_component().execute(None)
        assert "test warning" in caplog.text

    def test_logs_message_at_debug_level_for_priority_2(self, caplog):
        config = {**_DEFAULT_CONFIG, "priority": "2"}
        with caplog.at_level(logging.DEBUG):
            _make_component(config=config).execute(None)
        assert "test warning" in caplog.text

    def test_logs_message_at_error_level_for_priority_5(self, caplog):
        config = {**_DEFAULT_CONFIG, "priority": "5"}
        with caplog.at_level(logging.ERROR):
            _make_component(config=config).execute(None)
        assert "test warning" in caplog.text

    def test_integer_code_accepted(self):
        config = {**_DEFAULT_CONFIG, "code": 100}
        result = _make_component(config=config).execute(None)
        assert result["main"] is not None


# ------------------------------------------------------------------
# TestGlobalMapVariables
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    def test_message_stored_in_globalmap(self):
        gm = GlobalMap()
        _make_component(global_map=gm).execute(None)
        assert gm.get("tWarn_1_MESSAGE") == "test warning"

    def test_code_stored_in_globalmap(self):
        gm = GlobalMap()
        _make_component(global_map=gm).execute(None)
        assert gm.get("tWarn_1_CODE") == 42

    def test_priority_stored_in_globalmap(self):
        gm = GlobalMap()
        _make_component(global_map=gm).execute(None)
        assert gm.get("tWarn_1_PRIORITY") == 4

    def test_nb_line_equals_input_rows(self):
        gm = GlobalMap()
        _make_component(global_map=gm).execute(_make_df())
        assert gm.get_component_stat("tWarn_1", "NB_LINE") == 3

    def test_nb_line_zero_for_none_input(self):
        gm = GlobalMap()
        _make_component(global_map=gm).execute(None)
        assert gm.get_component_stat("tWarn_1", "NB_LINE") == 0

    def test_nb_line_reject_is_zero(self):
        gm = GlobalMap()
        _make_component(global_map=gm).execute(_make_df())
        assert gm.get_component_stat("tWarn_1", "NB_LINE_REJECT") == 0

    def test_works_without_global_map(self):
        comp = Warn(
            component_id="tWarn_1",
            config=dict(_DEFAULT_CONFIG),
            global_map=None,
            context_manager=ContextManager(),
        )
        result = comp.execute(None)
        assert result["main"] is not None


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    def test_globalmap_var_in_message_resolved(self):
        """((Integer)globalMap.get("key")) patterns are replaced with GlobalMap values."""
        gm = GlobalMap()
        gm.put("row_count", 99)
        config = {
            **_DEFAULT_CONFIG,
            "message": 'Found ((Integer)globalMap.get("row_count")) rows',
        }
        _make_component(config=config, global_map=gm).execute(None)
        assert gm.get("tWarn_1_MESSAGE") == "Found 99 rows"

    def test_globalmap_var_missing_key_defaults_to_zero(self):
        gm = GlobalMap()
        config = {
            **_DEFAULT_CONFIG,
            "message": 'Count: ((Integer)globalMap.get("missing_key"))',
        }
        comp = _make_component(config=config, global_map=gm)
        comp.execute(None)
        assert gm.get("tWarn_1_MESSAGE") == "Count: 0"

    def test_message_without_globalmap_vars_unchanged(self):
        gm = GlobalMap()
        config = {**_DEFAULT_CONFIG, "message": "plain message"}
        _make_component(config=config, global_map=gm).execute(None)
        assert gm.get("tWarn_1_MESSAGE") == "plain message"

    def test_empty_dataframe_handled(self):
        result = _make_component().execute(pd.DataFrame())
        assert result["main"].empty


# ------------------------------------------------------------------
# TestResolveGlobalmapVars (unit tests for helper)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestResolveGlobalmapVars:
    def test_resolves_integer_cast_pattern(self):
        class MockMap:
            def get(self, key, default=None):
                return 42

        result = _resolve_globalmap_vars('val=((Integer)globalMap.get("x"))', MockMap())
        assert result == "val=42"

    def test_resolves_string_cast_pattern(self):
        class MockMap:
            def get(self, key, default=None):
                return "hello"

        result = _resolve_globalmap_vars('((String)globalMap.get("msg"))', MockMap())
        assert result == "hello"

    def test_non_string_message_returns_string(self):
        result = _resolve_globalmap_vars(None, None)
        assert result == ""

    def test_no_global_map_returns_message_unchanged(self):
        result = _resolve_globalmap_vars("plain", None)
        assert result == "plain"


# ------------------------------------------------------------------
# TestIterateReexecution
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIterateReexecution:
    def test_second_execute_produces_same_result(self):
        comp = _make_component()
        df = _make_df()
        r1 = comp.execute(df)
        comp.reset()
        r2 = comp.execute(df)
        assert len(r1["main"]) == len(r2["main"])

    def test_config_not_mutated_across_executions(self):
        comp = _make_component()
        comp.execute(_make_df())
        snapshot = comp._original_config.copy()
        comp.reset()
        comp.execute(_make_df())
        assert comp._original_config == snapshot
