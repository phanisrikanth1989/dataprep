"""Rows dropped for a fault are told in the log.

A component that is told not to stop on a row with something wrong with it
turns the row away. When no flow takes its reject output the row is gone,
and the job still ends in success. The log then has one WARNING line for the
component: how many rows, what was wrong with the first, and where it was.
"""
import json
import logging

import pytest

from src.v2.cli import main

from .components.kit import columns, flow, job, reader, through, writer
from .components.test_file_input_excel import book, excel
from .components.test_file_input_json import json_job
from .components.test_file_input_positional import cut
from .components.test_python_dataframe import coded
from .test_row_numbers import copying, keyed, ran

IDS = "id:int, amount:int"
# The row with id 3 holds an amount that is no number: line 4 of the file, under one header line.
DATA = b"id;amount\n1;10\n2;20\n3;x\n4;40\n"
NO_TAKER = "(no flow takes this component's rejects)"
UNREADABLE = "Column 'amount': could not convert string to float: 'x'"


def told(caplog, tmp_path, made, files):
    """Run a job on v2 inside tmp_path; returns (how it ended, the warnings it logged)."""
    caplog.set_level(logging.INFO, logger="src.v2")
    caplog.clear()
    result = ran(tmp_path, made, files)
    return result, [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]


# ------------------------------------------------------------------
# A reader that cannot read a row
# ------------------------------------------------------------------

def test_reader_tells_of_the_row_it_could_not_read_and_dropped(caplog, tmp_path):
    result, said = told(caplog, tmp_path, keyed(copying(header_rows=1)), {"in.csv": DATA})
    assert result.status == "success"
    assert said == [f"[in] 1 row was dropped {NO_TAKER}: {UNREADABLE}; the row is line 4 of in.csv (id=3)"]
    assert (tmp_path / "out.csv").read_bytes() == b"id;amount\n1;10\n2;20\n4;40\n"


def test_several_dropped_rows_are_counted_and_the_first_is_named(caplog, tmp_path):
    data = b"id;amount\n1;10\n2;x\n3;30\n4;y\n5;z\n"
    result, said = told(caplog, tmp_path, keyed(copying(header_rows=1)), {"in.csv": data})
    assert result.status == "success"
    assert said == [f"[in] 3 rows were dropped {NO_TAKER}; the first: {UNREADABLE}; "
                    "the row is line 3 of in.csv (id=2)"]


def test_row_dropped_for_a_column_read_as_text_is_told_too(caplog, tmp_path):
    # A Decimal is read from its text by the reader itself, so the file is read once; an int is first
    # handed to Polars, which fails on it and has the file read again.
    made = keyed(copying("id:int, amount:Decimal#2", header_rows=1))
    result, said = told(caplog, tmp_path, made, {"in.csv": DATA})
    assert result.status == "success"
    assert said == [f"[in] 1 row was dropped {NO_TAKER}: Column 'amount': could not convert string to Decimal: 'x'"
                    "; the row is line 4 of in.csv (id=3)"]


def test_nothing_is_told_when_no_row_is_dropped(caplog, tmp_path):
    result, said = told(caplog, tmp_path, keyed(copying(header_rows=1)), {"in.csv": b"id;amount\n1;10\n2;20\n"})
    assert result.status == "success" and said == []


def test_nothing_is_told_when_a_flow_takes_the_rejects(caplog, tmp_path):
    made = job([reader(IDS, outputs=("row1", "bad"), header_rows=1), writer(IDS, inputs=("row1",)),
                writer(None, component_id="rej", path="rej.csv", inputs=("bad",))],
               [flow("row1", "in", "out"), flow("bad", "in", "rej", "reject")])
    result, said = told(caplog, tmp_path, made, {"in.csv": DATA})
    assert result.status == "success" and said == []
    assert (tmp_path / "rej.csv").read_bytes().splitlines()[1].startswith(b"3;x;")


def test_nothing_is_told_of_dropped_rows_when_the_reader_stops_the_job(caplog, tmp_path):
    result, said = told(caplog, tmp_path, copying(header_rows=1, die_on_error=True), {"in.csv": DATA})
    assert result.status == "failed" and said == []


def test_nothing_is_told_when_the_job_fails_further_on(caplog, tmp_path):
    # The reader turns the third row away, and the sort stops the job on the fourth, which has no amount.
    # Nothing was written, so nothing was dropped.
    made = through({"type": "SortRow", "config": {"criteria": [{"column": "id", "sort_type": "num", "order": "asc"}]}},
                   IDS, "id:int, amount:int!")
    result, said = told(caplog, tmp_path, made, {"in.csv": b"id;amount\n1;10\n2;20\n3;x\n4;\n"})
    assert result.status == "failed" and result.failed_component == "it"
    assert said == []


