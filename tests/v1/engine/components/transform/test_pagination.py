"""Tests for the Pagination engine component (Pagination / tPagination).

Statement pagination with a configurable ASCENDING multi-column sort:

  * Sort keys come from ``sort_columns`` and are compared as PLAIN STRINGS,
    ascending (no ``int()`` cast on the account).
  * The D/C flag column (``dc_flag_column``) is NOT a sort key -- it drives the
    debit/credit split during aggregation only.
  * The ``main`` flow is 1:1 with the input (no aggregation): every row is
    stamped with its PAGE's AMT_D/AMT_C and the computed OPBAL/CLBAL (broadcast).
  * Optional config-gated derived columns: absolute balance, D/C sign columns,
    multi-page flag.
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

_SORT_COLS = ["SUBACC", "OPBALCCY", "CLBALDATE"]

_CONFIG = {
    "page_size": 2,
    "sort_columns": _SORT_COLS,
    "account_column": "SUBACC",
    "dc_flag_column": "DRORCR",
    "amount_column": "AMOUNT",
    "page_column": "STMTPG",
    "opening_balance_column": "OPBAL",
    "closing_balance_column": "CLBAL",
}


def _make_component(config=None, global_map=None, context_manager=None):
    """Build a Pagination component with stock defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager if context_manager is not None else ContextManager()
    cfg = dict(config if config is not None else {"page_size": 2})
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

    Input order is intentionally scrambled so the (SUBACC, OPBALCCY, CLBALDATE)
    ascending sort -- NOT the DRORCR flag -- determines row order.

    Sorted account-1 order is EUR/240103, USD/240101, USD/240102:
      page 1 -> {EUR D 30, USD C 20}, page 2 -> {USD D 10}.
    """
    return pd.DataFrame({
        "SUBACC":    ["1", "1", "1", "2"],
        "OPBALCCY":  ["USD", "USD", "EUR", "USD"],
        "CLBALDATE": ["240102", "240101", "240103", "240101"],
        "DRORCR":    ["D", "C", "D", "D"],
        "AMOUNT":    ["10", "20", "30", "40"],
        "OPBAL":     ["50.00", "50.00", "50.00", "200.00"],
        "STMTPG":    ["", "", "", ""],
        "CLBAL":     ["", "", "", ""],
    })


def _by_page(main_df):
    """Index main rows by (SUBACC, page-as-str). Page values are identical across
    all rows of a page (broadcast), so collapsing to the last row per page is fine
    for page-level value assertions."""
    return {(str(r["SUBACC"]), str(r["STMTPG"])): r for _, r in main_df.iterrows()}


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
# TestSort -- the headline behaviour
# ----------------------------------------------------------------


@pytest.mark.unit
class TestSort:
    def test_detail_sorted_by_three_keys_ascending(self):
        detail = _make_component(config=_CONFIG)._process(_make_df())["detail"]
        # account 1: EUR/240103, USD/240101, USD/240102 ; then account 2.
        assert detail["OPBALCCY"].tolist() == ["EUR", "USD", "USD", "USD"]
        assert detail["CLBALDATE"].tolist() == ["240103", "240101", "240102", "240101"]
        assert detail["DRORCR"].tolist() == ["D", "C", "D", "D"]

    def test_page_assigned_in_sorted_order(self):
        detail = _make_component(config=_CONFIG)._process(_make_df())["detail"]
        assert detail["STMTPG"].tolist() == [1, 1, 2, 1]

    def test_account_sorted_as_string_not_numeric(self):
        # String ascending: "10" sorts before "2".
        df = pd.DataFrame({
            "SUBACC":    ["2", "10"],
            "OPBALCCY":  ["USD", "USD"],
            "CLBALDATE": ["240101", "240101"],
            "DRORCR":    ["D", "D"],
            "AMOUNT":    ["1", "2"],
            "OPBAL":     ["0", "0"],
            "STMTPG":    ["", ""],
            "CLBAL":     ["", ""],
        })
        detail = _make_component(config=_CONFIG)._process(df)["detail"]
        assert detail["SUBACC"].tolist() == ["10", "2"]

    def test_dc_flag_is_not_a_sort_key(self):
        # Same (SUBACC, OPBALCCY, CLBALDATE) for both rows -> stable input order
        # is preserved regardless of DRORCR value (C before D here).
        df = pd.DataFrame({
            "SUBACC":    ["1", "1"],
            "OPBALCCY":  ["USD", "USD"],
            "CLBALDATE": ["240101", "240101"],
            "DRORCR":    ["C", "D"],
            "AMOUNT":    ["5", "7"],
            "OPBAL":     ["0", "0"],
            "STMTPG":    ["", ""],
            "CLBAL":     ["", ""],
        })
        detail = _make_component(config=_CONFIG)._process(df)["detail"]
        assert detail["DRORCR"].tolist() == ["C", "D"]


# ----------------------------------------------------------------
# TestSplit -- DRORCR still drives debit/credit
# ----------------------------------------------------------------


@pytest.mark.unit
class TestSplit:
    def test_debit_credit_split_uses_dc_flag(self):
        rows = _by_page(_make_component(config=_CONFIG)._process(_make_df())["main"])
        # page (1,1): EUR D 30 + USD C 20
        assert rows[("1", "1")]["AMT_D"] == "30.00"
        assert rows[("1", "1")]["AMT_C"] == "20.00"
        # page (1,2): USD D 10
        assert rows[("1", "2")]["AMT_D"] == "10.00"
        assert rows[("1", "2")]["AMT_C"] == "0"

    def test_null_blank_and_nan_amounts_become_zero(self):
        # NULL token, blank string, and float NaN all parse to zero (no contribution).
        df = pd.DataFrame({
            "SUBACC":    ["1", "1", "1", "1"],
            "OPBALCCY":  ["USD", "USD", "USD", "USD"],
            "CLBALDATE": ["240101", "240101", "240101", "240101"],
            "DRORCR":    ["D", "C", "D", "C"],
            "AMOUNT":    ["NULL", "", float("nan"), "20.00"],
            "OPBAL":     ["0", "0", "0", "0"],
            "STMTPG":    ["", "", "", ""],
            "CLBAL":     ["", "", "", ""],
        })
        rows = _by_page(_make_component(config={**_CONFIG, "page_size": 10})._process(df)["main"])
        page = rows[("1", "1")]
        assert page["AMT_D"] == "0"       # NULL + NaN debits -> zero
        assert page["AMT_C"] == "20.00"   # only the real credit counts


# ----------------------------------------------------------------
# TestMainBroadcast -- main keeps every row + per-page values
# ----------------------------------------------------------------


@pytest.mark.unit
class TestMainBroadcast:
    def test_main_is_one_to_one_with_input(self):
        df = _make_df()
        main = _make_component(config=_CONFIG)._process(df)["main"]
        assert len(main) == len(df)  # 4 in -> 4 out (no aggregation)
        combos = {(r["SUBACC"], int(r["STMTPG"])) for _, r in main.iterrows()}
        assert combos == {("1", 1), ("1", 2), ("2", 1)}

    def test_main_columns_are_detail_plus_amt(self):
        res = _make_component(config=_CONFIG)._process(_make_df())
        main, detail = res["main"], res["detail"]
        assert list(main.columns) == list(detail.columns) + ["AMT_D", "AMT_C"]

    def test_each_row_keeps_its_own_passthrough(self):
        # No first-row carry: every row retains its OWN pass-through value.
        df = _make_df()
        df["SIDE"] = ["S0", "S1", "S2", "S3"]  # input index 0..3
        main = _make_component(config=_CONFIG)._process(df)["main"]
        # main is in sorted order: idx2, idx1, idx0 (acct1), idx3 (acct2).
        assert main["SIDE"].tolist() == ["S2", "S1", "S0", "S3"]

    def test_page_values_identical_across_rows_of_page(self):
        main = _make_component(config=_CONFIG)._process(_make_df())["main"]
        pg1 = main[(main["SUBACC"] == "1") & (main["STMTPG"] == 1)]
        assert len(pg1) == 2  # two rows share page 1
        assert set(pg1["AMT_D"]) == {"30.00"}
        assert set(pg1["AMT_C"]) == {"20.00"}
        assert set(pg1["OPBAL"]) == {"50.00"}
        assert set(pg1["CLBAL"]) == {"40.00"}

    def test_running_balance_carries_across_pages(self):
        rows = _by_page(_make_component(config=_CONFIG)._process(_make_df())["main"])
        # page1: 50 - 30 + 20 = 40 ; page2 opens at 40, 40 - 10 + 0 = 30
        assert rows[("1", "1")]["OPBAL"] == "50.00"
        assert rows[("1", "1")]["CLBAL"] == "40.00"
        assert rows[("1", "2")]["OPBAL"] == "40.00"   # carry-forward, overwrites raw 50.00
        assert rows[("1", "2")]["CLBAL"] == "30.00"

    def test_balance_resets_on_account_change(self):
        rows = _by_page(_make_component(config=_CONFIG)._process(_make_df())["main"])
        assert rows[("2", "1")]["OPBAL"] == "200.00"
        assert rows[("2", "1")]["CLBAL"] == "160.00"


# ----------------------------------------------------------------
# TestDerivedColumns -- config-gated abs / sign / multi-page flag
# ----------------------------------------------------------------

_DERIVED = {
    **_CONFIG,
    "absolute_balance": True,
    "opening_sign_column": "OPBALSIGN",
    "closing_sign_column": "CLBALSIGN",
    "opening_multipage_column": "OPBALTP",
    "closing_multipage_column": "CLBALTP",
    "multipage_value": "M",
    "multipage_single_value": "F",
}


def _derived_df():
    """Account 1 spans 2 pages and goes negative; account 2 is single-page."""
    return pd.DataFrame({
        "SUBACC":    ["1", "1", "1", "2"],
        "OPBALCCY":  ["USD", "USD", "USD", "USD"],
        "CLBALDATE": ["240101", "240102", "240103", "240101"],
        "DRORCR":    ["D", "D", "C", "C"],
        "AMOUNT":    ["100", "100", "10", "5"],
        "OPBAL":     ["50.00", "50.00", "50.00", "100.00"],
        "OPBALSIGN": ["", "", "", ""],
        "CLBALSIGN": ["", "", "", ""],
        "OPBALTP":   ["", "", "", ""],
        "CLBALTP":   ["", "", "", ""],
        "STMTPG":    ["", "", "", ""],
        "CLBAL":     ["", "", "", ""],
    })


@pytest.mark.unit
class TestDerivedColumns:
    def test_absolute_balance(self):
        rows = _by_page(_make_component(config=_DERIVED)._process(_derived_df())["main"])
        # page1: 50 - 200 = -150 -> abs 150 ; opening 50 -> 50
        assert rows[("1", "1")]["OPBAL"] == "50.00"
        assert rows[("1", "1")]["CLBAL"] == "150.00"
        assert rows[("2", "1")]["CLBAL"] == "105.00"

    def test_sign_columns_from_signed_value(self):
        rows = _by_page(_make_component(config=_DERIVED)._process(_derived_df())["main"])
        assert rows[("1", "1")]["OPBALSIGN"] == "C"   # +50
        assert rows[("1", "1")]["CLBALSIGN"] == "D"   # -150
        assert rows[("1", "2")]["CLBALSIGN"] == "D"   # -140
        assert rows[("2", "1")]["CLBALSIGN"] == "C"   # +105

    def test_zero_balance_sign_is_credit(self):
        df = pd.DataFrame({
            "SUBACC": ["9"], "OPBALCCY": ["USD"], "CLBALDATE": ["240101"],
            "DRORCR": ["D"], "AMOUNT": ["100.00"], "OPBAL": ["100.00"],
            "OPBALSIGN": [""], "CLBALSIGN": [""], "CLBALTP": [""],
            "STMTPG": [""], "CLBAL": [""],
        })
        rows = _by_page(_make_component(config=_DERIVED)._process(df)["main"])
        assert rows[("9", "1")]["CLBAL"] == "0.00"     # 100 - 100
        assert rows[("9", "1")]["CLBALSIGN"] == "C"     # zero -> credit

    def test_opening_multipage_flag_marks_first_page_final(self):
        # OPBALTP: F on page 1, M on later pages; single-page account -> F.
        rows = _by_page(_make_component(config=_DERIVED)._process(_derived_df())["main"])
        assert rows[("1", "1")]["OPBALTP"] == "F"   # first page of a multi-page acct
        assert rows[("1", "2")]["OPBALTP"] == "M"   # later page
        assert rows[("2", "1")]["OPBALTP"] == "F"   # single-page account

    def test_closing_multipage_flag_marks_last_page_final(self):
        # CLBALTP: F on the last page (== max STMTPG), M before it; single-page -> F.
        rows = _by_page(_make_component(config=_DERIVED)._process(_derived_df())["main"])
        assert rows[("1", "1")]["CLBALTP"] == "M"   # not yet the last page
        assert rows[("1", "2")]["CLBALTP"] == "F"   # last page of the account
        assert rows[("2", "1")]["CLBALTP"] == "F"   # single-page account

    def test_derived_off_by_default(self):
        # Without the derived keys, balances are NOT absolute and sign/type untouched.
        rows = _by_page(_make_component(config=_CONFIG)._process(_derived_df())["main"])
        assert rows[("1", "1")]["CLBAL"] == "-150.00"   # raw, not abs
        assert rows[("1", "1")]["OPBALSIGN"] == ""        # untouched input
        assert rows[("1", "1")]["OPBALTP"] == ""          # untouched input
        assert rows[("1", "1")]["CLBALTP"] == ""          # untouched input


# ----------------------------------------------------------------
# TestValidation
# ----------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    def test_default_config_valid(self):
        _make_component(config={})._validate_config()  # no raise

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

    def test_non_list_sort_columns_raises(self):
        comp = _make_component(config={"sort_columns": "SUBACC"})
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        assert "sort_columns" in str(ei.value)

    def test_empty_sort_column_entry_raises(self):
        comp = _make_component(config={"sort_columns": ["SUBACC", ""]})
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_non_bool_absolute_balance_raises(self):
        comp = _make_component(config={"absolute_balance": "yes"})
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        assert "absolute_balance" in str(ei.value)

    def test_non_string_sign_column_raises(self):
        comp = _make_component(config={"opening_sign_column": 123})
        with pytest.raises(ConfigurationError) as ei:
            comp._validate_config()
        assert "opening_sign_column" in str(ei.value)

    def test_missing_required_input_column_raises(self):
        df = _make_df().drop(columns=["AMOUNT"])
        comp = _make_component(config=_CONFIG)
        with pytest.raises(ConfigurationError) as ei:
            comp._process(df)
        assert "AMOUNT" in str(ei.value)

    def test_missing_sort_column_in_data_raises(self):
        df = _make_df().drop(columns=["CLBALDATE"])
        comp = _make_component(config=_CONFIG)
        with pytest.raises(ConfigurationError) as ei:
            comp._process(df)
        assert "CLBALDATE" in str(ei.value)


# ----------------------------------------------------------------
# TestEdgeCases
# ----------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    def test_empty_dataframe(self):
        empty = pd.DataFrame(columns=["SUBACC", "OPBALCCY", "CLBALDATE", "DRORCR", "AMOUNT"])
        result = _make_component(config=_CONFIG)._process(empty)
        assert result["main"].empty
        assert result["detail"].empty

    def test_none_input(self):
        result = _make_component(config=_CONFIG)._process(None)
        assert result["main"] is None
        assert result["detail"] is None
