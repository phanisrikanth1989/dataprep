"""Integration tests for stage-based orchestration in PyETLEngine."""
import polars as pl
import pytest

from src.v2.engine import PyETLEngine


@pytest.fixture
def temp_job_dir(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    return {"base": tmp_path, "input": input_dir, "output": output_dir}


@pytest.fixture
def sample_csv(temp_job_dir):
    """Create a simple CSV file for testing."""
    csv_path = temp_job_dir["input"] / "data.csv"
    df = pl.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "amount": [100.0, 200.0, 300.0],
    })
    df.write_csv(csv_path)
    return csv_path


class TestEngineNoTriggers:
    """Existing behavior preserved when no triggers are present."""

    def test_simple_pipeline_no_triggers(self, temp_job_dir, sample_csv):
        """A job without triggers runs identically to current behavior."""
        output_path = temp_job_dir["output"] / "out.csv"
        config = {
            "name": "no_trigger_test",
            "components": [
                {"id": "input", "type": "file_input_delimited", "config": {
                    "path": str(sample_csv),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "float"},
                    ],
                }},
                {"id": "output", "type": "file_output_delimited", "config": {
                    "path": str(output_path),
                }},
            ],
            "flows": [{"source": "input", "target": "output"}],
        }
        engine = PyETLEngine(config)
        result = engine.execute()
        assert result["status"] == "success"
        output_df = pl.read_csv(output_path)
        assert len(output_df) == 3


