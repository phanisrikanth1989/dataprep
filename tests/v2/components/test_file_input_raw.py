"""Raw file input: a whole file as one value."""
import logging
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, writer

from .test_file_actions_kit import filled, on_v2

TEXT = "first line\r\nsecond; with a separator\n\nlast, no line end"


def raw(schema="content:str", kind="FileInputRaw", **config):
    """a file's text -> out.txt, as it is and followed by one line end."""
    source = {"id": "in", "type": kind, "config": config, "inputs": [], "outputs": ["row1"],
              "schema": {"input": [], "output": columns(schema) if schema else []}}
    out = writer(schema, path="out.txt", inputs=("row1",), include_header=False)
    return job([source, out], [flow("row1", "in", "out")])


def ran(tmp_path, made, files):
    """Run in a folder of these files; returns how it ended and the bytes of out.txt (None when it is not there)."""
    folder = filled(tmp_path, files)
    result = on_v2(made, folder)
    written = folder / "out.txt"
    return result, written.read_bytes() if written.exists() else None


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# The text
# ------------------------------------------------------------------

def test_file_is_one_row_holding_its_text_as_it_is(tmp_path):
    result, written = ran(tmp_path, raw(filename="in.txt", encoding="UTF-8"), {"in.txt": TEXT.encode()})
    assert result.status == "success", result.error
    assert written == TEXT.encode() + b"\n"
    assert result.rows == {"out": 1}


def test_encoding_is_iso_8859_15_when_none_is_given(tmp_path):
    _, written = ran(tmp_path, raw(filename="in.txt"), {"in.txt": b"5 \xa4 caf\xe9"})
    assert written.decode() == "5 \u20ac caf\u00e9\n"


@pytest.mark.parametrize("encoding, data", [
    ("UTF-8", b"\xef\xbb\xbfab\xc3\xa9"), ("UTF-16", "ab\u00e9".encode("utf-16")), ("UTF-16LE", "\ufeffab\u00e9".encode("utf-16-le")),
], ids=["utf-8", "utf-16", "utf-16le"])
def test_byte_order_mark_is_no_part_of_the_text(tmp_path, encoding, data):
    _, written = ran(tmp_path, raw(filename="in.txt", encoding=encoding), {"in.txt": data})
    assert written.decode() == "ab\u00e9\n"


def test_empty_file_is_a_row_of_empty_text(tmp_path):
    result, written = ran(tmp_path, raw(filename="in.txt"), {"in.txt": b""})
    assert result.status == "success" and result.rows == {"out": 1}
    assert written == b"\n"


def test_column_has_the_name_the_job_declares_and_talends_when_it_declares_none(tmp_path):
    made = dict(raw("body:str", filename="in.txt"), run={"only": {"source": "in", "rows": [1]}, "trace": True})
    result, _ = ran(tmp_path, made, {"in.txt": b"x"})
    assert result.summary()["trace"][0]["outputs"]["main"]["columns"] == [{"name": "body", "type": "str"}]
    made = dict(raw(None, filename="in.txt"), run={"only": {"source": "in", "rows": [1]}, "trace": True})
    result, written = ran(tmp_path / "again", made, {"in.txt": b"x"})
    assert result.summary()["trace"][0]["outputs"]["main"]["columns"] == [{"name": "content", "type": "str"}]
    assert written == b"x\n"


def test_column_declared_an_object_as_a_converted_job_declares_it(tmp_path):
    result, written = ran(tmp_path, raw("content:object", filename="in.txt"), {"in.txt": b"x"})
    assert result.status == "success" and written == b"x\n"


# ------------------------------------------------------------------
# What cannot be read
# ------------------------------------------------------------------

def test_byte_that_is_no_character_fails_the_job_and_says_where(tmp_path):
    data = b"one\ntwo\nthr\xe9e\n"
    result, written = ran(tmp_path, raw(filename="in.txt", encoding="UTF-8"), {"in.txt": data})
    assert (result.status, written) == ("failed", None)
    assert result.error == "'in.txt' is not written in UTF-8: byte 12 of it, on line 3, is no character there"


def test_file_that_is_not_there_fails_the_job(tmp_path):
    result, written = ran(tmp_path, raw(filename="nope.txt"), {})
    assert (result.status, result.error, written) == ("failed", "File not found: 'nope.txt'", None)


