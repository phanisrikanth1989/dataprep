"""Tests for FileInputFullRowComponent (tFileInputFullRow engine implementation)."""
import pytest
import pandas as pd

from src.v1.engine.components.file.file_input_fullrow import FileInputFullRowComponent
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, FileOperationError, ComponentExecutionError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "FileInputFullRowComponent",
    "filename": "/tmp/placeholder.txt",  # overridden per test via tmp_path
    "row_separator": "\\n",
    "header_rows": 0,
    "footer_rows": 0,
    "limit": "",
    "remove_empty_row": True,
    "encoding": "ISO-8859-15",
    "random": False,
    "nb_random": 10,
}


def _make_component(config=None, global_map=None, context_manager=None, schema=None):
    """Create a FileInputFullRowComponent with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    comp = FileInputFullRowComponent(
        component_id="tFIFR_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    if schema is not None:
        comp.output_schema = schema
    return comp


def _write_file(tmp_path, filename, content, encoding="iso-8859-15"):
    """Write content to file, return path as string."""
    f = tmp_path / filename
    f.write_bytes(content.encode(encoding))
    return str(f)


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    """Both V1 and Talend alias are registered in REGISTRY."""

    def test_v1_name_registered(self):
        assert "FileInputFullRowComponent" in REGISTRY

    def test_talend_alias_registered(self):
        assert "tFileInputFullRow" in REGISTRY

    def test_both_map_to_same_class(self):
        assert REGISTRY.get("FileInputFullRowComponent") is REGISTRY.get("tFileInputFullRow")

    def test_registered_class_is_correct(self):
        assert REGISTRY.get("tFileInputFullRow") is FileInputFullRowComponent


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for missing/invalid filename."""

    def test_missing_filename_raises(self):
        config = dict(_DEFAULT_CONFIG)
        del config["filename"]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="filename"):
            comp.execute(None)

    def test_empty_filename_raises(self):
        config = {**_DEFAULT_CONFIG, "filename": ""}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="filename"):
            comp.execute(None)

    def test_none_filename_raises(self):
        config = {**_DEFAULT_CONFIG, "filename": None}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="filename"):
            comp.execute(None)

    def test_valid_config_does_not_raise(self, tmp_path):
        filepath = _write_file(tmp_path, "valid.txt", "line1\nline2\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert result["main"] is not None

    def test_invalid_limit_raises(self, tmp_path):
        filepath = _write_file(tmp_path, "test.txt", "a\nb\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "limit": "abc"}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="limit"):
            comp.execute(None)

    def test_file_not_found_raises_file_operation_error(self, tmp_path):
        # FileOperationError from _process() is wrapped in ComponentExecutionError by BaseComponent
        config = {**_DEFAULT_CONFIG, "filename": str(tmp_path / "nonexistent.txt")}
        comp = _make_component(config=config)
        with pytest.raises((FileOperationError, ComponentExecutionError), match="not found"):
            comp.execute(None)


# ------------------------------------------------------------------
# TestCoreReading
# ------------------------------------------------------------------

@pytest.mark.unit
class TestCoreReading:
    """Basic file reading, column naming, encoding."""

    def test_reads_lines_as_single_column(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "alpha\nbeta\ngamma\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "remove_empty_row": False}
        comp = _make_component(config=config)
        result = comp.execute(None)
        df = result["main"]
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["line"]
        assert list(df["line"]) == ["alpha", "beta", "gamma", ""]

    def test_default_column_name_is_line(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "hello\nworld\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert "line" in result["main"].columns

    def test_schema_column_name_overrides_default(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "row1\nrow2\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath}
        schema = [{"name": "raw_text", "type": "str", "nullable": True}]
        comp = _make_component(config=config, schema=schema)
        result = comp.execute(None)
        assert "raw_text" in result["main"].columns
        assert "line" not in result["main"].columns

    def test_iso_8859_15_encoding_default(self, tmp_path):
        # Write a plain ASCII file and confirm ISO-8859-15 encoding reads it correctly
        filepath = str(tmp_path / "encoded.txt")
        with open(filepath, "wb") as f:
            f.write(b"line1\nline2\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "encoding": "ISO-8859-15"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["line1", "line2"]

    def test_custom_row_separator(self, tmp_path):
        # Use || as separator
        filepath = _write_file(tmp_path, "data.txt", "a||b||c")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "row_separator": "||", "remove_empty_row": False}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["a", "b", "c"]

    def test_tab_escape_sequence_separator(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "a\tb\tc")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "row_separator": "\\t", "remove_empty_row": False}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["a", "b", "c"]

    def test_windows_line_endings_normalised(self, tmp_path):
        # File has CRLF; engine should produce same result as LF
        filepath = str(tmp_path / "crlf.txt")
        with open(filepath, "wb") as f:
            f.write(b"line1\r\nline2\r\nline3\r\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "remove_empty_row": True}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["line1", "line2", "line3"]

    def test_no_reject_key_in_result(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "a\nb\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        # tFileInputFullRow has no REJECT connector in Talend
        assert result.get("reject") is None


# ------------------------------------------------------------------
# TestHeaderFooter
# ------------------------------------------------------------------

@pytest.mark.unit
class TestHeaderFooter:
    """Header and footer row skipping."""

    def test_header_rows_skipped(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "HDR1\nHDR2\ndata1\ndata2\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "header_rows": 2}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["data1", "data2"]

    def test_footer_rows_skipped(self, tmp_path):
        # No trailing newline so split gives exactly 4 tokens: footer removes last 2
        filepath = _write_file(tmp_path, "data.txt", "data1\ndata2\nFTR1\nFTR2")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "footer_rows": 2, "remove_empty_row": False}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["data1", "data2"]

    def test_header_and_footer_both_skipped(self, tmp_path):
        # No trailing newline so split gives exactly 4 tokens: H1, data1, data2, F1
        filepath = _write_file(tmp_path, "data.txt", "H1\ndata1\ndata2\nF1")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "header_rows": 1, "footer_rows": 1, "remove_empty_row": False}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["data1", "data2"]

    def test_zero_header_footer_no_skip(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "a\nb\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "header_rows": 0, "footer_rows": 0}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["a", "b"]

    def test_footer_larger_than_content_returns_empty(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "a\nb\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "footer_rows": 10}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 0


# ------------------------------------------------------------------
# TestEmptyRowRemoval
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEmptyRowRemoval:
    """Talend parity: remove_empty_row removes strictly-empty lines only."""

    def test_remove_empty_row_true_drops_empty_strings(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "a\n\nb\n\nc\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "remove_empty_row": True}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["a", "b", "c"]

    def test_remove_empty_row_true_keeps_whitespace_only_lines(self, tmp_path):
        # Talend parity: "" == empty, "   " is NOT empty
        filepath = _write_file(tmp_path, "data.txt", "a\n   \nb\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "remove_empty_row": True}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["a", "   ", "b"]

    def test_remove_empty_row_false_keeps_empty_strings(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "a\n\nb\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "remove_empty_row": False}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert "" in list(result["main"]["line"])

    def test_default_remove_empty_row_is_true(self, tmp_path):
        """Talend default is True — engine must match."""
        filepath = _write_file(tmp_path, "data.txt", "x\n\ny\n")
        config = dict(_DEFAULT_CONFIG)
        config["filename"] = filepath
        comp = _make_component(config=config)
        result = comp.execute(None)
        # Default remove_empty_row=True → empty lines dropped
        assert list(result["main"]["line"]) == ["x", "y"]


# ------------------------------------------------------------------
# TestLimit
# ------------------------------------------------------------------

@pytest.mark.unit
class TestLimit:
    """Limit behaviour including Talend parity for 0 = unlimited."""

    def test_limit_restricts_row_count(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "1\n2\n3\n4\n5\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "limit": "3"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 3

    def test_limit_empty_string_means_unlimited(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "1\n2\n3\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "limit": ""}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 3

    def test_limit_zero_means_unlimited(self, tmp_path):
        """Talend parity: LIMIT=0 means no limit, not zero rows."""
        filepath = _write_file(tmp_path, "data.txt", "1\n2\n3\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "limit": "0"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 3

    def test_limit_larger_than_file_returns_all(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "a\nb\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "limit": "1000"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2


# ------------------------------------------------------------------
# TestRandom
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRandom:
    """Random line extraction mode."""

    def test_random_returns_nb_random_lines(self, tmp_path):
        lines = "\n".join(str(i) for i in range(100))
        filepath = _write_file(tmp_path, "data.txt", lines)
        config = {**_DEFAULT_CONFIG, "filename": filepath, "random": True, "nb_random": 10}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 10

    def test_random_nb_larger_than_file_returns_all(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "a\nb\nc\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "random": True, "nb_random": 100}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 3  # only 3 non-empty lines

    def test_random_false_returns_sequential(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "1\n2\n3\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "random": False, "limit": "2"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["1", "2"]

    def test_random_lines_are_subset_of_file(self, tmp_path):
        all_lines = [str(i) for i in range(50)]
        filepath = _write_file(tmp_path, "data.txt", "\n".join(all_lines))
        config = {**_DEFAULT_CONFIG, "filename": filepath, "random": True, "nb_random": 5}
        comp = _make_component(config=config)
        result = comp.execute(None)
        for val in result["main"]["line"]:
            assert val in all_lines


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    """GlobalMap stats set correctly."""

    def test_stats_total_read_reflects_raw_lines(self, tmp_path):
        # File has 5 lines including 1 empty; remove_empty_row=True drops it.
        # NB_LINE = 5 (total after split), NB_LINE_OK = 4 (non-empty)
        filepath = _write_file(tmp_path, "data.txt", "a\nb\n\nc\nd\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "remove_empty_row": True}
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        comp.execute(None)
        assert gm.get("tFIFR_1_NB_LINE_OK") == 4

    def test_stats_nb_line_reject_is_zero(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "a\nb\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath}
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        comp.execute(None)
        assert gm.get("tFIFR_1_NB_LINE_REJECT", 0) == 0


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEdgeCases:
    """Empty file, single line, multi-char separator, context var filename."""

    def test_empty_file_returns_empty_dataframe(self, tmp_path):
        # Empty file: split("", "\n") gives [""] -- remove_empty_row=True drops it → 0 rows
        filepath = _write_file(tmp_path, "empty.txt", "")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "remove_empty_row": True}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0

    def test_single_line_no_trailing_newline(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "only_line")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "remove_empty_row": False}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["only_line"]

    def test_multichar_separator(self, tmp_path):
        filepath = _write_file(tmp_path, "data.txt", "a---b---c")
        config = {**_DEFAULT_CONFIG, "filename": filepath, "row_separator": "---", "remove_empty_row": False}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["a", "b", "c"]

    def test_input_data_is_ignored(self, tmp_path):
        """Source component: input_data passed by engine is ignored."""
        filepath = _write_file(tmp_path, "data.txt", "hello\n")
        config = {**_DEFAULT_CONFIG, "filename": filepath}
        comp = _make_component(config=config)
        dummy_input = pd.DataFrame({"x": [1, 2, 3]})
        result = comp.execute(dummy_input)
        assert list(result["main"]["line"]) == ["hello"]

    def test_header_footer_applied_before_limit(self, tmp_path):
        # File: H1, data1..data5, F1 → skip 1 header + 1 footer → 5 data rows → limit 2
        lines = ["H1", "data1", "data2", "data3", "data4", "data5", "F1"]
        filepath = _write_file(tmp_path, "data.txt", "\n".join(lines))
        config = {
            **_DEFAULT_CONFIG,
            "filename": filepath,
            "header_rows": 1,
            "footer_rows": 1,
            "limit": "2",
            "remove_empty_row": False,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert list(result["main"]["line"]) == ["data1", "data2"]
