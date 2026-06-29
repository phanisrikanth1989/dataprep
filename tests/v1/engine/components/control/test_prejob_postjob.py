"""Tests for Prejob (tPrejob) and Postjob (tPostjob) no-op marker components.

These components are deliberate no-ops: they produce no data and exist only so
the node executes successfully (letting its OnSubjobOk trigger fire). The
"run first" / "run last" ordering and the post-job success-gate are enforced by
ExecutionPlan and Executor, not by these classes -- see
tests/v1/engine/test_execution_plan.py and tests/v1/engine/test_executor.py.
"""
import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.control.postjob import Postjob
from src.v1.engine.components.control.prejob import Prejob
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap


# (class, v1_name, talend_name)
_MARKERS = [
    (Prejob, "Prejob", "tPrejob"),
    (Postjob, "Postjob", "tPostjob"),
]
_IDS = ["prejob", "postjob"]


def _make(cls, config=None, global_map=None):
    return cls(
        component_id=f"{cls.__name__}_1",
        config=config if config is not None else {},
        global_map=global_map if global_map is not None else GlobalMap(),
        context_manager=ContextManager(),
    )


def _df():
    return pd.DataFrame({"id": [1, 2, 3]})


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("cls, v1_name, talend_name", _MARKERS, ids=_IDS)
class TestRegistration:
    def test_v1_name_registered(self, cls, v1_name, talend_name):
        assert REGISTRY.get(v1_name) is cls

    def test_talend_alias_registered(self, cls, v1_name, talend_name):
        assert REGISTRY.get(talend_name) is cls


# ------------------------------------------------------------------
# No-op execution
# ------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("cls, v1_name, talend_name", _MARKERS, ids=_IDS)
class TestNoOpExecution:
    def test_validate_config_never_raises(self, cls, v1_name, talend_name):
        # Even with unexpected keys, the marker has no structural requirements.
        comp = _make(cls, config={"label": "x", "tstatcatcher_stats": True, "junk": 1})
        comp.config = dict(comp._original_config)
        assert comp._validate_config() is None

    def test_none_input_produces_no_data(self, cls, v1_name, talend_name):
        result = _make(cls).execute(None)
        assert result["main"] is None
        assert result["reject"] is None

    def test_dataframe_input_is_ignored(self, cls, v1_name, talend_name):
        # A marker carries no data flow; any incoming frame is dropped.
        result = _make(cls).execute(_df())
        assert result["main"] is None

    def test_executes_without_global_map(self, cls, v1_name, talend_name):
        comp = cls(
            component_id="m1",
            config={},
            global_map=None,
            context_manager=ContextManager(),
        )
        result = comp.execute(None)
        assert result["main"] is None


# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("cls, v1_name, talend_name", _MARKERS, ids=_IDS)
class TestStats:
    def test_stats_all_zero_on_none_input(self, cls, v1_name, talend_name):
        gm = GlobalMap()
        comp = _make(cls, global_map=gm)
        comp.execute(None)
        assert comp.stats["NB_LINE"] == 0
        assert comp.stats["NB_LINE_OK"] == 0
        assert comp.stats["NB_LINE_REJECT"] == 0


# ------------------------------------------------------------------
# Iterate re-execution
# ------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("cls, v1_name, talend_name", _MARKERS, ids=_IDS)
class TestReexecution:
    def test_second_execute_same_result(self, cls, v1_name, talend_name):
        comp = _make(cls)
        r1 = comp.execute(None)
        comp.reset()
        r2 = comp.execute(None)
        assert r1["main"] is None and r2["main"] is None

    def test_config_not_mutated(self, cls, v1_name, talend_name):
        comp = _make(cls, config={"label": "lbl"})
        comp.execute(None)
        snapshot = dict(comp._original_config)
        comp.reset()
        comp.execute(None)
        assert comp._original_config == snapshot
