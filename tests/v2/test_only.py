"""A run for a few picked rows of one reader: ``run.only``.

The whole job runs as it always does and writes its files as it always
does. The one difference: the reader that is named hands on the picked rows
and no others. Every other reader is read whole.
"""
import json
import logging

import pytest

from src.v2 import load_job, run_job
from src.v2.cli import main
from src.v2.errors import JobRefusedError

from .components.kit import columns, flow, job, reader, through, writer
from .components.test_file_input_excel import book, excel
from .components.test_file_input_fullrow import read_lines
from .components.test_file_input_json import json_job
from .components.test_file_input_positional import cut
from .test_row_numbers import copying, ran

IDS = "id:int, amount:int"
DATA = b"id;amount\n1;10\n2;20\n3;30\n4;40\n5;50\n6;60\n7;70\n"


def only(made, source="in", **picked):
    """A job config with a ``run.only`` block for one of its readers."""
    made["run"] = {"only": {"source": source, **picked}}
    return made


def out(tmp_path, name="out.csv"):
    return (tmp_path / name).read_bytes().decode().splitlines()


def refusals(made):
    with pytest.raises(JobRefusedError) as caught:
        run_job(made)
    return [(refusal.key, refusal.reason) for refusal in caught.value.report]


# ------------------------------------------------------------------
# By the value a column holds
# ------------------------------------------------------------------

def test_run_is_for_the_row_that_holds_the_value_and_no_other(tmp_path):
    result = ran(tmp_path, only(copying(header_rows=1), where={"id": 3}), {"in.csv": DATA})
    assert result.status == "success", result.error
    assert out(tmp_path) == ["id;amount", "3;30"]
    assert result.summary()["only"] == {"source": "in", "rows": ["line 4 of in.csv"]}


def test_several_values_pick_several_rows_in_the_files_order(tmp_path):
    result = ran(tmp_path, only(copying(header_rows=1), where={"id": [6, 2]}), {"in.csv": DATA})
    assert out(tmp_path) == ["id;amount", "2;20", "6;60"]
    assert result.summary()["only"]["rows"] == ["line 3 of in.csv", "line 7 of in.csv"]


def test_two_columns_both_have_to_hold_their_value(tmp_path):
    data = b"id;amount\n1;10\n1;20\n2;20\n"
    ran(tmp_path, only(copying(header_rows=1), where={"id": 1, "amount": 20}), {"in.csv": data})
    assert out(tmp_path) == ["id;amount", "1;20"]


@pytest.mark.parametrize("schema, data, column, value, found", [
    ("id:int, name:str", b"id;name\n007;ann\n8;bob\n", "id", "7", "7;ann"),
    ("id:int, name:str", b"id;name\n7;ann\n8;bob\n", "name", "bob", "8;bob"),
    ("id:int, amt:Decimal#2", b"id;amt\n1;10.50\n2;7\n", "amt", 10.5, "1;10.50"),
    ("id:int, day:datetime@%Y-%m-%d", b"id;day\n1;2024-01-31\n2;2024-02-01\n", "day", "2024-02-01", "2;2024-02-01"),
    ("id:int, ok:bool", b"id;ok\n1;true\n2;false\n", "ok", False, "2;false"),
], ids=["a whole number written with zeros", "text", "a Decimal", "a date by the column's pattern", "true or false"])
def test_value_is_read_as_the_columns_type(tmp_path, schema, data, column, value, found):
    ran(tmp_path, only(copying(schema, header_rows=1), where={column: value}), {"in.csv": data})
    assert out(tmp_path)[1:] == [found]


# ------------------------------------------------------------------
# By the place a failure names
# ------------------------------------------------------------------

def test_row_is_picked_by_its_line_as_a_failure_names_it(tmp_path):
    result = ran(tmp_path, only(copying(header_rows=1), lines=[4]), {"in.csv": DATA})
    assert out(tmp_path) == ["id;amount", "3;30"]
    assert result.summary()["only"]["rows"] == ["line 4 of in.csv"]


def test_blank_lines_count_as_lines(tmp_path):
    ran(tmp_path, only(copying(header_rows=1), lines=[5]), {"in.csv": b"id;amount\n1;10\n\n\n2;20\n"})
    assert out(tmp_path) == ["id;amount", "2;20"]


def test_file_with_enclosures_is_picked_from_by_record(tmp_path):
    made = only(copying("id:int, note:str", header_rows=1, csv_option=True), records=[2])
    ran(tmp_path, made, {"in.csv": b'id;note\n1;"two\nlines"\n2;b\n'})
    assert out(tmp_path) == ["id;note", "2;b"]


