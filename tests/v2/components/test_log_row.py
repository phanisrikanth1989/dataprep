"""Log row, against v1 on the same job config: the rows passed on and the lines printed."""
import glob
import json
import logging
import os

import pytest

from src.v2 import load_job
from src.v2.components.transform.log_row import LogRow
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import REPO_ROOT, assert_matches_v1, run_job, run_v1, run_v2

from .kit import columns, flow, job, reader, through, writer

V1_LOGGER = "src.v1.engine.components.transform.log_row"
V2_LOGGER = "src.v2.components.transform.log_row"

SCHEMA = "id:int, name:str, amt:float"
DATA = b"id;name;amt\n1;alice;10.5\n2;bob;\n3;;7\n4;a-very-long-name;1234567.25\n"
ALL_TYPES = "s:str, i:int, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2"
ALL_DATA = b"s;i;f;b;d;m\na;1;1.5;true;2024-01-31;12.345\nb;-2;30200.00;false;1999-12-31;7\nc;;;;;\n;4;;;;\n"


def logged(config, schema=SCHEMA, **more):
    """file -> log row -> file."""
    return through({"type": "LogRow", "config": config}, schema, **more)


def ending(config, schema=SCHEMA):
    """file -> log row, with nothing after it: only what is printed is compared."""
    log = {"id": "it", "type": "LogRow", "config": config,
           "schema": {"input": columns(schema), "output": columns(schema)}, "inputs": ["row1"], "outputs": []}
    return job([reader(schema, header_rows=1), log], [flow("row1", "in", "it")])


def printed(caplog, logger_name):
    return [record.getMessage() for record in caplog.records
            if record.name == logger_name and record.levelno == logging.INFO]


def same(tmp_path, caplog, config, data=DATA, schema=SCHEMA, made=None, inputs=None):
    """Both engines pass the same rows on and print the same lines. Returns the lines."""
    caplog.set_level(logging.INFO)
    caplog.clear()
    run = assert_matches_v1(made or logged(config, schema), inputs or {"in.csv": data}, tmp_path)
    assert run.succeeded, run.error
    assert printed(caplog, V2_LOGGER) == printed(caplog, V1_LOGGER)
    return printed(caplog, V2_LOGGER)


def v2_only(tmp_path, caplog, config, data=DATA, schema=SCHEMA):
    """Run on v2 alone, where v1's own printing is not the answer. Returns (run, lines)."""
    caplog.set_level(logging.INFO)
    caplog.clear()
    run = run_job(logged(config, schema), {"in.csv": data}, tmp_path / "v2", run_v2)
    return run, printed(caplog, V2_LOGGER)


def v1_finishes(tmp_path, config, data=DATA, schema=SCHEMA):
    return run_job(logged(config, schema), {"in.csv": data}, tmp_path / "v1", run_v1).succeeded


# ------------------------------------------------------------------
# One line per row
# ------------------------------------------------------------------

def test_rows_pass_through_and_are_printed_one_line_each(tmp_path, caplog):
    lines = same(tmp_path, caplog, {})
    assert lines == ["1|alice|10.5", "2|bob|", "3||7.0", "4|a-very-long-name|1234567.25"]
    assert (tmp_path / "v2" / "out.csv").read_bytes() == (
        b"id;name;amt\n1;alice;10.5\n2;bob;\n3;;7.0\n4;a-very-long-name;1234567.25\n"
    )


def test_every_type_is_printed_as_v1_prints_it(tmp_path, caplog):
    lines = same(tmp_path, caplog, {}, ALL_DATA, ALL_TYPES)
    assert lines == [
        "a|1|1.5|True|2024-01-31 00:00:00|12.35",
        "b|-2|30200.0|False|1999-12-31 00:00:00|7.00",
        "c|||False||",
        "|4||False||",
    ]


