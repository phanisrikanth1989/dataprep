"""
Component tests for v2 File I/O components.

Tests the rewritten file components that use the new V2 base classes
(SourceComponent/SinkComponent) and register with REGISTRY.
"""
import pytest
import polars as pl
from pathlib import Path
from datetime import date, datetime

from src.v2.components.file import (
    FileInputDelimited,
    FileOutputDelimited,
    FileInputExcel,
    FileOutputParquet,
)
from src.v2.components.registry import REGISTRY


# -----------------------------------------------------------------------
# FileInputDelimited Tests
# -----------------------------------------------------------------------
class TestFileInputDelimited:
    """Test FileInputDelimited component."""

    def test_basic_csv_read(self, tmp_path):
        """Test basic CSV reading with explicit schema."""
        csv = tmp_path / "test.csv"
        csv.write_text("id,name,amount\n1,Alice,100.5\n2,Bob,200.0\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "delimiter": ",",
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
                {"name": "amount", "type": "float"},
            ],
        })

        result = comp.apply({})
        assert "main" in result
        assert isinstance(result["main"], pl.LazyFrame)
        df = result["main"].collect()
        assert len(df) == 2
        assert df["id"].dtype == pl.Int64
        assert df["name"][0] == "Alice"

    def test_context_var_in_path(self, tmp_path):
        """Test ${context.var} substitution in path."""
        csv = tmp_path / "test.csv"
        csv.write_text("a\n1\n")

        comp = FileInputDelimited("read", {
            "path": "${context.dir}/test.csv",
            "delimiter": ",",
            "schema": [{"name": "a", "type": "string"}],
        }, context={"dir": str(tmp_path)})

        result = comp.apply({})
        assert result["main"].collect().shape[0] == 1

    def test_no_header(self, tmp_path):
        """Test reading file with no header row."""
        csv = tmp_path / "test.csv"
        csv.write_text("1,Alice\n2,Bob\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "delimiter": ",",
            "has_header": False,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 2
        assert "id" in df.columns
        assert "name" in df.columns

    def test_tsv_delimiter(self, tmp_path):
        """Test tab-separated file reading."""
        tsv = tmp_path / "test.tsv"
        tsv.write_text("id\tname\n1\tAlice\n2\tBob\n")

        comp = FileInputDelimited("read", {
            "path": str(tsv),
            "delimiter": "\t",
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 2
        assert df["name"][0] == "Alice"

    def test_schema_type_mapping(self, tmp_path):
        """Test all major type mappings work."""
        csv = tmp_path / "types.csv"
        csv.write_text("s,i,f,b\nhello,42,3.14,true\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "delimiter": ",",
            "schema": [
                {"name": "s", "type": "string"},
                {"name": "i", "type": "integer"},
                {"name": "f", "type": "float"},
                {"name": "b", "type": "boolean"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert df["s"].dtype == pl.Utf8
        assert df["i"].dtype == pl.Int64
        assert df["f"].dtype == pl.Float64
        assert df["b"].dtype == pl.Boolean

    def test_produce_returns_lazy(self, tmp_path):
        """Test that produce() returns LazyFrame (not DataFrame)."""
        csv = tmp_path / "test.csv"
        csv.write_text("id\n1\n2\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "delimiter": ",",
            "schema": [{"name": "id", "type": "integer"}],
        })

        result = comp.produce()
        assert "main" in result
        assert isinstance(result["main"], pl.LazyFrame)

    def test_registry_registration(self):
        """Test that FileInputDelimited is registered under canonical name only."""
        assert REGISTRY.get("file_input_delimited") is FileInputDelimited
        # Old aliases removed per D-32/D-33
        assert REGISTRY.get("file_input") is None
        assert REGISTRY.get("file_input_csv") is None

    def test_validate_missing_path(self):
        """Test validation catches missing path."""
        comp = FileInputDelimited("read", {"delimiter": ","})
        errors = comp.validate()
        assert any("path" in e for e in errors)

    def test_skip_rows(self, tmp_path):
        """Test skip_rows parameter."""
        csv = tmp_path / "test.csv"
        # First row is a comment, then header, then data
        csv.write_text("# comment line\nid,name\n1,Alice\n2,Bob\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "delimiter": ",",
            "skip_rows": 1,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 2

    def test_schema_names_override_header(self, tmp_path):
        """Schema column names take priority over file header names."""
        csv = tmp_path / "test.csv"
        csv.write_text("customer_id,customer_name,total_amount\n1,Alice,100.5\n2,Bob,200.0\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
                {"name": "amount", "type": "float"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert df.columns == ["id", "name", "amount"]
        assert df["id"][0] == 1
        assert df["name"][0] == "Alice"
        assert df["amount"][0] == 100.5

    def test_validate_missing_schema(self):
        """Missing schema should produce a validation error."""
        comp = FileInputDelimited("read", {"path": "/tmp/test.csv"})
        errors = comp.validate()
        assert any("schema" in e.lower() for e in errors)

    def test_validate_empty_schema(self):
        """Empty schema list should produce a validation error."""
        comp = FileInputDelimited("read", {"path": "/tmp/test.csv", "schema": []})
        errors = comp.validate()
        assert any("schema" in e.lower() for e in errors)


# -----------------------------------------------------------------------
# FileOutputDelimited Tests
# -----------------------------------------------------------------------
class TestFileOutputDelimited:
    """Test FileOutputDelimited component."""

    def test_basic_csv_write(self, tmp_path):
        """Test basic CSV writing."""
        out = tmp_path / "output.csv"

        comp = FileOutputDelimited("write", {
            "path": str(out),
            "delimiter": ",",
        })

        df = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}).lazy()
        comp.apply({"main": df})

        assert out.exists()
        result = pl.read_csv(out)
        assert len(result) == 2
        assert result["name"][0] == "Alice"

    def test_is_barrier(self):
        """Test that FileOutputDelimited is a barrier component."""
        comp = FileOutputDelimited("write", {"path": "/tmp/test.csv"})
        assert comp.is_barrier is True

    def test_write_from_dataframe(self, tmp_path):
        """Test writing from a regular DataFrame (not lazy)."""
        out = tmp_path / "output.csv"

        comp = FileOutputDelimited("write", {"path": str(out)})

        df = pl.DataFrame({"id": [1, 2], "value": [100, 200]})
        comp.consume({"main": df})

        assert out.exists()
        result = pl.read_csv(out)
        assert len(result) == 2

    def test_creates_parent_dirs(self, tmp_path):
        """Test that parent directories are created automatically."""
        out = tmp_path / "subdir" / "nested" / "output.csv"

        comp = FileOutputDelimited("write", {"path": str(out)})

        df = pl.DataFrame({"id": [1]}).lazy()
        comp.apply({"main": df})

        assert out.exists()

    def test_custom_delimiter(self, tmp_path):
        """Test writing with tab delimiter."""
        out = tmp_path / "output.tsv"

        comp = FileOutputDelimited("write", {
            "path": str(out),
            "delimiter": "\t",
        })

        df = pl.DataFrame({"id": [1], "name": ["Alice"]}).lazy()
        comp.apply({"main": df})

        content = out.read_text()
        assert "\t" in content

    def test_apply_returns_empty_dict(self, tmp_path):
        """Test that apply() returns empty dict (sink pattern)."""
        out = tmp_path / "output.csv"

        comp = FileOutputDelimited("write", {"path": str(out)})

        df = pl.DataFrame({"id": [1]}).lazy()
        result = comp.apply({"main": df})
        assert result == {}

    def test_no_input_is_noop(self, tmp_path):
        """Test that missing 'main' input is a no-op."""
        out = tmp_path / "output.csv"

        comp = FileOutputDelimited("write", {"path": str(out)})
        comp.consume({})

        assert not out.exists()

    def test_registry_registration(self):
        """Test that FileOutputDelimited is registered under canonical name only."""
        assert REGISTRY.get("file_output_delimited") is FileOutputDelimited
        assert REGISTRY.get("file_output") is None
        assert REGISTRY.get("file_output_csv") is None

    def test_validate_missing_path(self):
        """Test validation catches missing path."""
        comp = FileOutputDelimited("write", {})
        errors = comp.validate()
        assert any("path" in e for e in errors)

    def test_context_var_in_path(self, tmp_path):
        """Test ${context.var} substitution in output path."""
        comp = FileOutputDelimited("write", {
            "path": "${context.outdir}/result.csv",
        }, context={"outdir": str(tmp_path)})

        df = pl.DataFrame({"id": [1]}).lazy()
        comp.apply({"main": df})

        assert (tmp_path / "result.csv").exists()

    def test_append_suppresses_header(self, tmp_path):
        """Test that appending to existing file suppresses header."""
        out = tmp_path / "output.csv"

        # First write
        comp1 = FileOutputDelimited("write", {
            "path": str(out),
            "append": True,
            "has_header": True,
        })
        df1 = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}).lazy()
        comp1.apply({"main": df1})

        # Second write (append)
        comp2 = FileOutputDelimited("write", {
            "path": str(out),
            "append": True,
            "has_header": True,
        })
        df2 = pl.DataFrame({"id": [3], "name": ["Charlie"]}).lazy()
        comp2.apply({"main": df2})

        content = out.read_text()
        lines = [l for l in content.strip().split("\n") if l]
        # Header + 2 rows from first + 1 row from second = 4 lines
        assert len(lines) == 4
        assert lines[0] == "id,name"  # Header only once
        assert "Charlie" in content

    def test_append_creates_new_file_with_header(self, tmp_path):
        """Test that append to non-existent file creates it with header."""
        out = tmp_path / "output.csv"
        assert not out.exists()

        comp = FileOutputDelimited("write", {
            "path": str(out),
            "append": True,
            "has_header": True,
        })
        df = pl.DataFrame({"id": [1]}).lazy()
        comp.apply({"main": df})

        content = out.read_text()
        assert content.startswith("id\n")

    def test_append_no_header(self, tmp_path):
        """Test append with has_header=false never writes header."""
        out = tmp_path / "output.csv"

        comp = FileOutputDelimited("write", {
            "path": str(out),
            "append": True,
            "has_header": False,
        })
        df = pl.DataFrame({"id": [1, 2]}).lazy()
        comp.apply({"main": df})
        comp.apply({"main": df})

        content = out.read_text()
        lines = [l for l in content.strip().split("\n") if l]
        # No header, just 4 data lines
        assert len(lines) == 4
        assert "id" not in lines[0]  # No header

    def test_delete_empty_file_skips_write(self, tmp_path):
        """Test delete_empty_file=true skips writing when 0 rows."""
        out = tmp_path / "output.csv"
        comp = FileOutputDelimited("write", {
            "path": str(out),
            "delete_empty_file": True,
        })
        df = pl.DataFrame({"id": pl.Series([], dtype=pl.Int64)}).lazy()
        comp.apply({"main": df})

        assert not out.exists()

    def test_delete_empty_file_false_writes_header_only(self, tmp_path):
        """Test delete_empty_file=false writes header-only file for 0 rows."""
        out = tmp_path / "output.csv"
        comp = FileOutputDelimited("write", {
            "path": str(out),
            "delete_empty_file": False,
            "has_header": True,
        })
        df = pl.DataFrame({"id": pl.Series([], dtype=pl.Int64)}).lazy()
        comp.apply({"main": df})

        assert out.exists()
        content = out.read_text().strip()
        assert content == "id"  # Header only

    def test_delete_empty_file_default_writes(self, tmp_path):
        """Test default behavior writes file even with 0 rows."""
        out = tmp_path / "output.csv"
        comp = FileOutputDelimited("write", {"path": str(out)})
        df = pl.DataFrame({"id": pl.Series([], dtype=pl.Int64)}).lazy()
        comp.apply({"main": df})

        assert out.exists()

    def test_error_if_exists_raises(self, tmp_path):
        """Test error_if_exists=true raises when file exists."""
        out = tmp_path / "output.csv"
        out.write_text("existing content")

        comp = FileOutputDelimited("write", {
            "path": str(out),
            "error_if_exists": True,
        })
        df = pl.DataFrame({"id": [1]}).lazy()

        with pytest.raises(FileExistsError):
            comp.apply({"main": df})

    def test_error_if_exists_ok_when_no_file(self, tmp_path):
        """Test error_if_exists=true works fine when file doesn't exist."""
        out = tmp_path / "output.csv"
        comp = FileOutputDelimited("write", {
            "path": str(out),
            "error_if_exists": True,
        })
        df = pl.DataFrame({"id": [1]}).lazy()
        comp.apply({"main": df})

        assert out.exists()

    def test_schema_selects_columns(self, tmp_path):
        """Test schema selects only named columns."""
        out = tmp_path / "output.csv"
        comp = FileOutputDelimited("write", {
            "path": str(out),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })
        # DataFrame has extra column 'extra' not in schema
        df = pl.DataFrame({
            "id": [1, 2],
            "name": ["Alice", "Bob"],
            "extra": [100, 200],
        }).lazy()
        comp.apply({"main": df})

        result = pl.read_csv(out)
        assert list(result.columns) == ["id", "name"]
        assert "extra" not in result.columns

    def test_schema_reorders_columns(self, tmp_path):
        """Test schema reorders columns to match schema order."""
        out = tmp_path / "output.csv"
        comp = FileOutputDelimited("write", {
            "path": str(out),
            "schema": [
                {"name": "name", "type": "string"},
                {"name": "id", "type": "integer"},
            ],
        })
        # DataFrame columns in different order
        df = pl.DataFrame({
            "id": [1],
            "name": ["Alice"],
        }).lazy()
        comp.apply({"main": df})

        result = pl.read_csv(out)
        assert list(result.columns) == ["name", "id"]

    def test_no_schema_writes_all_columns(self, tmp_path):
        """Test without schema, all columns are written as-is."""
        out = tmp_path / "output.csv"
        comp = FileOutputDelimited("write", {"path": str(out)})
        df = pl.DataFrame({"a": [1], "b": [2], "c": [3]}).lazy()
        comp.apply({"main": df})

        result = pl.read_csv(out)
        assert list(result.columns) == ["a", "b", "c"]

    def test_validate_quote_char_single_char(self):
        """Test validation rejects multi-character quote_char."""
        comp = FileOutputDelimited("write", {
            "path": "/tmp/test.csv",
            "quote_char": "ab",
        })
        errors = comp.validate()
        assert any("quote_char" in e for e in errors)

    def test_validate_quote_char_single_char_ok(self):
        """Test validation accepts single-character quote_char."""
        comp = FileOutputDelimited("write", {
            "path": "/tmp/test.csv",
            "quote_char": "'",
        })
        errors = comp.validate()
        assert not errors

    def test_validate_quote_style_invalid(self):
        """Test validation rejects invalid quote_style."""
        comp = FileOutputDelimited("write", {
            "path": "/tmp/test.csv",
            "quote_style": "invalid",
        })
        errors = comp.validate()
        assert any("quote_style" in e for e in errors)

    def test_validate_quote_style_valid(self):
        """Test validation accepts all valid quote_style values."""
        for style in ("necessary", "always", "never", "non_numeric"):
            comp = FileOutputDelimited("write", {
                "path": "/tmp/test.csv",
                "quote_style": style,
            })
            errors = comp.validate()
            assert not errors, f"quote_style '{style}' should be valid"

    def test_validate_append_and_error_if_exists_conflict(self):
        """Test validation rejects append=true + error_if_exists=true."""
        comp = FileOutputDelimited("write", {
            "path": "/tmp/test.csv",
            "append": True,
            "error_if_exists": True,
        })
        errors = comp.validate()
        assert any("append" in e.lower() or "error_if_exists" in e.lower() for e in errors)

    def test_validate_line_terminator_empty(self):
        """Test validation rejects empty line_terminator."""
        comp = FileOutputDelimited("write", {
            "path": "/tmp/test.csv",
            "line_terminator": "",
        })
        errors = comp.validate()
        assert any("line_terminator" in e for e in errors)

    def test_line_terminator_crlf(self, tmp_path):
        """Test writing with Windows-style line endings."""
        out = tmp_path / "output.csv"
        comp = FileOutputDelimited("write", {
            "path": str(out),
            "line_terminator": "\r\n",
        })
        df = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}).lazy()
        comp.apply({"main": df})

        raw = out.read_bytes()
        # Header + 2 data rows, each ending with \r\n
        assert raw.count(b"\r\n") >= 3

    def test_line_terminator_default_lf(self, tmp_path):
        """Test default line terminator is LF."""
        out = tmp_path / "output.csv"
        comp = FileOutputDelimited("write", {"path": str(out)})
        df = pl.DataFrame({"id": [1]}).lazy()
        comp.apply({"main": df})

        raw = out.read_bytes()
        assert b"\r\n" not in raw
        assert b"\n" in raw

    def test_quote_style_always(self, tmp_path):
        """Test quote_style='always' wraps all fields."""
        out = tmp_path / "output.csv"
        comp = FileOutputDelimited("write", {
            "path": str(out),
            "quote_style": "always",
        })
        df = pl.DataFrame({"id": [1], "name": ["Alice"]}).lazy()
        comp.apply({"main": df})

        content = out.read_text()
        assert '"id"' in content
        assert '"Alice"' in content
        assert '"1"' in content

    def test_quote_style_never(self, tmp_path):
        """Test quote_style='never' writes no quotes."""
        out = tmp_path / "output.csv"
        comp = FileOutputDelimited("write", {
            "path": str(out),
            "quote_style": "never",
        })
        df = pl.DataFrame({"id": [1], "name": ["Alice"]}).lazy()
        comp.apply({"main": df})

        content = out.read_text()
        assert '"' not in content

    def test_quote_char_custom(self, tmp_path):
        """Test custom quote character."""
        out = tmp_path / "output.csv"
        comp = FileOutputDelimited("write", {
            "path": str(out),
            "quote_char": "'",
            "quote_style": "always",
        })
        df = pl.DataFrame({"id": [1], "name": ["Alice"]}).lazy()
        comp.apply({"main": df})

        content = out.read_text()
        assert "'" in content
        assert '"' not in content


# -----------------------------------------------------------------------
# FileOutputParquet Tests
# -----------------------------------------------------------------------
class TestFileOutputParquet:
    """Test FileOutputParquet component."""

    def test_parquet_write(self, tmp_path):
        """Test basic Parquet writing."""
        out = tmp_path / "output.parquet"

        comp = FileOutputParquet("write", {"path": str(out)})

        df = pl.DataFrame({"id": [1, 2]}).lazy()
        comp.apply({"main": df})

        assert out.exists()
        result = pl.read_parquet(out)
        assert len(result) == 2

    def test_is_barrier(self):
        """Test that FileOutputParquet is a barrier component."""
        comp = FileOutputParquet("write", {"path": "/tmp/test.parquet"})
        assert comp.is_barrier is True

    def test_parquet_with_compression(self, tmp_path):
        """Test Parquet with explicit compression."""
        out = tmp_path / "output.parquet"

        comp = FileOutputParquet("write", {
            "path": str(out),
            "compression": "snappy",
        })

        df = pl.DataFrame({"id": list(range(100))}).lazy()
        comp.apply({"main": df})

        assert out.exists()
        result = pl.read_parquet(out)
        assert len(result) == 100

    def test_creates_parent_dirs(self, tmp_path):
        """Test that parent directories are created."""
        out = tmp_path / "deep" / "nested" / "output.parquet"

        comp = FileOutputParquet("write", {"path": str(out)})

        df = pl.DataFrame({"id": [1]}).lazy()
        comp.apply({"main": df})

        assert out.exists()

    def test_registry_registration(self):
        """Test that FileOutputParquet is registered."""
        assert REGISTRY.get("file_output_parquet") is FileOutputParquet

    def test_validate_missing_path(self):
        """Test validation catches missing path."""
        comp = FileOutputParquet("write", {})
        errors = comp.validate()
        assert any("path" in e for e in errors)

    def test_validate_invalid_compression(self):
        """Test validation catches invalid compression."""
        comp = FileOutputParquet("write", {
            "path": "/tmp/test.parquet",
            "compression": "invalid",
        })
        errors = comp.validate()
        assert any("compression" in e for e in errors)


# -----------------------------------------------------------------------
# FileInputExcel Tests
# -----------------------------------------------------------------------
class TestFileInputExcel:
    """Test FileInputExcel component."""

    def test_registry_registration(self):
        """Test that FileInputExcel is registered."""
        assert REGISTRY.get("file_input_excel") is FileInputExcel

    def test_validate_missing_path(self):
        """Test validation catches missing path."""
        comp = FileInputExcel("read", {})
        errors = comp.validate()
        assert any("path" in e for e in errors)

    def test_produce_returns_lazyframe(self, tmp_path):
        """Test that produce() returns a LazyFrame for Excel.

        This test requires openpyxl and xlsxwriter. Skip if not available.
        """
        pytest.importorskip("openpyxl")
        pytest.importorskip("xlsxwriter")

        # Create an Excel file using Polars
        xlsx = tmp_path / "test.xlsx"
        df = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
        df.write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        assert "main" in result
        assert isinstance(result["main"], pl.LazyFrame)
        collected = result["main"].collect()
        assert len(collected) == 2

    def test_date_missing_pattern_fails_validation(self):
        """Date column without date_pattern should fail validation."""
        comp = FileInputExcel("read", {
            "path": "/tmp/dummy.xlsx",
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "order_date", "type": "date"},
            ],
        })
        errors = comp.validate()
        assert any("date_pattern" in e for e in errors)

    def test_validate_missing_schema(self):
        """Validation fails when schema is not provided."""
        comp = FileInputExcel("read", {"path": "/tmp/dummy.xlsx"})
        errors = comp.validate()
        assert any("schema" in e.lower() for e in errors)

    def test_validate_empty_schema(self):
        """Validation fails when schema is an empty list."""
        comp = FileInputExcel("read", {"path": "/tmp/dummy.xlsx", "schema": []})
        errors = comp.validate()
        assert any("schema" in e.lower() for e in errors)

    def test_validate_negative_footer_rows(self):
        """Validation fails when footer_rows is negative."""
        comp = FileInputExcel("read", {
            "path": "/tmp/dummy.xlsx",
            "schema": [{"name": "id", "type": "integer"}],
            "footer_rows": -1,
        })
        errors = comp.validate()
        assert any("footer_rows" in e for e in errors)

    def test_validate_negative_limit(self):
        """Validation fails when limit is negative."""
        comp = FileInputExcel("read", {
            "path": "/tmp/dummy.xlsx",
            "schema": [{"name": "id", "type": "integer"}],
            "limit": -5,
        })
        errors = comp.validate()
        assert any("limit" in e for e in errors)

    def test_validate_first_column_zero(self):
        """Validation fails when first_column is 0 (must be >= 1)."""
        comp = FileInputExcel("read", {
            "path": "/tmp/dummy.xlsx",
            "schema": [{"name": "id", "type": "integer"}],
            "first_column": 0,
        })
        errors = comp.validate()
        assert any("first_column" in e for e in errors)

    def test_validate_last_column_less_than_first(self):
        """Validation fails when last_column < first_column."""
        comp = FileInputExcel("read", {
            "path": "/tmp/dummy.xlsx",
            "schema": [{"name": "id", "type": "integer"}],
            "first_column": 3,
            "last_column": 1,
        })
        errors = comp.validate()
        assert any("last_column" in e for e in errors)

    def test_validate_conflicting_sheet_config(self):
        """Validation fails when both sheet and sheets are specified."""
        comp = FileInputExcel("read", {
            "path": "/tmp/dummy.xlsx",
            "schema": [{"name": "id", "type": "integer"}],
            "sheet": "Sheet1",
            "sheets": [{"name": "Sheet2"}],
        })
        errors = comp.validate()
        assert any("sheet" in e.lower() and "sheets" in e.lower() for e in errors)

    def test_validate_conflicting_all_sheets_and_sheet(self):
        """Validation fails when both sheet and all_sheets are specified."""
        comp = FileInputExcel("read", {
            "path": "/tmp/dummy.xlsx",
            "schema": [{"name": "id", "type": "integer"}],
            "sheet": "Sheet1",
            "all_sheets": True,
        })
        errors = comp.validate()
        assert any("all_sheets" in e for e in errors)

    def test_validate_conflicting_all_sheets_and_sheets(self):
        """Validation fails when both sheets and all_sheets are specified."""
        comp = FileInputExcel("read", {
            "path": "/tmp/dummy.xlsx",
            "schema": [{"name": "id", "type": "integer"}],
            "sheets": [{"name": "Sheet1"}],
            "all_sheets": True,
        })
        errors = comp.validate()
        assert any("Cannot specify both" in e for e in errors)

    def test_validate_last_column_zero(self):
        """last_column=0 should produce validation error (1-based)."""
        comp = FileInputExcel("read", {
            "path": "/tmp/dummy.xlsx",
            "schema": [{"name": "a", "type": "string"}],
            "last_column": 0,
        })
        errors = comp.validate()
        assert any("last_column" in e for e in errors)

    def test_validate_sheets_entry_missing_name_and_index(self):
        """Validation fails when a sheets entry has neither name nor index."""
        comp = FileInputExcel("read", {
            "path": "/tmp/dummy.xlsx",
            "schema": [{"name": "id", "type": "integer"}],
            "sheets": [{"name": "Sheet1"}, {}],
        })
        errors = comp.validate()
        assert any("Sheet entry" in e for e in errors)

    def test_validate_invalid_regex(self):
        """Invalid regex in sheets config is caught at validation time."""
        comp = FileInputExcel("read", {
            "path": "/tmp/dummy.xlsx",
            "schema": [{"name": "id", "type": "integer"}],
            "sheets": [{"name": "[invalid(", "regex": True}],
        })
        errors = comp.validate()
        assert any("invalid regex" in e.lower() for e in errors)

    def test_validate_valid_regex(self):
        """Valid regex in sheets config passes validation."""
        comp = FileInputExcel("read", {
            "path": "/tmp/dummy.xlsx",
            "schema": [{"name": "id", "type": "integer"}],
            "sheets": [{"name": "Sheet\\d+", "regex": True}],
        })
        errors = comp.validate()
        assert not any("regex" in e.lower() for e in errors)

    def test_schema_more_columns_than_file(self, tmp_path):
        """Schema with more columns than file raises ValueError."""
        pytest.importorskip("openpyxl")
        pytest.importorskip("xlsxwriter")
        xlsx = tmp_path / "few_cols.xlsx"
        pl.DataFrame({"a": [1], "b": [2], "c": [3]}).write_excel(xlsx)
        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "schema": [
                {"name": "a", "type": "integer"},
                {"name": "b", "type": "integer"},
                {"name": "c", "type": "integer"},
                {"name": "d", "type": "integer"},
                {"name": "e", "type": "integer"},
            ],
        })
        with pytest.raises(ValueError, match="schema defines 5 columns but data only has 3"):
            comp.produce()

    def test_schema_exact_columns(self, tmp_path):
        """Schema with same column count as file works correctly."""
        pytest.importorskip("openpyxl")
        pytest.importorskip("xlsxwriter")
        xlsx = tmp_path / "exact_cols.xlsx"
        pl.DataFrame({"a": [1], "b": [2]}).write_excel(xlsx)
        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "schema": [
                {"name": "col_a", "type": "integer"},
                {"name": "col_b", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        assert df.columns == ["col_a", "col_b"]
        assert df["col_a"][0] == 1


# -----------------------------------------------------------------------
# FileInputExcel Footer Tests
# -----------------------------------------------------------------------
class TestFileInputExcelFooter:
    """Test footer row skipping for Excel files."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_excel(self):
        pytest.importorskip("openpyxl")
        pytest.importorskip("xlsxwriter")

    def test_footer_removes_last_rows(self, tmp_path):
        """footer_rows=2 on 5-row file should return 3 rows."""
        xlsx = tmp_path / "footer.xlsx"
        pl.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "TOTAL", "END"],
        }).write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "footer_rows": 2,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        df = result["main"].collect()
        assert len(df) == 3
        assert df["name"].to_list() == ["Alice", "Bob", "Charlie"]

    def test_footer_greater_than_rows_returns_empty(self, tmp_path):
        """footer_rows=10 on 2-row file should return 0 rows."""
        xlsx = tmp_path / "tiny.xlsx"
        pl.DataFrame({
            "id": [1, 2],
            "name": ["Alice", "Bob"],
        }).write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "footer_rows": 10,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        df = result["main"].collect()
        assert len(df) == 0

    def test_footer_zero_is_noop(self, tmp_path):
        """footer_rows=0 should return all rows."""
        xlsx = tmp_path / "all.xlsx"
        pl.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
        }).write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "footer_rows": 0,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        df = result["main"].collect()
        assert len(df) == 3


# -----------------------------------------------------------------------
# FileInputExcel Limit Tests
# -----------------------------------------------------------------------
class TestFileInputExcelLimit:
    """Test row limit for Excel files."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_excel(self):
        pytest.importorskip("openpyxl")
        pytest.importorskip("xlsxwriter")

    def test_limit_restricts_rows(self, tmp_path):
        """limit=3 on 5-row file should return first 3 rows."""
        xlsx = tmp_path / "data.xlsx"
        pl.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
        }).write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "limit": 3,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        df = result["main"].collect()
        assert len(df) == 3
        assert df["name"].to_list() == ["Alice", "Bob", "Charlie"]

    def test_limit_zero_returns_empty(self, tmp_path):
        """limit=0 should return 0 rows (Talend behavior)."""
        xlsx = tmp_path / "data.xlsx"
        pl.DataFrame({
            "id": [1, 2],
            "name": ["Alice", "Bob"],
        }).write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "limit": 0,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        df = result["main"].collect()
        assert len(df) == 0

    def test_limit_greater_than_rows_returns_all(self, tmp_path):
        """limit=100 on 2-row file should return all 2 rows."""
        xlsx = tmp_path / "small.xlsx"
        pl.DataFrame({
            "id": [1, 2],
            "name": ["Alice", "Bob"],
        }).write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "limit": 100,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        df = result["main"].collect()
        assert len(df) == 2

    def test_footer_and_limit_combined(self, tmp_path):
        """footer_rows=1, limit=2 on 5-row file: footer first (4 rows), then limit (2 rows)."""
        xlsx = tmp_path / "combo.xlsx"
        pl.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Diana", "FOOTER"],
        }).write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "footer_rows": 1,
            "limit": 2,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        df = result["main"].collect()
        assert len(df) == 2
        assert df["name"].to_list() == ["Alice", "Bob"]


