"""Every source numbers its rows, and a failure names the row it was.

The number is a hidden column: it travels with the row through the job and
is never written to a file. These tests hold what a failure says; that no
file changes is held by every test that compares v2's files with v1's.
"""
import os

import pytest

from src.v2 import run_job

from .components.kit import columns, flow, job, reader, through, writer

IDS = "id:int, amount:int"


def keyed(made, component_id="in", key="id"):
    """Mark a column of a component's output schema as its key."""
    for component in made["components"]:
        if component["id"] == component_id:
            for column in component["schema"]["output"]:
                column["key"] = column["name"] == key
    return made


def copying(schema=IDS, write_schema="same", **read):
    """file -> file."""
    return job([reader(schema, **read), writer(schema if write_schema == "same" else write_schema, inputs=("row1",))],
               [flow("row1", "in", "out")])


def ran(tmp_path, made, files):
    """Run a job on v2 inside tmp_path with these files; returns how it ended."""
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def failed(tmp_path, made, files):
    result = ran(tmp_path, made, files)
    assert result.status == "failed", "the job finished"
    return result.error


# ------------------------------------------------------------------
# A reader names the line
# ------------------------------------------------------------------

def test_reader_names_the_line_of_the_row_it_cannot_read(tmp_path):
    error = failed(tmp_path, copying(header_rows=1, die_on_error=True), {"in.csv": b"id;amount\n1;10\n2;20\n3;x\n4;40\n"})
    assert error == ("Schema/coercion failed for 1 row(s); first error: Column 'amount': could not convert string "
                     "to float: 'x'; the row is line 4 of in.csv")


def test_reader_shows_the_value_of_the_key_column_too(tmp_path):
    made = keyed(copying(header_rows=1, die_on_error=True))
    error = failed(tmp_path, made, {"in.csv": b"id;amount\n1;10\n2;20\n3;x\n4;40\n"})
    assert error.endswith("; the row is line 4 of in.csv (id=3)")


def test_first_bad_row_is_the_one_named_and_all_are_counted(tmp_path):
    error = failed(tmp_path, keyed(copying(die_on_error=True)), {"in.csv": b"1;10\n2;x\n3;30\n4;y\n"})
    assert error.startswith("Schema/coercion failed for 2 row(s); first error: ") and "'x'" in error
    assert error.endswith("; the row is line 2 of in.csv (id=2)")


def test_blank_lines_before_the_row_are_counted_as_lines(tmp_path):
    error = failed(tmp_path, copying(header_rows=1, die_on_error=True), {"in.csv": b"id;amount\n1;10\n\n\n2;x\n"})
    assert error.endswith("; the row is line 5 of in.csv")


def test_line_is_right_when_the_reader_splits_the_rows_itself(tmp_path):
    made = copying(header_rows=2, die_on_error=True, check_fields_num=True)
    error = failed(tmp_path, made, {"in.csv": b"title\nid;amount\n1;10\n\n2;20;extra\n3;30\n"})
    assert "Field count mismatch" in error
    assert error.endswith("; the row is line 5 of in.csv")


def test_file_with_enclosures_names_the_record_not_a_line(tmp_path):
    # A field may hold a line break there, so a record's number is not the line an editor shows.
    made = copying("id:int, note:str, amount:int", header_rows=1, die_on_error=True, csv_option=True)
    error = failed(tmp_path, made, {"in.csv": b'id;note;amount\n1;"two\nlines";10\n2;b;x\n'})
    assert error.endswith("; the row is record 2 of in.csv")


def test_key_value_is_cut_at_a_hundred_characters(tmp_path):
    made = keyed(copying("name:str, amount:int", die_on_error=True), key="name")
    error = failed(tmp_path, made, {"in.csv": b"a;1\n" + b"k" * 150 + b";x\n"})
    assert error.endswith("; the row is line 2 of in.csv (name=" + "k" * 100 + "...)")


def test_path_is_named_as_the_job_gives_it(tmp_path):
    (tmp_path / "data").mkdir()
    made = copying(path="data/in.csv", die_on_error=True)
    error = failed(tmp_path, made, {"data/in.csv": b"1;x\n"})
    assert error.endswith("; the row is line 1 of data/in.csv")


# ------------------------------------------------------------------
# The number is never seen
# ------------------------------------------------------------------

def test_file_written_holds_the_declared_columns_only(tmp_path):
    result = ran(tmp_path, keyed(copying(header_rows=1)), {"in.csv": b"id;amount\n1;10\n2;20\n"})
    assert result.status == "success"
    assert (tmp_path / "out.csv").read_bytes() == b"id;amount\n1;10\n2;20\n"


def test_reject_file_holds_no_number(tmp_path):
    made = job([reader(IDS, outputs=("row1", "bad")), writer(IDS, inputs=("row1",)),
                writer(None, component_id="rej", path="rej.csv", inputs=("bad",))],
               [flow("row1", "in", "out"), flow("bad", "in", "rej", "reject")])
    result = ran(tmp_path, keyed(made), {"in.csv": b"1;10\n2;x\n"})
    assert result.status == "success"
    assert (tmp_path / "rej.csv").read_bytes().splitlines()[0] == b"id;amount;errorCode;errorMessage"
