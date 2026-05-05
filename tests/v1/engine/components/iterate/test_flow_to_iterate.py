"""Unit tests for FlowToIterate engine component (Phase 10-04).

Covers ITER-01, ITER-02, ITER-03, ITER-10, ITER-11; empty input; pd.NA handling;
non-string column names; iterator contract; finalize semantics.
"""
import pytest
import pandas as pd

from src.v1.engine.components.iterate.flow_to_iterate import FlowToIterate, FlowToIterateItem
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.context_manager import ContextManager


def _make_flow_to_iterate(
    comp_id="tFlowToIterate_1",
    config=None,
    global_map=None,
    inputs=None,
):
    """Factory helper: creates a FlowToIterate with resolved config state."""
    config = config if config is not None else {}
    gm = global_map if global_map is not None else GlobalMap()
    ctx = ContextManager(initial_context={"Default": {}})
    comp = FlowToIterate(comp_id, config, gm, ctx)
    # Simulate engine wiring: engine.py sets comp.inputs from comp_config["inputs"]
    comp.inputs = inputs if inputs is not None else []
    # Populate config directly so tests can call _validate_config() / prepare_iterations()
    # without going through execute() (mirrors test_file_exist.py pattern).
    import copy
    comp.config = copy.deepcopy(comp._original_config)
    return comp


# ===========================================================================
# ITER-10: Registration
# ===========================================================================

@pytest.mark.unit
class TestRegistration:
    """ITER-10: FlowToIterate registered under both aliases."""

    def test_registered_as_FlowToIterate(self):
        assert REGISTRY.get("FlowToIterate") is FlowToIterate

    def test_registered_as_tFlowToIterate(self):
        assert REGISTRY.get("tFlowToIterate") is FlowToIterate


# ===========================================================================
# Phase 7.1 Rule 12: _validate_config structural-only
# ===========================================================================

@pytest.mark.unit
class TestValidateConfig:
    """Validate structural checks only -- no content resolution."""

    def test_default_map_bool_valid(self):
        comp = _make_flow_to_iterate(config={"default_map": True, "map_entries": []}, inputs=["row1"])
        comp._validate_config()  # should not raise

    def test_default_map_false_requires_map_entries_list(self):
        comp = _make_flow_to_iterate(
            config={"default_map": False, "map_entries": "not_a_list"},
            inputs=["row1"],
        )
        with pytest.raises(ConfigurationError, match="map_entries"):
            comp._validate_config()

    def test_map_entries_defaults_to_list_ok(self):
        comp = _make_flow_to_iterate(config={"default_map": True}, inputs=["row1"])
        comp._validate_config()  # default_map=True; map_entries irrelevant

    def test_inputs_must_be_non_empty_when_called(self):
        """_validate_config checks that self.inputs is non-empty (structural: set by engine)."""
        comp = _make_flow_to_iterate(config={"default_map": True}, inputs=[])
        with pytest.raises(ConfigurationError, match="inputs"):
            comp._validate_config()

    def test_does_not_check_row_content(self):
        """_validate_config must NOT inspect actual row data (Rule 12 -- structural only)."""
        comp = _make_flow_to_iterate(
            config={"default_map": False, "map_entries": [{"key": "k", "value": "col"}]},
            inputs=["row1"],
        )
        # This must not raise even though 'col' may not exist in any actual row.
        comp._validate_config()


# ===========================================================================
# ITER-01: prepare_iterations
# ===========================================================================

@pytest.mark.unit
class TestPrepareIterations:
    """ITER-01: one item produced per input row; bounded iterator."""

    def test_iterates_each_row(self):
        df = pd.DataFrame([
            {"filepath": "/a", "filename": "a.txt"},
            {"filepath": "/b", "filename": "b.txt"},
            {"filepath": "/c", "filename": "c.txt"},
        ])
        comp = _make_flow_to_iterate(config={"default_map": True}, inputs=["row1"])
        items = list(comp.prepare_iterations(df))
        assert len(items) == 3
        assert all(isinstance(it, FlowToIterateItem) for it in items)

    def test_items_have_one_based_index(self):
        df = pd.DataFrame([{"a": 1}, {"a": 2}, {"a": 3}])
        comp = _make_flow_to_iterate(config={"default_map": True}, inputs=["row1"])
        items = list(comp.prepare_iterations(df))
        assert [it.index for it in items] == [1, 2, 3]

    def test_total_iterations_set_correctly(self):
        df = pd.DataFrame([{"x": i} for i in range(5)])
        comp = _make_flow_to_iterate(config={"default_map": True}, inputs=["row1"])
        list(comp.prepare_iterations(df))
        assert comp.total_iterations == 5

    def test_returns_iterator_not_list(self):
        df = pd.DataFrame([{"a": 1}, {"a": 2}])
        comp = _make_flow_to_iterate(config={"default_map": True}, inputs=["row1"])
        it = comp.prepare_iterations(df)
        assert not isinstance(it, list)
        assert iter(it) is it

    def test_empty_dataframe_zero_iterations_no_error(self):
        df = pd.DataFrame()
        comp = _make_flow_to_iterate(config={"default_map": True}, inputs=["row1"])
        it = comp.prepare_iterations(df)
        items = list(it)
        assert items == []
        assert comp.total_iterations == 0

    def test_none_input_raises_configuration_error(self):
        comp = _make_flow_to_iterate(config={"default_map": True}, inputs=["row1"])
        with pytest.raises(ConfigurationError, match="non-None"):
            comp.prepare_iterations(None)


