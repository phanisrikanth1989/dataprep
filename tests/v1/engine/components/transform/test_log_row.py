"""Tests for LogRow (tLogRow engine implementation).

Phase 7.2-01 regression tests: prove that max_rows content check is
deferred from _validate_config to _process so that legitimate
${context.MAX_ROWS} references are accepted at validate time and resolved
/ re-validated at process time.
"""
import pandas as pd
import pytest

from src.v1.engine.components.transform.log_row import LogRow
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_component(config, context_manager=None, global_map=None):
    """Create a LogRow with explicit config.

    Mirrors BaseComponent.execute() Step 1 by populating ``self.config``
    so that direct ``_validate_config()`` calls work in isolation.
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    comp = LogRow(
        component_id="tLogRow_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(config)
    return comp


def _sample_df():
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "name": ["a", "b", "c", "d", "e"],
    })


# ------------------------------------------------------------------
# max_rows: validate accepts context-var, process resolves, invalid raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMaxRowsContextVar:
    """max_rows accepts ${context.MAX_ROWS} at validate time."""

    def test_validate_config_accepts_context_var_max_rows(self):
        config = {"max_rows": "${context.MAX_ROWS}"}
        comp = _make_component(config)
        errors = comp._validate_config()
        assert errors == []

    def test_validate_config_empty_returns_empty_errors(self):
        comp = _make_component({})
        assert comp._validate_config() == []

    def test_process_resolves_context_var_max_rows(self, capsys):
        cm = ContextManager()
        cm.set("MAX_ROWS", "2")
        config = {
            "max_rows": "${context.MAX_ROWS}",
            "basic_mode": True,
            "table_print": False,
            "print_header": False,
        }
        comp = _make_component(config, context_manager=cm)
        result = comp.execute(_sample_df())
        # Pass-through unchanged
        assert len(result["main"]) == 5
        # But only first 2 rows logged
        captured = capsys.readouterr()
        # Output should contain only 2 rows of basic-mode lines
        printed_lines = [
            line for line in captured.out.splitlines()
            if line.strip() and not line.startswith("[")
        ]
        # In basic_mode without print_header, exactly max_rows lines
        assert len(printed_lines) == 2

    def test_process_invalid_resolved_max_rows_raises(self):
        config = {
            "max_rows": "not_a_number",
            "basic_mode": True,
            "table_print": False,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="max_rows"):
            comp.execute(_sample_df())

    def test_process_negative_resolved_max_rows_raises(self):
        config = {
            "max_rows": "-3",
            "basic_mode": True,
            "table_print": False,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="non-negative"):
            comp.execute(_sample_df())
