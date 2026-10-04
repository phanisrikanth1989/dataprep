"""
Tests for Iterate Components in v2 Engine.

Tests:
- FileList iterate component
- FlowToIterate component
"""
import os
import pytest
import polars as pl

from src.v2.components.iterate.file_list import FileList
from src.v2.components.iterate.flow_to_iterate import FlowToIterate


class TestFileList:
    def test_find_files(self, tmp_path):
        # Create test files
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "b.csv").write_text("data")
        (tmp_path / "c.txt").write_text("data")

        comp = FileList("fl", {"directory": str(tmp_path), "files": [{"filemask": "*.csv"}]})
        result = comp.apply({})

        assert "__iterations__" in result
        iterations = result["__iterations__"]
        assert len(iterations) == 2
        assert iterations[0]["fl_CURRENT_FILEEXT"] == ".csv"

    def test_no_files_error(self, tmp_path):
        comp = FileList("fl", {"directory": str(tmp_path), "files": [{"filemask": "*.csv"}], "error": True})
        with pytest.raises(FileNotFoundError):
            comp.apply({})

    def test_no_files_no_error(self, tmp_path):
        comp = FileList("fl", {"directory": str(tmp_path), "files": [{"filemask": "*.csv"}], "error": False})
        result = comp.apply({})
        assert result["__iterations__"] == []

    def test_sort_by_filename(self, tmp_path):
        (tmp_path / "b.csv").write_text("data")
        (tmp_path / "a.csv").write_text("data")

        comp = FileList("fl", {"directory": str(tmp_path), "files": [{"filemask": "*.csv"}], "order_by": "FILENAME"})
        result = comp.apply({})
        filenames = [it["fl_CURRENT_FILE"] for it in result["__iterations__"]]
        assert filenames == sorted(filenames)

    def test_include_subdirs(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.csv").write_text("data")
        (sub / "b.csv").write_text("data")

        comp = FileList("fl", {"directory": str(tmp_path), "files": [{"filemask": "*.csv"}], "include_subdirs": True})
        result = comp.apply({})
        assert len(result["__iterations__"]) == 2

    def test_directory_not_found(self):
        comp = FileList("fl", {"directory": "/nonexistent/path", "error": True})
        with pytest.raises(FileNotFoundError):
            comp.apply({})

    def test_directory_not_found_no_error(self):
        comp = FileList("fl", {"directory": "/nonexistent/path", "error": False})
        result = comp.apply({})
        assert result["__iterations__"] == []

    def test_is_barrier(self):
        comp = FileList("fl", {"directory": "."})
        assert comp.is_barrier is True

    def test_validate_missing_directory(self):
        comp = FileList("fl", {})
        errors = comp.validate()
        assert len(errors) > 0

    def test_validate_valid(self):
        comp = FileList("fl", {"directory": "/tmp"})
        assert comp.validate() == []

    def test_context_resolution(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        comp = FileList("fl", {"directory": "${context.dir}"}, context={"dir": str(tmp_path)})
        result = comp.apply({})
        assert len(result["__iterations__"]) >= 1

    def test_registry(self):
        from src.v2.components.registry import REGISTRY
        assert REGISTRY.get("file_list") is not None
        assert REGISTRY.get("iterate_file_list") is not None

    def test_all_files_mode(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        comp = FileList("fl", {"directory": str(tmp_path), "files": [{"filemask": "*"}], "list_mode": "ALL"})
        result = comp.apply({})
        assert len(result["__iterations__"]) >= 1

    def test_file_info_fields(self, tmp_path):
        (tmp_path / "test.csv").write_text("data")
        comp = FileList("fl", {"directory": str(tmp_path), "files": [{"filemask": "*.csv"}]})
        result = comp.apply({})
        it = result["__iterations__"][0]
        assert "fl_CURRENT_FILE" in it
        assert "fl_CURRENT_FILEPATH" in it
        assert "fl_CURRENT_FILEDIRECTORY" in it
        assert "fl_CURRENT_FILEEXT" in it
        assert "fl_CURRENT_FILE_SIZE" in it

    def test_sort_by_filesize(self, tmp_path):
        (tmp_path / "small.csv").write_text("a")
        (tmp_path / "large.csv").write_text("a" * 100)

        comp = FileList("fl", {
            "directory": str(tmp_path),
            "files": [{"filemask": "*.csv"}],
            "order_by": "FILESIZE",
        })
        result = comp.apply({})
        sizes = [it["fl_CURRENT_FILE_SIZE"] for it in result["__iterations__"]]
        assert sizes == sorted(sizes)

    def test_sort_descending(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "b.csv").write_text("data")

        comp = FileList("fl", {
            "directory": str(tmp_path),
            "files": [{"filemask": "*.csv"}],
            "order_by": "FILENAME",
            "order_desc": True,
        })
        result = comp.apply({})
        filenames = [it["fl_CURRENT_FILE"] for it in result["__iterations__"]]
        assert filenames == sorted(filenames, reverse=True)

    def test_directories_mode(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (tmp_path / "file.csv").write_text("data")

        comp = FileList("fl", {
            "directory": str(tmp_path),
            "files": [{"filemask": "*"}],
            "list_mode": "DIRECTORIES",
        })
        result = comp.apply({})
        iterations = result["__iterations__"]
        assert len(iterations) == 1
        assert iterations[0]["fl_CURRENT_FILE"] == "subdir"

    def test_default_filemask(self, tmp_path):
        """When files config not provided, defaults to wildcard."""
        (tmp_path / "a.txt").write_text("data")
        comp = FileList("fl", {"directory": str(tmp_path)})
        result = comp.apply({})
        assert len(result["__iterations__"]) >= 1

    def test_string_filemask(self, tmp_path):
        """File mask can be a plain string instead of dict."""
        (tmp_path / "a.csv").write_text("data")
        comp = FileList("fl", {"directory": str(tmp_path), "files": ["*.csv"]})
        result = comp.apply({})
        assert len(result["__iterations__"]) == 1

    def test_multiple_masks(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "b.txt").write_text("data")
        (tmp_path / "c.json").write_text("data")

        comp = FileList("fl", {
            "directory": str(tmp_path),
            "files": [{"filemask": "*.csv"}, {"filemask": "*.txt"}],
        })
        result = comp.apply({})
        assert len(result["__iterations__"]) == 2


class TestFlowToIterate:
    def test_basic_iteration(self):
        comp = FlowToIterate("fti", {})
        df = pl.DataFrame({"id": [1, 2, 3], "name": ["A", "B", "C"]}).lazy()
        result = comp.apply({"main": df})

        assert "__iterations__" in result
        iterations = result["__iterations__"]
        assert len(iterations) == 3
        assert iterations[0]["fti_id"] == 1
        assert iterations[0]["fti_name"] == "A"

    def test_no_input_returns_empty(self):
        comp = FlowToIterate("fti", {})
        result = comp.apply({})
        assert result["__iterations__"] == []

    def test_column_filter(self):
        comp = FlowToIterate("fti", {"columns": ["id"]})
        df = pl.DataFrame({"id": [1], "name": ["A"], "extra": [True]}).lazy()
        result = comp.apply({"main": df})
        iterations = result["__iterations__"]
        assert "fti_id" in iterations[0]
        assert "fti_name" not in iterations[0]

    def test_is_barrier(self):
        comp = FlowToIterate("fti", {})
        assert comp.is_barrier is True

    def test_dataframe_input(self):
        comp = FlowToIterate("fti", {})
        df = pl.DataFrame({"x": [1]})  # Not lazy
        result = comp.apply({"main": df})
        assert len(result["__iterations__"]) == 1

    def test_registry(self):
        from src.v2.components.registry import REGISTRY
        assert REGISTRY.get("flow_to_iterate") is not None

    def test_empty_dataframe(self):
        comp = FlowToIterate("fti", {})
        df = pl.DataFrame({"x": pl.Series([], dtype=pl.Int64)}).lazy()
        result = comp.apply({"main": df})
        assert result["__iterations__"] == []

    def test_non_dataframe_input(self):
        comp = FlowToIterate("fti", {})
        result = comp.apply({"main": "not_a_dataframe"})
        assert result["__iterations__"] == []

    def test_multiple_columns(self):
        comp = FlowToIterate("fti", {})
        df = pl.DataFrame({
            "path": ["/a", "/b"],
            "size": [100, 200],
            "flag": [True, False],
        }).lazy()
        result = comp.apply({"main": df})
        iterations = result["__iterations__"]
        assert len(iterations) == 2
        assert iterations[0]["fti_path"] == "/a"
        assert iterations[0]["fti_size"] == 100
        assert iterations[0]["fti_flag"] is True
        assert iterations[1]["fti_path"] == "/b"
        assert iterations[1]["fti_size"] == 200
        assert iterations[1]["fti_flag"] is False

    def test_column_filter_multiple(self):
        comp = FlowToIterate("fti", {"columns": ["a", "c"]})
        df = pl.DataFrame({"a": [1], "b": [2], "c": [3]}).lazy()
        result = comp.apply({"main": df})
        it = result["__iterations__"][0]
        assert "fti_a" in it
        assert "fti_c" in it
        assert "fti_b" not in it

    def test_component_id_prefix(self):
        """Context keys should be prefixed with component_id."""
        comp = FlowToIterate("my_iter", {})
        df = pl.DataFrame({"col": [1]}).lazy()
        result = comp.apply({"main": df})
        assert "my_iter_col" in result["__iterations__"][0]