@pytest.mark.parametrize(
    "config",
    [
        {"print_header": True},
        {"print_unique_name": True},
        {"print_colnames": True},
        {"print_header": True, "print_unique_name": True, "print_colnames": True},
        {"print_header": False, "print_unique_name": False, "print_colnames": False},
    ],
)
def test_header_component_name_and_column_names(tmp_path, caplog, config):
    assert same(tmp_path, caplog, config)


def test_header_and_names_exactly(tmp_path, caplog):
    config = {"print_header": True, "print_unique_name": True, "print_colnames": True, "max_rows": 2}
    assert same(tmp_path, caplog, config) == [
        "[it] id|name|amt", "[it] id=1|name=alice|amt=10.5", "[it] id=2|name=bob|amt=",
    ]


@pytest.mark.parametrize("separator", ["|", ";", " , ", "", "\\t", "->"])
def test_field_separator_is_used_as_written(tmp_path, caplog, separator):
    lines = same(tmp_path, caplog, {"fieldseparator": separator, "print_header": True})
    assert lines[0] == separator.join(["id", "name", "amt"])


def test_basic_mode_is_what_is_printed_whatever_the_key_says(tmp_path, caplog):
    assert same(tmp_path, caplog, {"basic_mode": False}) == same(tmp_path / "b", caplog, {"basic_mode": True})


@pytest.mark.parametrize("config", [{"print_unique": False}, {"print_content_with_log4j": False}])
def test_keys_with_no_effect_on_the_lines(tmp_path, caplog, config):
    assert same(tmp_path, caplog, config) == same(tmp_path / "plain", caplog, {})


# ------------------------------------------------------------------
# Table
# ------------------------------------------------------------------

def test_table(tmp_path, caplog):
    assert same(tmp_path, caplog, {"table_print": True}) == [
        "+--+----------------+----------+",
        "|id|name            |amt       |",
        "+--+----------------+----------+",
        "|1 |alice           |10.5      |",
        "|2 |bob             |          |",
        "|3 |                |7.0       |",
        "|4 |a-very-long-name|1234567.25|",
        "+--+----------------+----------+",
    ]


def test_table_with_the_component_name_above(tmp_path, caplog):
    lines = same(tmp_path, caplog, {"table_print": True, "print_unique_name": True})
    assert lines[0] == "[it]" and lines[1].startswith("+--+")


def test_table_ignores_the_keys_of_the_other_layouts(tmp_path, caplog):
    config = {"table_print": True, "print_header": True, "print_colnames": True, "fieldseparator": ";"}
    assert same(tmp_path, caplog, config) == same(tmp_path / "plain", caplog, {"table_print": True})


def test_table_of_text_with_wide_and_special_characters(tmp_path, caplog):
    data = "a;b\ncaf\u00e9;\u4e2d\u6587\n100%;%s\n;x\n".encode("utf-8")
    lines = same(tmp_path, caplog, {"table_print": True}, data, "a:str, b:str")
    assert lines[3:5] == ["|caf\u00e9|\u4e2d\u6587|", "|100%|%s|"]


def test_table_with_times_and_missing_dates(tmp_path, caplog):
    data = b"d;s\n2024-01-31 10:11:12;x\n;y\n"
    assert same(tmp_path, caplog, {"table_print": True}, data, "d:datetime@%Y-%m-%d %H:%M:%S, s:str")


# ------------------------------------------------------------------
# Vertical
# ------------------------------------------------------------------

def test_vertical(tmp_path, caplog):
    assert same(tmp_path, caplog, {"vertical": True, "max_rows": 2}) == [
        "--- [it] row 1 ---", "  id: 1", "  name: alice", "  amt: 10.5",
        "--- [it] row 2 ---", "  id: 2", "  name: bob", "  amt: ",
    ]


def test_vertical_wins_over_table(tmp_path, caplog):
    both = same(tmp_path, caplog, {"vertical": True, "table_print": True})
    assert both == same(tmp_path / "v", caplog, {"vertical": True})


