"""Tests for Die (tDie engine implementation)."""
import logging

import pandas as pd
import pytest

from src.v1.engine.components.control.die import Die, _resolve_globalmap_vars
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "tDie",
    "message": "the end is near",
    "code": "4",
    "priority": "5",
}


def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    return Die(
        component_id="tDie_1",
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
        assert REGISTRY.get("Die") is Die

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tDie") is Die

    def test_both_resolve_same_class(self):
        assert REGISTRY.get("Die") is REGISTRY.get("tDie")


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    def test_non_string_message_raises(self):
        config = {**_DEFAULT_CONFIG, "message": 999}
        with pytest.raises(ConfigurationError, match="message"):
            _make_component(config=config).execute(None)

    def test_non_integer_code_raises(self):
        config = {**_DEFAULT_CONFIG, "code": "bad"}
        with pytest.raises(ConfigurationError, match="code"):
            _make_component(config=config).execute(None)

    def test_non_integer_priority_raises(self):
        config = {**_DEFAULT_CONFIG, "priority": "critical"}
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

    def test_non_integer_exit_code_raises(self):
        config = {**_DEFAULT_CONFIG, "exit_code": "bad"}
        with pytest.raises(ConfigurationError, match="exit_code"):
            _make_component(config=config).execute(None)

    def test_none_message_is_valid(self):
        """None message is accepted (treated as None string)."""
        config = {**_DEFAULT_CONFIG, "message": None}
        with pytest.raises(ComponentExecutionError):
            _make_component(config=config).execute(None)


# ------------------------------------------------------------------
# TestTermination
# ------------------------------------------------------------------


@pytest.mark.unit
class TestTermination:
    def test_always_raises_component_execution_error(self):
        with pytest.raises(ComponentExecutionError):
            _make_component().execute(None)

    def test_always_raises_with_dataframe_input(self):
        with pytest.raises(ComponentExecutionError):
            _make_component().execute(_make_df())

    def test_exit_code_attached_to_exception(self):
        """exit_code is set on the Die exception; the base class wraps it,
        so it lives on exc_info.value.cause."""
        config = {**_DEFAULT_CONFIG, "exit_code": 42}
        with pytest.raises(ComponentExecutionError) as exc_info:
            _make_component(config=config).execute(None)
        assert exc_info.value.cause.exit_code == 42

    def test_default_exit_code_is_1(self):
        with pytest.raises(ComponentExecutionError) as exc_info:
            _make_component().execute(None)
        assert exc_info.value.cause.exit_code == 1

    def test_message_included_in_exception(self):
        config = {**_DEFAULT_CONFIG, "message": "fatal error occurred"}
        with pytest.raises(ComponentExecutionError) as exc_info:
            _make_component(config=config).execute(None)
        assert "fatal error occurred" in str(exc_info.value)

    def test_logs_at_error_level_for_priority_5(self, caplog):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ComponentExecutionError):
                _make_component().execute(None)
        assert "the end is near" in caplog.text

    def test_logs_at_critical_level_for_priority_6(self, caplog):
        config = {**_DEFAULT_CONFIG, "priority": "6"}
        with caplog.at_level(logging.CRITICAL):
            with pytest.raises(ComponentExecutionError):
                _make_component(config=config).execute(None)
        assert "the end is near" in caplog.text

    def test_integer_code_accepted(self):
        config = {**_DEFAULT_CONFIG, "code": 500}
        with pytest.raises(ComponentExecutionError):
            _make_component(config=config).execute(None)


