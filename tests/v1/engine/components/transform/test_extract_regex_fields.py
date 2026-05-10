"""Tests for ExtractRegexFields engine component (tExtractRegexFields).

Test classes:
    TestRegistry        -- @REGISTRY.register, BaseComponent inheritance
    TestValidateConfig  -- _validate_config() structural checks (Rule 12)
    TestProcessEmpty    -- None / empty DataFrame input
    TestProcessMain     -- happy-path regex extraction scenarios
    TestProcessReject   -- reject flow (NULL_SOURCE, NO_MATCH, FIELD_COUNT_MISMATCH)
    TestStats           -- NB_LINE / NB_LINE_OK / NB_LINE_REJECT tracking
"""
import pytest
import pandas as pd

from src.v1.engine.components.transform.extract_regex_fields import ExtractRegexFields
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
    comp = ExtractRegexFields(
        component_id="tERF_1",
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
        assert REGISTRY.get("ExtractRegexFields") is ExtractRegexFields

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tExtractRegexFields") is ExtractRegexFields

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(ExtractRegexFields, BaseComponent)


# ------------------------------------------------------------------
# TestValidateConfig
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_missing_field_raises(self):
        comp = _make_component(config={"regex": r"(\w+)"})
        with pytest.raises(ConfigurationError, match="field"):
            comp._validate_config()

    def test_missing_regex_raises(self):
        comp = _make_component(config={"field": "src"})
        with pytest.raises(ConfigurationError, match="regex"):
            comp._validate_config()

    def test_die_on_error_not_bool_raises(self):
        comp = _make_component(config={"field": "src", "regex": r"(\w+)", "die_on_error": "yes"})
        with pytest.raises(ConfigurationError, match="die_on_error"):
            comp._validate_config()

    def test_check_fields_num_not_bool_raises(self):
        comp = _make_component(config={"field": "src", "regex": r"(\w+)", "check_fields_num": 1})
        with pytest.raises(ConfigurationError, match="check_fields_num"):
            comp._validate_config()

    def test_valid_config_passes(self):
        comp = _make_component(config={"field": "src", "regex": r"(\w+)"})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestProcessEmpty
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessEmpty:
    def test_none_input_returns_empty(self):
        comp = _make_component(config={"field": "src", "regex": r"(\w+)"})
        result = comp.execute(None)
        assert result["main"].empty

    def test_empty_df_returns_empty(self):
        comp = _make_component(config={"field": "src", "regex": r"(\w+)"})
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty


# ------------------------------------------------------------------
# TestProcessMain
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessMain:
    def test_basic_two_groups(self):
        comp = _make_component(config={
            "field": "src",
            "regex": r"(\w+)\s+(\w+)",
            "die_on_error": False,
        })
        _set_schema(comp, ["src", "word1", "word2"])
        df = pd.DataFrame([{"src": "hello world"}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        row = result["main"].iloc[0]
        assert row["word1"] == "hello"
        assert row["word2"] == "world"

    def test_passthrough_column_preserved(self):
        comp = _make_component(config={
            "field": "src",
            "regex": r"(\d+)",
            "die_on_error": False,
        })
        _set_schema(comp, ["src", "id", "num"])
        df = pd.DataFrame([{"src": "abc123", "id": 42}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["id"] == 42

    def test_multiple_rows(self):
        comp = _make_component(config={
            "field": "src",
            "regex": r"([A-Z]+)(\d+)",
            "die_on_error": False,
        })
        _set_schema(comp, ["src", "letters", "digits"])
        df = pd.DataFrame([{"src": "AB12"}, {"src": "CD34"}])
        result = comp.execute(df)
        assert len(result["main"]) == 2
        assert result["main"].iloc[0]["letters"] == "AB"
        assert result["main"].iloc[1]["digits"] == "34"

    def test_partial_match_captured(self):
        comp = _make_component(config={
            "field": "src",
            "regex": r"age=(\d+)",
            "die_on_error": False,
        })
        _set_schema(comp, ["src", "age"])
        df = pd.DataFrame([{"src": "name=John age=30 city=NY"}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["age"] == "30"


# ------------------------------------------------------------------
# TestProcessReject
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessReject:
    def test_null_source_rejected(self):
        comp = _make_component(config={
            "field": "src",
            "regex": r"(\w+)",
            "die_on_error": False,
        })
        _set_schema(comp, ["src", "col1"])
        df = pd.DataFrame([{"src": None}])
        result = comp.execute(df)
        assert result["main"].empty
        assert result["reject"].iloc[0]["errorCode"] == "NULL_SOURCE"

    def test_no_match_rejected(self):
        comp = _make_component(config={
            "field": "src",
            "regex": r"^(\d+)$",
            "die_on_error": False,
        })
        _set_schema(comp, ["src", "num"])
        df = pd.DataFrame([{"src": "notanumber"}])
        result = comp.execute(df)
        assert result["main"].empty
        assert result["reject"].iloc[0]["errorCode"] == "NO_MATCH"

    def test_field_count_mismatch_rejected(self):
        comp = _make_component(config={
            "field": "src",
            "regex": r"(\w+)",
            "die_on_error": False,
            "check_fields_num": True,
        })
        _set_schema(comp, ["src", "col1", "col2"])  # expects 2 extracted cols
        df = pd.DataFrame([{"src": "hello"}])  # only 1 group captured
        result = comp.execute(df)
        assert result["reject"].iloc[0]["errorCode"] == "FIELD_COUNT_MISMATCH"

    def test_die_on_error_raises_on_no_match(self):
        comp = _make_component(config={
            "field": "src",
            "regex": r"^(\d+)$",
            "die_on_error": True,
        })
        _set_schema(comp, ["src", "num"])
        df = pd.DataFrame([{"src": "notanumber"}])
        with pytest.raises(ComponentExecutionError):
            comp.execute(df)


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    def test_stats_ok_rows(self):
        gm = GlobalMap()
        comp = _make_component(
            config={"field": "src", "regex": r"(\w+)", "die_on_error": False},
            global_map=gm,
        )
        _set_schema(comp, ["src", "col1"])
        df = pd.DataFrame([{"src": "hello"}, {"src": "world"}])
        comp.execute(df)
        assert gm.get_nb_line(comp.id) == 2

    def test_stats_zero_on_empty(self):
        gm = GlobalMap()
        comp = _make_component(config={"field": "src", "regex": r"(\w+)"}, global_map=gm)
        comp.execute(None)
        assert gm.get_nb_line(comp.id) == 0


# ------------------------------------------------------------------
# TestCoverageLift_14_05 (COV-ERF-001)
#
# Target missed lines from Phase 14 baseline:
#   - 91, 95   (field / regex empty after resolution -> DataValidationError)
#   - 104-105  (re.compile error -> DataValidationError)
#   - 113-120  (field missing in columns: die_on_error=True raises;
#               die_on_error=False warns + uses first column)
#   - 132-133  (no output_schema -> all_out_cols = input.columns; no extraction)
#   - 174      (check_fields_num + die_on_error -> raise inside loop)
#   - 195      (main_df missing schema column filled with None)
#
# NOTE: Former lines 144-147 (pd.isna try/except for TypeError/ValueError)
# were removed under D-C5 in this same plan -- pd.isna() never raises on the
# scalar source-column values (str/NaN/None) this component actually receives.
# ------------------------------------------------------------------


from src.v1.engine.exceptions import DataValidationError


@pytest.mark.unit
class TestCoverageLift1405:
    """Targeted coverage for residual missed branches in extract_regex_fields.py."""

    def test_field_empty_raises(self):
        # Hits line 91.
        comp = _make_component(config={"field": "", "regex": r"(\w+)"})
        df = pd.DataFrame([{"src": "abc"}])
        with pytest.raises((DataValidationError, ComponentExecutionError)) as excinfo:
            comp.execute(df)
        assert "field" in str(excinfo.value)

    def test_regex_empty_raises(self):
        # Hits line 95.
        comp = _make_component(config={"field": "src", "regex": ""})
        df = pd.DataFrame([{"src": "abc"}])
        with pytest.raises((DataValidationError, ComponentExecutionError)) as excinfo:
            comp.execute(df)
        assert "regex" in str(excinfo.value)

    def test_invalid_regex_raises_data_validation_error(self):
        # Hits lines 104-105.
        comp = _make_component(config={"field": "src", "regex": "(unbalanced"})
        df = pd.DataFrame([{"src": "abc"}])
        with pytest.raises((DataValidationError, ComponentExecutionError)) as excinfo:
            comp.execute(df)
        assert "valid regular expression" in str(excinfo.value)

    def test_field_missing_with_die_on_error_raises(self):
        # Hits lines 113-116.
        comp = _make_component(config={
            "field": "missing", "regex": r"(\w+)", "die_on_error": True,
        })
        _set_schema(comp, ["missing", "col1"])
        df = pd.DataFrame([{"src": "hello"}])
        with pytest.raises((DataValidationError, ComponentExecutionError)) as excinfo:
            comp.execute(df)
        assert "missing" in str(excinfo.value)

    def test_field_missing_without_die_on_error_falls_back_to_first(self, caplog):
        # Hits lines 117-120.
        comp = _make_component(config={
            "field": "missing", "regex": r"(\w+)", "die_on_error": False,
        })
        _set_schema(comp, ["missing", "col1"])
        df = pd.DataFrame([{"src": "hello"}])
        with caplog.at_level("WARNING"):
            result = comp.execute(df)
        assert any("missing" in rec.message for rec in caplog.records)
        # Match was attempted on the first column ("src").
        assert len(result["main"]) == 1

    def test_no_output_schema_passes_through_without_extraction(self):
        # Hits lines 132-133.
        comp = _make_component(config={
            "field": "src", "regex": r"(\w+)", "die_on_error": False,
        })
        # Do NOT set output_schema -- extracted_col_names becomes [], and
        # all_out_cols becomes the original input columns.
        df = pd.DataFrame([{"src": "hello"}])
        result = comp.execute(df)
        assert list(result["main"].columns) == ["src"]
        assert result["main"].iloc[0]["src"] == "hello"

    def test_check_fields_num_with_die_on_error_raises(self):
        # Hits line 174.
        comp = _make_component(config={
            "field": "src",
            "regex": r"(\w+)",  # 1 group
            "die_on_error": True,
            "check_fields_num": True,
        })
        _set_schema(comp, ["src", "col1", "col2"])  # expects 2 extracted groups
        df = pd.DataFrame([{"src": "hello"}])
        with pytest.raises((DataValidationError, ComponentExecutionError)) as excinfo:
            comp.execute(df)
        assert "Expected" in str(excinfo.value)

    def test_missing_schema_columns_filled_with_none(self):
        # Hits line 195: main_df missing column gets None.
        comp = _make_component(config={
            "field": "src", "regex": r"(\w+)", "die_on_error": False,
        })
        # 3 schema cols but regex captures only 1 group; one of the schema
        # cols is absent from extraction and must be filled with None.
        comp.output_schema = [
            {"name": "src", "type": "id_String"},
            {"name": "col1", "type": "id_String"},
            {"name": "col2", "type": "id_String"},  # absent from groups
        ]
        df = pd.DataFrame([{"src": "hello"}])
        result = comp.execute(df)
        assert "col2" in result["main"].columns
        assert pd.isna(result["main"].iloc[0]["col2"])
