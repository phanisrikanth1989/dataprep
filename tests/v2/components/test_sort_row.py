"""Sort row, against v1 on the same job config and bytes."""
import datetime
import json
import os
from pathlib import Path

import polars as pl
import pytest

from src.v2 import load_job, run_job
from src.v2.components.base import Source
from src.v2.components.registry import REGISTRY, Registry
from src.v2.errors import JobRefusedError
from src.v2.job.keys import Key
from tests.v2.answer_key import assert_matches_v1

from .kit import flow, job, through, writer

SAMPLES = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons"

# name and txt are text (txt holds numbers, some unreadable); age, amt and d have missing values;
# rows 1 and 8 share a name, rows 2 and 9 an m, rows 1, 6 and 8 a txt read as a number.
SCHEMA = "id:int!, name:str, age:int, amt:float, flag:bool, d:datetime@%Y-%m-%d, m:Decimal#2!, txt:str"
DATA = (
    b"id;name;age;amt;flag;d;m;txt\n"
    b"1;bob;30;10.5;true;2024-01-31;1.50;10\n"
    b"2;Alice;;20;false;2023-12-01;7;9\n"
    b"3;;25;;true;;-2.345;abc\n"
    b"4;alice;41;-3.25;false;2024-02-29;100; 7 \n"
    b"5;Bob;25;1e3;false;2024-01-31;0;\n"
    b"6;30;-7;0;true;2025-06-15;12345.678;1e1\n"
    b"7;\xc3\xa9cole;7;-0.5;true;2024-01-01;-0.5;-2.5\n"
    b"8;bob;100;2.5;false;2024-12-31;25;10.0\n"
    b"9;Zed;;;false;;7;x\n"
)
GROUPS_SCHEMA = "id:int!, g:str, n:int, t:str"
GROUPS = b"id;g;n;t\n1;b;2;x\n2;a;;y\n3;b;1;z\n4;a;2;w\n5;;1;v\n6;b;2;u\n7;a;1;t\n8;b;;s\n9;a;2;r\n"
TEXT_SCHEMA = "id:int!, t:str"


def by(*keys):
    """Criteria from shorthand: ``"name:alpha:desc"``. A part left out is left out of the config."""
    made = []
    for key in keys:
        column, sort_type, order = (key.split(":") + ["", ""])[:3]
        criterion = {"column": column}
        if sort_type:
            criterion["sort_type"] = sort_type
        if order:
            criterion["order"] = order
        made.append(criterion)
    return made


def sort_job(config, schema=SCHEMA, out_schema=None):
    return through({"type": "SortRow", "config": config}, schema, out_schema)


def same(tmp_path, config, data=DATA, fails=False, **kwargs):
    """Both engines do the same with the job; ``fails`` says the job is one neither finishes."""
    run = assert_matches_v1(sort_job(config, **kwargs), {"in.csv": data}, tmp_path)
    assert run.succeeded is not fails, run.error
    return run


def ids(data):
    """The first field of every data line of a file."""
    return ",".join(line.split(b";")[0].decode() for line in data.split(b"\n")[1:-1])


def order(tmp_path, criteria, data=DATA, **kwargs):
    """The ids in the order both engines write them."""
    return ids(same(tmp_path, {"criteria": criteria}, data=data, **kwargs).files["out.csv"])


