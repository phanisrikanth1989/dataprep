"""Tests for MemorizeRows engine component (tMemorizeRows).

Test classes:
    TestRegistration       -- registry decorator, BaseComponent inheritance
    TestValidation         -- _validate_config structural checks (Rule 12)
    TestEmptyInput         -- empty DataFrame returns empty without error
    TestPassthrough        -- all rows pass through unchanged
    TestGlobalMapSingleRow -- row_count=1: last row stored in globalMap at offset 0
    TestGlobalMapMultiRow  -- row_count=N: multiple offsets stored
    TestSpecifyCols        -- specify_cols filters which columns are memorized
    TestAllColsDefault     -- empty specify_cols memorizes all columns
    TestRowCountText       -- row_count is TEXT; context-var resolved in execute()
    TestRowCountInvalid    -- invalid row_count raises ConfigurationError
    TestStatistics         -- NB_LINE / NB_LINE_OK match input row count
    TestFewRowsThanCount   -- fewer input rows than row_count: missing offsets = None
"""
import pytest
import pandas as pd

from src.v1.engine.components.transform.memorize_rows import MemorizeRows
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_component(config=None, global_map=None, context_manager=None):
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    cfg = config if config is not None else {"row_count": "1"}
    comp = MemorizeRows(
        component_id="tMemorizeRows_1",
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
        assert REGISTRY.get("MemorizeRows") is MemorizeRows

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tMemorizeRows") is MemorizeRows

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(MemorizeRows, BaseComponent)


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidation:
    """_validate_config() -- structural checks, raises ConfigurationError."""

    def test_specify_cols_not_list_raises(self):
        comp = _make_component({"row_count": "1", "specify_cols": "bad"})
        with pytest.raises(ConfigurationError, match="specify_cols"):
            comp._validate_config()

    def test_valid_config_does_not_raise(self):
        comp = _make_component({"row_count": "1", "specify_cols": []})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestEmptyInput
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEmptyInput:
    """Empty DataFrame returns empty without error."""

    def test_empty_df_returns_empty(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame())
        assert isinstance(result["main"], pd.DataFrame)

    def test_none_returns_empty(self):
        comp = _make_component()
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)


# ------------------------------------------------------------------
# TestPassthrough
# ------------------------------------------------------------------

@pytest.mark.unit
class TestPassthrough:
    """All input rows pass through to main output unchanged."""

    def test_all_rows_pass_through(self):
        df = _df(("a",), ("b",), ("c",), columns=["val"])
        comp = _make_component()
        result = comp.execute(df)
        assert list(result["main"]["val"]) == ["a", "b", "c"]

    def test_reject_is_none(self):
        df = _df((1,), (2,), columns=["n"])
        comp = _make_component()
        result = comp.execute(df)
        assert result["reject"] is None

    def test_column_count_preserved(self):
        df = _df((1, "x", 3.0), columns=["a", "b", "c"])
        comp = _make_component()
        result = comp.execute(df)
        assert list(result["main"].columns) == ["a", "b", "c"]


# ------------------------------------------------------------------
# TestGlobalMapSingleRow
# ------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapSingleRow:
    """row_count=1 stores last row at offset 0 in globalMap."""

    def test_last_row_stored_offset_0(self):
        df = _df(("first",), ("last",), columns=["name"])
        gm = GlobalMap()
        comp = _make_component({"row_count": "1"}, global_map=gm)
        comp.execute(df)
        assert gm.get("tMemorizeRows_1_name_0") == "last"

    def test_not_first_row_at_offset_0(self):
        df = _df(("A",), ("B",), ("C",), columns=["v"])
        gm = GlobalMap()
        comp = _make_component({"row_count": "1"}, global_map=gm)
        comp.execute(df)
        assert gm.get("tMemorizeRows_1_v_0") == "C"


# ------------------------------------------------------------------
# TestGlobalMapMultiRow
# ------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapMultiRow:
    """row_count=2 stores last 2 rows at offsets 0 and 1."""

    def test_two_offsets_stored(self):
        df = _df((10,), (20,), (30,), columns=["n"])
        gm = GlobalMap()
        comp = _make_component({"row_count": "2"}, global_map=gm)
        comp.execute(df)
        # offset 0 = last row (30), offset 1 = second-to-last (20)
        assert gm.get("tMemorizeRows_1_n_0") == 30
        assert gm.get("tMemorizeRows_1_n_1") == 20

    def test_three_rows_row_count_3(self):
        df = _df(("a",), ("b",), ("c",), ("d",), columns=["v"])
        gm = GlobalMap()
        comp = _make_component({"row_count": "3"}, global_map=gm)
        comp.execute(df)
        assert gm.get("tMemorizeRows_1_v_0") == "d"
        assert gm.get("tMemorizeRows_1_v_1") == "c"
        assert gm.get("tMemorizeRows_1_v_2") == "b"


