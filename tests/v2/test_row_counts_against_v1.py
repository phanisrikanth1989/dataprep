"""Row counts on request, against the counts v1 keeps for the same job.

v1 counts the rows of every component it runs: read, passed on, rejected
(``component_stats``). A run of v2 that asks for row counts must come to the
same three numbers for every component. The payments scenario
(``test_scenario_payments.py``) holds that for the ten component types its
job uses; the jobs here hold it for the others, and for the outputs of a
reader or a map that the scenario leaves unused.
"""
import pytest

from src.v2 import run_job as run_on_v2
from tests.v2.answer_key import run_job, run_v1

from .components.kit import columns, flow, job, reader, through, writer
from .components.test_file_delimited import copy
from .components.test_file_input_excel import book, excel
from .components.test_file_input_fullrow import read_lines
from .components.test_file_input_json import ODD, ODD_PATHS, ODD_SCHEMA, as_bytes, json_job
from .components.test_file_input_positional import cut
from .components.test_log_row import logged
from .components.test_map import (BY_CODE, INNER, JOINED, JOINED_COLUMNS, MISSED, MISSES, TWO, TWO_DATA, config,
                                  lookup, mapping, out)
from .components.test_python_dataframe import coded


def counts(line, ok, reject):
    return {"NB_LINE": line, "NB_LINE_OK": ok, "NB_LINE_REJECT": reject}


def counted(job_config, inputs, tmp_path):
    """Run a job on v1 and on v2, each in its own folder; returns (v1's counts, v2's) by component id."""
    held = {}

    def on_v1(made):
        held["v1"] = run_v1(made)

    def on_v2(made):
        result = run_on_v2(made, row_counts=True)
        result.raise_for_status()
        held["v2"] = result.counts

    for engine, runner in (("v1", on_v1), ("v2", on_v2)):
        run = run_job(job_config, inputs, tmp_path / engine, runner)
        assert run.succeeded, f"{engine}: {run.error}"
    return held["v1"], held["v2"]


def same_counts(job_config, inputs, tmp_path):
    """Both engines come to the same counts for every component. Returns them."""
    v1, v2 = counted(job_config, inputs, tmp_path)
    assert v2 == v1
    return v2


# ------------------------------------------------------------------
# Readers
# ------------------------------------------------------------------

def test_delimited_reader_counts_the_rows_it_passes_on_and_the_ones_it_rejects(tmp_path):
    made = copy("id:int, name:str", reject_schema=True)
    found = same_counts(made, {"in.csv": b"1;a\nx;b\n3;c\n;d\ny;e\n"}, tmp_path)
    assert found["in"] == counts(5, 3, 2) and found["out"] == counts(3, 3, 0) and found["rej"] == counts(2, 2, 0)


def test_positional_reader_counts_the_rows_it_reads(tmp_path):
    made = cut(schema="a:str, n:int", pattern="3,3", header_rows=1, limit=2)
    found = same_counts(made, {"in.txt": b"nam  n\nabc  1\n\ndef  2\nghi  3\n"}, tmp_path)
    assert found["in"] == counts(2, 2, 0)


def test_excel_reader_counts_the_rows_it_reads(tmp_path):
    made = excel("a:str, n:int", header=1)
    sheet = book({"Sheet1": [["a", "n"], ["a", 1], ["b", 2], ["c", 3]]})
    found = same_counts(made, {"in.xlsx": sheet}, tmp_path)
    assert found["in"] == counts(3, 3, 0)


def test_json_reader_counts_the_records_it_passes_on_and_the_ones_it_turns_away(tmp_path):
    found = same_counts(json_job(ODD_SCHEMA, ODD_PATHS), {"in.json": as_bytes(ODD)}, tmp_path)
    assert found["in"] == counts(4, 2, 2) and found["out"] == counts(2, 2, 0)


