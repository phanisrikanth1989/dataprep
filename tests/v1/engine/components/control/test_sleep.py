"""Tests for Sleep (tSleep engine implementation)."""
import math
import time
from unittest.mock import patch

import pandas as pd
import pytest

from src.v1.engine.components.control.sleep import Sleep
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "tSleep",
    "pause_duration": 0,
}


def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    return Sleep(
        component_id="tSleep_1",
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
        assert REGISTRY.get("Sleep") is Sleep

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tSleep") is Sleep

    def test_legacy_alias_registered(self):
        """SleepComponent alias kept for backward compat with existing JSONs."""
        assert REGISTRY.get("SleepComponent") is Sleep


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    def test_invalid_pause_duration_type_raises(self):
        config = {**_DEFAULT_CONFIG, "pause_duration": [1, 2]}
        with pytest.raises(ConfigurationError, match="pause_duration"):
            _make_component(config=config).execute(None)

    def test_dict_pause_duration_raises(self):
        config = {**_DEFAULT_CONFIG, "pause_duration": {"seconds": 1}}
        with pytest.raises(ConfigurationError, match="pause_duration"):
            _make_component(config=config).execute(None)

    def test_int_pause_duration_is_valid(self):
        comp = _make_component(config={**_DEFAULT_CONFIG, "pause_duration": 0})
        result = comp.execute(None)
        assert result["main"] is not None

    def test_float_pause_duration_is_valid(self):
        comp = _make_component(config={**_DEFAULT_CONFIG, "pause_duration": 0.0})
        result = comp.execute(None)
        assert result["main"] is not None

    def test_string_numeric_pause_duration_is_valid(self):
        comp = _make_component(config={**_DEFAULT_CONFIG, "pause_duration": "0"})
        result = comp.execute(None)
        assert result["main"] is not None

    def test_missing_pause_duration_uses_default(self):
        """pause_duration is optional; missing key defaults to 0."""
        comp = _make_component(config={"component_type": "tSleep"})
        result = comp.execute(None)
        assert result["main"] is not None


# ------------------------------------------------------------------
# TestMainFlow
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMainFlow:
    def test_none_input_returns_empty_dataframe(self):
        comp = _make_component()
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty

    def test_dataframe_input_passed_through_unchanged(self):
        comp = _make_component()
        df = _make_df()
        result = comp.execute(df)
        assert len(result["main"]) == 3
        assert list(result["main"]["id"]) == [1, 2, 3]

    def test_columns_preserved(self):
        comp = _make_component()
        df = _make_df()
        result = comp.execute(df)
        assert list(result["main"].columns) == list(df.columns)

    def test_reject_is_none(self):
        comp = _make_component()
        result = comp.execute(_make_df())
        assert result["reject"] is None

    @patch("src.v1.engine.components.control.sleep.time.sleep")
    def test_positive_duration_calls_sleep(self, mock_sleep):
        config = {**_DEFAULT_CONFIG, "pause_duration": 2}
        comp = _make_component(config=config)
        comp.execute(None)
        mock_sleep.assert_called_once_with(2.0)

    @patch("src.v1.engine.components.control.sleep.time.sleep")
    def test_zero_duration_skips_sleep(self, mock_sleep):
        comp = _make_component()
        comp.execute(None)
        mock_sleep.assert_not_called()

    @patch("src.v1.engine.components.control.sleep.time.sleep")
    def test_negative_duration_skips_sleep(self, mock_sleep):
        config = {**_DEFAULT_CONFIG, "pause_duration": -1}
        comp = _make_component(config=config)
        comp.execute(None)
        mock_sleep.assert_not_called()

    @patch("src.v1.engine.components.control.sleep.time.sleep")
    def test_string_numeric_duration_sleeps(self, mock_sleep):
        config = {**_DEFAULT_CONFIG, "pause_duration": "3"}
        comp = _make_component(config=config)
        comp.execute(None)
        mock_sleep.assert_called_once_with(3.0)


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    @patch("src.v1.engine.components.control.sleep.time.sleep")
    def test_inf_duration_skips_sleep(self, mock_sleep):
        config = {**_DEFAULT_CONFIG, "pause_duration": float("inf")}
        comp = _make_component(config=config)
        comp.execute(None)
        mock_sleep.assert_not_called()

    @patch("src.v1.engine.components.control.sleep.time.sleep")
    def test_nan_duration_skips_sleep(self, mock_sleep):
        config = {**_DEFAULT_CONFIG, "pause_duration": float("nan")}
        comp = _make_component(config=config)
        comp.execute(None)
        mock_sleep.assert_not_called()

    @patch("src.v1.engine.components.control.sleep.time.sleep")
    def test_non_numeric_string_skips_sleep(self, mock_sleep):
        """Unparseable string logs a warning and skips sleep (doesn't crash)."""
        config = {**_DEFAULT_CONFIG, "pause_duration": "not-a-number"}
        comp = _make_component(config=config)
        comp.execute(None)
        mock_sleep.assert_not_called()

    def test_empty_dataframe_passed_through(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty

    @patch("src.v1.engine.components.control.sleep.time.sleep")
    def test_float_duration(self, mock_sleep):
        config = {**_DEFAULT_CONFIG, "pause_duration": 1.5}
        comp = _make_component(config=config)
        comp.execute(None)
        mock_sleep.assert_called_once_with(1.5)


# ------------------------------------------------------------------
# TestGlobalMapVariables
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    def test_nb_line_equals_input_row_count(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        df = _make_df()
        comp.execute(df)
        assert gm.get_component_stat("tSleep_1", "NB_LINE") == 3

    def test_nb_line_ok_equals_row_count(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_make_df())
        assert gm.get_component_stat("tSleep_1", "NB_LINE_OK") == 3

    def test_nb_line_reject_is_zero(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_make_df())
        assert gm.get_component_stat("tSleep_1", "NB_LINE_REJECT") == 0

    def test_nb_line_zero_when_none_input(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(None)
        assert gm.get_component_stat("tSleep_1", "NB_LINE") == 0

    def test_works_without_global_map(self):
        comp = Sleep(
            component_id="tSleep_1",
            config=dict(_DEFAULT_CONFIG),
            global_map=None,
            context_manager=ContextManager(),
        )
        result = comp.execute(None)
        assert result["main"] is not None


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
