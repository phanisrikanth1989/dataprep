"""Post-bridge reject routing for is_reject / inner_join_reject /
catch_output_reject outputs."""
import pandas as pd

from src.v1.engine.components.transform.map.map_config import (
    parse_config, MapConfig,
)
from src.v1.engine.components.transform.map.map_reject_routing import (
    route_rejects,
)


def _cfg(outputs):
    raw = {
        "component_type": "Map",
        "inputs": {
            "main": {"name": "row1", "filter": "", "activate_filter": False,
                     "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
            "lookups": [],
        },
        "variables": [],
        "outputs": outputs,
        "die_on_error": True,
    }
    return parse_config(raw)


def test_is_reject_passes_through():
    """Active script populates is_reject outputs inline; routing is identity."""
    active_results = {
        "out": pd.DataFrame({"id": [1, 2]}),
        "rej": pd.DataFrame({"id": [3]}),  # already populated by active script
    }
    cfg = _cfg([
        {"name": "out", "is_reject": False, "inner_join_reject": False,
         "catch_output_reject": False, "filter": "", "activate_filter": False,
         "columns": [{"name": "id", "expression": "row1.id", "type": "int", "nullable": True}]},
        {"name": "rej", "is_reject": True, "inner_join_reject": False,
         "catch_output_reject": False, "filter": "", "activate_filter": False,
         "columns": [{"name": "id", "expression": "row1.id", "type": "int", "nullable": True}]},
    ])
    result = route_rejects(
        active_results=active_results, reject_results={},
        errors_df=None, inner_join_reject_dfs={},
        cfg=cfg, joined_df=pd.DataFrame({"id": [1, 2, 3]}),
    )
    assert list(result["out"]["id"]) == [1, 2]
    assert list(result["rej"]["id"]) == [3]


def test_inner_join_reject_uses_reject_script_result():
    """inner_join_reject outputs come from the reject-pass bridge call."""
    active_results = {"out": pd.DataFrame({"id": [1, 2]})}
    reject_results = {"rej_inner": pd.DataFrame({"id": [99], "reason": ["miss"]})}
    cfg = _cfg([
        {"name": "out", "is_reject": False, "inner_join_reject": False,
         "catch_output_reject": False, "filter": "", "activate_filter": False,
         "columns": [{"name": "id", "expression": "row1.id", "type": "int", "nullable": True}]},
        {"name": "rej_inner", "is_reject": False, "inner_join_reject": True,
         "catch_output_reject": False, "filter": "", "activate_filter": False,
         "columns": [
             {"name": "id", "expression": "row1.id", "type": "int", "nullable": True},
             {"name": "reason", "expression": '"miss"', "type": "str", "nullable": True},
         ]},
    ])
    result = route_rejects(
        active_results=active_results, reject_results=reject_results,
        errors_df=None, inner_join_reject_dfs={"row2": pd.DataFrame({"id": [99]})},
        cfg=cfg, joined_df=pd.DataFrame({"id": [1, 2]}),
    )
    assert list(result["rej_inner"]["id"]) == [99]
    assert list(result["rej_inner"]["reason"]) == ["miss"]


def test_catch_output_reject_populates_framework_columns_d06():
    """D-06: framework errorMessage/errorStackTrace WIN over user expressions."""
    active_results = {"out": pd.DataFrame({"id": [1, 3]})}  # row 2 (idx 1) failed
    errors_df = pd.DataFrame({
        "rowIndex": [1],
        "errorMessage": ["NPE at line 5"],
        "errorStackTrace": ["java.lang.NullPointerException\n  at ..."],
    })
    cfg = _cfg([
        {"name": "out", "is_reject": False, "inner_join_reject": False,
         "catch_output_reject": False, "filter": "", "activate_filter": False,
         "columns": [{"name": "id", "expression": "row1.id", "type": "int", "nullable": True}]},
        {"name": "errs", "is_reject": False, "inner_join_reject": False,
         "catch_output_reject": True, "filter": "", "activate_filter": False,
         "columns": [
             {"name": "id", "expression": "row1.id", "type": "int", "nullable": True},
             {"name": "errorMessage", "expression": '"placeholder"', "type": "str", "nullable": True},
             {"name": "errorStackTrace", "expression": '""', "type": "str", "nullable": True},
         ]},
    ])
    joined_df = pd.DataFrame({"id": [1, 2, 3]})  # 3 input rows; row 1 (0-indexed) failed
    result = route_rejects(
        active_results=active_results, reject_results={},
        errors_df=errors_df, inner_join_reject_dfs={},
        cfg=cfg, joined_df=joined_df,
    )
    errs = result["errs"]
    assert len(errs) == 1
    # User-declared 'id' column: evaluated against joined_df row at rowIndex=1 -> id=2
    assert errs.iloc[0]["id"] == 2
    # Framework values WIN for reserved cols (user "placeholder" expr overwritten)
    assert errs.iloc[0]["errorMessage"] == "NPE at line 5"
    assert "NullPointerException" in errs.iloc[0]["errorStackTrace"]


def test_no_failing_rows_returns_empty_catch_output():
    """No __errors__ -> empty catch_output_reject frame."""
    active_results = {"out": pd.DataFrame({"id": [1, 2, 3]})}
    cfg = _cfg([
        {"name": "out", "is_reject": False, "inner_join_reject": False,
         "catch_output_reject": False, "filter": "", "activate_filter": False,
         "columns": [{"name": "id", "expression": "row1.id", "type": "int", "nullable": True}]},
        {"name": "errs", "is_reject": False, "inner_join_reject": False,
         "catch_output_reject": True, "filter": "", "activate_filter": False,
         "columns": [{"name": "id", "expression": "row1.id", "type": "int", "nullable": True}]},
    ])
    result = route_rejects(
        active_results=active_results, reject_results={},
        errors_df=None, inner_join_reject_dfs={},
        cfg=cfg, joined_df=pd.DataFrame({"id": [1, 2, 3]}),
    )
    assert len(result["errs"]) == 0
