"""RED phase tests for tContextLoad rewrite.

These tests define the expected behavior of the rewritten ContextLoad component.
They should FAIL against the old implementation and PASS after the rewrite.
"""
import pytest
import pandas as pd

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError, DataValidationError


def _make_component(config=None, context_vars=None, context_types=None):
    """Create a ContextLoad component with optional pre-loaded context."""
    from src.v1.engine.components.context.context_load import ContextLoad
    gm = GlobalMap()
    cm = ContextManager()
    if context_vars:
        for k, v in context_vars.items():
            t = context_types.get(k) if context_types else None
            cm.set(k, v, t)
    comp = ContextLoad("tContextLoad_1", config or {}, gm, cm)
    return comp, gm, cm


@pytest.mark.unit
class TestRegistration:
    """Component must be registered via @REGISTRY.register decorator."""

    def test_registry_contextload(self):
        from src.v1.engine.component_registry import REGISTRY
        from src.v1.engine import components  # noqa: F401 -- trigger registration
        from src.v1.engine.components.context.context_load import ContextLoad
        assert REGISTRY.get("ContextLoad") is ContextLoad

    def test_registry_tcontextload(self):
        from src.v1.engine.component_registry import REGISTRY
        from src.v1.engine import components  # noqa: F401
        from src.v1.engine.components.context.context_load import ContextLoad
        assert REGISTRY.get("tContextLoad") is ContextLoad


@pytest.mark.unit
class TestBasicLoading:
    """DataFrame with key/value loads to context correctly."""

    def test_load_key_value_pairs(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({"key": ["db_host", "db_port"], "value": ["localhost", "5432"]})
        result = comp.execute(df)
        assert cm.get("db_host") == "localhost"
        assert cm.get("db_port") == "5432"
        assert isinstance(result["main"], pd.DataFrame)


@pytest.mark.unit
class TestNaNHandling:
    """NaN values must be stored as None, not string 'nan'."""

    def test_nan_value_stored_as_none(self):
        comp, gm, cm = _make_component()
        df = pd.DataFrame({"key": ["my_key"], "value": [float("nan")]})
        result = comp.execute(df)
        assert cm.get("my_key") is None, f"Expected None, got {cm.get('my_key')!r}"


@pytest.mark.unit
class TestDieOnError:
    """die_on_error=True with unsuppressed ERROR-level message raises."""

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


@pytest.mark.unit
class TestValidateConfig:
    """Invalid policy values must be rejected."""

    def test_invalid_load_new_variable(self):
        config = {"load_new_variable": "INVALID"}
        comp, gm, cm = _make_component(config=config)
        df = pd.DataFrame({"key": ["k"], "value": ["v"]})
        with pytest.raises(ConfigurationError):
            comp.execute(df)
