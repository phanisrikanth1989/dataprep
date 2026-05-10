"""Tests for FileOutputPositional (tFileOutputPositional engine implementation).

Coverage:
    - Registration under both V1 and Talend names
    - _validate_config raises ConfigurationError for structural errors only
    - _process content validation (size, align, keep, flushonrow_num)
    - Basic write: fixed-width output matches expected layout
    - Header row on/off
    - Append mode
    - Encoding
    - Alignment: L, R, C (and full-word LEFT/RIGHT/CENTER)
    - KEEP modes: ALL, LEFT, MIDDLE, RIGHT (and legacy single-letter aliases)
    - Gzip compression (write and append)
    - delete_empty_file
    - flushonrow / flushonrow_num config key aliases
    - Statistics: NB_LINE, NB_LINE_OK, NB_LINE_REJECT
    - Pass-through: 'main' output equals original input DataFrame
"""
import gzip
import os

import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.file.file_output_positional import FileOutputPositional
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_SIMPLE_FORMATS = [
    {"schema_column": "name", "size": 10, "align": "L", "padding_char": " "},
    {"schema_column": "age",  "size":  5, "align": "R", "padding_char": "0"},
]

_SIMPLE_DATA = pd.DataFrame({"name": ["Alice", "Bob"], "age": ["25", "30"]})