class TestEngineWithTriggers:
    """Tests for stage-based orchestration with triggers."""

    def test_two_stages_on_success(self, temp_job_dir, sample_csv):
        """Stage 1 -> on_success -> Stage 2."""
        output1 = temp_job_dir["output"] / "out1.csv"
        output2 = temp_job_dir["output"] / "out2.csv"

        csv2 = temp_job_dir["input"] / "data2.csv"
        pl.DataFrame({"x": [10, 20]}).write_csv(csv2)

        config = {
            "name": "two_stage_test",
            "components": [
                {"id": "in1", "type": "file_input_delimited", "config": {
                    "path": str(sample_csv),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "float"},
                    ],
                }},
                {"id": "out1", "type": "file_output_delimited", "config": {
                    "path": str(output1),
                }},
                {"id": "in2", "type": "file_input_delimited", "config": {
                    "path": str(csv2),
                    "schema": [{"name": "x", "type": "integer"}],
                }},
                {"id": "out2", "type": "file_output_delimited", "config": {
                    "path": str(output2),
                }},
            ],
            "flows": [
                {"source": "in1", "target": "out1"},
                {"source": "in2", "target": "out2"},
            ],
            "triggers": [
                {"source": "out1", "target": "in2", "type": "on_success"},
            ],
        }
        engine = PyETLEngine(config)
        result = engine.execute()
        assert result["status"] == "success"
        assert pl.read_csv(output1).shape[0] == 3
        assert pl.read_csv(output2).shape[0] == 2

    def test_on_failure_trigger_runs_error_handler(self, temp_job_dir):
        """Stage 1 fails -> on_failure -> Stage 2 (error handler) runs."""
        error_output = temp_job_dir["output"] / "error.csv"

        # Create error marker CSV
        error_csv = temp_job_dir["input"] / "error_marker.csv"
        pl.DataFrame({"error": ["stage_1_failed"]}).write_csv(error_csv)

        config = {
            "name": "failure_test",
            "components": [
                {"id": "bad_input", "type": "file_input_delimited", "config": {
                    "path": "/nonexistent/file.csv",
                    "schema": [{"name": "x", "type": "string"}],
                }},
                {"id": "error_input", "type": "file_input_delimited", "config": {
                    "path": str(error_csv),
                    "schema": [{"name": "error", "type": "string"}],
                }},
                {"id": "error_output", "type": "file_output_delimited", "config": {
                    "path": str(error_output),
                }},
            ],
            "flows": [
                {"source": "error_input", "target": "error_output"},
            ],
            "triggers": [
                {"source": "bad_input", "target": "error_input", "type": "on_failure"},
            ],
        }
        engine = PyETLEngine(config)
        result = engine.execute()
        assert result["status"] == "error"
        assert error_output.exists()
        assert pl.read_csv(error_output).shape[0] == 1

    def test_on_success_skips_when_stage_fails(self, temp_job_dir):
        """Stage 1 fails -> on_success -> Stage 2 is SKIPPED."""
        output2 = temp_job_dir["output"] / "out2.csv"
        csv2 = temp_job_dir["input"] / "data2.csv"
        pl.DataFrame({"x": [1]}).write_csv(csv2)

        config = {
            "name": "skip_test",
            "components": [
                {"id": "bad_input", "type": "file_input_delimited", "config": {
                    "path": "/nonexistent/file.csv",
                    "schema": [{"name": "x", "type": "string"}],
                }},
                {"id": "in2", "type": "file_input_delimited", "config": {
                    "path": str(csv2),
                    "schema": [{"name": "x", "type": "integer"}],
                }},
                {"id": "out2", "type": "file_output_delimited", "config": {
                    "path": str(output2),
                }},
            ],
            "flows": [
                {"source": "in2", "target": "out2"},
            ],
            "triggers": [
                {"source": "bad_input", "target": "in2", "type": "on_success"},
            ],
        }
        engine = PyETLEngine(config)
        result = engine.execute()
        assert result["status"] == "error"
        assert not output2.exists()

    def test_three_stage_chain(self, temp_job_dir, sample_csv):
        """Stage A -> on_success -> Stage B -> on_success -> Stage C."""
        out1 = temp_job_dir["output"] / "out1.csv"
        out2 = temp_job_dir["output"] / "out2.csv"
        csv2 = temp_job_dir["input"] / "data2.csv"
        csv3 = temp_job_dir["input"] / "data3.csv"
        pl.DataFrame({"x": [10, 20]}).write_csv(csv2)
        pl.DataFrame({"y": [100]}).write_csv(csv3)

        config = {
            "name": "three_stage_chain",
            "components": [
                {"id": "in1", "type": "file_input_delimited", "config": {
                    "path": str(sample_csv),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "float"},
                    ],
                }},
                {"id": "out1", "type": "file_output_delimited", "config": {
                    "path": str(out1),
                }},
                {"id": "in2", "type": "file_input_delimited", "config": {
                    "path": str(csv2),
                    "schema": [{"name": "x", "type": "integer"}],
                }},
                {"id": "out2", "type": "file_output_delimited", "config": {
                    "path": str(out2),
                }},
                {"id": "in3", "type": "file_input_delimited", "config": {
                    "path": str(csv3),
                    "schema": [{"name": "y", "type": "integer"}],
                }},
            ],
            "flows": [
                {"source": "in1", "target": "out1"},
                {"source": "in2", "target": "out2"},
            ],
            "triggers": [
                {"source": "out1", "target": "in2", "type": "on_success"},
                {"source": "out2", "target": "in3", "type": "on_success"},
            ],
        }
        engine = PyETLEngine(config)
        result = engine.execute()
        assert result["status"] == "success"
        assert pl.read_csv(out1).shape[0] == 3
        assert pl.read_csv(out2).shape[0] == 2

    def test_stages_result_in_output(self, temp_job_dir, sample_csv):
        """Result dict includes stage information when triggers are present."""
        output_path = temp_job_dir["output"] / "out.csv"
        ctx_path = temp_job_dir["input"] / "ctx.json"
        ctx_path.write_text('{"env": "test"}')

        config = {
            "name": "stages_result_test",
            "components": [
                {"id": "ctx", "type": "context_load", "config": {
                    "path": str(ctx_path),
                    "format": "json",
                }},
                {"id": "in1", "type": "file_input_delimited", "config": {
                    "path": str(sample_csv),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "float"},
                    ],
                }},
                {"id": "out1", "type": "file_output_delimited", "config": {
                    "path": str(output_path),
                }},
            ],
            "flows": [{"source": "in1", "target": "out1"}],
            "triggers": [
                {"source": "ctx", "target": "in1", "type": "on_success"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()
        assert result["status"] == "success"
        assert "stages" in result
        assert len(result["stages"]) == 2
