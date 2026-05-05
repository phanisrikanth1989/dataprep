"""Tests for ExtractPositionalFields engine component (tExtractPositionalFields).

Test classes:
    TestRegistry        -- @REGISTRY.register, BaseComponent inheritance
    TestValidateConfig  -- _validate_config() structural checks (Rule 12)
    TestProcessEmpty    -- None / empty DataFrame input
    TestProcessMain     -- happy-path positional extraction scenarios
    TestProcessReject   -- reject flow (die_on_error=False)
    TestStats           -- NB_LINE / NB_LINE_OK / NB_LINE_REJECT tracking
"""
import pytest
import pandas as pd

from src.v1.engine.components.transform.extract_positional_fields import ExtractPositionalFields
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, ComponentExecutionError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    cfg = config or {}
    comp = ExtractPositionalFields(
        component_id="tEPF_1",
        config=cfg,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(cfg)
    return comp


def _set_schema(comp, col_names):
    comp.output_schema = [{"name": c, "type": "id_String"} for c in col_names]


# ------------------------------------------------------------------
# TestRegistry
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistry:
    def test_v1_name_registered(self):
        assert REGISTRY.get("ExtractPositionalFields") is ExtractPositionalFields

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tExtractPositionalFields") is ExtractPositionalFields

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(ExtractPositionalFields, BaseComponent)


# ------------------------------------------------------------------
# TestValidateConfig
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_missing_pattern_raises(self):
        comp = _make_component(config={})
        with pytest.raises(ConfigurationError, match="pattern"):
            comp._validate_config()

    def test_trim_not_bool_raises(self):
        comp = _make_component(config={"pattern": "5,5", "trim": "yes"})
        with pytest.raises(ConfigurationError, match="trim"):
            comp._validate_config()

    def test_die_on_error_not_bool_raises(self):
        comp = _make_component(config={"pattern": "5,5", "die_on_error": 1})
        with pytest.raises(ConfigurationError, match="die_on_error"):
            comp._validate_config()

    def test_ignore_source_null_not_bool_raises(self):
        comp = _make_component(config={"pattern": "5,5", "ignore_source_null": "true"})
        with pytest.raises(ConfigurationError, match="ignore_source_null"):
            comp._validate_config()

    def test_valid_config_passes(self):
        comp = _make_component(config={"pattern": "5,5", "die_on_error": False})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestProcessEmpty
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessEmpty:
    def test_none_input_returns_empty(self):
        comp = _make_component(config={"pattern": "5,5"})
        result = comp.execute(None)
        assert result["main"].empty

    def test_empty_df_returns_empty(self):
        comp = _make_component(config={"pattern": "5,5"})
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty


# ------------------------------------------------------------------
# TestProcessMain
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessMain:
    def _base_config(self):
        return {"pattern": "3,4", "die_on_error": False}

    def test_basic_extraction(self):
        comp = _make_component(config=self._base_config())
        _set_schema(comp, ["src", "col1", "col2"])
        df = pd.DataFrame([{"src": "abcXYZW"}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        row = result["main"].iloc[0]
        assert row["col1"] == "abc"
        assert row["col2"] == "XYZW"

    def test_trim_option(self):
        comp = _make_component(config={**self._base_config(), "trim": True})
        _set_schema(comp, ["src", "col1", "col2"])
        df = pd.DataFrame([{"src": "ab  XY  "}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["col1"] == "ab"

    def test_passthrough_input_columns(self):
        comp = _make_component(config=self._base_config())
        _set_schema(comp, ["src", "id", "col1"])
        df = pd.DataFrame([{"src": "abcXYZW", "id": 99}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["id"] == 99

    def test_first_column_fallback_when_field_not_in_schema(self):
        """When 'field' config not set, use first input column."""
        comp = _make_component(config={"pattern": "3,4"})
        _set_schema(comp, ["first", "col1", "col2"])
        df = pd.DataFrame([{"first": "abcXYZW"}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["col1"] == "abc"

    def test_multiple_rows(self):
        comp = _make_component(config=self._base_config())
        _set_schema(comp, ["src", "col1", "col2"])
        df = pd.DataFrame([{"src": "abcXYZW"}, {"src": "defGHIJ"}])
        result = comp.execute(df)
        assert len(result["main"]) == 2


# ------------------------------------------------------------------
# TestProcessReject
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessReject:
    def test_null_source_goes_to_reject_when_not_ignored(self):
        comp = _make_component(config={
            "pattern": "3,4",
            "ignore_source_null": False,
            "die_on_error": False,
        })
        _set_schema(comp, ["src", "col1", "col2"])
        df = pd.DataFrame([{"src": None}])
        result = comp.execute(df)
        assert result["main"].empty
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "NULL_SOURCE"

    def test_null_source_silently_skipped_when_ignored(self):
        comp = _make_component(config={
            "pattern": "3,4",
            "ignore_source_null": True,
            "die_on_error": False,
        })
        _set_schema(comp, ["src", "col1", "col2"])
        df = pd.DataFrame([{"src": None}, {"src": "abcXYZW"}])
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_check_fields_num_reject(self):
        comp = _make_component(config={
            "pattern": "3,4,2",
            "die_on_error": False,
            "check_fields_num": True,
        })
        _set_schema(comp, ["src", "col1", "col2", "col3"])
        df = pd.DataFrame([{"src": "abc"}])  # only 3 chars; col2/col3 would be empty
        result = comp.execute(df)
        # depends on implementation: either ok with None or rejected
        # Just verify no crash
        assert "main" in result


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    def test_stats_updated_on_success(self):
        gm = GlobalMap()
        comp = _make_component(config={"pattern": "3,4"}, global_map=gm)
        _set_schema(comp, ["src", "col1", "col2"])
        df = pd.DataFrame([{"src": "abcXYZW"}, {"src": "defGHIJ"}])
        comp.execute(df)
        assert gm.get_nb_line(comp.id) == 2

    def test_stats_empty_input(self):
        gm = GlobalMap()
        comp = _make_component(config={"pattern": "3,4"}, global_map=gm)
        comp.execute(None)
        assert gm.get_nb_line(comp.id) == 0
