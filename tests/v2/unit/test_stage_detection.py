"""Tests for stage detection from flow connections."""
import pytest

from src.v2.execution.stage import Stage, StageDetector
from src.v2.config.job_config import JobConfig


def _make_config(components, flows=None, triggers=None):
    """Helper to build a minimal JobConfig for testing."""
    return JobConfig(
        name="test",
        components=[
            {"id": cid, "type": "file_input_delimited", "config": {}}
            for cid in components
        ],
        flows=flows or [],
        triggers=triggers or [],
    )


class TestStageDataclass:
    """Tests for the Stage dataclass."""

    def test_stage_creation(self):
        s = Stage(stage_id="stage_0", component_ids={"A", "B"})
        assert s.stage_id == "stage_0"
        assert s.component_ids == {"A", "B"}

    def test_stage_contains(self):
        s = Stage(stage_id="stage_0", component_ids={"A", "B"})
        assert "A" in s.component_ids
        assert "C" not in s.component_ids


class TestStageDetector:
    """Tests for StageDetector.detect() — finds connected components from flows."""

    def test_single_component_no_flows(self):
        config = _make_config(["A"])
        stages = StageDetector.detect(config)
        assert len(stages) == 1
        assert stages[0].component_ids == {"A"}

    def test_two_isolated_components(self):
        config = _make_config(["A", "B"])
        stages = StageDetector.detect(config)
        assert len(stages) == 2
        stage_sets = [s.component_ids for s in stages]
        assert {"A"} in stage_sets
        assert {"B"} in stage_sets

    def test_two_connected_components(self):
        config = _make_config(
            ["A", "B"],
            flows=[{"source": "A", "target": "B"}],
        )
        stages = StageDetector.detect(config)
        assert len(stages) == 1
        assert stages[0].component_ids == {"A", "B"}

    def test_linear_chain_single_stage(self):
        config = _make_config(
            ["A", "B", "C"],
            flows=[
                {"source": "A", "target": "B"},
                {"source": "B", "target": "C"},
            ],
        )
        stages = StageDetector.detect(config)
        assert len(stages) == 1
        assert stages[0].component_ids == {"A", "B", "C"}

    def test_two_separate_pipelines(self):
        config = _make_config(
            ["A", "B", "C", "D"],
            flows=[
                {"source": "A", "target": "B"},
                {"source": "C", "target": "D"},
            ],
        )
        stages = StageDetector.detect(config)
        assert len(stages) == 2
        stage_sets = [s.component_ids for s in stages]
        assert {"A", "B"} in stage_sets
        assert {"C", "D"} in stage_sets

    def test_diamond_topology_single_stage(self):
        config = _make_config(
            ["A", "B", "C", "D"],
            flows=[
                {"source": "A", "target": "B"},
                {"source": "A", "target": "C"},
                {"source": "B", "target": "D"},
                {"source": "C", "target": "D"},
            ],
        )
        stages = StageDetector.detect(config)
        assert len(stages) == 1
        assert stages[0].component_ids == {"A", "B", "C", "D"}

    def test_mixed_connected_and_isolated(self):
        config = _make_config(
            ["A", "B", "C", "D", "E"],
            flows=[
                {"source": "A", "target": "B"},
                {"source": "D", "target": "E"},
            ],
        )
        stages = StageDetector.detect(config)
        assert len(stages) == 3
        stage_sets = [s.component_ids for s in stages]
        assert {"A", "B"} in stage_sets
        assert {"C"} in stage_sets
        assert {"D", "E"} in stage_sets

    def test_stage_ids_are_deterministic(self):
        config = _make_config(["A", "B", "C"])
        stages1 = StageDetector.detect(config)
        stages2 = StageDetector.detect(config)
        assert [s.stage_id for s in stages1] == [s.stage_id for s in stages2]

    def test_triggers_do_not_affect_stage_detection(self):
        config = _make_config(
            ["A", "B"],
            flows=[],
            triggers=[{"source": "A", "target": "B", "type": "on_success"}],
        )
        stages = StageDetector.detect(config)
        assert len(stages) == 2

    def test_component_to_stage_mapping(self):
        config = _make_config(
            ["A", "B", "C"],
            flows=[{"source": "A", "target": "B"}],
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        assert comp_map["A"] == comp_map["B"]
        assert comp_map["C"] != comp_map["A"]

    def test_empty_components(self):
        config = _make_config([])
        stages = StageDetector.detect(config)
        assert len(stages) == 0

    def test_invalid_flow_reference_raises(self):
        config = JobConfig(
            name="test",
            components=[{"id": "A", "type": "file_input_delimited", "config": {}}],
            flows=[{"source": "A", "target": "MISSING"}],
        )
        with pytest.raises(ValueError, match="unknown component"):
            StageDetector.detect(config)
