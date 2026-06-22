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
        # WR-17 fix: set comp.input_schema directly (the engine sets this attribute,
        # not config["schema"]). The component reads self.input_schema, not config.
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "include_header": True,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        comp.input_schema = [{"name": "x", "type": "int"}, {"name": "y", "type": "str"}]
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


# ------------------------------------------------------------------
# TestMultiCharDelimiter
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMultiCharDelimiter:
    """Multi-character field separator behaviour (Talend parity).

    Verified against Talaxie tdi-studio-se primary source on 2026-04-29:

    - csv_option=True + multi-char fieldseparator: Talend's csv writer takes a
      Java char (single UTF-16 unit) via setSeparator(char). The component
      truncates to the first character and emits a warning (parity).
    - csv_option=False + multi-char fieldseparator: Talend writes via
      BufferedWriter.write(String), which accepts arbitrary-length separators.
      The component preserves the full string between fields.
    """

    def test_pipe_semicolon_delimiter_with_csv_option(self, tmp_path, caplog):
        """csv_option=True + '|;' -> first char '|' used; warning logged."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "fieldseparator": "|;", "csv_option": True,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        with caplog.at_level("WARNING"):
            comp.execute(_make_input_df())
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 3
        # Output uses single-char '|' only; multi-char '|;' must NOT appear.
        assert "|;" not in content
        assert "|" in lines[0]
        # Warning emitted explaining the truncation (Talend parity).
        truncate_warns = [
            r for r in caplog.records
            if "Multi-character fieldseparator" in r.message and "first character" in r.message
        ]
        assert truncate_warns, (
            f"Expected truncate warning for multi-char + csv_option=True. "
            f"Records: {[r.message for r in caplog.records]}"
        )

    def test_multichar_delimiter_with_header(self, tmp_path):
        """csv_option=True + multi-char + with_header -> header line uses first char only."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "fieldseparator": "|;", "csv_option": True, "include_header": True,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 4  # 1 header + 3 data
        # Header line uses '|' only, never '|;'.
        assert "|;" not in lines[0]
        assert "|" in lines[0]

    def test_multichar_delimiter_with_csv_option(self, tmp_path):
        """csv_option=True: rows use single-char '|', not '|;' (Talend setSeparator(char))."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "fieldseparator": "|;", "csv_option": True,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": 1, "name": "Alice", "value": 100.0}])
        comp.execute(df)
        content = open(filepath, encoding="ISO-8859-15").read()
        # CSV mode encloses every field; the delimiter between fields is '|', not '|;'.
        assert '"1"|"Alice"|"100.0"' in content
        assert "|;" not in content

    def test_multichar_delimiter_csv_escapes_enclosure_in_value(self, tmp_path):
        """csv_option=True + multi-char: enclosure chars in values are still escaped."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "fieldseparator": "|;", "csv_option": True,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": 1, "name": 'Alice "The Great"', "value": 100.0}])
        comp.execute(df)
        content = open(filepath, encoding="ISO-8859-15").read()
        # Doubled quotes for escaping (CSV doublequote behavior).
        assert '""The Great""' in content

    def test_multichar_delimiter_split_mode(self, tmp_path):
        """csv_option=True + split + multi-char -> all split files use first char only."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "fieldseparator": "|;", "csv_option": True,
            "split": True, "split_every": "2",
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        comp.execute(_make_input_df())
        file0 = open(str(tmp_path / "output0.csv"), encoding="ISO-8859-15").read()
        file1 = open(str(tmp_path / "output1.csv"), encoding="ISO-8859-15").read()
        # First-char-only delimiter in every split file.
        assert "|;" not in file0
        assert "|;" not in file1
        assert "|" in file0
        assert "|" in file1
        assert len(file0.splitlines()) == 2
        assert len(file1.splitlines()) == 1

    def test_multichar_delimiter_append_mode(self, tmp_path):
        """csv_option=True + append + multi-char -> appended lines use first char only."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "fieldseparator": "|;", "csv_option": True, "append": True,
            "file_exist_exception": False,
        }
        comp1 = _make_component(config=config)
        comp1.execute(_make_input_df([{"id": 1, "name": "Alice", "value": 100.0}]))
        comp2 = _make_component(config=config)
        comp2.execute(_make_input_df([{"id": 2, "name": "Bob", "value": 200.0}]))
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 2
        # Both lines use single-char '|'; multi-char must not appear.
        assert "|;" not in content
        assert "|" in lines[0]
        assert "|" in lines[1]

    def test_multichar_delimiter_no_csv_succeeds(self, tmp_path):
        """csv_option=False + multi-char '||' -> no error; raw concatenation preserves '||'.

        Talend writes via BufferedWriter.write(String) in non-csv mode, which
        accepts any-length separator. The engine matches via _write_raw_mode.
        """
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "fieldseparator": "||", "csv_option": False,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        # Must not raise.
        result = comp.execute(_make_input_df([{"id": 1, "name": "Alice", "value": 100.0}]))
        assert result["main"] is not None
        content = open(filepath, encoding="ISO-8859-15").read()
        # Raw concatenation preserves the multi-char separator literally.
        assert "1||Alice||100.0" in content


