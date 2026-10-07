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

from .components.kit import through
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
