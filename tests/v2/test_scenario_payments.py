"""The payments scenario at a tiny size: every variant writes the same files.

The scenario itself (scenarios/payments) is timed at millions of rows. This
keeps it honest at a size a test can afford: the job runs on v2, on v1 with
its PyMap, and on v1 with a tMap of Java expressions, and the files the
three leave behind are compared byte for byte.
"""
import pytest

from scenarios.payments import data, jobs
from src.v2 import run_job
from tests.v2.answer_key import bridge_available, run_v1

ROWS = 4000
KINDS = [number % 100 for number in range(ROWS)]
# What the generator plants: bad formats, a branch nobody knows, a reference used twice.
BAD_FORMAT = sum(kind in (7, 23) for kind in KINDS)
UNKNOWN_BRANCH = KINDS.count(41)
REPEATED = KINDS.count(57)


@pytest.fixture(scope="module")
def work(tmp_path_factory):
    folder = tmp_path_factory.mktemp("payments")
    data.generate(folder / "data", ROWS)
    return folder


def written(folder):
    return {path.name: path.read_bytes() for path in sorted(folder.iterdir())}


def rows(content):
    """The data rows of a written file: its lines less the header."""
    return len(content.splitlines()) - 1


@pytest.fixture(scope="module")
def on_v2(work):
    out = work / "v2"
    out.mkdir()
    result = run_job(jobs.build("python", work / "data", out))
    assert result.status == "success", result.error
    return written(out)


@pytest.fixture(scope="module")
def v1_pymap(work):
    """v1 with its PyMap, run once: the files it wrote and the row counts it kept."""
    out = work / "v1_pymap"
    out.mkdir()
    counts = run_v1(jobs.build("python", work / "data", out))
    return written(out), counts


@pytest.fixture(scope="module")
def on_v1_pymap(v1_pymap):
    return v1_pymap[0]


@pytest.fixture(scope="module")
def v2_counted(work):
    """v2 asked for row counts: the files it wrote and the counts."""
    out = work / "v2_counted"
    out.mkdir()
    result = run_job(jobs.build("python", work / "data", out), row_counts=True)
    assert result.status == "success", result.error
    return written(out), result.counts


@pytest.fixture(scope="module")
def on_v1_tmap(work):
    if not bridge_available():
        pytest.skip("the Java bridge is not available")
    out = work / "v1_tmap"
    out.mkdir()
    run_v1(jobs.build("java", work / "data", out))
    return written(out)


def differing(ours, theirs):
    """The files two runs do not agree on, by name."""
    return sorted(name for name in set(ours) | set(theirs) if ours.get(name) != theirs.get(name))


def test_v2_writes_every_file_of_the_job(on_v2):
    assert sorted(on_v2) == sorted(jobs.OUTPUTS)


def test_each_step_keeps_and_turns_away_the_rows_it_should(on_v2):
    assert rows(on_v2["format_rejects.csv"]) == BAD_FORMAT
    assert rows(on_v2["unknown_branch.csv"]) == UNKNOWN_BRANCH
    assert rows(on_v2["enriched.csv"]) == ROWS - BAD_FORMAT - UNKNOWN_BRANCH - REPEATED
    assert 0 < rows(on_v2["high_value.csv"]) < rows(on_v2["cross_border.csv"]) < rows(on_v2["enriched.csv"])
    assert rows(on_v2["summary.csv"]) > 0 and rows(on_v2["reject_report.csv"]) > 0


def test_v1_with_pymap_writes_the_same_files_as_v2(on_v2, on_v1_pymap):
    assert differing(on_v2, on_v1_pymap) == []


@pytest.mark.java
def test_v1_with_a_tmap_of_java_writes_the_same_files_as_v2(on_v2, on_v1_tmap):
    assert differing(on_v2, on_v1_tmap) == []


def test_row_counts_asked_for_are_v1s_for_every_component(v2_counted, v1_pymap):
    _, counts = v2_counted
    assert len(counts) == 24
    assert counts == v1_pymap[1]
    # Not a job where nothing is turned away: the counts that differ from one step to the next are in it.
    assert counts["format_check"]["NB_LINE_REJECT"] == BAD_FORMAT
    assert counts["branch_join"]["NB_LINE_REJECT"] == UNKNOWN_BRANCH
    assert counts["no_repeats"]["NB_LINE_REJECT"] == REPEATED