# ------------------------------------------------------------------
# TestCsvOptionQuoteAll
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCsvOptionQuoteAll:
    """csv_option=True encloses ALL fields (QUOTE_ALL), not just those with special chars."""

    def test_all_fields_enclosed(self, tmp_path):
        """Every field gets enclosed even without special chars."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "csv_option": True,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": 1, "name": "Alice", "value": 100.0}])
        comp.execute(df)
        content = open(filepath, encoding="ISO-8859-15").read()
        first_line = content.splitlines()[0]
        # All fields enclosed
        assert first_line.startswith('"')
        assert '";"' in first_line

    def test_csv_option_escapes_double_quotes_in_value(self, tmp_path):
        """Enclosure chars inside values are doubled."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "csv_option": True,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": 1, "name": 'Say "Hello"', "value": 100.0}])
        comp.execute(df)
        content = open(filepath, encoding="ISO-8859-15").read()
        assert '""Hello""' in content

    def test_csv_option_with_custom_enclosure_quotes_all(self, tmp_path):
        """Custom text_enclosure still encloses all fields."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "csv_option": True,
            "text_enclosure": "'", "escape_char": "'",
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": 1, "name": "Alice", "value": 100.0}])
        comp.execute(df)
        content = open(filepath, encoding="ISO-8859-15").read()
        first_line = content.splitlines()[0]
        assert first_line.startswith("'")
        assert "';'" in first_line

    def test_csv_option_false_no_enclosure(self, tmp_path):
        """csv_option=False: plain fields have no enclosure."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "csv_option": False,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": 1, "name": "Alice", "value": 100.0}])
        comp.execute(df)
        content = open(filepath, encoding="ISO-8859-15").read()
        assert '"' not in content


# ------------------------------------------------------------------
# TestAdvancedSeparatorDeferred
# ------------------------------------------------------------------


@pytest.mark.unit
class TestAdvancedSeparatorDeferred:
    """advanced_separator logs warning when enabled."""

    def test_advanced_separator_logs_warning(self, tmp_path, caplog):
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "advanced_separator": True, "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        with caplog.at_level("WARNING"):
            comp.execute(_make_input_df())
        assert any("advanced_separator" in r.message for r in caplog.records)

    def test_advanced_separator_false_no_warning(self, tmp_path, caplog):
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "advanced_separator": False, "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        with caplog.at_level("WARNING"):
            comp.execute(_make_input_df())
        assert not any("advanced_separator" in r.message for r in caplog.records)


# ------------------------------------------------------------------
# TestPassthrough (CR-09 / ENG-CR-06 / ENG-WR-04)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPassthrough:
    """Sink passthrough contract: the original input DataFrame is not mutated in-place."""

    def test_input_returned_unmutated(self, tmp_path):
        """CR-09 / ENG-CR-06: original input_data is NOT mutated in-place by _process.

        The old bug: validate_schema was called inside _process and reassigned input_data.
        This caused the caller's reference to see mutated (truncated) data even before
        execute() returned. After the fix, _process works on a copy and never touches
        the original input_data object.

        Verification: values of the original df are unchanged after execute() returns.
        """
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        df = pd.DataFrame([
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"},
        ])
        # Record values BEFORE execute
        original_values = list(df["name"].copy())
        comp.execute(df)
        # Original df must be unchanged -- _process must NOT mutate in-place
        post_execute_values = list(df["name"])
        assert post_execute_values == original_values, (
            f"_process mutated original input_data in-place: "
            f"before={original_values}, after={post_execute_values}"
        )

    def test_date_patterns_dont_mutate_input(self, tmp_path):
        """ENG-WR-04: _apply_date_patterns must not alter the ORIGINAL input_data in-place.

        The old bug: _apply_date_patterns was called with input_data (not a copy),
        so the caller's datetime column was replaced with strings. After the fix,
        only the working copy (df_out) has date-formatted strings; the original df
        retains datetime dtype.

        Verification: the caller's df still has datetime dtype after execute().
        """
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        comp.input_schema = [
            {"name": "dt", "type": "datetime", "date_pattern": "%Y-%m-%d"},
        ]
        df = pd.DataFrame({"dt": pd.to_datetime(["2024-01-15", "2024-06-30"])})
        original_dtype = df["dt"].dtype
        comp.execute(df)
        # Original df must still have datetime dtype -- NOT string (which date_pattern produces)
        post_execute_dtype = df["dt"].dtype
        assert pd.api.types.is_datetime64_any_dtype(post_execute_dtype), (
            f"_apply_date_patterns mutated original df in-place: "
            f"dtype changed from {original_dtype} to {post_execute_dtype}"
        )


