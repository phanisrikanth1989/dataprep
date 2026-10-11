"""File row count, against v1: the count each engine leaves in globalMap, and what a trigger makes of it."""
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1
from tests.v2.components.kit import flow, job, reader, writer

LINES = "<id>_COUNT, NB_LINE, NB_LINE_OK, NB_LINE_REJECT"


def counting(kind="FileRowCount", **config):
    return {"id": "cnt", "type": kind, "config": {"filename": "f.txt", **config},
            "schema": {"input": [], "output": []}, "inputs": [], "outputs": []}


def on_v1(made, files, folder):
    """What v1 leaves in globalMap for the counter: (count, rows found, counted, not counted); None when it fails."""
    from src.v1.engine.engine import ETLEngine
    folder.mkdir(parents=True)
    for name, data in files.items():
        (folder / name).write_bytes(data)
    previous = os.getcwd()
    os.chdir(folder)
    try:
        engine = ETLEngine(made)
        if engine.execute().get("status") != "success":
            return None
        return tuple(engine.global_map.get(f"cnt_{name}") for name in ("COUNT", "NB_LINE", "NB_LINE_OK", "NB_LINE_REJECT"))
    finally:
        os.chdir(previous)


def on_v2(made, files, folder):
    folder.mkdir(parents=True)
    for name, data in files.items():
        (folder / name).write_bytes(data)
    previous = os.getcwd()
    os.chdir(folder)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    if result.status != "success":
        return result
    return tuple(result.global_map.get(f"cnt_{name}") for name in ("COUNT", "NB_LINE", "NB_LINE_OK", "NB_LINE_REJECT"))


def same(tmp_path, data, **config):
    """Both engines come to the same four numbers. Returns them."""
    made = job([counting(**config)], [])
    key, got = on_v1(made, {"f.txt": data}, tmp_path / "v1"), on_v2(made, {"f.txt": data}, tmp_path / "v2")
    assert got == key and key is not None
    return got


@pytest.mark.parametrize("data, count", [
    (b"a\nb\nc\n", 3), (b"a\nb\nc", 3), (b"", 0), (b"\n", 1), (b"a\n\n  \nb\n", 4), (b"a\r\nb\rc\n", 3), (b"\r\n\r\n", 2),
    (b"a\r\r\nb", 3),
])
def test_every_kind_of_line_end_ends_a_row_and_the_last_row_needs_none(tmp_path, data, count):
    assert same(tmp_path, data) == (count, count, count, 0)
    assert same(tmp_path / "b", data, row_separator="\\r\\n") == (count, count, count, 0)
    assert same(tmp_path / "c", data, row_separator="\\r") == (count, count, count, 0)


@pytest.mark.parametrize("separator, data, count", [
    ("|", b"a|b||c|", 4), ("|", b"a|b||c", 4), ("|", b"a\nb|c\n", 2), ("\\t", b"a\tb\tc", 3), ("::", b"a::b::", 2),
    ("|", b"", 0), ("|", b"|", 1), ("|", b"abc", 1), (";\\n", b"a;\nb\n;\nc", 3),
    ("|\\r", b"a|\rb|\rc", 3), ("|", b"a\r\n|b\r|c", 3),
])
def test_another_separator_splits_the_whole_text(tmp_path, separator, data, count):
    assert same(tmp_path, data, row_separator=separator) == (count, count, count, 0)


def test_rows_of_nothing_but_blanks_are_not_counted_when_asked(tmp_path):
    assert same(tmp_path, b"a\n\n  \nb\n\t\n", ignore_empty_row=True) == (2, 5, 2, 3)
    assert same(tmp_path / "b", b"a|b|| |c", row_separator="|", ignore_empty_row=True) == (3, 5, 3, 2)


def test_file_is_read_in_its_encoding(tmp_path):
    assert same(tmp_path, "é\nü\n".encode("utf-16"), encoding="UTF-16") == (2, 2, 2, 0)
    assert same(tmp_path / "b", "é\nü\n".encode("utf-8")) == (2, 2, 2, 0)
    # U+2028 is a line end to Python's own splitting, and none to a file read line by line.
    assert same(tmp_path / "c", "a b\nc\x0bd\n".encode("utf-8"), encoding="UTF-8") == (2, 2, 2, 0)


def test_large_file_is_counted_without_being_held(tmp_path):
    assert same(tmp_path, b"row of some length\n" * 300000 + b"last")[0] == 300001


def test_trigger_that_reads_the_count_sets_off_what_follows(tmp_path):
    copy = [reader("id:int, name:str", component_id="in"), writer("id:int, name:str", inputs=("row1",))]
    for limit, runs in ((2, True), (3, False)):
        made = job([counting(filename="in.csv"), *copy], [flow("row1", "in", "out")])
        made["triggers"] = [{"type": "RunIf", "from": "cnt", "to": "in",
                             "condition": f'((Integer)globalMap.get("cnt_COUNT")) > {limit}'}]
        run = assert_matches_v1(made, {"in.csv": b"1;a\n2;b\n3;c\n"}, tmp_path / str(limit))
        assert run.succeeded and ("out.csv" in run.files) is runs


