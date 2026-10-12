"""File touch: a file is made, or the time it was changed is set to now."""
import logging
import os
import time

import pytest

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import flow, job, reader

from .test_file_actions_kit import action, filled, on_v2, tree

FILES = {"a.txt": b"kept", "dir/": None}
LONG_AGO = 1_000_000_000


def touch(kind="FileTouch", **config):
    return action("mark", kind, **config)


def ran(tmp_path, files=FILES, **config):
    folder = filled(tmp_path, files)
    for name in files:
        os.utime(folder / name, (LONG_AGO, LONG_AGO))
    return on_v2(job([touch(**config)], []), folder), folder


def test_file_that_is_not_there_is_made_empty(tmp_path):
    result, folder = ran(tmp_path, filename="new.txt")
    assert result.status == "success", result.error
    assert tree(folder) == {"a.txt": b"kept", "dir/": None, "new.txt": b""}


def test_file_that_is_there_keeps_what_it_holds_and_its_time_is_now(tmp_path):
    before = time.time() - 2
    result, folder = ran(tmp_path, filename="a.txt")
    assert result.status == "success", result.error
    assert (folder / "a.txt").read_bytes() == b"kept"
    assert os.stat(folder / "a.txt").st_mtime >= before


def test_folder_that_is_there_has_its_time_set_to_now(tmp_path):
    before = time.time() - 2
    result, folder = ran(tmp_path, filename="dir")
    assert result.status == "success", result.error
    assert (folder / "dir").is_dir() and os.stat(folder / "dir").st_mtime >= before


def test_missing_folder_fails_the_job_unless_it_is_to_be_made(tmp_path):
    result, folder = ran(tmp_path, filename="deep/er/new.txt")
    assert result.status == "failed"
    assert result.error == "the folder 'deep/er' is not there, and is not to be made"
    assert "deep/" not in tree(folder)


@pytest.mark.parametrize("key", ["createdir", "create_directory"])
def test_missing_folder_is_made_when_asked(tmp_path, key):
    result, folder = ran(tmp_path, filename="deep/er/new.txt", **{key: True})
    assert result.status == "success", result.error
    assert (folder / "deep/er/new.txt").read_bytes() == b""


def test_what_is_left_in_globalmap(tmp_path):
    made = dict(job([touch(filename="new.txt")], []), run={"row_counts": True})
    result = on_v2(made, filled(tmp_path, FILES))
    assert result.counts["mark"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}
    assert result.global_map["mark_FILENAME"] == "new.txt"


def test_file_that_cannot_be_made_fails_the_job_in_plain_words(tmp_path):
    result, _ = ran(tmp_path, filename="a.txt/under.txt")
    assert result.status == "failed"
    assert result.error == "'a.txt/under.txt' cannot be touched: not a directory"


def test_path_from_the_context(tmp_path):
    made = job([touch(filename="${context.dir}/new.txt")], [])
    made["context"] = {"Default": {"dir": {"value": "dir", "type": "str"}}}
    folder = filled(tmp_path, FILES)
    assert on_v2(made, folder).status == "success"
    assert (folder / "dir/new.txt").exists()


def test_what_the_converter_writes_is_taken(tmp_path):
    result, folder = ran(tmp_path, filename="new.txt", createdir=False, tstatcatcher_stats=False, label="")
    assert result.status == "success", result.error


@pytest.mark.parametrize("config, key", [({}, "filename"), ({"filename": ""}, "filename"), ({"filename": "a", "nope": 1}, "nope")])
def test_what_cannot_be_read_refuses_the_job(config, key):
    with pytest.raises(JobRefusedError) as refused:
        load_job(job([touch(**config)], []))
    assert [refusal.key for refusal in refused.value.report] == [key]


@pytest.mark.parametrize("kind", ["file_touch", "FileTouch", "tFileTouch"])
def test_every_name_of_it(tmp_path, kind):
    folder = filled(tmp_path, FILES)
    assert on_v2(job([touch(kind=kind, filename="new.txt")], []), folder).status == "success"
    assert (folder / "new.txt").exists()


def test_log_says_whether_the_file_was_made_or_was_there(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    ran(tmp_path / "one", filename="new.txt")
    ran(tmp_path / "two", filename="a.txt")
    said = [record.getMessage() for record in caplog.records if record.getMessage().startswith("[mark]")]
    assert said == ["[mark] made 'new.txt', an empty file", "[mark] 'a.txt' was there; its time is set to now"]


def test_name_that_ends_in_a_slash_is_a_folder_and_no_file_is_made_of_it(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    result, folder = ran(tmp_path, filename="fresh/", createdir=True)
    assert result.status == "success", result.error
    assert (folder / "fresh").is_dir()
    assert "[mark] made the folder 'fresh/'" in [record.getMessage() for record in caplog.records]
    result, _ = ran(tmp_path / "again", filename="fresh/")
    assert (result.status, result.error) == ("failed", "the folder 'fresh' is not there, and is not to be made")


def test_flow_to_it_refuses_the_job():
    step = dict(touch(filename="new.txt"), inputs=["row1"])
    with pytest.raises(JobRefusedError) as refused:
        load_job(job([reader("id:int"), step], [flow("row1", "in", "mark")]))
    assert [(refusal.where, refusal.key, refusal.reason) for refusal in refused.value.report] == [
        ("component mark (FileTouch)", "inputs", "takes no input, but 1 flow arrives")]


def test_link_to_nowhere_fails_the_job_and_nothing_is_made_through_it(tmp_path):
    folder = filled(tmp_path, FILES)
    os.symlink("elsewhere.txt", folder / "link.txt")
    result = on_v2(job([touch(filename="link.txt")], []), folder)
    assert (result.status, result.error) == ("failed", "'link.txt' cannot be touched: no such file or directory")
    assert not (folder / "elsewhere.txt").exists()


def test_link_to_a_file_sets_the_time_of_the_file(tmp_path):
    folder = filled(tmp_path, FILES)
    os.utime(folder / "a.txt", (LONG_AGO, LONG_AGO))
    os.symlink("a.txt", folder / "link.txt")
    before = time.time() - 2
    assert on_v2(job([touch(filename="link.txt")], []), folder).status == "success"
    assert os.stat(folder / "a.txt").st_mtime >= before and (folder / "a.txt").read_bytes() == b"kept"


def test_job_that_is_not_to_die_goes_on_and_says_why(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    folder = filled(tmp_path, FILES)
    made = dict(job([touch(filename="deep/new.txt", die_on_error=False)], []), run={"row_counts": True})
    result = on_v2(made, folder)
    assert result.status == "success", result.error
    assert result.global_map["mark_ERROR_MESSAGE"] == "the folder 'deep' is not there, and is not to be made"
    assert result.counts["mark"] == {"NB_LINE": 1, "NB_LINE_OK": 0, "NB_LINE_REJECT": 1}
    assert [record.getMessage() for record in caplog.records] == [
        "[mark] the folder 'deep' is not there, and is not to be made; the job goes on"]
    assert "mark_FILENAME" not in result.global_map and not (folder / "deep").exists()


def test_job_that_is_to_die_does(tmp_path):
    result, _ = ran(tmp_path, filename="deep/new.txt", die_on_error=True)
    assert result.status == "failed"