def v2(tmp_path, config, data=DATA, **kwargs):
    """Run on v2 only, inside tmp_path; returns (result, the folder)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(sort_job(config, **kwargs)), tmp_path
    finally:
        os.chdir(previous)


def v2_order(tmp_path, criteria, data=DATA, **kwargs):
    result, folder = v2(tmp_path, {"criteria": criteria}, data=data, **kwargs)
    assert result.status == "success", result.error
    return ids((folder / "out.csv").read_bytes())


def refused(config, **kwargs):
    """The refusal report v2 gives the job at load."""
    with pytest.raises(JobRefusedError) as caught:
        load_job(sort_job(config, **kwargs))
    return caught.value.report.format()


# ------------------------------------------------------------------
# One column: every sort type, both orders, every kind of column
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "column, sort_type, direction, want",
    [
        ("name", "alpha", "asc", "3,6,2,5,9,4,1,8,7"),
        ("name", "alpha", "desc", "7,1,8,4,9,5,2,6,3"),
        ("name", "num", "asc", "6,1,2,3,4,5,7,8,9"),
        ("name", "num", "desc", "6,1,2,3,4,5,7,8,9"),
        ("name", "date", "asc", "1,2,3,4,5,6,7,8,9"),
        ("name", "date", "desc", "1,2,3,4,5,6,7,8,9"),
        ("age", "alpha", "asc", "6,7,3,5,1,4,8,2,9"),
        ("age", "alpha", "desc", "8,4,1,3,5,7,6,2,9"),
        ("age", "num", "asc", "6,7,3,5,1,4,8,2,9"),
        ("age", "num", "desc", "8,4,1,3,5,7,6,2,9"),
        ("amt", "alpha", "asc", "4,7,6,8,1,2,5,3,9"),
        ("amt", "alpha", "desc", "5,2,1,8,6,7,4,3,9"),
        ("amt", "num", "asc", "4,7,6,8,1,2,5,3,9"),
        ("amt", "num", "desc", "5,2,1,8,6,7,4,3,9"),
        ("flag", "alpha", "asc", "2,4,5,8,9,1,3,6,7"),
        ("flag", "alpha", "desc", "1,3,6,7,2,4,5,8,9"),
        ("flag", "num", "asc", "2,4,5,8,9,1,3,6,7"),
        ("flag", "num", "desc", "1,3,6,7,2,4,5,8,9"),
        ("d", "alpha", "asc", "2,7,1,5,4,8,6,3,9"),
        ("d", "alpha", "desc", "6,8,4,1,5,7,2,3,9"),
        ("d", "num", "asc", "3,9,2,7,1,5,4,8,6"),
        ("d", "num", "desc", "6,8,4,1,5,7,2,3,9"),
        ("d", "date", "asc", "2,7,1,5,4,8,6,3,9"),
        ("d", "date", "desc", "6,8,4,1,5,7,2,3,9"),
        ("m", "alpha", "asc", "3,7,5,1,2,9,8,4,6"),
        ("m", "alpha", "desc", "6,4,8,2,9,1,5,7,3"),
        ("m", "num", "asc", "3,7,5,1,2,9,8,4,6"),
        ("m", "num", "desc", "6,4,8,2,9,1,5,7,3"),
        ("txt", "alpha", "asc", "5,4,7,1,8,6,2,3,9"),
        ("txt", "alpha", "desc", "9,3,2,6,8,1,7,4,5"),
        ("txt", "num", "asc", "7,4,2,1,6,8,3,5,9"),
        ("txt", "num", "desc", "1,6,8,2,4,7,3,5,9"),
        ("txt", "date", "asc", "1,2,3,4,5,6,7,8,9"),
        ("txt", "date", "desc", "1,2,3,4,5,6,7,8,9"),
    ],
)
def test_one_key(tmp_path, column, sort_type, direction, want):
    assert order(tmp_path, by(f"{column}:{sort_type}:{direction}")) == want


def test_sorted_rows_are_written_whole(tmp_path):
    run = same(tmp_path, {"criteria": by("amt:num:desc")})
    assert run.files["out.csv"].split(b"\n")[:3] == [
        b"id;name;age;amt;flag;d;m;txt",
        b"5;Bob;25;1000.0;false;2024-01-31;0.00;",
        b"2;Alice;;20.0;false;2023-12-01;7.00;9",
    ]


@pytest.mark.parametrize(
    "sort_type, direction, want",
    [
        ("alpha", "asc", "4,2,5,1,3"),
        ("alpha", "desc", "1,2,5,4,3"),
        ("num", "asc", "3,4,2,5,1"),
        ("num", "desc", "1,2,5,4,3"),
        ("date", "asc", "4,2,5,1,3"),
        ("date", "desc", "1,2,5,4,3"),
    ],
)
def test_dates_with_a_time(tmp_path, sort_type, direction, want):
    data = b"id;ts\n1;2024-03-01 10:00:00\n2;2024-03-01 09:00:00\n3;\n4;2024-01-15 23:59:59\n5;2024-03-01 09:00:00\n"
    schema = "id:int!, ts:datetime@%Y-%m-%d %H:%M:%S"
    assert order(tmp_path, by(f"ts:{sort_type}:{direction}"), data=data, schema=schema) == want


@pytest.mark.parametrize(
    "data, direction, want",
    [
        (b"1;2024-03-01\n2;2023-12-31\n3;\n4;2024-01-15\n5;notadate\n6;2024-01-15\n", "asc", "2,4,6,1,3,5"),
        (b"1;2024-03-01\n2;2023-12-31\n3;\n4;2024-01-15\n5;notadate\n6;2024-01-15\n", "desc", "1,4,6,2,3,5"),
        (b"1;2024-03-01 10:00:00\n2;2024-03-01 09:00:00\n3;\n4;2024-01-15 23:59:59\n", "asc", "4,2,1,3"),
        (b"1;2024-03-01 10:00:00\n2;2024-03-01 09:00:00\n3;\n4;2024-01-15 23:59:59\n", "desc", "1,2,4,3"),
        (b"1;31/01/2024\n2;01/02/2023\n3;15/06/2023\n", "asc", "2,3,1"),
        (b"1;31/01/2024\n2;01/02/2023\n3;15/06/2023\n", "desc", "1,3,2"),
    ],
)
def test_text_sorted_as_dates(tmp_path, data, direction, want):
    assert order(tmp_path, by(f"t:date:{direction}"), data=b"id;t\n" + data, schema=TEXT_SCHEMA) == want


def test_text_is_read_as_a_date_value_by_value(tmp_path):
    # v1 lets pandas guess one format for the whole column from its first value: month first here.
    data = b"id;t\n1;01/02/2024\n2;03/01/2024\n3;02/03/2023\n"
    assert v2_order(tmp_path / "a", by("t:date:asc"), data=data, schema=TEXT_SCHEMA) == "3,2,1"
    # v1's guess reads these; v2 reads %Y-%m-%d %H:%M:%S, %Y-%m-%d and %d/%m/%Y, and leaves the rest last.
    data = b"id;t\n1;20240301\n2;20231231\n3;2024-01-15\n"
    assert v2_order(tmp_path / "b", by("t:date:asc"), data=data, schema=TEXT_SCHEMA) == "3,1,2"


@pytest.mark.parametrize("direction, want", [("asc", "5,3,1,2,4"), ("desc", "1,3,5,2,4")])
def test_text_that_spells_not_a_number_sorts_with_the_unreadable(tmp_path, direction, want):
    data = b"id;t\n1;inf\n2;x\n3;7\n4;nan\n5;-inf\n"
    assert order(tmp_path, by(f"t:num:{direction}"), data=data, schema=TEXT_SCHEMA) == want


def test_text_sorted_as_numbers_skips_plain_blanks_only(tmp_path):
    data = "id;t\n1; 3\t\n2;\u00a01\n3;2\n".encode("utf-8")
    assert order(tmp_path, by("t:num:asc"), data=data, schema=TEXT_SCHEMA) == "3,1,2"


CLOSE = b"id;m\n1;12345678.1234567892\n2;12345678.1234567891\n3;5\n4;12345678.1234567890\n5;12345678.1234567999\n"
CLOSER = b"id;m\n1;8136260.8241560952\n2;8136260.8241560950\n3;5\n"


@pytest.mark.parametrize(
    "data, key, want",
    [
        (CLOSE, "m:num:asc", "3,1,2,4,5"),
        (CLOSE, "m:num:desc", "5,1,2,4,3"),
        (CLOSE, "m:alpha:asc", "3,4,2,1,5"),
        (CLOSE, "m:alpha:desc", "5,1,2,4,3"),
        (CLOSER, "m:num:asc", "3,1,2"),
        (CLOSER, "m:alpha:asc", "3,2,1"),
    ],
)
def test_decimals_one_number_cannot_tell_apart(tmp_path, data, key, want):
    # Sorted as num they are equal numbers and keep their input order; in their own order they are not.
    assert order(tmp_path, by(key), data=data, schema="id:int!, m:Decimal!") == want


@pytest.mark.parametrize("direction, want", [("asc", "3,1,5,2,4"), ("desc", "5,1,3,2,4")])
def test_decimal_with_missing_values_sorted_as_numbers(tmp_path, direction, want):
    data = b"id;m\n1;7\n2;\n3;-2.345\n4;\n5;100\n"
    assert order(tmp_path, by(f"m:num:{direction}"), data=data, schema="id:int!, m:Decimal#2") == want


@pytest.mark.parametrize("direction, want", [("asc", "3,1,5,2,4"), ("desc", "5,1,3,2,4")])
def test_decimal_with_missing_values_sorted_in_its_own_order(tmp_path, direction, want):
    # v1 fails here: it keeps an empty Decimal field as empty text and cannot compare text with a Decimal.
    data = b"id;m\n1;7\n2;\n3;-2.345\n4;\n5;100\n"
    assert v2_order(tmp_path, by(f"m:alpha:{direction}"), data=data, schema="id:int!, m:Decimal#2") == want


# ------------------------------------------------------------------
# Values no file read by v1 can hold: missing text, NaN, types the reader does not make
# ------------------------------------------------------------------

class Given(Source):
    """Rows a test hands over with their Polars types."""

    names = ("given",)
    keys = (Key("rows", required=True),)
    frames = {
        "floats": pl.DataFrame({"id": [1, 2, 3, 4, 5], "x": [1.5, float("nan"), None, -2.0, 0.5]}),
        "texts": pl.DataFrame({"id": [1, 2, 3, 4, 5], "x": ["b", None, "", "a", None]}),
        "days": pl.DataFrame({"id": [1, 2, 3], "x": [datetime.date(2024, 1, 31), None, datetime.date(2023, 12, 1)]}),
        "flags": pl.DataFrame({"id": [1, 2, 3], "x": [True, None, False]}),
        "nothing": pl.DataFrame({"id": [1, 2], "x": [None, None]}),
    }

    def read(self):
        return {"main": Given.frames[self.config["rows"]].lazy()}


TYPED = Registry()
for _cls in REGISTRY.classes() + [Given]:
    TYPED.register(_cls)


@pytest.mark.parametrize(
    "rows, key, want",
    [
        # A float that is not a number is a missing value, as in v1: last, either way.
        ("floats", "x:alpha:asc", "4,5,1,2,3"),
        ("floats", "x:alpha:desc", "1,5,4,2,3"),
        ("floats", "x:num:asc", "4,5,1,2,3"),
        ("floats", "x:num:desc", "1,5,4,2,3"),
        # Missing text is last; empty text is the smallest text.
        ("texts", "x:alpha:asc", "3,4,1,2,5"),
        ("texts", "x:alpha:desc", "1,4,3,2,5"),
        ("texts", "x:num:asc", "1,2,3,4,5"),
        ("texts", "x:date:desc", "1,2,3,4,5"),
        ("days", "x:alpha:asc", "3,1,2"),
        ("days", "x:date:desc", "1,3,2"),
        ("days", "x:num:asc", "2,3,1"),
        ("days", "x:num:desc", "1,3,2"),
        ("flags", "x:alpha:asc", "3,1,2"),
        ("flags", "x:num:desc", "1,3,2"),
        ("nothing", "x:alpha:desc", "1,2"),
        ("nothing", "x:num:asc", "1,2"),
        ("nothing", "x:date:asc", "1,2"),
    ],
)
def test_typed_values(tmp_path, rows, key, want):
    components = [
        {"id": "in", "type": "given", "config": {"rows": rows}, "inputs": [], "outputs": ["row1"]},
        {"id": "it", "type": "SortRow", "config": {"criteria": by(key)}, "inputs": ["row1"], "outputs": ["row2"]},
        writer(None),
    ]
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(job(components, [flow("row1", "in", "it"), flow("row2", "it", "out")]), registry=TYPED)
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    assert ids((tmp_path / "out.csv").read_bytes()) == want


# ------------------------------------------------------------------
# Several columns, ties and defaults
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "keys, want",
    [
        (("g:alpha:asc", "n:num:desc"), "5,4,9,7,2,1,6,3,8"),
        (("g:alpha:desc", "n:num:asc"), "3,1,6,8,7,4,9,2,5"),
        (("g:alpha:desc", "n:num:desc"), "1,6,3,8,4,9,7,2,5"),
        (("n:num:asc", "g:alpha:asc", "t:alpha:desc"), "5,7,3,4,9,1,6,2,8"),
        (("n:num:desc", "g:alpha:desc", "t:alpha:asc"), "6,1,9,4,3,7,5,8,2"),
        (("n:alpha:asc", "t:alpha:asc"), "7,5,3,9,6,4,1,8,2"),
    ],
)
def test_several_keys(tmp_path, keys, want):
    assert order(tmp_path, by(*keys), data=GROUPS, schema=GROUPS_SCHEMA) == want


@pytest.mark.parametrize(
    "key, want",
    [("n", "3,5,7,1,4,6,9,2,8"), ("g", "5,2,4,7,9,1,3,6,8"), ("t:alpha", "9,8,7,6,5,4,1,2,3"),
     ("n::desc", "1,4,6,9,3,5,7,2,8")],
)
def test_sort_type_defaults_to_alpha_and_order_to_asc(tmp_path, key, want):
    assert order(tmp_path, by(key), data=GROUPS, schema=GROUPS_SCHEMA) == want


@pytest.mark.parametrize(
    "keys, want",
    [
        (("t:num:asc", "t:alpha:asc"), "6,1,3,5,2,7,4"),
        (("t:alpha:asc", "t:num:asc"), "2,7,1,3,5,4,6"),
        (("t:num:asc", "t:alpha:desc"), "6,1,3,5,2,7,4"),
        (("t:num:desc", "t:num:asc"), "1,3,5,2,7,4,6"),
        (("t:alpha:desc", "t:num:desc"), "1,3,5,2,7,4,6"),
    ],
)
def test_column_listed_twice_takes_its_last_sort_type(tmp_path, keys, want):
    data = b"id;t\n1;10\n2;9\n3;10.0\n4;abc\n5;1e1\n6;\n7;9.0\n"
    assert order(tmp_path, by(*keys), data=data, schema=TEXT_SCHEMA) == want


def test_equal_rows_keep_their_input_order_on_a_large_input(tmp_path):
    lines = [b"id;g;n;f"]
    for i in range(1, 6001):
        n = b"" if i % 13 == 0 else str(i * 31 % 17).encode()
        f = b"" if i % 11 == 0 else str((i * 37 % 23) / 2).encode()
        lines.append(b"%d;%s;%s;%s" % (i, b"abcde"[i * 7 % 5:i * 7 % 5 + 1], n, f))
    data = b"\n".join(lines) + b"\n"
    run = same(tmp_path, {"criteria": by("g:alpha:desc", "n:num:asc", "f:num:desc")}, data=data,
               schema="id:int!, g:str, n:int, f:float")
    written = run.files["out.csv"].split(b"\n")
    assert len(written) == 6002 and written[1].split(b";")[1] == b"e"


# ------------------------------------------------------------------
# No rows, declared schemas, keys that change nothing
# ------------------------------------------------------------------

@pytest.mark.parametrize("data", [b"id;name;age;amt;flag;d;m;txt\n", b""])
def test_no_input_rows(tmp_path, data):
    run = same(tmp_path, {"criteria": by("name")}, data=data)
    assert run.files["out.csv"] == b"id;name;age;amt;flag;d;m;txt\n"


def test_no_input_rows_and_no_declared_schema_keeps_the_columns(tmp_path):
    # v1 writes an empty file: on empty input its sort hands on a frame with no columns.
    made = sort_job({"criteria": by("t:num")}, schema=TEXT_SCHEMA)
    made["components"][1]["schema"] = {"input": [], "output": []}
    made["components"][2]["schema"] = {"input": [], "output": []}
    (tmp_path / "in.csv").write_bytes(b"id;t\n")
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert run_job(made).status == "success"
    finally:
        os.chdir(previous)
    assert (tmp_path / "out.csv").read_bytes() == b"id;t\n"


def test_sort_that_declares_no_schema(tmp_path):
    made = sort_job({"criteria": by("amt:num:desc")})
    made["components"][1]["schema"] = {"input": [], "output": []}
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.succeeded and ids(run.files["out.csv"]) == "5,2,1,8,6,7,4,3,9"


def test_declared_columns_come_first(tmp_path):
    run = same(tmp_path, {"criteria": by("t:num:desc")}, data=b"id;t\n1;5\n2;7\n", schema=TEXT_SCHEMA, out_schema="t:str")
    assert run.files["out.csv"] == b"t;id\n7;2\n5;1\n"


@pytest.mark.parametrize("config", [{}, {"die_on_error": True}])
def test_missing_value_the_schema_forbids_fails_the_sort(tmp_path, config):
    schema = "id:int!, name:str, age:int!, amt:float, flag:bool, d:datetime@%Y-%m-%d, m:Decimal#2!, txt:str"
    same(tmp_path, dict(config, criteria=by("id:num:desc")), out_schema=schema, fails=True)
    result, _ = v2(tmp_path / "direct", dict(config, criteria=by("id:num:desc")), out_schema=schema)
    # Rows 2 and 9 lack an age; sorted by id descending, row 9 is the first the sort hands on.
    assert result.failed_component == "it"
    assert result.error == "Column 'age' has NULL values but is not nullable; the row is line 10 of in.csv"


def test_missing_value_the_schema_forbids_drops_the_row_when_errors_are_not_fatal(tmp_path):
    schema = "id:int!, name:str, age:int!, amt:float, flag:bool, d:datetime@%Y-%m-%d, m:Decimal#2!, txt:str"
    run = same(tmp_path, {"die_on_error": False, "criteria": by("id:num:desc")}, out_schema=schema)
    assert ids(run.files["out.csv"]) == "8,7,6,5,4,3,1"


def test_keys_that_change_nothing_are_accepted(tmp_path):
    config = {"criteria": by("amt:num:desc"), "external": True, "tempfile": "/tmp/sort", "createdir": True,
              "external_sort_buffersize": "1000000", "tstatcatcher_stats": False, "label": "Sort_By_Amount",
              "execution_mode": "batch", "chunk_size": 3}
    assert ids(same(tmp_path, config).files["out.csv"]) == "5,2,1,8,6,7,4,3,9"


@pytest.mark.parametrize("name", ["SortRow", "tSortRow"])
def test_v1_type_names(tmp_path, name):
    made = sort_job({"criteria": by("amt:num:desc")})
    made["components"][1]["type"] = name
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.succeeded and ids(run.files["out.csv"]) == "5,2,1,8,6,7,4,3,9"


def test_v2_spellings(tmp_path):
    made = sort_job({"columns": [{"name": "amt", "sort_type": "num", "order": "desc"}]})
    made["components"][1]["type"] = "sort_row"
    (tmp_path / "in.csv").write_bytes(DATA)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert run_job(made).status == "success"
    finally:
        os.chdir(previous)
    assert ids((tmp_path / "out.csv").read_bytes()) == "5,2,1,8,6,7,4,3,9"


# ------------------------------------------------------------------
# What v2 says no to
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "config, said",
    [
        ({"criteria": []}, "criteria: at least one column to sort by is needed"),
        ({}, "criteria: required config key is missing"),
        ({"criteria": by("amt:NUM:asc")}, "criteria[0].sort_type: 'NUM' is not allowed; use one of 'alpha', 'num', 'date'"),
        ({"criteria": by("amt:num:ASC")}, "criteria[0].order: 'ASC' is not allowed; use one of 'asc', 'desc'"),
        ({"criteria": [{"sort_type": "num", "order": "asc"}]}, "criteria[0].column: required config key is missing"),
        ({"criteria": "amt"}, "criteria: expected a list"),
    ],
)
def test_config_neither_engine_accepts(tmp_path, config, said):
    same(tmp_path, config, fails=True)
    assert said in refused(config)


@pytest.mark.parametrize(
    "config, said",
    [
        # v1 leaves a criterion on a column that is not there out of the sort.
        ({"criteria": by("nope:num:asc", "amt:num:desc")}, "criteria[0]: there is no column 'nope' to sort by"),
        # v1 reads a number as nanoseconds since 1970, and anything else as no date at all.
        ({"criteria": by("amt:date:asc")}, "criteria[0]: column 'amt' is a number and cannot be sorted as a date"),
        ({"criteria": by("age:date:asc")}, "criteria[0]: column 'age' is a number and cannot be sorted as a date"),
        ({"criteria": by("m:date:asc")}, "criteria[0]: column 'm' is a number and cannot be sorted as a date"),
        ({"criteria": by("name", "flag:date:desc")},
         "criteria[1]: column 'flag' is a true/false value and cannot be sorted as a date"),
        ({"criteria": by("amt"), "bogus": 1}, "bogus: unknown config key"),
        ({"criteria": [{"column": "amt", "nulls_last": True}]}, "criteria[0].nulls_last: unknown config key"),
        ({"criteria": by("amt"), "columns": by("amt")}, "columns: also given as 'criteria'; use one spelling"),
    ],
)
def test_refused_config(config, said):
    assert said in refused(config)


@pytest.mark.parametrize("sample", ["Job_tSortRow_0.1.json", "Job_tAggregatedSortedRow_0.1.json"])
def test_converter_sample_loads(sample):
    component = next(c for c in json.loads((SAMPLES / sample).read_text())["components"] if c["type"] == "SortRow")
    schema = ", ".join(
        "{name}:{type}{nullable}{pattern}".format(
            name=column["name"], type=column["type"], nullable="" if column["nullable"] else "!",
            pattern="@" + column["date_pattern"] if column.get("date_pattern") else "",
        )
        for column in component["schema"]["input"]
    )
    load_job(through({"type": "SortRow", "config": component["config"], "schema": component["schema"]}, schema))