@pytest.mark.parametrize(
    "config, title",
    [
        ({"print_label": True, "label": "My label"}, "My label"),
        ({"print_label": True, "label": ""}, "[it]"),
        ({"print_label": True}, "[it]"),
        ({"print_unique_label": True, "label": "My label"}, "[it] My label"),
        ({"print_unique_label": True, "label": ""}, "[it]"),
        ({"print_unique_label": True, "label": "  x  "}, "[it]   x"),
        ({"print_unique_label": True, "print_label": True, "label": "L"}, "[it] L"),
        ({"print_unique": True, "label": "unused"}, "[it]"),
    ],
)
def test_vertical_titles(tmp_path, caplog, config, title):
    lines = same(tmp_path, caplog, {"vertical": True, "max_rows": 1, **config})
    assert lines[0] == f"--- {title} row 1 ---"


def test_label_may_come_from_the_context(tmp_path, caplog):
    made = logged({"vertical": True, "print_label": True, "label": "run ${context.n}", "max_rows": 1})
    made["context"] = {"Default": {"n": {"value": "7", "type": "int"}}}
    assert same(tmp_path, caplog, None, made=made)[0] == "--- run 7 row 1 ---"


def test_vertical_ignores_the_keys_of_the_other_layouts(tmp_path, caplog):
    config = {"vertical": True, "print_header": True, "print_colnames": True, "print_unique_name": True,
              "fieldseparator": ";"}
    assert same(tmp_path, caplog, config) == same(tmp_path / "plain", caplog, {"vertical": True})


# ------------------------------------------------------------------
# Fixed widths
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "config",
    [
        {"lengths": [3, 4]},
        {"lengths": [3, 4, 5, 6], "print_colnames": True, "print_header": True, "print_unique_name": True},
        {"lengths": [0, 2, 1]},
        {"lengths": []},
        {"lengths": [3, 4], "vertical": True},
        {"lengths": [3, 4], "table_print": True},
        {"lengths": [3, 20, 12], "table_print": True, "print_unique_name": True},
        {"lengths": [], "table_print": True},
        {"lengths": [2.0, 30]},
    ],
)
def test_fixed_widths(tmp_path, caplog, config):
    assert same(tmp_path, caplog, {"use_fixed_length": True, **config})


def test_fixed_widths_cut_and_pad_a_line_but_only_pad_a_table(tmp_path, caplog):
    fixed = {"use_fixed_length": True, "lengths": [3, 4], "max_rows": 1}
    assert same(tmp_path, caplog, fixed) == ["1  |alic|10.5"]
    assert same(tmp_path / "v", caplog, {**fixed, "vertical": True}) == [
        "--- [it] row 1 ---", "  id: 1  ", "  name: alic", "  amt: 10.5",
    ]
    assert same(tmp_path / "t", caplog, {**fixed, "table_print": True}) == [
        "+---+----+---+", "|id |name|amt|", "+---+----+---+", "|1  |alice|10.5|", "+---+----+---+",
    ]


@pytest.mark.parametrize("layout", [{}, {"table_print": True}, {"vertical": True}])
def test_widths_are_not_used_unless_asked_for(tmp_path, caplog, layout):
    assert same(tmp_path, caplog, {"lengths": [3, 4, 5], **layout}) == same(tmp_path / "plain", caplog, layout)


# ------------------------------------------------------------------
# How many rows are printed
# ------------------------------------------------------------------

@pytest.mark.parametrize("max_rows, count", [(2, 2), ("2", 2), (1, 1), (4, 4), (100, 4), (0, 0)])
def test_max_rows_limits_the_lines_and_never_the_flow(tmp_path, caplog, max_rows, count):
    assert len(same(tmp_path, caplog, {"max_rows": max_rows})) == count
    assert (tmp_path / "v2" / "out.csv").read_bytes().count(b"\n") == 5


