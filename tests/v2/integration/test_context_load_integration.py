"""Integration tests for context_load component with the engine."""
import pytest
import polars as pl
from src.v2.engine import PyETLEngine


class TestContextLoadEngineIntegration:
    def test_context_load_updates_downstream(self, tmp_path):
        """Context loaded by context_load should be available to downstream components."""
        ctx_file = tmp_path / "ctx.properties"
        ctx_file.write_text("greeting=hello\n")

        data_file = tmp_path / "data.csv"
        data_file.write_text("id,name\n1,Alice\n2,Bob\n")

        output_file = tmp_path / "output.csv"

        config = {
            "name": "test_context_load",
            "version": "2.0",
            "context": {},
            "components": [
                {"id": "load_ctx", "type": "context_load", "config": {"path": str(ctx_file)}},
                {"id": "read_data", "type": "file_input_delimited", "config": {
                    "path": str(data_file), "delimiter": ",",
                    "schema": [{"name": "id", "type": "int"}, {"name": "name", "type": "str"}],
                }},
                {"id": "write_output", "type": "file_output_delimited", "config": {"path": str(output_file), "delimiter": ","}},
            ],
            "flows": [
                {"source": "load_ctx", "target": "read_data", "name": "trigger"},
                {"source": "read_data", "target": "write_output", "name": "data"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()
        assert result is not None
        assert output_file.exists()

    def test_context_load_values_in_expressions(self, tmp_path):
        """Loaded context values should be usable in downstream expressions."""
        ctx_file = tmp_path / "ctx.properties"
        ctx_file.write_text("multiplier=10\n")

        data_file = tmp_path / "data.csv"
        data_file.write_text("id,amount\n1,100\n2,200\n")

        output_file = tmp_path / "output.csv"

        config = {
            "name": "test_ctx_expr",
            "version": "2.0",
            "context": {"multiplier": {"value": 1, "type": "int"}},
            "components": [
                {"id": "load_ctx", "type": "context_load", "config": {"path": str(ctx_file)}},
                {"id": "read_data", "type": "file_input_delimited", "config": {
                    "path": str(data_file), "delimiter": ",",
                    "schema": [{"name": "id", "type": "int"}, {"name": "amount", "type": "int"}],
                }},
                {"id": "transform", "type": "map", "config": {
                    "outputs": [{"name": "main", "columns": [
                        {"name": "id", "expression": "id"},
                        {"name": "total", "expression": "amount * context.multiplier"},
                    ]}],
                }},
                {"id": "write_output", "type": "file_output_delimited", "config": {"path": str(output_file), "delimiter": ","}},
            ],
            "flows": [
                {"source": "load_ctx", "target": "read_data", "name": "trigger"},
                {"source": "read_data", "target": "transform", "name": "data"},
                {"source": "transform", "target": "write_output", "name": "result"},
            ],
        }

        engine = PyETLEngine(config)
        engine.execute()

        output = pl.read_csv(output_file)
        assert output["total"].to_list() == [1000, 2000]

    def test_multiple_context_loads(self, tmp_path):
        """Multiple context_load components should chain correctly."""
        ctx1 = tmp_path / "db.properties"
        ctx1.write_text("host=localhost\n")
        ctx2 = tmp_path / "app.properties"
        ctx2.write_text("port=8080\n")

        data_file = tmp_path / "data.csv"
        data_file.write_text("id\n1\n")
        output_file = tmp_path / "output.csv"

        config = {
            "name": "test_multi_ctx",
            "version": "2.0",
            "context": {},
            "components": [
                {"id": "load_db", "type": "context_load", "config": {"path": str(ctx1)}},
                {"id": "load_app", "type": "context_load", "config": {"path": str(ctx2)}},
                {"id": "read_data", "type": "file_input_delimited", "config": {
                    "path": str(data_file), "delimiter": ",",
                    "schema": [{"name": "id", "type": "int"}],
                }},
                {"id": "write_output", "type": "file_output_delimited", "config": {"path": str(output_file), "delimiter": ","}},
            ],
            "flows": [
                {"source": "load_db", "target": "load_app", "name": "chain"},
                {"source": "load_app", "target": "read_data", "name": "trigger"},
                {"source": "read_data", "target": "write_output", "name": "data"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()
        assert result is not None