# v1's full-row input counts as read every line the file splits into: the header and footer it skips,
# the empty lines it drops, the lines past its limit, and the nothing after the last line end.
def test_row_generator_counts_the_rows_it_makes_and_the_ones_whose_expression_fails(tmp_path):
    source = {"id": "in", "type": "RowGenerator", "inputs": [], "outputs": ["row1", "bad"],
              "config": {"nb_rows": 5, "values": [{"schema_column": "id", "array": "1"}]},
              "schema": {"input": [], "output": columns("id:int")}}
    made = job([source, writer("id:int", inputs=("row1",)), writer("id:int", component_id="rej", path="rej.csv", inputs=("bad",))],
               [flow("row1", "in", "out"), flow("bad", "in", "rej", kind="reject")])
    assert same_counts(made, {}, tmp_path)["in"] == counts(5, 5, 0)
    source["config"]["values"][0]["array"] = "1/0"
    assert same_counts(made, {}, tmp_path / "b")["in"] == counts(5, 0, 5)
    del source["outputs"][1], made["components"][2], made["flows"][1]
    assert same_counts(made, {}, tmp_path / "c")["in"] == counts(5, 0, 5)


LINES = b"h1\nh2\na\n\nb\nc\nf1\nf2"


@pytest.mark.parametrize("config", [
    {}, {"header_rows": 2}, {"header_rows": 2, "footer_rows": 2}, {"limit": "2"},
    {"header_rows": 1, "limit": 3}, {"footer_rows": 9},
])
@pytest.mark.parametrize("ending", [b"", b"\n"])
@pytest.mark.parametrize("remove_empty_row", [True, False])
def test_full_row_reader_counts_every_line_of_the_file_as_read(tmp_path, config, ending, remove_empty_row):
    made = read_lines(remove_empty_row=remove_empty_row, **config)
    found = same_counts(made, {"in.txt": LINES + ending}, tmp_path)
    assert found["in"]["NB_LINE"] == 8 + (ending == b"\n")
    assert found["in"]["NB_LINE_OK"] == found["out"]["NB_LINE"]


def test_full_row_reader_of_an_empty_file_has_read_one_line_of_nothing(tmp_path):
    found = same_counts(read_lines(), {"in.txt": b""}, tmp_path)
    assert found["in"] == counts(1, 0, 0)


# ------------------------------------------------------------------
# Transforms the payments scenario does not use
# ------------------------------------------------------------------

SCHEMA = "id:int, name:str, amt:float"
DATA = b"id;name;amt\n1;alice;10.5\n2;bob;\n3;;7\n4;dave;1\n"


def test_filter_columns_counts_its_rows(tmp_path):
    made = through({"type": "FilterColumns", "config": {}}, SCHEMA, "name:str, id:int")
    assert same_counts(made, {"in.csv": DATA}, tmp_path)["it"] == counts(4, 4, 0)


def test_log_row_counts_its_rows(tmp_path):
    assert same_counts(logged({}), {"in.csv": DATA}, tmp_path)["it"] == counts(4, 4, 0)


def test_python_dataframe_counts_the_rows_it_is_handed_and_the_ones_it_returns(tmp_path):
    made = coded("df = df[df['id'] > 1]")
    assert same_counts(made, {"in.csv": DATA}, tmp_path)["it"] == counts(4, 3, 0)


def test_map_counts_the_rows_of_its_outputs_the_rejecting_ones_apart(tmp_path):
    outputs = [out("o", JOINED_COLUMNS, filter="row2.rate > 3", activate_filter=True),
               out("low", JOINED_COLUMNS, is_reject=True), out("rej", MISSES, inner_join_reject=True)]
    made = mapping(config(outputs, lookups=[lookup("row2", BY_CODE, **INNER)]), TWO,
                   {"o": JOINED, "low": JOINED, "rej": MISSED})
    found = same_counts(made, TWO_DATA, tmp_path)
    assert found["map"]["NB_LINE_REJECT"] == found["out_low"]["NB_LINE"] + found["out_rej"]["NB_LINE"] > 0
    assert found["map"]["NB_LINE_OK"] == found["out_o"]["NB_LINE"] > 0


# ------------------------------------------------------------------
# Where v2 does not follow v1
# ------------------------------------------------------------------

