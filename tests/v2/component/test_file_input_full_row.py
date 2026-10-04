"""Tests for FileInputFullRow V2 component."""

import pytest
import polars as pl
from pathlib import Path

from src.v2.components.file.file_input_full_row import FileInputFullRow
from src.v2.components.registry import REGISTRY


class TestFileInputFullRow:
    """Test FileInputFullRow component."""

    def test_basic_read(self, tmp_path):
        """Each line becomes a single string value."""
        f = tmp_path / "data.csv"
        f.write_text("id,name,city\n1,Alice,New York\n2,Bob,London\n")

        comp = FileInputFullRow("read", {
            "path": str(f),
            "schema": [{"name": "line", "type": "string"}],
        })

        result = comp.apply({})
        assert "main" in result
        df = result["main"].collect()
        assert len(df) == 3
        assert df.columns == ["line"]
        assert df["line"][0] == "id,name,city"
        assert df["line"][1] == "1,Alice,New York"
        assert df["line"][2] == "2,Bob,London"

    def test_header_rows_skip(self, tmp_path):
        """header_rows skips N rows at the start."""
        f = tmp_path / "data.csv"
        f.write_text("id,name,city\n1,Alice,New York\n2,Bob,London\n")

        comp = FileInputFullRow("read", {
            "path": str(f),
            "header_rows": 1,
            "schema": [{"name": "line", "type": "string"}],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 2
        assert df["line"][0] == "1,Alice,New York"

    def test_footer_rows_skip(self, tmp_path):
        """footer_rows skips N rows at the end."""
        f = tmp_path / "data.txt"
        f.write_text("header\nrow1\nrow2\nrow3\ntrailer\n")

        comp = FileInputFullRow("read", {
            "path": str(f),
            "header_rows": 1,
            "footer_rows": 1,
            "schema": [{"name": "line", "type": "string"}],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 3
        assert df["line"][0] == "row1"
        assert df["line"][2] == "row3"

    def test_limit(self, tmp_path):
        """limit restricts number of rows returned."""
        f = tmp_path / "data.txt"
        f.write_text("line1\nline2\nline3\nline4\nline5\n")

        comp = FileInputFullRow("read", {
            "path": str(f),
            "limit": 2,
            "schema": [{"name": "line", "type": "string"}],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 2
        assert df["line"][0] == "line1"

    def test_skip_empty_rows(self, tmp_path):
        """skip_empty_rows filters out blank lines."""
        f = tmp_path / "data.txt"
        f.write_text("line1\n\nline2\n\n\nline3\n")

        comp = FileInputFullRow("read", {
            "path": str(f),
            "skip_empty_rows": True,
            "schema": [{"name": "line", "type": "string"}],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 3
        assert df["line"].to_list() == ["line1", "line2", "line3"]

    def test_custom_column_name(self, tmp_path):
        """Column name comes from user's schema, not hardcoded."""
        f = tmp_path / "data.txt"
        f.write_text("hello\nworld\n")

        comp = FileInputFullRow("read", {
            "path": str(f),
            "schema": [{"name": "raw_data", "type": "string"}],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert df.columns == ["raw_data"]
        assert df["raw_data"][0] == "hello"

    def test_context_var_in_path(self, tmp_path):
        """${context.var} substitution works in path."""
        f = tmp_path / "data.txt"
        f.write_text("hello\n")

        comp = FileInputFullRow("read", {
            "path": "${context.dir}/data.txt",
            "schema": [{"name": "line", "type": "string"}],
        }, context={"dir": str(tmp_path)})

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 1

    def test_returns_lazy_frame(self, tmp_path):
        """Output should be a LazyFrame."""
        f = tmp_path / "data.txt"
        f.write_text("hello\n")

        comp = FileInputFullRow("read", {
            "path": str(f),
            "schema": [{"name": "line", "type": "string"}],
        })

        result = comp.apply({})
        assert isinstance(result["main"], pl.LazyFrame)

    def test_preserves_delimiters_in_line(self, tmp_path):
        """Commas, tabs, pipes etc. are preserved in the line string."""
        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n1,2,3\n")

        comp = FileInputFullRow("read", {
            "path": str(f),
            "schema": [{"name": "line", "type": "string"}],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert df["line"][0] == "a,b,c"
        assert df["line"][1] == "1,2,3"

    def test_empty_file(self, tmp_path):
        """Empty file produces zero rows."""
        f = tmp_path / "empty.txt"
        f.write_text("")

        comp = FileInputFullRow("read", {
            "path": str(f),
            "schema": [{"name": "line", "type": "string"}],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 0


class TestFileInputFullRowValidation:
    """Test validation logic."""

    def test_missing_path(self):
        comp = FileInputFullRow("read", {
            "schema": [{"name": "line", "type": "string"}],
        })
        errors = comp.validate()
        assert any("path" in e.lower() for e in errors)

    def test_missing_schema(self):
        comp = FileInputFullRow("read", {"path": "/tmp/test.txt"})
        errors = comp.validate()
        assert any("schema" in e.lower() for e in errors)

    def test_schema_must_have_one_column(self):
        comp = FileInputFullRow("read", {
            "path": "/tmp/test.txt",
            "schema": [
                {"name": "col1", "type": "string"},
                {"name": "col2", "type": "string"},
            ],
        })
        errors = comp.validate()
        assert any("single" in e.lower() or "one" in e.lower() or "1" in e for e in errors)

    def test_schema_must_be_string_type(self):
        comp = FileInputFullRow("read", {
            "path": "/tmp/test.txt",
            "schema": [{"name": "line", "type": "integer"}],
        })
        errors = comp.validate()
        assert any("string" in e.lower() for e in errors)

    def test_valid_config_no_errors(self, tmp_path):
        comp = FileInputFullRow("read", {
            "path": str(tmp_path / "test.txt"),
            "schema": [{"name": "line", "type": "string"}],
        })
        errors = comp.validate()
        assert errors == []


class TestFileInputFullRowRegistry:
    """Test component registration."""

    def test_registered_as_file_input_full_row(self):
        cls = REGISTRY.get("file_input_full_row")
        assert cls is FileInputFullRow

    def test_registered_as_file_input_full(self):
        cls = REGISTRY.get("file_input_full")
        assert cls is FileInputFullRow