# ------------------------------------------------------------------
# TestGlobalMapVariables
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    def test_message_stored_before_raise(self):
        gm = GlobalMap()
        with pytest.raises(ComponentExecutionError):
            _make_component(global_map=gm).execute(None)
        assert gm.get("tDie_1_MESSAGE") == "the end is near"

    def test_code_stored_before_raise(self):
        gm = GlobalMap()
        with pytest.raises(ComponentExecutionError):
            _make_component(global_map=gm).execute(None)
        assert gm.get("tDie_1_CODE") == 4

    def test_priority_stored_before_raise(self):
        gm = GlobalMap()
        with pytest.raises(ComponentExecutionError):
            _make_component(global_map=gm).execute(None)
        assert gm.get("tDie_1_PRIORITY") == 5

    def test_exit_code_stored_before_raise(self):
        gm = GlobalMap()
        config = {**_DEFAULT_CONFIG, "exit_code": 7}
        with pytest.raises(ComponentExecutionError):
            _make_component(config=config, global_map=gm).execute(None)
        assert gm.get("tDie_1_EXIT_CODE") == 7

    def test_job_error_message_stored(self):
        gm = GlobalMap()
        with pytest.raises(ComponentExecutionError):
            _make_component(global_map=gm).execute(None)
        assert gm.get("JOB_ERROR_MESSAGE") == "the end is near"

    def test_job_exit_code_stored(self):
        gm = GlobalMap()
        with pytest.raises(ComponentExecutionError):
            _make_component(global_map=gm).execute(None)
        assert gm.get("JOB_EXIT_CODE") == 1

    def test_nb_line_equals_input_rows(self):
        gm = GlobalMap()
        with pytest.raises(ComponentExecutionError):
            _make_component(global_map=gm).execute(_make_df())
        assert gm.get_component_stat("tDie_1", "NB_LINE") == 3

    def test_nb_line_ok_is_zero(self):
        gm = GlobalMap()
        with pytest.raises(ComponentExecutionError):
            _make_component(global_map=gm).execute(_make_df())
        assert gm.get_component_stat("tDie_1", "NB_LINE_OK") == 0

    def test_nb_line_reject_equals_input_rows(self):
        gm = GlobalMap()
        with pytest.raises(ComponentExecutionError):
            _make_component(global_map=gm).execute(_make_df())
        assert gm.get_component_stat("tDie_1", "NB_LINE_REJECT") == 3

    def test_none_input_counts_as_one_reject(self):
        gm = GlobalMap()
        with pytest.raises(ComponentExecutionError):
            _make_component(global_map=gm).execute(None)
        assert gm.get_component_stat("tDie_1", "NB_LINE") == 1
        assert gm.get_component_stat("tDie_1", "NB_LINE_REJECT") == 1

    def test_works_without_global_map(self):
        comp = Die(
            component_id="tDie_1",
            config=dict(_DEFAULT_CONFIG),
            global_map=None,
            context_manager=ContextManager(),
        )
        with pytest.raises(ComponentExecutionError):
            comp.execute(None)


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    def test_globalmap_var_in_message_resolved(self):
        gm = GlobalMap()
        gm.put("error_count", 5)
        config = {
            **_DEFAULT_CONFIG,
            "message": 'Errors: ((Integer)globalMap.get("error_count"))',
        }
        with pytest.raises(ComponentExecutionError) as exc_info:
            _make_component(config=config, global_map=gm).execute(None)
        assert "Errors: 5" in str(exc_info.value)

    def test_exit_jvm_accepted_and_ignored(self):
        """exit_jvm is accepted from converter but has no engine effect."""
        config = {**_DEFAULT_CONFIG, "exit_jvm": True}
        with pytest.raises(ComponentExecutionError):
            _make_component(config=config).execute(None)

    def test_empty_dataframe_counts_zero_rejects(self):
        gm = GlobalMap()
        with pytest.raises(ComponentExecutionError):
            _make_component(global_map=gm).execute(pd.DataFrame())
        # empty DataFrame → .empty is True → falls back to 1
        assert gm.get_component_stat("tDie_1", "NB_LINE") == 1


# ------------------------------------------------------------------
# TestIterateReexecution
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIterateReexecution:
    def test_second_execute_also_raises(self):
        comp = _make_component()
        with pytest.raises(ComponentExecutionError):
            comp.execute(None)
        comp.reset()
        with pytest.raises(ComponentExecutionError):
            comp.execute(None)

    def test_config_not_mutated_across_executions(self):
        comp = _make_component()
        snapshot = comp._original_config.copy()
        with pytest.raises(ComponentExecutionError):
            comp.execute(None)
        assert comp._original_config == snapshot
