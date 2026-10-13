"""File exist, against v1: what each engine leaves in globalMap."""
import pytest

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1
from tests.v2.components.kit import flow, job, reader, writer

from .test_file_actions_kit import action, both, filled, on_v2

FILES = {"a.txt": b"x", "dir/": None, "dir/b.txt": b"y"}


def exist(kind="FileExistComponent", **config):
    return action("look", kind, **config)


@pytest.mark.parametrize("config, there", [
    ({"file_name": "a.txt"}, True), ({"file_name": "nope.txt"}, False), ({"file_name": "dir"}, True),
    ({"file_name": "dir/b.txt"}, True), ({"file_name": "dir", "check_directory": True}, True),
    ({"file_name": "a.txt", "check_directory": True}, False), ({"file_name": "nope", "check_directory": True}, False),
    ({"file_path": "a.txt"}, True), ({"FILE_NAME": "a.txt"}, True),
])
def test_whether_it_is_there_is_left_in_globalmap(tmp_path, config, there):
    held, result = both(exist(**config), FILES, tmp_path)
    path = next(iter(value for key, value in config.items() if key != "check_directory"))
    assert result.global_map["look_EXISTS"] is there and held.get("look_EXISTS") is there
    assert result.global_map["look_FILENAME"] == path == held.get("look_FILENAME")


def test_it_counts_one_row_as_v1_counts(tmp_path):
    made = dict(job([exist(file_name="a.txt")], []), run={"row_counts": True})
    result = on_v2(made, filled(tmp_path, FILES))
    assert result.counts["look"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}


def test_trigger_reads_whether_it_is_there(tmp_path):
    copy = [reader("id:int", component_id="in"), writer("id:int", inputs=("row1",))]
    for name, runs in (("in.csv", True), ("nope.csv", False)):
        made = job([exist(file_name=name), *copy], [flow("row1", "in", "out")])
        made["triggers"] = [{"type": "RunIf", "from": "look", "to": "in", "condition": '((Boolean)globalMap.get("look_EXISTS"))'}]
        run = assert_matches_v1(made, {"in.csv": b"1\n"}, tmp_path / name)
        assert run.succeeded and ("out.csv" in run.files) is runs


def test_path_from_the_context(tmp_path):
    made = job([exist(file_name="${context.dir}/b.txt")], [])
    made["context"] = {"Default": {"dir": {"value": "dir", "type": "str"}}}
    assert on_v2(made, filled(tmp_path, FILES)).global_map["look_EXISTS"] is True


@pytest.mark.parametrize("config, key", [({}, "path"), ({"file_name": ""}, "path"), ({"file_name": "a", "nope": 1}, "nope")])
def test_what_cannot_be_read_refuses_the_job(config, key):
    with pytest.raises(JobRefusedError) as refused:
        load_job(job([exist(**config)], []))
    assert [refusal.key for refusal in refused.value.report] == [key]


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("file_exist", "FileExistComponent", "FileExist", "tFileExist")):
        result = on_v2(job([exist(kind=kind, file_name="a.txt")], []), filled(tmp_path / str(at), FILES))
        assert result.global_map["look_EXISTS"] is True


def test_link_to_nothing_is_not_there_and_a_tilde_is_no_home_folder(tmp_path):
    # Ticket 85.
    import os
    folder = filled(tmp_path, FILES)
    os.symlink("nowhere", folder / "broken")
    os.symlink("a.txt", folder / "good")
    assert on_v2(job([exist(file_name="broken")], []), folder).global_map["look_EXISTS"] is False
    assert on_v2(job([exist(file_name="good")], []), folder).global_map["look_EXISTS"] is True
    assert on_v2(job([exist(file_name="~")], []), folder).global_map["look_EXISTS"] is False