def test_a_hundred_rows_are_printed_when_nothing_is_said(tmp_path, caplog):
    data = b"id;name;amt\n" + b"".join(b"%d;n%d;%d.5\n" % (n, n, n) for n in range(250))
    lines = same(tmp_path, caplog, {}, data)
    assert len(lines) == 100 and lines[-1] == "99|n99|99.5"
    assert (tmp_path / "v2" / "out.csv").read_bytes().count(b"\n") == 251


@pytest.mark.parametrize(
    "config, lines",
    [
        ({"print_header": True}, ["id|name|amt"]),
        ({"print_header": True, "print_unique_name": True}, ["[it] id|name|amt"]),
        ({"table_print": True, "print_unique_name": True}, []),
        ({"vertical": True}, []),
    ],
)
def test_no_rows_to_print_still_prints_the_header_line(tmp_path, caplog, config, lines):
    assert same(tmp_path, caplog, {"max_rows": 0, **config}) == lines


@pytest.mark.parametrize("config", [{"print_header": True}, {"table_print": True, "print_unique_name": True},
                                    {"vertical": True}, {"max_rows": 0, "print_header": True}])
def test_empty_flow_prints_nothing_at_all(tmp_path, caplog, config):
    assert same(tmp_path, caplog, config, b"id;name;amt\n") == []
    assert (tmp_path / "v2" / "out.csv").read_bytes() == b"id;name;amt\n"


def test_max_rows_may_come_from_the_context(tmp_path, caplog):
    made = logged({"max_rows": "${context.shown}"})
    made["context"] = {"Default": {"shown": {"value": "3", "type": "int"}}}
    assert len(same(tmp_path, caplog, None, made=made)) == 3


def test_only_the_rows_to_print_are_held(tmp_path, caplog, monkeypatch):
    held = []
    keep = LogRow._print
    monkeypatch.setattr(LogRow, "_print", lambda self, rows: (held.append(rows.height), keep(self, rows))[1])
    data = b"id;name;amt\n" + b"".join(b"%d;n;1.5\n" % n for n in range(5000))
    run, lines = v2_only(tmp_path, caplog, {"max_rows": 3}, data)
    assert run.succeeded and len(lines) == 3 and held == [3]
    assert run.files["out.csv"].count(b"\n") == 5001
    spec = load_job(logged({})).components["it"]
    assert LogRow(spec, spec.config, None).needs_rows() is False


# ------------------------------------------------------------------
# Values
# ------------------------------------------------------------------

@pytest.mark.parametrize("layout", [{}, {"vertical": True}])
def test_missing_values_of_every_type_print_as_nothing(tmp_path, caplog, layout):
    assert same(tmp_path, caplog, layout, ALL_DATA, ALL_TYPES)


@pytest.mark.parametrize(
    "text",
    ["1.5", "2", "30200.00", "0.0001", "0.00001", "0.00001234", "1e-6", "1.5e-7", "2.5e-9", "1e-10", "-0.000012",
     "1e15", "1e16", "1e22", "-0.0", "inf", "-inf", "1e-5", "9.99e-5", "0.1", "-1.5e-8", "1e-300", "5e-324"],
)
def test_floats_are_printed_as_python_writes_them(tmp_path, caplog, text):
    made = ending({}, "k:str, v:float")
    assert same(tmp_path, caplog, None, f"k;v\nx;{text}\n".encode(), made=made) == [f"x|{float(text)!r}"]


def test_floats_of_every_size_are_printed_as_python_writes_them(tmp_path, caplog):
    numbers = [sign * mantissa * 10.0 ** power for power in range(-30, 31) for mantissa in (1.0, 1.25, 9.999999, 1 / 3)
               for sign in (1, -1)]
    data = "v\n" + "".join(f"{number!r}\n" for number in numbers)
    caplog.set_level(logging.INFO)
    run = run_job(ending({"max_rows": len(numbers)}, "v:float"), {"in.csv": data.encode()}, tmp_path / "v2", run_v2)
    assert run.succeeded, run.error
    assert printed(caplog, V2_LOGGER) == [repr(number) for number in numbers]