def _make_component(config: dict, input_schema=None):
    comp = FileOutputPositional(
        component_id="tFOP_test",
        config=config,
        global_map=GlobalMap(),
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    comp.input_schema = input_schema or []
    return comp


def _read_text(path: str, encoding: str = "ISO-8859-15") -> str:
    with open(path, encoding=encoding) as fh:
        return fh.read()


# ------------------------------------------------------------------
# 1. Registration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component must be discoverable under both registry names."""

    def test_v1_name_registered(self):
        assert REGISTRY.get("FileOutputPositional") is FileOutputPositional

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tFileOutputPositional") is FileOutputPositional


# ------------------------------------------------------------------
# 2. _validate_config
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidateConfig:
    """_validate_config must raise ConfigurationError for structural gaps."""

    def test_missing_filepath_raises(self):
        comp = _make_component({"formats": _SIMPLE_FORMATS})
        with pytest.raises(ConfigurationError, match="filepath"):
            comp._validate_config()

    def test_missing_formats_raises(self):
        comp = _make_component({"filepath": "/tmp/out.txt"})
        with pytest.raises(ConfigurationError, match="formats"):
            comp._validate_config()

    def test_formats_not_list_raises(self):
        comp = _make_component({"filepath": "/tmp/out.txt", "formats": "bad"})
        with pytest.raises(ConfigurationError, match="formats"):
            comp._validate_config()

    def test_empty_formats_raises(self):
        comp = _make_component({"filepath": "/tmp/out.txt", "formats": []})
        with pytest.raises(ConfigurationError, match="formats"):
            comp._validate_config()

    def test_format_missing_schema_column_raises(self):
        comp = _make_component({
            "filepath": "/tmp/out.txt",
            "formats": [{"size": 10}],
        })
        with pytest.raises(ConfigurationError, match="schema_column"):
            comp._validate_config()

    def test_format_missing_size_raises(self):
        comp = _make_component({
            "filepath": "/tmp/out.txt",
            "formats": [{"schema_column": "col1"}],
        })
        with pytest.raises(ConfigurationError, match="size"):
            comp._validate_config()

    def test_valid_config_does_not_raise(self):
        comp = _make_component({"filepath": "/tmp/out.txt", "formats": _SIMPLE_FORMATS})
        comp._validate_config()  # Must not raise


# ------------------------------------------------------------------
# 3. Content validation deferred to _process
# ------------------------------------------------------------------


@pytest.mark.unit
class TestProcessContentValidation:
    """Content checks (size range, align enum, keep enum) run in _process."""

    def test_size_zero_raises_config_error(self, tmp_path):
        # size=0 passes structural _validate_config (key present) but fails content check
        comp = _make_component({
            "filepath": str(tmp_path / "out.txt"),
            "formats": [{"schema_column": "x", "size": "0"}],  # String '0' int converts to 0
        })
        with pytest.raises(ConfigurationError, match="size.*positive"):
            comp._process(_SIMPLE_DATA)

    def test_size_non_integer_raises_config_error(self, tmp_path):
        comp = _make_component({
            "filepath": str(tmp_path / "out.txt"),
            "formats": [{"schema_column": "x", "size": "bad"}],
        })
        with pytest.raises(ConfigurationError, match="size.*integer"):
            comp._process(_SIMPLE_DATA)

    def test_invalid_align_raises_config_error(self, tmp_path):
        comp = _make_component({
            "filepath": str(tmp_path / "out.txt"),
            "formats": [{"schema_column": "x", "size": 5, "align": "Z"}],
        })
        with pytest.raises(ConfigurationError, match="align"):
            comp._process(_SIMPLE_DATA)

    def test_invalid_keep_raises_config_error(self, tmp_path):
        comp = _make_component({
            "filepath": str(tmp_path / "out.txt"),
            "formats": [{"schema_column": "x", "size": 5, "keep": "NOPE"}],
        })
        with pytest.raises(ConfigurationError, match="keep"):
            comp._process(_SIMPLE_DATA)

    def test_flushonrow_num_zero_raises(self, tmp_path):
        comp = _make_component({
            "filepath": str(tmp_path / "out.txt"),
            "formats": _SIMPLE_FORMATS,
            "flushonrow_num": 0,
        })
        with pytest.raises(ConfigurationError, match="flushonrow_num.*positive"):
            comp._process(_SIMPLE_DATA)


# ------------------------------------------------------------------
# 4. Basic write
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBasicWrite:
    """Written file must match expected fixed-width layout."""

    def test_two_rows_no_header(self, tmp_path):
        out = str(tmp_path / "out.txt")
        comp = _make_component({
            "filepath": out,
            "formats": _SIMPLE_FORMATS,
            "include_header": False,
        })
        comp._process(_SIMPLE_DATA)
        content = _read_text(out)
        lines = content.splitlines()
        assert len(lines) == 2
        # name: 10 chars left-aligned, age: 5 chars right-aligned with '0'
        assert lines[0] == "Alice     00025"
        assert lines[1] == "Bob       00030"

    def test_passthrough_returns_original_df(self, tmp_path):
        out = str(tmp_path / "out.txt")
        comp = _make_component({"filepath": out, "formats": _SIMPLE_FORMATS})
        result = comp._process(_SIMPLE_DATA)
        assert result["main"] is _SIMPLE_DATA

    def test_creates_output_directory(self, tmp_path):
        out = str(tmp_path / "subdir" / "out.txt")
        comp = _make_component({"filepath": out, "formats": _SIMPLE_FORMATS})
        comp._process(_SIMPLE_DATA)
        assert os.path.exists(out)


# ------------------------------------------------------------------
# 5. Header row
# ------------------------------------------------------------------


@pytest.mark.unit
class TestHeaderRow:
    """include_header default is False; True writes column names as first row."""

    def test_default_no_header(self, tmp_path):
        out = str(tmp_path / "out.txt")
        comp = _make_component({"filepath": out, "formats": _SIMPLE_FORMATS})
        comp._process(_SIMPLE_DATA)
        content = _read_text(out)
        assert "name" not in content  # no header

    def test_include_header_true(self, tmp_path):
        out = str(tmp_path / "out.txt")
        comp = _make_component({
            "filepath": out,
            "formats": _SIMPLE_FORMATS,
            "include_header": True,
        })
        comp._process(_SIMPLE_DATA)
        first_line = _read_text(out).splitlines()[0]
        assert first_line.startswith("name")
        assert "age" in first_line


# ------------------------------------------------------------------
# 6. Append mode
# ------------------------------------------------------------------


@pytest.mark.unit
class TestAppendMode:
    """append=True adds rows; append=False overwrites."""

    def test_append_adds_rows(self, tmp_path):
        out = str(tmp_path / "out.txt")
        cfg = {"filepath": out, "formats": _SIMPLE_FORMATS, "include_header": False}
        comp = _make_component(cfg)
        comp._process(_SIMPLE_DATA)
        comp2 = _make_component({**cfg, "append": True})
        comp2._process(_SIMPLE_DATA)
        lines = _read_text(out).splitlines()
        assert len(lines) == 4

    def test_no_append_overwrites(self, tmp_path):
        out = str(tmp_path / "out.txt")
        cfg = {"filepath": out, "formats": _SIMPLE_FORMATS, "include_header": False}
        _make_component(cfg)._process(_SIMPLE_DATA)
        _make_component(cfg)._process(_SIMPLE_DATA)  # second write -- same data
        lines = _read_text(out).splitlines()
        assert len(lines) == 2


# ------------------------------------------------------------------
# 7. Encoding
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEncoding:
    """Default encoding is ISO-8859-15; explicit UTF-8 also works."""

    def test_default_encoding_is_iso_8859_15(self):
        assert FileOutputPositional.DEFAULT_ENCODING == 'ISO-8859-15'

    def test_explicit_utf8(self, tmp_path):
        out = str(tmp_path / "out.txt")
        df = pd.DataFrame({"name": ["Ünïcödé"], "age": ["1"]})
        comp = _make_component({
            "filepath": out,
            "formats": _SIMPLE_FORMATS,
            "encoding": "utf-8",
            "include_header": False,
        })
        comp._process(df)
        content = _read_text(out, encoding="utf-8")
        assert "Ünïcödé" in content


# ------------------------------------------------------------------
# 8. Alignment
# ------------------------------------------------------------------


@pytest.mark.unit
class TestAlignment:
    """L, R, C alignments; full-word LEFT/RIGHT/CENTER are normalised."""

    _FMT_L  = [{"schema_column": "v", "size": 8, "align": "L",      "padding_char": "_"}]
    _FMT_R  = [{"schema_column": "v", "size": 8, "align": "R",      "padding_char": "_"}]
    _FMT_C  = [{"schema_column": "v", "size": 8, "align": "C",      "padding_char": "_"}]
    _FMT_LW = [{"schema_column": "v", "size": 8, "align": "LEFT",   "padding_char": "_"}]
    _FMT_CW = [{"schema_column": "v", "size": 8, "align": "CENTER", "padding_char": "_"}]

    def _run(self, tmp_path, formats, data_val="hi"):
        out = str(tmp_path / "out.txt")
        df = pd.DataFrame({"v": [data_val]})
        comp = _make_component({"filepath": out, "formats": formats, "include_header": False})
        comp._process(df)
        return _read_text(out).rstrip("\n")

    def test_left_align(self, tmp_path):
        assert self._run(tmp_path, self._FMT_L) == "hi______"

    def test_right_align(self, tmp_path):
        assert self._run(tmp_path, self._FMT_R) == "______hi"

    def test_center_align(self, tmp_path):
        result = self._run(tmp_path, self._FMT_C)
        assert result == "___hi___"

    def test_full_word_left_normalised(self, tmp_path):
        assert self._run(tmp_path, self._FMT_LW) == "hi______"

    def test_full_word_center_normalised(self, tmp_path):
        result = self._run(tmp_path, self._FMT_CW)
        assert result == "___hi___"


# ------------------------------------------------------------------
# 9. KEEP modes
# ------------------------------------------------------------------


@pytest.mark.unit
class TestKeepModes:
    """ALL keeps full value; LEFT/MIDDLE/RIGHT truncate accordingly."""

    _SIZE = 5

    def _run_keep(self, tmp_path, keep: str, value: str = "ABCDEFGH") -> str:
        out = str(tmp_path / "out.txt")
        df = pd.DataFrame({"v": [value]})
        fmt = [{"schema_column": "v", "size": self._SIZE, "keep": keep,
                "align": "L", "padding_char": " "}]
        comp = _make_component({"filepath": out, "formats": fmt, "include_header": False})
        comp._process(df)
        return _read_text(out).rstrip("\n")

    def test_keep_all_allows_overflow(self, tmp_path):
        result = self._run_keep(tmp_path, "ALL")
        assert result == "ABCDEFGH"  # No truncation

    def test_keep_left_keeps_first_n(self, tmp_path):
        result = self._run_keep(tmp_path, "LEFT")
        assert result == "ABCDE"

    def test_keep_right_keeps_last_n(self, tmp_path):
        result = self._run_keep(tmp_path, "RIGHT")
        assert result == "DEFGH"

    def test_keep_middle_keeps_center_n(self, tmp_path):
        result = self._run_keep(tmp_path, "MIDDLE")
        # len=8, size=5: start=(8-5)//2=1 -> "BCDEF"
        assert result == "BCDEF"

    def test_keep_no_truncation_when_value_fits(self, tmp_path):
        result = self._run_keep(tmp_path, "LEFT", value="AB")
        # value shorter than size -- should be padded
        assert result == "AB   "

    def test_legacy_alias_a_maps_to_all(self, tmp_path):
        """Old single-letter 'A' must behave like ALL."""
        result = self._run_keep(tmp_path, "A")
        assert result == "ABCDEFGH"

    def test_legacy_alias_c_maps_to_left(self, tmp_path):
        """Old single-letter 'C' (legacy cut) must keep first N chars."""
        result = self._run_keep(tmp_path, "C")
        assert result == "ABCDE"


# ------------------------------------------------------------------
# 10. Gzip compression
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGzipCompression:
    """compress=True produces valid gzip output."""

    def test_compressed_output_is_valid_gzip(self, tmp_path):
        out = str(tmp_path / "out.txt.gz")
        comp = _make_component({
            "filepath": out,
            "formats": _SIMPLE_FORMATS,
            "compress": True,
            "include_header": False,
        })
        comp._process(_SIMPLE_DATA)
        with gzip.open(out, "rb") as f:
            content = f.read().decode("ISO-8859-15")
        assert "Alice" in content

    def test_compress_without_append_overwrites(self, tmp_path):
        out = str(tmp_path / "out.gz")
        cfg = {
            "filepath": out, "formats": _SIMPLE_FORMATS,
            "compress": True, "include_header": False,
        }
        _make_component(cfg)._process(_SIMPLE_DATA)
        _make_component(cfg)._process(_SIMPLE_DATA)  # BUG-FOP-003 fix: should overwrite
        with gzip.open(out, "rb") as f:
            lines = f.read().decode("ISO-8859-15").splitlines()
        assert len(lines) == 2, "Second write should overwrite, not append"

    def test_compress_with_append_appends(self, tmp_path):
        out = str(tmp_path / "out.gz")
        cfg_first  = {"filepath": out, "formats": _SIMPLE_FORMATS, "compress": True,
                      "include_header": False, "append": False}
        cfg_append = {**cfg_first, "append": True}
        _make_component(cfg_first)._process(_SIMPLE_DATA)
        _make_component(cfg_append)._process(_SIMPLE_DATA)
        with gzip.open(out, "rb") as f:
            lines = f.read().decode("ISO-8859-15").splitlines()
        assert len(lines) == 4


# ------------------------------------------------------------------
# 11. delete_empty_file
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDeleteEmptyFile:
    """delete_empty_file=True removes file when input is empty."""

    def test_empty_input_deletes_existing_file(self, tmp_path):
        out = str(tmp_path / "out.txt")
        out_path = tmp_path / "out.txt"
        out_path.write_text("existing")  # pre-create
        comp = _make_component({
            "filepath": out,
            "formats": _SIMPLE_FORMATS,
            "delete_empty_file": True,
        })
        comp._process(pd.DataFrame())
        assert not os.path.exists(out)

    def test_empty_input_without_flag_does_not_delete(self, tmp_path):
        out = str(tmp_path / "out.txt")
        out_path = tmp_path / "out.txt"
        out_path.write_text("existing")
        comp = _make_component({
            "filepath": out,
            "formats": _SIMPLE_FORMATS,
            "delete_empty_file": False,
        })
        comp._process(pd.DataFrame())
        assert os.path.exists(out)


# ------------------------------------------------------------------
# 12. flushonrow config key aliases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFlushOnRowAliases:
    """Both 'flushonrow' (converter) and 'flush_on_row' (engine) keys work."""

    def test_converter_key_flushonrow(self, tmp_path):
        out = str(tmp_path / "out.txt")
        comp = _make_component({
            "filepath": out,
            "formats": _SIMPLE_FORMATS,
            "flushonrow": True,
            "flushonrow_num": 1,
            "include_header": False,
        })
        comp._process(_SIMPLE_DATA)
        assert os.path.exists(out)

    def test_engine_key_flush_on_row(self, tmp_path):
        out = str(tmp_path / "out.txt")
        comp = _make_component({
            "filepath": out,
            "formats": _SIMPLE_FORMATS,
            "flush_on_row": True,
            "flush_on_row_num": 1,
            "include_header": False,
        })
        comp._process(_SIMPLE_DATA)
        assert os.path.exists(out)


# ------------------------------------------------------------------
# 13. Statistics
# ------------------------------------------------------------------


@pytest.mark.unit
class TestStatistics:
    """NB_LINE / NB_LINE_OK populated correctly."""

    def test_stats_on_normal_write(self, tmp_path):
        # Call _process() directly -- stats are in comp.stats (not pushed to GlobalMap
        # until execute() calls _update_global_map()).
        out = str(tmp_path / "out.txt")
        comp = _make_component({"filepath": out, "formats": _SIMPLE_FORMATS})
        comp._process(_SIMPLE_DATA)
        assert comp.stats["NB_LINE"] == 2
        assert comp.stats["NB_LINE_OK"] == 2
        assert comp.stats["NB_LINE_REJECT"] == 0

    def test_stats_on_empty_input(self, tmp_path):
        out = str(tmp_path / "out.txt")
        comp = _make_component({"filepath": out, "formats": _SIMPLE_FORMATS})
        comp._process(pd.DataFrame())
        assert comp.stats["NB_LINE"] == 0
        assert comp.stats["NB_LINE_OK"] == 0


# ------------------------------------------------------------------
# 14. Streaming multi-chunk append fix
# ------------------------------------------------------------------


@pytest.mark.unit
class TestStreamingWriteStarted:
    """_streaming_write_started flag prevents chunk overwrite in streaming mode.

    Bug fixed: without the flag every chunk opened the fixed-width file with
    mode='w', so only the last chunk survived.  The fix forces append=True
    for every chunk after the first by tracking _streaming_write_started.
    """

    def test_flag_is_false_on_init(self):
        """_streaming_write_started is False on a freshly created component."""
        comp = _make_component({"filepath": "/tmp/x.txt", "formats": _SIMPLE_FORMATS})
        assert comp._streaming_write_started is False

    def test_flag_set_true_after_first_process(self, tmp_path):
        """After the first _process() call the flag becomes True."""
        out = str(tmp_path / "out.txt")
        comp = _make_component({"filepath": out, "formats": _SIMPLE_FORMATS})
        comp._process(_SIMPLE_DATA)
        assert comp._streaming_write_started is True

    def test_second_chunk_appends_not_overwrites(self, tmp_path):
        """Second _process() call appends even when append=False is in config.

        Core regression: without the fix chunk 2 would overwrite chunk 1.
        """
        out = str(tmp_path / "out.txt")
        comp = _make_component({"filepath": out, "formats": _SIMPLE_FORMATS, "append": False})

        chunk1 = pd.DataFrame({"name": ["Alice", "Bob"],    "age": ["25", "30"]})
        chunk2 = pd.DataFrame({"name": ["Charlie", "Dave"], "age": ["35", "40"]})
        comp._process(chunk1)
        comp._process(chunk2)

        lines = _read_text(out).splitlines()
        assert len(lines) == 4, (
            f"Expected 4 rows (2 per chunk), got {len(lines)}. "
            f"The second chunk probably overwrote the first."
        )

    def test_three_chunks_all_rows_present(self, tmp_path):
        """All rows from three sequential _process() calls survive in the file."""
        out = str(tmp_path / "out.txt")
        comp = _make_component({"filepath": out, "formats": _SIMPLE_FORMATS, "append": False})

        for start in [10, 20, 30]:
            chunk = pd.DataFrame({"name": [f"P{start}a", f"P{start}b"],
                                   "age":  [str(start), str(start + 1)]})
            comp._process(chunk)

        lines = _read_text(out).splitlines()
        assert len(lines) == 6, f"Expected 6 rows (3 chunks x 2), got {len(lines)}"

    def test_reset_clears_flag(self, tmp_path):
        """reset() sets _streaming_write_started back to False."""
        out = str(tmp_path / "out.txt")
        comp = _make_component({"filepath": out, "formats": _SIMPLE_FORMATS})
        comp._process(_SIMPLE_DATA)
        assert comp._streaming_write_started is True

        comp.reset()
        assert comp._streaming_write_started is False

    def test_iterate_pattern_second_pass_overwrites(self, tmp_path):
        """After reset(), a fresh _process() overwrites — correct iterate-loop behaviour.

        In a tFileList loop each pass calls reset() then execute() again.
        The output file must contain only the rows from the most recent pass.
        """
        out = str(tmp_path / "out.txt")
        comp = _make_component({"filepath": out, "formats": _SIMPLE_FORMATS, "append": False})

        # First pass — 1 row
        comp._process(pd.DataFrame({"name": ["Pass1"], "age": ["99"]}))
        comp.reset()

        # Second pass — 2 rows
        comp._process(pd.DataFrame({"name": ["Pass2a", "Pass2b"], "age": ["11", "22"]}))

        content = _read_text(out)
        lines = content.splitlines()
        assert len(lines) == 2, (
            f"After reset() the file should contain only the second pass (2 rows), "
            f"got {len(lines)}"
        )
        assert "Pass2" in content
        assert "Pass1" not in content

    def test_explicit_append_config_respected_on_first_chunk(self, tmp_path):
        """append=True in config is honoured on the first chunk."""
        out = str(tmp_path / "out.txt")
        with open(out, "w", encoding="ISO-8859-15") as fh:
            fh.write("Existing  00000\n")

        comp = _make_component(
            {"filepath": out, "formats": _SIMPLE_FORMATS, "append": True}
        )
        comp._process(pd.DataFrame({"name": ["New"], "age": ["42"]}))

        content = _read_text(out)
        assert "Existing" in content, "Pre-existing content must be kept when append=True"
        assert "New" in content


# ------------------------------------------------------------------
# Plan 14-08 coverage lift: missed-line clusters
#   149 (formats=[] structural), 154 (formats item not dict),
#   214, 218 (filepath / formats content checks),
#   224-225 (flushonrow_num non-int -> raise),
#   270-271 (delete_empty_file OSError -> warn),
#   290-297 (write OSError -> FileOperationError; Exception -> CEE),
#   305-307 (post-write delete-zero-byte),
#   382 (compress=True header writer),
#   403-406 (finally close swallows Exception),
#   437 (padding_char surrounded by single quotes),
#   480 (column not in df.columns: empty Series),
#   484-492 (numeric type _fmt_float),
#   494-501 (integer type _fmt_int),
#   513 (KEEP=MIDDLE truncation),
#   539 (build_row_strings empty cols),
#   567 (header CENTER alignment).
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCoverageLift1408ValidateConfig:
    def test_validate_empty_formats_list_raises(self):
        """formats=[] -> ConfigurationError ('Missing required config key' fires first)."""
        comp = _make_component({"filepath": "/tmp/x.txt", "formats": []})
        # Line 148-151 ('cannot be empty') is unreachable because the earlier
        # `if not formats:` (line 140) treats [] as falsy and raises with
        # 'Missing required config key' first.
        with pytest.raises(ConfigurationError, match="Missing required"):
            comp._validate_config()

    def test_validate_format_item_not_dict_raises(self):
        """formats[i] not a dict -> ConfigurationError (line 154)."""
        comp = _make_component({"filepath": "/tmp/x.txt", "formats": ["not_a_dict"]})
        with pytest.raises(ConfigurationError, match="must be a dict"):
            comp._validate_config()


@pytest.mark.unit
class TestCoverageLift1408ProcessChecks:
    def test_empty_filepath_in_process_raises(self):
        """filepath empty after resolution -> ConfigurationError (line 214)."""
        from src.v1.engine.exceptions import ComponentExecutionError
        comp = _make_component(
            {"filepath": "  ", "formats": _SIMPLE_FORMATS}
        )
        # _process directly (filepath = "  " trimmed); the structural check at
        # line 213 fires.
        comp.config["filepath"] = ""
        with pytest.raises((ConfigurationError, ComponentExecutionError),
                           match="must not be empty"):
            comp._process(_SIMPLE_DATA)

    def test_formats_not_list_raises_in_process(self):
        """formats not list -> ConfigurationError (line 217-220)."""
        from src.v1.engine.exceptions import ComponentExecutionError
        comp = _make_component(
            {"filepath": "/tmp/x.txt", "formats": "not_a_list"}
        )
        with pytest.raises((ConfigurationError, ComponentExecutionError),
                           match="non-empty list"):
            comp._process(_SIMPLE_DATA)

    def test_flushonrow_num_non_int_raises(self):
        """flushonrow_num non-integer -> ConfigurationError (line 224-225)."""
        from src.v1.engine.exceptions import ComponentExecutionError
        comp = _make_component(
            {"filepath": "/tmp/x.txt", "formats": _SIMPLE_FORMATS,
             "flushonrow_num": "not_an_int"}
        )
        with pytest.raises((ConfigurationError, ComponentExecutionError),
                           match="must be an integer"):
            comp._process(_SIMPLE_DATA)


@pytest.mark.unit
class TestCoverageLift1408DeleteEmptyFile:
    def test_delete_empty_file_oserror_logs_warning(self, tmp_path, caplog, monkeypatch):
        """delete_empty_file=True + os.remove OSError -> warning, no raise (270-271)."""
        import logging
        out = str(tmp_path / "delete.txt")
        # Pre-create file
        with open(out, "w", encoding="ISO-8859-15") as fh:
            fh.write("data")
        comp = _make_component(
            {"filepath": out, "formats": _SIMPLE_FORMATS,
             "delete_empty_file": True}
        )

        original_remove = os.remove

        def remove_raise(path, *a, **k):
            if str(path) == out:
                raise OSError("simulated rm failure")
            return original_remove(path, *a, **k)

        monkeypatch.setattr(os, "remove", remove_raise)
        with caplog.at_level(logging.WARNING):
            comp._process(pd.DataFrame())  # Empty input -> delete-empty branch
        assert any("Could not delete file" in r.message for r in caplog.records)


@pytest.mark.unit
class TestCoverageLift1408WriteFailures:
    def test_write_oserror_wraps_as_file_operation_error(self, tmp_path, monkeypatch):
        """OSError during _write_positional_file -> FileOperationError (292-295)."""
        from src.v1.engine.exceptions import FileOperationError, ComponentExecutionError
        out = str(tmp_path / "fail.txt")
        comp = _make_component(
            {"filepath": out, "formats": _SIMPLE_FORMATS}
        )

        import builtins
        original_open = builtins.open

        def selective_open(path, *a, **kw):
            if str(path) == out:
                raise OSError("simulated I/O")
            return original_open(path, *a, **kw)

        monkeypatch.setattr(builtins, "open", selective_open)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="I/O error writing",
        ):
            comp._process(_SIMPLE_DATA)

    def test_write_unexpected_exception_wraps_as_component_execution_error(
        self, tmp_path, monkeypatch
    ):
        """Non-OSError Exception during write -> ComponentExecutionError (296-301)."""
        from src.v1.engine.exceptions import ComponentExecutionError
        out = str(tmp_path / "fail.txt")
        comp = _make_component(
            {"filepath": out, "formats": _SIMPLE_FORMATS}
        )

        # Force an unexpected exception inside _write_positional_file
        def boom(*a, **k):
            raise RuntimeError("simulated unexpected")

        monkeypatch.setattr(comp, "_write_positional_file", boom)
        with pytest.raises(ComponentExecutionError, match="Unexpected error"):
            comp._process(_SIMPLE_DATA)

    def test_write_file_operation_error_passes_through(self, tmp_path, monkeypatch):
        """FileOperationError raised by _write_positional_file is re-raised (line 291)."""
        from src.v1.engine.exceptions import (
            ComponentExecutionError,
            FileOperationError,
        )
        out = str(tmp_path / "foe.txt")
        comp = _make_component(
            {"filepath": out, "formats": _SIMPLE_FORMATS}
        )

        def raise_foe(*a, **k):
            raise FileOperationError("inner-foe")

        monkeypatch.setattr(comp, "_write_positional_file", raise_foe)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="inner-foe",
        ):
            comp._process(_SIMPLE_DATA)