def test_row_with_the_wrong_number_of_fields_is_told_with_its_line_and_no_second_number(caplog, tmp_path):
    made = copying(header_rows=1, check_fields_num=True)
    result, said = told(caplog, tmp_path, made, {"in.csv": b"id;amount\n1;10\n\n2;20;extra\n3;30\n"})
    assert result.status == "success"
    assert said == [f"[in] 1 row was dropped {NO_TAKER}: Field count mismatch: expected 2, got 3; "
                    "the row is line 4 of in.csv"]


def test_positional_reader_tells_of_the_row_it_dropped(caplog, tmp_path):
    made = keyed(cut(schema="a:str, n:int", pattern="3,3", header_rows=1), key="a")
    result, said = told(caplog, tmp_path, made, {"in.txt": b"nam  n\nabc  1\n\ndef  x\nghi  3\n"})
    assert result.status == "success"
    assert said == [f"[in] 1 row was dropped {NO_TAKER}: Column 'n': could not convert string to float: 'x'; "
                    "the row is line 4 of in.txt (a=def)"]


# ------------------------------------------------------------------
# A missing value where none is allowed
# ------------------------------------------------------------------

MISSING = "Column 'n': non-nullable column has null"


def test_excel_reader_tells_of_the_row_it_dropped_for_a_missing_value(caplog, tmp_path):
    made = keyed(excel("id:int, n:int!", header=1, all_sheets=True))
    sheets = book({"first": [["id", "n"], [1, 10], [2, 20]], "second": [["id", "n"], [3, 30], [4, None], [5, 50]]})
    result, said = told(caplog, tmp_path, made, {"in.xlsx": sheets})
    assert result.status == "success"
    assert said == [f"[in] 1 row was dropped {NO_TAKER}: {MISSING}; "
                    "the row is row 3 of sheet 'second' of in.xlsx (id=4)"]


def test_step_without_a_reject_output_tells_of_the_row_it_dropped(caplog, tmp_path):
    sort = {"type": "SortRow", "config": {"criteria": [{"column": "id", "sort_type": "num", "order": "asc"}],
                                           "die_on_error": False}}
    made = keyed(through(sort, "id:int, n:int", "id:int, n:int!"))
    result, said = told(caplog, tmp_path, made, {"in.csv": b"id;n\n2;5\n1;\n3;7\n"})
    assert result.status == "success"
    assert said == [f"[it] 1 row was dropped: {MISSING}; the row is line 3 of in.csv (id=1)"]
    assert (tmp_path / "out.csv").read_bytes() == b"id;n\n2;5\n3;7\n"


def test_step_that_stops_the_job_on_a_missing_value_tells_of_no_dropped_row(caplog, tmp_path):
    sort = {"type": "SortRow", "config": {"criteria": [{"column": "id", "sort_type": "num", "order": "asc"}]}}
    result, said = told(caplog, tmp_path, through(sort, "id:int, n:int", "id:int, n:int!"),
                        {"in.csv": b"id;n\n2;5\n1;\n3;7\n"})
    assert result.status == "failed" and said == []


# ------------------------------------------------------------------
# A JSON record
# ------------------------------------------------------------------

ODD = {"items": [{"id": 1, "tags": ["a"]}, {"id": 2, "tags": 5}, {"id": 3, "tags": ["c"]}]}


@pytest.mark.parametrize("die_on_error", [True, False])
def test_json_reader_tells_of_the_record_a_path_could_not_be_followed_on(caplog, tmp_path, die_on_error):
    # Such a record is turned away whatever die_on_error says, as in v1.
    made = keyed(json_job("id:int, tag:str", [("id", "$.id"), ("tag", "$.tags[0]")], die_on_error=die_on_error))
    result, said = told(caplog, tmp_path, made, {"in.json": json.dumps(ODD).encode()})
    assert result.status == "success"
    assert said == [f"[in] 1 row was dropped {NO_TAKER}: a path could not be followed on the record "
                    "(object of type 'int' has no len()); the row is record 2 ($.items[1]) of in.json (id=2)"]


def test_json_reader_tells_of_the_record_it_dropped_for_a_missing_value(caplog, tmp_path):
    document = {"items": [{"id": 1, "n": "a"}, {"id": 2, "n": None}, {"id": 3, "n": "c"}]}
    made = keyed(json_job("id:int, n:str!", [("id", "$.id"), ("n", "$.n")], die_on_error=False))
    result, said = told(caplog, tmp_path, made, {"in.json": json.dumps(document).encode()})
    assert result.status == "success"
    assert said == [f"[in] 1 row was dropped {NO_TAKER}: {MISSING}; "
                    "the row is record 2 ($.items[1]) of in.json (id=2)"]


