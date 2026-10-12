"""File properties: one row that says what a file is, by the columns asked for."""
import hashlib
import logging
import os
import time

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, writer

from .test_file_actions_kit import filled, on_v2

LONG_AGO = 1_700_000_000
FILES = {"a.txt": b"hello", "dir/": None, "dir/b.txt": b"y"}
TALEND = "abs_path;dirname;basename;mode_string;size;mtime;mtime_string"


def properties(schema=None, out=None, kind="FileProperties", **config):
    """the properties of a file -> out.csv."""
    source = {"id": "in", "type": kind, "config": config, "inputs": [], "outputs": ["row1"],
              "schema": {"input": [], "output": columns(schema) if schema else []}}
    return job([source, writer(out or schema, inputs=("row1",))], [flow("row1", "in", "out")])


def ran(tmp_path, made, files=FILES):
    """Run in a folder of these files, each last changed long ago and open to its owner and group; returns
    how it ended, the lines of out.csv and the folder."""
    folder = filled(tmp_path, files)
    for name in files:
        os.chmod(folder / name, 0o750 if name.endswith("/") else 0o640)
        os.utime(folder / name, (LONG_AGO, LONG_AGO))
    result = on_v2(made, folder)
    written = folder / "out.csv"
    return result, written.read_text().splitlines() if written.exists() else None, os.path.realpath(folder)


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


def local(seconds):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(seconds))


# ------------------------------------------------------------------
# The columns Talend's component has, when the job declares none
# ------------------------------------------------------------------

def test_job_that_declares_no_columns_gets_the_seven_talend_has(tmp_path):
    result, lines, folder = ran(tmp_path, properties(filename="a.txt"))
    assert result.status == "success", result.error
    assert lines == [TALEND, f"{folder}/a.txt;{folder};a.txt;-rw-r-----;5;{LONG_AGO * 1000};{local(LONG_AGO)}"]


def test_md5_is_an_eighth_column_when_it_is_asked_for(tmp_path):
    result, lines, _ = ran(tmp_path, properties(filename="a.txt", md5=True))
    assert result.status == "success", result.error
    assert lines[0] == TALEND + ";md5"
    assert lines[1].endswith(";" + hashlib.md5(b"hello").hexdigest())


def test_path_given_in_full_and_a_file_in_a_folder(tmp_path):
    folder = os.path.realpath(filled(tmp_path, FILES))
    made = properties("abs_path:str, dirname:str, basename:str", filename=f"{folder}/dir/../dir/b.txt")
    _, lines, _ = ran(tmp_path, made)
    assert lines[1] == f"{folder}/dir/b.txt;{folder}/dir;b.txt"


# ------------------------------------------------------------------
# The columns the job declares
# ------------------------------------------------------------------

def test_declared_columns_are_the_ones_handed_on_in_their_order(tmp_path):
    result, lines, _ = ran(tmp_path, properties("size:int, basename:str", filename="a.txt"))
    assert result.status == "success", result.error
    assert lines == ["size;basename", "5;a.txt"]


def test_type_and_the_two_check_sums(tmp_path):
    _, lines, _ = ran(tmp_path, properties("type:str, md5:str, sha256:str", filename="a.txt"))
    assert lines[1] == f"file;{hashlib.md5(b'hello').hexdigest()};{hashlib.sha256(b'hello').hexdigest()}"


def test_check_sum_of_a_file_longer_than_one_piece_read(tmp_path):
    data = bytes(range(256)) * 20_000  # 5 MB
    _, lines, _ = ran(tmp_path, properties("size:int, sha256:str", filename="big.bin"), {"big.bin": data})
    assert lines[1] == f"{len(data)};{hashlib.sha256(data).hexdigest()}"


def test_folder_has_a_type_and_no_check_sum(tmp_path):
    result, lines, folder = ran(tmp_path, properties("basename:str, type:str, mode_string:str, md5:str", filename="dir"))
    assert result.status == "success", result.error
    assert lines[1] == "dir;folder;drwxr-x---;"


def test_a_column_can_be_declared_another_type(tmp_path):
    made = properties("size:str, mtime_string:datetime@%d/%m/%Y %H:%M", filename="a.txt")
    result, lines, _ = ran(tmp_path, made)
    assert result.status == "success", result.error
    assert lines[1] == "5;" + time.strftime("%d/%m/%Y %H:%M", time.localtime(LONG_AGO))


def test_link_has_the_properties_of_what_it_leads_to(tmp_path):
    folder = filled(tmp_path, FILES)
    os.symlink("dir/b.txt", folder / "link.txt")
    os.symlink("dir", folder / "to_dir")
    _, lines, _ = ran(tmp_path, properties("basename:str, type:str, size:int", filename="link.txt"))
    assert lines[1] == "link.txt;file;1"
    _, lines, _ = ran(tmp_path, properties("basename:str, type:str", filename="to_dir"))
    assert lines[1] == "to_dir;folder"


