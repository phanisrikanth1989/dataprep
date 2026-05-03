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
