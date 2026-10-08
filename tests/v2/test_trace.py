"""What every component did with the picked rows: ``run.trace``.

A run for picked rows (``run.only``) that asks for a trace has it in its
result: for each component whose rows come from the picked rows, every
output with its columns and its rows, across all the stages of the job. The
log has a short version.
"""
import json
import logging

import pytest

from src.v2 import run_job
from src.v2.cli import main
from src.v2.errors import JobRefusedError

from .components.kit import columns, flow, job, reader, through, writer
from .components.test_map import config as map_config
from .components.test_map import out as map_out
from .components.test_python_dataframe import chained, coded
from .test_only import DATA, IDS, only
from .test_row_numbers import copying, keyed, ran

INT_COLUMNS = [{"name": "id", "type": "int"}, {"name": "amount", "type": "int"}]


def traced(tmp_path, made, files, **picked):
    """Run a job for picked rows with a trace; returns (how it ended, the trace by component id)."""
    made = only(made, **picked)
    made["run"]["trace"] = True
    result = ran(tmp_path, made, files)
    return result, {entry["id"]: entry for entry in result.summary()["trace"]}


def rows_of(entry, port="main"):
    return entry["outputs"][port]["data"]


# ------------------------------------------------------------------
# What the trace holds
# ------------------------------------------------------------------

def test_trace_holds_every_output_of_every_component_the_row_went_through(tmp_path):
    result, trace = traced(tmp_path, copying(header_rows=1), {"in.csv": DATA}, where={"id": 3})
    assert result.status == "success", result.error
    assert result.summary()["trace"] == [
        {"id": "in", "type": "FileInputDelimited", "outputs": {
            "main": {"rows": 1, "columns": INT_COLUMNS, "data": [["3", "30"]], "from": ["line 4 of in.csv"]},
            "reject": {"rows": 0, "data": [], "from": [], "columns": [
                {"name": "id", "type": "str"}, {"name": "amount", "type": "str"},
                {"name": "errorCode", "type": "str"}, {"name": "errorMessage", "type": "str"}]},
        }},
        {"id": "out", "type": "FileOutputDelimited", "path": "out.csv", "written": True, "rows": 1,
         "columns": INT_COLUMNS, "data": [["3", "30"]], "from": ["line 4 of in.csv"]},
    ]
    assert json.loads(json.dumps(result.summary())) == result.summary()
    assert (tmp_path / "out.csv").read_bytes() == b"id;amount\n3;30\n"


def test_row_names_the_picked_row_it_came_from_with_its_key(tmp_path):
    _, trace = traced(tmp_path, keyed(copying(header_rows=1)), {"in.csv": DATA}, where={"id": [5, 2]})
    assert trace["in"]["outputs"]["main"]["from"] == ["line 3 of in.csv (id=2)", "line 6 of in.csv (id=5)"]
    assert rows_of(trace["in"]) == [["2", "20"], ["5", "50"]]


def test_values_are_the_text_a_file_would_hold_and_a_missing_one_is_null(tmp_path):
    schema = "id:int, amt:Decimal#2, day:datetime@%Y-%m-%d, ok:bool, f:float, name:str"
    data = b"id;amt;day;ok;f;name\n1;10.5;2024-01-31;true;2.50;ann\n2;;;false;;\n"
    _, trace = traced(tmp_path, copying(schema, header_rows=1), {"in.csv": data}, where={"id": [1, 2]})
    assert trace["in"]["outputs"]["main"]["columns"] == [
        {"name": "id", "type": "int"}, {"name": "amt", "type": "Decimal"}, {"name": "day", "type": "datetime"},
        {"name": "ok", "type": "bool"}, {"name": "f", "type": "float"}, {"name": "name", "type": "str"}]
    assert rows_of(trace["in"]) == [
        ["1", "10.50", "2024-01-31", "true", "2.5", "ann"],
        ["2", None, None, "false", None, ""],
    ]


# ------------------------------------------------------------------
# Component by component
# ------------------------------------------------------------------