def test_count_is_there_for_a_later_stage_to_read(tmp_path):
    source = {"id": "in", "type": "FixedFlowInputComponent", "inputs": [], "outputs": ["row1"],
              "config": {"nb_rows": 1, "values_config": [{"schema_column": "n", "value": 'globalMap.get("cnt_COUNT")'}]},
              "schema": {"input": [], "output": [{"name": "n", "type": "int", "nullable": True}]}}
    made = job([counting(), source, writer("n:int", inputs=("row1",))], [flow("row1", "in", "out")])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "cnt", "to": "in"}]
    run = assert_matches_v1(made, {"f.txt": b"a\nb\n"}, tmp_path)
    assert run.files["out.csv"] == b"n\n2\n"


def test_run_for_a_few_rows_of_a_reader_still_counts_the_whole_file_and_the_trace_passes_it_by(tmp_path):
    copy = [reader("id:int, name:str", component_id="in"), writer("id:int, name:str", inputs=("row1",))]
    made = job([counting(filename="in.csv"), *copy], [flow("row1", "in", "out")])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "cnt", "to": "in"}]
    made["run"] = {"only": {"source": "in", "where": {"id": [2]}}, "trace": True}
    result = on_v2(made, {"in.csv": b"1;a\n2;b\n3;c\n"}, tmp_path / "a")
    assert result == (3, 3, 3, 0)
    assert (tmp_path / "a" / "out.csv").read_bytes() == b"id;name\n2;b\n"


def test_job_with_a_counter_is_checked_without_the_file_being_there(tmp_path):
    load_job(job([counting(filename="not/there.txt")], []))


def test_counts_are_said_with_the_others_when_a_run_asks_for_them(tmp_path):
    (tmp_path / "f.txt").write_bytes(b"a\n\nb\n")
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(dict(job([counting(ignore_empty_row=True)], []), run={"row_counts": True}))
    finally:
        os.chdir(previous)
    assert result.status == "success" and result.counts["cnt"] == {"NB_LINE": 3, "NB_LINE_OK": 2, "NB_LINE_REJECT": 1}


def test_file_that_is_not_there_or_not_in_its_encoding_fails_the_job(tmp_path):
    made = job([counting()], [])
    assert on_v1(made, {}, tmp_path / "v1") is None
    result = on_v2(made, {}, tmp_path / "v2")
    assert result.status == "failed" and result.failed_component == "cnt" and result.error == "File not found: 'f.txt'"
    made = job([counting(encoding="UTF-8")], [])
    assert on_v1(made, {"f.txt": b"ok\n\xff\xfe\n"}, tmp_path / "b1") is None
    result = on_v2(made, {"f.txt": b"ok\n\xff\xfe\n"}, tmp_path / "b2")
    assert result.status == "failed" and result.error == "'f.txt' is not written in UTF-8: a byte in it is no character there"


def test_subjob_that_follows_a_failed_count_does_not_run_and_its_error_trigger_does(tmp_path):
    copy = [reader("id:int", component_id="in"), writer("id:int", inputs=("row1",))]
    made = job([counting(), *copy], [flow("row1", "in", "out")])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "cnt", "to": "in"}]
    result = on_v2(made, {"in.csv": b"1\n"}, tmp_path / "a")
    assert result.status == "failed" and not (tmp_path / "a" / "out.csv").exists()
    made["triggers"] = [{"type": "OnSubjobError", "from": "cnt", "to": "in"}]
    on_v2(made, {"in.csv": b"1\n"}, tmp_path / "b")
    assert (tmp_path / "b" / "out.csv").read_bytes() == b"id\n1\n"


@pytest.mark.parametrize("config, key", [
    ({"filename": ""}, "path"), ({"row_separator": ""}, "row_separator"), ({"encoding": "nope-8"}, "encoding"),
    ({"nope": 1}, "nope"),
])
def test_what_cannot_be_read_refuses_the_job(config, key):
    with pytest.raises(JobRefusedError) as refused:
        load_job(job([counting(**config)], []))
    assert [refusal.key for refusal in refused.value.report] == [key]


def test_flow_into_it_or_out_of_it_is_refused():
    made = job([reader("id:int"), counting()], [flow("row1", "in", "cnt")])
    made["components"][1]["inputs"] = ["row1"]
    with pytest.raises(JobRefusedError, match="takes no input"):
        load_job(made)
    made = job([counting(), writer("id:int", inputs=("row1",))], [flow("row1", "cnt", "out")])
    made["components"][0]["outputs"] = ["row1"]
    with pytest.raises(JobRefusedError):
        load_job(made)


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("file_row_count", "FileRowCount", "tFileRowCount")):
        assert on_v2(job([counting(kind=kind)], []), {"f.txt": b"a\nb\n"}, tmp_path / str(at)) == (2, 2, 2, 0)