# -----------------------------------------------------------------------
# FileInputExcel Skip Empty Rows Tests
# -----------------------------------------------------------------------
class TestFileInputExcelSkipEmpty:
    """Test skip_empty_rows for Excel files."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_excel(self):
        pytest.importorskip("openpyxl")
        pytest.importorskip("xlsxwriter")

    def test_skip_empty_rows_removes_all_null(self, tmp_path):
        """Rows where all fields are null/whitespace-only should be removed.

        Excel drops truly null rows on write, so we use whitespace-only
        values (space chars) which survive the round-trip but should be
        treated as empty by skip_empty_rows.
        """
        xlsx = tmp_path / "gaps.xlsx"
        pl.DataFrame({
            "id": ["1", " ", "2", " ", "3"],
            "name": ["Alice", " ", "Bob", " ", "Charlie"],
        }).write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "skip_empty_rows": True,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        df = result["main"].collect()
        assert len(df) == 3
        assert df["name"].to_list() == ["Alice", "Bob", "Charlie"]

    def test_skip_empty_false_preserves_all(self, tmp_path):
        """skip_empty_rows=false should preserve all rows including whitespace-only."""
        xlsx = tmp_path / "gaps.xlsx"
        pl.DataFrame({
            "id": ["1", " ", "2"],
            "name": ["Alice", " ", "Bob"],
        }).write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "skip_empty_rows": False,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        df = result["main"].collect()
        assert len(df) == 3


# -----------------------------------------------------------------------
# FileInputExcel Trim Tests
# -----------------------------------------------------------------------
class TestFileInputExcelTrim:
    """Test trim_all whitespace stripping for Excel files."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_excel(self):
        pytest.importorskip("openpyxl")
        pytest.importorskip("xlsxwriter")

    def test_trim_strips_whitespace(self, tmp_path):
        """Leading/trailing whitespace should be stripped."""
        xlsx = tmp_path / "spaces.xlsx"
        pl.DataFrame({
            "id": [1, 2],
            "name": ["  Alice  ", "  Bob  "],
        }).write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "trim_all": True,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        df = result["main"].collect()
        assert df["name"][0] == "Alice"
        assert df["name"][1] == "Bob"

    def test_trim_false_preserves_whitespace(self, tmp_path):
        """trim_all=false should preserve whitespace."""
        xlsx = tmp_path / "spaces.xlsx"
        pl.DataFrame({
            "id": [1],
            "name": ["  Alice  "],
        }).write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "trim_all": False,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        df = result["main"].collect()
        assert df["name"][0] == "  Alice  "

    def test_trim_only_affects_string_columns(self, tmp_path):
        """Integer columns should not be affected by trim."""
        xlsx = tmp_path / "mixed.xlsx"
        pl.DataFrame({
            "id": [1, 2],
            "name": ["  Alice  ", "  Bob  "],
        }).write_excel(xlsx)

        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "trim_all": True,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.produce()
        df = result["main"].collect()
        assert df["id"].dtype == pl.Int64
        assert df["id"].to_list() == [1, 2]
        assert df["name"][0] == "Alice"