# Most of v1's components count their rows themselves, before v1 checks what they made against the
# declared schema. A row that check then drops, or moves to the reject output, stays in v1's count
# of rows passed on. v2 counts the rows a component hands on, which are the ones the next one gets.

def test_row_the_schema_check_drops_is_not_counted_as_passed_on(tmp_path):
    made = through({"type": "SortRow", "config": {"criteria": [{"column": "id", "sort_type": "num", "order": "asc"}],
                                                   "die_on_error": False}},
                   "id:int, n:int", "id:int, n:int!")
    v1, v2 = counted(made, {"in.csv": b"id;n\n2;5\n1;\n3;7\n"}, tmp_path)
    assert v1["it"] == counts(3, 3, 0) and v1["out"] == counts(2, 2, 0)
    assert v2["it"] == counts(3, 2, 0) and v2["out"] == counts(2, 2, 0)


def test_row_the_schema_check_moves_to_reject_is_counted_as_rejected(tmp_path):
    made = cut(schema="a:str, n:int!", pattern="3,3", reject=True)
    v1, v2 = counted(made, {"in.txt": b"abc  1\ndef   \nghi  3\n"}, tmp_path)
    assert v1["in"] == counts(3, 3, 0) and v1["rej"] == counts(1, 1, 0)
    assert v2["in"] == counts(3, 2, 1) and v2["rej"] == counts(1, 1, 0)


# ------------------------------------------------------------------
# The components added with tickets 53 to 60
# ------------------------------------------------------------------

@pytest.mark.parametrize("step, out, expected", [
    ({"type": "Replicate", "config": {}}, SCHEMA, counts(4, 4, 0)),
    ({"type": "Replace", "config": {"substitutions": [
        {"input_column": "name", "search_pattern": "bob", "replace_string": "rob"}]}}, SCHEMA, counts(4, 4, 0)),
    ({"type": "SplitRow", "config": {"col_mapping": [{"id": "row1.id"}, {"id": "row1.id"}]}}, "id:int", counts(4, 8, 0)),
    ({"type": "UnpivotRow", "config": {"row_keys": ["id"]}}, "id:int, pivot_key:str, pivot_value:str", counts(4, 8, 0)),
    ({"type": "Denormalize", "config": {"denormalize_columns": [{"input_column": "name"}, {"input_column": "id"}]}},
     "amt:float, name:str, id:str", counts(4, 4, 0)),
    ({"type": "AggregateSortedRow", "config": {
        "groupbys": [{"input_column": "id", "output_column": "id"}],
        "operations": [{"output_column": "amt", "function": "sum", "input_column": "amt"}]}}, "id:int, amt:float",
     counts(4, 4, 0)),
    ({"type": "ConvertType", "config": {"manualtable": [{"input_column": "id", "output_column": "n"}]}},
     SCHEMA + ", n:float", counts(4, 4, 0)),
], ids=["replicate", "replace", "split row", "unpivot row", "denormalize", "aggregate sorted row", "convert type"])
def test_new_transforms_count_their_rows(tmp_path, step, out, expected):
    made = through(step, SCHEMA, out)
    assert same_counts(made, {"in.csv": DATA}, tmp_path)["it"] == expected


def test_sample_row_counts_the_rows_it_picks_and_the_others(tmp_path):
    from .components.test_sample_row import DATA as TWELVE, sampled
    found = same_counts(sampled(range="1,5,10..20"), {"in.csv": TWELVE}, tmp_path)
    assert found["it"] == counts(12, 5, 7)


def test_convert_type_counts_the_rows_it_turns_away(tmp_path):
    from .components.test_convert_type import DATA as TEXT, IN, converted
    made = converted(IN + ", n2:int", manualtable=[{"input_column": "n", "output_column": "n2"}])
    assert same_counts(made, {"in.csv": TEXT}, tmp_path)["it"] == counts(4, 3, 1)


