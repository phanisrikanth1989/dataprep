import pandas as pd

from agents.tools.reference_matcher import match_phase_a


def _main():
    return pd.DataFrame({"cc": ["US", "UK", "FR"], "amt": [10, 20, 30]})


def test_exact_match_and_one_sided_break():
    lookup = pd.DataFrame({"cc": ["US", "UK"], "name": ["United States", "United Kingdom"]})
    r = match_phase_a(_main(), lookup, keys=["cc"])
    assert r["stats"] == {"n_matched": 2, "n_break_no_match": 1, "n_break_multi": 0}
    assert set(r["matched"]["cc"]) == {"US", "UK"}
    assert list(r["breaks"]["cc"]) == ["FR"]
    assert list(r["breaks"]["break_reason"]) == ["no_match"]


def test_on_multi_first_keeps_one():
    lookup = pd.DataFrame({"cc": ["US", "US", "UK"], "name": ["A", "B", "United Kingdom"]})
    r = match_phase_a(_main(), lookup, keys=["cc"], on_multi="first")
    assert r["stats"]["n_matched"] == 2 and r["stats"]["n_break_multi"] == 0
    assert list(r["matched"].loc[r["matched"]["cc"] == "US", "name"]) == ["A"]


def test_on_multi_all_fans_out():
    lookup = pd.DataFrame({"cc": ["US", "US", "UK"], "name": ["A", "B", "United Kingdom"]})
    r = match_phase_a(_main(), lookup, keys=["cc"], on_multi="all")
    assert r["stats"]["n_matched"] == 3  # US x2 + UK x1


def test_on_multi_break_flags_duplicate():
    lookup = pd.DataFrame({"cc": ["US", "US", "UK"], "name": ["A", "B", "United Kingdom"]})
    r = match_phase_a(_main(), lookup, keys=["cc"], on_multi="break")
    assert r["stats"] == {"n_matched": 1, "n_break_no_match": 1, "n_break_multi": 1}
    assert set(r["breaks"].loc[r["breaks"]["break_reason"] == "multi_match", "cc"]) == {"US"}
