"""Tests for PythonDataFrameComponent (tPythonDataFrame engine implementation).

Plan 14-06 lift target: 19.6% -> >=95%.

Covers:
  TestRegistration       -- v1 name + Talend alias registered (BUG-PDC-001 fix)
  TestValidation         -- missing/empty python_code -> ConfigurationError
  TestExecution          -- happy path: globalMap, context, vectorized ops
  TestOutputColumns      -- output_columns filter (subset of input cols, no overlap, all)
  TestRoutines           -- Python routines accessible by name + via routines.X
  TestNamespace          -- pd, np, len/str/int/float/bool/sum/min/max accessible
  TestErrorBranches      -- exec failure wraps to ComponentExecutionError
  TestEdgeCases          -- None / empty input, no context_manager, output_df shrink
"""
import logging
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.transform.python_dataframe_component import (
    PythonDataFrameComponent,
)
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import (
    ComponentExecutionError,
    ConfigurationError,
)
from src.v1.engine.global_map import GlobalMap


# ----------------------------------------------------------------
# Fixture / helpers
# ----------------------------------------------------------------


_DEFAULT_CONFIG = {
    "component_type": "PythonDataFrameComponent",
    "python_code": "df['doubled'] = df['x'] * 2",
}


def _make_component(config=None, global_map=None, context_manager=None,
                    python_routine_manager=None):
    """Build a PythonDataFrameComponent with stock defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager if context_manager is not None else ContextManager()
    comp = PythonDataFrameComponent(
        component_id="tPythonDataFrame_1",
        config=config if config is not None else dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    # Mirror what BaseComponent.execute() Step 1 would do, so direct _process
    # calls in unit tests have the same self.config view as a real run.
    comp.config = dict(config if config is not None else _DEFAULT_CONFIG)
    if python_routine_manager is not None:
        comp.python_routine_manager = python_routine_manager
    return comp


def _make_df(n: int = 3) -> pd.DataFrame:
    """Sample DataFrame with mixed dtypes (D-C4)."""
    return pd.DataFrame({
        "x": pd.array(list(range(1, n + 1)), dtype="Int64"),
        "name": pd.array([f"r{i}" for i in range(n)], dtype="string"),
    })


# ----------------------------------------------------------------
# TestRegistration -- BUG-PDC-001
# ----------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component registers under V1 name + Talend alias (Phase 14-06 BUG-PDC-001)."""

    def test_registered_as_v1_name(self):
        assert REGISTRY.get("PythonDataFrameComponent") is PythonDataFrameComponent

    def test_registered_as_talend_alias(self):
        assert REGISTRY.get("tPythonDataFrame") is PythonDataFrameComponent


# ----------------------------------------------------------------
# TestValidation
# ----------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """Missing/empty python_code -> ConfigurationError (Rule 12 minimal validation)."""

    def test_missing_python_code_raises_config_error(self):
        config = dict(_DEFAULT_CONFIG)
        config.pop("python_code")
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError) as ei:
            comp._process(input_data=_make_df())
        msg = str(ei.value)
        assert "[tPythonDataFrame_1]" in msg
        assert "python_code" in msg

    def test_empty_python_code_raises_config_error(self):
        config = dict(_DEFAULT_CONFIG)
        config["python_code"] = ""
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="python_code"):
            comp._process(input_data=_make_df())

    def test_validate_config_directly_raises_on_missing_key(self):
        """Direct _validate_config call raises ConfigurationError (validate-time gate)."""
        config = dict(_DEFAULT_CONFIG)
        config.pop("python_code")
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="python_code"):
            comp._validate_config()

    def test_validate_config_passes_with_python_code(self):
        """_validate_config returns None when python_code is non-empty."""
        comp = _make_component()
        # Direct call -- should not raise
        assert comp._validate_config() is None


# ----------------------------------------------------------------
# TestExecution -- happy path
# ----------------------------------------------------------------


