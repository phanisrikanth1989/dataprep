"""The answer-key harness itself, proven with v1 and with stand-ins for v2."""
import copy
import json
import os
from pathlib import Path

import pytest

from tests.v2 import answer_key
from tests.v2.answer_key import JobRun, assert_matches_v1, differences, run_job, run_v1

HERE = Path(__file__).parent
REPO = HERE.parents[2]
EMPLOYEES = REPO / "tests" / "v1" / "engine" / "fixtures" / "data" / "employees.csv"
JOB = json.loads((HERE / "first_slice.json").read_text())
INPUTS = {"employees.csv": EMPLOYEES}

HEADER = b"id;first_name;last_name;department;salary;country_code\n"
# salary >= 70000, then department ascending and salary descending.
EXPECTED = (
    HEADER
    + b"3;Pierre;Dupont;Engineering;90000;FR\n"
    + b"1;John;Smith;Engineering;85000;US\n"
    + b"5;Maria;Garcia;Engineering;78000;ES\n"
    + b"6;Yuki;Tanaka;Marketing;72000;JP\n"
    + b"7;Li;Wei;Sales;95000;CN\n"
)


def _run(files, succeeded=True, error=""):
    return JobRun(succeeded=succeeded, error=error, files=files, folder=Path("."))


# ------------------------------------------------------------------
# Running a job in its own folder
# ------------------------------------------------------------------

def test_v1_run_reports_only_the_file_the_job_wrote(tmp_path):
    run = run_job(JOB, INPUTS, tmp_path / "v1", run_v1)
    assert run.succeeded
    assert run.error == ""
    assert run.files == {"out/result.csv": EXPECTED}


def test_input_given_as_bytes_is_written_into_the_folder(tmp_path):
    inputs = {"employees.csv": HEADER + b"9;Ada;Byron;Ops;99000;IN\n"}
    run = run_job(JOB, inputs, tmp_path / "v1", run_v1)
    assert run.files == {"out/result.csv": HEADER + b"9;Ada;Byron;Ops;99000;IN\n"}


def test_input_the_job_changes_counts_as_written(tmp_path):
    def rewrite_input(job):
        Path("employees.csv").write_bytes(b"changed")

    run = run_job(JOB, INPUTS, tmp_path / "x", rewrite_input)
    assert run.files == {"employees.csv": b"changed"}


def test_job_that_does_not_finish_is_reported_not_raised(tmp_path):
    run = run_job(JOB, {}, tmp_path / "v1", run_v1)
    assert not run.succeeded
    assert run.error != ""


def test_working_directory_is_restored_when_the_runner_raises(tmp_path):
    def explode(job):
        raise RuntimeError("boom")

    before = os.getcwd()
    run = run_job(JOB, INPUTS, tmp_path / "x", explode)
    assert os.getcwd() == before
    assert not run.succeeded
    assert "boom" in run.error


def test_runner_cannot_change_the_callers_job(tmp_path):
    pristine = copy.deepcopy(JOB)

    def meddle(job):
        job["components"].clear()

    run_job(JOB, INPUTS, tmp_path / "x", meddle)
    assert JOB == pristine


# ------------------------------------------------------------------
# Comparing two runs
# ------------------------------------------------------------------

def test_identical_runs_have_no_differences():
    assert differences(_run({"a.csv": b"1\n"}), _run({"a.csv": b"1\n"})) == []


def test_different_bytes_name_the_file_the_line_and_both_lines():
    found = differences(
        _run({"a.csv": b"id\n1\n2\n"}),
        _run({"a.csv": b"id\n1\r\n2\n"}),
    )
    assert len(found) == 1
    assert "a.csv" in found[0]
    assert "line 2" in found[0]
    assert repr(b"1\n") in found[0]
    assert repr(b"1\r\n") in found[0]


def test_shorter_file_is_reported_at_the_first_missing_line():
    found = differences(_run({"a.csv": b"id\n1\n"}), _run({"a.csv": b"id\n"}))
    assert "line 2" in found[0]
    assert "2 lines" in found[0] and "1 line" in found[0]


def test_file_only_v1_wrote_is_a_difference():
    found = differences(_run({"a.csv": b"1\n"}), _run({}))
    assert found == ["a.csv: v1 wrote it, v2 did not"]


def test_file_only_v2_wrote_is_a_difference():
    found = differences(_run({}), _run({"b.csv": b"1\n"}))
    assert found == ["b.csv: v2 wrote it, v1 did not"]


def test_v2_not_finishing_when_v1_did_is_a_difference():
    found = differences(_run({"a.csv": b"1\n"}), _run({}, succeeded=False, error="no such file"))
    assert found == ["v1 finished, v2 did not: no such file"]


def test_v2_finishing_when_v1_did_not_is_a_difference():
    found = differences(_run({}, succeeded=False, error="bad cast"), _run({"a.csv": b"1\n"}))
    assert found == ["v1 did not finish (bad cast), v2 did"]


def test_files_are_not_compared_when_neither_engine_finishes():
    v1 = _run({"half.csv": b"1\n"}, succeeded=False, error="x")
    v2 = _run({}, succeeded=False, error="y")
    assert differences(v1, v2) == []


# ------------------------------------------------------------------
# assert_matches_v1
# ------------------------------------------------------------------

def test_v1_standing_in_for_v2_matches(tmp_path):
    run = assert_matches_v1(JOB, INPUTS, tmp_path, run_v2=run_v1)
    assert run.files == {"out/result.csv": EXPECTED}


def test_v2_that_writes_other_bytes_fails_naming_the_file(tmp_path):
    def wrong(job):
        Path("out").mkdir()
        Path("out/result.csv").write_bytes(EXPECTED.replace(b"90000", b"90000.0"))

    with pytest.raises(AssertionError, match="out/result.csv"):
        assert_matches_v1(JOB, INPUTS, tmp_path, run_v2=wrong)


def test_v2_that_raises_fails(tmp_path):
    def explode(job):
        raise RuntimeError("v2 broke")

    with pytest.raises(AssertionError, match="v2 broke"):
        assert_matches_v1(JOB, INPUTS, tmp_path, run_v2=explode)


def test_v2_runs_its_own_job_config_when_one_is_given(tmp_path):
    stricter = copy.deepcopy(JOB)
    stricter["components"][1]["config"]["conditions"][0]["value"] = "90000"
    with pytest.raises(AssertionError, match="out/result.csv"):
        assert_matches_v1(JOB, INPUTS, tmp_path, v2_job=stricter, run_v2=run_v1)


def test_job_needing_the_java_bridge_is_skipped_on_a_machine_without_one(tmp_path, monkeypatch):
    monkeypatch.setattr(answer_key, "bridge_available", lambda: False)
    java_job = copy.deepcopy(JOB)
    java_job["components"][1]["config"]["advanced_cond"] = "{{java}}input_row.salary > 1"
    with pytest.raises(pytest.skip.Exception):
        assert_matches_v1(java_job, INPUTS, tmp_path, run_v2=run_v1)


def test_java_free_job_runs_on_a_machine_without_a_bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(answer_key, "bridge_available", lambda: False)
    assert_matches_v1(JOB, INPUTS, tmp_path, run_v2=run_v1)