# -----------------------------------------------------------------------
# FileInputExcel Column Range Tests
# -----------------------------------------------------------------------
class TestFileInputExcelColumnRange:
    """Test first_column / last_column support for Excel."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_excel(self):
        pytest.importorskip("openpyxl")
        pytest.importorskip("xlsxwriter")

    def test_first_column(self, tmp_path):
        """first_column should skip leading columns."""
        xlsx = tmp_path / "cols.xlsx"
        pl.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]}).write_excel(xlsx)
        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "first_column": 2,
            "schema": [
                {"name": "b", "type": "integer"},
                {"name": "c", "type": "integer"},
                {"name": "d", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        assert df.columns == ["b", "c", "d"]
        assert df["b"][0] == 2

    def test_last_column(self, tmp_path):
        """last_column should stop reading at that column."""
        xlsx = tmp_path / "cols_last.xlsx"
        pl.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]}).write_excel(xlsx)
        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "last_column": 2,
            "schema": [
                {"name": "a", "type": "integer"},
                {"name": "b", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        assert df.columns == ["a", "b"]
        assert df["b"][0] == 2

    def test_first_and_last_column(self, tmp_path):
        """Both first_column and last_column define a range."""
        xlsx = tmp_path / "cols_range.xlsx"
        pl.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]}).write_excel(xlsx)
        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "first_column": 2,
            "last_column": 3,
            "schema": [
                {"name": "b", "type": "integer"},
                {"name": "c", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        assert df.columns == ["b", "c"]
        assert df["b"][0] == 2
        assert df["c"][0] == 3

    def test_no_column_range_reads_all(self, tmp_path):
        """Without first/last_column, all columns are read."""
        xlsx = tmp_path / "cols_all.xlsx"
        pl.DataFrame({"a": [1], "b": [2], "c": [3]}).write_excel(xlsx)
        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "schema": [
                {"name": "a", "type": "integer"},
                {"name": "b", "type": "integer"},
                {"name": "c", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        assert len(df.columns) == 3

    def test_first_column_exceeds_columns(self, tmp_path):
        """first_column beyond sheet width raises ValueError."""
        xlsx = tmp_path / "cols_oob.xlsx"
        pl.DataFrame({"a": [1], "b": [2], "c": [3]}).write_excel(xlsx)
        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "first_column": 10,
            "schema": [{"name": "a", "type": "integer"}],
        })
        with pytest.raises(ValueError, match="first_column.*10.*exceeds.*3"):
            comp.produce()

    def test_last_column_exceeds_columns_clamps(self, tmp_path):
        """last_column beyond sheet width clamps without error."""
        xlsx = tmp_path / "cols_clamp.xlsx"
        pl.DataFrame({"a": [1], "b": [2], "c": [3]}).write_excel(xlsx)
        comp = FileInputExcel("read", {
            "path": str(xlsx),
            "last_column": 10,
            "schema": [
                {"name": "a", "type": "integer"},
                {"name": "b", "type": "integer"},
                {"name": "c", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        assert len(df.columns) == 3


# -----------------------------------------------------------------------
# FileInputExcel Multi-Sheet Tests
# -----------------------------------------------------------------------
class TestFileInputExcelMultiSheet:
    """Test multi-sheet reading support for Excel."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_excel(self):
        pytest.importorskip("openpyxl")
        pytest.importorskip("xlsxwriter")

    @pytest.fixture
    def multi_sheet_xlsx(self, tmp_path):
        """Create an Excel file with multiple sheets."""
        import xlsxwriter
        xlsx = tmp_path / "multi.xlsx"
        workbook = xlsxwriter.Workbook(str(xlsx))
        # Sheet1: Sales_2025
        ws1 = workbook.add_worksheet("Sales_2025")
        ws1.write_row(0, 0, ["id", "amount"])
        ws1.write_row(1, 0, [1, 100])
        ws1.write_row(2, 0, [2, 200])
        # Sheet2: Sales_2026
        ws2 = workbook.add_worksheet("Sales_2026")
        ws2.write_row(0, 0, ["id", "amount"])
        ws2.write_row(1, 0, [3, 300])
        ws2.write_row(2, 0, [4, 400])
        # Sheet3: Summary
        ws3 = workbook.add_worksheet("Summary")
        ws3.write_row(0, 0, ["id", "amount"])
        ws3.write_row(1, 0, [99, 999])
        workbook.close()
        return xlsx

    def test_all_sheets(self, multi_sheet_xlsx):
        """all_sheets=True reads all sheets concatenated."""
        comp = FileInputExcel("read", {
            "path": str(multi_sheet_xlsx),
            "all_sheets": True,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "amount", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        assert len(df) == 5
        assert sorted(df["id"].to_list()) == [1, 2, 3, 4, 99]

    def test_sheets_by_name(self, multi_sheet_xlsx):
        """sheets with name entries selects specific sheets."""
        comp = FileInputExcel("read", {
            "path": str(multi_sheet_xlsx),
            "sheets": [{"name": "Sales_2025"}, {"name": "Summary"}],
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "amount", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        assert len(df) == 3
        assert sorted(df["id"].to_list()) == [1, 2, 99]

    def test_sheets_by_index(self, multi_sheet_xlsx):
        """sheets with index entry selects by 0-based index."""
        comp = FileInputExcel("read", {
            "path": str(multi_sheet_xlsx),
            "sheets": [{"index": 1}],
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "amount", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        assert len(df) == 2
        assert df["id"].to_list() == [3, 4]

    def test_sheets_by_regex(self, multi_sheet_xlsx):
        """sheets with regex=True matches sheet names by pattern."""
        comp = FileInputExcel("read", {
            "path": str(multi_sheet_xlsx),
            "sheets": [{"name": "Sales_.*", "regex": True}],
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "amount", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        assert len(df) == 4
        assert sorted(df["id"].to_list()) == [1, 2, 3, 4]

    def test_sheets_mixed_name_and_regex(self, multi_sheet_xlsx):
        """Mix of exact name and regex entries."""
        comp = FileInputExcel("read", {
            "path": str(multi_sheet_xlsx),
            "sheets": [
                {"name": "Summary"},
                {"name": "Sales_2025"},
            ],
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "amount", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        assert len(df) == 3
        assert sorted(df["id"].to_list()) == [1, 2, 99]

    def test_multi_sheet_with_footer(self, multi_sheet_xlsx):
        """footer_rows applied per-sheet before concatenation."""
        comp = FileInputExcel("read", {
            "path": str(multi_sheet_xlsx),
            "all_sheets": True,
            "footer_rows": 1,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "amount", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        # Sales_2025: 2 rows - 1 footer = 1 row (id=1)
        # Sales_2026: 2 rows - 1 footer = 1 row (id=3)
        # Summary: 1 row - 1 footer = 0 rows
        assert len(df) == 2
        assert sorted(df["id"].to_list()) == [1, 3]

    def test_multi_sheet_with_limit(self, multi_sheet_xlsx):
        """limit applied per-sheet before concatenation."""
        comp = FileInputExcel("read", {
            "path": str(multi_sheet_xlsx),
            "all_sheets": True,
            "limit": 1,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "amount", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        # Each sheet keeps 1 row: id=1, id=3, id=99
        assert len(df) == 3
        assert sorted(df["id"].to_list()) == [1, 3, 99]

    def test_single_sheet_default(self, multi_sheet_xlsx):
        """No sheet config reads first sheet only."""
        comp = FileInputExcel("read", {
            "path": str(multi_sheet_xlsx),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "amount", "type": "integer"},
            ],
        })
        df = comp.produce()["main"].collect()
        assert len(df) == 2
        assert df["id"].to_list() == [1, 2]

    def test_regex_no_match_raises(self, multi_sheet_xlsx):
        """Regex matching nothing raises ValueError."""
        comp = FileInputExcel("read", {
            "path": str(multi_sheet_xlsx),
            "sheets": [{"name": "NoMatch_.*", "regex": True}],
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "amount", "type": "integer"},
            ],
        })
        with pytest.raises(ValueError, match="No sheets matched"):
            comp.produce()


# -----------------------------------------------------------------------
# Integration: Round-trip test
# -----------------------------------------------------------------------
class TestFileRoundTrip:
    """Test read -> write round-trip."""

    def test_csv_round_trip(self, tmp_path):
        """Test writing then reading back CSV data."""
        out = tmp_path / "round_trip.csv"

        # Write
        write_comp = FileOutputDelimited("write", {
            "path": str(out),
            "delimiter": ",",
        })
        original = pl.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "amount": [100.5, 200.0, 300.75],
        })
        write_comp.apply({"main": original.lazy()})

        # Read back
        read_comp = FileInputDelimited("read", {
            "path": str(out),
            "delimiter": ",",
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
                {"name": "amount", "type": "float"},
            ],
        })
        result = read_comp.apply({})
        df = result["main"].collect()

        assert len(df) == 3
        assert df["id"].to_list() == [1, 2, 3]
        assert df["name"].to_list() == ["Alice", "Bob", "Charlie"]

    def test_parquet_round_trip(self, tmp_path):
        """Test writing then reading back Parquet data."""
        out = tmp_path / "round_trip.parquet"

        # Write
        write_comp = FileOutputParquet("write", {"path": str(out)})
        original = pl.DataFrame({
            "id": [1, 2, 3],
            "value": [10.0, 20.0, 30.0],
        })
        write_comp.apply({"main": original.lazy()})

        # Read back (via Polars directly since we don't have FileInputParquet)
        result = pl.read_parquet(out)
        assert len(result) == 3
        assert result["id"].to_list() == [1, 2, 3]


# -----------------------------------------------------------------------
# FileInputDelimited Date Parsing Tests
# -----------------------------------------------------------------------
class TestFileInputDateParsing:
    """Test date/datetime parsing at source."""

    def test_date_column_parsed_to_pl_date(self, tmp_path):
        """Date columns with date_pattern should become pl.Date."""
        csv_file = tmp_path / "dates.csv"
        csv_file.write_text("id,order_date\n1,2026-03-01\n2,2026-03-02\n")
        comp = FileInputDelimited("read", {
            "path": str(csv_file),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "order_date", "type": "date", "date_pattern": "%Y-%m-%d"},
            ],
        })
        result = comp.produce()
        df = result["main"].collect()
        assert df["order_date"].dtype == pl.Date
        assert df["order_date"][0] == date(2026, 3, 1)

    def test_datetime_column_parsed_to_pl_datetime(self, tmp_path):
        """Datetime columns with date_pattern should become pl.Datetime."""
        csv_file = tmp_path / "datetimes.csv"
        csv_file.write_text("id,created_at\n1,2026-03-01T14:30:00\n2,2026-03-02T09:15:00\n")
        comp = FileInputDelimited("read", {
            "path": str(csv_file),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "created_at", "type": "datetime", "date_pattern": "%Y-%m-%dT%H:%M:%S"},
            ],
        })
        result = comp.produce()
        df = result["main"].collect()
        assert df["created_at"].dtype == pl.Datetime
        assert df["created_at"][0] == datetime(2026, 3, 1, 14, 30, 0)

    def test_date_custom_format(self, tmp_path):
        """Date columns with non-ISO format should parse correctly."""
        csv_file = tmp_path / "custom_dates.csv"
        csv_file.write_text("id,event_date\n1,01/03/2026\n2,15/06/2025\n")
        comp = FileInputDelimited("read", {
            "path": str(csv_file),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "event_date", "type": "date", "date_pattern": "%d/%m/%Y"},
            ],
        })
        result = comp.produce()
        df = result["main"].collect()
        assert df["event_date"].dtype == pl.Date
        assert df["event_date"][0] == date(2026, 3, 1)

    def test_date_missing_pattern_fails_validation(self, tmp_path):
        """Date column without date_pattern should fail validation."""
        csv_file = tmp_path / "dates.csv"
        csv_file.write_text("id,order_date\n1,2026-03-01\n")
        comp = FileInputDelimited("read", {
            "path": str(csv_file),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "order_date", "type": "date"},
            ],
        })
        errors = comp.validate()
        assert any("date_pattern" in e for e in errors)

    def test_date_bad_value_crashes_die_on_error_true(self, tmp_path):
        """Bad date value with die_on_error=true should crash."""
        csv_file = tmp_path / "bad_dates.csv"
        csv_file.write_text("id,order_date\n1,2026-03-01\n2,not_a_date\n")
        comp = FileInputDelimited("read", {
            "path": str(csv_file),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "order_date", "type": "date", "date_pattern": "%Y-%m-%d"},
            ],
        })
        with pytest.raises(Exception):
            comp.produce()["main"].collect()

    def test_pipeline_stays_lazy_with_dates(self, tmp_path):
        """Date parsing should not break laziness."""
        csv_file = tmp_path / "dates.csv"
        csv_file.write_text("id,order_date\n1,2026-03-01\n2,2026-03-02\n")
        comp = FileInputDelimited("read", {
            "path": str(csv_file),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "order_date", "type": "date", "date_pattern": "%Y-%m-%d"},
            ],
        })
        result = comp.produce()
        assert isinstance(result["main"], pl.LazyFrame)


