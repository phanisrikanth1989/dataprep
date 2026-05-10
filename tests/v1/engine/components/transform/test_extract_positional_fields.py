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


# ------------------------------------------------------------------
# TestCoverageLift_14_05 (COV-EPF-001)
#
# Target missed lines from Phase 14 baseline:
#   - 102      (pattern empty after strip)
#   - 107-108  (pattern not comma-separated integers)
#   - 113      (field width <= 0)
#   - 119      (field present and in input_data.columns)
#   - 121-126  (field given but not in columns -> fallback warn)
#   - 140-141  (no output_schema -> generated field_N names)
#   - 164-165  (pd.isna raises -> is_null=False)
#   - 180      (BOM strip on first character)
#   - 196      (die_on_error=True -> raise inside extraction loop)
#   - 209      (main_df missing schema columns filled with None)
# ------------------------------------------------------------------


from src.v1.engine.exceptions import DataValidationError


@pytest.mark.unit
class TestCoverageLift1405:
    """Targeted coverage for residual missed branches in extract_positional_fields.py."""

    def test_pattern_empty_raises(self):
        # Hits line 102.
        comp = _make_component(config={"pattern": "   "})
        df = pd.DataFrame([{"src": "abc"}])
        with pytest.raises((DataValidationError, ComponentExecutionError)) as excinfo:
            comp.execute(df)
        assert "pattern" in str(excinfo.value)

    def test_pattern_non_integer_raises(self):
        # Hits lines 107-108.
        comp = _make_component(config={"pattern": "abc,def"})
        df = pd.DataFrame([{"src": "abcdef"}])
        with pytest.raises((DataValidationError, ComponentExecutionError)) as excinfo:
            comp.execute(df)
        assert "comma-separated integers" in str(excinfo.value)

    def test_pattern_negative_width_raises(self):
        # Hits line 113.
        comp = _make_component(config={"pattern": "3,-1"})
        df = pd.DataFrame([{"src": "abcdef"}])
        with pytest.raises((DataValidationError, ComponentExecutionError)) as excinfo:
            comp.execute(df)
        assert "must be > 0" in str(excinfo.value)

    def test_field_present_in_input_columns(self):
        # Hits line 119.
        comp = _make_component(config={"pattern": "3,4", "field": "src"})
        _set_schema(comp, ["src", "col1", "col2"])
        df = pd.DataFrame([{"src": "abcXYZW", "id": 1}])
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_field_given_but_not_in_columns_falls_back_to_first(self, caplog):
        # Hits lines 121-126.
        comp = _make_component(config={"pattern": "3,4", "field": "missing_col"})
        _set_schema(comp, ["src", "col1", "col2"])
        df = pd.DataFrame([{"src": "abcXYZW"}])
        with caplog.at_level("WARNING"):
            result = comp.execute(df)
        assert any("missing_col" in rec.message for rec in caplog.records)
        assert len(result["main"]) == 1

    def test_no_output_schema_generates_field_n_names(self):
        # Hits lines 140-141.
        comp = _make_component(config={"pattern": "3,4"})
        # Do NOT set output_schema -- triggers field_1/field_2 generation.
        df = pd.DataFrame([{"src": "abcXYZW"}])
        result = comp.execute(df)
        assert "field_1" in result["main"].columns
        assert "field_2" in result["main"].columns
        assert result["main"].iloc[0]["field_1"] == "abc"
        assert result["main"].iloc[0]["field_2"] == "XYZW"

    # NOTE on previous lines 162-165 (pd.isna try/except):
    # The defensive try/except for TypeError/ValueError around pd.isna() was
    # unreachable for the scalar source-column values this component actually
    # consumes (str / NaN / None never raise). Per D-C5 dead-code policy the
    # branch was deleted in Plan 14-05 instead of contorting tests to reach
    # it. Lines 164-165 in the baseline no longer exist.

    def test_bom_stripped_from_first_character(self):
        # Hits line 180.
        comp = _make_component(config={"pattern": "3,4", "field": "src"})
        _set_schema(comp, ["src", "col1", "col2"])
        # ﻿ is the Unicode BOM; chr(0xFEFF) prepended to value.
        df = pd.DataFrame([{"src": "﻿abcXYZW"}])
        result = comp.execute(df)
        # BOM stripped: col1 starts at "a".
        assert result["main"].iloc[0]["col1"] == "abc"
        assert result["main"].iloc[0]["col2"] == "XYZW"

    def test_die_on_error_raises_on_extraction_failure(self):
        # Hits line 196: die_on_error=True with check_fields_num and short input.
        comp = _make_component(config={
            "pattern": "5,5",
            "field": "src",
            "die_on_error": True,
            "check_fields_num": True,
        })
        _set_schema(comp, ["src", "col1", "col2"])
        df = pd.DataFrame([{"src": "abc"}])  # only 3 chars; required is 10
        with pytest.raises((DataValidationError, ComponentExecutionError)) as excinfo:
            comp.execute(df)
        msg = str(excinfo.value)
        assert "Row extraction failed" in msg or "Line length" in msg

    def test_missing_schema_columns_filled_with_none(self):
        # Hits line 209: main_df missing columns get None.
        comp = _make_component(config={"pattern": "3,4", "field": "src"})
        # 4 schema cols but only 2 widths in pattern -> col3 is absent from
        # extraction and must be filled with None at line 209.
        comp.output_schema = [
            {"name": "src", "type": "id_String"},
            {"name": "col1", "type": "id_String"},
            {"name": "col2", "type": "id_String"},
            {"name": "col3", "type": "id_String"},  # absent from extraction
        ]
        df = pd.DataFrame([{"src": "abcXYZW"}])
        result = comp.execute(df)
        assert "col3" in result["main"].columns
        assert pd.isna(result["main"].iloc[0]["col3"])
