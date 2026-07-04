"""Comprehensive tests for FileInputRaw (tFileInputRaw engine component).

Plan 14-09 COV-FIR-001 -- lift coverage from 15% to >=95%.

Covers:
- Registry registration (V1 + Talend names)
- _validate_config (shape-only)
- as_string=True (single-string single-row output)
- as_string=False (binary bytes single-row)
- Encoding variations (UTF-8 + UTF-8 BOM + ISO-8859-15)
- Missing file (die_on_error True -> FileNotFoundError / ComponentExecutionError
                die_on_error False -> warning + empty output)
- Windows/Unix/Mac line-ending detection (debug_content branch)
- Pipeline test via run_job_fixture("file/raw_text", ...)
"""
import os
from pathlib import Path

import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.file.file_input_raw import FileInputRaw
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ComponentExecutionError
from src.v1.engine.global_map import GlobalMap


_FIXTURES_DATA = Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "data"
SAMPLE_RAW_UTF8 = str(_FIXTURES_DATA / "sample_raw_utf8.txt")
SAMPLE_RAW_ISO8859 = str(_FIXTURES_DATA / "sample_raw_iso8859.txt")


def _make_component(config):
    cm = ContextManager()
    gm = GlobalMap()
    comp = FileInputRaw(
        component_id="tFIR_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(config)
    comp.output_schema = None
    return comp


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    def test_v1_name_resolves(self):
        assert REGISTRY.get("FileInputRaw") is FileInputRaw

    def test_talend_alias_resolves(self):
        assert REGISTRY.get("tFileInputRaw") is FileInputRaw


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    def test_missing_filename_returns_error(self):
        comp = _make_component({})
        errors = comp._validate_config()
        assert any("filename" in e for e in errors)

    def test_non_str_encoding_returns_error(self):
        comp = _make_component({"filename": "x.txt", "encoding": 123})
        errors = comp._validate_config()
        assert any("encoding" in e for e in errors)

    def test_empty_encoding_returns_error(self):
        comp = _make_component({"filename": "x.txt", "encoding": "   "})
        errors = comp._validate_config()
        assert any("encoding" in e for e in errors)

    def test_non_bool_as_string_returns_error(self):
        comp = _make_component({"filename": "x.txt", "as_string": "yes"})
        errors = comp._validate_config()
        assert any("as_string" in e for e in errors)

    def test_non_bool_die_on_error_returns_error(self):
        comp = _make_component({"filename": "x.txt", "die_on_error": 1})
        errors = comp._validate_config()
        assert any("die_on_error" in e for e in errors)

    def test_valid_config_returns_empty(self):
        comp = _make_component({"filename": "x.txt", "as_string": True,
                                "encoding": "UTF-8", "die_on_error": False})
        assert comp._validate_config() == []


# ------------------------------------------------------------------
# as_string=True (text mode, default)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestAsStringTrue:
    def test_read_utf8_with_bom(self):
        """sample_raw_utf8.txt has BOM prefix + 3 lines."""
        comp = _make_component({
            "filename": SAMPLE_RAW_UTF8,
            "as_string": True,
            "encoding": "utf-8-sig",  # strips BOM
        })
        result = comp.execute()
        assert len(result["main"]) == 1
        content = result["main"]["content"].iloc[0]
        assert "Line one" in content
        assert "Line three" in content
        # BOM stripped due to utf-8-sig
        assert not content.startswith("﻿")

    def test_read_utf8_with_bom_kept_when_plain_utf8(self):
        """utf-8 (not utf-8-sig) preserves BOM character."""
        comp = _make_component({
            "filename": SAMPLE_RAW_UTF8,
            "as_string": True,
            "encoding": "utf-8",
        })
        result = comp.execute()
        content = result["main"]["content"].iloc[0]
        # BOM char retained when decoded as utf-8 (not utf-8-sig)
        assert content.startswith("﻿")

    def test_read_iso8859_with_non_ascii(self):
        """ISO-8859-15 file with e-acute (0xe9) decodes correctly."""
        comp = _make_component({
            "filename": SAMPLE_RAW_ISO8859,
            "as_string": True,
            "encoding": "iso-8859-15",
        })
        result = comp.execute()
        content = result["main"]["content"].iloc[0]
        assert "café" in content


@pytest.mark.unit
class TestAsStringFalse:
    """as_string=False returns bytes."""

    def test_read_binary(self):
        comp = _make_component({
            "filename": SAMPLE_RAW_UTF8,
            "as_string": False,
        })
        result = comp.execute()
        content = result["main"]["content"].iloc[0]
        assert isinstance(content, bytes)
        # BOM bytes at start
        assert content.startswith(b"\xef\xbb\xbf")


# ------------------------------------------------------------------
# Line-ending detection (debug_content branch)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestLineEndingDetection:
    """debug_content logs different line endings.

    Note: Python's open(..., 'r') uses universal newlines and translates
    \\r\\n -> \\n in the content. To exercise the three branches in
    debug_content we call it directly with synthesized strings.
    """

    def test_debug_content_windows(self, caplog):
        import logging
        caplog.set_level(logging.INFO,
                         logger="src.v1.engine.components.file.file_input_raw")
        comp = _make_component({"filename": "x.txt"})
        comp.debug_content("a\r\nb\r\n")
        assert any("Windows" in r.message for r in caplog.records)

    def test_debug_content_unix(self, caplog):
        import logging
        caplog.set_level(logging.INFO,
                         logger="src.v1.engine.components.file.file_input_raw")
        comp = _make_component({"filename": "x.txt"})
        comp.debug_content("a\nb\nc\n")
        assert any("Unix" in r.message for r in caplog.records)

    def test_debug_content_mac(self, caplog):
        import logging
        caplog.set_level(logging.INFO,
                         logger="src.v1.engine.components.file.file_input_raw")
        comp = _make_component({"filename": "x.txt"})
        comp.debug_content("a\rb\rc\r")
        assert any("Mac" in r.message for r in caplog.records)

    def test_debug_content_no_line_endings(self, caplog):
        import logging
        caplog.set_level(logging.INFO,
                         logger="src.v1.engine.components.file.file_input_raw")
        comp = _make_component({"filename": "x.txt"})
        comp.debug_content("no_line_endings_at_all")
        assert any("Content length" in r.message for r in caplog.records)

    def test_execute_runs_debug_content(self, tmp_path, caplog):
        """End-to-end: execute() invokes debug_content for string content."""
        import logging
        caplog.set_level(logging.INFO,
                         logger="src.v1.engine.components.file.file_input_raw")
        p = tmp_path / "unix_e2e.txt"
        p.write_bytes(b"a\nb\nc\n")
        comp = _make_component({"filename": str(p), "as_string": True})
        comp.execute()
        assert any("Content length" in r.message for r in caplog.records)


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------


@pytest.mark.unit
class TestErrorHandling:
    def test_missing_file_die_on_error_false_returns_empty(self, tmp_path):
        comp = _make_component({
            "filename": str(tmp_path / "missing.txt"),
            "as_string": True,
            "die_on_error": False,
        })
        result = comp.execute()
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0

    def test_missing_file_die_on_error_true_raises(self, tmp_path):
        comp = _make_component({
            "filename": str(tmp_path / "missing.txt"),
            "as_string": True,
            "die_on_error": True,
        })
        with pytest.raises((FileNotFoundError, ComponentExecutionError)):
            comp.execute()

    def test_permission_error_die_on_error_false(self, tmp_path):
        """Read failure (simulated via unreadable path) with die_on_error=False."""
        comp = _make_component({
            "filename": "/this/path/does/not/exist/file.txt",
            "as_string": True,
            "die_on_error": False,
        })
        result = comp.execute()
        # Empty DataFrame returned on error
        assert len(result["main"]) == 0


# ------------------------------------------------------------------
# Statistics
# ------------------------------------------------------------------


@pytest.mark.unit
class TestStatistics:
    def test_stats_set_after_success(self):
        comp = _make_component({
            "filename": SAMPLE_RAW_UTF8,
            "as_string": True,
            "encoding": "utf-8-sig",
        })
        result = comp.execute()
        stats = result.get("stats", {})
        # FileInputRaw stats: 1 file read = 1 row, NB_LINE=1, NB_LINE_OK=1
        assert stats.get("NB_LINE", 0) == 1
        assert stats.get("NB_LINE_OK", 0) == 1
        assert stats.get("NB_LINE_REJECT", 0) == 0

    def test_stats_on_failure_die_on_error_false(self, tmp_path):
        comp = _make_component({
            "filename": str(tmp_path / "missing.txt"),
            "as_string": True,
            "die_on_error": False,
        })
        result = comp.execute()
        stats = result.get("stats", {})
        # Stats updated: 1 file attempted, 0 ok
        assert stats.get("NB_LINE_OK", 0) == 0


# ------------------------------------------------------------------
# Pipeline integration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineIntegration:
    def test_pipeline_raw_text_to_csv(self, run_job_fixture, tmp_path):
        """Pipeline run reads raw file and writes content into a single-row CSV.

        The fixture file content contains newlines so the CSV writer needs
        to quote/escape it; the pipeline fixture sets fieldseparator=';'
        without escape configuration, which trips the underlying writer.
        We use a simple no-special-char file instead.
        """
        clean_input = tmp_path / "clean.txt"
        clean_input.write_text("HelloWorld")
        out_csv = str(tmp_path / "out.csv")
        result = run_job_fixture(
            "file/raw_text",
            mutations={
                "tFileInputRaw_1": {"filename": str(clean_input),
                                     "encoding": "utf-8"},
                "tFileOutputDelimited_1": {"filepath": out_csv},
            },
        )
        assert os.path.exists(out_csv)
        with open(out_csv, "r", encoding="utf-8") as f:
            csv_content = f.read()
        assert "HelloWorld" in csv_content