def test_float_that_is_not_a_number_prints_as_nothing(tmp_path, caplog):
    assert same(tmp_path, caplog, {}, b"k;v\nx;NaN\ny;2.5\n", "k:str, v:float") == ["x|", "y|2.5"]


@pytest.mark.parametrize(
    "pattern, text, shown",
    [
        ("%Y-%m-%d", "2024-01-31", "2024-01-31 00:00:00"),
        ("%d/%m/%Y", "31/01/2024", "2024-01-31 00:00:00"),
        ("%Y-%m-%d %H:%M:%S", "2024-01-31 10:11:12", "2024-01-31 10:11:12"),
        ("%Y-%m-%d %H:%M:%S.%f", "2024-01-31 10:11:12.123", "2024-01-31 10:11:12.123000"),
        ("%Y-%m-%d %H:%M:%S.%f", "2024-01-31 10:11:12.000", "2024-01-31 10:11:12"),
    ],
)
def test_dates_are_printed_whole_whatever_their_pattern(tmp_path, caplog, pattern, text, shown):
    lines = same(tmp_path, caplog, {}, f"k;v\nx;{text}\n".encode(), f"k:str, v:datetime@{pattern}")
    assert lines == [f"x|{shown}"]


@pytest.mark.parametrize("places, shown", [(0, ["2", "7", "-1"]), (2, ["1.50", "7.00", "-1.01"]),
                                           (4, ["1.5000", "7.0000", "-1.0050"])])
def test_decimals_are_printed_to_their_declared_places(tmp_path, caplog, places, shown):
    lines = same(tmp_path, caplog, {}, b"k;v\na;1.50\nb;7\nc;-1.005\n", f"k:str, v:Decimal#{places}")
    assert lines == [f"{key}|{value}" for key, value in zip("abc", shown)]


@pytest.mark.parametrize(
    "schema, data",
    [
        ("i:int!, j:int!", b"i;j\n1;15\n-2;25\n"),
        ("i:int!, b:bool", b"i;b\n1;true\n2;false\n"),
        ("f:float, b:bool!", b"f;b\n1.5;true\n2;false\n"),
        ("i:int, f:float", b"i;f\n1;1.5\n2;2.5\n"),
    ],
)
def test_frames_without_text_columns(tmp_path, caplog, schema, data):
    assert same(tmp_path, caplog, {}, data, schema)


# ------------------------------------------------------------------
# Where it sits in a job
# ------------------------------------------------------------------

def test_log_row_at_the_end_of_a_flow_still_prints(tmp_path, caplog):
    made = job([reader(SCHEMA, header_rows=1),
                {"id": "log", "type": "tLogRow", "config": {"print_unique_name": True},
                 "schema": {"input": columns(SCHEMA), "output": columns(SCHEMA)}, "inputs": ["row1"], "outputs": []}],
               [flow("row1", "in", "log")])
    assert same(tmp_path, caplog, None, made=made)[0] == "[log] 1|alice|10.5"


def test_two_log_rows_in_a_row_print_one_after_the_other(tmp_path, caplog):
    def log(component_id, inputs, outputs):
        return {"id": component_id, "type": "LogRow", "config": {"print_unique_name": True, "max_rows": 2},
                "schema": {"input": columns(SCHEMA), "output": columns(SCHEMA)}, "inputs": inputs, "outputs": outputs}

    made = job(
        [reader(SCHEMA, header_rows=1), log("a", ["row1"], ["mid"]), log("b", ["mid"], ["row2"]), writer(SCHEMA)],
        [flow("row1", "in", "a"), flow("mid", "a", "b"), flow("row2", "b", "out")],
    )
    lines = same(tmp_path, caplog, None, made=made)
    assert [line[:3] for line in lines] == ["[a]", "[a]", "[b]", "[b]"]


