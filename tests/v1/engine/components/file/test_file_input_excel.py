"""Tests for FileInputExcel (tFileInputExcel engine implementation).

Phase 7.2-01 regression tests: prove that header / first_column .isdigit()
content checks are deferred from _validate_config to _process so that
legitimate ${context.HEADER} / ${context.FIRST_COL} references are
accepted at validate time and resolved / re-validated at process time.

Scope: header and first_column only (per CONTEXT.md decision A).
footer and limit checks are explicitly retained in _validate_config.
"""
import openpyxl
import pandas as pd
import pytest

from src.v1.engine.components.file.file_input_excel import FileInputExcel
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_component(config, context_manager=None, global_map=None):
    """Create a FileInputExcel with explicit config.

    Mirrors BaseComponent.execute() Step 1 by populating ``self.config``
    so that direct ``_validate_config()`` calls work in isolation.
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    comp = FileInputExcel(
        component_id="tFIE_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(config)
    comp.output_schema = None
    return comp


def _make_xlsx(tmp_path):
    """Write a small xlsx fixture with two columns and three data rows."""
    p = tmp_path / "input.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["name", "age"])
    ws.append(["alice", 25])
    ws.append(["bob", 30])
    ws.append(["carol", 35])
    wb.save(str(p))
    return str(p)


# ------------------------------------------------------------------
# header: validate accepts context-var, process resolves, invalid raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestHeaderContextVar:
    """header accepts ${context.HEADER} at validate time."""

    def test_validate_config_accepts_context_var_header(self, tmp_path):
        config = {
            "filepath": _make_xlsx(tmp_path),
            "header": "${context.HEADER}",
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        # Must NOT contain a header error -- decision A defers it
        assert all("'header'" not in e for e in errors)

    def test_process_resolves_context_var_header(self, tmp_path):
        cm = ContextManager()
        cm.set("HEADER", "1")
        config = {
            "filepath": _make_xlsx(tmp_path),
            "header": "${context.HEADER}",
            "die_on_error": True,
        }
        comp = _make_component(config, context_manager=cm)
        result = comp.execute()
        assert "main" in result
        df = result["main"]
        # 3 data rows (header row consumed)
        assert len(df) == 3

    def test_process_invalid_resolved_header_raises(self, tmp_path):
        config = {
            "filepath": _make_xlsx(tmp_path),
            "header": "abc",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="header"):
            comp.execute()


# ------------------------------------------------------------------
# first_column: validate accepts context-var, process resolves, invalid raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFirstColumnContextVar:
    """first_column accepts ${context.FIRST_COL} at validate time."""

    def test_validate_config_accepts_context_var_first_column(self, tmp_path):
        config = {
            "filepath": _make_xlsx(tmp_path),
            "first_column": "${context.FIRST_COL}",
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        assert all("first_column" not in e for e in errors)

    def test_process_resolves_context_var_first_column(self, tmp_path):
        cm = ContextManager()
        cm.set("FIRST_COL", "1")
        config = {
            "filepath": _make_xlsx(tmp_path),
            "first_column": "${context.FIRST_COL}",
            "die_on_error": True,
        }
        comp = _make_component(config, context_manager=cm)
        result = comp.execute()
        assert "main" in result
        # 3 data rows
        assert len(result["main"]) == 3

    def test_process_invalid_resolved_first_column_raises(self, tmp_path):
        config = {
            "filepath": _make_xlsx(tmp_path),
            "first_column": "0",  # zero is not a positive integer
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="first_column"):
            comp.execute()


# ------------------------------------------------------------------
# Out-of-scope: footer and limit checks must remain in _validate_config
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFooterAndLimitStillStrict:
    """Per CONTEXT.md decision A: footer / limit checks remain in
    _validate_config (out-of-scope for this phase). Verify they still
    flag bad string values at validate time."""

    def test_footer_string_still_caught_at_validate(self, tmp_path):
        config = {
            "filepath": _make_xlsx(tmp_path),
            "footer": "abc",
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        assert any("footer" in e for e in errors)

    def test_limit_bad_string_still_caught_at_validate(self, tmp_path):
        config = {
            "filepath": _make_xlsx(tmp_path),
            "limit": "abc",
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        assert any("limit" in e for e in errors)
