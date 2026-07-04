"""Tests for the parity-harness engine-run capture (Task 4).

Uses a bridge-free FileInputDelimited -> FileOutputDelimited passthrough job
(no tMap, no {{java}}), so no JVM is required.

Job-shape note:
    The engine reads component schemas as ``schema['output']`` /
    ``schema['input']`` (see engine.py:205-206), routes data through *named*
    flows whose ``type`` maps to a result key (``flow`` -> ``main``; see
    output_router.py:22-23 and the hard ``flow['name']`` lookup at line 75),
    and builds subjobs from each component's ``subjob_id`` field
    (engine.py:251-260). A flat-list ``schema`` or a nameless ``type:"main"``
    flow does NOT run on the real engine, so _passthrough_job uses the proven
    dict-config shape from tests/v1/engine/test_full_pipeline.py. The RunResult
    behaviour under test (output file captured into ``outputs[id]``; an
    unknown-type component surfaced in ``dropped_components``) is unchanged.
"""
import uuid
from pathlib import Path

import pandas as pd

from agents.tools.run_and_validate import RunResult, run_job_capture


def _passthrough_job(in_csv, out_csv):
    return {
        "job_name": "passthrough",
        "components": [
            {"id": "in1", "type": "FileInputDelimited",
             "config": {"filepath": str(in_csv), "fieldseparator": ",", "header_rows": 1,
                        "die_on_error": False},
             "inputs": [], "outputs": ["f1"],
             "schema": {"input": [], "output": [
                 {"name": "cc", "type": "str", "nullable": True, "key": False},
                 {"name": "amt", "type": "str", "nullable": True, "key": False}]},
             "subjob_id": "subjob_1", "is_subjob_start": True},
            {"id": "out1", "type": "FileOutputDelimited",
             "config": {"filepath": str(out_csv), "fieldseparator": ",", "include_header": True,
                        "file_exist_exception": False, "create_directory": True},
             "inputs": ["f1"], "outputs": [],
             "schema": {"input": [
                 {"name": "cc", "type": "str", "nullable": True, "key": False},
                 {"name": "amt", "type": "str", "nullable": True, "key": False}], "output": []},
             "subjob_id": "subjob_1", "is_subjob_start": False},
        ],
        "flows": [{"name": "f1", "from": "in1", "to": "out1", "type": "flow"}],
    }


def test_capture_reads_output_file_and_stats(tmp_path):
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\nUK,20\n")
    out_csv = tmp_path / "out.csv"
    rr = run_job_capture(_passthrough_job(in_csv, out_csv), tmp_path)
    assert isinstance(rr, RunResult)
    assert rr.status == "success"
    assert rr.dropped_components == []
    assert set(rr.outputs["out1"]["cc"]) == {"US", "UK"}


def test_capture_detects_dropped_unknown_component(tmp_path):
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\n")
    job = _passthrough_job(in_csv, tmp_path / "out.csv")
    job["components"].append({"id": "ghost", "type": "tNotARealComponent", "config": {}, "schema": []})
    rr = run_job_capture(job, tmp_path)
    assert "ghost" in rr.dropped_components


def test_dropped_is_by_unregistered_type_not_missing_stats():
    from agents.tools.run_and_validate import _dropped_components
    comps = [
        {"id": "a", "type": "FileInputDelimited"},        # registered -> NOT dropped
        {"id": "b", "type": "FilterRows"},                # registered -> NOT dropped
        {"id": "ghost", "type": "tNotARealComponent"},    # unregistered -> dropped
    ]
    assert _dropped_components(comps) == ["ghost"]


# ---------------------------------------------------------------------------
# I3: FileOutput filepaths are jailed to work_dir. A path that resolves OUTSIDE
# work_dir (absolute-outside, '..'-escape, or symlink-escape) is refused BEFORE
# the engine runs, so nothing is ever written outside the jail.
# ---------------------------------------------------------------------------
def test_capture_rejects_output_escaping_work_dir(tmp_path):
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\n")
    escape = Path("/tmp") / f"escape_{uuid.uuid4().hex}.csv"  # absolute, outside tmp_path
    assert not escape.exists()
    rr = run_job_capture(_passthrough_job(in_csv, escape), tmp_path)
    assert rr.status == "error"
    assert "escapes" in (rr.error or "")
    assert not escape.exists()  # jail refused the run: nothing written outside work_dir


