"""Tests for FileProperties engine component (tFileProperties).

Test classes:
    TestRegistry        -- @REGISTRY.register, BaseComponent inheritance
    TestValidateConfig  -- _validate_config() structural checks (Rule 12)
    TestProcessMain     -- happy-path file metadata extraction
    TestMd5             -- MD5 calculation
    TestProcessErrors   -- missing file, empty filename
    TestStats           -- NB_LINE / NB_LINE_OK always 1/1
"""
import os
import hashlib
import tempfile

import pytest
import pandas as pd

from src.v1.engine.components.file.file_properties import FileProperties
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, ComponentExecutionError, FileOperationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    cfg = config or {}
    comp = FileProperties(
        component_id="tFP_1",
        config=cfg,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(cfg)
    return comp


def _write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ------------------------------------------------------------------
# TestRegistry
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistry:
    def test_v1_name_registered(self):
        assert REGISTRY.get("FileProperties") is FileProperties

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tFileProperties") is FileProperties

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(FileProperties, BaseComponent)


# ------------------------------------------------------------------
# TestValidateConfig
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_missing_filename_raises(self):
        comp = _make_component(config={})
        with pytest.raises(ConfigurationError, match="filename"):
            comp._validate_config()

    def test_md5_not_bool_raises(self):
        comp = _make_component(config={"filename": "/f.txt", "md5": "yes"})
        with pytest.raises(ConfigurationError, match="md5"):
            comp._validate_config()

    def test_valid_config_passes(self):
        comp = _make_component(config={"filename": "/f.txt"})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestProcessMain
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessMain:
    def test_returns_one_row(self, tmp_path):
        f = str(tmp_path / "test.txt")
        _write_file(f, "hello")
        comp = _make_component(config={"filename": f, "md5": False})
        result = comp.execute(None)
        assert len(result["main"]) == 1

    def test_basename_correct(self, tmp_path):
        f = str(tmp_path / "myfile.txt")
        _write_file(f, "hello")
        comp = _make_component(config={"filename": f})
        result = comp.execute(None)
        assert result["main"].iloc[0]["basename"] == "myfile.txt"

    def test_size_correct(self, tmp_path):
        f = str(tmp_path / "sized.txt")
        content = "A" * 100
        _write_file(f, content)
        comp = _make_component(config={"filename": f})
        result = comp.execute(None)
        assert result["main"].iloc[0]["size"] == os.path.getsize(f)

    def test_abs_path_is_absolute(self, tmp_path):
        f = str(tmp_path / "abs.txt")
        _write_file(f, "x")
        comp = _make_component(config={"filename": f})
        result = comp.execute(None)
        assert os.path.isabs(result["main"].iloc[0]["abs_path"])

    def test_mtime_string_format(self, tmp_path):
        f = str(tmp_path / "time.txt")
        _write_file(f, "x")
        comp = _make_component(config={"filename": f})
        result = comp.execute(None)
        mtime_str = result["main"].iloc[0]["mtime_string"]
        # Should be YYYY-MM-DD HH:MM:SS
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", mtime_str)

    def test_reject_is_none(self, tmp_path):
        f = str(tmp_path / "test.txt")
        _write_file(f, "x")
        comp = _make_component(config={"filename": f})
        result = comp.execute(None)
        assert result["reject"] is None


# ------------------------------------------------------------------
# TestMd5
# ------------------------------------------------------------------

@pytest.mark.unit
class TestMd5:
    def test_md5_calculated_correctly(self, tmp_path):
        f = str(tmp_path / "md5.txt")
        content = b"hello world"
        with open(f, "wb") as fh:
            fh.write(content)
        expected = hashlib.md5(content).hexdigest()
        comp = _make_component(config={"filename": f, "md5": True})
        result = comp.execute(None)
        assert result["main"].iloc[0]["md5"] == expected

    def test_no_md5_col_when_disabled(self, tmp_path):
        f = str(tmp_path / "nomd5.txt")
        _write_file(f, "x")
        comp = _make_component(config={"filename": f, "md5": False})
        result = comp.execute(None)
        assert "md5" not in result["main"].columns


# ------------------------------------------------------------------
# TestProcessErrors
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessErrors:
    def test_missing_file_raises(self):
        comp = _make_component(config={"filename": "/no/such/file.txt"})
        with pytest.raises((ComponentExecutionError, FileOperationError)):
            comp.execute(None)

    def test_empty_filename_raises(self):
        comp = _make_component(config={"filename": ""})
        with pytest.raises((ComponentExecutionError, ConfigurationError, FileOperationError)):
            comp.execute(None)


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    def test_nb_line_is_one(self, tmp_path):
        f = str(tmp_path / "stats.txt")
        _write_file(f, "x")
        gm = GlobalMap()
        comp = _make_component(config={"filename": f}, global_map=gm)
        comp.execute(None)
        assert gm.get_nb_line(comp.id) == 1

    def test_nb_line_ok_is_one(self, tmp_path):
        f = str(tmp_path / "stats_ok.txt")
        _write_file(f, "x")
        gm = GlobalMap()
        comp = _make_component(config={"filename": f}, global_map=gm)
        comp.execute(None)
        assert gm.get_nb_line_ok(comp.id) == 1


# ------------------------------------------------------------------
# Plan 14-08 coverage lift: missed-line clusters
#   84-85 (os.stat OSError -> FileOperationError),
#   131-132 (MD5 read OSError -> FileOperationError).
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCoverageLift1408:
    """Targeted tests added in Plan 14-08 to lift file_properties.py to 100%."""

    def test_oserror_on_stat_raises_file_operation_error(self, tmp_path, monkeypatch):
        """os.stat OSError (other than FileNotFoundError) wraps as FileOperationError (84-85)."""
        f = tmp_path / "perm.txt"
        f.write_text("x")
        comp = _make_component(config={"filename": str(f)})

        original_stat = os.stat

        def stat_raise(path, *args, **kwargs):
            if str(path) == str(f):
                raise PermissionError("permission denied simulation")
            return original_stat(path, *args, **kwargs)

        monkeypatch.setattr(os, "stat", stat_raise)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="Cannot stat file",
        ):
            comp.execute(None)

    def test_md5_read_failure_raises_file_operation_error(self, tmp_path, monkeypatch):
        """MD5 read OSError wraps as FileOperationError (131-132)."""
        f = tmp_path / "md5.txt"
        f.write_text("hello")
        comp = _make_component(config={"filename": str(f), "md5": True})

        # Monkeypatch open() to raise when file_properties._calculate_md5 opens
        # the file. We let stat() succeed (so we reach the md5 step), then fail
        # the read.
        import builtins
        original_open = builtins.open

        def selective_open(path, *args, **kwargs):
            if str(path) == str(f) and ("rb" in args or kwargs.get("mode") == "rb"):
                raise OSError("read failure simulation")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", selective_open)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="Failed to calculate MD5",
        ):
            comp.execute(None)