# ------------------------------------------------------------------
# A file that is not there
# ------------------------------------------------------------------

def test_file_that_is_not_there_fails_the_job(tmp_path):
    result, lines, _ = ran(tmp_path, properties(filename="nope.txt"))
    assert (result.status, result.error) == ("failed", "File not found: 'nope.txt'")
    assert lines is None


def test_job_that_asks_whether_it_exists_gets_a_row_either_way(tmp_path):
    asked = "basename:str, exists:bool, size:int, md5:str"
    _, lines, _ = ran(tmp_path, properties(asked, filename="a.txt"))
    assert lines[1] == f"a.txt;true;5;{hashlib.md5(b'hello').hexdigest()}"
    result, lines, _ = ran(tmp_path / "again", properties(asked, filename="nope.txt"))
    assert result.status == "success", result.error
    assert lines[1] == "nope.txt;false;;"


def test_job_that_is_not_to_die_goes_on_with_no_row_and_says_why(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    made = dict(properties("basename:str", filename="nope.txt", die_on_error=False), run={"row_counts": True})
    result, lines, _ = ran(tmp_path, made)
    assert result.status == "success", result.error
    assert result.rows == {"out": 0} and result.counts["in"] == {"NB_LINE": 0, "NB_LINE_OK": 0, "NB_LINE_REJECT": 0}
    assert result.global_map["in_ERROR_MESSAGE"] == "File not found: 'nope.txt'"
    assert [record.getMessage() for record in caplog.records] == [
        "[in] File not found: 'nope.txt'; the job goes on with no row"]


def test_file_that_cannot_be_looked_at_fails_the_job_in_plain_words(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root may look at everything")
    folder = filled(tmp_path, {"shut/": None, "shut/a.txt": b"x"})
    os.chmod(folder / "shut", 0o000)
    try:
        result = on_v2(properties(filename="shut/a.txt"), folder)
    finally:
        os.chmod(folder / "shut", 0o700)
    assert (result.status, result.error) == ("failed", "'shut/a.txt' cannot be looked at: permission denied")


def test_file_that_cannot_be_read_for_its_check_sum_fails_the_job_in_plain_words(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root may read everything")
    folder = filled(tmp_path, FILES)
    os.chmod(folder / "a.txt", 0o000)
    result = on_v2(properties("basename:str, md5:str", filename="a.txt"), folder)
    assert (result.status, result.error) == (
        "failed", "'a.txt' cannot be read for its check sum: permission denied")


# ------------------------------------------------------------------
# The row and its place
# ------------------------------------------------------------------

def test_failure_later_on_names_the_file(tmp_path):
    result, _, _ = ran(tmp_path, properties("basename:str, md5:str!", filename="dir"))
    assert result.status == "failed"
    assert result.error == "Column 'md5' has NULL values but is not nullable; the row is the properties of dir"


def test_it_counts_one_row(tmp_path):
    made = dict(properties(filename="a.txt"), run={"row_counts": True})
    result, _, _ = ran(tmp_path, made)
    assert result.counts["in"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}


def test_run_for_its_one_row_and_the_trace_of_it(tmp_path):
    made = dict(properties("basename:str, size:int", filename="a.txt"), run={"only": {"source": "in", "rows": [1]}, "trace": True})
    result, lines, _ = ran(tmp_path, made)
    assert result.status == "success", result.error
    assert result.summary()["only"]["rows"] == ["the properties of a.txt"]
    held = result.summary()["trace"][0]["outputs"]["main"]
    assert (held["data"], held["from"]) == ([["a.txt", "5"]], ["the properties of a.txt"])
    assert lines == ["basename;size", "a.txt;5"]


def test_columns_have_their_own_types_when_the_job_declares_none(tmp_path):
    made = dict(properties(filename="a.txt", md5=True), run={"only": {"source": "in", "rows": [1]}, "trace": True})
    result, _, _ = ran(tmp_path, made)
    held = result.summary()["trace"][0]["outputs"]["main"]["columns"]
    assert [(column["name"], column["type"]) for column in held] == [
        ("abs_path", "str"), ("dirname", "str"), ("basename", "str"), ("mode_string", "str"), ("size", "int"),
        ("mtime", "int"), ("mtime_string", "str"), ("md5", "str")]


@pytest.mark.parametrize("picked, said", [
    ({"rows": [2]}, "'in' has no row at row 2"), ({"where": {"basename": ["nope"]}}, "no row of 'in' has basename=nope")])
def test_run_for_a_row_it_does_not_have_says_so(tmp_path, picked, said):
    made = dict(properties("basename:str", filename="a.txt"), run={"only": {"source": "in", **picked}})
    result, lines, _ = ran(tmp_path, made)
    assert (result.status, result.error) == ("failed", said)
    assert lines is None


def test_run_for_its_row_picked_by_what_a_column_holds(tmp_path):
    made = dict(properties("basename:str, size:int", filename="a.txt"), run={"only": {"source": "in", "where": {"size": [5]}}})
    result, lines, _ = ran(tmp_path, made)
    assert result.summary()["only"]["rows"] == ["the properties of a.txt"] and lines[1] == "a.txt;5"


def test_run_that_picks_by_line_is_told_how_its_row_is_picked():
    made = dict(properties("basename:str", filename="a.txt"), run={"only": {"source": "in", "lines": [1]}})
    with pytest.raises(JobRefusedError) as refused:
        run_job(made)
    assert [(refusal.key, refusal.reason) for refusal in refused.value.report] == [
        ("run.only.lines", "'in' hands on one row, the properties of its file: pick its rows with `rows`")]


def test_key_column_is_shown_beside_the_place(tmp_path):
    made = properties("basename:str, md5:str!", filename="dir")
    made["components"][0]["schema"]["output"][0]["key"] = True
    result, _, _ = ran(tmp_path, made)
    assert result.error.endswith("the row is the properties of dir (basename=dir)")


def counting(monkeypatch):
    """Count how often a file is read for its check sums."""
    from src.v2.components.file.file_properties import FileProperties
    calls, real = [], FileProperties._check_sums
    monkeypatch.setattr(FileProperties, "_check_sums", staticmethod(lambda path, wanted: calls.append(wanted) or real(path, wanted)))
    return calls


def test_file_is_read_for_a_check_sum_only_when_one_is_asked_for(tmp_path, monkeypatch):
    calls = counting(monkeypatch)
    ran(tmp_path, properties(filename="a.txt"))
    ran(tmp_path / "again", properties("size:int, basename:str", filename="a.txt"))
    assert calls == []


def test_file_is_read_once_in_a_run_however_often_the_source_is(tmp_path, monkeypatch):
    calls = counting(monkeypatch)
    made = dict(properties("basename:str, md5:str, sha256:str", filename="a.txt"), run={"only": {"source": "in", "rows": [1]}})
    result, _, _ = ran(tmp_path, made)
    assert result.status == "success", result.error
    assert calls == [["md5", "sha256"]]


def test_path_from_the_context(tmp_path):
    made = properties("basename:str", filename="${context.dir}/b.txt")
    made["context"] = {"Default": {"dir": {"value": "dir", "type": "str"}}}
    _, lines, _ = ran(tmp_path, made)
    assert lines[1] == "b.txt"


# ------------------------------------------------------------------
# What is refused, and the names it goes by
# ------------------------------------------------------------------

def test_column_that_is_no_property_refuses_the_job():
    assert refusals(properties("basename:str, owner:str, inode:int", filename="a.txt")) == [
        ("schema", "there is no property 'owner' or 'inode': a column is one of abs_path, dirname, basename, "
                   "mode_string, size, mtime, mtime_string, md5, sha256, exists, type")]


@pytest.mark.parametrize("config, key", [({}, "filename"), ({"filename": " "}, "filename"), ({"filename": "a", "nope": 1}, "nope")])
def test_what_cannot_be_read_refuses_the_job(config, key):
    assert [key for key, _ in refusals(properties(**config))] == [key]


def test_check_goes_on_down_the_flow_with_talends_columns_when_none_are_declared():
    made = properties(filename="a.txt")
    step = {"id": "sorted", "type": "SortRow", "inputs": ["row1"], "outputs": ["row2"],
            "config": {"criteria": [{"column": "nope", "sort_type": "alpha", "order": "asc"}]},
            "schema": {"input": [], "output": []}}
    made["components"] = [made["components"][0], step, writer(None)]
    made["flows"] = [flow("row1", "in", "sorted"), flow("row2", "sorted", "out")]
    assert refusals(made) == [("config", "criteria[0]: there is no column 'nope' to sort by")]


@pytest.mark.parametrize("kind", ["file_properties", "FileProperties", "tFileProperties"])
def test_every_name_of_it(tmp_path, kind):
    result, lines, _ = ran(tmp_path, properties("basename:str", kind=kind, filename="a.txt"))
    assert result.status == "success" and lines == ["basename", "a.txt"]


def test_names_v1s_engine_reads_and_what_the_converter_writes(tmp_path):
    made = properties("basename:str, md5:str", FILENAME="a.txt", MD5=True, tstatcatcher_stats=False, label="")
    result, lines, _ = ran(tmp_path, made)
    assert result.status == "success", result.error
    assert lines[1] == "a.txt;" + hashlib.md5(b"hello").hexdigest()