# -----------------------------------------------------------------------
# FileInputDelimited Quoting Tests
# -----------------------------------------------------------------------
class TestFileInputQuoting:
    """Test CSV quoting support."""

    def test_quoted_field_with_delimiter(self, tmp_path):
        """Quoted fields containing the delimiter should be read as one field."""
        csv = tmp_path / "quoted.csv"
        csv.write_text('name,address\nAlice,"123 Main St, Apt 4"\nBob,"456 Oak Ave"\n')

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "schema": [
                {"name": "name", "type": "string"},
                {"name": "address", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 2
        assert df["address"][0] == "123 Main St, Apt 4"

    def test_quoted_field_with_newline(self, tmp_path):
        """Quoted fields containing newlines should be read as one field."""
        csv = tmp_path / "newline.csv"
        csv.write_text('id,notes\n1,"line one\nline two"\n2,"simple"\n')

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "notes", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 2
        assert "line one\nline two" == df["notes"][0]

    def test_escaped_quote_inside_field(self, tmp_path):
        """Doubled quotes inside a quoted field should become a single quote."""
        csv = tmp_path / "escaped.csv"
        csv.write_text('id,value\n1,"say ""hello"""\n2,"normal"\n')

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "value", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert df["value"][0] == 'say "hello"'

    def test_quote_char_none_disables(self, tmp_path):
        """Setting quote_char to null should treat quotes as literal characters."""
        csv = tmp_path / "noquote.csv"
        csv.write_text('id,value\n1,"quoted"\n2,plain\n')

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "value", "type": "string"},
            ],
            "quote_char": None,
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert df["value"][0] == '"quoted"'

    def test_custom_quote_char(self, tmp_path):
        """Custom quote character (single quote) should work."""
        csv = tmp_path / "single_quote.csv"
        csv.write_text("id,value\n1,'hello, world'\n2,'simple'\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "value", "type": "string"},
            ],
            "quote_char": "'",
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert df["value"][0] == "hello, world"

    def test_validate_quote_char_multi_char(self):
        """quote_char with more than one character should fail validation."""
        comp = FileInputDelimited("read", {
            "path": "/tmp/test.csv",
            "schema": [{"name": "a", "type": "string"}],
            "quote_char": "ab",
        })
        errors = comp.validate()
        assert any("quote_char" in e for e in errors)