def test_positional_file_is_picked_from_by_line_or_by_value(tmp_path):
    data = {"in.txt": b"nam  n\nabc  1\n\ndef  2\nghi  3\n"}
    ran(tmp_path, only(cut(schema="a:str, n:int", pattern="3,3", header_rows=1), lines=[4]), data)
    assert out(tmp_path)[-1] == "def;2"
    ran(tmp_path, only(cut(schema="a:str, n:int", pattern="3,3", header_rows=1), where={"a": "ghi"}), data)
    assert out(tmp_path)[-1] == "ghi;3"


def test_full_row_file_is_picked_from_by_line(tmp_path):
    made = only(read_lines(header_rows=1), lines=[3])
    result = ran(tmp_path, made, {"in.txt": b"numbers\n10\n20\n30\n"})
    assert result.status == "success", result.error
    assert result.summary()["only"]["rows"] == ["line 3 of in.txt"]


def test_json_document_is_picked_from_by_record_or_by_value(tmp_path):
    document = json.dumps({"items": [{"id": 1, "n": "a"}, {"id": 2, "n": "b"}, {"id": 3, "n": "c"}]}).encode()
    result = ran(tmp_path, only(json_job("id:int, n:str", [("id", "$.id"), ("n", "$.n")]), records=[2]),
                 {"in.json": document})
    assert out(tmp_path) == ["id;n", "2;b"]
    assert result.summary()["only"]["rows"] == ["record 2 ($.items[1]) of in.json"]
    ran(tmp_path, only(json_job("id:int, n:str", [("id", "$.id"), ("n", "$.n")]), where={"n": "c"}),
        {"in.json": document})
    assert out(tmp_path) == ["id;n", "3;c"]


def test_workbook_is_picked_from_by_sheet_and_row_or_by_value(tmp_path):
    sheets = book({"first": [["id", "n"], [1, 10], [2, 20]], "second": [["id", "n"], [3, 30], [4, 40]]})
    made = only(excel("id:int, n:int", header=1, all_sheets=True), rows=[3], sheet="second")
    result = ran(tmp_path, made, {"in.xlsx": sheets})
    assert out(tmp_path) == ["4;40"]
    assert result.summary()["only"]["rows"] == ["row 3 of sheet 'second' of in.xlsx"]
    ran(tmp_path, only(excel("id:int, n:int", header=1, all_sheets=True), where={"id": 2}), {"in.xlsx": sheets})
    assert out(tmp_path) == ["2;20"]


# ------------------------------------------------------------------
# The rest of the job is as in any run
# ------------------------------------------------------------------

def test_other_readers_are_read_whole(tmp_path):
    join = {"id": "it", "type": "Join", "inputs": ["row1", "row2"], "outputs": ["hit"],
            "config": {"join_key": [{"input_column": "id", "lookup_column": "id"}], "use_inner_join": True,
                       "use_lookup_cols": True, "lookup_cols": [{"lookup_column": "name", "output_column": "name"}]},
            "schema": {"input": columns("id:int, name:str"), "output": columns("id:int, amount:int, name:str")}}
    made = job([reader(IDS, header_rows=1), reader("id:int, name:str", "names", "names.csv", ("row2",), header_rows=1),
                join, writer("id:int, amount:int, name:str", inputs=("hit",))],
               [flow("row1", "in", "it"), flow("row2", "names", "it"), flow("hit", "it", "out")])
    names = b"id;name\n1;ann\n2;bob\n3;cy\n4;di\n"
    ran(tmp_path, only(made, where={"id": 3}), {"in.csv": DATA, "names.csv": names})
    assert out(tmp_path) == ["id;amount;name", "3;30;cy"]


def test_every_stage_runs_and_a_later_stage_reads_what_this_run_wrote(tmp_path):
    # Stage one copies the picked row to out.csv; stage two reads out.csv and writes it on to last.csv.
    made = job(
        [reader(IDS, header_rows=1), writer(IDS, inputs=("row1",)),
         reader(IDS, "again", "out.csv", ("row9",), header_rows=1), writer(IDS, "last", "last.csv", ("row9",))],
        [flow("row1", "in", "out"), flow("row9", "again", "last")],
        triggers=[{"type": "OnSubjobOk", "from": "in", "to": "again"}],
    )
    result = ran(tmp_path, only(made, where={"id": 5}), {"in.csv": DATA})
    assert result.status == "success", result.error
    assert out(tmp_path, "last.csv") == ["id;amount", "5;50"] and result.rows == {"out": 1, "last": 1}