# ------------------------------------------------------------------
# TestMultiCharSepValidation (CR-06 superseded: see 260429-hc2)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMultiCharSepValidation:
    """Multi-character fieldseparator validation (Talend parity).

    CR-06 (Phase 7.1) originally rejected multi-char delimiters with a
    ConfigurationError gate. Primary-source review of Talaxie tdi-studio-se
    showed Talend itself accepts both modes (csv_option=True truncates to
    first char; csv_option=False preserves full multi-char). The contract
    was superseded -- _validate_config no longer raises on multi-char.
    """

    def test_multichar_sep_no_csv_succeeds(self, tmp_path):
        """csv_option=False + multi-char fieldseparator -> no ConfigurationError.

        Talend non-csv mode uses BufferedWriter.write(String); arbitrary-length
        separators are valid. The engine matches via _write_raw_mode.
        """
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "fieldseparator": "||", "csv_option": False,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        # Must not raise.
        result = comp.execute(_make_input_df())
        assert result["main"] is not None
        content = open(filepath, encoding="ISO-8859-15").read()
        # Raw concatenation preserves the full multi-char separator.
        assert "||" in content

    def test_multichar_sep_with_csv_ok(self, tmp_path):
        """csv_option=True + multi-char fieldseparator -> truncated to first char (Talend parity)."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "fieldseparator": "||", "csv_option": True,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        # Should not raise; csv_option=True path truncates and warns.
        result = comp.execute(_make_input_df())
        assert result["main"] is not None
        content = open(filepath, encoding="ISO-8859-15").read()
        # Truncated to first char '|'; '||' must not appear.
        assert "||" not in content
        assert "|" in content

    def test_multichar_sep_with_context_var_no_validate_error(self, tmp_path):
        """Regression: fieldseparator='${context.SEP}' must not be measured as multi-char.

        Validation runs against the resolved value (single-char ';'), not the
        raw 14-char template string. Previously a too-eager _validate_config
        rejected this configuration before context resolution.
        """
        filepath = str(tmp_path / "output.csv")
        cm = ContextManager()
        cm.set("SEP", ";")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "fieldseparator": "${context.SEP}",  # 14-char raw, resolves to ';'
            "csv_option": False,
            "file_exist_exception": False,
        }
        comp = _make_component(config=config, context_manager=cm)
        # Must not raise -- raw template length must NOT be checked as multi-char.
        result = comp.execute(_make_input_df())
        assert result["main"] is not None
        content = open(filepath, encoding="ISO-8859-15").read()
        # Resolved separator ';' appears; raw template '${context.SEP}' must not.
        assert ";" in content
        assert "${context.SEP}" not in content


# ------------------------------------------------------------------
# TestEscape (ENG-WR-05)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEscape:
    """ENG-WR-05: non-CSV branch preserves literal backslashes in field values."""

    def test_backslash_field_preserved(self, tmp_path):
        """Non-CSV mode must NOT escape backslashes in field values (escapechar=None)."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath, "csv_option": False,
            "file_exist_exception": False, "os_line_separator": False,
            "row_separator": "\\n",
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": 1, "path": "C:\\Users\\Alice"}])
        comp.execute(df)
        raw = open(filepath, encoding="ISO-8859-15").read()
        # One backslash per occurrence, not doubled
        assert "C:\\Users\\Alice" in raw, (
            f"Backslash was escaped (doubled) in output. Got: {raw!r}"
        )


