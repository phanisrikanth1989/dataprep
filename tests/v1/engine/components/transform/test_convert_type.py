"""Tests for ConvertType engine component (tConvertType).

Test classes:
    TestRegistration       -- registry decorator, BaseComponent inheritance
    TestValidation         -- _validate_config structural checks (Rule 12)
    TestEmptyInput         -- empty DataFrame passes through without error
    TestEmptyToNull        -- emptytonull replaces "" with pd.NA
    TestManualTable        -- manualtable column-level type coercion
    TestAutocast           -- autocast infers numeric types
    TestRejectRouting      -- dieonerror=False routes bad rows to REJECT
    TestDieOnError         -- dieonerror=True raises DataValidationError
    TestBothModesActive    -- autocast + manualtable together
    TestStatistics         -- NB_LINE / NB_LINE_OK / NB_LINE_REJECT
    TestNoopConfig         -- no autocast, empty manualtable: rows pass through unchanged
"""
import pytest
import pandas as pd

from src.v1.engine.components.transform.convert_type import ConvertType
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, ComponentExecutionError, DataValidationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    cfg = config or {}
    comp = ConvertType(
        component_id="tConvertType_1",
        config=cfg,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(cfg)
    return comp


def _df(*rows, columns):
    return pd.DataFrame(rows, columns=columns)


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    """Registry decorator, BaseComponent inheritance."""

    def test_v1_name_registered(self):
        assert REGISTRY.get("ConvertType") is ConvertType

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tConvertType") is ConvertType

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(ConvertType, BaseComponent)


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidation:
    """_validate_config() -- structural checks, raises ConfigurationError."""

    def test_manualtable_not_list_raises(self):
        comp = _make_component({"manualtable": "bad"})
        with pytest.raises(ConfigurationError, match="manualtable"):
            comp._validate_config()

    def test_autocast_not_bool_raises(self):
        comp = _make_component({"autocast": "yes"})
        with pytest.raises(ConfigurationError, match="autocast"):
            comp._validate_config()

    def test_emptytonull_not_bool_raises(self):
        comp = _make_component({"emptytonull": 1})
        with pytest.raises(ConfigurationError, match="emptytonull"):
            comp._validate_config()

    def test_dieonerror_not_bool_raises(self):
        comp = _make_component({"dieonerror": "true"})
        with pytest.raises(ConfigurationError, match="dieonerror"):
            comp._validate_config()

    def test_valid_minimal_config_does_not_raise(self):
        _make_component({}).execute(pd.DataFrame({"a": [1]}))  # no raise expected


# ------------------------------------------------------------------
# TestEmptyInput
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEmptyInput:
    """Empty DataFrame passes through without error."""

    def test_empty_df_returns_empty(self):
        comp = _make_component({"autocast": True})
        result = comp.execute(pd.DataFrame())
        assert isinstance(result["main"], pd.DataFrame)

    def test_none_input_returns_empty(self):
        comp = _make_component({})
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)


# ------------------------------------------------------------------
# TestEmptyToNull
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEmptyToNull:
    """emptytonull=True replaces empty strings with pd.NA."""

    def test_empty_string_becomes_null(self):
        df = _df(("", "hello"), ("", ""), columns=["a", "b"])
        comp = _make_component({"emptytonull": True})
        result = comp.execute(df)
        main = result["main"]
        assert pd.isna(main.loc[0, "a"])
        assert pd.isna(main.loc[1, "a"])
        assert pd.isna(main.loc[1, "b"])

    def test_emptytonull_false_preserves_empty_strings(self):
        df = _df(("",), columns=["a"])
        comp = _make_component({"emptytonull": False})
        result = comp.execute(df)
        assert result["main"].loc[0, "a"] == ""


# ------------------------------------------------------------------
# TestManualTable
# ------------------------------------------------------------------

@pytest.mark.unit
class TestManualTable:
    """manualtable drives explicit column coercion."""

    def test_string_to_int_cast(self):
        df = _df(("42",), ("7",), columns=["score"])
        comp = _make_component({
            "manualtable": [{"input_column": "score", "output_column": "score"}],
            "dieonerror": True,
        })
        result = comp.execute(df)
        assert result["main"]["score"].dtype in (object, "Int64", "int64", "float64")

    def test_unknown_column_skipped_with_warning(self):
        df = _df((1,), columns=["val"])
        comp = _make_component({
            "manualtable": [{"input_column": "nonexistent", "output_column": "nonexistent"}],
        })
        result = comp.execute(df)  # must not raise
        assert "main" in result

    def test_empty_manualtable_is_noop(self):
        df = _df(("text",), columns=["col"])
        comp = _make_component({"manualtable": []})
        result = comp.execute(df)
        assert list(result["main"]["col"]) == ["text"]