@pytest.mark.unit
class TestExecution:
    """Vectorized DataFrame transformations succeed."""

    def test_vectorized_arithmetic(self):
        comp = _make_component({
            "python_code": "df['doubled'] = df['x'] * 2",
        })
        result = comp._process(input_data=_make_df(3))
        assert "doubled" in result["main"].columns
        assert result["main"]["doubled"].tolist() == [2, 4, 6]

    def test_vectorized_string_ops(self):
        comp = _make_component({
            "python_code": "df['upper'] = df['name'].str.upper()",
        })
        result = comp._process(input_data=_make_df(2))
        assert result["main"]["upper"].tolist() == ["R0", "R1"]

    def test_globalmap_accessible(self):
        gm = GlobalMap()
        comp = _make_component(
            {"python_code": "globalMap.put('rows', len(df))"},
            global_map=gm,
        )
        comp._process(input_data=_make_df(4))
        assert gm.get("rows") == 4

    def test_context_dict_readable(self):
        cm = ContextManager()
        cm.set("PREFIX", "user_")
        comp = _make_component(
            {"python_code": "df['prefixed'] = context['PREFIX'] + df['name'].astype(str)"},
            context_manager=cm,
        )
        result = comp._process(input_data=_make_df(2))
        assert result["main"]["prefixed"].tolist() == ["user_r0", "user_r1"]

    def test_pandas_module_accessible(self):
        comp = _make_component({
            "python_code": (
                "df['cat'] = pd.cut(df['x'], bins=[0,2,10], labels=['low','high'])"
            ),
        })
        result = comp._process(input_data=_make_df(3))
        # x = 1,2,3 -> 1,2 in [0,2] -> 'low'; 3 in (2,10] -> 'high'
        assert "cat" in result["main"].columns

    def test_numpy_module_accessible(self):
        comp = _make_component({
            "python_code": "df['sqrt_x'] = np.sqrt(df['x'].astype(float))",
        })
        result = comp._process(input_data=_make_df(3))
        # sqrt(1)=1, sqrt(2)=~1.414, sqrt(3)=~1.732
        sqrt_vals = result["main"]["sqrt_x"].tolist()
        assert abs(sqrt_vals[0] - 1.0) < 1e-9
        assert abs(sqrt_vals[2] - np.sqrt(3)) < 1e-9


# ----------------------------------------------------------------
# TestOutputColumns -- column filter post-exec
# ----------------------------------------------------------------


@pytest.mark.unit
class TestOutputColumns:
    """output_columns filters the post-exec DataFrame to a column subset."""

    def test_subset_filter_keeps_only_listed(self):
        comp = _make_component({
            "python_code": "df['doubled'] = df['x'] * 2",
            "output_columns": ["x", "doubled"],
        })
        result = comp._process(input_data=_make_df(2))
        assert list(result["main"].columns) == ["x", "doubled"]
        assert "name" not in result["main"].columns

    def test_subset_filter_partial_match_keeps_available_only(self):
        """If output_columns lists names that don't exist, only existing names kept."""
        comp = _make_component({
            "python_code": "df['doubled'] = df['x'] * 2",
            "output_columns": ["x", "MISSING_COL", "doubled"],
        })
        result = comp._process(input_data=_make_df(2))
        # Only x and doubled exist
        assert list(result["main"].columns) == ["x", "doubled"]

    def test_no_match_logs_warning_and_keeps_full_df(self, caplog):
        """If NO listed columns exist, log warning and keep full df."""
        comp = _make_component({
            "python_code": "df['doubled'] = df['x'] * 2",
            "output_columns": ["UNKNOWN1", "UNKNOWN2"],
        })
        with caplog.at_level(logging.WARNING):
            result = comp._process(input_data=_make_df(2))
        # Output not filtered (full df with x, name, doubled)
        assert "doubled" in result["main"].columns
        # Warning emitted
        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("output_columns" in w for w in warnings)

    def test_no_output_columns_keeps_all(self):
        """No output_columns -> full DataFrame in output."""
        comp = _make_component({
            "python_code": "df['doubled'] = df['x'] * 2",
        })
        result = comp._process(input_data=_make_df(2))
        # All original cols + new col
        assert set(result["main"].columns) == {"x", "name", "doubled"}


# ----------------------------------------------------------------
# TestRoutines -- python_routine_manager exposed under routines + by name
# ----------------------------------------------------------------