def test_row_a_filter_turns_away_is_seen_on_its_reject_output_and_goes_no_further(tmp_path):
    step = {"type": "FilterRows", "config": {"conditions": [{"column": "amount", "operator": ">", "function": "", "value": "35"}]}}
    result, trace = traced(tmp_path, through(step, IDS), {"in.csv": DATA}, where={"id": 3})
    assert result.status == "success"
    assert trace["it"]["outputs"]["main"]["rows"] == 0
    assert rows_of(trace["it"], "reject")[0][:2] == ["3", "30"]
    assert trace["out"]["rows"] == 0 and trace["out"]["data"] == []


def test_map_shows_what_each_of_its_outputs_holds(tmp_path):
    made = through({"type": "PyMap", "config": map_config([
        map_out("row2", [("id", "row1.id", "int"), ("twice", "row1.amount * 2", "int"), ("who", "'n' + str(row1.id)", "str")]),
    ]), "schema": {"inputs": {"row1": columns(IDS)}}}, IDS, "id:int, twice:int, who:str")
    _, trace = traced(tmp_path, made, {"in.csv": DATA}, where={"id": 3})
    assert trace["it"]["outputs"] == {"row2": {
        "rows": 1, "columns": [{"name": "id", "type": "int"}, {"name": "twice", "type": "int"},
                               {"name": "who", "type": "str"}],
        "data": [["3", "60", "n3"]], "from": ["line 4 of in.csv"]}}


def joined_with_names():
    join = {"id": "it", "type": "Join", "inputs": ["row1", "row2"], "outputs": ["hit"],
            "config": {"join_key": [{"input_column": "id", "lookup_column": "id"}], "use_inner_join": True,
                       "use_lookup_cols": True, "lookup_cols": [{"lookup_column": "name", "output_column": "name"}]},
            "schema": {"input": columns("id:int, name:str"), "output": columns("id:int, amount:int, name:str")}}
    return job([reader(IDS, header_rows=1), reader("id:int, name:str", "names", "names.csv", ("row2",), header_rows=1),
                join, writer("id:int, amount:int, name:str", inputs=("hit",))],
               [flow("row1", "in", "it"), flow("row2", "names", "it"), flow("hit", "it", "out")])


def test_lookup_is_read_whole_and_not_listed_and_what_it_gave_is_in_the_joins_output(tmp_path):
    names = b"id;name\n1;ann\n2;bob\n3;cy\n4;di\n"
    _, trace = traced(tmp_path, joined_with_names(), {"in.csv": DATA, "names.csv": names}, where={"id": 3})
    assert trace["names"] == {"id": "names", "type": "FileInputDelimited", "outputs": None,
                              "why": "its rows do not come from the picked rows"}
    assert rows_of(trace["it"]) == [["3", "30", "cy"]]
    assert list(trace) == ["in", "names", "it", "out"]


def test_group_of_the_picked_rows_says_how_many_went_into_it(tmp_path):
    grouped = {"groupbys": [{"input_column": "amount", "output_column": "amount"}],
               "operations": [{"output_column": "id", "function": "max", "input_column": "id"}]}
    made = through({"type": "AggregateRow", "config": grouped}, IDS)
    data = b"id;amount\n1;10\n2;10\n3;30\n"
    _, trace = traced(tmp_path, made, {"in.csv": data}, where={"amount": 10})
    assert rows_of(trace["it"]) == [["2", "10"]]
    assert trace["it"]["outputs"]["main"]["from"] == ["line 2 of in.csv, the first of 2 rows that were combined"]


def test_every_row_a_normalize_makes_of_the_picked_row_is_listed(tmp_path):
    made = through({"type": "Normalize", "config": {"normalize_column": "tags"}}, "id:int, tags:str")
    _, trace = traced(tmp_path, made, {"in.csv": b"id;tags\n1;a\n2;x,y,z\n"}, where={"id": 2})
    assert rows_of(trace["it"]) == [["2", "x"], ["2", "y"], ["2", "z"]]
    assert trace["it"]["outputs"]["main"]["from"] == ["line 3 of in.csv"] * 3


def test_output_of_many_rows_lists_the_first_fifty_and_says_how_many_there_are(tmp_path):
    made = through({"type": "Normalize", "config": {"normalize_column": "tags"}}, "id:int, tags:str")
    data = b"id;tags\n1;" + b",".join(b"t%d" % n for n in range(60)) + b"\n"
    _, trace = traced(tmp_path, made, {"in.csv": data}, where={"id": 1})
    listed = trace["it"]["outputs"]["main"]
    assert listed["rows"] == 60 and len(listed["data"]) == 50 and listed["data"][49] == ["1", "t49"]
    assert trace["out"]["rows"] == 60 and len(trace["out"]["data"]) == 50
    assert len((tmp_path / "out.csv").read_bytes().splitlines()) == 61


