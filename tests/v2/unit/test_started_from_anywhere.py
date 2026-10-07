"""Starting the engine from any folder, and from a service.

The command is the engine's own path, so it needs no installing and no
particular folder to start in:

    python /opt/dataprep/src/v2 /data/jobs/pay.json

A service calls ``run_job`` with what a request holds: the job config, the
context values that override its own, and the run settings.
"""
import json
import os
import runpy
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from src.v2 import run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import flow, job, reader, writer

REPO = Path(__file__).parents[3]
ENGINE = REPO / "src" / "v2"
IDS = "id:int, amount:int"


def job_at(folder, **more):
    """file -> file with full paths, written to job.json in a folder. Returns the path of the job file."""
    (folder / "in.csv").write_bytes(b"id;amount\n1;10\n2;20\n")
    made = job([reader(IDS, path=str(folder / "in.csv"), header_rows=1),
                writer(IDS, path=str(folder / "out.csv"), inputs=("row1",))], [flow("row1", "in", "out")], **more)
    (folder / "job.json").write_text(json.dumps(made))
    return str(folder / "job.json")


def started(command, folder):
    """Run a command in a folder, with nothing in the environment that tells Python where the project is."""
    env = {name: value for name, value in os.environ.items() if name != "PYTHONPATH"}
    return subprocess.run(command, cwd=folder, env=env, capture_output=True, text=True)


# ------------------------------------------------------------------
# By the engine's path, from any folder
# ------------------------------------------------------------------

@pytest.mark.parametrize("engine", [ENGINE, ENGINE / "__main__.py"], ids=["the folder", "its __main__.py"])
def test_engine_started_by_its_path_runs_a_job_from_another_folder(tmp_path, engine):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    done = started([sys.executable, str(engine), job_at(tmp_path)], elsewhere)
    assert done.returncode == 0, done.stderr
    assert (tmp_path / "out.csv").read_bytes() == b"id;amount\n1;10\n2;20\n"
    assert json.loads(done.stdout[done.stdout.index("\n{"):])["status"] == "success"


def test_engine_started_as_a_module_from_the_projects_folder_still_runs(tmp_path):
    done = started([sys.executable, "-m", "src.v2", job_at(tmp_path)], REPO)
    assert done.returncode == 0, done.stderr


def test_started_by_its_path_the_engines_own_files_are_not_taken_for_the_standard_librarys(tmp_path, monkeypatch):
    # The engine's folder holds a types.py. Run in this process, as `python <path>` runs it: afterwards
    # Python must look for modules in the project's folder and no longer in the engine's.
    monkeypatch.setattr(sys, "argv", [str(ENGINE), job_at(tmp_path)])
    monkeypatch.setattr(sys, "path", [str(ENGINE)] + [entry for entry in sys.path if entry != str(REPO)])
    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(ENGINE), run_name="__main__")
    assert stopped.value.code == 0
    assert sys.path[0] == str(REPO) and str(ENGINE) not in sys.path


# ------------------------------------------------------------------
# From a service
# ------------------------------------------------------------------

def test_request_as_a_service_holds_it_runs_in_a_thread_of_its_own(tmp_path):
    # As api/routes/jobs.py runs v1: the job config as a dict, the context overrides as text, in a
    # background thread; and with them the run settings of the request.
    (tmp_path / "in.csv").write_bytes(b"id;amount\n1;10\n2;20\n")
    request = {
        "job_config": job(
            [reader(IDS, path="${context.folder}/in.csv", header_rows=1),
             writer(IDS, path="${context.folder}/out.csv", inputs=("row1",))],
            [flow("row1", "in", "out")],
            context={"Default": {"folder": {"value": "/nowhere", "type": "str"}}},
            run={"row_counts": False},
        ),
        "context_overrides": {"folder": str(tmp_path)},
        "run": {"row_counts": True},
    }
    runs = {}

    def in_background(run_id):
        result = run_job(request["job_config"], context=request["context_overrides"], run=request["run"])
        runs[run_id] = result.summary()

    thread = threading.Thread(target=in_background, args=("r1",), daemon=True)
    thread.start()
    thread.join()
    sent = json.loads(json.dumps(runs["r1"]))
    assert sent["status"] == "success" and sent["rows"] == {"out": 2}
    assert sent["counts"]["in"] == {"NB_LINE": 2, "NB_LINE_OK": 2, "NB_LINE_REJECT": 0}
    assert (tmp_path / "out.csv").read_bytes() == b"id;amount\n1;10\n2;20\n"


def test_request_with_a_run_setting_that_is_not_known_is_refused_before_anything_runs(tmp_path):
    made = json.loads(Path(job_at(tmp_path)).read_text())
    with pytest.raises(JobRefusedError) as caught:
        run_job(made, context={}, run={"row_count": True})
    assert "run.row_count" in caught.value.report.format() and "did you mean 'row_counts'" in caught.value.report.format()
    assert not (tmp_path / "out.csv").exists()
