"""Engine unit tests for SetGlobalVar (tSetGlobalVar)."""
import pandas as pd
import pytest

from src.v1.engine.components.file.set_global_var import SetGlobalVar
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_component(config, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    comp = SetGlobalVar(
        component_id="tSetGlobalVar_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    return comp


def _base_config(*rows):
    """Build a minimal config with the given variable rows."""
    return {"variables": list(rows)}


# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    def test_registered_under_v1_name(self):
        from src.v1.engine.component_registry import REGISTRY
        assert REGISTRY.get("SetGlobalVar") is SetGlobalVar

    def test_registered_under_talend_alias(self):
        from src.v1.engine.component_registry import REGISTRY
        assert REGISTRY.get("tSetGlobalVar") is SetGlobalVar


# ---------------------------------------------------------------------------
# 2. _validate_config
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_missing_variables_key_raises(self):
        comp = _make_component({})
        with pytest.raises(ConfigurationError, match="variables"):
            comp._validate_config()

    def test_variables_not_list_raises(self):
        comp = _make_component({"variables": "bad"})
        with pytest.raises(ConfigurationError, match="list"):
            comp._validate_config()

    def test_empty_list_is_valid(self):
        """Empty variable table is legal -- no variables to set."""
        comp = _make_component({"variables": []})
        comp._validate_config()  # must not raise

    def test_valid_list_passes(self):
        comp = _make_component(_base_config({"key": "x", "value": "1"}))
        comp._validate_config()  # must not raise

    def test_uppercase_variables_key_also_valid(self):
        """Legacy uppercase VARIABLES key accepted in validate."""
        comp = _make_component({"VARIABLES": [{"name": "x", "value": "1"}]})
        comp._validate_config()  # must not raise


# ---------------------------------------------------------------------------
# 3. Setting globalMap variables
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestProcessSetsVariables:
    def test_single_variable_set(self):
        gm = GlobalMap()
        comp = _make_component(_base_config({"key": "batch_id", "value": "B001"}), global_map=gm)
        comp.execute()
        assert gm.get("batch_id") == "B001"

    def test_multiple_variables_set(self):
        gm = GlobalMap()
        comp = _make_component(
            _base_config(
                {"key": "a", "value": "1"},
                {"key": "b", "value": "2"},
                {"key": "c", "value": "3"},
            ),
            global_map=gm,
        )
        comp.execute()
        assert gm.get("a") == "1"
        assert gm.get("b") == "2"
        assert gm.get("c") == "3"

    def test_variable_value_can_be_none(self):
        gm = GlobalMap()
        comp = _make_component(_base_config({"key": "nullvar", "value": None}), global_map=gm)
        comp.execute()
        assert gm.get("nullvar") is None

    def test_empty_variable_list_sets_nothing(self):
        gm = GlobalMap()
        before = dict(gm._map)
        comp = _make_component({"variables": []}, global_map=gm)
        comp.execute()
        # Only stats keys should have been added by base class
        new_keys = set(gm._map) - set(before)
        assert all("tSetGlobalVar_1" in k for k in new_keys)


# ---------------------------------------------------------------------------
# 4. Legacy key shapes (backward compatibility)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLegacyKeyFallback:
    def test_uppercase_VARIABLES_key_works(self):
        """Engine should fall back to VARIABLES (uppercase) when variables absent."""
        gm = GlobalMap()
        comp = _make_component({"VARIABLES": [{"name": "x", "value": "42"}]}, global_map=gm)
        comp.execute()
        assert gm.get("x") == "42"

    def test_name_field_fallback_for_var_name(self):
        """Row using 'name' instead of 'key' must still be resolved."""
        gm = GlobalMap()
        comp = _make_component(_base_config({"name": "legacy_key", "value": "hello"}), global_map=gm)
        comp.execute()
        assert gm.get("legacy_key") == "hello"

    def test_VALUE_uppercase_field_fallback(self):
        """Row using 'VALUE' (uppercase) field for the value."""
        gm = GlobalMap()
        comp = _make_component(_base_config({"key": "k", "VALUE": "v"}), global_map=gm)
        comp.execute()
        assert gm.get("k") == "v"


# ---------------------------------------------------------------------------
# 5. Pass-through behaviour
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPassThrough:
    def test_dataframe_input_passed_through_unchanged(self):
        df = pd.DataFrame({"col": [1, 2, 3]})
        comp = _make_component(_base_config({"key": "x", "value": "1"}))
        result = comp.execute(df)
        pd.testing.assert_frame_equal(result["main"], df)

    def test_none_input_returns_none_main(self):
        comp = _make_component(_base_config({"key": "x", "value": "1"}))
        result = comp.execute(None)
        assert result["main"] is None

    def test_input_dataframe_not_mutated(self):
        df = pd.DataFrame({"a": [10, 20]})
        original = df.copy()
        comp = _make_component(_base_config({"key": "x", "value": "val"}))
        comp.execute(df)
        pd.testing.assert_frame_equal(df, original)


# ---------------------------------------------------------------------------
# 6. Statistics
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStatistics:
    def test_nb_line_always_zero(self):
        comp = _make_component(_base_config({"key": "x", "value": "1"}))
        result = comp.execute()
        assert result["stats"]["NB_LINE"] == 0

    def test_nb_line_ok_always_zero(self):
        comp = _make_component(_base_config({"key": "x", "value": "1"}))
        result = comp.execute()
        assert result["stats"]["NB_LINE_OK"] == 0

    def test_nb_line_reject_always_zero(self):
        comp = _make_component(_base_config({"key": "x", "value": "1"}))
        result = comp.execute()
        assert result["stats"]["NB_LINE_REJECT"] == 0

    def test_stats_unchanged_with_dataframe_input(self):
        """Stats are 0 even when a DataFrame is passed in (not a row processor)."""
        df = pd.DataFrame({"x": range(100)})
        comp = _make_component(_base_config({"key": "k", "value": "v"}))
        result = comp.execute(df)
        assert result["stats"]["NB_LINE"] == 0


# ---------------------------------------------------------------------------
# 7. die_on_error
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDieOnError:
    def test_non_dict_row_die_on_error_true_raises(self):
        comp = _make_component({"variables": ["not_a_dict"], "die_on_error": True})
        with pytest.raises(ConfigurationError):
            comp.execute()

    def test_non_dict_row_die_on_error_false_skips(self):
        """Bad row is skipped; subsequent valid rows are still set."""
        gm = GlobalMap()
        comp = _make_component(
            {"variables": ["bad_row", {"key": "good", "value": "ok"}], "die_on_error": False},
            global_map=gm,
        )
        comp.execute()
        assert gm.get("good") == "ok"

    def test_missing_name_die_on_error_true_raises(self):
        comp = _make_component({"variables": [{"value": "orphan"}], "die_on_error": True})
        with pytest.raises(ConfigurationError, match="name"):
            comp.execute()

    def test_missing_name_die_on_error_false_skips(self):
        gm = GlobalMap()
        comp = _make_component(
            {"variables": [{"value": "orphan"}, {"key": "real", "value": "set"}],
             "die_on_error": False},
            global_map=gm,
        )
        comp.execute()
        assert gm.get("real") == "set"


# ---------------------------------------------------------------------------
# 8. No globalMap (component must not crash)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNoGlobalMap:
    def test_runs_without_global_map(self):
        comp = SetGlobalVar(
            component_id="tSetGlobalVar_nogm",
            config=_base_config({"key": "x", "value": "1"}),
            global_map=None,
            context_manager=ContextManager(),
        )
        comp.config = _base_config({"key": "x", "value": "1"})
        result = comp.execute()
        assert result["main"] is None