# ===========================================================================
# ITER-02: DEFAULT_MAP=true (key format <inputFlow>.<col>)
# ===========================================================================

@pytest.mark.unit
class TestDefaultMapTrue:
    """ITER-02: DEFAULT_MAP=true writes <inputFlow>.<col> keys to globalMap."""

    def _make(self, inputs=None, gm=None):
        gm = gm or GlobalMap()
        comp = _make_flow_to_iterate(
            config={"default_map": True},
            global_map=gm,
            inputs=inputs or ["row1"],
        )
        return comp, gm

    def test_keys_use_input_flow_prefix(self):
        gm = GlobalMap()
        comp, gm = self._make(inputs=["row1"], gm=gm)
        item = FlowToIterateItem(
            row={"filepath": "/x", "filename": "x.txt"},
            index=1,
        )
        comp.set_iteration_globalmap(item)
        assert gm.get("row1.filepath") == "/x"
        assert gm.get("row1.filename") == "x.txt"

    def test_last_row_persists_after_iteration(self):
        """D-F6: after all iterations globalMap has last-row values."""
        gm = GlobalMap()
        comp, gm = self._make(inputs=["row1"], gm=gm)
        for i, val in enumerate(["/a", "/b", "/c"], start=1):
            item = FlowToIterateItem(row={"filepath": val}, index=i)
            comp.set_iteration_globalmap(item)
        assert gm.get("row1.filepath") == "/c"

    def test_no_inputs_raises_on_set_globalmap(self):
        comp, gm = self._make(inputs=[])
        item = FlowToIterateItem(row={"col": 1}, index=1)
        with pytest.raises(ConfigurationError):
            comp.set_iteration_globalmap(item)

    def test_pd_na_converted_to_none(self):
        """RESEARCH Risk 10.2: pd.NA must not leak into globalMap."""
        gm = GlobalMap()
        comp, gm = self._make(inputs=["row1"], gm=gm)
        item = FlowToIterateItem(
            row={"a": pd.NA},
            index=1,
        )
        comp.set_iteration_globalmap(item)
        assert gm.get("row1.a") is None

    def test_non_string_column_coerced(self):
        """Risk 10.2: int column names must be str()-coerced in key."""
        gm = GlobalMap()
        comp, gm = self._make(inputs=["row1"], gm=gm)
        # Column name is int 0 (positional DataFrame)
        item = FlowToIterateItem(row={0: "val"}, index=1)
        comp.set_iteration_globalmap(item)
        assert gm.get("row1.0") == "val"


# ===========================================================================
# ITER-03: DEFAULT_MAP=false (custom MAP entries, verbatim user keys)
# ===========================================================================

