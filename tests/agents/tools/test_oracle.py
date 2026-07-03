import pandas as pd

from agents.tools.run_and_validate import RunResult, check, diff_frames


def test_diff_keyed_detects_missing_and_mismatch():
    exp = pd.DataFrame({"cc": ["US", "UK"], "name": ["A", "B"]})
    act = pd.DataFrame({"cc": ["US"], "name": ["X"]})
    d = diff_frames(act, exp, keys=["cc"])
    assert d["missing"] == 1  # UK absent from actual
    assert d["value_mismatch"] == 1  # US name X != A


def test_diff_bag_when_no_keys():
    exp = pd.DataFrame({"v": ["a", "b"]})
    assert diff_frames(pd.DataFrame({"v": ["b", "a"]}), exp, keys=None)["equal"] is True
    assert diff_frames(pd.DataFrame({"v": ["a"]}), exp, keys=None)["equal"] is False


def test_keyed_diff_fails_loud_on_non_unique_key():
    exp = pd.DataFrame({"cc": ["US", "US"], "name": ["A", "B"]})
    act = pd.DataFrame({"cc": ["US", "US"], "name": ["A", "Z"]})
    d = diff_frames(act, exp, keys=["cc"])
    assert d["equal"] is False and "unique" in d.get("reason", "")


def _rr(outputs, status="success", dropped=None, comp_err=None):
    cs = {"c": {"status": "error"}} if comp_err else {}
    return RunResult(status=status, outputs=outputs, dropped_components=dropped or [], component_stats=cs)


def test_check_passes_on_exact_match():
    exp = {"matched": pd.DataFrame({"cc": ["US"]})}
    rr = _rr({"out1": pd.DataFrame({"cc": ["US"]})})
    rep = check(rr, exp, output_map={"matched": "out1"}, keys={"matched": ["cc"]})
    assert rep["passed"] is True


def test_check_fails_on_dropped_component():
    exp = {"matched": pd.DataFrame({"cc": ["US"]})}
    rr = _rr({"out1": pd.DataFrame({"cc": ["US"]})}, dropped=["ghost"])
    rep = check(rr, exp, output_map={"matched": "out1"}, keys={"matched": ["cc"]})
    assert rep["passed"] is False
    assert any("dropped" in r for r in rep["reasons"])