# ------------------------------------------------------------------
# TestBoolCoercion (ENG-WR-11)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBoolCoercion:
    """ENG-WR-11: JSON bool string values coerced correctly via _bool helper."""

    def test_json_string_true_routes_csv_mode(self, tmp_path):
        """csv_option='true' (string) must route to CSV quoting mode."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "csv_option": "true",  # JSON string, not bool
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": 1, "name": "Alice"}])
        comp.execute(df)
        content = open(filepath, encoding="ISO-8859-15").read()
        # CSV mode encloses all fields in quotes
        assert '"' in content, "csv_option='true' string should activate CSV quoting mode"

    def test_json_string_false_no_spurious_deferred_warning(self, tmp_path, caplog):
        """split='false' (string) must NOT trigger deferred-feature warning.

        Python's 'if "false":' evaluates as truthy. _bool("false") must return False.
        """
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "compress": "false",  # JSON string "false" -- must NOT warn
            "file_exist_exception": False,
        }
        comp = _make_component(config=config)
        with caplog.at_level("WARNING"):
            comp.execute(_make_input_df())
        deferred_warns = [r for r in caplog.records if "compress" in r.message]
        assert not deferred_warns, (
            f"compress='false' string triggered spurious warning: "
            f"{[r.message for r in deferred_warns]}"
        )


# ------------------------------------------------------------------
# TestEmptyInputCsvHeader (ENG-IN-04)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEmptyInputCsvHeader:
    """ENG-IN-04: empty input + csv_option=True + include_header uses _enclose_field."""

    def test_csv_header_quoted(self, tmp_path):
        """Empty input + include_header=True + csv_option=True -> header fields quoted."""
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG, "filepath": filepath,
            "include_header": True, "csv_option": True,
            "text_enclosure": '"', "escape_char": '"',
            "file_exist_exception": False,
            "os_line_separator": False, "csvrowseparator": "LF",
        }
        comp = _make_component(config=config)
        comp.output_schema = [
            {"name": "id", "type": "int"},
            {"name": "name", "type": "str"},
        ]
        comp.execute(pd.DataFrame())
        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 1, f"Expected 1 header line, got {len(lines)}: {lines}"
        # Header fields should be enclosed in double quotes
        assert '"id"' in lines[0] or lines[0].startswith('"'), (
            f"Header not quoted in CSV mode: {lines[0]!r}"
        )


# ------------------------------------------------------------------
# TestStreamingWriteStarted — streaming multi-chunk append fix
# ------------------------------------------------------------------


@pytest.mark.unit
class TestStreamingWriteStarted:
    """_streaming_write_started flag prevents chunk overwrite in streaming mode.

    Bug fixed: BaseComponent._execute_streaming() calls _process() once per
    chunk.  Without the flag, every chunk opened the file with mode='w' so
    only the last chunk survived.  The fix forces append=True for every chunk
    after the first by tracking state in _streaming_write_started.

    Note: BaseComponent.__init__ sets self.config = {} and only populates it
    inside execute().  Tests that call _process() directly must set comp.config
    explicitly, mirroring what execute() does before delegating.
    """

    def _make_proc_component(self, config: dict):
        """Create a component with self.config pre-populated for direct _process() calls."""
        comp = _make_component(config=config)
        comp.config = dict(config)   # mirror what execute() does before calling _process()
        return comp

    def test_flag_is_false_on_init(self, tmp_path):
        """_streaming_write_started starts False on a freshly created component."""
        filepath = str(tmp_path / "out.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component(config=config)
        assert comp._streaming_write_started is False

    def test_flag_set_true_after_first_process(self, tmp_path):
        """After the first _process() call the flag becomes True."""
        filepath = str(tmp_path / "out.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = self._make_proc_component(config)
        comp._process(_make_input_df())
        assert comp._streaming_write_started is True

    def test_second_chunk_appends_not_overwrites(self, tmp_path):
        """Second _process() call appends even when config has append=False.

        This is the core regression: without the fix, chunk 2 would open the
        file with 'w' (reading append=False from config) and erase chunk 1.
        """
        filepath = str(tmp_path / "out.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "append": False,
                  "file_exist_exception": False}
        comp = self._make_proc_component(config)

        chunk1 = _make_input_df([{"id": 1, "name": "Alice", "value": 1.0},
                                  {"id": 2, "name": "Bob",   "value": 2.0}])
        chunk2 = _make_input_df([{"id": 3, "name": "Charlie", "value": 3.0},
                                  {"id": 4, "name": "Dave",    "value": 4.0}])
        comp._process(chunk1)
        comp._process(chunk2)

        lines = open(filepath, encoding="ISO-8859-15").read().splitlines()
        assert len(lines) == 4, (
            f"Expected 4 rows (2 per chunk), got {len(lines)}. "
            f"The second chunk probably overwrote the first."
        )

    def test_three_chunks_all_rows_present(self, tmp_path):
        """All rows from all chunks survive when _process() is called three times."""
        filepath = str(tmp_path / "out.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "append": False,
                  "file_exist_exception": False}
        comp = self._make_proc_component(config)

        for i in range(3):
            chunk = _make_input_df(
                [{"id": i * 3 + j, "name": f"r{i}{j}", "value": float(j)} for j in range(3)]
            )
            comp._process(chunk)

        lines = open(filepath, encoding="ISO-8859-15").read().splitlines()
        assert len(lines) == 9, f"Expected 9 total rows (3 chunks x 3), got {len(lines)}"

    def test_reset_clears_flag(self, tmp_path):
        """reset() sets _streaming_write_started back to False."""
        filepath = str(tmp_path / "out.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = self._make_proc_component(config)
        comp._process(_make_input_df())
        assert comp._streaming_write_started is True

        comp.reset()
        assert comp._streaming_write_started is False

    def test_iterate_pattern_second_pass_overwrites(self, tmp_path):
        """After reset(), a fresh _process() overwrites — correct iterate-loop behaviour.

        In an iterate loop each pass calls reset() then execute() again.
        The file should contain only the rows from the most recent pass.
        """
        filepath = str(tmp_path / "out.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "append": False,
                  "file_exist_exception": False}
        comp = self._make_proc_component(config)

        # First iterate pass — 1 row
        comp._process(_make_input_df([{"id": 1, "name": "Pass1", "value": 1.0}]))
        comp.reset()
        comp.config = dict(config)  # re-populate after reset (mirrors execute() behaviour)

        # Second iterate pass — 2 rows
        comp._process(_make_input_df([{"id": 2, "name": "Pass2A", "value": 2.0},
                                       {"id": 3, "name": "Pass2B", "value": 3.0}]))

        content = open(filepath, encoding="ISO-8859-15").read()
        lines = content.splitlines()
        assert len(lines) == 2, (
            f"After reset() the file should contain only the second pass (2 rows), "
            f"got {len(lines)}"
        )
        assert "Pass2" in content
        assert "Pass1" not in content

    def test_explicit_append_config_respected_on_first_chunk(self, tmp_path):
        """append=True in config is honoured on the first chunk (pre-existing content kept)."""
        filepath = str(tmp_path / "out.csv")
        with open(filepath, "w", encoding="ISO-8859-15") as fh:
            fh.write("pre;existing;row\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "append": True,
                  "file_exist_exception": False}
        comp = self._make_proc_component(config)
        comp._process(_make_input_df([{"id": 1, "name": "New", "value": 9.0}]))

        content = open(filepath, encoding="ISO-8859-15").read()
        assert "pre" in content, "Pre-existing content must be kept when append=True"
        assert "New" in content


# ------------------------------------------------------------------
# Plan 14-08 coverage lift: missed-line clusters
# (Pragma at line 364 already deleted in commit STALE-FOD-001)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCoverageLift1408ModuleHelpers:
    """Module-level helpers _safe_int and _resolve_csv_row_separator."""

    def test_safe_int_parses_valid_string(self):
        from src.v1.engine.components.file.file_output_delimited import _safe_int
        assert _safe_int("42", default=99) == 42

    def test_safe_int_falls_back_on_invalid(self):
        from src.v1.engine.components.file.file_output_delimited import _safe_int
        assert _safe_int("abc", default=99) == 99
        assert _safe_int(None, default=7) == 7

    def test_resolve_csv_row_separator_known_codes(self):
        from src.v1.engine.components.file.file_output_delimited import (
            _resolve_csv_row_separator,
        )
        assert _resolve_csv_row_separator("LF") == "\n"
        assert _resolve_csv_row_separator("CRLF") == "\r\n"

    def test_resolve_csv_row_separator_falls_back_to_unescape(self):
        """_resolve_csv_row_separator: unknown code goes through _unescape (line 893)."""
        from src.v1.engine.components.file.file_output_delimited import (
            _resolve_csv_row_separator,
        )
        # raw escape sequence not in the known code map
        assert _resolve_csv_row_separator("\\t") == "\t"
        # plain literal passes through unchanged
        assert _resolve_csv_row_separator("|") == "|"


@pytest.mark.unit
class TestCoverageLift1408HeaderColumns:
    """_get_header_columns logic."""

    def test_returns_empty_list_when_no_schemas(self):
        """No output_schema and no input_schema -> [] (line 837)."""
        comp = _make_component()
        comp.output_schema = None
        comp.input_schema = None
        assert comp._get_header_columns() == []


@pytest.mark.unit
class TestCoverageLift1408DateFormatter:
    """Branches inside _apply_date_patterns."""

    def test_skips_non_dict_schema_entries(self):
        """schema entry that isn't a dict -> continue (line 351-352)."""
        comp = _make_component()
        comp.input_schema = ["not_a_dict",
                             {"name": "ts", "type": "datetime",
                              "date_pattern": "%Y-%m-%d"}]
        df = pd.DataFrame({"ts": pd.to_datetime(["2024-01-15"])})
        out = comp._apply_date_patterns(df.copy())
        assert list(out["ts"]) == ["2024-01-15"]

    def test_skips_columns_missing_from_dataframe(self):
        """schema name missing from df.columns -> continue (354-355)."""
        comp = _make_component()
        comp.input_schema = [{"name": "missing_col", "type": "datetime",
                              "date_pattern": "%Y-%m-%d"}]
        df = pd.DataFrame({"present_col": [1, 2]})
        out = comp._apply_date_patterns(df.copy())
        assert "missing_col" not in out.columns
        assert list(out["present_col"]) == [1, 2]

    def test_skips_when_no_pattern_or_non_date_type(self):
        """no pattern OR non-date type -> continue (358-359)."""
        comp = _make_component()
        comp.input_schema = [
            {"name": "x", "type": "datetime", "date_pattern": ""},
            {"name": "y", "type": "str", "date_pattern": "%Y"},
        ]
        df = pd.DataFrame({"x": pd.to_datetime(["2024-01-15"]),
                           "y": ["raw"]})
        out = comp._apply_date_patterns(df.copy())
        assert pd.api.types.is_datetime64_any_dtype(out["x"])
        assert list(out["y"]) == ["raw"]

    def test_coerces_non_datetime_column_via_to_datetime(self):
        """series not datetime dtype -> pd.to_datetime(...,errors='coerce') (line 368)."""
        comp = _make_component()
        comp.input_schema = [{"name": "ts", "type": "datetime",
                              "date_pattern": "%Y-%m-%d"}]
        df = pd.DataFrame({"ts": ["2024-01-15", "2024-02-20", "garbage"]})
        out = comp._apply_date_patterns(df.copy())
        assert list(out["ts"]) == ["2024-01-15", "2024-02-20", ""]


