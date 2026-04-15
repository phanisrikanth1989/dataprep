"""Exhaustive unit tests for ContextLoad (tContextLoad) engine component.

Tests cover: basic loading, type preservation, NaN handling,
LOAD_NEW_VARIABLE policy, NOT_LOAD_OLD_VARIABLE policy, DISABLE_*
flags, die_on_error interaction, globalMap variables, config
validation, edge cases, and registry registration.
"""
import logging

import pytest
import pandas as pd

from src.v1.engine.components.context.context_load import ContextLoad
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.exceptions import (
    ComponentExecutionError,
    ConfigurationError,
    DataValidationError,
)
from src.v1.engine.component_registry import REGISTRY


# ------------------------------------------------------------------
# Test Helpers
# ------------------------------------------------------------------


def _make_component(config=None, context_vars=None, context_types=None):
    """Create a ContextLoad component with optional pre-loaded context.

    Args:
        config: Component config dict. Defaults to empty.
        context_vars: Dict of pre-loaded context variables.
        context_types: Dict of pre-loaded context type strings.

    Returns:
        Tuple of (component, global_map, context_manager).
    """
    gm = GlobalMap()
    cm = ContextManager()
    if context_vars:
        for k, v in context_vars.items():
            t = context_types.get(k) if context_types else None
            cm.set(k, v, t)
    comp = ContextLoad("tContextLoad_1", config or {}, gm, cm)
    return comp, gm, cm