def test_asking_for_row_counts_changes_no_file(on_v2, v2_counted):
    assert differing(on_v2, v2_counted[0]) == []


def test_job_runs_the_same_at_the_debug_level(work, on_v2, caplog):
    # Every debug line is made inside the run: none of them may get in its way, for any component.
    import logging

    caplog.set_level(logging.DEBUG, logger="src.v2")
    out = work / "v2_debug"
    out.mkdir()
    result = run_job(jobs.build("python", work / "data", out), row_counts=True)
    assert result.status == "success", result.error
    assert differing(on_v2, written(out)) == []
    said = [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG]
    for component_id in result.counts:
        assert any(line.startswith(f"[{component_id}] config: ") for line in said), component_id
    assert [line for line in said if not line.isascii()] == []


# ------------------------------------------------------------------
# Two faults on one flow
# ------------------------------------------------------------------

def test_two_faults_put_into_the_job_are_reported_in_one_go(work):
    from src.v2 import JobRefusedError, load_job

    made = jobs.build("python", work / "data", work / "refused")
    by_id = {component["id"]: component for component in made["components"]}
    # The filter tests a column that is not there, and so does the map, five components further down.
    by_id["format_check"]["config"]["conditions"][0]["column"] = "debit_acount"
    column = next(column for column in by_id["prepare"]["config"]["outputs"][0]["columns"]
                  if "joined.amount" in column["expression"])
    column["expression"] = column["expression"].replace("joined.amount", "joined.amout")
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    report = caught.value.report
    assert [refusal.where.split()[1] for refusal in report] == ["format_check", "prepare"]
    assert "debit_acount" in report.refusals[0].reason and "amout" in report.refusals[1].reason
    assert "'format_check' declares" in report.refusals[1].reason


# ------------------------------------------------------------------
# The one command that times the variants
# ------------------------------------------------------------------

def timed(tmp_path, *arguments):
    import json

    from scenarios.payments import run

    code = run.main(["--rows", "2000", "--work", str(tmp_path), *arguments])
    report = json.loads((tmp_path / "results.json").read_text())
    return code, {entry["variant"]: entry for entry in report["runs"]}


def test_one_command_times_the_variants_and_checks_their_files(tmp_path):
    code, runs = timed(tmp_path, "--variants", "v2,v1-pymap", "--v2-runs", "2")
    assert code == 0
    assert runs["v2"]["status"] == "finished" and len(runs["v2"]["seconds"]) == 2
    assert runs["v1-pymap"]["status"] == "finished" and runs["v1-pymap"]["same_files_as_v2"] is True
    for run in runs.values():
        assert [stage["name"] for stage in run["stages"]] == [
            "start-up", "settings", "validate and enrich", "reject report",
        ]
        assert run["rows"] == 2000 and run["peak_memory_gb"] > 0
        assert sum(stage["seconds"] for stage in run["stages"]) <= run["reported_seconds"] + 0.5


def test_v1_run_that_passes_the_cap_is_stopped_and_said_to_be(tmp_path):
    code, runs = timed(tmp_path, "--variants", "v1-pymap", "--v1-cap", "1")
    assert code == 1
    assert runs["v1-pymap"]["status"] == "stopped at the cap"
    assert 1 <= runs["v1-pymap"]["reported_seconds"] < 4


def test_data_script_runs_on_its_own(tmp_path):
    # Handed to someone without the repository, the one file must be enough to make the inputs.
    import subprocess
    import sys
    from pathlib import Path

    script = Path(data.__file__)
    done = subprocess.run([sys.executable, str(script), "--rows", "50", "--out", "inputs"],
                          cwd=tmp_path, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    made = tmp_path / "inputs"
    assert sorted(path.name for path in made.iterdir()) == [
        "branches.csv", "customers.csv", "payments.csv", "purposes.csv", "settings.csv",
    ]
    assert len((made / "payments.csv").read_text().splitlines()) == 51
    assert "50" in done.stdout and "payments.csv" in done.stdout


def test_data_script_refuses_a_row_count_below_one(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    done = subprocess.run([sys.executable, str(Path(data.__file__)), "--rows", "0", "--out", "inputs"],
                          cwd=tmp_path, capture_output=True, text=True)
    assert done.returncode == 2 and "at least 1" in done.stderr
    assert not (tmp_path / "inputs").exists()