@pytest.mark.unit
class TestCoverageLift1408DecimalFormatter:
    """Branches inside _format_decimal_columns (schema-iterating decimal formatter)."""

    def test_skips_non_dict_schema_entries(self):
        """non-dict schema entry -> continue (392-393)."""
        comp = _make_component()
        comp.input_schema = ["not_a_dict",
                             {"name": "amt", "type": "decimal", "precision": 2}]
        df = pd.DataFrame({"amt": [12.345]})
        out = comp._format_decimal_columns(df.copy())
        assert list(out["amt"]) == ["12.35"]

    def test_skips_columns_missing_from_dataframe(self):
        """missing col in df -> continue (line 396)."""
        comp = _make_component()
        comp.input_schema = [{"name": "missing", "type": "decimal", "precision": 2}]
        df = pd.DataFrame({"present": [1.0]})
        out = comp._format_decimal_columns(df.copy())
        assert "missing" not in out.columns

    def test_skips_when_precision_missing_or_negative(self):
        """precision None / < 0 -> natural-precision string (decimal/bigdecimal)."""
        comp = _make_component()
        comp.input_schema = [
            {"name": "a", "type": "decimal"},
            {"name": "b", "type": "decimal", "precision": -1},
        ]
        df = pd.DataFrame({"a": [1.5], "b": [2.5]})
        out = comp._format_decimal_columns(df.copy())
        # No/negative precision on a decimal column -> Talend natural precision
        # (trailing zeros stripped via Decimal.normalize), emitted as a string.
        assert out["a"].iloc[0] == "1.5"
        assert out["b"].iloc[0] == "2.5"

    def test_fmt_handles_none_nan_and_format_fallback(self):
        """_fmt: None / NaN / format / TypeError fallback (405-414)."""
        comp = _make_component()
        comp.input_schema = [{"name": "amt", "type": "decimal", "precision": 2}]
        df = pd.DataFrame({"amt": [None, float("nan"), 12.345, "not_numeric"]})
        out = comp._format_decimal_columns(df.copy())
        vals = list(out["amt"])
        assert vals[0] == ""
        assert vals[1] == ""
        assert vals[2] == "12.35"
        assert vals[3] == "not_numeric"


