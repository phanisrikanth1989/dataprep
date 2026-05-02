"""Tests for ChangeFileEncoding engine component (tChangeFileEncoding).

Test classes:
    TestRegistration     -- registry decorator, BaseComponent inheritance
    TestValidation       -- _validate_config structural checks (Rule 12)
    TestHappyPath        -- successful re-encoding scenarios
    TestCreateFlag       -- create=True/False behavior
    TestBufferSize       -- custom buffer sizes, expression-resolved buffers
    TestEdgeCases        -- missing source, bad encoding, directory creation
    TestStatistics       -- NB_LINE/NB_LINE_OK/NB_LINE_REJECT always 0
"""
import os
import tempfile

import pytest
import pandas as pd

from src.v1.engine.components.transform.change_file_encoding import ChangeFileEncoding
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, ComponentExecutionError, FileOperationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_component(config=None, global_map=None):
    """Create a ChangeFileEncoding with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    return ChangeFileEncoding(
        component_id="tCFE_1",
        config=config or {},
        global_map=gm,
        context_manager=cm,
    )


def _write_file(path: str, content: str, encoding: str = "utf-8") -> None:
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


def _read_file(path: str, encoding: str = "utf-8") -> str:
    with open(path, "r", encoding=encoding) as f:
        return f.read()


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    """Registry decorator places component under both V1 and Talend names."""

    def test_v1_name_registered(self):
        assert REGISTRY.get("ChangeFileEncoding") is ChangeFileEncoding

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tChangeFileEncoding") is ChangeFileEncoding

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(ChangeFileEncoding, BaseComponent)


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidation:
    """_validate_config() -- structural checks only (Rules 2, 7, 12)."""

    def test_missing_infile_name_raises(self, tmp_path):
        comp = _make_component(config={"outfile_name": str(tmp_path / "out.txt")})
        with pytest.raises(ConfigurationError, match="infile_name"):
            comp.execute(None)

    def test_empty_infile_name_raises(self, tmp_path):
        comp = _make_component(config={"infile_name": "", "outfile_name": str(tmp_path / "out.txt")})
        with pytest.raises(ConfigurationError, match="infile_name"):
            comp.execute(None)

    def test_missing_outfile_name_raises(self, tmp_path):
        comp = _make_component(config={"infile_name": str(tmp_path / "in.txt")})
        with pytest.raises(ConfigurationError, match="outfile_name"):
            comp.execute(None)

    def test_empty_outfile_name_raises(self, tmp_path):
        comp = _make_component(config={"infile_name": str(tmp_path / "in.txt"), "outfile_name": ""})
        with pytest.raises(ConfigurationError, match="outfile_name"):
            comp.execute(None)

    def test_use_inencoding_not_bool_raises(self, tmp_path):
        comp = _make_component(config={
            "infile_name": str(tmp_path / "in.txt"),
            "outfile_name": str(tmp_path / "out.txt"),
            "use_inencoding": "true",  # string, not bool
        })
        with pytest.raises(ConfigurationError, match="use_inencoding"):
            comp.execute(None)

    def test_create_not_bool_raises(self, tmp_path):
        comp = _make_component(config={
            "infile_name": str(tmp_path / "in.txt"),
            "outfile_name": str(tmp_path / "out.txt"),
            "create": "yes",  # string, not bool
        })
        with pytest.raises(ConfigurationError, match="create"):
            comp.execute(None)

    def test_valid_config_does_not_raise_on_valid_structure(self, tmp_path):
        """Valid structural config: no ConfigurationError raised before _process runs."""
        src = tmp_path / "in.txt"
        src.write_text("hello", encoding="utf-8")
        dst = tmp_path / "out.txt"
        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        })
        comp.execute(None)  # should not raise

    def test_error_includes_component_id(self, tmp_path):
        comp = _make_component(config={"outfile_name": str(tmp_path / "out.txt")})
        with pytest.raises(ConfigurationError, match="tCFE_1"):
            comp.execute(None)


# ------------------------------------------------------------------
# TestHappyPath
# ------------------------------------------------------------------

@pytest.mark.unit
class TestHappyPath:
    """Successful re-encoding scenarios."""

    def test_utf8_to_utf8_roundtrip(self, tmp_path):
        """Basic: read UTF-8 write UTF-8, content preserved."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        content = "Hello, World!\nLine two.\n"
        _write_file(str(src), content, "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        })
        result = comp.execute(None)

        assert dst.exists()
        assert _read_file(str(dst), "utf-8") == content
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty
        assert result["reject"] is None

    def test_iso_to_utf8_conversion(self, tmp_path):
        """Re-encode ISO-8859-15 content to UTF-8."""
        src = tmp_path / "iso.txt"
        dst = tmp_path / "utf8.txt"
        content = "Caf\xe9 au lait"  # é in ISO-8859-15 is 0xE9
        _write_file(str(src), content, "iso-8859-15")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "iso-8859-15",
            "encoding": "utf-8",
            "create": True,
        })
        comp.execute(None)

        assert _read_file(str(dst), "utf-8") == content

    def test_utf8_to_latin1(self, tmp_path):
        """Re-encode UTF-8 to latin-1."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        content = "naïve"
        _write_file(str(src), content, "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "latin-1",
            "create": True,
        })
        comp.execute(None)

        assert _read_file(str(dst), "latin-1") == content

    def test_use_inencoding_false_uses_system_default(self, tmp_path):
        """use_inencoding=False: source read with system encoding (no error)."""
        import locale
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        content = "simple ascii text"
        sys_enc = locale.getpreferredencoding(False)
        _write_file(str(src), content, sys_enc)

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": False,
            "encoding": "utf-8",
            "create": True,
        })
        comp.execute(None)

        assert dst.exists()
        assert _read_file(str(dst), "utf-8") == content

    def test_input_data_ignored(self, tmp_path):
        """File utility: passing a DataFrame as input_data is silently ignored."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        _write_file(str(src), "test", "utf-8")

        import pandas as pd
        dummy_df = pd.DataFrame({"col": [1, 2, 3]})

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        })
        result = comp.execute(dummy_df)
        assert result["main"].empty  # output is always empty DF

    def test_multiline_content_preserved(self, tmp_path):
        """Multiline file content is fully preserved after re-encoding."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        lines = "\n".join(f"line {i}" for i in range(100))
        _write_file(str(src), lines, "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        })
        comp.execute(None)
        assert _read_file(str(dst), "utf-8") == lines

    def test_output_main_is_empty_dataframe(self, tmp_path):
        """Result 'main' is always an empty DataFrame (no rows, no columns)."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        _write_file(str(src), "data", "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        })
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0
        assert len(result["main"].columns) == 0

    def test_reject_key_always_none(self, tmp_path):
        """Rule 3: result must have 'reject' key, value is None."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        _write_file(str(src), "data", "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        })
        result = comp.execute(None)
        assert "reject" in result
        assert result["reject"] is None


# ------------------------------------------------------------------
# TestCreateFlag
# ------------------------------------------------------------------

@pytest.mark.unit
class TestCreateFlag:
    """create=True/False behavior."""

    def test_create_true_creates_new_file(self, tmp_path):
        """create=True: output file is created even if it does not exist."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        _write_file(str(src), "hello", "utf-8")
        assert not dst.exists()

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        })
        comp.execute(None)
        assert dst.exists()

    def test_create_false_existing_file_succeeds(self, tmp_path):
        """create=False: succeeds when output file already exists."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        _write_file(str(src), "hello", "utf-8")
        _write_file(str(dst), "old content", "utf-8")  # pre-exists

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": False,
        })
        comp.execute(None)
        assert _read_file(str(dst), "utf-8") == "hello"

    def test_create_false_missing_file_raises(self, tmp_path):
        """create=False: raises ComponentExecutionError wrapping FileOperationError when output file does not exist."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "nonexistent.txt"
        _write_file(str(src), "hello", "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": False,
        })
        with pytest.raises(ComponentExecutionError, match="create=False"):
            comp.execute(None)

    def test_create_true_creates_parent_directory(self, tmp_path):
        """create=True: parent directories created automatically."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "subdir" / "nested" / "out.txt"
        _write_file(str(src), "hello", "utf-8")
        assert not dst.parent.exists()

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        })
        comp.execute(None)
        assert dst.exists()
        assert _read_file(str(dst), "utf-8") == "hello"

    def test_create_default_is_true(self, tmp_path):
        """Default create=True when key absent -- file created."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        _write_file(str(src), "hello", "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            # create key absent -- defaults to True
        })
        comp.execute(None)
        assert dst.exists()