def test_python_code_is_shown_by_what_it_was_handed_and_what_it_gave_back(tmp_path):
    result, trace = traced(tmp_path, coded("df['amount'] = df['amount'] * 2", schema=IDS), {"in.csv": DATA},
                           where={"id": 3})
    assert result.status == "success", result.error
    assert rows_of(trace["in"]) == [["3", "30"]]
    assert trace["it"]["outputs"]["main"]["data"] == [["3", "60"]] and trace["it"]["outputs"]["main"]["from"] == [None]


# ------------------------------------------------------------------
# Across the stages of a job
# ------------------------------------------------------------------

def two_stages(second_reads):
    """Stage one copies the picked rows to out.csv; stage two reads a file and writes it on to last.csv."""
    return job(
        [reader(IDS, header_rows=1), writer(IDS, inputs=("row1",)),
         reader(IDS, "again", second_reads, ("row9",), header_rows=1), writer(IDS, "last", "last.csv", ("row9",))],
        [flow("row1", "in", "out"), flow("row9", "again", "last")],
        triggers=[{"type": "OnSubjobOk", "from": "in", "to": "again"}],
    )


def test_later_stage_that_reads_what_this_run_wrote_is_traced_too(tmp_path):
    result, trace = traced(tmp_path, two_stages("out.csv"), {"in.csv": DATA}, where={"id": 5})
    assert result.status == "success", result.error
    assert rows_of(trace["again"]) == [["5", "50"]]
    assert trace["again"]["outputs"]["main"]["from"] == ["line 2 of out.csv"]
    assert trace["last"]["data"] == [["5", "50"]] and list(trace) == ["in", "out", "again", "last"]


def test_stage_whose_rows_are_not_the_picked_ones_runs_as_ever_and_is_not_listed(tmp_path):
    other = b"id;amount\n" + b"".join(b"%d;1\n" % n for n in range(300))
    result, trace = traced(tmp_path, two_stages("other.csv"), {"in.csv": DATA, "other.csv": other}, where={"id": 5})
    assert result.status == "success" and result.rows == {"out": 1, "last": 300}
    assert trace["again"]["outputs"] is None and trace["last"] == {
        "id": "last", "type": "FileOutputDelimited", "outputs": None,
        "why": "its rows do not come from the picked rows"}


# ------------------------------------------------------------------
# A row the job fails on
# ------------------------------------------------------------------

def test_trace_of_a_row_the_job_fails_on_goes_as_far_as_the_failure_and_holds_it(tmp_path):
    made = through({"type": "PyMap", "config": map_config([
        map_out("row2", [("id", "row1.id", "int"), ("n", "int(row1.code)", "int")]),
    ]), "schema": {"inputs": {"row1": columns("id:int, code:str")}}}, "id:int, code:str", "id:int, n:int")
    result, trace = traced(tmp_path, made, {"in.csv": b"id;code\n1;10\n2;x320\n3;30\n"}, where={"id": 2})
    assert result.status == "failed" and result.failed_component == "it"
    assert rows_of(trace["in"]) == [["2", "x320"]]
    assert trace["it"] == {"id": "it", "type": "PyMap", "error": result.error}
    assert result.error.endswith("the row is line 3 of in.csv") and "out" not in trace


def test_reader_that_stops_the_job_on_the_picked_row_is_where_the_trace_ends(tmp_path):
    result, trace = traced(tmp_path, copying(header_rows=1, die_on_error=True),
                           {"in.csv": b"id;amount\n1;10\n2;x\n"}, lines=[3])
    assert result.status == "failed"
    assert trace == {"in": {"id": "in", "type": "FileInputDelimited", "error": result.error}}


# ------------------------------------------------------------------
# Asking for it
# ------------------------------------------------------------------

def test_trace_is_asked_for_apart_from_the_rows(tmp_path):
    result = ran(tmp_path, only(copying(header_rows=1), where={"id": 3}), {"in.csv": DATA})
    assert "trace" not in result.summary()


