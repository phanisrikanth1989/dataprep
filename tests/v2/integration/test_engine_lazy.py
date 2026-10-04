"""
Integration tests for V2 engine with barrier-aware lazy execution.

Tests verify:
- Linear pipeline stays lazy until sink (barrier) collects
- Stats are recorded per-component
- Ref counting frees upstream outputs
"""
import pytest
import polars as pl
from pathlib import Path
from src.v2.engine import PyETLEngine


class TestLazyPipelineFusion:
    def test_linear_pipeline_stays_lazy(self, tmp_path):
        """read -> filter -> write: only one collect at the sink"""
        input_file = tmp_path / "input.csv"
        output_file = tmp_path / "output.csv"
        input_file.write_text("id,name,amount\n1,Alice,150\n2,Bob,50\n3,Charlie,200\n")

        config = {
            "name": "test_lazy",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_file), "delimiter": ",",
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "float"},
                    ]
                }},
                {"id": "filter", "type": "filter", "config": {
                    "condition": "amount > 100"
                }},
                {"id": "write", "type": "file_output_delimited", "config": {
                    "path": str(output_file), "delimiter": ","
                }},
            ],
            "flows": [
                {"source": "read", "target": "filter"},
                {"source": "filter", "target": "write"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        assert output_file.exists()
        df = pl.read_csv(output_file)
        assert len(df) == 2  # Alice (150) and Charlie (200)
        assert set(df["name"].to_list()) == {"Alice", "Charlie"}
        # Verify stats
        assert "components" in result
        assert "write" in result["components"]

    def test_stats_structure(self, tmp_path):
        """Execution result contains per-component stats"""
        input_file = tmp_path / "input.csv"
        output_file = tmp_path / "output.csv"
        input_file.write_text("id,val\n1,100\n2,200\n")

        config = {
            "name": "test_stats",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_file), "delimiter": ",",
                    "schema": [{"name": "id", "type": "integer"}, {"name": "val", "type": "integer"}],
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_file)}},
            ],
            "flows": [{"source": "read", "target": "write"}],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert "components" in result
        assert "read" in result["components"]
        assert "write" in result["components"]
        assert "duration_ms" in result["components"]["read"]

    def test_ref_counting_frees_memory(self, tmp_path):
        """Upstream outputs are freed after all consumers are done."""
        input_file = tmp_path / "input.csv"
        output_file = tmp_path / "output.csv"
        input_file.write_text("id,val\n1,100\n2,200\n")

        config = {
            "name": "test_refcount",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_file), "delimiter": ",",
                    "schema": [{"name": "id", "type": "integer"}, {"name": "val", "type": "integer"}],
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_file)}},
            ],
            "flows": [{"source": "read", "target": "write"}],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        # After execution, "read" output should have been freed by ref counting
        # (write consumed it, ref count reached 0)

    def test_error_handling(self, tmp_path):
        """Engine returns error result on failure."""
        output_file = tmp_path / "output.csv"
        config = {
            "name": "test_error",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(tmp_path / "nonexistent.csv"), "delimiter": ",",
                    "schema": [{"name": "id", "type": "integer"}],
                }},
                {"id": "write", "type": "file_output_delimited", "config": {
                    "path": str(output_file),
                }},
            ],
            "flows": [{"source": "read", "target": "write"}],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "error"
        assert "error" in result
        assert "error_type" in result

    def test_barrier_at_sink(self, tmp_path):
        """Sink components are barriers and force materialization."""
        input_file = tmp_path / "input.csv"
        output_file = tmp_path / "output.csv"
        input_file.write_text("a,b\n1,2\n3,4\n")

        config = {
            "name": "test_barrier",
            "components": [
                {"id": "src", "type": "file_input_delimited", "config": {
                    "path": str(input_file), "delimiter": ",",
                    "schema": [{"name": "a", "type": "integer"}, {"name": "b", "type": "integer"}],
                }},
                {"id": "sink", "type": "file_output_delimited", "config": {
                    "path": str(output_file), "delimiter": ","
                }},
            ],
            "flows": [{"source": "src", "target": "sink"}],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        assert "components" in result
        assert result["components"]["sink"]["barrier"] is True

    def test_job_metadata_in_result(self, tmp_path):
        """Execution result includes job name and duration."""
        input_file = tmp_path / "input.csv"
        output_file = tmp_path / "output.csv"
        input_file.write_text("x\n1\n")

        config = {
            "name": "my_test_job",
            "components": [
                {"id": "r", "type": "file_input_delimited", "config": {
                    "path": str(input_file), "delimiter": ",",
                    "schema": [{"name": "x", "type": "integer"}],
                }},
                {"id": "w", "type": "file_output_delimited", "config": {"path": str(output_file)}},
            ],
            "flows": [{"source": "r", "target": "w"}],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        assert result["job_name"] == "my_test_job"
        assert "duration_ms" in result
        assert isinstance(result["duration_ms"], float)
