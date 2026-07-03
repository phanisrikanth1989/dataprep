import json

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


def test_keyed_diff_flags_extra_actual_column():
    exp = pd.DataFrame({"cc": ["US"], "name": ["A"]})
    act = pd.DataFrame({"cc": ["US"], "name": ["A"], "leaked": ["X"]})
    d = diff_frames(act, exp, keys=["cc"])
    assert d["equal"] is False


def test_bag_mode_column_order_insensitive():
    exp = pd.DataFrame({"a": ["1"], "b": ["2"]})
    act = pd.DataFrame({"b": ["2"], "a": ["1"]})
    assert diff_frames(act, exp, keys=None)["equal"] is True


def test_bag_mode_flags_column_name_mismatch():
    exp = pd.DataFrame({"a": ["1"]})
    act = pd.DataFrame({"z": ["1"]})
    assert diff_frames(act, exp, keys=None)["equal"] is False


def test_cli_missing_golden_dir_returns_two(tmp_path, capsys):
    from agents.tools.run_and_validate import main
    job = tmp_path / "job.json"
    job.write_text('{"components": [], "flows": []}')
    rc = main(["--job", str(job), "--golden-dir", str(tmp_path / "nope")])
    assert rc == 2


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


def test_keyed_diff_flags_missing_expected_column_zero_rows():
    exp = pd.DataFrame({"cc": pd.Series([], dtype=str), "name": pd.Series([], dtype=str)})
    act = pd.DataFrame({"cc": pd.Series([], dtype=str)})  # actual dropped 'name'
    d = diff_frames(act, exp, keys=["cc"])
    assert d["equal"] is False


def test_cli_wrong_shape_manifest_returns_two(tmp_path):
    from agents.tools.run_and_validate import main
    job = tmp_path / "job.json"; job.write_text('{"components": [], "flows": []}')
    gdir = tmp_path / "g"; gdir.mkdir()
    (gdir / "manifest.json").write_text('[1, 2, 3]')   # valid JSON, wrong shape
    rc = main(["--job", str(job), "--golden-dir", str(gdir)])
    assert rc == 2


# ---------------------------------------------------------------------------
# main() happy-path CLI tests (bridge-free FileInputDelimited -> FileOutputDelimited
# passthrough, no tMap / no {{java}}). The golden data is ';'-separated -- the repo
# convention -- and the manifest OMITS 'sep' so the CLI's default separator is the
# thing under test (guards I-4: the old ',' default mis-parses ';' golden data).
# ---------------------------------------------------------------------------
def _passthrough_job(in_csv, out_csv, sep=";"):
    """A minimal engine-runnable passthrough job (shape mirrors test_run_capture)."""
    cols = [{"name": "cc", "type": "str", "nullable": True, "key": False},
            {"name": "amt", "type": "str", "nullable": True, "key": False}]
    return {
        "job_name": "passthrough",
        "components": [
            {"id": "in1", "type": "FileInputDelimited",
             "config": {"filepath": str(in_csv), "fieldseparator": sep, "header_rows": 1,
                        "die_on_error": False},
             "inputs": [], "outputs": ["f1"],
             "schema": {"input": [], "output": cols},
             "subjob_id": "subjob_1", "is_subjob_start": True},
            {"id": "out1", "type": "FileOutputDelimited",
             "config": {"filepath": str(out_csv), "fieldseparator": sep, "include_header": True,
                        "file_exist_exception": False, "create_directory": True},
             "inputs": ["f1"], "outputs": [],
             "schema": {"input": cols, "output": []},
             "subjob_id": "subjob_1", "is_subjob_start": False},
        ],
        "flows": [{"name": "f1", "from": "in1", "to": "out1", "type": "flow"}],
    }


def _write_cli_case(tmp_path, expected_csv_text):
    """Wire up job.json + golden dir (manifest OMITS sep) and return main() argv."""
    src = tmp_path / "source.csv"
    src.write_text("cc;amt\nUS;10\nUK;20\n")
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(_passthrough_job(src, tmp_path / "out.csv")))
    gdir = tmp_path / "golden"; gdir.mkdir()
    (gdir / "manifest.json").write_text(json.dumps({"outputs": {"out": {"component": "out1", "keys": ["cc"]}}}))
    (gdir / "out_expected.csv").write_text(expected_csv_text)
    report_path = tmp_path / "report.json"
    return ["--job", str(job_path), "--golden-dir", str(gdir), "--out", str(report_path)], report_path


def test_cli_main_passes_on_matching_output(tmp_path):
    from agents.tools.run_and_validate import main
    argv, report_path = _write_cli_case(tmp_path, "cc;amt\nUS;10\nUK;20\n")
    rc = main(argv)
    assert rc == 0
    assert json.loads(report_path.read_text())["passed"] is True


def test_cli_main_fails_on_mutated_expected(tmp_path):
    from agents.tools.run_and_validate import main
    # US amt mutated 10 -> 999: parses cleanly (return 1 is a DIFF fail, not a load error).
    argv, report_path = _write_cli_case(tmp_path, "cc;amt\nUS;999\nUK;20\n")
    rc = main(argv)
    assert rc == 1
    assert json.loads(report_path.read_text())["passed"] is False


def test_cli_empty_outputs_returns_two(tmp_path):
    from agents.tools.run_and_validate import main
    job = tmp_path / "job.json"; job.write_text('{"components": [], "flows": []}')
    gdir = tmp_path / "g"; gdir.mkdir()
    (gdir / "manifest.json").write_text('{"outputs": {}}')
    report_path = tmp_path / "report.json"
    rc = main(["--job", str(job), "--golden-dir", str(gdir), "--out", str(report_path)])
    assert rc == 2
    rep = json.loads(report_path.read_text())
    assert rep["passed"] is False
    assert "no outputs" in rep["error"]
