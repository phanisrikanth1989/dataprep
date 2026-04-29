"""Tests for FileInputPositional (tFileInputPositional engine implementation).

Phase 7.2-01 regression tests: prove that pattern / header_rows /
footer_rows / limit content checks are deferred from _validate_config to
_process so that legitimate ${context.X} references are accepted at
validate time and resolved / re-validated at process time.
"""
import pandas as pd
import pytest

from src.v1.engine.components.file.file_input_positional import FileInputPositional
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_component(config, context_manager=None, global_map=None, schema=None):
    """Create a FileInputPositional with explicit config.

    Mirrors BaseComponent.execute() Step 1 by populating ``self.config``
    so that direct ``_validate_config()`` calls work in isolation.
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    comp = FileInputPositional(
        component_id="tFIP_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(config)
    comp.output_schema = schema
    return comp


def _make_fwf_file(tmp_path, content="alice0025\nbob  0030\ncharl0035\n"):
    """Write a small fixed-width text file. Default schema: name(5) age(4)."""
    p = tmp_path / "input.txt"
    p.write_text(content, encoding="utf-8")
    return str(p)


# ------------------------------------------------------------------
# Pattern: validate accepts context-var, process resolves, invalid raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPatternContextVar:
    """pattern field accepts ${context.WIDTHS} at validate time."""

    def test_validate_config_accepts_context_var_pattern(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "${context.WIDTHS}",
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        assert errors == []

    def test_process_resolves_context_var_pattern(self, tmp_path):
        cm = ContextManager()
        cm.set("WIDTHS", "5,4")
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "${context.WIDTHS}",
            "die_on_error": True,
        }
        comp = _make_component(config, context_manager=cm)
        result = comp.execute()
        assert "main" in result
        df = result["main"]
        assert len(df) == 3
        # Two columns (5-wide name, 4-wide age)
        assert df.shape[1] == 2

    def test_process_invalid_resolved_pattern_raises(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "abc,def",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="comma-separated integers"):
            comp.execute()

    def test_process_negative_pattern_widths_raises(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,-4",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="positive integers"):
            comp.execute()


# ------------------------------------------------------------------
# header_rows: validate accepts, process resolves, invalid raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestHeaderRowsContextVar:
    """header_rows accepts ${context.HEADER_ROWS} at validate time."""

    def test_validate_config_accepts_context_var_header_rows(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "header_rows": "${context.HEADER_ROWS}",
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        assert errors == []

    def test_process_resolves_context_var_header_rows(self, tmp_path):
        cm = ContextManager()
        cm.set("HEADER_ROWS", "1")
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "header_rows": "${context.HEADER_ROWS}",
            "die_on_error": True,
        }
        comp = _make_component(config, context_manager=cm)
        result = comp.execute()
        # 3 raw rows minus 1 header = 2 data rows
        assert len(result["main"]) == 2

    def test_process_invalid_resolved_header_rows_raises(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "header_rows": "not_a_number",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="header_rows"):
            comp.execute()


# ------------------------------------------------------------------
# footer_rows: validate accepts, process resolves, invalid raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFooterRowsContextVar:
    """footer_rows accepts ${context.FOOTER_ROWS} at validate time."""

    def test_validate_config_accepts_context_var_footer_rows(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "footer_rows": "${context.FOOTER_ROWS}",
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        assert errors == []

    def test_process_resolves_context_var_footer_rows(self, tmp_path):
        cm = ContextManager()
        cm.set("FOOTER_ROWS", "1")
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "footer_rows": "${context.FOOTER_ROWS}",
            "die_on_error": True,
        }
        comp = _make_component(config, context_manager=cm)
        result = comp.execute()
        # 3 raw rows minus 1 footer = 2 data rows
        assert len(result["main"]) == 2

    def test_process_invalid_resolved_footer_rows_raises(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "footer_rows": "abc",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="footer_rows"):
            comp.execute()


# ------------------------------------------------------------------
# limit: validate accepts, process resolves, invalid raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestLimitContextVar:
    """limit accepts ${context.LIMIT} at validate time."""

    def test_validate_config_accepts_context_var_limit(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "limit": "${context.LIMIT}",
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        assert errors == []

    def test_process_resolves_context_var_limit(self, tmp_path):
        cm = ContextManager()
        cm.set("LIMIT", "2")
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "limit": "${context.LIMIT}",
            "die_on_error": True,
        }
        comp = _make_component(config, context_manager=cm)
        result = comp.execute()
        # limit=2 -> only 2 rows
        assert len(result["main"]) == 2

    def test_process_invalid_resolved_limit_raises(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "limit": "abc",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="limit"):
            comp.execute()
