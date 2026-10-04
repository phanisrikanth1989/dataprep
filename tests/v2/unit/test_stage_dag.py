"""Tests for StageDAG — DAG of stages built from triggers."""
import logging

import pytest

from src.v2.execution.stage import StageDAG, StageDetector
from src.v2.config.job_config import (
    JobConfig, TriggerType,
)


def _make_config(components, flows=None, triggers=None):
    """Helper to build a minimal JobConfig."""
    return JobConfig(
        name="test",
        components=[
            {"id": cid, "type": "file_input_delimited", "config": {}}
            for cid in components
        ],
        flows=flows or [],
        triggers=triggers or [],
    )


class TestStageDAG:
    """Tests for StageDAG construction and topological sort."""

    def test_no_triggers_all_entry_stages(self):
        """No triggers → all stages are entry stages, topo order = sorted stage IDs."""
        config = _make_config(["A", "B", "C"])
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)
        order = dag.get_execution_order()
        assert len(order) == 3

    def test_single_trigger_orders_stages(self):
        """A --on_success--> B means stage(A) before stage(B)."""
        config = _make_config(
            ["A", "B"],
            triggers=[{"source": "A", "target": "B", "type": "on_success"}],
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)
        order = dag.get_execution_order()
        assert len(order) == 2
        idx_a = order.index(comp_map["A"])
        idx_b = order.index(comp_map["B"])
        assert idx_a < idx_b

    def test_chain_of_triggers(self):
        """A --on_success--> B --on_success--> C gives linear order."""
        config = _make_config(
            ["A", "B", "C"],
            triggers=[
                {"source": "A", "target": "B", "type": "on_success"},
                {"source": "B", "target": "C", "type": "on_success"},
            ],
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)
        order = dag.get_execution_order()
        idx_a = order.index(comp_map["A"])
        idx_b = order.index(comp_map["B"])
        idx_c = order.index(comp_map["C"])
        assert idx_a < idx_b < idx_c

    def test_fan_out_triggers(self):
        """A --on_success--> B, A --on_failure--> C. Both B,C after A."""
        config = _make_config(
            ["A", "B", "C"],
            triggers=[
                {"source": "A", "target": "B", "type": "on_success"},
                {"source": "A", "target": "C", "type": "on_failure"},
            ],
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)
        order = dag.get_execution_order()
        idx_a = order.index(comp_map["A"])
        idx_b = order.index(comp_map["B"])
        idx_c = order.index(comp_map["C"])
        assert idx_a < idx_b
        assert idx_a < idx_c

    def test_fan_in_triggers(self):
        """A --on_success--> C, B --on_success--> C. C after both A and B."""
        config = _make_config(
            ["A", "B", "C"],
            triggers=[
                {"source": "A", "target": "C", "type": "on_success"},
                {"source": "B", "target": "C", "type": "on_success"},
            ],
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)
        order = dag.get_execution_order()
        idx_a = order.index(comp_map["A"])
        idx_b = order.index(comp_map["B"])
        idx_c = order.index(comp_map["C"])
        assert idx_a < idx_c
        assert idx_b < idx_c

    def test_circular_triggers_raises(self):
        """Circular triggers should raise an error."""
        config = _make_config(
            ["A", "B"],
            triggers=[
                {"source": "A", "target": "B", "type": "on_success"},
                {"source": "B", "target": "A", "type": "on_success"},
            ],
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        with pytest.raises(ValueError, match="[Cc]ircular|[Cc]ycle"):
            StageDAG.build(stages, config.triggers, comp_map)

    def test_entry_stages(self):
        """Entry stages have no incoming triggers."""
        config = _make_config(
            ["A", "B", "C"],
            triggers=[
                {"source": "A", "target": "B", "type": "on_success"},
            ],
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)
        entry = dag.get_entry_stages()
        assert comp_map["A"] in entry
        assert comp_map["C"] in entry
        assert comp_map["B"] not in entry

    def test_triggers_for_stage(self):
        """get_incoming_triggers returns triggers targeting a specific stage."""
        config = _make_config(
            ["A", "B", "C"],
            triggers=[
                {"source": "A", "target": "B", "type": "on_success"},
                {"source": "A", "target": "C", "type": "on_failure"},
            ],
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)
        triggers_b = dag.get_incoming_triggers(comp_map["B"])
        assert len(triggers_b) == 1
        assert triggers_b[0].type == TriggerType.ON_SUCCESS

    def test_same_stage_trigger_ignored_with_warning(self, caplog):
        """Trigger between components in the same stage is ignored with warning."""
        config = _make_config(
            ["A", "B"],
            flows=[{"source": "A", "target": "B"}],
            triggers=[{"source": "A", "target": "B", "type": "on_success"}],
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        assert comp_map["A"] == comp_map["B"]
        with caplog.at_level(logging.WARNING, logger="src.v2.execution.stage"):
            dag = StageDAG.build(stages, config.triggers, comp_map)
        assert any("ignored" in r.message for r in caplog.records)
        order = dag.get_execution_order()
        assert len(order) == 1