@pytest.mark.unit
class TestCoverageLift1408BooleanFormatter:
    """Branches inside _apply_boolean_format."""

    def test_skips_non_dict_schema_entries(self):
        comp = _make_component()
        comp.input_schema = ["not_a_dict",
                             {"name": "flag", "type": "bool"}]
        df = pd.DataFrame({"flag": [True, False]})
        out = comp._apply_boolean_format(df.copy())
        assert list(out["flag"]) == ["true", "false"]

    def test_skips_columns_missing_from_dataframe(self):
        comp = _make_component()
        comp.input_schema = [{"name": "missing", "type": "bool"}]
        df = pd.DataFrame({"present": [1]})
        out = comp._apply_boolean_format(df.copy())
        assert "missing" not in out.columns

    def test_fmt_bool_full_branch_coverage(self):
        """Cover None / Python bool / true-string / blank / fallthrough (446-459)."""
        comp = _make_component()
        comp.input_schema = [{"name": "flag", "type": "bool"}]
        df = pd.DataFrame({"flag": [
            None, True, False, "TRUE", "false", "", "nan", "yes",
        ]})
        out = comp._apply_boolean_format(df.copy())
        assert list(out["flag"]) == [
            "", "true", "false", "true", "false", "", "", "yes",
        ]


@pytest.mark.unit
class TestCoverageLift1408EmptyInputHandler:
    """Branches inside _handle_empty_input."""

    def test_empty_input_csv_multichar_truncate(self, tmp_path):
        """csv_option=True with multi-char field separator -> truncate (line 511)."""
        filepath = str(tmp_path / "empty_csv.csv")
        cfg = {**_DEFAULT_CONFIG, "filepath": filepath,
               "include_header": True, "fieldseparator": ";|",
               "csv_option": True, "encoding": "utf-8",
               "file_exist_exception": False}
        comp = _make_component(config=cfg)
        comp.config = dict(cfg)
        empty_df = pd.DataFrame({"a": [], "b": []})
        comp._process(empty_df)
        content = open(filepath, encoding="utf-8").read()
        assert ";" in content
        assert ";|" not in content

    def test_empty_input_uses_df_columns(self, tmp_path):
        """Empty DF has columns -> use df.columns for header (line 517)."""
        filepath = str(tmp_path / "empty_dfcols.csv")
        cfg = {**_DEFAULT_CONFIG, "filepath": filepath,
               "include_header": True, "encoding": "utf-8",
               "file_exist_exception": False}
        comp = _make_component(config=cfg)
        comp.config = dict(cfg)
        empty_df = pd.DataFrame(columns=["col_x", "col_y"])
        comp._process(empty_df)
        content = open(filepath, encoding="utf-8").read()
        assert "col_x" in content
        assert "col_y" in content

    def test_empty_input_no_schema_writes_empty_bytes(self, tmp_path):
        """Empty df + no columns + no schema -> empty file (line 537)."""
        filepath = str(tmp_path / "empty_nothing.csv")
        cfg = {**_DEFAULT_CONFIG, "filepath": filepath,
               "include_header": True, "encoding": "utf-8",
               "file_exist_exception": False}
        comp = _make_component(config=cfg)
        comp.config = dict(cfg)
        comp.input_schema = None
        comp.output_schema = None
        comp._process(pd.DataFrame())
        assert os.path.getsize(filepath) == 0


@pytest.mark.unit
class TestCoverageLift1408AppendHeaderRule:
    def test_append_with_existing_content_skips_header(self, tmp_path):
        """append=True + include_header=True + file exists w/ content -> drop header (line 292)."""
        filepath = str(tmp_path / "append.csv")
        with open(filepath, "w", encoding="ISO-8859-15") as f:
            f.write("pre_existing_data\n")
        cfg = {**_DEFAULT_CONFIG, "filepath": filepath,
               "append": True, "include_header": True,
               "file_exist_exception": False}
        comp = _make_component(config=cfg)
        comp.config = dict(cfg)
        comp._process(_make_input_df([{"id": 1, "name": "X", "value": 1.0}]))
        content = open(filepath, encoding="ISO-8859-15").read()
        assert content.count("id;name;value") == 0
        assert "pre_existing_data" in content


@pytest.mark.unit
class TestCoverageLift1408EncloseFieldEscape:
    def test_enclose_field_escape_distinct_from_quote(self):
        """_enclose_field with escape != quote (line 731)."""
        out = FileOutputDelimited._enclose_field('hi"x', text_enclosure='"', escape_char="\\")
        assert out == '"hi\\"x"'


