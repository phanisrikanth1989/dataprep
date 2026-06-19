"""Tests for the Pagination engine component (Pagination / tPagination).

Covers:
  TestRegistration   -- v1 name + Talend alias registered
  TestValidation     -- page_size / column-name config validation
  TestPagination     -- per-account page assignment + boundary at page_size
  TestSplit          -- debit/credit split incl. NULL / blank / non-D/C flag
  TestAggregation    -- SUM debit/credit, MIN opening balance, 0 -> "0" quirk
  TestRunningBalance -- carry-forward across pages, reset on account / page 1
  TestFlows          -- both main + detail flows, detail schema
  TestConfigurable   -- custom column-name mapping end to end
  TestEdgeCases      -- empty / None input guard
"""
import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.transform.pagination import Pagination
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ----------------------------------------------------------------
# Fixtures / helpers
# ----------------------------------------------------------------

_DEFAULT_CONFIG = {"page_size": 2}


def _make_component(config=None, global_map=None, context_manager=None):
    """Build a Pagination component with stock defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager if context_manager is not None else ContextManager()
    cfg = dict(config if config is not None else _DEFAULT_CONFIG)
    comp = Pagination(
        component_id="tPagination_1",
        config=cfg,
        global_map=gm,
        context_manager=cm,
    )
    # Mirror BaseComponent.execute() Step 1 so direct _process calls see self.config.
    comp.config = dict(cfg)
    return comp


def _make_df():
    """Two accounts; account 1 spans two pages at page_size=2.

    Input order is intentionally unsorted to exercise the (int(account), flag) sort.
    """
    return pd.DataFrame({
        "SUBACC":  ["1", "1", "1", "2"],
        "IDRORCR": ["D", "D", "C", "D"],
        "IAMOUNT": ["30", "20", "100", "40"],
        "OPBAL":   ["50.00", "50.00", "50.00", "200.00"],
        "STMTPG":  ["", "", "", ""],
        "CLBAL":   ["", "", "", ""],
    })


def _by_page(main_df):
    """Index summary rows by (SUBACC, STMTPG) for easy assertions."""
    return {
        (r["SUBACC"], r["STMTPG"]): r
        for _, r in main_df.iterrows()
    }


# ----------------------------------------------------------------
# TestRegistration
# ----------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    def test_registered_as_v1_name(self):
        assert REGISTRY.get("Pagination") is Pagination

    def test_registered_as_talend_alias(self):
        assert REGISTRY.get("tPagination") is Pagination


# ----------------------------------------------------------------
# TestValidation
# ----------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    def test_default_page_size_is_valid(self):
        comp = _make_component(config={})
        comp._validate_config()  # no raise

    def test_zero_page_size_raises(self):
        comp = _make_component(config={"page_size": 0})
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        assert "page_size" in str(ei.value)

    def test_negative_page_size_raises(self):
        comp = _make_component(config={"page_size": -5})
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_non_int_page_size_raises(self):
        comp = _make_component(config={"page_size": "100"})
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_bool_page_size_raises(self):
        # bool is a subclass of int -- must be rejected.
        comp = _make_component(config={"page_size": True})
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_empty_column_name_raises(self):
        comp = _make_component(config={"page_size": 10, "account_column": ""})
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        assert "account_column" in str(ei.value)

    def test_non_string_column_name_raises(self):
        comp = _make_component(config={"page_size": 10, "amount_column": 123})
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_missing_required_input_column_raises(self):
        comp = _make_component(config={"page_size": 2})
        df = pd.DataFrame({"SUBACC": ["1"], "IDRORCR": ["D"]})  # no IAMOUNT
        with pytest.raises(ConfigurationError) as ei:
            comp._process(df)
        assert "IAMOUNT" in str(ei.value)


# ----------------------------------------------------------------
# TestPagination
# ----------------------------------------------------------------


@pytest.mark.unit
class TestPagination:
    def test_page_breaks_every_page_size_rows(self):
        comp = _make_component(config={"page_size": 2})
        detail = comp._process(_make_df())["detail"]
        # Sorted order: acct1 -> C,D,D (pages 1,1,2); acct2 -> D (page 1)
        assert detail["STMTPG"].tolist() == [1, 1, 2, 1]

    def test_page_resets_per_account(self):
        # Three rows in account 2 -> its own pages 1,1,2 independent of account 1.
        df = pd.DataFrame({
            "SUBACC":  ["1", "2", "2", "2"],
            "IDRORCR": ["D", "D", "D", "D"],
            "IAMOUNT": ["1", "2", "3", "4"],
            "OPBAL":   ["0", "0", "0", "0"],
            "STMTPG":  ["", "", "", ""],
            "CLBAL":   ["", "", "", ""],
        })
        comp = _make_component(config={"page_size": 2})
        detail = comp._process(df)["detail"]
        assert detail["SUBACC"].tolist() == ["1", "2", "2", "2"]
        assert detail["STMTPG"].tolist() == [1, 1, 1, 2]

    def test_large_page_size_single_page(self):
        comp = _make_component(config={"page_size": 100000})
        main = comp._process(_make_df())["main"]
        # Account 1 collapses to a single page; account 2 to one page -> 2 summary rows.
        assert len(main) == 2
        assert set(main["STMTPG"]) == {"1"}


# ----------------------------------------------------------------
# TestSplit
# ----------------------------------------------------------------


@pytest.mark.unit
class TestSplit:
    def test_debit_credit_amounts_split_and_summed(self):
        comp = _make_component(config={"page_size": 2})
        rows = _by_page(comp._process(_make_df())["main"])
        # Page (1,1): C 100 + D 30
        assert rows[("1", "1")]["AMT_D"] == "30.00"
        assert rows[("1", "1")]["AMT_C"] == "100.00"

    def test_null_blank_and_unknown_flag_become_zero(self):
        df = pd.DataFrame({
            "SUBACC":  ["1", "1", "1"],
            "IDRORCR": ["D", "C", "X"],
            "IAMOUNT": ["NULL", "", "999"],   # null token / blank / non-D-C flag
            "OPBAL":   ["", "", ""],
            "STMTPG":  ["", "", ""],
            "CLBAL":   ["", "", ""],
        })
        comp = _make_component(config={"page_size": 10})
        rows = _by_page(comp._process(df)["main"])
        page = rows[("1", "1")]
        assert page["AMT_D"] == "0"
        assert page["AMT_C"] == "0"

    def test_nan_amount_becomes_zero(self):
        # A real float NaN in the amount column must be treated as null, not parsed.
        df = pd.DataFrame({
            "SUBACC":  ["1", "1"],
            "IDRORCR": ["D", "C"],
            "IAMOUNT": [float("nan"), "20.00"],
            "OPBAL":   ["0", "0"],
            "STMTPG":  ["", ""],
            "CLBAL":   ["", ""],
        })
        comp = _make_component(config={"page_size": 10})
        rows = _by_page(comp._process(df)["main"])
        page = rows[("1", "1")]
        assert page["AMT_D"] == "0"      # NaN debit -> zero
        assert page["AMT_C"] == "20.00"  # credit unaffected


# ----------------------------------------------------------------
# TestAggregation
# ----------------------------------------------------------------


@pytest.mark.unit
class TestAggregation:
    def test_min_opening_balance_per_page(self):
        df = pd.DataFrame({
            "SUBACC":  ["1", "1"],
            "IDRORCR": ["D", "D"],
            "IAMOUNT": ["1", "2"],
            "OPBAL":   ["80.00", "30.00"],   # MIN -> 30.00
            "STMTPG":  ["", ""],
            "CLBAL":   ["", ""],
        })
        comp = _make_component(config={"page_size": 10})
        rows = _by_page(comp._process(df)["main"])
        assert rows[("1", "1")]["OPBAL"] == "30.00"

    def test_zero_sum_formats_as_bare_zero(self):
        # Exact-zero credit total must render as "0", not "0.00" (parity quirk).
        rows = _by_page(_make_component(config={"page_size": 2})._process(_make_df())["main"])
        assert rows[("1", "2")]["AMT_C"] == "0"

    def test_nonzero_sum_formats_two_decimals(self):
        rows = _by_page(_make_component(config={"page_size": 2})._process(_make_df())["main"])
        assert rows[("1", "2")]["AMT_D"] == "20.00"


# ----------------------------------------------------------------
# TestRunningBalance
# ----------------------------------------------------------------


@pytest.mark.unit
class TestRunningBalance:
    def test_carry_forward_within_account(self):
        rows = _by_page(_make_component(config={"page_size": 2})._process(_make_df())["main"])
        # Page1 closing carries into page2 opening.
        assert rows[("1", "1")]["CLBAL"] == "120.00"
        assert rows[("1", "2")]["OPBAL"] == "120.00"
        assert rows[("1", "2")]["CLBAL"] == "100.00"

    def test_balance_resets_on_account_change(self):
        rows = _by_page(_make_component(config={"page_size": 2})._process(_make_df())["main"])
        # Account 2 page 1 opens at its own OPBAL (200.00), not account 1's closing.
        assert rows[("2", "1")]["OPBAL"] == "200.00"
        assert rows[("2", "1")]["CLBAL"] == "160.00"

    def test_balance_resets_on_page_one(self):
        # Two accounts each with one page; page==1 always resets to that page's OPBAL.
        df = pd.DataFrame({
            "SUBACC":  ["5", "9"],
            "IDRORCR": ["D", "C"],
            "IAMOUNT": ["10.00", "5.00"],
            "OPBAL":   ["100.00", "70.00"],
            "STMTPG":  ["", ""],
            "CLBAL":   ["", ""],
        })
        rows = _by_page(_make_component(config={"page_size": 10})._process(df)["main"])
        assert rows[("5", "1")]["OPBAL"] == "100.00"
        assert rows[("5", "1")]["CLBAL"] == "90.00"
        assert rows[("9", "1")]["OPBAL"] == "70.00"
        assert rows[("9", "1")]["CLBAL"] == "75.00"


# ----------------------------------------------------------------
# TestFlows
# ----------------------------------------------------------------


@pytest.mark.unit
class TestFlows:
    def test_both_flows_returned(self):
        result = _make_component(config={"page_size": 2})._process(_make_df())
        assert set(result.keys()) == {"main", "detail"}
        assert isinstance(result["main"], pd.DataFrame)
        assert isinstance(result["detail"], pd.DataFrame)

    def test_detail_keeps_input_columns_plus_filled_page(self):
        df = _make_df()
        detail = _make_component(config={"page_size": 2})._process(df)["detail"]
        assert list(detail.columns) == list(df.columns)
        assert detail["STMTPG"].tolist() == [1, 1, 2, 1]

    def test_summary_columns_are_input_plus_derived(self):
        df = _make_df()
        main = _make_component(config={"page_size": 2})._process(df)["main"]
        assert list(main.columns) == list(df.columns) + ["AMT_D", "AMT_C"]

    def test_unrelated_columns_blank_in_summary(self):
        df = _make_df()
        df["NARRATIVE"] = ["a", "b", "c", "d"]
        main = _make_component(config={"page_size": 2})._process(df)["main"]
        assert (main["NARRATIVE"] == "").all()

    def test_stats_updated(self):
        comp = _make_component(config={"page_size": 2})
        comp._process(_make_df())
        assert comp.stats["NB_LINE"] == 4
        assert comp.stats["NB_LINE_OK"] == 3
        assert comp.stats["NB_LINE_REJECT"] == 0


# ----------------------------------------------------------------
# TestConfigurable
# ----------------------------------------------------------------


@pytest.mark.unit
class TestConfigurable:
    def test_custom_column_names(self):
        df = pd.DataFrame({
            "ACCT":   ["1", "1"],
            "DC":     ["D", "C"],
            "AMT":    ["10.00", "40.00"],
            "OPEN":   ["100.00", "100.00"],
            "PAGE":   ["", ""],
            "CLOSE":  ["", ""],
        })
        config = {
            "page_size": 10,
            "account_column": "ACCT",
            "dc_flag_column": "DC",
            "amount_column": "AMT",
            "page_column": "PAGE",
            "opening_balance_column": "OPEN",
            "closing_balance_column": "CLOSE",
            "debit_column": "DR",
            "credit_column": "CR",
        }
        result = _make_component(config=config)._process(df)
        main = result["main"]
        assert list(main.columns) == list(df.columns) + ["DR", "CR"]
        row = main.iloc[0]
        assert row["ACCT"] == "1"
        assert row["PAGE"] == "1"
        assert row["DR"] == "10.00"
        assert row["CR"] == "40.00"
        assert row["OPEN"] == "100.00"
        assert row["CLOSE"] == "130.00"  # 100 - 10 + 40
        assert result["detail"]["PAGE"].tolist() == [1, 1]

    def test_custom_flag_and_null_token(self):
        df = pd.DataFrame({
            "SUBACC":  ["1", "1"],
            "IDRORCR": ["DR", "CR"],
            "IAMOUNT": ["5.00", "NIL"],
            "OPBAL":   ["0", "0"],
            "STMTPG":  ["", ""],
            "CLBAL":   ["", ""],
        })
        config = {
            "page_size": 10,
            "debit_flag_value": "DR",
            "credit_flag_value": "CR",
            "null_token": "NIL",
        }
        rows = _by_page(_make_component(config=config)._process(df)["main"])
        page = rows[("1", "1")]
        assert page["AMT_D"] == "5.00"
        assert page["AMT_C"] == "0"   # NIL treated as null


# ----------------------------------------------------------------
# TestEdgeCases
# ----------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    def test_empty_dataframe(self):
        empty = pd.DataFrame(columns=["SUBACC", "IDRORCR", "IAMOUNT"])
        result = _make_component(config={"page_size": 2})._process(empty)
        assert result["main"].empty
        assert result["detail"].empty

    def test_none_input(self):
        result = _make_component(config={"page_size": 2})._process(None)
        assert result["main"] is None
        assert result["detail"] is None
