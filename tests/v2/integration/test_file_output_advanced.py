"""Integration tests for FileOutputDelimited advanced features."""
import polars as pl

from v2 import PyETLEngine


class TestAppendWithQuoting:
    """End-to-end pipeline: file_input -> file_output with append and quoting."""

    def test_append_with_always_quoting(self, tmp_path):
        """Write initial file, then append with quote_style='always'."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create input CSV
        input_file = input_dir / "data.csv"
        input_file.write_text("id,name\n1,Alice\n2,Bob\n")
        output_file = output_dir / "result.csv"

        # Pipeline config for initial write
        config = {
            "name": "test_append_quoting",
            "version": "2.0",
            "components": [
                {
                    "id": "source",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_file),
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "name", "type": "string"},
                        ],
                    },
                },
                {
                    "id": "sink",
                    "type": "file_output_delimited",
                    "config": {
                        "path": str(output_file),
                        "quote_style": "always",
                        "line_terminator": "\r\n",
                    },
                },
            ],
            "flows": [{"source": "source", "target": "sink"}],
        }

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        # read_bytes to preserve CRLF (read_text normalises \r\n -> \n)
        raw = output_file.read_bytes().decode("utf-8")
        # Should have quotes around all fields and CRLF line endings
        lines = raw.split("\r\n")
        assert lines[0] == '"id","name"'
        assert '"1","Alice"' in raw
        assert '"2","Bob"' in raw

        # Now append more data
        input_file.write_text("id,name\n3,Charlie\n")
        config["components"][1]["config"]["append"] = True
        result2 = PyETLEngine(config).execute()
        assert result2["status"] == "success"

        raw2 = output_file.read_bytes().decode("utf-8")
        # Original data should still be there
        assert '"1","Alice"' in raw2
        assert '"2","Bob"' in raw2
        # New data should be appended
        assert '"3","Charlie"' in raw2


class TestSchemaColumnOrdering:
    """End-to-end pipeline: file_input -> file_output with schema column selection."""

    def test_schema_selects_and_reorders_columns(self, tmp_path):
        """Schema should select subset and reorder columns."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        input_file = input_dir / "data.csv"
        input_file.write_text("id,name,city,age\n1,Alice,NYC,30\n2,Bob,LA,25\n")
        output_file = output_dir / "result.csv"

        config = {
            "name": "test_schema_ordering",
            "version": "2.0",
            "components": [
                {
                    "id": "source",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_file),
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "name", "type": "string"},
                            {"name": "city", "type": "string"},
                            {"name": "age", "type": "integer"},
                        ],
                    },
                },
                {
                    "id": "sink",
                    "type": "file_output_delimited",
                    "config": {
                        "path": str(output_file),
                        "schema": [
                            {"name": "city", "type": "string"},
                            {"name": "name", "type": "string"},
                        ],
                    },
                },
            ],
            "flows": [{"source": "source", "target": "sink"}],
        }

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        content = output_file.read_text()
        lines = content.strip().split("\n")
        assert lines[0] == "city,name"
        assert lines[1] == "NYC,Alice"
        assert lines[2] == "LA,Bob"
