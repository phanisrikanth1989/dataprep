"""Tests for FileOutputDelimited (tFileOutputDelimited engine implementation)."""
import csv
import os

import pytest
import pandas as pd

from src.v1.engine.components.file.file_output_delimited import FileOutputDelimited
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import (
    ComponentExecutionError,
    ConfigurationError,
    FileOperationError,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "FileOutputDelimited",
    "filepath": "/tmp/test_output.csv",
    "fieldseparator": ";",
    "encoding": "ISO-8859-15",
    "include_header": False,
    "append": False,
    "csv_option": False,
    "os_line_separator": True,
    "csvrowseparator": "LF",
    "create_directory": True,
    "split": False,
    "split_every": "1000",
    "delete_empty_file": False,
    "file_exist_exception": True,
    "die_on_error": False,
}


def _make_component(config=None, global_map=None, context_manager=None):
    """Create a FileOutputDelimited with test defaults.

    Always creates fresh GlobalMap and ContextManager instances
    unless explicitly provided.
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    return FileOutputDelimited(
        component_id="tFOD_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )


def _make_input_df(rows=None):
    """Create test input DataFrame with realistic data."""
    if rows is None:
        rows = [
            {"id": 1, "name": "Alice", "value": 100.50},
            {"id": 2, "name": "Bob", "value": 200.75},
            {"id": 3, "name": "Charlie", "value": 0.0},
        ]
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for missing/invalid keys."""

    def test_missing_filepath_raises(self, tmp_path):
        config = dict(_DEFAULT_CONFIG)
        del config["filepath"]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="filepath"):
            comp.execute(_make_input_df())

    def test_empty_filepath_raises(self, tmp_path):
        config = {**_DEFAULT_CONFIG, "filepath": ""}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="filepath"):
            comp.execute(_make_input_df())

    def test_valid_config_does_not_raise(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert "main" in result


# ------------------------------------------------------------------
# TestDefaults
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDefaults:
    """Default config produces expected behavior matching Talend defaults."""

    def test_default_fieldseparator_is_semicolon(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False, "include_header": True}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        content = open(filepath, encoding="ISO-8859-15").read()
        # Header line should use semicolons
        header = content.split(os.linesep)[0] if os.linesep in content else content.splitlines()[0]
        assert ";" in header

    def test_default_encoding_is_iso_8859_15(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        # File should be readable with ISO-8859-15
        content = open(filepath, encoding="ISO-8859-15").read()
        assert len(content) > 0

    def test_default_include_header_is_false(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        content = open(filepath, encoding="ISO-8859-15").read()
        # No header row -- first line should be data, not column names
        first_line = content.splitlines()[0]
        assert "id" not in first_line
        assert "name" not in first_line

    def test_default_file_exist_exception_is_true(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        # Create file first
        open(filepath, "w").close()
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)
        with pytest.raises(ComponentExecutionError, match="already exists"):
            comp.execute(_make_input_df())

    def test_default_create_directory_is_true(self, tmp_path):
        filepath = str(tmp_path / "subdir" / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        assert os.path.exists(filepath)

    def test_default_append_is_false(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        df = _make_input_df()
        comp.execute(df)
        first_content = open(filepath, encoding="ISO-8859-15").read()
        # Write again -- should overwrite, not append
        comp2 = _make_component(config=config)
        comp2.execute(df)
        second_content = open(filepath, encoding="ISO-8859-15").read()
        assert first_content == second_content


# ------------------------------------------------------------------
# TestBasicWriting
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBasicWriting:
    """Core file writing with various configurations."""

    def test_writes_semicolon_delimited_file(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 3
        assert ";" in lines[0]

    def test_writes_pipe_delimited_file(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "fieldseparator": "|", "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert "|" in lines[0]

    def test_writes_with_header(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "include_header": True, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 4  # 1 header + 3 data rows
        assert "id" in lines[0]
        assert "name" in lines[0]
        assert "value" in lines[0]

    def test_writes_without_header_default(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 3  # Data only, no header

    def test_writes_with_specified_encoding(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "encoding": "UTF-8", "file_exist_exception": False}
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": 1, "name": "cafe"}])
        comp.execute(df)
        content = open(filepath, encoding="UTF-8").read()
        assert "cafe" in content

    def test_append_mode_appends_to_existing(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "append": True, "file_exist_exception": False}
        comp1 = _make_component(config=config)
        comp1.execute(_make_input_df([{"id": 1, "name": "Alice", "value": 100.0}]))
        comp2 = _make_component(config=config)
        comp2.execute(_make_input_df([{"id": 2, "name": "Bob", "value": 200.0}]))
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 2

    def test_passthrough_returns_input_data(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        df = _make_input_df()
        result = comp.execute(df)
        # Sink component passes through input as main
        assert result["main"] is not None
        assert len(result["main"]) == 3


# ------------------------------------------------------------------
# TestFileExistException (FOLD-05)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFileExistException:
    """FILE_EXIST_EXCEPTION prevents accidental overwrites."""

    def test_raises_when_file_exists_and_exception_true(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        open(filepath, "w").close()
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": True}
        comp = _make_component(config=config)
        with pytest.raises(ComponentExecutionError, match="already exists"):
            comp.execute(_make_input_df())

    def test_does_not_raise_with_append_true(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        open(filepath, "w").close()
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": True, "append": True}
        comp = _make_component(config=config)
        # Should not raise because append=True
        result = comp.execute(_make_input_df())
        assert result["main"] is not None

    def test_does_not_raise_when_exception_false(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        open(filepath, "w").close()
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert result["main"] is not None

    def test_does_not_raise_when_file_does_not_exist(self, tmp_path):
        filepath = str(tmp_path / "new_output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": True}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert result["main"] is not None


# ------------------------------------------------------------------
# TestSplitOutput (FOLD-04)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSplitOutput:
    """SPLIT/SPLIT_EVERY produces correctly named split files."""

    def test_split_creates_multiple_files(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "split": True, "split_every": "2", "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())  # 3 rows, split_every=2 -> 2 files
        assert os.path.exists(str(tmp_path / "output0.csv"))
        assert os.path.exists(str(tmp_path / "output1.csv"))

    def test_split_files_named_correctly(self, tmp_path):
        filepath = str(tmp_path / "data.txt")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "split": True, "split_every": "1", "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())  # 3 rows -> 3 files
        assert os.path.exists(str(tmp_path / "data0.txt"))
        assert os.path.exists(str(tmp_path / "data1.txt"))
        assert os.path.exists(str(tmp_path / "data2.txt"))

    def test_split_file_correct_row_count(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "split": True, "split_every": "2", "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())  # 3 rows
        file0 = open(str(tmp_path / "output0.csv"), encoding="ISO-8859-15").read()
        file1 = open(str(tmp_path / "output1.csv"), encoding="ISO-8859-15").read()
        assert len(file0.splitlines()) == 2
        assert len(file1.splitlines()) == 1

    def test_split_last_file_fewer_rows(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        df = pd.DataFrame([{"id": i, "name": f"user_{i}", "value": float(i)} for i in range(5)])
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "split": True, "split_every": "3", "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(df)
        file0 = open(str(tmp_path / "output0.csv"), encoding="ISO-8859-15").read()
        file1 = open(str(tmp_path / "output1.csv"), encoding="ISO-8859-15").read()
        assert len(file0.splitlines()) == 3
        assert len(file1.splitlines()) == 2

    def test_split_false_writes_single_file(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "split": False, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        assert os.path.exists(filepath)
        # No split files should exist
        assert not os.path.exists(str(tmp_path / "output0.csv"))


# ------------------------------------------------------------------
# TestOsLineSeparator (D-19)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestOsLineSeparator:
    """OS_LINE_SEPARATOR and CSV row separator behavior."""

    def test_os_line_separator_uses_os_linesep(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "os_line_separator": True, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df([{"id": 1, "name": "A", "value": 1.0}]))
        raw = open(filepath, "rb").read()
        # Should contain os.linesep as binary
        assert os.linesep.encode("ISO-8859-15") in raw

    def test_csv_option_with_crlf_separator(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "os_line_separator": False,
            "csv_option": True, "csvrowseparator": "CRLF", "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        comp.execute(_make_input_df([{"id": 1, "name": "A", "value": 1.0}]))
        raw = open(filepath, "rb").read()
        assert b"\r\n" in raw

    def test_explicit_row_separator(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "os_line_separator": False,
            "csv_option": False, "row_separator": "\\n", "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        comp.execute(_make_input_df([{"id": 1, "name": "A", "value": 1.0}]))
        raw = open(filepath, "rb").read()
        assert b"\n" in raw

    def test_csv_option_with_cr_separator(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "os_line_separator": False,
            "csv_option": True, "csvrowseparator": "CR", "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        comp.execute(_make_input_df([{"id": 1, "name": "A", "value": 1.0}]))
        raw = open(filepath, "rb").read()
        assert b"\r" in raw


# ------------------------------------------------------------------
# TestCsvOption
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCsvOption:
    """CSV quoting mode behavior."""

    def test_csv_option_quotes_fields_with_delimiter(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "csv_option": True,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        # Data with semicolons in name field should be quoted
        df = pd.DataFrame([{"id": 1, "name": "Alice;Bob", "value": 100.0}])
        comp.execute(df)
        content = open(filepath, encoding="ISO-8859-15").read()
        # The field containing the delimiter should be quoted
        assert '"Alice;Bob"' in content

    def test_csv_option_false_no_quoting(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "csv_option": False,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": 1, "name": "Alice", "value": 100.0}])
        comp.execute(df)
        content = open(filepath, encoding="ISO-8859-15").read()
        # No quotes around plain fields
        assert '"' not in content

    def test_csv_option_with_custom_enclosure(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "csv_option": True,
            "text_enclosure": "'", "escape_char": "'", "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": 1, "name": "Alice;Bob", "value": 100.0}])
        comp.execute(df)
        content = open(filepath, encoding="ISO-8859-15").read()
        assert "'Alice;Bob'" in content


# ------------------------------------------------------------------
# TestCreateDirectory
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCreateDirectory:
    """Directory creation behavior."""

    def test_creates_parent_directory(self, tmp_path):
        filepath = str(tmp_path / "deep" / "nested" / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "create_directory": True, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        assert os.path.exists(filepath)

    def test_fails_without_create_directory(self, tmp_path):
        filepath = str(tmp_path / "missing_dir" / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "create_directory": False, "file_exist_exception": False}
        comp = _make_component(config=config)
        with pytest.raises(Exception):
            comp.execute(_make_input_df())

    def test_existing_directory_no_error(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "create_directory": True, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        assert os.path.exists(filepath)


# ------------------------------------------------------------------
# TestDeleteEmptyFile
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDeleteEmptyFile:
    """Empty input with delete_empty_file behavior."""

    def test_empty_input_delete_produces_no_file(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "delete_empty_file": True, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(pd.DataFrame())
        assert not os.path.exists(filepath)

    def test_empty_input_no_delete_produces_file(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "delete_empty_file": False, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(pd.DataFrame())
        assert os.path.exists(filepath)

    def test_delete_empty_file_removes_existing(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        # Create file first
        open(filepath, "w").write("old content")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "delete_empty_file": True, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(pd.DataFrame())
        assert not os.path.exists(filepath)


# ------------------------------------------------------------------
# TestEmptyInputHeaderOnly
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEmptyInputHeaderOnly:
    """Empty input with include_header=True produces header-only file."""

    def test_empty_dataframe_with_header_writes_header_only(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "include_header": True, "file_exist_exception": False}
        comp = _make_component(config=config)
        # Set output_schema to provide column names
        comp.output_schema = [
            {"name": "id", "type": "int"},
            {"name": "name", "type": "str"},
            {"name": "value", "type": "float"},
        ]
        comp.execute(pd.DataFrame())
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 1
        assert "id" in lines[0]
        assert "name" in lines[0]
        assert "value" in lines[0]

    def test_none_input_with_header_and_schema_writes_header(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "include_header": True, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.output_schema = [
            {"name": "col_a", "type": "str"},
            {"name": "col_b", "type": "int"},
        ]
        comp.execute(None)
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 1
        assert "col_a" in lines[0]
        assert "col_b" in lines[0]

    def test_empty_dataframe_without_header_writes_empty_file(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "include_header": False, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(pd.DataFrame())
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) == 0

    def test_empty_input_header_uses_input_schema(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "include_header": True,
            "file_exist_exception": False,
            "schema": {"input": [{"name": "x", "type": "int"}, {"name": "y", "type": "str"}], "output": []},
        }
        comp = _make_component(config=config)
        comp.execute(pd.DataFrame())
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 1
        assert "x" in lines[0]
        assert "y" in lines[0]


# ------------------------------------------------------------------
# TestGlobalMapVariables (FOLD-06)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    """GlobalMap FILE_NAME and NB_LINE variables set correctly."""

    def test_file_name_set_in_global_map(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        comp.execute(_make_input_df())
        assert gm.get("tFOD_1_FILE_NAME") == filepath

    def test_nb_line_set_in_global_map(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        comp.execute(_make_input_df())
        assert gm.get("tFOD_1_NB_LINE") == 3

    def test_stats_pushed_to_global_map(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        comp.execute(_make_input_df())
        # BaseComponent pushes NB_LINE, NB_LINE_OK, NB_LINE_REJECT
        assert gm.get_component_stat("tFOD_1", "NB_LINE") >= 0

    def test_works_without_global_map(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config, global_map=None)
        comp.global_map = None
        result = comp.execute(_make_input_df())
        assert "main" in result


# ------------------------------------------------------------------
# TestDeferredFeatures
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDeferredFeatures:
    """Deferred features log a warning and proceed."""

    def test_compress_logs_warning(self, tmp_path, caplog):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "compress": True, "file_exist_exception": False}
        comp = _make_component(config=config)
        with caplog.at_level("WARNING"):
            comp.execute(_make_input_df())
        assert any("compress" in r.message for r in caplog.records)

    def test_usestream_logs_warning(self, tmp_path, caplog):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "usestream": True, "file_exist_exception": False}
        comp = _make_component(config=config)
        with caplog.at_level("WARNING"):
            comp.execute(_make_input_df())
        assert any("usestream" in r.message for r in caplog.records)

    def test_row_mode_logs_warning(self, tmp_path, caplog):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "row_mode": True, "file_exist_exception": False}
        comp = _make_component(config=config)
        with caplog.at_level("WARNING"):
            comp.execute(_make_input_df())
        assert any("row_mode" in r.message for r in caplog.records)


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge case handling: None, single row, empty DataFrame."""

    def test_none_input(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert "main" in result
        # File should exist (empty or with header)
        assert os.path.exists(filepath)

    def test_single_row_writes_correctly(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        df = _make_input_df([{"id": 1, "name": "Only", "value": 42.0}])
        result = comp.execute(df)
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 1

    def test_empty_dataframe(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        result = comp.execute(pd.DataFrame())
        assert "main" in result
        assert os.path.exists(filepath)

    def test_tab_separated_output(self, tmp_path):
        filepath = str(tmp_path / "output.tsv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "fieldseparator": "\\t", "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        content = open(filepath, encoding="ISO-8859-15").read()
        assert "\t" in content


# ------------------------------------------------------------------
# TestIterateReexecution
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIterateReexecution:
    """execute() twice with reset() between gives correct results."""

    def test_second_execute_produces_correct_results(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        df = _make_input_df()

        result1 = comp.execute(df)
        comp.reset()
        result2 = comp.execute(df)

        # Both results should have data
        assert result1["main"] is not None
        assert result2["main"] is not None

    def test_stats_reset_between_executions(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        df = _make_input_df()

        comp.execute(df)
        comp.reset()
        comp.execute(df)

        # Stats should reflect only the second execution
        assert gm.get("tFOD_1_NB_LINE") == 3

    def test_config_not_mutated_across_executions(self, tmp_path):
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        df = _make_input_df()

        comp.execute(df)
        original_snapshot = comp._original_config.copy()
        comp.reset()
        comp.execute(df)

        assert comp._original_config == original_snapshot