# ------------------------------------------------------------------
# When and where it is said
# ------------------------------------------------------------------

def test_row_dropped_before_code_that_needs_the_rows_in_hand_is_told_once(caplog, tmp_path):
    made = keyed(coded("df['amount'] = df['amount'] * 2", schema=IDS))
    result, said = told(caplog, tmp_path, made, {"in.csv": DATA})
    assert result.status == "success"
    assert said == [f"[in] 1 row was dropped {NO_TAKER}: {UNREADABLE}; the row is line 4 of in.csv (id=3)"]


def test_it_is_said_after_the_files_are_written_and_before_the_subjob_is_said_to_be_finished(caplog, tmp_path):
    told(caplog, tmp_path, keyed(copying(header_rows=1)), {"in.csv": DATA})
    said = [record.getMessage() for record in caplog.records if record.name == "src.v2.engine.runner"]
    wrote = next(place for place, line in enumerate(said) if line.startswith("[out] wrote 3 row(s)"))
    dropped = next(place for place, line in enumerate(said) if line.startswith("[in] 1 row was dropped"))
    finished = next(place for place, line in enumerate(said) if "subjob finished" in line)
    assert wrote < dropped < finished


def test_value_beyond_ascii_is_written_in_ascii(caplog, tmp_path):
    result, said = told(caplog, tmp_path, copying(header_rows=1), {"in.csv": "id;amount\n1;zéro\n".encode()})
    assert result.status == "success"
    assert said == [f"[in] 1 row was dropped {NO_TAKER}: Column 'amount': could not convert string to float: "
                    "'z\\xe9ro'; the row is line 2 of in.csv"]


def test_command_line_puts_it_on_standard_error_and_still_ends_with_0(tmp_path, capsys):
    (tmp_path / "in.csv").write_bytes(DATA)
    made = job([reader(IDS, path=str(tmp_path / "in.csv"), header_rows=1),
                writer(IDS, path=str(tmp_path / "out.csv"), inputs=("row1",))], [flow("row1", "in", "out")])
    (tmp_path / "job.json").write_text(json.dumps(made))
    assert main([str(tmp_path / "job.json")]) == 0
    printed = capsys.readouterr()
    assert f"WARNING src.v2.engine.runner - [in] 1 row was dropped {NO_TAKER}: {UNREADABLE}; the row is line 4 of" \
        in printed.err
    assert "was dropped" not in printed.out


def test_rows_dropped_from_sheets_put_one_after_another_and_cut_are_counted_right(caplog, tmp_path):
    # Polars 1.44 miscounts a plain count of frames put one after another and then cut by a limit. The limit
    # is two rows of each sheet: of the four read, three have no n.
    made = keyed(excel("id:int, n:int!", header=1, all_sheets=True, limit=2))
    sheets = book({"first": [["id", "n"], [1, None], [2, 20], [3, None]],
                   "second": [["id", "n"], [4, None], [5, None], [6, 60]]})
    result, said = told(caplog, tmp_path, made, {"in.xlsx": sheets})
    assert result.status == "success"
    assert (tmp_path / "out.csv").read_bytes() == b"2;20\n"
    assert said == [f"[in] 3 rows were dropped {NO_TAKER}; the first: {MISSING}; "
                    "the row is row 2 of sheet 'first' of in.xlsx (id=1)"]


def test_component_that_drops_rows_for_two_kinds_of_fault_tells_of_each(caplog, tmp_path):
    # The second record cannot be followed by the path; the third has no id, where one is needed.
    document = {"items": [{"id": 1, "tags": ["a"]}, {"id": 2, "tags": 5}, {"id": None, "tags": ["c"]}]}
    made = json_job("id:int!, tag:str", [("id", "$.id"), ("tag", "$.tags[0]")], die_on_error=False)
    result, said = told(caplog, tmp_path, made, {"in.json": json.dumps(document).encode()})
    assert result.status == "success"
    assert said == [
        f"[in] 1 row was dropped {NO_TAKER}: a path could not be followed on the record "
        "(object of type 'int' has no len()); the row is record 2 ($.items[1]) of in.json",
        f"[in] 1 row was dropped {NO_TAKER}: Column 'id': non-nullable column has null; "
        "the row is record 3 ($.items[2]) of in.json",
    ]
    assert (tmp_path / "out.csv").read_bytes() == b"id;tag\n1;a\n"