# ------------------------------------------------------------------
# TestSpecifyCols
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSpecifyCols:
    """specify_cols with memorize_it=False excludes columns from globalMap."""

    def test_memorize_it_false_not_stored(self):
        df = _df((1, "x"), columns=["num", "txt"])
        gm = GlobalMap()
        comp = _make_component({
            "row_count": "1",
            "specify_cols": [
                {"memorize_it": True},   # num
                {"memorize_it": False},  # txt
            ],
        }, global_map=gm)
        comp.execute(df)
        assert gm.get("tMemorizeRows_1_num_0") == 1
        assert gm.get("tMemorizeRows_1_txt_0") is None

    def test_all_memorize_it_true(self):
        df = _df((5, "y"), columns=["a", "b"])
        gm = GlobalMap()
        comp = _make_component({
            "row_count": "1",
            "specify_cols": [{"memorize_it": True}, {"memorize_it": True}],
        }, global_map=gm)
        comp.execute(df)
        assert gm.get("tMemorizeRows_1_a_0") == 5
        assert gm.get("tMemorizeRows_1_b_0") == "y"


# ------------------------------------------------------------------
# TestAllColsDefault
# ------------------------------------------------------------------

@pytest.mark.unit
class TestAllColsDefault:
    """Empty specify_cols memorizes all columns."""

    def test_all_columns_memorized_when_specify_cols_empty(self):
        df = _df((100, "z"), columns=["p", "q"])
        gm = GlobalMap()
        comp = _make_component({"row_count": "1", "specify_cols": []}, global_map=gm)
        comp.execute(df)
        assert gm.get("tMemorizeRows_1_p_0") == 100
        assert gm.get("tMemorizeRows_1_q_0") == "z"


# ------------------------------------------------------------------
# TestRowCountText
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRowCountText:
    """row_count is TEXT; context-variable-resolved string is coerced in _process."""

    def test_string_integer_accepted(self):
        df = _df((1,), (2,), columns=["v"])
        comp = _make_component({"row_count": "2"})
        result = comp.execute(df)
        assert len(result["main"]) == 2

    def test_context_var_resolved(self):
        df = _df(("a",), ("b",), columns=["x"])
        gm = GlobalMap()
        cm = ContextManager()
        cm.set("N", "1")
        comp = _make_component({"row_count": "${context.N}"}, global_map=gm, context_manager=cm)
        comp.execute(df)
        assert gm.get("tMemorizeRows_1_x_0") == "b"


# ------------------------------------------------------------------
# TestRowCountInvalid
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRowCountInvalid:
    """Non-integer row_count raises ConfigurationError in _process."""

    def test_non_integer_raises(self):
        df = _df((1,), columns=["v"])
        comp = _make_component({"row_count": "bad"})
        with pytest.raises(ConfigurationError, match="row_count"):
            comp.execute(df)

    def test_zero_raises(self):
        df = _df((1,), columns=["v"])
        comp = _make_component({"row_count": "0"})
        with pytest.raises(ConfigurationError, match="row_count"):
            comp.execute(df)


# ------------------------------------------------------------------
# TestStatistics
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStatistics:
    """NB_LINE / NB_LINE_OK match input row count."""

    def test_nb_line_equals_input_rows(self):
        df = _df((1,), (2,), (3,), columns=["v"])
        gm = GlobalMap()
        comp = _make_component({"row_count": "1"}, global_map=gm)
        comp.execute(df)
        assert gm.get("tMemorizeRows_1_NB_LINE") == 3
        assert gm.get("tMemorizeRows_1_NB_LINE_OK") == 3
        assert gm.get("tMemorizeRows_1_NB_LINE_REJECT") == 0


# ------------------------------------------------------------------
# TestFewRowsThanCount
# ------------------------------------------------------------------

@pytest.mark.unit
class TestFewRowsThanCount:
    """Fewer input rows than row_count: missing offsets filled with None."""

    def test_missing_offsets_are_none(self):
        df = _df(("only",), columns=["v"])
        gm = GlobalMap()
        comp = _make_component({"row_count": "3"}, global_map=gm)
        comp.execute(df)
        assert gm.get("tMemorizeRows_1_v_0") == "only"
        assert gm.get("tMemorizeRows_1_v_1") is None
        assert gm.get("tMemorizeRows_1_v_2") is None
