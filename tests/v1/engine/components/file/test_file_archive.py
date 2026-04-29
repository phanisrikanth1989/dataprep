"""Tests for FileArchiveComponent (tFileArchive engine implementation).

Phase 7.2-01 regression tests: prove that compression_level content checks
are deferred from _validate_config to _process so that legitimate
${context.LEVEL} references are accepted at validate time and resolved /
re-validated at process time.
"""
import os
import zipfile

import pandas as pd
import pytest

from src.v1.engine.components.file.file_archive import FileArchiveComponent
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_component(config, context_manager=None, global_map=None):
    """Create a FileArchiveComponent with explicit config.

    Populates ``self.config`` from the original config so that direct
    ``_validate_config()`` calls (without going through ``execute()``)
    can inspect the same dict that ``execute()`` would.
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    comp = FileArchiveComponent(
        component_id="tFileArchive_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    # Mirror what BaseComponent.execute() Step 1 does, so unit tests of
    # _validate_config() in isolation work without invoking execute().
    comp.config = dict(config)
    return comp


def _make_source_dir(tmp_path):
    """Create a small source directory with two files for archiving."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("alpha", encoding="utf-8")
    (src / "b.txt").write_text("beta", encoding="utf-8")
    return str(src)


# ------------------------------------------------------------------
# Validation: context-var literal accepted at _validate_config time
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidateConfigAcceptsContextVar:
    """_validate_config must NOT measure unresolved compression_level."""

    def test_validate_config_accepts_context_var_compression_level(self, tmp_path):
        config = {
            "source": str(tmp_path / "src"),
            "target": str(tmp_path / "out.zip"),
            "compression_level": "${context.LEVEL}",
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        assert errors == []

    def test_validate_config_still_rejects_missing_source(self, tmp_path):
        config = {
            "target": str(tmp_path / "out.zip"),
            "compression_level": "5",
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        assert any("'source'" in e for e in errors)

    def test_validate_config_still_rejects_bad_archive_format(self, tmp_path):
        config = {
            "source": str(tmp_path / "src"),
            "target": str(tmp_path / "out.tar"),
            "archive_format": "tar",
            "compression_level": "5",
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        assert any("archive_format" in e for e in errors)


# ------------------------------------------------------------------
# Process: resolved context-var compression_level used correctly
# ------------------------------------------------------------------


@pytest.mark.unit
class TestProcessResolvesContextVar:
    """_process must use the resolved compression_level value."""

    def test_process_resolves_context_var_compression_level(self, tmp_path):
        src = _make_source_dir(tmp_path)
        target = str(tmp_path / "out.zip")
        cm = ContextManager()
        cm.set("LEVEL", "5")
        config = {
            "source": src,
            "target": target,
            "compression_level": "${context.LEVEL}",
            "die_on_error": True,
        }
        comp = _make_component(config, context_manager=cm)
        result = comp.execute()
        assert "main" in result
        assert os.path.exists(target)
        with zipfile.ZipFile(target, "r") as zf:
            names = sorted(zf.namelist())
        assert names == ["a.txt", "b.txt"]


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
            "compression_level": "not_a_number",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="must be a valid integer"):
            comp.execute()

    def test_process_out_of_range_compression_level_raises(self, tmp_path):
        src = _make_source_dir(tmp_path)
        target = str(tmp_path / "out.zip")
        config = {
            "source": src,
            "target": target,
            "compression_level": "11",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="between 0 and 9"):
            comp.execute()