def test_row_counts_are_of_the_picked_rows(tmp_path):
    made = only(copying(header_rows=1), where={"id": [1, 2]})
    made["run"]["row_counts"] = True
    result = ran(tmp_path, made, {"in.csv": DATA})
    assert result.counts["in"] == {"NB_LINE": 2, "NB_LINE_OK": 2, "NB_LINE_REJECT": 0}


def test_row_past_the_readers_own_limit_is_not_there_to_be_picked(tmp_path):
    result = ran(tmp_path, only(copying(header_rows=1, limit=2), where={"id": 5}), {"in.csv": DATA})
    assert result.status == "failed" and result.error == "no row of 'in' has id=5"


# ------------------------------------------------------------------
# Rows with something wrong with them
# ------------------------------------------------------------------

BAD = b"id;amount\n1;10\n2;x\n3;30\n4;y\n"


def test_picked_row_fails_the_job_as_it_does_in_the_full_run(tmp_path):
    result = ran(tmp_path, only(copying(header_rows=1, die_on_error=True), lines=[3]), {"in.csv": BAD})
    assert result.status == "failed"
    assert result.error == ("Schema/coercion failed for 1 row(s); first error: Column 'amount': could not convert "
                            "string to float: 'x'; the row is line 3 of in.csv")


def test_row_that_is_wrong_elsewhere_in_the_file_does_not_stop_a_run_for_another(tmp_path):
    result = ran(tmp_path, only(copying(header_rows=1, die_on_error=True), where={"id": 3}), {"in.csv": BAD})
    assert result.status == "success", result.error
    assert out(tmp_path) == ["id;amount", "3;30"]


