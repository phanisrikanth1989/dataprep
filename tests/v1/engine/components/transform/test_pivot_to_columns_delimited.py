"""Tests for PivotToColumnsDelimited (tPivotToColumnsDelimited engine implementation).

Phase 7.2-01 regression tests: prove that field_separator len()==1 check
is deferred from _validate_config to _process so legitimate ${context.SEP}
references are accepted at validate time and re-validated at process
time. This is the direct CR-06 clone (same pattern as
file_output_delimited.py / quick task 260429-hc2).
"""
import pandas as pd
import pytest

from src.v1.engine.components.transform.pivot_to_columns_delimited import (
    PivotToColumnsDelimited,
)
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_component(config, context_manager=None, global_map=None):
    """Create a PivotToColumnsDelimited with explicit config.

    Mirrors BaseComponent.execute() Step 1 by populating ``self.config``
    so that direct ``_validate_config()`` calls work in isolation.
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    comp = PivotToColumnsDelimited(
        component_id="tPivot_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(config)
    return comp


def _sample_df():
    return pd.DataFrame({
        "region": ["N", "N", "S", "S"],
        "category": ["A", "B", "A", "B"],
        "amount": [10, 20, 30, 40],
    })


def _base_config(tmp_path, **overrides):
    cfg = {
        "pivot_column": "category",
        "aggregation_column": "amount",
        "aggregation_function": "sum",
        "group_by_columns": ["region"],
        "filename": str(tmp_path / "out.csv"),
        "create": False,  # avoid pandas to_csv path differences
    }
    cfg.update(overrides)
    return cfg


# ------------------------------------------------------------------
# field_separator: validate accepts context-var, process resolves, invalid raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFieldSeparatorContextVar:
    """field_separator accepts ${context.SEP} at validate time."""

    def test_validate_config_accepts_context_var_field_separator(self, tmp_path):
        cfg = _base_config(tmp_path, field_separator="${context.SEP}")
        comp = _make_component(cfg)
        errors = comp._validate_config()
        # Should NOT contain a field_separator error -- decision A defers it
        assert all("field_separator" not in e for e in errors)

    def test_process_resolves_context_var_field_separator(self, tmp_path):
        cm = ContextManager()
        cm.set("SEP", ";")
        cfg = _base_config(
            tmp_path,
            field_separator="${context.SEP}",
            create=False,
        )
        comp = _make_component(cfg, context_manager=cm)
        result = comp.execute(_sample_df())
        assert "main" in result
        # Pivot produced 2 region rows
        assert len(result["main"]) == 2

    def test_process_invalid_resolved_field_separator_raises(self, tmp_path):
        cfg = _base_config(tmp_path, field_separator="abc")
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError, match="single-character"):
            comp.execute(_sample_df())


# ------------------------------------------------------------------
# Validation still rejects required-field misses
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRequiredFieldChecksRetained:
    """key-presence and isinstance shape checks must remain in _validate_config."""

    def test_missing_pivot_column_still_errors(self, tmp_path):
        cfg = _base_config(tmp_path)
        del cfg["pivot_column"]
        comp = _make_component(cfg)
        errors = comp._validate_config()
        assert any("pivot_column" in e for e in errors)

    def test_group_by_columns_must_be_list(self, tmp_path):
        cfg = _base_config(tmp_path, group_by_columns="region")
        comp = _make_component(cfg)
        errors = comp._validate_config()
        assert any("must be a list" in e for e in errors)