def test_excel_output_counts_the_rows_it_writes(tmp_path):
    sink = {"id": "out", "type": "FileOutputExcel", "inputs": ["row1"], "outputs": [],
            "config": {"filename": "out.xlsx", "includeheader": True},
            "schema": {"input": columns("id:int, name:str"), "output": []}}
    made = job([reader("id:int, name:str", header_rows=1), sink], [flow("row1", "in", "out")])
    assert same_counts(made, {"in.csv": b"id;name\n1;a\n2;b\n3;\n"}, tmp_path)["out"] == counts(3, 3, 0)


def test_positional_output_counts_the_rows_it_writes(tmp_path):
    sink = {"id": "out", "type": "FileOutputPositional", "inputs": ["row1"], "outputs": [],
            "config": {"filepath": "out.txt", "include_header": True,
                       "formats": [{"schema_column": "id", "size": "3"}, {"schema_column": "name", "size": "4"}]},
            "schema": {"input": columns("id:int, name:str"), "output": []}}
    made = job([reader("id:int, name:str", header_rows=1), sink], [flow("row1", "in", "out")])
    assert same_counts(made, {"in.csv": b"id;name\n1;a\n2;b\n3;\n"}, tmp_path)["out"] == counts(3, 3, 0)


def test_extract_delimited_fields_counts_the_rows_it_hands_on_and_turns_away_and_not_those_it_leaves_out(tmp_path):
    from .components.test_extract_delimited_fields import extract
    made = extract(schema="id:int, raw:float", out="id:int, a:str, b:str", fieldseparator=".", reject="",
                   check_fields_num=True)
    data = b"id|raw\n1|1.5\n2|\n3|2.5\n4|7\n"
    assert same_counts(made, {"in.csv": data}, tmp_path)["it"] == counts(4, 3, 0)
    made = extract(reject="", check_fields_num=True)
    assert same_counts(made, {"in.csv": b"id|raw\n1|a;b;c\n2|d;e\n"}, tmp_path / "b")["it"] == counts(2, 1, 1)


def test_extract_positional_fields_counts_its_rows(tmp_path):
    from .components.test_extract_positional_fields import extract
    made = extract(reject="", check_fields_num=True)
    assert same_counts(made, {"in.csv": b"id|raw\n1|abcdefghij\n2|abc\n"}, tmp_path)["it"] == counts(2, 1, 1)


def test_pivot_counts_the_rows_it_reads_and_the_groups_it_writes(tmp_path):
    pivot = {"id": "it", "type": "PivotToColumnsDelimited", "inputs": ["row1"], "outputs": [],
             "config": {"pivot_column": "q", "aggregation_column": "amt", "groupbys": ["id"], "filename": "out.csv"},
             "schema": {"input": columns("id:int, q:str, amt:float"), "output": []}}
    made = job([reader("id:int, q:str, amt:float", header_rows=1), pivot], [flow("row1", "in", "it")])
    data = b"id;q;amt\n1;a;2\n1;b;3.5\n2;a;1\n2;b;4\n3;a;\n"
    assert same_counts(made, {"in.csv": data}, tmp_path)["it"] == counts(5, 3, 0)


def test_schema_compliance_check_counts_the_rows_that_fit_and_the_others(tmp_path):
    from .components.test_schema_compliance_check import DATA as ROWS, checked
    assert same_counts(checked(), {"in.csv": ROWS}, tmp_path)["it"] == counts(7, 1, 6)


@pytest.mark.parametrize("step", [
    {"type": "Denormalize", "config": {"denormalize_columns": [{"input_column": "amt"}]}},
    {"type": "AggregateSortedRow", "config": {
        "groupbys": [{"input_column": "id", "output_column": "id"}, {"input_column": "name", "output_column": "name"}],
        "operations": [{"output_column": "amt", "function": "count", "input_column": "amt"}]}},
], ids=["denormalize", "aggregate sorted row"])
def test_rows_read_and_rows_handed_on_are_told_apart_where_several_rows_become_one(tmp_path, step):
    made = through(step, SCHEMA, "id:int, name:str, amt:str")
    found = same_counts(made, {"in.csv": b"id;name;amt\n1;a;1\n1;a;2\n2;b;3\n"}, tmp_path)
    assert found["it"] == counts(3, 2, 0)