def test_trace_without_picked_rows_is_refused(tmp_path):
    made = copying(header_rows=1)
    made["run"] = {"trace": True}
    with pytest.raises(JobRefusedError) as caught:
        run_job(made)
    assert [(refusal.key, refusal.reason) for refusal in caught.value.report] == [
        ("run.trace", "a trace is of the rows `only` picks; say which rows")]


def test_run_without_a_trace_is_handed_to_polars_once(tmp_path, monkeypatch):
    import src.v2.engine.runner as runner

    made, run = [], runner.pl.collect_all

    def counted(plans, **kwargs):
        made.append(len(plans))
        return run(plans, **kwargs)

    monkeypatch.setattr(runner.pl, "collect_all", counted)
    assert ran(tmp_path, copying(header_rows=1), {"in.csv": DATA}).status == "success"
    assert made == [1]


def test_command_line_asks_for_a_trace_and_the_log_has_its_short_version(tmp_path, capsys):
    (tmp_path / "in.csv").write_bytes(DATA)
    made = job([reader(IDS, path=str(tmp_path / "in.csv"), header_rows=1),
                {"id": "it", "type": "PyMap", "inputs": ["row1"], "outputs": ["row2"],
                 "config": map_config([map_out("row2", [("id", "row1.id", "int"), ("amount", "row1.amount + 1", "int"),
                                                        ("who", "'n' + str(row1.id)", "str")])]),
                 "schema": {"inputs": {"row1": columns(IDS)}}},
                writer("id:int, amount:int, who:str", path=str(tmp_path / "out.csv"))],
               [flow("row1", "in", "it"), flow("row2", "it", "out")])
    (tmp_path / "job.json").write_text(json.dumps(made))
    assert main([str(tmp_path / "job.json"), "--only", "in:id=3", "--trace"]) == 0
    printed = capsys.readouterr().out
    summary = json.loads(printed[printed.index("\n{"):])
    assert [entry["id"] for entry in summary["trace"]] == ["in", "it", "out"]
    said = [line.split(" - ", 1)[1] for line in printed.splitlines() if " trace: " in line]
    assert said == [
        "[in] trace: main 1 row, reject 0 rows",
        "[it] trace: row2 1 row; added who=n3; changed amount: 30 -> 31",
        f"[out] trace: 1 row for {tmp_path / 'out.csv'}",
    ]


def test_log_says_of_each_picked_row_what_changed_for_it(tmp_path, caplog):
    made = through({"type": "PyMap", "config": map_config([
        map_out("row2", [("id", "row1.id", "int"), ("amount", "row1.amount * 2", "int")]),
    ]), "schema": {"inputs": {"row1": columns(IDS)}}}, IDS)
    caplog.set_level(logging.INFO, logger="src.v2")
    traced(tmp_path, made, {"in.csv": DATA}, where={"id": [2, 3]})
    said = [record.getMessage() for record in caplog.records if record.getMessage().startswith("[it] trace")]
    assert said == ["[it] trace: row2 2 rows; line 3 of in.csv: changed amount: 20 -> 40; "
                    "line 4 of in.csv: changed amount: 30 -> 60"]


def test_log_says_which_output_a_change_is_on_when_a_component_has_several(tmp_path, caplog):
    made = job(
        [reader(IDS, header_rows=1),
         {"id": "it", "type": "PyMap", "inputs": ["row1"], "outputs": ["a", "b"],
          "config": map_config([map_out("a", [("id", "row1.id", "int"), ("big", "row1.amount * 10", "int")]),
                                map_out("b", [("id", "row1.id", "int"), ("amount", "row1.amount + 1", "int")])]),
          "schema": {"inputs": {"row1": columns(IDS)}}},
         writer("id:int, big:int", "out_a", "a.csv", ("a",)), writer(IDS, "out_b", "b.csv", ("b",))],
        [flow("row1", "in", "it"), flow("a", "it", "out_a"), flow("b", "it", "out_b")])
    caplog.set_level(logging.INFO, logger="src.v2")
    traced(tmp_path, made, {"in.csv": DATA}, where={"id": 3})
    said = [record.getMessage() for record in caplog.records if record.getMessage().startswith("[it] trace")]
    assert said == ["[it] trace: a 1 row, b 1 row; a: added big=300; b: changed amount: 30 -> 31"]


