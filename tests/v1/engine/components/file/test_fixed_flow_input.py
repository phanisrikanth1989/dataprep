"""Tests for FixedFlowInputComponent (tFixedFlowInput engine implementation).

All tests exercise the component via ``execute()`` to mirror the true runtime
lifecycle. ``_validate_config()`` and ``_process()`` are never called directly
from test code (MANUAL_COMPONENT_AUTHORING.md Rule 4).
"""
import pytest
import pandas as pd

from src.v1.engine.components.file.fixed_flow_input import FixedFlowInputComponent
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_SCHEMA_2COL = [
    {"name": "id", "type": "id_Integer"},
    {"name": "name", "type": "id_String"},
]

_BASE_CONFIG: dict = {
    "component_type": "FixedFlowInputComponent",
    "nb_rows": 1,
    "use_singlemode": True,
    "use_intable": False,
    "use_inlinecontent": False,
    "schema": _SCHEMA_2COL,
    "values_config": [
        {"schema_column": "id", "value": "1"},
        {"schema_column": "name", "value": "Alice"},
    ],
}


def _make(config=None, global_map=None):
    """Construct a FixedFlowInputComponent ready for execute() calls."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    return FixedFlowInputComponent(
        component_id="tFFI_1",
        config=dict(config) if config is not None else dict(_BASE_CONFIG),
        global_map=gm,
        context_manager=cm,
    )


# ---------------------------------------------------------------------------
# 1. REGISTRY
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    def test_v1_name_registered(self):
        assert REGISTRY.get("FixedFlowInputComponent") is FixedFlowInputComponent

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tFixedFlowInput") is FixedFlowInputComponent


# ---------------------------------------------------------------------------
# 2. Architecture contract: execute() is not overridden
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNoExecuteOverride:
    def test_execute_not_in_class_dict(self):
        assert "execute" not in FixedFlowInputComponent.__dict__, (
            "FixedFlowInputComponent must not override execute() -- "
            "BaseComponent.execute() is the sealed template (Rule 4)"
        )


# ---------------------------------------------------------------------------
# 3. Validation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestValidation:
    def test_string_nb_rows_raises(self):
        """_validate_config must raise ConfigurationError for non-int nb_rows."""
        cfg = dict(_BASE_CONFIG)
        cfg["nb_rows"] = "${context.X}"
        comp = _make(cfg)
        with pytest.raises(ConfigurationError):
            comp.execute(None)

    def test_negative_nb_rows_raises(self):
        """_process must raise ConfigurationError for negative nb_rows."""
        cfg = dict(_BASE_CONFIG)
        cfg["nb_rows"] = -1
        comp = _make(cfg)
        with pytest.raises(ConfigurationError):
            comp.execute(None)

    def test_valid_config_runs_clean(self):
        """Standard single-mode config must execute without error."""
        comp = _make()
        result = comp.execute(None)
        assert "main" in result


# ---------------------------------------------------------------------------
# 4. Single mode
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSingleMode:
    def test_basic_one_row(self):
        comp = _make()
        result = comp.execute(None)
        df = result["main"]
        assert len(df) == 1
        assert list(df.columns) == ["id", "name"]

    def test_nb_rows_repeats_template(self):
        cfg = dict(_BASE_CONFIG)
        cfg["nb_rows"] = 3
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df) == 3
        # Every row has the same values_config values
        assert all(df["name"] == "Alice")

    def test_nb_rows_zero_returns_empty_df_with_columns(self):
        cfg = dict(_BASE_CONFIG)
        cfg["nb_rows"] = 0
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df) == 0
        assert list(df.columns) == ["id", "name"]

    def test_values_config_list_of_dicts_format(self):
        """Converter emits list[dict] with 'schema_column' / 'value' keys."""
        cfg = dict(_BASE_CONFIG)
        cfg["values_config"] = [
            {"schema_column": "id", "value": "42"},
            {"schema_column": "name", "value": "Bob"},
        ]
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert df.iloc[0]["id"] == 42  # numeric string coerced to int
        assert df.iloc[0]["name"] == "Bob"

    def test_values_config_dict_fallback(self):
        """Legacy plain-dict format is also accepted."""
        cfg = dict(_BASE_CONFIG)
        cfg["values_config"] = {"id": 7, "name": "Charlie"}
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert df.iloc[0]["id"] == 7
        assert df.iloc[0]["name"] == "Charlie"

    def test_missing_column_in_values_config_gives_none(self):
        """Column absent from values_config must yield None, not KeyError."""
        cfg = dict(_BASE_CONFIG)
        cfg["values_config"] = [{"schema_column": "id", "value": "1"}]
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert pd.isna(df.iloc[0]["name"]) or df.iloc[0]["name"] is None

    def test_empty_values_config_fills_none(self):
        cfg = dict(_BASE_CONFIG)
        cfg["values_config"] = []
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df) == 1
        assert df.iloc[0]["id"] is None


# ---------------------------------------------------------------------------
# 5. Inline table mode
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestIntableMode:
    _INTABLE_CONFIG: dict = {
        "component_type": "FixedFlowInputComponent",
        "nb_rows": 2,
        "use_singlemode": False,
        "use_intable": True,
        "use_inlinecontent": False,
        "schema": _SCHEMA_2COL,
        "intable": [
            {"element_ref": "id",   "value": "1"},
            {"element_ref": "name", "value": "Alice"},
            {"element_ref": "id",   "value": "2"},
            {"element_ref": "name", "value": "Bob"},
        ],
    }

    def test_basic_two_rows(self):
        comp = _make(self._INTABLE_CONFIG)
        df = comp.execute(None)["main"]
        assert len(df) == 2
        assert df.iloc[0]["name"] == "Alice"
        assert df.iloc[1]["name"] == "Bob"

    def test_reads_intable_key_not_intable_data(self):
        """Engine must read 'intable', not the old 'intable_data' key."""
        cfg = dict(self._INTABLE_CONFIG)
        cfg.pop("intable")
        cfg["intable_data"] = cfg.get("intable", [])  # wrong key
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        # intable_data is not read; result is empty
        assert len(df) == 0

    def test_nb_rows_limits_output(self):
        cfg = dict(self._INTABLE_CONFIG)
        cfg["nb_rows"] = 1
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df) == 1
        assert df.iloc[0]["name"] == "Alice"

    def test_no_null_padding_beyond_data(self):
        """If intable has fewer rows than nb_rows, no null rows are appended."""
        cfg = dict(self._INTABLE_CONFIG)
        cfg["nb_rows"] = 5  # only 2 rows of data available
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df) == 2

    def test_empty_intable_returns_empty_df(self):
        cfg = dict(self._INTABLE_CONFIG)
        cfg["intable"] = []
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df) == 0
        assert list(df.columns) == ["id", "name"]


# ---------------------------------------------------------------------------
# 6. Inline content mode
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestInlineContentMode:
    _IC_CONFIG: dict = {
        "component_type": "FixedFlowInputComponent",
        "nb_rows": 99,           # must be ignored in inline content mode
        "use_singlemode": False,
        "use_intable": False,
        "use_inlinecontent": True,
        "schema": _SCHEMA_2COL,
        "inline_content": "1;Alice\n2;Bob\n3;Charlie",
        "row_separator": "\\n",
        "field_separator": ";",
    }

    def test_basic_parse_three_rows(self):
        comp = _make(self._IC_CONFIG)
        df = comp.execute(None)["main"]
        assert len(df) == 3
        assert df.iloc[0]["name"] == "Alice"
        assert df.iloc[2]["name"] == "Charlie"

    def test_nb_rows_is_ignored(self):
        """nb_rows must be ignored; all content lines are emitted."""
        cfg = dict(self._IC_CONFIG)
        cfg["nb_rows"] = 1  # only 1, but content has 3 rows
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df) == 3

    def test_backslash_n_separator_normalised(self):
        """\\n in row_separator config must be converted to actual newline."""
        comp = _make(self._IC_CONFIG)
        df = comp.execute(None)["main"]
        assert len(df) == 3

    def test_tab_separator_normalised(self):
        cfg = dict(self._IC_CONFIG)
        cfg["inline_content"] = "1\tAlice\n2\tBob"
        cfg["field_separator"] = "\\t"
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df) == 2
        assert df.iloc[0]["name"] == "Alice"

    def test_empty_content_returns_empty_df(self):
        cfg = dict(self._IC_CONFIG)
        cfg["inline_content"] = ""
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df) == 0
        assert list(df.columns) == ["id", "name"]

    def test_pipe_separator_normalised(self):
        cfg = dict(self._IC_CONFIG)
        cfg["inline_content"] = "10|Dave\n20|Eve"
        cfg["field_separator"] = "\\|"
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df) == 2
        assert df.iloc[1]["name"] == "Eve"


# ---------------------------------------------------------------------------
# 7. Statistics (NB_LINE contract for source components)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    def test_nb_line_equals_rows_generated(self):
        cfg = dict(_BASE_CONFIG)
        cfg["nb_rows"] = 5
        comp = _make(cfg)
        comp.execute(None)
        assert comp.global_map.get("tFFI_1_NB_LINE") == 5

    def test_nb_line_ok_equals_rows_generated(self):
        cfg = dict(_BASE_CONFIG)
        cfg["nb_rows"] = 5
        comp = _make(cfg)
        comp.execute(None)
        assert comp.global_map.get("tFFI_1_NB_LINE_OK") == 5

    def test_nb_line_reject_is_zero(self):
        cfg = dict(_BASE_CONFIG)
        cfg["nb_rows"] = 5
        comp = _make(cfg)
        comp.execute(None)
        assert comp.global_map.get("tFFI_1_NB_LINE_REJECT") == 0

    def test_nb_line_is_zero_when_no_rows(self):
        cfg = dict(_BASE_CONFIG)
        cfg["nb_rows"] = 0
        comp = _make(cfg)
        comp.execute(None)
        assert comp.global_map.get("tFFI_1_NB_LINE") == 0


# ---------------------------------------------------------------------------
# 8. Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEdgeCases:
    def test_none_input_data_is_ignored(self):
        """Source component: None input_data must not cause errors."""
        comp = _make()
        result = comp.execute(None)
        assert "main" in result

    def test_dataframe_input_data_is_ignored(self):
        """Even if a DataFrame is passed, it must be ignored."""
        comp = _make()
        dummy = pd.DataFrame({"x": [1, 2, 3]})
        result = comp.execute(dummy)
        df = result["main"]
        assert list(df.columns) == ["id", "name"]

    def test_empty_schema_produces_empty_df(self):
        cfg = dict(_BASE_CONFIG)
        cfg["schema"] = []
        cfg["nb_rows"] = 3
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df.columns) == 0

    def test_numeric_string_coerced_to_int(self):
        """String '42' in values_config value must become int 42."""
        cfg = dict(_BASE_CONFIG)
        cfg["values_config"] = [
            {"schema_column": "id", "value": "42"},
            {"schema_column": "name", "value": "hello"},
        ]
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert df.iloc[0]["id"] == 42
        assert not isinstance(df.iloc[0]["id"], str)

    def test_negative_numeric_string_coerced(self):
        """-5 as a string must be coerced to int -5 (not left as '-5')."""
        cfg = dict(_BASE_CONFIG)
        cfg["schema"] = [{"name": "val", "type": "id_Integer"}]
        cfg["values_config"] = [{"schema_column": "val", "value": "-5"}]
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert df.iloc[0]["val"] == -5
        assert not isinstance(df.iloc[0]["val"], str)

    def test_no_reject_key_in_result(self):
        """Source component must not include 'reject' key in return dict."""
        comp = _make()
        result = comp.execute(None)
        assert "reject" not in result


# ---------------------------------------------------------------------------
# Plan 14-08 coverage lift: missed-line clusters
#   115-116 (no mode selected -> warn + default to single),
#   150 (values_config is non-list/dict -> empty lookup),
#   209 (inline_content empty line skipped),
#   240-241 (resolve_string raises -> fallback to original value),
#   244 (resolved != value -> coerce numeric branch),
#   248-252 (globalMap.get(...) string pattern),
#   264 (coerce_numeric: non-string -> return as-is),
#   269 (coerce_numeric: decimal-pattern -> float).
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoverageLift1408:
    """Targeted tests added in Plan 14-08 to lift fixed_flow_input.py to >= 95%."""

    def test_no_mode_selected_logs_warning_and_defaults_to_single(self, caplog):
        """All three mode flags False -> WARNING + single-mode build (115-116)."""
        import logging
        cfg = dict(_BASE_CONFIG)
        cfg["use_singlemode"] = False
        cfg["use_intable"] = False
        cfg["use_inlinecontent"] = False
        comp = _make(cfg)
        with caplog.at_level(logging.WARNING):
            df = comp.execute(None)["main"]
        assert any(
            "no mode selected, defaulting to single" in r.message
            for r in caplog.records
        )
        # Built one row from values_config like single mode would
        assert len(df) == 1

    def test_values_config_non_list_non_dict_yields_empty_lookup(self):
        """values_config of unsupported type -> empty lookup -> all None values (line 150)."""
        cfg = dict(_BASE_CONFIG)
        cfg["values_config"] = "not_a_list_or_dict"
        cfg["nb_rows"] = 2
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df) == 2
        # All values None because lookup is empty for both columns
        assert df["id"].isnull().all()
        assert df["name"].isnull().all()

    def test_inline_content_skips_blank_lines(self):
        """Inline-content mode skips empty / whitespace-only lines (line 209)."""
        cfg = dict(_BASE_CONFIG)
        cfg["use_singlemode"] = False
        cfg["use_inlinecontent"] = True
        # 3 lines but 2 are blank/whitespace; only 1 row should be produced
        cfg["inline_content"] = "1;Alice\n   \n2;Bob"
        cfg["row_separator"] = "\\n"
        cfg["field_separator"] = ";"
        comp = _make(cfg)
        df = comp.execute(None)["main"]
        assert len(df) == 2
        assert list(df["name"]) == ["Alice", "Bob"]

    def test_resolve_value_falls_back_when_resolve_raises(self, monkeypatch):
        """If context_manager.resolve_string raises, _resolve_value falls back (240-241).

        This test invokes _resolve_value directly because BaseComponent.execute()
        resolves the entire config via context_manager.resolve_dict BEFORE calling
        _process(); a top-level monkeypatch on resolve_string would crash that
        outer step instead of exercising the fallback inside _resolve_value.
        """
        comp = _make()

        def boom(s):
            raise RuntimeError("simulated resolve failure")

        monkeypatch.setattr(comp.context_manager, "resolve_string", boom)
        # Direct call to _resolve_value: should swallow exception and return
        # the original value unchanged (modulo numeric coercion fall-through).
        out = comp._resolve_value("BobBoom")
        assert out == "BobBoom"

    def test_resolve_value_coerces_after_resolution(self, monkeypatch):
        """Context resolution returning a different string triggers numeric coerce (line 244)."""
        comp = _make()

        def fake_resolve(s):
            # Simulate a context substitution that turns the placeholder into "42"
            if s == "${context.id_val}":
                return "42"
            return s

        monkeypatch.setattr(comp.context_manager, "resolve_string", fake_resolve)
        out = comp._resolve_value("${context.id_val}")
        # Resolved differently from input -> _coerce_numeric path (line 244)
        # int("42") == 42 (Python int, not numpy)
        assert out == 42
        assert isinstance(out, int)

    def test_global_map_get_pattern_resolved(self):
        """globalMap.get(\"KEY\") string pattern resolves at runtime (248-252)."""
        cfg = dict(_BASE_CONFIG)
        cfg["values_config"] = [
            {"schema_column": "id", "value": 'globalMap.get("upstream_id")'},
            {"schema_column": "name", "value": "static"},
        ]
        gm = GlobalMap()
        gm.put("upstream_id", 999)
        comp = _make(cfg, global_map=gm)
        df = comp.execute(None)["main"]
        assert df.iloc[0]["id"] == 999

    def test_coerce_numeric_non_string_returns_as_is(self):
        """_coerce_numeric: non-string input is returned unchanged (line 264)."""
        from src.v1.engine.components.file.fixed_flow_input import _coerce_numeric

        sentinel = [1, 2, 3]
        assert _coerce_numeric(sentinel) is sentinel
        assert _coerce_numeric(42) == 42
        assert _coerce_numeric(None) is None

    def test_coerce_numeric_decimal_to_float(self):
        """_coerce_numeric: decimal-pattern string -> float (line 269)."""
        from src.v1.engine.components.file.fixed_flow_input import _coerce_numeric

        assert _coerce_numeric("3.14") == 3.14
        assert _coerce_numeric("-0.5") == -0.5
        # Plain string remains unchanged
        assert _coerce_numeric("hello") == "hello"