@pytest.mark.unit
class TestRoutines:
    """Routines from python_routine_manager available in user code."""

    def test_routines_dict_accessible(self):
        """routines['MyRoutine'] reachable in user code."""
        prm = MagicMock()
        # Routine manager returns a dict {name: object}
        class _Helper:
            @staticmethod
            def shout(s):
                return s.upper() + "!"
        prm.get_all_routines.return_value = {"Helper": _Helper}
        comp = _make_component(
            {"python_code": "df['shouted'] = df['name'].apply(routines['Helper'].shout)"},
            python_routine_manager=prm,
        )
        result = comp._process(input_data=_make_df(2))
        assert result["main"]["shouted"].tolist() == ["R0!", "R1!"]

    def test_routine_accessible_by_bare_name(self):
        """Routines also injected into namespace by their name (df['x'].apply(MyRoutine.method))."""
        prm = MagicMock()

        class _Helper:
            @staticmethod
            def add_one(x):
                return int(x) + 1

        prm.get_all_routines.return_value = {"Helper": _Helper}
        comp = _make_component(
            {"python_code": "df['plus1'] = df['x'].apply(Helper.add_one)"},
            python_routine_manager=prm,
        )
        result = comp._process(input_data=_make_df(3))
        assert result["main"]["plus1"].tolist() == [2, 3, 4]

    def test_no_routine_manager_means_empty_routines(self):
        """No python_routine_manager attribute -> routines = {} (no crash)."""
        comp = _make_component({
            "python_code": "globalMap.put('routine_count', len(routines))",
        })
        # python_routine_manager is None (BaseComponent default)
        comp._process(input_data=_make_df(1))
        assert comp.global_map.get("routine_count") == 0


# ----------------------------------------------------------------
# TestBuiltinNamespace -- pd / np / common builtins exposed
# ----------------------------------------------------------------


@pytest.mark.unit
class TestBuiltinNamespace:
    """Whitelisted builtins (len, str, int, float, bool, sum, min, max) accessible."""

    @pytest.mark.parametrize(
        "code,expected_key,expected_val",
        [
            ("globalMap.put('n', len(df))", "n", 3),
            ("globalMap.put('s', sum(df['x']))", "s", 6),
            ("globalMap.put('mn', min(df['x']))", "mn", 1),
            ("globalMap.put('mx', max(df['x']))", "mx", 3),
            ("globalMap.put('si', str(int(df['x'].iloc[0])))", "si", "1"),
            ("globalMap.put('f', float(df['x'].iloc[0]))", "f", 1.0),
            ("globalMap.put('b', bool(df['x'].iloc[0]))", "b", True),
        ],
    )
    def test_builtin_callable(self, code, expected_key, expected_val):
        comp = _make_component({"python_code": code})
        comp._process(input_data=_make_df(3))
        assert comp.global_map.get(expected_key) == expected_val


# ----------------------------------------------------------------
# TestErrorBranches -- exec failures wrap to ComponentExecutionError
# ----------------------------------------------------------------


@pytest.mark.unit
class TestErrorBranches:
    """Bad python_code wraps via ComponentExecutionError(component_id, msg, cause)."""

    def test_syntax_error_wrapped(self):
        comp = _make_component({"python_code": "df['bad'] ="})
        with pytest.raises(ComponentExecutionError) as ei:
            comp._process(input_data=_make_df())
        assert ei.value.component_id == "tPythonDataFrame_1"
        # Original cause preserved
        assert isinstance(ei.value.cause, SyntaxError)

    def test_name_error_wrapped(self):
        """Reference to undefined name wraps to ComponentExecutionError."""
        comp = _make_component({
            "python_code": "df['bad'] = undefined_function(df['x'])",
        })
        with pytest.raises(ComponentExecutionError) as ei:
            comp._process(input_data=_make_df())
        assert ei.value.component_id == "tPythonDataFrame_1"
        assert isinstance(ei.value.cause, NameError)

    def test_division_by_zero_wrapped(self):
        comp = _make_component({"python_code": "x = 1 / 0"})
        with pytest.raises(ComponentExecutionError) as ei:
            comp._process(input_data=_make_df())
        assert isinstance(ei.value.cause, ZeroDivisionError)

    def test_keyerror_wrapped(self):
        """Accessing a missing column wraps to ComponentExecutionError."""
        comp = _make_component({"python_code": "y = df['MISSING_COL']"})
        with pytest.raises(ComponentExecutionError) as ei:
            comp._process(input_data=_make_df())
        assert ei.value.component_id == "tPythonDataFrame_1"

    def test_configuration_error_passes_through(self):
        """ConfigurationError raised inside user code is NOT re-wrapped."""
        # A user can plausibly raise ConfigurationError; our except block
        # explicitly re-raises ETLError subclasses untouched.
        comp = _make_component({
            "python_code": (
                "from src.v1.engine.exceptions import ConfigurationError; "
                "raise ConfigurationError('user explicit')"
            ),
        })
        with pytest.raises(ConfigurationError, match="user explicit"):
            comp._process(input_data=_make_df())