@pytest.mark.unit
class TestCoverageLift1408FinallyClose:
    def test_finally_close_swallows_exception(self, tmp_path, monkeypatch):
        """File-handle close in finally block swallows exceptions (lines 403-406)."""
        out = str(tmp_path / "swallow.txt")
        comp = _make_component(
            {"filepath": out, "formats": _SIMPLE_FORMATS}
        )

        # Patch open() to return a wrapper whose write succeeds but whose
        # final flush raises -- this triggers exit-via-exception, leaving the
        # file_handle non-None so the finally block calls close(); and close()
        # itself raises -- which the bare except in lines 403-406 swallows.
        import builtins
        original_open = builtins.open

        class FailHandle:
            def __init__(self, real):
                self._real = real
                self._closed = False
            def write(self, *a, **k): return self._real.write(*a, **k)
            def flush(self):
                # Force an exception on the FIRST flush so file_handle stays
                # non-None inside the try block.
                raise OSError("flush failure")
            def close(self):
                # Close also raises -- the finally block swallows it (403-406).
                if not self._closed:
                    self._closed = True
                    raise OSError("close failure")

        def selective_open(path, *a, **kw):
            if str(path) == out:
                return FailHandle(original_open(path, *a, **kw))
            return original_open(path, *a, **kw)

        monkeypatch.setattr(builtins, "open", selective_open)
        # The outer except OSError wraps the OSError as FileOperationError;
        # the `finally` block's close() OSError is swallowed (403-406).
        from src.v1.engine.exceptions import (
            ComponentExecutionError,
            FileOperationError,
        )
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="I/O error|flush failure",
        ):
            comp._process(_SIMPLE_DATA)


