"""Tests for StageExecutor — orchestration layer."""
import pytest

from src.v2.execution.stage import (
    StageDAG, StageDetector, StageExecutor, StageResult, StageStatus,
)
from src.v2.config.job_config import JobConfig


def _make_config(components, flows=None, triggers=None, context=None):
    """Helper to build a minimal JobConfig."""
    return JobConfig(
        name="test",
        components=[
            {"id": cid, "type": "file_input_delimited", "config": {}}
            for cid in components
        ],
        flows=flows or [],
        triggers=triggers or [],
        context=context or {},
    )


class TestStageExecutorRunDecision:
    """Tests for should-run logic based on trigger rules."""

    def test_entry_stage_always_runs(self):
        """Stages with no incoming triggers always run."""
        config = _make_config(["A", "B"],
            triggers=[{"source": "A", "target": "B", "type": "on_success"}])
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {})
        assert executor.should_stage_run(comp_map["A"]) is True

    def test_on_success_runs_after_success(self):
        config = _make_config(["A", "B"],
            triggers=[{"source": "A", "target": "B", "type": "on_success"}])
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {})
        executor.record_result(StageResult(
            stage_id=comp_map["A"], status=StageStatus.SUCCESS,
        ))
        assert executor.should_stage_run(comp_map["B"]) is True

    def test_on_success_skips_after_failure(self):
        config = _make_config(["A", "B"],
            triggers=[{"source": "A", "target": "B", "type": "on_success"}])
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {})
        executor.record_result(StageResult(
            stage_id=comp_map["A"], status=StageStatus.FAILED,
        ))
        assert executor.should_stage_run(comp_map["B"]) is False

    def test_on_failure_runs_after_failure(self):
        config = _make_config(["A", "B"],
            triggers=[{"source": "A", "target": "B", "type": "on_failure"}])
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {})
        executor.record_result(StageResult(
            stage_id=comp_map["A"], status=StageStatus.FAILED,
        ))
        assert executor.should_stage_run(comp_map["B"]) is True

    def test_on_failure_skips_after_success(self):
        config = _make_config(["A", "B"],
            triggers=[{"source": "A", "target": "B", "type": "on_failure"}])
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {})
        executor.record_result(StageResult(
            stage_id=comp_map["A"], status=StageStatus.SUCCESS,
        ))
        assert executor.should_stage_run(comp_map["B"]) is False

    def test_conditional_runs_when_true(self):
        config = _make_config(
            ["A", "B"],
            triggers=[{"source": "A", "target": "B", "type": "conditional",
                       "condition": "${context.env} == 'PROD'"}],
            context={"env": "PROD"},
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {"env": "PROD"})
        executor.record_result(StageResult(
            stage_id=comp_map["A"], status=StageStatus.SUCCESS,
        ))
        assert executor.should_stage_run(comp_map["B"]) is True

    def test_conditional_skips_when_false(self):
        config = _make_config(
            ["A", "B"],
            triggers=[{"source": "A", "target": "B", "type": "conditional",
                       "condition": "${context.env} == 'PROD'"}],
            context={"env": "DEV"},
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {"env": "DEV"})
        executor.record_result(StageResult(
            stage_id=comp_map["A"], status=StageStatus.SUCCESS,
        ))
        assert executor.should_stage_run(comp_map["B"]) is False

    def test_fan_in_or_semantics(self):
        """Stage C runs if ANY incoming trigger is satisfied (OR)."""
        config = _make_config(
            ["A", "B", "C"],
            triggers=[
                {"source": "A", "target": "C", "type": "on_success"},
                {"source": "B", "target": "C", "type": "on_success"},
            ],
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {})
        executor.record_result(StageResult(
            stage_id=comp_map["A"], status=StageStatus.FAILED,
        ))
        executor.record_result(StageResult(
            stage_id=comp_map["B"], status=StageStatus.SUCCESS,
        ))
        assert executor.should_stage_run(comp_map["C"]) is True

    def test_skip_propagation(self):
        """Downstream of SKIPPED stage is also SKIPPED."""
        config = _make_config(
            ["A", "B", "C"],
            triggers=[
                {"source": "A", "target": "B", "type": "on_success"},
                {"source": "B", "target": "C", "type": "on_success"},
            ],
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {})
        executor.record_result(StageResult(
            stage_id=comp_map["A"], status=StageStatus.FAILED,
        ))
        assert executor.should_stage_run(comp_map["B"]) is False
        executor.record_result(StageResult(
            stage_id=comp_map["B"], status=StageStatus.SKIPPED,
        ))
        assert executor.should_stage_run(comp_map["C"]) is False


class TestStageExecutorResults:
    """Tests for result tracking and job status."""

    def test_all_success_job_status(self):
        config = _make_config(["A", "B"],
            triggers=[{"source": "A", "target": "B", "type": "on_success"}])
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {})
        executor.record_result(StageResult(stage_id=comp_map["A"], status=StageStatus.SUCCESS))
        executor.record_result(StageResult(stage_id=comp_map["B"], status=StageStatus.SUCCESS))

        assert executor.get_job_status() == "success"

    def test_unhandled_failure_job_status(self):
        """Failed stage with no on_failure handler -> job failed."""
        config = _make_config(["A", "B"],
            triggers=[{"source": "A", "target": "B", "type": "on_success"}])
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {})
        executor.record_result(StageResult(stage_id=comp_map["A"], status=StageStatus.FAILED))
        executor.record_result(StageResult(stage_id=comp_map["B"], status=StageStatus.SKIPPED))

        assert executor.get_job_status() == "error"

    def test_handled_failure_job_status(self):
        """Failed stage WITH on_failure handler that succeeds -> job still error."""
        config = _make_config(
            ["A", "B", "C"],
            triggers=[
                {"source": "A", "target": "B", "type": "on_success"},
                {"source": "A", "target": "C", "type": "on_failure"},
            ],
        )
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {})
        executor.record_result(StageResult(stage_id=comp_map["A"], status=StageStatus.FAILED))
        executor.record_result(StageResult(stage_id=comp_map["B"], status=StageStatus.SKIPPED))
        executor.record_result(StageResult(stage_id=comp_map["C"], status=StageStatus.SUCCESS))

        assert executor.get_job_status() == "error"

    def test_get_results(self):
        config = _make_config(["A"])
        stages, comp_map = StageDetector.detect_with_mapping(config)
        dag = StageDAG.build(stages, config.triggers, comp_map)

        executor = StageExecutor(dag, comp_map, {})
        executor.record_result(StageResult(
            stage_id=comp_map["A"], status=StageStatus.SUCCESS,
            rows_out={"main": 100}, duration_ms=50.0,
        ))

        results = executor.get_results()
        assert len(results) == 1
        assert results[0].rows_out == {"main": 100}