@pytest.mark.parametrize("rows, runs", [(4, True), (2, False)])
def test_rows_passed_on_are_counted_whatever_max_rows_says(tmp_path, caplog, rows, runs):
    made = logged({"max_rows": 2})
    made["components"] += [reader("a:str", component_id="in2", path="in.csv", outputs=("row3",)),
                           writer("a:str", component_id="out2", path="after.csv", inputs=("row3",))]
    made["flows"].append(flow("row3", "in2", "out2"))
    made["triggers"] = [{"type": "RunIf", "from": "it", "to": "in2",
                         "condition": f'((Integer)globalMap.get("it_NB_LINE")) == {rows}'}]
    assert len(same(tmp_path, caplog, None, made=made)) == 2
    assert (tmp_path / "v2" / "after.csv").exists() is runs


def test_rejected_rows_are_printed_with_their_reason(tmp_path, caplog):
    bad = "id:int, name:str"
    made = job(
        [reader(bad, header_rows=1, outputs=("row1", "bad")), writer(bad, inputs=("row1",)),
         {"id": "log", "type": "LogRow", "config": {"print_header": True},
          "schema": {"input": columns(bad), "output": columns(bad)}, "inputs": ["bad"], "outputs": ["row3"]},
         writer(None, component_id="rej", path="rej.csv", inputs=("row3",))],
        [flow("row1", "in", "out"), flow("bad", "in", "log", "reject"), flow("row3", "log", "rej")],
    )
    lines = same(tmp_path, caplog, None, made=made, inputs={"in.csv": b"id;name\n1;a\nx;b\n"})
    assert lines == ["id|name|errorCode|errorMessage",
                     "x|b|TYPE_CONVERSION|Column 'id': could not convert string to float: 'x'"]
    assert (tmp_path / "v2" / "rej.csv").read_bytes().startswith(b"id;name;errorCode_user;errorMessage_user\n")


def test_missing_value_where_the_log_row_allows_none_fails_it_after_it_printed(tmp_path, caplog):
    made = logged({}, SCHEMA, out_schema="id:int, name:str, amt:float!")
    caplog.set_level(logging.INFO)
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert not run.succeeded and "Column 'amt' has NULL values but is not nullable" in run.error
    assert printed(caplog, V2_LOGGER) == printed(caplog, V1_LOGGER) and len(printed(caplog, V2_LOGGER)) == 4


def test_columns_are_printed_as_they_arrive_and_passed_on_as_declared(tmp_path, caplog):
    made = logged({"print_header": True}, SCHEMA, out_schema="amt:float, id:int, name:str, extra:str")
    assert same(tmp_path, caplog, None, made=made)[0] == "id|name|amt"
    assert (tmp_path / "v2" / "out.csv").read_bytes().startswith(b"amt;id;name;extra\n10.5;1;alice;\n")


# ------------------------------------------------------------------
# Where v1's own printing is not the answer
# ------------------------------------------------------------------

def test_table_with_a_missing_whole_number_is_printed(tmp_path, caplog):
    # v1 fails here: its table cannot hold a missing value in an int column.
    data = b"id;name;amt\n1;alice;10.5\n;bob;2\n"
    assert not v1_finishes(tmp_path, {"table_print": True}, data)
    run, lines = v2_only(tmp_path, caplog, {"table_print": True}, data)
    assert run.succeeded
    assert lines == ["+--+-----+----+", "|id|name |amt |", "+--+-----+----+", "|1 |alice|10.5|", "|  |bob  |2.0 |",
                     "+--+-----+----+"]


def test_table_with_a_date_column_holding_nothing_is_printed(tmp_path, caplog):
    # v1 fails here as well: it cannot measure a date column whose printed rows are all missing.
    data, schema = b"k;d\na;\n", "k:str, d:datetime@%Y-%m-%d"
    assert not v1_finishes(tmp_path, {"table_print": True}, data, schema)
    run, lines = v2_only(tmp_path, caplog, {"table_print": True}, data, schema)
    assert run.succeeded and lines == ["+-+-+", "|k|d|", "+-+-+", "|a| |", "+-+-+"]