@pytest.mark.unit
class TestCoverageLift1408PostWriteCleanup:
    def test_zero_byte_file_deleted_after_write(self, tmp_path):
        """delete_empty_file=True + zero-byte after write -> remove (305-307)."""
        out = str(tmp_path / "zero.txt")
        comp = _make_component(
            {"filepath": out, "formats": _SIMPLE_FORMATS,
             "delete_empty_file": True, "include_header": False}
        )
        # 0 input rows but DF has 'name' and 'age' columns so it's not "empty"
        # via input_data.empty -- need rows to bypass empty branch.
        # Use a DF with 1 row but make _write_positional_file produce empty file
        # by passing zero formats matching column. Actually simpler: 1 row of
        # data -> file is non-empty. The post-write zero-byte branch only fires
        # if writing produced a 0-byte file. Use a DF with len > 0 but data
        # that yields zero bytes is not possible because formats define width.
        # So we tickle this by truncating after.
        df = pd.DataFrame({"name": ["A"], "age": ["1"]})
        comp._process(df)
        # Now manually truncate & re-run delete-empty with already existing file
        with open(out, "w", encoding="ISO-8859-15") as fh:
            pass  # zero bytes
        # Also reset streaming flag
        comp._streaming_write_started = False
        # Re-call with non-empty data - the file will be empty momentarily from
        # the truncate before write happens. Since the post-write check looks
        # at filesize AFTER write, we need a different approach: monkeypatch
        # _write_positional_file to leave a zero-byte file.
        comp = _make_component(
            {"filepath": out, "formats": _SIMPLE_FORMATS,
             "delete_empty_file": True}
        )
        with open(out, "w", encoding="ISO-8859-15") as fh:
            pass
        # Stub the write to leave a zero-byte file in place
        def zero_write(*a, **k):
            with open(out, "w", encoding="ISO-8859-15") as fh:
                pass  # 0 bytes
            return 0
        comp._write_positional_file = zero_write  # type: ignore
        comp._process(df)
        assert not os.path.exists(out), "Zero-byte file should be deleted"