def test_log_names_a_dozen_columns_at_most_and_counts_the_rest(tmp_path, caplog):
    wide = [("id", "row1.id", "int")] + [(f"c{n}", f"row1.amount + {n}", "int") for n in range(15)]
    made = through({"type": "PyMap", "config": map_config([map_out("row2", wide)]),
                    "schema": {"inputs": {"row1": columns(IDS)}}}, IDS, ", ".join(f"{name}:int" for name, _, _ in wide))
    caplog.set_level(logging.INFO, logger="src.v2")
    _, trace = traced(tmp_path, made, {"in.csv": DATA}, where={"id": 3})
    said, = [record.getMessage() for record in caplog.records if record.getMessage().startswith("[it] trace")]
    assert said == ("[it] trace: row2 1 row; added " + ", ".join(f"c{n}={30 + n}" for n in range(12)) + " and 3 more")
    assert len(rows_of(trace["it"], "row2")[0]) == 16


# ------------------------------------------------------------------
# Rows as the trace holds them
# ------------------------------------------------------------------

def test_types_and_text_of_every_kind_of_column():
    import datetime
    from decimal import Decimal

    import polars as pl

    from src.v2.engine.tracing import as_text, type_name
    from src.v2.job.model import Column

    rows = pl.DataFrame({
        "f": [2.5, None], "d": [datetime.date(2024, 1, 31), None], "t": [datetime.time(9, 30), None],
        "m": [Decimal("1.50"), None],
    }, schema={"f": pl.Float64, "d": pl.Date, "t": pl.Time, "m": pl.Decimal(38, 2)})
    assert [type_name(dtype) for dtype in rows.dtypes] == ["float", "date", "Time", "Decimal"]
    assert as_text(rows).rows() == [("2.5", "2024-01-31", "09:30:00", "1.50"), (None, None, None, None)]
    # A component that declares the columns writes a date by its pattern and a Decimal to its places.
    declared = [Column(name="d", type="date", date_pattern="%d/%m/%Y"), Column(name="m", type="Decimal")]
    assert as_text(rows, declared).rows()[0] == ("2.5", "31/01/2024", "09:30:00", "1.5")


def test_log_says_nothing_of_a_row_that_was_not_among_those_that_came_in(tmp_path, caplog):
    # The reader's rejects are put after its rows: the row that was turned away is new to what came in by main.
    made = job([reader(IDS, outputs=("row1", "bad"), header_rows=1),
                {"id": "it", "type": "Unite", "config": {}, "inputs": ["row1", "bad"], "outputs": ["all"],
                 "schema": {"input": columns(IDS), "output": columns("id:str, amount:str")}},
                writer("id:str, amount:str", inputs=("all",))],
               [flow("row1", "in", "it"), flow("bad", "in", "it", "reject"), flow("all", "it", "out")])
    caplog.set_level(logging.INFO, logger="src.v2")
    result, trace = traced(tmp_path, made, {"in.csv": b"id;amount\n1;10\n2;x\n"}, where={"id": [1, 2]})
    assert result.status == "success", result.error
    assert [row[:2] for row in rows_of(trace["it"])] == [["1", "10"], ["2", "x"]]
    said = [record.getMessage() for record in caplog.records if record.getMessage().startswith("[it] trace")]
    # Of the first row it says the two columns the unite gave it from the reject flow; of the second, nothing.
    assert said == ["[it] trace: main 2 rows; line 2 of in.csv: added errorCode_user=(nothing), "
                    "errorMessage_user=(nothing)"]


# ------------------------------------------------------------------
# What a second reader of this work found
# ------------------------------------------------------------------