# -----------------------------------------------------------------------
# FileInputDelimited Footer Row Tests
# -----------------------------------------------------------------------
class TestFileInputFooter:
    """Test footer row skipping."""

    def test_footer_rows_skips_last_n(self, tmp_path):
        """footer_rows=2 should skip the last 2 rows."""
        csv = tmp_path / "footer.csv"
        csv.write_text("id,name\n1,Alice\n2,Bob\n3,Charlie\nTOTAL,3\nEND,\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "footer_rows": 2,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 3
        assert df["name"].to_list() == ["Alice", "Bob", "Charlie"]

    def test_footer_zero_stays_lazy(self, tmp_path):
        """footer_rows=0 (default) should produce a LazyFrame."""
        csv = tmp_path / "test.csv"
        csv.write_text("id,name\n1,Alice\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "footer_rows": 0,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        assert isinstance(result["main"], pl.LazyFrame)

    def test_footer_plus_header(self, tmp_path):
        """Footer and header combined."""
        csv = tmp_path / "both.csv"
        csv.write_text("header_id,header_name\n1,Alice\n2,Bob\nFOOTER,LINE\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "footer_rows": 1,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 2
        assert df["name"].to_list() == ["Alice", "Bob"]

    def test_footer_larger_than_data(self, tmp_path):
        """Footer larger than data rows should return 0 rows."""
        csv = tmp_path / "tiny.csv"
        csv.write_text("id,name\n1,Alice\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "footer_rows": 10,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 0


# -----------------------------------------------------------------------
# FileInputDelimited Limit Tests
# -----------------------------------------------------------------------
class TestFileInputLimit:
    """Test row limit."""

    def test_limit_returns_n_rows(self, tmp_path):
        """limit=2 should return exactly 2 rows."""
        csv = tmp_path / "data.csv"
        csv.write_text("id,name\n1,Alice\n2,Bob\n3,Charlie\n4,Diana\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "limit": 2,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 2

    def test_limit_null_returns_all(self, tmp_path):
        """limit=null (default) should return all rows."""
        csv = tmp_path / "data.csv"
        csv.write_text("id,name\n1,Alice\n2,Bob\n3,Charlie\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 3

    def test_limit_zero_returns_empty(self, tmp_path):
        """limit=0 should return zero rows (Talend behavior)."""
        csv = tmp_path / "data.csv"
        csv.write_text("id,name\n1,Alice\n2,Bob\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "limit": 0,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 0

    def test_limit_larger_than_file(self, tmp_path):
        """limit larger than file should return all rows."""
        csv = tmp_path / "data.csv"
        csv.write_text("id,name\n1,Alice\n2,Bob\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "limit": 1000,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 2

    def test_limit_with_footer(self, tmp_path):
        """limit + footer_rows combined: footer first, then limit."""
        csv = tmp_path / "data.csv"
        csv.write_text("id,name\n1,Alice\n2,Bob\n3,Charlie\n4,Diana\nFOOTER,X\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "footer_rows": 1,
            "limit": 2,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 2
        assert df["name"][0] == "Alice"

    def test_validate_negative_limit(self):
        """Negative limit should produce a validation error."""
        comp = FileInputDelimited("read", {
            "path": "/tmp/test.csv",
            "schema": [{"name": "a", "type": "string"}],
            "limit": -1,
        })
        errors = comp.validate()
        assert any("limit" in e for e in errors)

    def test_validate_negative_footer_rows(self):
        """Negative footer_rows should produce a validation error."""
        comp = FileInputDelimited("read", {
            "path": "/tmp/test.csv",
            "schema": [{"name": "a", "type": "string"}],
            "footer_rows": -1,
        })
        errors = comp.validate()
        assert any("footer_rows" in e for e in errors)


# -----------------------------------------------------------------------
# FileInputDelimited Skip Empty Rows Tests
# -----------------------------------------------------------------------
class TestFileInputSkipEmpty:
    """Test skip_empty_rows."""

    def test_skip_empty_rows_removes_blank_lines(self, tmp_path):
        """Blank lines should be removed when skip_empty_rows=True."""
        csv = tmp_path / "gaps.csv"
        csv.write_text("id,name\n1,Alice\n,\n2,Bob\n,\n3,Charlie\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "skip_empty_rows": True,
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 3
        assert df["name"].to_list() == ["Alice", "Bob", "Charlie"]

    def test_skip_empty_rows_false_preserves(self, tmp_path):
        """Default (false) should preserve blank lines."""
        csv = tmp_path / "gaps.csv"
        csv.write_text("id,name\n1,Alice\n,\n2,Bob\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert len(df) == 3  # includes the blank line


# -----------------------------------------------------------------------
# FileInputDelimited Trim All Tests
# -----------------------------------------------------------------------
class TestFileInputTrimAll:
    """Test trim_all whitespace stripping."""

    def test_trim_strips_whitespace(self, tmp_path):
        """Leading/trailing whitespace should be stripped from string columns."""
        csv = tmp_path / "spaces.csv"
        csv.write_text("id,name\n1, Alice \n2,  Bob  \n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "trim_all": True,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert df["name"][0] == "Alice"
        assert df["name"][1] == "Bob"

    def test_trim_false_preserves_whitespace(self, tmp_path):
        """Default (false) should preserve whitespace."""
        csv = tmp_path / "spaces.csv"
        csv.write_text("id,name\n1, Alice \n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert df["name"][0] == " Alice "

    def test_trim_only_affects_string_columns(self, tmp_path):
        """Non-string columns should not be affected by trim."""
        csv = tmp_path / "mixed.csv"
        csv.write_text("id,name,amount\n1, Alice ,100.5\n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "trim_all": True,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
                {"name": "amount", "type": "float"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert df["name"][0] == "Alice"
        assert df["amount"][0] == 100.5

    def test_trim_before_date_parsing(self, tmp_path):
        """Trim should happen before date parsing so padded dates work."""
        csv = tmp_path / "dates.csv"
        csv.write_text("id,d\n1, 2026-03-01 \n")

        comp = FileInputDelimited("read", {
            "path": str(csv),
            "trim_all": True,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "d", "type": "date", "date_pattern": "%Y-%m-%d"},
            ],
        })

        result = comp.apply({})
        df = result["main"].collect()
        assert df["d"].dtype == pl.Date