@pytest.mark.unit
class TestDefaultMapFalse:
    """ITER-03: DEFAULT_MAP=false writes user-defined keys verbatim (no prefix)."""

    def _make(self, map_entries, inputs=None, gm=None):
        gm = gm or GlobalMap()
        comp = _make_flow_to_iterate(
            config={"default_map": False, "map_entries": map_entries},
            global_map=gm,
            inputs=inputs or ["row1"],
        )
        return comp, gm

    def test_custom_map_uses_user_keys_no_prefix(self):
        gm = GlobalMap()
        comp, gm = self._make(
            map_entries=[{"key": "my_path", "value": "filepath"}],
            inputs=["row1"],
            gm=gm,
        )
        item = FlowToIterateItem(row={"filepath": "/data/file.csv"}, index=1)
        comp.set_iteration_globalmap(item)
        assert gm.get("my_path") == "/data/file.csv"
        # Must NOT write prefixed key
        assert gm.get("row1.filepath") is None

    def test_multiple_entries(self):
        gm = GlobalMap()
        comp, gm = self._make(
            map_entries=[
                {"key": "target_path", "value": "filepath"},
                {"key": "target_name", "value": "filename"},
            ],
            inputs=["row1"],
            gm=gm,
        )
        item = FlowToIterateItem(
            row={"filepath": "/path/f.csv", "filename": "f.csv"},
            index=1,
        )
        comp.set_iteration_globalmap(item)
        assert gm.get("target_path") == "/path/f.csv"
        assert gm.get("target_name") == "f.csv"

    def test_value_col_missing_raises(self):
        comp, _ = self._make(
            map_entries=[{"key": "dest", "value": "nonexistent_col"}],
            inputs=["row1"],
        )
        item = FlowToIterateItem(row={"filepath": "/x"}, index=1)
        with pytest.raises(ConfigurationError, match="nonexistent_col"):
            comp.set_iteration_globalmap(item)

    def test_pd_na_converted_to_none(self):
        """RESEARCH Risk 10.2: pd.NA must not leak into globalMap via custom map."""
        gm = GlobalMap()
        comp, gm = self._make(
            map_entries=[{"key": "my_val", "value": "col"}],
            inputs=["row1"],
            gm=gm,
        )
        item = FlowToIterateItem(row={"col": pd.NA}, index=1)
        comp.set_iteration_globalmap(item)
        assert gm.get("my_val") is None


# ===========================================================================
# ITER-11: CURRENT_ITERATION key naming (typo absence)
# ===========================================================================

@pytest.mark.unit
class TestCurrentIterationKey:
    """ITER-11: FlowToIterate itself does NOT write _CURRENT_ITERATE (old typo key).

    The executor (BaseIterateComponent.get_next_iteration_context) writes
    {cid}_CURRENT_ITERATION. FlowToIterate.set_iteration_globalmap must not
    write the old typo variant.
    """

    def test_does_not_write_current_iterate_typo(self):
        """Confirms FlowToIterate.set_iteration_globalmap does NOT write _CURRENT_ITERATE."""
        gm = GlobalMap()
        comp = _make_flow_to_iterate(
            config={"default_map": True},
            global_map=gm,
            inputs=["row1"],
        )
        item = FlowToIterateItem(row={"col": "val"}, index=1)
        comp.set_iteration_globalmap(item)
        # The typo key must not be present
        assert gm.get("tFlowToIterate_1_CURRENT_ITERATE") is None
        # The correct key is written by the executor (not by this method)
        assert gm.get("tFlowToIterate_1_CURRENT_ITERATION") is None

    def test_executor_writes_current_iteration_key(self):
        """Verifies BaseIterateComponent.get_next_iteration_context sets correct key."""
        gm = GlobalMap()
        comp = _make_flow_to_iterate(
            config={"default_map": True},
            global_map=gm,
            inputs=["row1"],
        )
        df = pd.DataFrame([{"col": "val1"}, {"col": "val2"}])
        # Drive via execute() + get_next_iteration_context() to verify executor writes key
        comp.execute(df)
        ctx = comp.get_next_iteration_context()
        assert ctx != {}
        # Executor should have written the _CURRENT_ITERATION key (ITER-11)
        assert gm.get("tFlowToIterate_1_CURRENT_ITERATION") == 1


# ===========================================================================
# Statistics
# ===========================================================================

@pytest.mark.unit
class TestStatistics:
    """NB_LINE, NB_LINE_OK, NB_LINE_REJECT set correctly after finalize()."""

    def test_finalize_sets_nb_line_total(self):
        df = pd.DataFrame([{"x": i} for i in range(4)])
        comp = _make_flow_to_iterate(config={"default_map": True}, inputs=["row1"])
        list(comp.prepare_iterations(df))
        comp.finalize()
        assert comp.stats["NB_LINE"] == 4

    def test_nb_line_ok_equals_nb_line(self):
        df = pd.DataFrame([{"x": i} for i in range(3)])
        comp = _make_flow_to_iterate(config={"default_map": True}, inputs=["row1"])
        list(comp.prepare_iterations(df))
        comp.finalize()
        assert comp.stats["NB_LINE_OK"] == comp.stats["NB_LINE"]

    def test_nb_line_reject_zero(self):
        df = pd.DataFrame([{"x": i} for i in range(2)])
        comp = _make_flow_to_iterate(config={"default_map": True}, inputs=["row1"])
        list(comp.prepare_iterations(df))
        comp.finalize()
        assert comp.stats["NB_LINE_REJECT"] == 0