def test_row_the_reader_turns_away_can_be_picked_by_a_value_too(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    result = ran(tmp_path, only(copying(header_rows=1), where={"id": 4}), {"in.csv": BAD})
    assert result.status == "success" and out(tmp_path) == ["id;amount"]
    said = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert said == ["[in] 1 row was dropped (no flow takes this component's rejects): Column 'amount': could not "
                    "convert string to float: 'y'; the row is line 5 of in.csv"]


# ------------------------------------------------------------------
# What stops the run
# ------------------------------------------------------------------

def test_no_row_holds_the_value(tmp_path):
    result = ran(tmp_path, only(copying(header_rows=1), where={"id": [3, 99]}), {"in.csv": DATA})
    assert result.status == "failed" and result.failed_component == "in"
    assert result.error == "no row of 'in' has id=99"
    assert not (tmp_path / "out.csv").exists()


def test_no_row_is_at_the_place(tmp_path):
    result = ran(tmp_path, only(copying(header_rows=1), lines=[4, 40]), {"in.csv": DATA})
    assert result.status == "failed" and result.error == "'in' has no row at line 40"


def test_line_of_the_header_is_no_row(tmp_path):
    result = ran(tmp_path, only(copying(header_rows=1), lines=[1]), {"in.csv": DATA})
    assert result.status == "failed" and result.error == "'in' has no row at line 1: its first 1 line(s) are the header"


def test_more_rows_than_a_run_may_be_for(tmp_path):
    data = b"id;amount\n" + b"".join(b"9;%d\n" % n for n in range(8))
    result = ran(tmp_path, only(copying(header_rows=1), where={"id": 9}), {"in.csv": data})
    assert result.status == "failed"
    assert result.error == "8 rows of 'in' have id=9; a run can be for 5 rows at most"


def test_what_is_wrong_with_the_asking_refuses_the_job(tmp_path):
    def asked(**picked):
        return refusals(only(copying("id:int, amount:int, day:datetime@%Y-%m-%d", header_rows=1), **picked))

    assert refusals(only(copying(header_rows=1), source="nope", where={"id": 1})) == [
        ("run.only.source", "there is no component 'nope'; the job's readers are: in")]
    assert refusals(only(copying(header_rows=1), source="out", where={"id": 1})) == [
        ("run.only.source", "'out' is not a reader; the job's readers are: in")]
    assert asked(where={"nope": 1}) == [
        ("run.only.where", "'in' has no column 'nope'; its columns are: id, amount, day")]
    assert asked(where={"id": "abc"}) == [("run.only.where", "column 'id' is int; 'abc' cannot be read as that")]
    assert asked(where={"day": "31/01/2024"}) == [
        ("run.only.where", "column 'day' is datetime; '31/01/2024' cannot be read as that")]
    assert asked(records=[2]) == [("run.only.records", "'in' is read line by line: pick its rows with `lines`")]
    assert asked(lines=[2], sheet="Q1") == [("run.only.sheet", "a sheet is named together with `rows`")]
    assert asked(where={"id": 1}, lines=[2]) == [
        ("run.only", "say which rows in one way: `where`, or one of `lines`, `records`, `rows`")]
    assert asked(lines=[1, 2, 3, 4, 5, 6]) == [("run.only.lines", "6 rows are named; a run can be for 5 rows at most")]
    assert asked(lines=[0]) == [("run.only.lines", "0 is not the number of a row; rows are numbered from 1")]


def test_file_read_with_enclosures_is_not_picked_from_by_line(tmp_path):
    made = only(copying("id:int, note:str", header_rows=1, csv_option=True), lines=[2])
    assert refusals(made) == [
        ("run.only.lines", "'in' is read with `csv_option`, where a record can span lines: pick its rows with `records`")]


# ------------------------------------------------------------------
# On the command line
# ------------------------------------------------------------------

def job_on_disk(tmp_path, **run):
    (tmp_path / "in.csv").write_bytes(DATA)
    made = job([reader(IDS, path=str(tmp_path / "in.csv"), header_rows=1),
                writer(IDS, path=str(tmp_path / "out.csv"), inputs=("row1",))], [flow("row1", "in", "out")])
    if run:
        made["run"] = run
    (tmp_path / "job.json").write_text(json.dumps(made))
    return str(tmp_path / "job.json")


@pytest.mark.parametrize("asked, written", [
    ("in:id=3", ["3;30"]),
    ("in:id=3,6", ["3;30", "6;60"]),
    ("in:line=4", ["3;30"]),
    ("in:line=4,5", ["3;30", "4;40"]),
    ('{"source": "in", "where": {"amount": [70]}}', ["7;70"]),
])
def test_command_line_names_the_rows(tmp_path, capsys, asked, written):
    assert main([job_on_disk(tmp_path), "--only", asked]) == 0
    assert out(tmp_path)[1:] == written


def test_command_lines_rows_win_over_the_job_configs(tmp_path, capsys):
    path = job_on_disk(tmp_path, only={"source": "in", "where": {"id": 1}})
    assert main([path, "--only", "in:id=2"]) == 0
    assert out(tmp_path)[1:] == ["2;20"]
    assert "run settings: only in where id=2 (command line)" in capsys.readouterr().out


def test_command_line_that_names_rows_badly_is_a_usage_error(tmp_path, capsys):
    assert main([job_on_disk(tmp_path), "--only", "in"]) == 2
    assert "--only" in capsys.readouterr().err
    assert main([job_on_disk(tmp_path), "--only", "in:id=abc"]) == 2
    assert "cannot be read as that" in capsys.readouterr().err


def test_word_that_is_a_place_and_a_column_has_to_be_said_in_full(tmp_path, capsys):
    (tmp_path / "in.csv").write_bytes(b"line;amount\n1;10\n")
    made = job([reader("line:int, amount:int", path=str(tmp_path / "in.csv"), header_rows=1),
                writer("line:int, amount:int", path=str(tmp_path / "out.csv"), inputs=("row1",))],
               [flow("row1", "in", "out")])
    (tmp_path / "job.json").write_text(json.dumps(made))
    assert main([str(tmp_path / "job.json"), "--only", "in:line=1"]) == 2
    assert "'line' is a column of 'in' and a place as well" in capsys.readouterr().err


# ------------------------------------------------------------------
# More of what can be asked wrongly
# ------------------------------------------------------------------

@pytest.mark.parametrize("picked, key, said", [
    ({"lines": []}, "run.only.lines", "names no row"),
    ({"where": {}}, "run.only.where", "names no column"),
    ({"where": {"id": [None]}}, "run.only.where", "column 'id': give the value a picked row holds, or a list of such values"),
    ({"where": {"id": [[1]]}}, "run.only.where", "column 'id': give the value a picked row holds, or a list of such values"),
])
def test_way_of_picking_that_names_nothing_refuses_the_job(picked, key, said):
    found = refusals(only(copying(header_rows=1), **picked))
    assert (key, said) in found


def test_no_row_holds_both_values_of_two_columns(tmp_path):
    result = ran(tmp_path, only(copying(header_rows=1), where={"id": 1, "amount": 20}), {"in.csv": DATA})
    assert result.status == "failed" and result.error == "no row of 'in' has id=1 and amount=20"


def test_workbook_is_asked_for_a_row_of_a_sheet_in_its_own_words(tmp_path):
    sheets = book({"first": [["id", "n"], [1, 10], [2, 20]], "second": [["id", "n"], [3, 30]]})

    def asked(**picked):
        return ran(tmp_path, only(excel("id:int, n:int", header=1, all_sheets=True), **picked), {"in.xlsx": sheets})

    assert asked(rows=[2]).error == "'in' has no row at row 2: say which sheet; those with rows are: first, second"
    assert asked(rows=[2], sheet="third").error == (
        "'in' has no row at row (of sheet 'third') 2: no sheet 'third' was read with rows; "
        "those with rows are: first, second")
    assert asked(rows=[9], sheet="first").error == (
        "'in' has no row at row (of sheet 'first') 9: the rows read from sheet 'first' are 2 to 3")
    assert asked(rows=[1], sheet="first").error == (
        "'in' has no row at row (of sheet 'first') 1: the rows read from sheet 'first' are 2 to 3")
    assert refusals(only(excel("id:int, n:int", header=1), lines=[2])) == [
        ("run.only.lines", "'in' reads the sheets of a workbook: pick its rows with `rows`")]


def test_workbook_column_held_as_another_type_than_declared_is_still_picked_by(tmp_path):
    # The sheet holds numbers in a column the job declares as text.
    sheets = book({"only": [["id", "n"], [1, 10], [2, 20]]})
    result = ran(tmp_path, only(excel("id:str, n:int", header=1), where={"id": "2"}), {"in.xlsx": sheets})
    assert result.status == "success", result.error
    assert out(tmp_path) == ["2;20"]


def test_json_document_is_not_picked_from_by_line():
    made = only(json_job("id:int, n:str", [("id", "$.id"), ("n", "$.n")]), lines=[2])
    assert refusals(made) == [
        ("run.only.lines", "'in' reads the records of a document: pick its rows with `records`")]


def test_reader_that_no_stage_comes_to_read_is_said_and_the_summary_names_no_row(tmp_path, caplog):
    # The second stage runs only when the first wrote nothing, which it never does here.
    made = job(
        [reader(IDS, header_rows=1), writer(IDS, inputs=("row1",)),
         reader(IDS, "later", "later.csv", ("row9",), header_rows=1), writer(IDS, "last", "last.csv", ("row9",))],
        [flow("row1", "in", "out"), flow("row9", "later", "last")],
        triggers=[{"type": "RunIf", "from": "out", "to": "later",
                   "condition": '((Integer)globalMap.get("out_NB_LINE")) == 0'}],
    )
    caplog.set_level(logging.WARNING, logger="src.v2")
    result = ran(tmp_path, only(made, source="later", where={"id": 1}), {"in.csv": DATA, "later.csv": DATA})
    assert result.status == "success" and result.summary()["only"] == {"source": "later", "rows": []}
    assert [record.getMessage() for record in caplog.records] == [
        "[t] the run was to be for picked rows of 'later', which no stage of this run came to read: "
        "every row of every other reader was run"]


def test_reader_that_cannot_be_read_to_find_the_rows_fails_the_job_at_that_reader(tmp_path, monkeypatch):
    import src.v2.engine.runner as runner

    def gone(plans, **kwargs):
        raise OSError("the file is gone")

    monkeypatch.setenv("V2_SAFE_READ", "1")
    monkeypatch.setattr(runner.pl, "collect_all", gone)
    result = ran(tmp_path, only(copying(header_rows=1), where={"id": 3}), {"in.csv": DATA})
    assert result.status == "failed" and result.failed_component == "in" and result.error == "the file is gone"


@pytest.mark.parametrize("asked, said", [
    ('{"source": "in", "where"', "not JSON"),
    ("in:line=four", "a line is a whole number, counted from 1"),
    ('{"source": "in", "where": {}}', "names no column"),
    ("in:=3", "expected READER:COLUMN=VALUE"),
])
def test_command_line_says_what_is_wrong_with_the_rows_it_was_given(tmp_path, capsys, asked, said):
    assert main([job_on_disk(tmp_path), "--only", asked]) == 2
    assert said in capsys.readouterr().err
    assert not (tmp_path / "out.csv").exists()
