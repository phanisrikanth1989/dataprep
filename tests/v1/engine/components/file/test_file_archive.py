"""Tests for FileArchive engine component (tFileArchive).

Test classes:
    TestRegistration       -- registry decorator, BaseComponent inheritance
    TestValidation         -- _validate_config structural checks (Rule 12)
    TestArchiveSingleFile  -- archive a single file to ZIP
    TestArchiveDirectory   -- archive a directory tree
    TestSubDirectory       -- sub_directroy=False suppresses recursion
    TestMkdir              -- mkdir=True/False controls directory creation
    TestOverwrite          -- overwrite=True/False behavior
    TestFileMask           -- all_files=False + mask filters files
    TestCompressionLevel   -- level TEXT field; context-var safe coercion
    TestGlobalMapVars      -- ARCHIVE_FILEPATH / ARCHIVE_FILENAME set correctly
    TestFormatValidation   -- unsupported archive_format raises FileOperationError
    TestMissingSource      -- source path does not exist raises FileOperationError
"""
import os
import zipfile

import pytest
import pandas as pd

from src.v1.engine.components.file.file_archive import FileArchive
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
    comp = FileArchive(
        component_id="tFileArchive_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    # Seed self.config so direct _validate_config() calls work without execute()
    comp.config = dict(config)
    return comp


def _make_source_dir(tmp_path, with_subdir=True):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("alpha", encoding="utf-8")
    (src / "b.txt").write_text("beta", encoding="utf-8")
    if with_subdir:
        sub = src / "sub"
        sub.mkdir()
        (sub / "c.txt").write_text("gamma", encoding="utf-8")
    return str(src)


def _make_source_file(tmp_path):
    f = tmp_path / "single.txt"
    f.write_text("hello", encoding="utf-8")
    return str(f)


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    """Registry decorator, BaseComponent inheritance."""

    def test_v1_name_registered(self):
        assert REGISTRY.get("FileArchive") is FileArchive

    def test_legacy_class_name_registered(self):
        assert REGISTRY.get("FileArchiveComponent") is FileArchive

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tFileArchive") is FileArchive

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(FileArchive, BaseComponent)


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidation:
    """_validate_config() -- structural checks, raises ConfigurationError."""

    def test_missing_source_raises(self, tmp_path):
        comp = _make_component({"target": str(tmp_path / "out.zip")})
        with pytest.raises(ConfigurationError, match="source"):
            comp._validate_config()

    def test_missing_target_raises(self, tmp_path):
        comp = _make_component({"source": str(tmp_path), "target": ""})
        with pytest.raises(ConfigurationError, match="target"):
            comp._validate_config()

    def test_valid_config_does_not_raise(self, tmp_path):
        comp = _make_component({"source": str(tmp_path), "target": str(tmp_path / "out.zip")})
        comp._validate_config()  # must not raise

    def test_bad_bool_sub_directroy_raises(self, tmp_path):
        comp = _make_component({
            "source": str(tmp_path),
            "target": str(tmp_path / "out.zip"),
            "sub_directroy": "yes",
        })
        with pytest.raises(ConfigurationError, match="sub_directroy"):
            comp._validate_config()

    def test_bad_bool_overwrite_raises(self, tmp_path):
        comp = _make_component({
            "source": str(tmp_path),
            "target": str(tmp_path / "out.zip"),
            "overwrite": 1,
        })
        with pytest.raises(ConfigurationError, match="overwrite"):
            comp._validate_config()

    def test_context_var_in_level_passes_validation(self, tmp_path):
        """level is TEXT -- context vars must be accepted at validate time."""
        comp = _make_component({
            "source": str(tmp_path),
            "target": str(tmp_path / "out.zip"),
            "level": "${context.LEVEL}",
        })
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestArchiveSingleFile
# ------------------------------------------------------------------

@pytest.mark.unit
class TestArchiveSingleFile:
    """Archive a single file."""

    def test_creates_zip(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "out.zip")
        comp = _make_component({"source": src, "target": target})
        result = comp.execute()
        assert os.path.exists(target)
        assert "main" in result

    def test_zip_contains_file(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "out.zip")
        _make_component({"source": src, "target": target}).execute()
        with zipfile.ZipFile(target) as zf:
            assert "single.txt" in zf.namelist()

    def test_returns_empty_dataframe(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "out.zip")
        result = _make_component({"source": src, "target": target}).execute()
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty


# ------------------------------------------------------------------
# TestArchiveDirectory
# ------------------------------------------------------------------

@pytest.mark.unit
class TestArchiveDirectory:
    """Archive a directory tree (default: with subdirectories)."""

    def test_creates_zip_from_dir(self, tmp_path):
        src = _make_source_dir(tmp_path)
        target = str(tmp_path / "arch.zip")
        _make_component({"source": src, "target": target}).execute()
        assert os.path.exists(target)

    def test_zip_includes_subdir_files(self, tmp_path):
        src = _make_source_dir(tmp_path)
        target = str(tmp_path / "arch.zip")
        _make_component({"source": src, "target": target}).execute()
        with zipfile.ZipFile(target) as zf:
            names = zf.namelist()
        assert any("sub" in n for n in names)


# ------------------------------------------------------------------
# TestSubDirectory
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSubDirectory:
    """sub_directroy=False prevents recursion into subdirectories."""

    def test_no_subdir_excludes_sub_files(self, tmp_path):
        src = _make_source_dir(tmp_path)
        target = str(tmp_path / "flat.zip")
        _make_component({
            "source": src,
            "target": target,
            "sub_directroy": False,
        }).execute()
        with zipfile.ZipFile(target) as zf:
            names = zf.namelist()
        assert not any("sub" in n for n in names)
        assert "a.txt" in names and "b.txt" in names


# ------------------------------------------------------------------
# TestMkdir
# ------------------------------------------------------------------

@pytest.mark.unit
class TestMkdir:
    """mkdir=True creates missing target directory; mkdir=False raises."""

    def test_mkdir_true_creates_dir(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "new_dir" / "out.zip")
        _make_component({"source": src, "target": target, "mkdir": True}).execute()
        assert os.path.exists(target)

    def test_mkdir_false_raises_when_dir_missing(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "missing_dir" / "out.zip")
        comp = _make_component({"source": src, "target": target, "mkdir": False})
        with pytest.raises((ComponentExecutionError, FileOperationError), match="mkdir"):
            comp.execute()


# ------------------------------------------------------------------
# TestOverwrite
# ------------------------------------------------------------------

@pytest.mark.unit
class TestOverwrite:
    """overwrite=True replaces existing archive; overwrite=False raises."""

    def test_overwrite_true_replaces(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "out.zip")
        _make_component({"source": src, "target": target}).execute()
        _make_component({"source": src, "target": target, "overwrite": True}).execute()
        assert os.path.exists(target)

    def test_overwrite_false_raises(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "out.zip")
        _make_component({"source": src, "target": target}).execute()
        comp = _make_component({"source": src, "target": target, "overwrite": False})
        with pytest.raises((ComponentExecutionError, FileOperationError), match="overwrite"):
            comp.execute()


# ------------------------------------------------------------------
# TestFileMask
# ------------------------------------------------------------------

@pytest.mark.unit
class TestFileMask:
    """all_files=False + mask filters which files enter the archive."""

    def test_mask_filters_txt_only(self, tmp_path):
        src = _make_source_dir(tmp_path, with_subdir=False)
        (tmp_path / "src" / "data.csv").write_text("a,b", encoding="utf-8")
        target = str(tmp_path / "out.zip")
        _make_component({
            "source": src,
            "target": target,
            "all_files": False,
            "mask": "*.txt",
            "sub_directroy": False,
        }).execute()
        with zipfile.ZipFile(target) as zf:
            names = zf.namelist()
        assert all(n.endswith(".txt") for n in names)
        assert not any(n.endswith(".csv") for n in names)


# ------------------------------------------------------------------
# TestCompressionLevel
# ------------------------------------------------------------------

@pytest.mark.unit
class TestCompressionLevel:
    """level TEXT field; resolved context vars coerced to int in _process."""

    def test_level_string_integer(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "out.zip")
        _make_component({"source": src, "target": target, "level": "6"}).execute()
        assert os.path.exists(target)

    def test_level_zero_uses_stored(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "stored.zip")
        _make_component({"source": src, "target": target, "level": "0"}).execute()
        with zipfile.ZipFile(target) as zf:
            info = zf.infolist()[0]
        assert info.compress_type == zipfile.ZIP_STORED

    def test_invalid_level_raises(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "out.zip")
        comp = _make_component({"source": src, "target": target, "level": "bad"})
        with pytest.raises(ConfigurationError, match="level"):
            comp.execute()

    def test_context_var_resolved_level(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "ctx.zip")
        cm = ContextManager()
        cm.set("LEVEL", "5")
        comp = _make_component(
            {"source": src, "target": target, "level": "${context.LEVEL}"},
            context_manager=cm,
        )
        comp.execute()
        assert os.path.exists(target)


# ------------------------------------------------------------------
# TestGlobalMapVars
# ------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapVars:
    """ARCHIVE_FILEPATH and ARCHIVE_FILENAME are set in globalMap."""

    def test_archive_filepath_set(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "out.zip")
        gm = GlobalMap()
        _make_component({"source": src, "target": target}, global_map=gm).execute()
        assert gm.get("tFileArchive_1_ARCHIVE_FILEPATH") == os.path.abspath(target)

    def test_archive_filename_set(self, tmp_path):
        src = _make_source_file(tmp_path)
        target = str(tmp_path / "out.zip")
        gm = GlobalMap()
        _make_component({"source": src, "target": target}, global_map=gm).execute()
        assert gm.get("tFileArchive_1_ARCHIVE_FILENAME") == "out.zip"


# ------------------------------------------------------------------
# TestFormatValidation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestFormatValidation:
    """Unsupported archive_format raises FileOperationError."""

    def test_tar_format_raises(self, tmp_path):
        src = _make_source_file(tmp_path)
        comp = _make_component({
            "source": src,
            "target": str(tmp_path / "out.tar"),
            "archive_format": "tar",
        })
        with pytest.raises((ComponentExecutionError, FileOperationError), match="format"):
            comp.execute()


# ------------------------------------------------------------------
# TestMissingSource
# ------------------------------------------------------------------

@pytest.mark.unit
class TestMissingSource:
    """Source path does not exist raises FileOperationError."""

    def test_missing_source_raises(self, tmp_path):
        comp = _make_component({
            "source": str(tmp_path / "does_not_exist"),
            "target": str(tmp_path / "out.zip"),
        })
        with pytest.raises((ComponentExecutionError, FileOperationError), match="does not exist"):
            comp.execute()


# ------------------------------------------------------------------
# Process: invalid resolved compression_level still raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestProcessInvalidResolvedRaises:
    """_process must raise ConfigurationError on bad resolved value."""

    def test_process_invalid_resolved_compression_level_raises(self, tmp_path):
        src = _make_source_dir(tmp_path)
        target = str(tmp_path / "out.zip")
        config = {
            "source": src,
            "target": target,
            "level": "not_a_number",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises((ConfigurationError, ComponentExecutionError), match="level|integer"):
            comp.execute()

    def test_process_out_of_range_compression_level_raises(self, tmp_path):
        src = _make_source_dir(tmp_path)
        target = str(tmp_path / "out.zip")
        config = {
            "source": src,
            "target": target,
            "level": "11",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises((ConfigurationError, ComponentExecutionError), match="level|0-9|integer"):
            comp.execute()
