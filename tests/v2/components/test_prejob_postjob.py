"""Prejob and postjob: where a job's set-up and its clean-up start."""
import pytest

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import flow, job, reader, writer

from .test_file_actions_kit import action, filled, on_v2, tree


def edged(pre="Prejob", post="Postjob", **config):
    """before: a file `started` is made. the job: in.csv is written to out.csv. after: a file `ended` is made."""
    components = [
        reader("id:int, name:str", outputs=("row2",)), writer("id:int, name:str"),
        action("post", post, **config), action("ended", "FileTouch", filename="ended"),
        action("pre", pre, **config), action("started", "FileTouch", filename="started"),
    ]
    made = job(components, [flow("row2", "in", "out")])
    made["triggers"] = [{"type": "OnComponentOk", "from": "pre", "to": "started"},
                        {"type": "OnComponentOk", "from": "post", "to": "ended"}]
    return made


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


def test_set_up_the_job_and_clean_up_all_run(tmp_path):
    folder = filled(tmp_path, {"in.csv": b"1;a\n"})
    result = on_v2(edged(), folder)
    assert result.status == "success", result.error
    assert tree(folder) == {"ended": b"", "in.csv": b"1;a\n", "out.csv": b"id;name\n1;a\n", "started": b""}


def test_clean_up_runs_when_the_job_failed(tmp_path):
    made = edged()
    made["components"][0]["config"]["die_on_error"] = True
    folder = filled(tmp_path, {"other.csv": b"x"})
    result = on_v2(made, folder)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert tree(folder) == {"ended": b"", "other.csv": b"x", "started": b""}


def test_job_is_not_run_when_its_set_up_failed(tmp_path):
    made = edged()
    # The set-up is to make a file in a folder that is not there.
    made["components"][5]["config"]["filename"] = "nowhere/started"
    folder = filled(tmp_path, {"in.csv": b"1;a\n"})
    result = on_v2(made, folder)
    assert (result.status, result.failed_component) == ("failed", "started")
    assert tree(folder) == {"ended": b"", "in.csv": b"1;a\n"}


def test_marks_count_no_row_and_leave_nothing(tmp_path):
    result = on_v2(dict(edged(), run={"row_counts": True}), filled(tmp_path, {"in.csv": b"1;a\n"}))
    assert result.counts["pre"] == result.counts["post"] == {"NB_LINE": 0, "NB_LINE_OK": 0, "NB_LINE_REJECT": 0}
    assert not [key for key in result.global_map if key.startswith(("pre_", "post_")) and "NB_LINE" not in key]


def test_flow_to_one_or_from_one_refuses_the_job():
    made = job([reader("id:int"), dict(action("pre", "Prejob"), inputs=["row1"])], [flow("row1", "in", "pre")])
    assert refusals(made) == [("inputs", "takes no input, but 1 flow arrives")]
    made = job([dict(action("post", "Postjob"), outputs=["row2"]), writer("id:int")], [flow("row2", "post", "out")])
    assert [key for key, _ in refusals(made)] == ["flows[0].type"]


def test_what_the_converter_writes_is_taken(tmp_path):
    made = edged(pre="tPrejob", post="tPostjob", tstatcatcher_stats=False, label="x")
    assert on_v2(made, filled(tmp_path, {"in.csv": b"1;a\n"})).status == "success"


@pytest.mark.parametrize("pre, post", [("prejob", "postjob"), ("Prejob", "Postjob"), ("tPrejob", "tPostjob")])
def test_every_name_of_them(tmp_path, pre, post):
    folder = filled(tmp_path, {"in.csv": b"1;a\n"})
    assert on_v2(edged(pre, post), folder).status == "success"
    assert sorted(path.name for path in folder.iterdir()) == ["ended", "in.csv", "out.csv", "started"]