def test_capture_rejects_dotdot_output_escape(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    in_csv = work / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\n")
    escape = work / ".." / f"escape_{uuid.uuid4().hex}.csv"  # '..' climbs out of work
    landing = Path(escape).resolve()
    assert not landing.exists()
    rr = run_job_capture(_passthrough_job(in_csv, escape), work)
    assert rr.status == "error"
    assert "escapes" in (rr.error or "")
    assert not landing.exists()


def test_capture_allows_output_inside_work_dir(tmp_path):
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\nUK,20\n")
    out_csv = tmp_path / "out.csv"  # inside the jail
    rr = run_job_capture(_passthrough_job(in_csv, out_csv), tmp_path)
    assert rr.status == "success"
    assert set(rr.outputs["out1"]["cc"]) == {"US", "UK"}


# ---------------------------------------------------------------------------
# I1: RELATIVE paths are anchored to work_dir, NOT the process CWD. The skill
# teaches relative paths; the CLI runs from the workspace root (CWD != work_dir).
# A correct job with a relative input+output must therefore run under work_dir.
# ---------------------------------------------------------------------------
def _strict_passthrough_job(in_path, out_path):
    """Passthrough whose output OMITS file_exist_exception (engine default True),
    so a naive re-run over an existing output would raise -- the harness must
    pre-delete declared outputs to stay idempotent (I2)."""
    job = _passthrough_job(in_path, out_path)
    job["components"][1]["config"].pop("file_exist_exception", None)
    return job


def test_relative_paths_anchored_to_work_dir_not_cwd(tmp_path):
    (tmp_path / "in.csv").write_text("cc,amt\nUS,10\nUK,20\n")
    # RELATIVE input+output. CWD is the repo root (pytest never chdirs into
    # tmp_path), proving CWD != work_dir.
    assert Path.cwd() != tmp_path
    rr = run_job_capture(_passthrough_job("in.csv", "out.csv"), tmp_path)
    assert rr.status == "success", rr.error
    assert (tmp_path / "out.csv").exists()  # written UNDER work_dir, not CWD
    assert set(rr.outputs["out1"]["cc"]) == {"US", "UK"}


# ---------------------------------------------------------------------------
# I2: FileOutputDelimited defaults file_exist_exception=True; a re-run over an
# existing output raises -> engine status "failed". The harness pre-deletes the
# declared outputs under work_dir so a re-run starts clean and stays green.
# ---------------------------------------------------------------------------
def test_rerun_over_existing_output_is_idempotent(tmp_path):
    (tmp_path / "in.csv").write_text("cc,amt\nUS,10\n")
    job = _strict_passthrough_job("in.csv", "out.csv")
    rr1 = run_job_capture(job, tmp_path)
    assert rr1.status == "success", rr1.error
    assert (tmp_path / "out.csv").exists()
    rr2 = run_job_capture(job, tmp_path)  # output now already exists
    assert rr2.status == "success", rr2.error


# ---------------------------------------------------------------------------
# C1: the jail is default-deny across ALL writers, not a FileOutput-only
# allowlist. A non-FileOutput writer (FileCopy) writing to an ABSOLUTE path
# outside work_dir is refused before the engine runs; a relative one under
# work_dir is anchored and allowed.
# ---------------------------------------------------------------------------
def _filecopy_job(source, destination):
    return {
        "job_name": "copyjob",
        "components": [
            {"id": "cp1", "type": "FileCopy",
             "config": {"filename": str(source), "destination": str(destination),
                        "replace_file": True, "create_directory": False},
             "inputs": [], "outputs": [], "schema": {"input": [], "output": []},
             "subjob_id": "sj1", "is_subjob_start": True},
        ],
        "flows": [],
    }


def test_rejects_non_fileoutput_writer_escaping_absolute_path(tmp_path):
    (tmp_path / "src.txt").write_text("hello", encoding="utf-8")
    escape = Path("/tmp") / f"escape_{uuid.uuid4().hex}.txt"  # absolute, outside tmp_path
    assert not escape.exists()
    rr = run_job_capture(_filecopy_job("src.txt", escape), tmp_path)
    assert rr.status == "error"
    assert "escapes" in (rr.error or "")
    assert not escape.exists()  # jail refused the run: nothing written outside work_dir


def test_allows_relative_non_fileoutput_writer_under_work_dir(tmp_path):
    (tmp_path / "src.txt").write_text("hello", encoding="utf-8")
    rr = run_job_capture(_filecopy_job("src.txt", "dst.txt"), tmp_path)  # both relative
    assert rr.status == "success", rr.error
    assert (tmp_path / "dst.txt").read_text(encoding="utf-8") == "hello"


def test_default_deny_catches_escape_in_unmanifested_key(tmp_path):
    # C1 completeness: an absolute path outside work_dir living in a config key that
    # is NOT in _PATH_CONFIG_KEYS is still refused by the recursive default-deny scan
    # -- the jail is not limited to the known path keys.
    escape = Path("/tmp") / f"escape_{uuid.uuid4().hex}"
    job = {
        "job_name": "j",
        "components": [
            {"id": "x", "type": "FilterRows",
             "config": {"some_unmapped_path": str(escape)},  # not a manifest key
             "inputs": [], "outputs": [], "schema": {"input": [], "output": []},
             "subjob_id": "sj1", "is_subjob_start": True},
        ],
        "flows": [],
    }
    rr = run_job_capture(job, tmp_path)
    assert rr.status == "error"
    assert "escapes" in (rr.error or "")