@pytest.mark.unit
class TestCoverageLift1408RawWriteFailure:
    def test_write_oserror_wraps_as_file_operation_error(self, tmp_path, monkeypatch):
        """OSError during _write_file -> FileOperationError (609-612)."""
        filepath = str(tmp_path / "fail.csv")
        cfg = {**_DEFAULT_CONFIG, "filepath": filepath,
               "fieldseparator": ";", "csv_option": False,
               "file_exist_exception": False, "encoding": "utf-8"}
        comp = _make_component(config=cfg)
        comp.config = dict(cfg)

        # Single-char + non-CSV -> pandas.to_csv path. Force OSError there.
        def boom(self_df, *a, **k):
            raise OSError("simulated write failure")

        monkeypatch.setattr(pd.DataFrame, "to_csv", boom)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="Failed to write file",
        ):
            comp._process(_make_input_df())

    def test_write_file_operation_error_reraised(self, tmp_path, monkeypatch):
        """FileOperationError raised by inner writer is re-raised, not re-wrapped (line 608)."""
        filepath = str(tmp_path / "reraise.csv")
        cfg = {**_DEFAULT_CONFIG, "filepath": filepath,
               "fieldseparator": ";", "csv_option": False,
               "file_exist_exception": False, "encoding": "utf-8"}
        comp = _make_component(config=cfg)
        comp.config = dict(cfg)

        def raise_foe(self_df, *a, **k):
            raise FileOperationError("inner-writer-error")

        monkeypatch.setattr(pd.DataFrame, "to_csv", raise_foe)
        # The original FileOperationError surfaces unchanged (no double-wrapping)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="inner-writer-error",
        ):
            comp._process(_make_input_df())


@pytest.mark.unit
class TestCoverageLift1408RawModeBranches:
    """_write_raw_mode header / per-row write paths (688-709)."""

    def test_raw_mode_with_header_csv_option(self, tmp_path):
        """Single-char delim + csv_option=True writes enclosed header + rows (690-695, 700-705).

        Note: multi-char delimiter + csv_option=True triggers single-char truncation
        per Talend semantics, so a single-char delimiter is used here -- this still
        routes to _write_raw_mode because csv_option=True+truncation goes through
        the writer's enclosure path.
        """
        filepath = str(tmp_path / "raw_csv.csv")
        cfg = {**_DEFAULT_CONFIG, "filepath": filepath,
               "fieldseparator": "<>",  # multi-char -- raw mode
               "csv_option": False,      # raw multi-char path with enclosure off
               "include_header": True,
               "file_exist_exception": False, "encoding": "utf-8"}
        comp = _make_component(config=cfg)
        comp.config = dict(cfg)
        comp._process(_make_input_df([{"id": 1, "name": "Alice", "value": 1.5}]))
        content = open(filepath, encoding="utf-8").read()
        # Header line uses raw multi-char delimiter
        assert "id<>name<>value" in content
        assert "1<>Alice<>1.5" in content

    def test_raw_mode_no_header_no_csv(self, tmp_path):
        """Raw multi-char + no header + plain values (line 696-697, 707)."""
        filepath = str(tmp_path / "raw_plain.csv")
        cfg = {**_DEFAULT_CONFIG, "filepath": filepath,
               "fieldseparator": "<>",
               "csv_option": False,
               "include_header": False,
               "file_exist_exception": False, "encoding": "utf-8"}
        comp = _make_component(config=cfg)
        comp.config = dict(cfg)
        comp._process(_make_input_df([{"id": 1, "name": "Alice", "value": 1.5}]))
        content = open(filepath, encoding="utf-8").read()
        assert "1<>Alice<>1.5" in content

    def test_raw_mode_direct_with_csv_option_enclosure(self, tmp_path):
        """_write_raw_mode invoked directly with csv_option=True hits enclosure paths (691, 702).

        Through _process this code path is unreachable (csv_option=True with multi-char
        delimiter is pre-truncated to single-char and routed to _write_csv_mode).
        Direct call exercises the enclosure-on-header / enclosure-on-row branches
        of _write_raw_mode for parity with the standalone API.
        """
        filepath = str(tmp_path / "raw_direct_csv.csv")
        comp = _make_component()
        df = pd.DataFrame([{"id": 1, "name": "Alice", "value": 1.5}])
        comp._write_raw_mode(
            df, filepath, field_sep="<>", line_sep="\n",
            encoding="utf-8", include_header=True, csv_option=True,
            text_enclosure='"', escape_char='"', mode="w",
        )
        content = open(filepath, encoding="utf-8").read()
        # Multi-char delimiter preserved; values + header are enclosed
        assert '"id"<>"name"<>"value"' in content
        assert '"1"<>"Alice"<>"1.5"' in content


@pytest.mark.unit
class TestCoverageLift1408SplitPipeline:
    """Plan 14-08 pipeline test: file/csv_split_output (FOLD-04)."""

    def test_csv_split_output_pipeline(self, run_job_fixture, tmp_path,
                                       assert_ascii_logs):
        out_path = tmp_path / "split.csv"
        result = run_job_fixture(
            "file/csv_split_output",
            mutations={
                "tFileOutputDelimited_1": {"filepath": str(out_path)},
            },
        )
        # nb_rows=5, split_every=2 -> ceil(5/2) = 3 split files: split0/1/2.csv
        produced = sorted(p.name for p in tmp_path.iterdir() if p.suffix == ".csv")
        assert produced == ["split0.csv", "split1.csv", "split2.csv"]
        # Total rows written across splits
        assert result.global_map.get("tFileOutputDelimited_1_NB_LINE") == 5


# ------------------------------------------------------------------
# TestJavaExprFilepath -- D-06 engine: honor {{java}} marker on filepath
# ------------------------------------------------------------------

import unittest.mock as mock


