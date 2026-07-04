import json

import pandas as pd

from agents.tools.run_and_validate import RunResult, check, diff_frames


def test_diff_keyed_detects_missing_and_mismatch():
    exp = pd.DataFrame({"cc": ["US", "UK"], "name": ["A", "B"]})
    act = pd.DataFrame({"cc": ["US"], "name": ["X"]})
    d = diff_frames(act, exp, keys=["cc"])
    assert d["missing"] == 1  # UK absent from actual
    assert d["value_mismatch"] == 1  # US name X != A


def test_diff_none_actual_is_not_equal():
    # No actual output produced (e.g. output file never written) -> never equal.
    d = diff_frames(None, pd.DataFrame({"cc": ["US"]}), keys=["cc"])
    assert d["equal"] is False


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


def test_check_fails_on_engine_status_failed():
    # Output MATCHES, but the engine status is not "success" -> must still FAIL.
    exp = {"matched": pd.DataFrame({"cc": ["US"]})}
    rr = _rr({"out1": pd.DataFrame({"cc": ["US"]})}, status="failed")
    rep = check(rr, exp, output_map={"matched": "out1"}, keys={"matched": ["cc"]})
    assert rep["passed"] is False and any("status" in r for r in rep["reasons"])


def test_check_fails_on_component_error():
    # Output MATCHES, but a component errored -> must still FAIL.
    exp = {"matched": pd.DataFrame({"cc": ["US"]})}
    rr = _rr({"out1": pd.DataFrame({"cc": ["US"]})}, comp_err=True)
    rep = check(rr, exp, output_map={"matched": "out1"}, keys={"matched": ["cc"]})
    assert rep["passed"] is False and any("error" in r.lower() for r in rep["reasons"])


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


# ---------------------------------------------------------------------------
# I-a: FileOutputDelimited defaults include_header=False (engine default). The
# readback must honor that: a headerless output's first line is DATA, not column
# names, so it is read with header=None and columns ASSIGNED from the sink's
# declared INPUT schema (a FileOutput writes its input columns). Reading it with
# pandas' default header=0 would eat the first data row and mislabel the columns.
# ---------------------------------------------------------------------------
def test_read_output_headerless_uses_schema_names(tmp_path):
    from agents.tools.run_and_validate import _read_output
    (tmp_path / 'o.csv').write_text('US;10\nUK;20\n')   # headerless, ; sep
    comp = {'id': 'o', 'type': 'FileOutputDelimited',
            'config': {'filepath': str(tmp_path / 'o.csv'), 'fieldseparator': ';', 'include_header': False},
            'schema': {'input': [{'name': 'cc'}, {'name': 'amt'}], 'output': []}}
    df = _read_output(comp)
    assert list(df.columns) == ['cc', 'amt'] and len(df) == 2 and set(df['cc']) == {'US', 'UK'}


def test_read_output_header_true_still_reads_header_row(tmp_path):
    # include_header=True keeps the current header=0 behavior: the first line names
    # the columns and is NOT counted as a data row.
    from agents.tools.run_and_validate import _read_output
    (tmp_path / 'o.csv').write_text('cc;amt\nUS;10\nUK;20\n')
    comp = {'id': 'o', 'type': 'FileOutputDelimited',
            'config': {'filepath': str(tmp_path / 'o.csv'), 'fieldseparator': ';', 'include_header': True},
            'schema': {'input': [{'name': 'cc'}, {'name': 'amt'}], 'output': []}}
    df = _read_output(comp)
    assert list(df.columns) == ['cc', 'amt'] and len(df) == 2 and set(df['cc']) == {'US', 'UK'}