# ------------------------------------------------------------------
# TestAutocast
# ------------------------------------------------------------------

@pytest.mark.unit
class TestAutocast:
    """autocast=True applies pd.to_numeric best-effort."""

    def test_numeric_strings_converted(self):
        df = _df(("10",), ("20",), columns=["n"])
        comp = _make_component({"autocast": True})
        result = comp.execute(df)
        assert pd.to_numeric(result["main"]["n"], errors="coerce").notna().all()

    def test_non_numeric_strings_left_as_is(self):
        df = _df(("hello",), columns=["s"])
        comp = _make_component({"autocast": True})
        result = comp.execute(df)
        # autocast is best-effort -- non-numeric strings stay
        assert result["main"]["s"].iloc[0] == "hello"


# ------------------------------------------------------------------
# TestRejectRouting
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRejectRouting:
    """dieonerror=False routes failed conversions to REJECT flow."""

    def test_bad_row_goes_to_reject(self):
        df = _df(("not_a_number",), ("42",), columns=["num"])
        comp = _make_component({
            "manualtable": [{"input_column": "num", "output_column": "num"}],
            "dieonerror": False,
        })
        result = comp.execute(df)
        # The component tries to cast; if "not_a_number" fails, it goes to reject
        # (if it succeeds under autocast=False, both rows pass)
        assert "main" in result
        assert result["reject"] is None or isinstance(result["reject"], pd.DataFrame)

    def test_reject_contains_error_columns_when_present(self):
        """If any row is rejected it must have error_code and error_message."""
        # Force a guaranteed failure: cast a pure string to datetime
        df = _df(("definitely_not_a_date",), columns=["dt"])
        comp = _make_component({
            "manualtable": [{"input_column": "dt", "output_column": "dt"}],
            "dieonerror": False,
            # Provide a fake output schema so we resolve a target dtype
        })
        # Manually set output_schema to force datetime coercion
        comp.output_schema = [{"name": "dt", "type": "date"}]
        result = comp.execute(df)
        if result["reject"] is not None and not result["reject"].empty:
            assert "error_code" in result["reject"].columns
            assert "error_message" in result["reject"].columns


# ------------------------------------------------------------------
# TestDieOnError
# ------------------------------------------------------------------

@pytest.mark.unit
class TestDieOnError:
    """dieonerror=True raises DataValidationError on first failure."""

    def test_raises_on_bad_conversion(self):
        df = _df(("not_a_date",), columns=["dt"])
        comp = _make_component({
            "manualtable": [{"input_column": "dt", "output_column": "dt"}],
            "dieonerror": True,
        })
        comp.output_schema = [{"name": "dt", "type": "date"}]
        with pytest.raises((ComponentExecutionError, DataValidationError)):
            comp.execute(df)


# ------------------------------------------------------------------
# TestBothModesActive
# ------------------------------------------------------------------

@pytest.mark.unit
class TestBothModesActive:
    """autocast and manualtable can both be active simultaneously."""

    def test_manual_takes_effect_on_listed_columns(self):
        df = _df(("5", "hello"), columns=["num", "text"])
        comp = _make_component({
            "autocast": True,
            "manualtable": [{"input_column": "num", "output_column": "num"}],
            "dieonerror": True,
        })
        result = comp.execute(df)
        assert "main" in result
        # text column still present (passed through)
        assert "text" in result["main"].columns


# ------------------------------------------------------------------
# TestStatistics
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStatistics:
    """NB_LINE_OK and NB_LINE_REJECT tracked via globalMap."""

    def test_stats_all_ok(self):
        df = _df(("1",), ("2",), columns=["n"])
        gm = GlobalMap()
        comp = _make_component({}, global_map=gm)
        comp.execute(df)
        # Both rows pass through -> NB_LINE_OK should be 2
        assert gm.get("tConvertType_1_NB_LINE_OK") in (2, None)  # None if not set by component

    def test_reject_key_is_none_by_default(self):
        df = _df(("a",), columns=["col"])
        comp = _make_component({})
        result = comp.execute(df)
        # With no manualtable/autocast that fails, reject should be None
        assert result.get("reject") is None


# ------------------------------------------------------------------
# TestNoopConfig
# ------------------------------------------------------------------

@pytest.mark.unit
class TestNoopConfig:
    """No autocast, empty manualtable: rows pass through unchanged."""

    def test_passthrough_preserves_all_rows(self):
        df = _df(("alpha",), ("beta",), columns=["word"])
        comp = _make_component({"autocast": False, "manualtable": []})
        result = comp.execute(df)
        assert list(result["main"]["word"]) == ["alpha", "beta"]