def test_table_columns_are_as_wide_as_what_is_printed_in_them(tmp_path, caplog):
    # v1 measures a date column without its time and a whole number without the ".0" it then prints.
    run, lines = v2_only(tmp_path, caplog, {"table_print": True}, b"d;n\n2024-01-31;5\n", "d:datetime@%Y-%m-%d, n:int!")
    assert run.succeeded
    assert lines == ["+-------------------+-+", "|d                  |n|", "+-------------------+-+",
                     "|2024-01-31 00:00:00|5|", "+-------------------+-+"]


def test_whole_number_is_printed_whole_whatever_the_other_columns_are(tmp_path, caplog):
    # v1 prints 1.0 for the int when every column of the row is a number and one is a float.
    run, lines = v2_only(tmp_path, caplog, {}, b"i;f\n1;1.5\n2;2.5\n", "i:int!, f:float")
    assert run.succeeded and lines == ["1|1.5", "2|2.5"]


def test_decimal_without_declared_places_prints_the_places_it_holds(tmp_path, caplog):
    # v1 prints the digits of the source text (1.50, 7, 1E+5); v2 holds ten places for such a column.
    run, lines = v2_only(tmp_path, caplog, {}, b"k;v\na;1.50\nb;7\nc;1e5\n", "k:str, v:Decimal")
    assert run.succeeded and lines == ["a|1.5000000000", "b|7.0000000000", "c|100000.0000000000"]


def test_columns_of_kinds_no_schema_declares_are_printed_as_python_prints_them(tmp_path, caplog):
    code = '''
df = df.select(
    pl.concat_list("id", "id").alias("pair"),
    pl.duration(hours="id").alias("gap"),
    pl.time(10, 11, 12).alias("at"),
    pl.struct("id", "name").alias("both"),
    pl.col("name").cast(pl.Categorical).alias("kind"),
    pl.col("name").cast(pl.Binary).alias("raw"),
    pl.datetime(2024, 1, 31, 10, time_zone="UTC").alias("zoned"),
    pl.lit(None).alias("nothing"),
)
'''
    made = job(
        [reader(SCHEMA, header_rows=1),
         {"id": "code", "type": "python_dataframe", "config": {"python_code": code, "dataframe": "polars"},
          "inputs": ["row1"], "outputs": ["row2"]},
         {"id": "it", "type": "log_row", "config": {"max_rows": 1, "print_header": True}, "inputs": ["row2"],
          "outputs": []}],
        [flow("row1", "in", "code"), flow("row2", "code", "it")],
    )
    caplog.set_level(logging.INFO)
    run = run_job(made, {"in.csv": DATA}, tmp_path / "v2", run_v2)
    assert run.succeeded, run.error
    assert printed(caplog, V2_LOGGER) == [
        "pair|gap|at|both|kind|raw|zoned|nothing",
        "[1, 1]|1:00:00|10:11:12|{'id': 1, 'name': 'alice'}|alice|b'alice'|2024-01-31 10:00:00+00:00|",
    ]


def test_empty_max_rows_means_the_default(tmp_path, caplog):
    # v1 fails on an empty max_rows.
    assert not v1_finishes(tmp_path, {"max_rows": ""})
    run, lines = v2_only(tmp_path, caplog, {"max_rows": ""})
    assert run.succeeded and len(lines) == 4


# ------------------------------------------------------------------
# What v2 says no to, and what it lets pass
# ------------------------------------------------------------------

def refused(config, **more):
    with pytest.raises(JobRefusedError) as caught:
        load_job(logged(config, **more))
    return caught.value.report.format()