# ------------------------------------------------------------------
# TestBufferSize
# ------------------------------------------------------------------

@pytest.mark.unit
class TestBufferSize:
    """Buffer size handling (TEXT type -- may be context-var resolved string)."""

    def test_large_buffer_size(self, tmp_path):
        """Large buffer (64KB): full file processed correctly."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        content = "x" * 10000
        _write_file(str(src), content, "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
            "buffersize": "65536",
        })
        comp.execute(None)
        assert _read_file(str(dst), "utf-8") == content

    def test_small_buffer_size(self, tmp_path):
        """Small buffer (4 bytes): multiple read iterations, content still correct."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        content = "abcdefghij"
        _write_file(str(src), content, "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
            "buffersize": "4",
        })
        comp.execute(None)
        assert _read_file(str(dst), "utf-8") == content

    def test_default_buffer_size(self, tmp_path):
        """Default buffersize 8192 used when key absent."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        _write_file(str(src), "test content", "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
            # buffersize absent -- default 8192
        })
        comp.execute(None)  # should not raise
        assert dst.exists()

    def test_invalid_buffersize_raises(self, tmp_path):
        """Non-numeric buffersize raises ComponentExecutionError (deferred per Rule 12)."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        _write_file(str(src), "test", "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
            "buffersize": "notanumber",
        })
        with pytest.raises(ComponentExecutionError, match="buffersize"):
            comp.execute(None)

    def test_zero_buffersize_raises(self, tmp_path):
        """Zero buffersize raises ComponentExecutionError."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        _write_file(str(src), "test", "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
            "buffersize": "0",
        })
        with pytest.raises(ComponentExecutionError, match="buffersize"):
            comp.execute(None)


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEdgeCases:
    """Error cases and edge conditions."""

    def test_missing_source_file_raises(self, tmp_path):
        """Source file does not exist -> ComponentExecutionError."""
        comp = _make_component(config={
            "infile_name": str(tmp_path / "nonexistent.txt"),
            "outfile_name": str(tmp_path / "out.txt"),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        })
        with pytest.raises(ComponentExecutionError, match="does not exist"):
            comp.execute(None)

    def test_empty_source_file(self, tmp_path):
        """Empty source file -> empty output file, no error."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        _write_file(str(src), "", "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        })
        comp.execute(None)
        assert _read_file(str(dst), "utf-8") == ""

    def test_overwrite_existing_output_file(self, tmp_path):
        """Existing output file is overwritten."""
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        _write_file(str(src), "new content", "utf-8")
        _write_file(str(dst), "old content", "utf-8")

        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        })
        comp.execute(None)
        assert _read_file(str(dst), "utf-8") == "new content"

    def test_error_message_includes_component_id(self, tmp_path):
        """ComponentExecutionError includes component id for traceability."""
        comp = _make_component(config={
            "infile_name": str(tmp_path / "missing.txt"),
            "outfile_name": str(tmp_path / "out.txt"),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        })
        with pytest.raises(ComponentExecutionError, match="tCFE_1"):
            comp.execute(None)


# ------------------------------------------------------------------
# TestStatistics
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStatistics:
    """NB_LINE / NB_LINE_OK / NB_LINE_REJECT are always 0 (file utility, no rows)."""

    def _run(self, tmp_path):
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        _write_file(str(src), "data", "utf-8")
        gm = GlobalMap()
        comp = _make_component(config={
            "infile_name": str(src),
            "outfile_name": str(dst),
            "use_inencoding": True,
            "inencoding": "utf-8",
            "encoding": "utf-8",
            "create": True,
        }, global_map=gm)
        result = comp.execute(None)
        return result, gm

    def test_nb_line_is_zero(self, tmp_path):
        result, _ = self._run(tmp_path)
        assert result["stats"]["NB_LINE"] == 0

    def test_nb_line_ok_is_zero(self, tmp_path):
        result, _ = self._run(tmp_path)
        assert result["stats"]["NB_LINE_OK"] == 0

    def test_nb_line_reject_is_zero(self, tmp_path):
        result, _ = self._run(tmp_path)
        assert result["stats"]["NB_LINE_REJECT"] == 0