def test_read_output_headerless_no_schema_falls_back_to_int_columns(tmp_path):
    # No declared input schema -> header=None with pandas' default integer columns,
    # still keeping every data row (no row consumed as a header).
    from agents.tools.run_and_validate import _read_output
    (tmp_path / 'o.csv').write_text('US;10\nUK;20\n')
    comp = {'id': 'o', 'type': 'FileOutputDelimited',
            'config': {'filepath': str(tmp_path / 'o.csv'), 'fieldseparator': ';', 'include_header': False},
            'schema': {'input': [], 'output': []}}
    df = _read_output(comp)
    assert len(df) == 2 and set(df.iloc[:, 0]) == {'US', 'UK'}


# ---------------------------------------------------------------------------
# #10: JSON configs may carry booleans as the STRINGS "true"/"false", and Python's
# bool("false") is True -- so _read_output must coerce include_header the same way
# the engine does. A string "false" is headerless (columns from schema.input, every
# data row kept); a string "true" is headed. Mirrors the bool-valued tests above.
# ---------------------------------------------------------------------------
def test_read_output_string_false_is_headerless(tmp_path):
    from agents.tools.run_and_validate import _read_output
    (tmp_path / 'o.csv').write_text('US;10\nUK;20\n')   # headerless
    comp = {'id': 'o', 'type': 'FileOutputDelimited',
            'config': {'filepath': str(tmp_path / 'o.csv'), 'fieldseparator': ';',
                       'include_header': 'false'},   # STRING, not bool
            'schema': {'input': [{'name': 'cc'}, {'name': 'amt'}], 'output': []}}
    df = _read_output(comp)
    assert list(df.columns) == ['cc', 'amt'] and len(df) == 2 and set(df['cc']) == {'US', 'UK'}


def test_read_output_string_true_is_headed(tmp_path):
    from agents.tools.run_and_validate import _read_output
    (tmp_path / 'o.csv').write_text('cc;amt\nUS;10\nUK;20\n')   # first line is header
    comp = {'id': 'o', 'type': 'FileOutputDelimited',
            'config': {'filepath': str(tmp_path / 'o.csv'), 'fieldseparator': ';',
                       'include_header': 'true'},   # STRING, not bool
            'schema': {'input': [{'name': 'cc'}, {'name': 'amt'}], 'output': []}}
    df = _read_output(comp)
    assert list(df.columns) == ['cc', 'amt'] and len(df) == 2 and set(df['cc']) == {'US', 'UK'}


def test_diff_frames_missing_key_no_crash():
    import pandas as pd
    from agents.tools.run_and_validate import diff_frames
    d = diff_frames(pd.DataFrame({'wrong': ['x']}), pd.DataFrame({'cc': ['US']}), keys=['cc'])  # must NOT raise
    assert d['equal'] is False
    assert 'missing from actual output' in d.get('reason', '')


# ---------------------------------------------------------------------------
# #2/#9: only the delimited FileOutput family is read back. A declared output
# whose producing component is a registered but NON-delimited writer (Positional/
# Excel/XML) yields actual=None; check() must emit a clear "delimited only" reason
# instead of the generic "no actual output" diff.
# ---------------------------------------------------------------------------
def test_check_non_delimited_output_gives_clear_reason():
    exp = {"sheet": pd.DataFrame({"cc": ["US"]})}
    rr = _rr({})  # nothing harvested -> actual is None
    rep = check(rr, exp, output_map={"sheet": "xls1"}, keys={"sheet": ["cc"]},
                output_types={"xls1": "FileOutputExcel"})
    assert rep["passed"] is False
    assert any("delimited only" in r for r in rep["reasons"])


# ---------------------------------------------------------------------------
# #6: check() with ZERO expected outputs must NOT report PASS (hollow oracle). A
# run that produced/expected nothing verified nothing -- an empty ``expected``
# would otherwise iterate zero diffs and fall through to passed=True.
# ---------------------------------------------------------------------------
def test_check_zero_expected_outputs_is_not_pass():
    rr = _rr({})  # clean engine run, but nothing to verify
    rep = check(rr, expected={}, output_map={}, keys={})
    assert rep["passed"] is False
    assert any("no outputs to verify" in r for r in rep["reasons"])