# ----------------------------------------------------------------
# TestEdgeCases
# ----------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """None / empty input + no context_manager + post-exec shrink."""

    def test_none_input_returns_empty(self):
        comp = _make_component()
        result = comp._process(input_data=None)
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty

    def test_empty_dataframe_returns_empty(self):
        comp = _make_component()
        result = comp._process(input_data=pd.DataFrame())
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty

    def test_input_unchanged_after_process(self):
        """Component must copy input -- mutating df in user code does NOT mutate caller's df."""
        df = _make_df(3)
        original_cols = list(df.columns)
        comp = _make_component({"python_code": "df['extra'] = 99"})
        comp._process(input_data=df)
        # Caller's df unchanged
        assert list(df.columns) == original_cols

    def test_no_context_manager_means_empty_context(self):
        """context_manager=None -> context dict is empty, code can still reference it."""
        comp = _make_component({
            "python_code": "globalMap.put('ctx_keys', list(context.keys()))",
        })
        comp.context_manager = None
        comp._process(input_data=_make_df(1))
        assert comp.global_map.get("ctx_keys") == []

    def test_context_with_flat_string_value(self):
        """ContextManager.get_all() may return flat str values directly (non-dict)."""
        cm = MagicMock()
        cm.get_all.return_value = {"FLAT_VAR": "hello"}
        comp = _make_component(
            {"python_code": "globalMap.put('v', context.get('FLAT_VAR'))"},
            context_manager=cm,
        )
        comp._process(input_data=_make_df(1))
        assert comp.global_map.get("v") == "hello"

    def test_context_with_nested_var_info_lacking_value(self):
        """Nested context structure where var_info is dict WITHOUT 'value' key."""
        cm = MagicMock()
        cm.get_all.return_value = {
            "Default": {
                "FOO": {"type": "str"},  # dict without 'value' key
            }
        }
        comp = _make_component(
            {"python_code": "globalMap.put('foo', context.get('FOO'))"},
            context_manager=cm,
        )
        comp._process(input_data=_make_df(1))
        # var_info passed through verbatim (since no 'value' key, full dict stored)
        assert comp.global_map.get("foo") == {"type": "str"}

    def test_context_with_nested_var_info_value_key(self):
        """Nested context structure with 'value' key -> extract the value."""
        cm = MagicMock()
        cm.get_all.return_value = {
            "Default": {
                "HOME": {"value": "US", "type": "str"},
            }
        }
        comp = _make_component(
            {"python_code": "globalMap.put('home', context.get('HOME'))"},
            context_manager=cm,
        )
        comp._process(input_data=_make_df(1))
        # 'value' extracted from nested var_info
        assert comp.global_map.get("home") == "US"

    def test_post_exec_row_shrink(self):
        """User can replace df with a subset; output reflects shrink."""
        comp = _make_component({
            "python_code": "df = df[df['x'] > 1]",
        })
        result = comp._process(input_data=_make_df(3))
        # x=1,2,3 -> kept x=2,3
        assert len(result["main"]) == 2

    def test_stats_updated_via_execute(self):
        """End-to-end execute() pushes stats to globalMap."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_make_df(3))
        # NB_LINE_OK = output rows; NB_LINE_REJECT = 0
        assert gm.get_nb_line_ok("tPythonDataFrame_1") == 3
        assert gm.get_nb_line_reject("tPythonDataFrame_1") == 0

    def test_stats_set_via_process_directly(self):
        """Direct _process() updates self.stats but does NOT push to globalMap (no _update_global_map)."""
        comp = _make_component()
        comp._process(input_data=_make_df(3))
        assert comp.stats["NB_LINE_OK"] == 3
        assert comp.stats["NB_LINE_REJECT"] == 0
        assert comp.stats["NB_LINE"] == 3