def test_file_another_stage_wrote_over_with_other_rows_is_no_longer_the_picked_rows(tmp_path):
    # Stage one writes the picked row to out.csv, stage two writes 300 other rows over it, stage three reads it.
    made = job(
        [reader(IDS, header_rows=1), writer(IDS, inputs=("row1",)),
         reader(IDS, "other", "other.csv", ("row5",), header_rows=1), writer(IDS, "over", "out.csv", ("row5",)),
         reader(IDS, "again", "out.csv", ("row9",), header_rows=1), writer(IDS, "last", "last.csv", ("row9",))],
        [flow("row1", "in", "out"), flow("row5", "other", "over"), flow("row9", "again", "last")],
        triggers=[{"type": "OnSubjobOk", "from": "in", "to": "other"},
                  {"type": "OnSubjobOk", "from": "other", "to": "again"}],
    )
    other = b"id;amount\n" + b"".join(b"%d;1\n" % n for n in range(300))
    result, trace = traced(tmp_path, made, {"in.csv": DATA, "other.csv": other}, where={"id": 5})
    assert result.status == "success" and result.rows == {"out": 1, "over": 300, "last": 300}
    assert trace["again"]["outputs"] is None and trace["last"]["outputs"] is None


def test_file_this_run_wrote_is_known_by_whatever_path_a_later_stage_reads_it_by(tmp_path):
    # The second stage reads the file through a link to its folder.
    (tmp_path / "link").symlink_to(tmp_path, target_is_directory=True)
    made = two_stages(str(tmp_path / "link" / "out.csv"))
    result, trace = traced(tmp_path, made, {"in.csv": DATA}, where={"id": 5})
    assert result.status == "success", result.error
    assert rows_of(trace["again"]) == [["5", "50"]]


def test_columns_of_kinds_only_code_can_make_are_shown_as_python_prints_them():
    import datetime

    import polars as pl

    from src.v2.engine.tracing import as_text

    rows = pl.DataFrame({"tags": [["a", "b"], None], "took": [datetime.timedelta(seconds=90), None], "raw": [b"\xff", None]})
    assert as_text(rows).rows() == [("['a', 'b']", "0:01:30", "b'\\xff'"), (None, None, None)]


def test_file_output_shows_its_rows_as_the_file_holds_them(tmp_path):
    made = copying("id:int, day:datetime@%d/%m/%Y, amt:Decimal", header_rows=1)
    _, trace = traced(tmp_path, made, {"in.csv": b"id;day;amt\n1;31/01/2024;1.5\n"}, where={"id": 1})
    assert (tmp_path / "out.csv").read_bytes().splitlines()[1] == b"1;31/01/2024;1.5"
    assert trace["out"]["data"] == [["1", "31/01/2024", "1.5"]]
    assert rows_of(trace["in"]) == [["1", "31/01/2024", "1.5"]]


def test_lookup_of_a_map_is_not_listed_and_what_it_gave_is_in_the_maps_output(tmp_path):
    from .components.test_map import lookup as map_lookup
    from .components.test_map import mapping

    kept = [("id", "row1.id", "int"), ("name", "names.name", "str")]
    made = mapping(map_config([map_out("o", kept)], lookups=[map_lookup("names", [("id", "row1.id")])]),
                   {"row1": IDS, "names": "id:int, name:str"}, {"o": "id:int, name:str"})
    files = {"row1.csv": DATA, "names.csv": b"id;name\n3;cy\n4;di\n"}
    made = only(made, source="in_row1", where={"id": 3})
    made["run"]["trace"] = True
    result = ran(tmp_path, made, files)
    trace = {entry["id"]: entry for entry in result.summary()["trace"]}
    assert result.status == "success", result.error
    assert trace["in_names"]["outputs"] is None
    assert trace["map"]["outputs"]["o"]["data"] == [["3", "cy"]]


def test_failure_of_a_component_that_is_not_listed_takes_the_place_of_its_entry(tmp_path):
    # The lookup holds a name where a number belongs and stops the job; it was noted as not listed before.
    made = joined_with_names()
    made["components"][1]["config"]["die_on_error"] = True
    result, trace = traced(tmp_path, made, {"in.csv": DATA, "names.csv": b"id;name\nx;ann\n3;cy\n"}, where={"id": 3})
    assert result.status == "failed" and result.failed_component == "names"
    assert trace["names"] == {"id": "names", "type": "FileInputDelimited", "error": result.error}
    assert [entry["id"] for entry in result.summary()["trace"]].count("names") == 1