# ------------------------------------------------------------------
# TestBasicLoading
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBasicLoading:
    """DataFrame with key/value loads to context correctly."""

    def test_load_key_value_pairs(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({
            "key": ["db_host", "db_port", "app_name"],
            "value": ["localhost", "5432", "test"],
        })
        result = comp.execute(df)
        assert cm.get("db_host") == "localhost"
        assert cm.get("db_port") == "5432"
        assert cm.get("app_name") == "test"

    def test_load_strips_key_whitespace(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({"key": [" spaced_key "], "value": ["val"]})
        comp.execute(df)
        assert cm.get("spaced_key") == "val"
        assert cm.get(" spaced_key ") is None

    def test_empty_key_skipped(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({"key": ["", "valid_key"], "value": ["skip", "keep"]})
        comp.execute(df)
        assert cm.get("valid_key") == "keep"
        assert cm.get("") is None

    def test_returns_empty_dataframe(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({"key": ["k"], "value": ["v"]})
        result = comp.execute(df)
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty


# ------------------------------------------------------------------
# TestTypePreservation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestTypePreservation:
    """Type column, ContextManager fallback, and id_String default."""

    def test_type_column_used_when_present(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({
            "key": ["count"],
            "value": ["42"],
            "type": ["id_Integer"],
        })
        comp.execute(df)
        assert cm.get_type("count") == "id_Integer"
        assert cm.get("count") == 42

    def test_existing_type_preserved_without_type_column(self):
        comp, gm, cm = _make_component(
            context_vars={"count": 10},
            context_types={"count": "id_Integer"},
        )
        df = pd.DataFrame({"key": ["count"], "value": ["42"]})
        comp.execute(df)
        assert cm.get_type("count") == "id_Integer"
        assert cm.get("count") == 42

    def test_type_column_overrides_existing_type(self):
        comp, gm, cm = _make_component(
            context_vars={"count": 10},
            context_types={"count": "id_Integer"},
        )
        df = pd.DataFrame({
            "key": ["count"],
            "value": ["42"],
            "type": ["id_String"],
        })
        comp.execute(df)
        assert cm.get_type("count") == "id_String"
        assert cm.get("count") == "42"

    def test_default_to_id_string(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({"key": ["new_var"], "value": ["hello"]})
        comp.execute(df)
        assert cm.get_type("new_var") == "id_String"

    def test_nan_in_type_column_falls_back(self):
        comp, gm, cm = _make_component(
            context_vars={"existing": "old"},
            context_types={"existing": "id_Integer"},
        )
        df = pd.DataFrame({
            "key": ["existing", "brand_new"],
            "value": ["99", "abc"],
            "type": [float("nan"), float("nan")],
        })
        comp.execute(df)
        # existing key falls back to existing type
        assert cm.get_type("existing") == "id_Integer"
        # brand_new key falls back to id_String
        assert cm.get_type("brand_new") == "id_String"


# ------------------------------------------------------------------
# TestNaNHandling
# ------------------------------------------------------------------


@pytest.mark.unit
class TestNaNHandling:
    """NaN values in DataFrame columns handled correctly."""

    def test_nan_value_stored_as_none(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({"key": ["my_key"], "value": [float("nan")]})
        comp.execute(df)
        assert cm.get("my_key") is None

    def test_nan_in_key_column_handled(self):
        """NaN in key column is skipped (empty after fillna + strip)."""
        comp, gm, cm = _make_component()
        df = pd.DataFrame({"key": [float("nan"), "valid"], "value": ["a", "b"]})
        comp.execute(df)
        # valid key is definitely loaded
        assert cm.get("valid") == "b"
        # NaN key is skipped -- not loaded at all

    def test_none_value_stored_as_none(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({"key": ["k"], "value": [None]})
        comp.execute(df)
        assert cm.get("k") is None


# ------------------------------------------------------------------
# TestLoadNewVariable
# ------------------------------------------------------------------


@pytest.mark.unit
class TestLoadNewVariable:
    """LOAD_NEW_VARIABLE policy for keys not in existing context."""

    def test_warning_policy_new_keys(self, caplog):
        config = {
            "load_new_variable": "WARNING",
            "disable_warnings": False,
        }
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["alpha", "beta"], "value": ["a", "b"]})
        with caplog.at_level(logging.WARNING):
            comp.execute(df)
        assert "New context variable 'alpha'" in caplog.text
        assert "New context variable 'beta'" in caplog.text
        # Keys are still loaded unconditionally
        assert cm.get("alpha") == "a"
        assert cm.get("beta") == "b"

    def test_error_policy_new_keys(self, caplog):
        config = {
            "load_new_variable": "ERROR",
            "disable_error": False,
            "die_on_error": False,
        }
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        with caplog.at_level(logging.ERROR):
            comp.execute(df)
        assert "New context variable 'new_key'" in caplog.text
        # Key is still loaded
        assert cm.get("new_key") == "val"

    def test_no_warning_policy_no_messages(self, caplog):
        config = {"load_new_variable": "NO_WARNING"}
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        with caplog.at_level(logging.DEBUG):
            comp.execute(df)
        assert "New context variable" not in caplog.text
        assert cm.get("new_key") == "val"

    def test_existing_keys_no_message(self, caplog):
        config = {
            "load_new_variable": "WARNING",
            "disable_warnings": False,
        }
        comp, gm, cm = _make_component(
            config=config,
            context_vars={"existing_key": "old_val"},
        )
        df = pd.DataFrame({"key": ["existing_key"], "value": ["new_val"]})
        with caplog.at_level(logging.WARNING):
            comp.execute(df)
        assert "New context variable" not in caplog.text

    def test_default_warnings_suppressed(self, caplog):
        """Default config has disable_warnings=True, so WARNING messages are suppressed."""
        config = {"load_new_variable": "WARNING"}  # disable_warnings defaults to True
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        with caplog.at_level(logging.WARNING):
            comp.execute(df)
        # Message should be suppressed by default
        assert "New context variable" not in caplog.text


# ------------------------------------------------------------------
# TestNotLoadOldVariable
# ------------------------------------------------------------------


@pytest.mark.unit
class TestNotLoadOldVariable:
    """NOT_LOAD_OLD_VARIABLE policy for context keys absent from flow."""

    def test_warning_policy_unloaded_keys(self, caplog):
        config = {
            "not_load_old_variable": "WARNING",
            "disable_warnings": False,
        }
        comp, gm, cm = _make_component(
            config=config,
            context_vars={"key_a": "a", "key_b": "b"},
        )
        df = pd.DataFrame({"key": ["key_a"], "value": ["new_a"]})
        with caplog.at_level(logging.WARNING):
            comp.execute(df)
        assert "Context variable 'key_b' not loaded" in caplog.text
        assert "Context variable 'key_a' not loaded" not in caplog.text

    def test_error_policy_unloaded_keys(self, caplog):
        config = {
            "not_load_old_variable": "ERROR",
            "disable_error": False,
            "die_on_error": False,
        }
        comp, gm, cm = _make_component(
            config=config,
            context_vars={"key_a": "a", "key_b": "b"},
        )
        df = pd.DataFrame({"key": ["key_a"], "value": ["new_a"]})
        with caplog.at_level(logging.ERROR):
            comp.execute(df)
        assert "Context variable 'key_b' not loaded" in caplog.text

    def test_no_warning_policy_no_messages(self, caplog):
        config = {"not_load_old_variable": "NO_WARNING"}
        comp, gm, cm = _make_component(
            config=config,
            context_vars={"old_key": "old"},
        )
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        with caplog.at_level(logging.DEBUG):
            comp.execute(df)
        assert "not loaded from incoming flow" not in caplog.text

    def test_all_keys_loaded_no_message(self, caplog):
        config = {
            "not_load_old_variable": "WARNING",
            "disable_warnings": False,
        }
        comp, gm, cm = _make_component(
            config=config,
            context_vars={"key_a": "old"},
        )
        df = pd.DataFrame({"key": ["key_a"], "value": ["new"]})
        with caplog.at_level(logging.WARNING):
            comp.execute(df)
        assert "not loaded from incoming flow" not in caplog.text


# ------------------------------------------------------------------
# TestDisableFlags
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDisableFlags:
    """DISABLE_ERROR/DISABLE_WARNINGS/DISABLE_INFO suppression."""

    def test_disable_warnings_default_true(self, caplog):
        """Default config suppresses WARNING-level messages."""
        config = {"load_new_variable": "WARNING"}
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        with caplog.at_level(logging.WARNING):
            comp.execute(df)
        # disable_warnings defaults True -> message suppressed
        assert "New context variable" not in caplog.text

    def test_disable_info_default_true(self, caplog):
        """Default config suppresses INFO-level messages."""
        config = {"load_new_variable": "INFO"}
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        # disable_info defaults True -> validation message suppressed
        assert "New context variable" not in caplog.text

    def test_disable_error_default_false(self, caplog):
        """Default config does NOT suppress ERROR-level messages."""
        config = {
            "load_new_variable": "ERROR",
            "die_on_error": False,
        }
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        with caplog.at_level(logging.ERROR):
            comp.execute(df)
        # disable_error defaults False -> message NOT suppressed
        assert "New context variable 'new_key'" in caplog.text

    def test_disable_error_suppresses_error(self, caplog):
        """disable_error=True suppresses ERROR messages."""
        config = {
            "load_new_variable": "ERROR",
            "disable_error": True,
            "die_on_error": False,
        }
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        with caplog.at_level(logging.ERROR):
            comp.execute(df)
        assert "New context variable" not in caplog.text

    def test_disable_warnings_false_allows_warnings(self, caplog):
        """disable_warnings=False allows WARNING messages through."""
        config = {
            "load_new_variable": "WARNING",
            "disable_warnings": False,
        }
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        with caplog.at_level(logging.WARNING):
            comp.execute(df)
        assert "New context variable 'new_key'" in caplog.text


# ------------------------------------------------------------------
# TestDieOnError
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDieOnError:
    """die_on_error interaction with ERROR-level messages and DISABLE flags."""

    def test_die_on_error_raises_on_error_message(self):
        config = {
            "die_on_error": True,
            "load_new_variable": "ERROR",
            "disable_error": False,
        }
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        with pytest.raises(ComponentExecutionError):
            comp.execute(df)

    def test_die_on_error_false_no_raise(self):
        config = {
            "die_on_error": False,
            "load_new_variable": "ERROR",
            "disable_error": False,
        }
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        # Should not raise
        result = comp.execute(df)
        assert cm.get("new_key") == "val"

    def test_die_on_error_true_but_error_disabled(self):
        config = {
            "die_on_error": True,
            "load_new_variable": "ERROR",
            "disable_error": True,
        }
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        # Should NOT raise -- error suppressed by disable_error
        result = comp.execute(df)
        assert cm.get("new_key") == "val"

    def test_die_on_error_warning_level_no_raise(self):
        config = {
            "die_on_error": True,
            "load_new_variable": "WARNING",
            "disable_warnings": False,
        }
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        # WARNING level does NOT trigger die_on_error (only ERROR does)
        result = comp.execute(df)
        assert cm.get("new_key") == "val"

    def test_die_on_error_with_not_load_old_error(self):
        config = {
            "die_on_error": True,
            "not_load_old_variable": "ERROR",
            "disable_error": False,
        }
        comp, gm, cm = _make_component(
            config=config,
            context_vars={"old_key": "old_val"},
        )
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        with pytest.raises(ComponentExecutionError):
            comp.execute(df)


# ------------------------------------------------------------------
# TestGlobalMapVariables
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    """GlobalMap variables set correctly after execution."""

    def test_nb_line_set(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({
            "key": ["k1", "k2", "k3"],
            "value": ["v1", "v2", "v3"],
        })
        comp.execute(df)
        assert gm.get("tContextLoad_1_NB_LINE") == 3

    def test_nb_context_loaded_set(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({
            "key": ["k1", "k2", "k3"],
            "value": ["v1", "v2", "v3"],
        })
        comp.execute(df)
        assert gm.get("tContextLoad_1_NB_CONTEXT_LOADED") == 3

    def test_key_not_incontext_set(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({
            "key": ["alpha", "beta"],
            "value": ["a", "b"],
        })
        comp.execute(df)
        assert gm.get("tContextLoad_1_KEY_NOT_INCONTEXT") == "alpha,beta"

    def test_key_not_loaded_set(self):
        comp, gm, cm = _make_component(
            context_vars={"old_key": "old_val"},
        )
        df = pd.DataFrame({"key": ["new_key"], "value": ["val"]})
        comp.execute(df)
        assert gm.get("tContextLoad_1_KEY_NOT_LOADED") == "old_key"


# ------------------------------------------------------------------
# TestValidateConfig
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidateConfig:
    """Invalid policy values must be rejected."""

    def test_invalid_load_new_variable(self):
        config = {"load_new_variable": "INVALID"}
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["k"], "value": ["v"]})
        with pytest.raises(ConfigurationError, match="load_new_variable"):
            comp.execute(df)

    def test_invalid_not_load_old_variable(self):
        config = {"not_load_old_variable": "BOGUS"}
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["k"], "value": ["v"]})
        with pytest.raises(ConfigurationError, match="not_load_old_variable"):
            comp.execute(df)

    def test_valid_policies_accepted(self):
        """All valid values accepted without error."""
        for policy in ("ERROR", "WARNING", "NO_WARNING", "INFO"):
            config = {
                "load_new_variable": policy,
                "not_load_old_variable": policy,
                "die_on_error": False,
                "disable_error": True,
                "disable_warnings": True,
                "disable_info": True,
            }
            comp, gm, cm = _make_component(config=config)
            df = pd.DataFrame({"key": ["k"], "value": ["v"]})
            comp.execute(df)  # Should not raise


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases: empty DataFrame, None input, missing dependencies."""

    def test_none_input(self):
        comp, gm, cm = _make_component()
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty

    def test_empty_dataframe(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({"key": [], "value": []})
        result = comp.execute(df)
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty

    def test_no_context_manager(self):
        """Component works without context_manager (None guard)."""
        gm = GlobalMap()
        comp = ContextLoad("tContextLoad_1", {}, gm, None)
        df = pd.DataFrame({"key": ["k"], "value": ["v"]})
        result = comp.execute(df)
        assert isinstance(result["main"], pd.DataFrame)

    def test_no_global_map(self):
        """Component works without global_map (None guard)."""
        cm = ContextManager()
        comp = ContextLoad("tContextLoad_1", {}, None, cm)
        df = pd.DataFrame({"key": ["k"], "value": ["v"]})
        result = comp.execute(df)
        assert cm.get("k") == "v"

    def test_missing_value_column(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({"key": ["k"]})
        with pytest.raises((DataValidationError, ComponentExecutionError)):
            comp.execute(df)


# ------------------------------------------------------------------
# TestPrintOperations
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPrintOperations:
    """print_operations=True logs each loaded key-value pair."""

    def test_print_operations_logs(self, caplog):
        config = {"print_operations": True}
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["db_host"], "value": ["localhost"]})
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        assert "Context loaded: db_host = localhost" in caplog.text


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component accessible via REGISTRY under both names."""

    def test_registry_contextload(self):
        from src.v1.engine import components  # noqa: F401 -- trigger registration
        assert REGISTRY.get("ContextLoad") is ContextLoad

    def test_registry_tcontextload(self):
        from src.v1.engine import components  # noqa: F401
        assert REGISTRY.get("tContextLoad") is ContextLoad