@pytest.mark.unit
class TestCoverageLift1408CompressedHeader:
    def test_compress_with_header_writes_encoded_header(self, tmp_path):
        """compress=True + include_header=True -> header.encode(encoding) (line 382)."""
        out = str(tmp_path / "compressed.txt.gz")
        comp = _make_component(
            {"filepath": out, "formats": _SIMPLE_FORMATS,
             "compress": True, "include_header": True}
        )
        comp._process(_SIMPLE_DATA)
        # Read back via gzip -- header should be the first line
        with gzip.open(out, "rt", encoding="ISO-8859-15") as fh:
            content = fh.read()
        assert "name" in content
        assert "Alice" in content


@pytest.mark.unit
class TestCoverageLift1408FormatColumns:
    """_prepare_column_formats and _format_columns branches."""

    def test_padding_char_with_single_quotes_strips_them(self, tmp_path):
        """padding_char wrapped in single quotes -> stripped (line 437)."""
        out = str(tmp_path / "padded.txt")
        formats = [
            {"schema_column": "x", "size": 5, "align": "L",
             "padding_char": "' '"},  # quoted single-space
        ]
        comp = _make_component({"filepath": out, "formats": formats})
        comp._process(pd.DataFrame({"x": ["A"]}))
        content = _read_text(out)
        # 'A' followed by 4 spaces (the quotes were stripped)
        assert content.startswith("A    ")

    def test_format_columns_missing_column_yields_blanks(self, tmp_path):
        """schema_column not in df -> empty Series (line 480)."""
        out = str(tmp_path / "missing.txt")
        formats = [
            {"schema_column": "missing", "size": 5, "align": "L",
             "padding_char": " "},
        ]
        comp = _make_component({"filepath": out, "formats": formats})
        comp._process(pd.DataFrame({"present": ["X"]}))
        content = _read_text(out)
        # 5 spaces output for the missing column row
        assert "     " in content

    def test_format_columns_numeric_type_fmt_float(self, tmp_path):
        """col_type=float triggers _fmt_float (484-492)."""
        out = str(tmp_path / "num.txt")
        formats = [
            {"schema_column": "amt", "size": 10, "align": "R",
             "padding_char": "0"},
        ]
        schema = [{"name": "amt", "type": "float", "precision": 2}]
        comp = _make_component(
            {"filepath": out, "formats": formats},
            input_schema=schema,
        )
        comp._process(pd.DataFrame({"amt": ["12.345", "", "not_numeric"]}))
        content = _read_text(out)
        # 12.345 -> '12.35' right-aligned with '0' padding
        assert "0000012.35" in content

    def test_format_columns_integer_type_fmt_int(self, tmp_path):
        """col_type=int triggers _fmt_int (494-501)."""
        out = str(tmp_path / "int.txt")
        formats = [
            {"schema_column": "n", "size": 6, "align": "R", "padding_char": "0"},
        ]
        schema = [{"name": "n", "type": "int"}]
        comp = _make_component(
            {"filepath": out, "formats": formats},
            input_schema=schema,
        )
        comp._process(pd.DataFrame({"n": ["42", "", "not_numeric"]}))
        content = _read_text(out)
        assert "000042" in content

    def test_keep_middle_truncation(self, tmp_path):
        """keep=MIDDLE -> middle slice; short value passes through (511-515 / 513)."""
        out = str(tmp_path / "mid.txt")
        formats = [
            {"schema_column": "v", "size": 5, "align": "L",
             "padding_char": " ", "keep": "MIDDLE"},
        ]
        comp = _make_component({"filepath": out, "formats": formats})
        # Mix of long (truncated middle) + short (passed through, line 513)
        comp._process(pd.DataFrame({"v": ["ABCDEFGHIJ", "AB"]}))
        content = _read_text(out)
        # Middle 5 of "ABCDEFGHIJ" -> indices 2-7 -> "CDEFG"
        assert "CDEFG" in content
        # "AB" is shorter than size=5, so passes through unchanged then padded
        assert "AB   " in content


@pytest.mark.unit
class TestCoverageLift1408HelperMethods:
    def test_build_row_strings_empty_returns_empty(self):
        """_build_row_strings([]) -> [] (line 538-539)."""
        comp = _make_component(
            {"filepath": "/tmp/x.txt", "formats": _SIMPLE_FORMATS}
        )
        assert comp._build_row_strings([], "\n") == []

    def test_format_header_row_center_alignment(self):
        """_format_header_row: align='C' -> center pad (line 567)."""
        comp = _make_component(
            {"filepath": "/tmp/x.txt", "formats": _SIMPLE_FORMATS}
        )
        col_names = ["abc"]
        col_formats = [{"size": 7, "pad": "*", "align": "C"}]
        out = comp._format_header_row(col_names, col_formats, "\n")
        # 'abc' centered in 7 chars padded with '*'
        assert "**abc**" in out
