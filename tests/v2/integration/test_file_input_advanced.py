"""Integration tests for FileInputDelimited advanced features."""
import pytest
import polars as pl
from pathlib import Path

from v2 import PyETLEngine


@pytest.fixture
def data_dir(tmp_path):
    """Create input/output dirs with test data."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return tmp_path


class TestQuotedCsvPipeline:
    """End-to-end pipeline with quoted CSV input."""

    def test_quoted_csv_through_map_to_sink(self, data_dir):
        """Quoted CSV fields should survive through Map and into output."""
        input_file = data_dir / "input" / "quoted.csv"
        input_file.write_text(
            'id,name,address\n'
            '1,Alice,"123 Main St, Apt 4"\n'
            '2,Bob,"456 Oak Ave"\n'
            '3,Charlie,"789 Pine Rd, Suite 100"\n'
        )
        output_file = data_dir / "output" / "result.csv"

        config = {
            "name": "quoted_csv_test",
            "version": "2.0",
            "components": [
                {
                    "id": "source",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_file),
                        "quote_char": '"',
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "name", "type": "string"},
                            {"name": "address", "type": "string"},
                        ],
                    },
                },
                {
                    "id": "transform",
                    "type": "map",
                    "config": {
                        "outputs": [
                            {
                                "name": "main",
                                "columns": [
                                    {"name": "id", "expression": "id"},
                                    {"name": "name", "expression": "UPPER(name)"},
                                    {"name": "address", "expression": "address"},
                                ],
                            }
                        ],
                    },
                },
                {
                    "id": "sink",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "source", "target": "transform"},
                {"source": "transform", "target": "sink"},
            ],
        }

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_csv(output_file)
        assert len(df) == 3
        assert df["name"][0] == "ALICE"
        assert df["address"][0] == "123 Main St, Apt 4"


class TestFooterLimitPipeline:
    """End-to-end pipeline with footer and limit."""

    def test_footer_and_limit_pipeline(self, data_dir):
        """Footer rows removed, limit applied, correct output."""
        input_file = data_dir / "input" / "data.csv"
        input_file.write_text(
            "id,name,amount\n"
            "1,Alice,100\n"
            "2,Bob,200\n"
            "3,Charlie,300\n"
            "4,Diana,400\n"
            "5,Eve,500\n"
            "TOTAL,,1500\n"
            "END,,\n"
        )
        output_file = data_dir / "output" / "result.csv"

        config = {
            "name": "footer_limit_test",
            "version": "2.0",
            "components": [
                {
                    "id": "source",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_file),
                        "footer_rows": 2,
                        "limit": 3,
                        "schema": [
                            {"name": "id", "type": "string"},
                            {"name": "name", "type": "string"},
                            {"name": "amount", "type": "string"},
                        ],
                    },
                },
                {
                    "id": "sink",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [{"source": "source", "target": "sink"}],
        }

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_csv(output_file)
        assert len(df) == 3
        assert df["name"].to_list() == ["Alice", "Bob", "Charlie"]


class TestTrimPipeline:
    """End-to-end pipeline with trim_all."""

    def test_trim_through_filter(self, data_dir):
        """Trimmed values should work with downstream filter."""
        input_file = data_dir / "input" / "padded.csv"
        input_file.write_text(
            "id,status\n"
            "1, ACTIVE \n"
            "2, INACTIVE \n"
            "3, ACTIVE \n"
        )
        output_file = data_dir / "output" / "result.csv"

        config = {
            "name": "trim_test",
            "version": "2.0",
            "components": [
                {
                    "id": "source",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_file),
                        "trim_all": True,
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "status", "type": "string"},
                        ],
                    },
                },
                {
                    "id": "filter",
                    "type": "filter",
                    "config": {"condition": "status == 'ACTIVE'"},
                },
                {
                    "id": "sink",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "source", "target": "filter"},
                {"source": "filter", "target": "sink"},
            ],
        }

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_csv(output_file)
        assert len(df) == 2
