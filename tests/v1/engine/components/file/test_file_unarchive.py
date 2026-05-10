"""Tests for FileUnarchive engine component (tFileUnarchive).

Test classes:
    TestRegistration      -- registry decorator, BaseComponent inheritance
    TestValidation        -- _validate_config structural checks (Rule 12)
    TestBasicExtraction   -- extract a standard ZIP archive
    TestPreservePaths     -- extractpath=True vs False behavior
    TestPasswordProtected -- checkpassword + password config
    TestRootname          -- rootname prefix stripping
    TestPrintout          -- printout=True logs file names
    TestGlobalMapVars     -- CURRENT_FILE set during extraction
    TestZipSlipProtection -- malicious paths rejected before extraction
    TestMissingArchive    -- missing ZIP file raises FileOperationError
    TestBadZip            -- corrupt ZIP raises FileOperationError
"""
import io
import os
import struct
import zipfile

import pytest
import pandas as pd

from src.v1.engine.components.file.file_unarchive import FileUnarchive
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, ComponentExecutionError, FileOperationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_component(config, context_manager=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    comp = FileUnarchive(
        component_id="tFileUnarchive_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    # Seed self.config so direct _validate_config() calls work without execute()
    comp.config = dict(config)
    return comp


def _make_zip(tmp_path, members: dict) -> str:
    """Create a ZIP archive at tmp_path/archive.zip with given {name: content} members."""
    zip_path = str(tmp_path / "archive.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return zip_path


def _make_zip_custom(tmp_path, zip_name: str, members: dict) -> str:
    zip_path = str(tmp_path / zip_name)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return zip_path


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    """Registry decorator, BaseComponent inheritance."""

    def test_v1_name_registered(self):
        assert REGISTRY.get("FileUnarchive") is FileUnarchive

    def test_legacy_class_name_registered(self):
        assert REGISTRY.get("FileUnarchiveComponent") is FileUnarchive

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tFileUnarchive") is FileUnarchive

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(FileUnarchive, BaseComponent)


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidation:
    """_validate_config() -- structural checks, raises ConfigurationError."""

    def test_missing_zipfile_raises(self, tmp_path):
        comp = _make_component({"directory": str(tmp_path / "out")})
        with pytest.raises(ConfigurationError, match="zipfile"):
            comp._validate_config()

    def test_missing_directory_raises(self, tmp_path):
        comp = _make_component({"zipfile": str(tmp_path / "a.zip"), "directory": ""})
        with pytest.raises(ConfigurationError, match="directory"):
            comp._validate_config()

    def test_valid_config_does_not_raise(self, tmp_path):
        comp = _make_component({
            "zipfile": str(tmp_path / "a.zip"),
            "directory": str(tmp_path / "out"),
        })
        comp._validate_config()  # must not raise

    def test_bad_bool_extractpath_raises(self, tmp_path):
        comp = _make_component({
            "zipfile": str(tmp_path / "a.zip"),
            "directory": str(tmp_path / "out"),
            "extractpath": "yes",
        })
        with pytest.raises(ConfigurationError, match="extractpath"):
            comp._validate_config()

    def test_bad_bool_checkpassword_raises(self, tmp_path):
        comp = _make_component({
            "zipfile": str(tmp_path / "a.zip"),
            "directory": str(tmp_path / "out"),
            "checkpassword": "no",
        })
        with pytest.raises(ConfigurationError, match="checkpassword"):
            comp._validate_config()


# ------------------------------------------------------------------
# TestBasicExtraction
# ------------------------------------------------------------------

@pytest.mark.unit
class TestBasicExtraction:
    """Standard ZIP extraction."""

    def test_extracts_files(self, tmp_path):
        zip_path = _make_zip(tmp_path, {"hello.txt": "hello world"})
        out_dir = str(tmp_path / "out")
        _make_component({"zipfile": zip_path, "directory": out_dir}).execute()
        assert os.path.exists(os.path.join(out_dir, "hello.txt"))

    def test_file_content_preserved(self, tmp_path):
        zip_path = _make_zip(tmp_path, {"data.txt": "test content 123"})
        out_dir = str(tmp_path / "out")
        _make_component({"zipfile": zip_path, "directory": out_dir}).execute()
        with open(os.path.join(out_dir, "data.txt")) as f:
            assert f.read() == "test content 123"

    def test_returns_empty_dataframe(self, tmp_path):
        zip_path = _make_zip(tmp_path, {"f.txt": "x"})
        out_dir = str(tmp_path / "out")
        result = _make_component({"zipfile": zip_path, "directory": out_dir}).execute()
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty

    def test_creates_output_dir_if_missing(self, tmp_path):
        zip_path = _make_zip(tmp_path, {"f.txt": "x"})
        out_dir = str(tmp_path / "new_out_dir")
        _make_component({"zipfile": zip_path, "directory": out_dir}).execute()
        assert os.path.isdir(out_dir)


# ------------------------------------------------------------------
# TestPreservePaths
# ------------------------------------------------------------------

@pytest.mark.unit
class TestPreservePaths:
    """extractpath=True preserves dir structure; extractpath=False flattens."""

    def test_extractpath_true_preserves_structure(self, tmp_path):
        zip_path = _make_zip(tmp_path, {"subdir/nested.txt": "nested"})
        out_dir = str(tmp_path / "out")
        _make_component({
            "zipfile": zip_path,
            "directory": out_dir,
            "extractpath": True,
        }).execute()
        assert os.path.exists(os.path.join(out_dir, "subdir", "nested.txt"))

    def test_extractpath_false_flattens(self, tmp_path):
        zip_path = _make_zip(tmp_path, {"subdir/nested.txt": "nested"})
        out_dir = str(tmp_path / "out")
        _make_component({
            "zipfile": zip_path,
            "directory": out_dir,
            "extractpath": False,
        }).execute()
        assert os.path.exists(os.path.join(out_dir, "nested.txt"))
        assert not os.path.exists(os.path.join(out_dir, "subdir"))


# ------------------------------------------------------------------
# TestRootname
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRootname:
    """rootname prefix is stripped from member paths before extraction."""

    def test_rootname_stripped(self, tmp_path):
        zip_path = _make_zip(tmp_path, {"myroot/data.txt": "content"})
        out_dir = str(tmp_path / "out")
        _make_component({
            "zipfile": zip_path,
            "directory": out_dir,
            "rootname": "myroot",
        }).execute()
        # After stripping 'myroot/', should extract as data.txt directly
        assert os.path.exists(os.path.join(out_dir, "data.txt"))


# ------------------------------------------------------------------
# TestGlobalMapVars
# ------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapVars:
    """CURRENT_FILE is updated in globalMap during extraction."""

    def test_current_file_set(self, tmp_path):
        zip_path = _make_zip(tmp_path, {"file.txt": "x"})
        out_dir = str(tmp_path / "out")
        gm = GlobalMap()
        _make_component({"zipfile": zip_path, "directory": out_dir}, global_map=gm).execute()
        val = gm.get("tFileUnarchive_1_CURRENT_FILE")
        assert val is not None
        assert val.endswith("file.txt")


# ------------------------------------------------------------------
# TestZipSlipProtection
# ------------------------------------------------------------------

@pytest.mark.unit
class TestZipSlipProtection:
    """Malicious zip entries with path traversal are rejected."""

    def test_zip_slip_raises(self, tmp_path):
        """A zip with '../../evil.txt' member must raise FileOperationError."""
        zip_path = str(tmp_path / "evil.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            # Manually add a traversal path entry
            info = zipfile.ZipInfo("../../evil.txt")
            zf.writestr(info, "pwned")
        out_dir = str(tmp_path / "safe_dir")
        os.makedirs(out_dir, exist_ok=True)
        comp = _make_component({"zipfile": zip_path, "directory": out_dir})
        with pytest.raises((ComponentExecutionError, FileOperationError), match="[Zz]ip.slip|traversal|outside"):
            comp.execute()


# ------------------------------------------------------------------
# TestMissingArchive
# ------------------------------------------------------------------

@pytest.mark.unit
class TestMissingArchive:
    """Missing ZIP file raises FileOperationError."""

    def test_missing_zip_raises(self, tmp_path):
        comp = _make_component({
            "zipfile": str(tmp_path / "does_not_exist.zip"),
            "directory": str(tmp_path / "out"),
        })
        with pytest.raises((ComponentExecutionError, FileOperationError), match="does not exist"):
            comp.execute()


# ------------------------------------------------------------------
# TestBadZip
# ------------------------------------------------------------------

@pytest.mark.unit
class TestBadZip:
    """Corrupt ZIP file raises FileOperationError."""

    def test_corrupt_zip_raises(self, tmp_path):
        bad_zip = str(tmp_path / "corrupt.zip")
        with open(bad_zip, "wb") as f:
            f.write(b"not a zip file at all")
        comp = _make_component({
            "zipfile": bad_zip,
            "directory": str(tmp_path / "out"),
        })
        with pytest.raises((ComponentExecutionError, FileOperationError), match="[Bb]ad|[Cc]orrupt"):
            comp.execute()


# ------------------------------------------------------------------
# Plan 14-08 coverage lift: missed-line clusters
#   119 (zf.setpassword), 147-148 (directory-entry skip),
#   161 (printout=True debug log), 168 (OSError -> FileOperationError).
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCoverageLift1408:
    """Targeted tests added in Plan 14-08 to lift file_unarchive.py to >= 95%."""

    def test_password_protected_zip_setpassword_called(self, tmp_path, monkeypatch):
        """checkpassword=True with password sets archive password (line 119).

        We can't easily produce a real encrypted-by-stdlib zip, so monkeypatch
        ZipFile.setpassword to record that it was invoked with our password.
        """
        zip_path = _make_zip(tmp_path, {"a.txt": b"hello"})
        recorded: dict = {}
        original_setpw = zipfile.ZipFile.setpassword

        def fake_setpw(self_zf, pwd):
            recorded["pwd"] = pwd
            # Don't actually encrypt; just record the call.
            return original_setpw(self_zf, pwd)

        monkeypatch.setattr(zipfile.ZipFile, "setpassword", fake_setpw)

        comp = _make_component({
            "zipfile": zip_path,
            "directory": str(tmp_path / "out"),
            "checkpassword": True,
            "password": "secret",
        })
        result = comp.execute()
        assert recorded["pwd"] == b"secret"
        assert isinstance(result["main"], pd.DataFrame)

    def test_directory_entry_creates_dir_and_skips(self, tmp_path):
        """ZIP member ending in '/' creates directory and continues (lines 147-148)."""
        zip_path = str(tmp_path / "with_dir.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            # Explicit directory entry
            zf.writestr("subdir/", "")
            zf.writestr("subdir/leaf.txt", b"content")
        out_dir = str(tmp_path / "out")
        comp = _make_component({"zipfile": zip_path, "directory": out_dir})
        comp.execute()
        assert os.path.isdir(os.path.join(out_dir, "subdir"))
        assert os.path.isfile(os.path.join(out_dir, "subdir", "leaf.txt"))

    def test_printout_logs_extracted_filename(self, tmp_path, caplog):
        """printout=True emits DEBUG log per file (line 161)."""
        import logging
        zip_path = _make_zip(tmp_path, {"a.txt": b"hello"})
        comp = _make_component({
            "zipfile": zip_path,
            "directory": str(tmp_path / "out"),
            "printout": True,
        })
        with caplog.at_level(logging.DEBUG, logger="src.v1.engine.components.file.file_unarchive"):
            comp.execute()
        assert any(
            "Extracted" in r.message and "a.txt" in r.message
            for r in caplog.records
            if r.levelno == logging.DEBUG
        )

    def test_oserror_during_extraction_raises_file_operation_error(self, tmp_path, monkeypatch):
        """OSError during extraction is wrapped as FileOperationError (line 168).

        We force `open(target_path, "wb")` (the destination write) to raise
        OSError so the surrounding `except OSError` branch fires.
        """
        zip_path = _make_zip(tmp_path, {"a.txt": b"hello"})
        comp = _make_component({
            "zipfile": zip_path,
            "directory": str(tmp_path / "out"),
        })

        # Force the write step inside _process to raise an OSError.
        import builtins
        original_open = builtins.open

        def selective_open(path, *args, **kwargs):
            if isinstance(path, str) and path.endswith("a.txt") and "w" in (args[0] if args else kwargs.get("mode", "")):
                raise OSError("disk full simulation")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", selective_open)

        # execute() wraps FileOperationError into ComponentExecutionError; both
        # ETLError subclasses are accepted since the source exception is the
        # FileOperationError raised at file_unarchive.py:168.
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="I/O error during extraction",
        ):
            comp.execute()
