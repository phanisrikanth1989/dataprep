"""Unit tests for Foreach engine component (tForeach).

Mirrors the test structure used for FlowToIterate (test_flow_to_iterate.py).
"""
import copy

import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.iterate.foreach import Foreach, ForeachItem
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


def _make_foreach(comp_id="tForeach_1", config=None, global_map=None):
    """Factory helper: creates a Foreach with resolved config state."""
    config = config if config is not None else {}
    gm = global_map if global_map is not None else GlobalMap()
    ctx = ContextManager(initial_context={"Default": {}})
    comp = Foreach(comp_id, config, gm, ctx)
    # Mirror flow_to_iterate test pattern: populate config directly so we can
    # call _validate_config()/prepare_iterations() without going through execute().
    comp.config = copy.deepcopy(comp._original_config)
    return comp


# ===========================================================================
# Registration
# ===========================================================================

@pytest.mark.unit
class TestRegistration:
    def test_registered_as_Foreach(self):
        assert REGISTRY.get("Foreach") is Foreach

    def test_registered_as_tForeach(self):
        assert REGISTRY.get("tForeach") is Foreach


# ===========================================================================
# _validate_config
# ===========================================================================

@pytest.mark.unit
class TestValidateConfig:
    def test_valid_string_values(self):
        comp = _make_foreach(config={"values": ["a", "b", "c"]})
        comp._validate_config()

    def test_empty_values_ok(self):
        comp = _make_foreach(config={"values": []})
        comp._validate_config()

    def test_missing_values_defaults_to_empty(self):
        comp = _make_foreach(config={})
        comp._validate_config()

    def test_values_not_list_raises(self):
        comp = _make_foreach(config={"values": "not_a_list"})
        with pytest.raises(ConfigurationError, match="values"):
            comp._validate_config()

    def test_non_string_value_raises(self):
        comp = _make_foreach(config={"values": ["a", 42, "c"]})
        with pytest.raises(ConfigurationError, match=r"values\[1\]"):
            comp._validate_config()


# ===========================================================================
# prepare_iterations
# ===========================================================================

@pytest.mark.unit
class TestPrepareIterations:
    def test_one_item_per_value(self):
        comp = _make_foreach(config={"values": ["x", "y", "z"]})
        items = list(comp.prepare_iterations())
        assert len(items) == 3
        assert all(isinstance(it, ForeachItem) for it in items)

    def test_items_have_one_based_index(self):
        comp = _make_foreach(config={"values": ["a", "b", "c"]})
        items = list(comp.prepare_iterations())
        assert [it.index for it in items] == [1, 2, 3]
        assert [it.value for it in items] == ["a", "b", "c"]

    def test_total_iterations_set(self):
        comp = _make_foreach(config={"values": ["a", "b", "c", "d"]})
        list(comp.prepare_iterations())
        assert comp.total_iterations == 4

    def test_returns_iterator_not_list(self):
        comp = _make_foreach(config={"values": ["a"]})
        it = comp.prepare_iterations()
        assert not isinstance(it, list)
        assert iter(it) is it

    def test_empty_values_zero_iterations(self):
        comp = _make_foreach(config={"values": []})
        items = list(comp.prepare_iterations())
        assert items == []
        assert comp.total_iterations == 0

    def test_input_data_ignored(self):
        """tForeach is a source component -- input_data is ignored, not validated."""
        import pandas as pd
        comp = _make_foreach(config={"values": ["a", "b"]})
        items = list(comp.prepare_iterations(pd.DataFrame([{"x": 1}])))
        assert [it.value for it in items] == ["a", "b"]


# ===========================================================================
# set_iteration_globalmap
# ===========================================================================

@pytest.mark.unit
class TestSetIterationGlobalMap:
    def test_writes_current_value_key(self):
        gm = GlobalMap()
        comp = _make_foreach(config={"values": ["foo"]}, global_map=gm)
        comp.set_iteration_globalmap(ForeachItem(value="foo", index=1))
        assert gm.get("tForeach_1_CURRENT_VALUE") == "foo"

    def test_last_value_persists(self):
        gm = GlobalMap()
        comp = _make_foreach(config={"values": ["a", "b", "c"]}, global_map=gm)
        for i, v in enumerate(["a", "b", "c"], start=1):
            comp.set_iteration_globalmap(ForeachItem(value=v, index=i))
        assert gm.get("tForeach_1_CURRENT_VALUE") == "c"

    def test_no_globalmap_noop(self):
        comp = _make_foreach(config={"values": ["x"]}, global_map=None)
        comp.global_map = None
        # Must not raise.
        comp.set_iteration_globalmap(ForeachItem(value="x", index=1))


# ===========================================================================
# Logging hook
# ===========================================================================

@pytest.mark.unit
class TestIterKeyInfo:
    def test_key_info_format(self):
        comp = _make_foreach(config={"values": ["abc"]})
        info = comp.get_iter_key_info(ForeachItem(value="abc", index=1), 1)
        assert info == "value='abc'"


# ===========================================================================
# Statistics
# ===========================================================================

@pytest.mark.unit
class TestStatistics:
    def test_finalize_sets_nb_line(self):
        comp = _make_foreach(config={"values": ["a", "b", "c"]})
        list(comp.prepare_iterations())
        comp.finalize()
        assert comp.stats["NB_LINE"] == 3
        assert comp.stats["NB_LINE_OK"] == 3
        assert comp.stats["NB_LINE_REJECT"] == 0

    def test_finalize_empty_values(self):
        comp = _make_foreach(config={"values": []})
        list(comp.prepare_iterations())
        comp.finalize()
        assert comp.stats["NB_LINE"] == 0
        assert comp.stats["NB_LINE_OK"] == 0
        assert comp.stats["NB_LINE_REJECT"] == 0


# ===========================================================================
# Executor-driven flow: _CURRENT_ITERATION written by base class
# ===========================================================================

@pytest.mark.unit
class TestCurrentIterationKey:
    def test_executor_writes_current_iteration_after_next(self):
        gm = GlobalMap()
        comp = _make_foreach(config={"values": ["a", "b"]}, global_map=gm)
        comp.execute()  # primes the iterator
        ctx = comp.get_next_iteration_context()
        assert ctx != {}
        assert gm.get("tForeach_1_CURRENT_ITERATION") == 1
        assert gm.get("tForeach_1_CURRENT_VALUE") == "a"

        ctx2 = comp.get_next_iteration_context()
        assert ctx2 != {}
        assert gm.get("tForeach_1_CURRENT_ITERATION") == 2
        assert gm.get("tForeach_1_CURRENT_VALUE") == "b"

        # Exhausted
        assert comp.get_next_iteration_context() == {}


# ===========================================================================
# Execution plan integration: Foreach is recognised as an iterate component
# ===========================================================================

@pytest.mark.unit
class TestExecutionPlanRegistration:
    def test_iterate_types_includes_foreach(self):
        from src.v1.engine.execution_plan import _ITERATE_TYPES
        assert "Foreach" in _ITERATE_TYPES
        assert "tForeach" in _ITERATE_TYPES
