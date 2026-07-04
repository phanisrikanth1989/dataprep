"""Tests for ExtractDelimitedFields engine component (tExtractDelimitedFields).

Test classes:
    TestRegistry        -- @REGISTRY.register, BaseComponent inheritance
    TestValidateConfig  -- _validate_config() structural checks (Rule 12)
    TestProcessEmpty    -- None / empty DataFrame input
    TestProcessMain     -- happy-path splitting scenarios
    TestProcessReject   -- reject flow
    TestStats           -- NB_LINE / NB_LINE_OK / NB_LINE_REJECT tracking
"""
import pytest
import pandas as pd

from src.v1.engine.components.transform.extract_delimited_fields import ExtractDelimitedFields
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
    comp = ExtractDelimitedFields(
        component_id="tEDF_1",
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
        assert REGISTRY.get("ExtractDelimitedFields") is ExtractDelimitedFields

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tExtractDelimitedFields") is ExtractDelimitedFields

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(ExtractDelimitedFields, BaseComponent)


# ------------------------------------------------------------------
# TestValidateConfig
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_missing_field_raises(self):
        comp = _make_component(config={})
        with pytest.raises(ConfigurationError, match="field"):
            comp._validate_config()

    def test_die_on_error_not_bool_raises(self):
        comp = _make_component(config={"field": "src", "die_on_error": "yes"})
        with pytest.raises(ConfigurationError, match="die_on_error"):
            comp._validate_config()

    def test_trim_not_bool_raises(self):
        comp = _make_component(config={"field": "src", "trim": 0})
        with pytest.raises(ConfigurationError, match="trim"):
            comp._validate_config()

    def test_valid_config_passes(self):
        comp = _make_component(config={"field": "src"})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestProcessEmpty
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessEmpty:
    def test_none_input_returns_empty(self):
        comp = _make_component(config={"field": "src"})
        result = comp.execute(None)
        assert result["main"].empty

    def test_empty_df_returns_empty(self):
        comp = _make_component(config={"field": "src"})
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty


# ------------------------------------------------------------------
# TestProcessMain
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessMain:
    def test_basic_semicolon_split(self):
        comp = _make_component(config={"field": "src", "fieldseparator": ";"})
        _set_schema(comp, ["src", "col1", "col2"])
        df = pd.DataFrame([{"src": "alpha;beta"}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        row = result["main"].iloc[0]
        assert row["col1"] == "alpha"
        assert row["col2"] == "beta"

    def test_passthrough_column_preserved(self):
        comp = _make_component(config={"field": "src", "fieldseparator": ";"})
        _set_schema(comp, ["src", "id", "col1"])
        df = pd.DataFrame([{"src": "alpha", "id": 7}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["id"] == 7

    def test_trim_strips_tokens(self):
        comp = _make_component(config={"field": "src", "fieldseparator": ";", "trim": True})
        _set_schema(comp, ["src", "col1"])
        df = pd.DataFrame([{"src": "  alpha  "}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["col1"] == "alpha"

    def test_multiple_rows(self):
        comp = _make_component(config={"field": "src", "fieldseparator": ","})
        _set_schema(comp, ["src", "a", "b"])
        df = pd.DataFrame([{"src": "1,2"}, {"src": "3,4"}])
        result = comp.execute(df)
        assert len(result["main"]) == 2

    def test_default_separator_is_semicolon(self):
        comp = _make_component(config={"field": "src"})
        _set_schema(comp, ["src", "col1", "col2"])
        df = pd.DataFrame([{"src": "x;y"}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["col1"] == "x"


# ------------------------------------------------------------------
# TestProcessReject
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessReject:
    def test_null_source_goes_to_reject(self):
        comp = _make_component(config={
            "field": "src",
            "fieldseparator": ";",
            "ignore_source_null": False,
            "die_on_error": False,
        })
        _set_schema(comp, ["src", "col1"])
        df = pd.DataFrame([{"src": None}])
        result = comp.execute(df)
        assert result["main"].empty
        assert len(result["reject"]) == 1

    def test_null_source_silently_skipped(self):
        comp = _make_component(config={
            "field": "src",
            "fieldseparator": ";",
            "ignore_source_null": True,
        })
        _set_schema(comp, ["src", "col1"])
        df = pd.DataFrame([{"src": None}, {"src": "a"}])
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_check_fields_num_rejects_mismatch(self):
        comp = _make_component(config={
            "field": "src",
            "fieldseparator": ";",
            "check_fields_num": True,
            "die_on_error": False,
        })
        _set_schema(comp, ["src", "col1", "col2"])
        # Only 1 token when 2 extracted cols expected
        df = pd.DataFrame([{"src": "onlyone"}])
        result = comp.execute(df)
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "FIELD_COUNT_MISMATCH"


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    def test_stats_ok_rows(self):
        gm = GlobalMap()
        comp = _make_component(config={"field": "src", "fieldseparator": ";"}, global_map=gm)
        _set_schema(comp, ["src", "col1"])
        df = pd.DataFrame([{"src": "a"}, {"src": "b"}])
        comp.execute(df)
        assert gm.get_nb_line(comp.id) == 2

    def test_stats_zero_on_empty(self):
        gm = GlobalMap()
        comp = _make_component(config={"field": "src"}, global_map=gm)
        comp.execute(None)
        assert gm.get_nb_line(comp.id) == 0


# ------------------------------------------------------------------
# TestCoverageLift_14_05 (COV-EDF-001)
#
# Target missed lines from Phase 14 baseline:
#   - 107      (field empty after resolution -> DataValidationError)
#   - 111      (field column not in input -> DataValidationError)
#   - 130-131  (no output_schema -> all_out_cols = input.columns, no extraction)
#   - 167      (check_fields_num + die_on_error -> raise inside loop)
#   - 180-189  (advanced_separator: numeric token normalization)
#
# Former lines 145-148 (pd.isna try/except) and 200-202 (main_df backfill)
# were removed under D-C5 dead-code policy in this same plan -- both
# branches were unreachable for realistic input shapes.
# ------------------------------------------------------------------


from src.v1.engine.exceptions import DataValidationError


@pytest.mark.unit
class TestCoverageLift1405:
    """Targeted coverage for residual missed branches in extract_delimited_fields.py."""

    def test_field_empty_raises(self):
        # Hits line 107.
        comp = _make_component(config={"field": ""})
        df = pd.DataFrame([{"src": "a;b"}])
        with pytest.raises((DataValidationError, ComponentExecutionError)) as excinfo:
            comp.execute(df)
        assert "field" in str(excinfo.value)

    def test_field_not_in_columns_raises(self):
        # Hits line 111.
        comp = _make_component(config={"field": "missing"})
        df = pd.DataFrame([{"src": "a;b"}])
        with pytest.raises((DataValidationError, ComponentExecutionError)) as excinfo:
            comp.execute(df)
        assert "missing" in str(excinfo.value)

    def test_no_output_schema_passthrough(self):
        # Hits lines 130-131.
        comp = _make_component(config={"field": "src", "fieldseparator": ";"})
        # Do NOT set output_schema -- triggers all_out_cols = input.columns
        # and extracted_info = []; the loop produces a passthrough row.
        df = pd.DataFrame([{"src": "a;b"}])
        result = comp.execute(df)
        assert list(result["main"].columns) == ["src"]

    def test_check_fields_num_with_die_on_error_raises(self):
        # Hits line 167.
        comp = _make_component(config={
            "field": "src",
            "fieldseparator": ";",
            "die_on_error": True,
            "check_fields_num": True,
        })
        _set_schema(comp, ["src", "col1", "col2"])  # expects 2 extracted tokens
        df = pd.DataFrame([{"src": "onlyone"}])  # 1 token, expected 2
        with pytest.raises((DataValidationError, ComponentExecutionError)) as excinfo:
            comp.execute(df)
        assert "Expected" in str(excinfo.value)

    def test_advanced_separator_normalizes_numeric_tokens(self):
        # Hits lines 180-189: numeric type tokens have thousands_sep stripped
        # and decimal_sep converted to '.'.
        comp = _make_component(config={
            "field": "src",
            "fieldseparator": "|",
            "advanced_separator": True,
            "thousands_separator": ".",  # European-style thousands
            "decimal_separator": ",",    # European-style decimal
            "die_on_error": False,
        })
        comp.output_schema = [
            {"name": "src", "type": "id_String"},
            {"name": "col1", "type": "id_Float"},   # numeric -- normalized
            {"name": "col2", "type": "id_String"},  # non-numeric -- left alone
        ]
        df = pd.DataFrame([{"src": "1.234,56|hello,world"}])
        result = comp.execute(df)
        # col1 numeric: "1.234,56" -> strip "." -> "1234,56" -> swap "," to "." -> "1234.56".
        assert result["main"].iloc[0]["col1"] == "1234.56"
        # col2 non-numeric: left untouched.
        assert result["main"].iloc[0]["col2"] == "hello,world"