def test_file_output_of_a_stage_that_failed_says_its_file_was_not_written(tmp_path, caplog):
    failing = {"id": "it", "type": "PyMap", "inputs": ["row1"], "outputs": ["row3"],
               "config": map_config([map_out("row3", [("id", "row1.id", "int"), ("n", "int(row1.code)", "int")])]),
               "schema": {"inputs": {"row1": columns("id:int, code:str")}}}
    made = job([reader("id:int, code:str", outputs=("row1", "row2"), header_rows=1),
                writer("id:int, code:str", inputs=("row2",)), failing,
                writer("id:int, n:int", "second", "second.csv", ("row3",))],
               [flow("row2", "in", "out"), flow("row1", "in", "it"), flow("row3", "it", "second")])
    caplog.set_level(logging.INFO, logger="src.v2")
    result, trace = traced(tmp_path, made, {"in.csv": b"id;code\n1;10\n2;x\n"}, where={"id": 2})
    assert result.status == "failed" and not (tmp_path / "out.csv").exists()
    assert trace["out"]["rows"] == 1 and trace["out"]["written"] is False
    assert "[out] trace: 1 row for out.csv" in [record.getMessage() for record in caplog.records]


def test_file_output_of_a_stage_that_finished_says_its_file_was_written(tmp_path):
    _, trace = traced(tmp_path, copying(header_rows=1), {"in.csv": DATA}, where={"id": 3})
    assert trace["out"]["written"] is True


def test_traced_run_says_each_thing_once_when_a_file_holds_what_the_fast_reader_does_not_take(tmp_path, caplog):
    # The lookup holds 3.0 where a whole number is declared: the fast reader fails on it, the tolerant one reads it.
    caplog.set_level(logging.INFO, logger="src.v2")
    result, trace = traced(tmp_path, joined_with_names(),
                           {"in.csv": DATA, "names.csv": b"id;name\n1;ann\n3.0;cy\n"}, where={"id": 3})
    assert result.status == "success", result.error
    said = [record.getMessage() for record in caplog.records]
    assert len([line for line in said if line.startswith("[in] trace:")]) == 1
    assert not [line for line in said if "reading again" in line]
    assert rows_of(trace["it"]) == [["3", "30", "cy"]]


def test_command_line_can_turn_off_the_trace_the_job_config_asks_for(tmp_path, capsys):
    (tmp_path / "in.csv").write_bytes(DATA)
    made = job([reader(IDS, path=str(tmp_path / "in.csv"), header_rows=1),
                writer(IDS, path=str(tmp_path / "out.csv"), inputs=("row1",))], [flow("row1", "in", "out")],
               run={"only": {"source": "in", "where": {"id": 3}}, "trace": True})
    (tmp_path / "job.json").write_text(json.dumps(made))
    assert main([str(tmp_path / "job.json"), "--no-trace"]) == 0
    printed = capsys.readouterr().out
    assert "trace" not in json.loads(printed[printed.index("\n{"):]) and " trace: " not in printed


def test_trace_of_a_run_whose_code_hands_on_a_list_is_made_all_the_same(tmp_path):
    first = 'df = df.with_columns(pl.col("tags").str.split(",").alias("parts"))'
    second = 'df = df.with_columns(pl.col("parts").list.len().alias("n")).drop("parts")'
    made = chained(first, second, "id:int, tags:str", out="id:int, tags:str, n:int", dataframe="polars")
    made["components"][1]["config"]["dataframe"] = "polars"
    result, trace = traced(tmp_path, made, {"in.csv": b"id;tags\n1;a,b\n2;c\n"}, where={"id": 1})
    assert result.status == "success", result.error
    handed_on = trace["one"]["outputs"]["main"]
    assert handed_on["columns"][-1] == {"name": "parts", "type": "List(String)"}
    assert handed_on["data"] == [["1", "a,b", "['a', 'b']"]]
    assert (tmp_path / "out.csv").read_bytes() == b"id;tags;n\n1;a,b;2\n"


def test_debug_says_why_a_traced_run_reads_every_column_as_text(tmp_path, caplog):
    caplog.set_level(logging.DEBUG, logger="src.v2")
    traced(tmp_path, copying(header_rows=1), {"in.csv": DATA}, where={"id": 3})
    assert ("[t] sources read every column as text in this subjob: the run is traced, which takes rows in hand, "
            "so the subjob cannot be read a second time") in [record.getMessage() for record in caplog.records]