def test_folder_fails_the_job(tmp_path):
    result, _ = ran(tmp_path, raw(filename="dir"), {"dir/": None})
    assert (result.status, result.error) == ("failed", "'dir' cannot be read: it is a folder")


def test_pipe_or_device_fails_the_job_and_is_never_opened(tmp_path):
    folder = filled(tmp_path, {})
    os.mkfifo(folder / "pipe")
    result = on_v2(raw(filename="pipe"), folder)
    assert (result.status, result.error) == ("failed", "'pipe' cannot be read: it is no file, but a pipe or a device")
    result = on_v2(raw(filename="/dev/zero"), folder)
    assert (result.status, result.error) == ("failed", "'/dev/zero' cannot be read: it is no file, but a pipe or a device")


def test_job_that_is_not_to_die_goes_on_with_no_row_and_says_why(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    made = dict(raw(filename="nope.txt", die_on_error=False), run={"row_counts": True})
    result, written = ran(tmp_path, made, {})
    assert result.status == "success", result.error
    assert result.rows == {"out": 0} and not written
    assert result.global_map["in_ERROR_MESSAGE"] == "File not found: 'nope.txt'"
    assert result.counts["in"] == {"NB_LINE": 0, "NB_LINE_OK": 0, "NB_LINE_REJECT": 0}
    assert [record.getMessage() for record in caplog.records] == [
        "[in] File not found: 'nope.txt'; the job goes on with no row"]


def test_job_that_is_not_to_die_goes_on_past_text_that_cannot_be_read(tmp_path):
    made = raw(filename="in.txt", encoding="UTF-8", die_on_error=False)
    result, _ = ran(tmp_path, made, {"in.txt": b"\xff"})
    assert result.status == "success" and result.rows == {"out": 0}
    assert result.global_map["in_ERROR_MESSAGE"] == (
        "'in.txt' is not written in UTF-8: byte 1 of it, on line 1, is no character there")


# ------------------------------------------------------------------
# The size it may have
# ------------------------------------------------------------------

def test_file_larger_than_the_limit_fails_the_job_before_it_is_read(tmp_path):
    big = b"x" * (2 * 1024 * 1024 + 1)
    result, written = ran(tmp_path, raw(filename="in.txt", size_limit_mb=2), {"in.txt": big})
    assert (result.status, written) == ("failed", None)
    assert result.error == (
        "'in.txt' holds 2097153 bytes, more than the 2 MB a raw file input reads by `size_limit_mb`: "
        "the whole file would be held in memory as one value")
    result, written = ran(tmp_path / "again", raw(filename="in.txt", size_limit_mb=3), {"in.txt": big})
    assert result.status == "success" and written == big + b"\n"


def test_file_as_large_as_the_limit_is_read(tmp_path):
    exact = b"y" * (1024 * 1024)
    result, written = ran(tmp_path, raw(filename="in.txt", size_limit_mb=1), {"in.txt": exact})
    assert result.status == "success" and written == exact + b"\n"


def test_limit_is_a_gigabyte_when_none_is_given():
    assert load_job(raw(filename="in.txt")).components["in"].config["size_limit_mb"] == 1024


# ------------------------------------------------------------------
# What it leaves, its row and its place
# ------------------------------------------------------------------

def test_path_is_left_in_globalmap_and_one_row_is_counted(tmp_path):
    made = dict(raw(filename="in.txt"), run={"row_counts": True})
    result, _ = ran(tmp_path, made, {"in.txt": b"x"})
    assert result.global_map["in_FILENAME_PATH"] == "in.txt"
    assert result.counts["in"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}


def test_run_for_its_one_row_names_it_by_its_file(tmp_path):
    made = dict(raw(filename="in.txt"), run={"only": {"source": "in", "rows": [1]}, "trace": True})
    result, _ = ran(tmp_path, made, {"in.txt": b"a\nb"})
    assert result.summary()["only"]["rows"] == ["the content of in.txt"]
    held = result.summary()["trace"][0]["outputs"]["main"]
    assert (held["data"], held["from"]) == ([["a\nb"]], ["the content of in.txt"])


def test_run_that_picks_by_line_is_told_how_its_row_is_picked():
    made = dict(raw(filename="in.txt"), run={"only": {"source": "in", "lines": [1]}})
    with pytest.raises(JobRefusedError) as refused:
        run_job(made)
    assert [(refusal.key, refusal.reason) for refusal in refused.value.report] == [
        ("run.only.lines", "'in' hands on one row, the content of its file: pick its rows with `rows`")]


def test_key_column_is_shown_beside_the_place(tmp_path):
    made = dict(raw(filename="in.txt"), run={"only": {"source": "in", "rows": [1]}, "trace": True})
    made["components"][0]["schema"]["output"][0]["key"] = True
    result, _ = ran(tmp_path, made, {"in.txt": b"abc"})
    assert result.summary()["trace"][0]["outputs"]["main"]["from"] == ["the content of in.txt (content=abc)"]


def test_check_goes_on_down_the_flow_with_talends_column_when_none_is_declared():
    made = raw(None, filename="in.txt")
    step = {"id": "sorted", "type": "SortRow", "inputs": ["row1"], "outputs": ["row2"],
            "config": {"criteria": [{"column": "nope", "sort_type": "alpha", "order": "asc"}]},
            "schema": {"input": [], "output": []}}
    made["components"] = [made["components"][0], step, writer(None)]
    made["flows"] = [flow("row1", "in", "sorted"), flow("row2", "sorted", "out")]
    assert refusals(made) == [("config", "criteria[0]: there is no column 'nope' to sort by")]


def test_file_is_read_once_in_a_run_however_often_the_source_is(tmp_path, monkeypatch):
    from src.v2.components.file.file_input_raw import FileInputRaw
    calls, real = [], FileInputRaw._text
    monkeypatch.setattr(FileInputRaw, "_text", lambda self: calls.append(self.id) or real(self))
    made = dict(raw(filename="in.txt"), run={"only": {"source": "in", "rows": [1]}})
    result, _ = ran(tmp_path, made, {"in.txt": b"x"})
    assert result.status == "success" and calls == ["in"]


def test_path_from_the_context(tmp_path):
    made = raw(filename="${context.dir}/in.txt")
    made["context"] = {"Default": {"dir": {"value": "dir", "type": "str"}}}
    _, written = ran(tmp_path, made, {"dir/in.txt": b"x"})
    assert written == b"x\n"


# ------------------------------------------------------------------
# What is refused, and the names it goes by
# ------------------------------------------------------------------

def test_bytes_and_streams_are_refused_and_say_why():
    assert refusals(raw(filename="a", as_string=False, as_bytearray=True)) == [
        ("as_bytearray", "v2 has no column type that holds bytes: read the file as text, or hand its path to the "
                         "component that needs it")]
    assert refusals(raw(filename="a", as_string=False, as_inputstream=True)) == [
        ("as_inputstream", "v2 hands on values and not open files: read the file as text, or hand its path to the "
                           "component that needs it")]


def test_what_the_converter_writes_is_taken(tmp_path):
    made = raw(filename="in.txt", as_string=True, as_bytearray=False, as_inputstream=False, encoding="ISO-8859-15",
               die_on_error=False, tstatcatcher_stats=False, label="")
    result, written = ran(tmp_path, made, {"in.txt": b"x"})
    assert result.status == "success" and written == b"x\n"


def test_more_than_one_column_refuses_the_job():
    assert refusals(raw("content:str, more:str", filename="a")) == [
        ("schema", "a raw file input hands on one column, the file's text; 2 are declared")]


@pytest.mark.parametrize("config, key", [
    ({}, "filename"), ({"filename": " "}, "filename"), ({"filename": "a", "nope": 1}, "nope"),
    ({"filename": "a", "encoding": "nope"}, "encoding"), ({"filename": "a", "size_limit_mb": 0}, "size_limit_mb"),
])
def test_what_cannot_be_read_refuses_the_job(config, key):
    assert [key for key, _ in refusals(raw(**config))] == [key]


@pytest.mark.parametrize("kind", ["file_input_raw", "FileInputRaw", "tFileInputRaw"])
def test_every_name_of_it(tmp_path, kind):
    result, written = ran(tmp_path, raw(kind=kind, filename="in.txt"), {"in.txt": b"x"})
    assert result.status == "success" and written == b"x\n"