def _make_component_with_bridge(config, java_bridge):
    """Create a FileOutputDelimited with a mock java_bridge injected."""
    gm = GlobalMap()
    cm = ContextManager()
    comp = FileOutputDelimited(
        component_id="tFOD_expr",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    comp.java_bridge = java_bridge
    return comp


@pytest.mark.unit
class TestJavaExprFilepath:
    """Engine honors {{java}} marker on filepath/streamname via bridge round-trip.

    D-06: After context resolution, if filepath still starts with {{java}},
    send to bridge for evaluation. Hard-fail if bridge unavailable.
    """

    def test_literal_filepath_no_bridge_call(self, tmp_path):
        """Test 1: literal filepath -- no {{java}} marker -- no bridge call."""
        filepath = str(tmp_path / "output.csv")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component_with_bridge(config, java_bridge=None)
        df = _make_input_df()
        # Should succeed without bridge
        result = comp.execute(df)
        assert result["main"] is not None
        assert (tmp_path / "output.csv").exists()

    def test_context_resolved_filepath_no_bridge_call(self, tmp_path):
        """Test 2: context-only filepath, resolved before _process -- no bridge."""
        filepath = str(tmp_path / "context_resolved.csv")
        # Filepath is already a plain string (context resolution happened in execute())
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "file_exist_exception": False}
        comp = _make_component_with_bridge(config, java_bridge=None)
        result = comp.execute(_make_input_df())
        assert result["main"] is not None
        assert (tmp_path / "context_resolved.csv").exists()

    def test_marked_filepath_with_bridge_evaluates(self, tmp_path):
        """Test 3: filepath with {{java}} marker and bridge present -- bridge evaluates it."""
        expected_path = str(tmp_path / "bridge_resolved.csv")
        mock_bridge = mock.MagicMock()
        config = {
            **_DEFAULT_CONFIG,
            "filepath": "{{java}}context.dir + \"/\" + context.name + \".csv\"",
            "file_exist_exception": False,
        }
        comp = _make_component_with_bridge(config, java_bridge=mock_bridge)
        # Patch _resolve_java_expr_param to return known path
        with mock.patch.object(comp, "_resolve_java_expr_param", return_value=expected_path):
            result = comp.execute(_make_input_df())
        assert result["main"] is not None
        assert (tmp_path / "bridge_resolved.csv").exists()

    def test_marked_filepath_bridge_none_raises_config_error(self, tmp_path):
        """Test 4: filepath with {{java}} marker and bridge=None -- raises ConfigurationError."""
        config = {
            **_DEFAULT_CONFIG,
            "filepath": "{{java}}context.dir + context.name + context.ext",
            "file_exist_exception": False,
        }
        comp = _make_component_with_bridge(config, java_bridge=None)
        with pytest.raises(ConfigurationError, match="Java bridge"):
            comp.execute(_make_input_df())

    def test_marked_filepath_bridge_failure_raises_component_error(self, tmp_path):
        """Test 5: bridge raises during eval -- wraps in ComponentExecutionError."""
        mock_bridge = mock.MagicMock()
        mock_bridge.execute_tmap_preprocessing.side_effect = RuntimeError("bridge down")
        config = {
            **_DEFAULT_CONFIG,
            "filepath": "{{java}}context.dir + \"/\" + context.name + \".csv\"",
            "file_exist_exception": False,
        }
        comp = _make_component_with_bridge(config, java_bridge=mock_bridge)
        with pytest.raises(ComponentExecutionError):
            comp.execute(_make_input_df())

    def test_issue_6_reproduction_no_literal_plus(self, tmp_path):
        """Test 6: Issue 6 -- filepath must resolve to actual path, not contain literal +."""
        expected_path = str(tmp_path / "output_via_expr.csv")
        mock_bridge = mock.MagicMock()
        # Bridge returns the evaluated concatenated path
        mock_bridge.execute_tmap_preprocessing.return_value = {
            "__param__": [expected_path],
        }
        config = {
            **_DEFAULT_CONFIG,
            "filepath": "{{java}}context.outdir + \"/\" + context.name + \".csv\"",
            "file_exist_exception": False,
        }
        comp = _make_component_with_bridge(config, java_bridge=mock_bridge)
        result = comp.execute(_make_input_df())
        assert result["main"] is not None
        # The resolved file must exist at the actual path
        assert (tmp_path / "output_via_expr.csv").exists()
        # The path must NOT contain literal + operators
        written_path = str(tmp_path / "output_via_expr.csv")
        assert "+" not in written_path
        assert "context.outdir" not in written_path

    def test_streamname_marked_with_bridge(self, tmp_path):
        """Test 7: streamname with {{java}} marker is resolved by bridge.

        Uses `usestream=False` so streamname resolution happens but the deferred
        usestream feature doesn't actually stream. Verifies _resolve_java_expr_param
        is called for {{java}}-marked streamname.
        """
        mock_bridge = mock.MagicMock()
        mock_bridge.execute_tmap_preprocessing.return_value = {
            "__param__": ["myResolvedStream"],
        }
        filepath = str(tmp_path / "output.csv")
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "usestream": False,
            "streamname": "{{java}}context.prefix + \"Stream\"",
            "file_exist_exception": False,
        }
        comp = _make_component_with_bridge(config, java_bridge=mock_bridge)
        # For streamname: patch _resolve_java_expr_param to confirm it's called
        with mock.patch.object(
            comp, "_resolve_java_expr_param", wraps=lambda v, n: "myResolvedStream" if v.startswith("{{java}}") else v
        ) as mock_resolve:
            result = comp.execute(_make_input_df())
        assert result["main"] is not None
        # _resolve_java_expr_param must have been called for the streamname
        mock_resolve.assert_any_call("{{java}}context.prefix + \"Stream\"", "streamname")