@pytest.mark.parametrize(
    "config, said",
    [
        ({"max_rows": -1}, "max_rows: must not be negative"),
        ({"max_rows": "abc"}, "max_rows: expected a whole number"),
        ({"max_rows": 2.5}, "max_rows: expected a whole number"),
        ({"lengths": ["5"]}, "lengths: '5' is not a column width"),
        ({"lengths": [True]}, "lengths: True is not a column width"),
        ({"lengths": [2.9]}, "lengths: 2.9 is not a column width"),
        ({"lengths": [-1]}, "lengths: -1 is not a column width"),
        ({"lengths": 10}, "lengths: expected a list"),
        ({"table_print": "yes"}, "table_print: expected true or false"),
        ({"label": 5}, "label: expected text"),
        ({"bogus": 1}, "bogus: unknown config key"),
    ],
)
def test_refused_config(config, said):
    assert said in refused(config)


def test_negative_max_rows_from_the_context_stops_the_job(tmp_path):
    made = logged({"max_rows": "${context.shown}"})
    made["context"] = {"Default": {"shown": {"value": "-1", "type": "int"}}}
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert not run.succeeded and "max_rows: must not be negative" in run.error


def test_log_row_has_one_input_and_no_reject_output():
    made = logged({})
    made["components"].append(writer(None, component_id="rej", path="rej.csv", inputs=("bad",)))
    made["flows"].append(flow("bad", "it", "rej", "reject"))
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    assert "has no 'reject' output" in caught.value.report.format()

    made = logged({})
    made["components"].append(reader(SCHEMA, component_id="in2", outputs=("more",)))
    made["flows"].append(flow("more", "in2", "it"))
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    assert "takes at most 1 input(s)" in caught.value.report.format()


def test_v2_spellings():
    made = logged({"delimiter": ";", "max_rows": 5})
    made["components"][1]["type"] = "log_row"
    assert load_job(made).components["it"].config["delimiter"] == ";"
    assert "also given as 'delimiter'" in refused({"delimiter": ";", "fieldseparator": "|"})


SAMPLES = sorted(glob.glob(str(REPO_ROOT / "tests" / "talend_xml_samples" / "converted_jsons" / "*.json")))


def sample_log_rows():
    for path in SAMPLES:
        with open(path, encoding="utf-8") as handle:
            for component in json.load(handle)["components"]:
                if component["type"] == "LogRow":
                    yield pytest.param(component, id=f"{os.path.basename(path)}:{component['id']}")


@pytest.mark.parametrize("sample", list(sample_log_rows()))
def test_every_log_row_of_the_converter_samples_loads(sample):
    declared = sample["schema"]["input"] or sample["schema"]["output"]
    source = {"id": "in", "type": "FileInputDelimited", "config": {"filepath": "in.csv"},
              "schema": {"input": [], "output": declared or columns("a:str")}, "inputs": [], "outputs": ["row1"]}
    log = {"id": sample["id"], "type": sample["type"], "config": sample["config"], "schema": sample["schema"],
           "inputs": ["row1"], "outputs": []}
    loaded = load_job(job([source, log], [flow("row1", "in", sample["id"])]))
    assert loaded.components[sample["id"]].cls is LogRow


def test_the_filter_row_sample_holds_log_rows():
    assert len([param for param in sample_log_rows() if "Job_tFilterRow_0.1.json" in param.id]) == 2


@pytest.mark.parametrize("name", ["Job_tFileInputDelimited_0.1.json", "Job_tSortRow_0.1.json"])
def test_whole_converter_samples_that_end_in_a_log_row_load(name):
    path = next(path for path in SAMPLES if path.endswith(name))
    loaded = load_job(path)
    assert any(spec.cls is LogRow for spec in loaded.components.values())


@pytest.mark.parametrize("path", SAMPLES, ids=os.path.basename)
def test_no_converter_sample_is_refused_for_a_key_of_a_log_row(path):
    try:
        load_job(path)
    except JobRefusedError as refusal:
        # A log row fed by a component v2 does not have yet is left without its input; nothing else may be said.
        about = [(found.key, found.reason) for found in refusal.report if found.where.endswith("(LogRow)")]
        assert all(key == "inputs" for key, _ in about), about
