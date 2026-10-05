"""Filter rows, against v1 on the same job config and bytes."""
import copy
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

from .kit import columns, flow, job, reader, through, writer

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tFilterRow_0.1.json"

# name is text (empty, padded, mixed case, a number written as text); age is a whole number that may be
# missing (row 2); qty is one that may not; amt (row 3) and d (row 3) may be missing; m is a Decimal.
SCHEMA = "id:int!, name:str, age:int, qty:int!, amt:float, flag:bool, d:datetime@%Y-%m-%d, m:Decimal#2!"
DATA = (
    b"id;name;age;qty;amt;flag;d;m\n"
    b"1;Alice;30;30;10.5;true;2024-01-31;1.50\n"
    b"2;bob;;41;20;false;2023-12-01;7\n"
    b"3;;25;25;;true;;-2.345\n"
    b"4; Carol ;41;-7;-3.25;false;2024-02-29;100\n"
    b"5;dAVE;25;25;1e3;false;2024-01-31;0\n"
    b"6;30;-7;0;0;true;2025-06-15;12345.678\n"
    b"7;\tEve\t;7;7;-0.5;true;2024-01-01;-0.5\n"
    b"8;x;100;100;2.5;false;2024-12-31;25\n"
)
EVERY_ROW = "1,2,3,4,5,6,7,8"


def filter_job(config, schema=SCHEMA, out_schema=None, reject=True, reject_schema=None):
    """file -> filter -> out.csv, with the filter's reject output written to rej.csv."""
    made = through({"type": "FilterRows", "config": config}, schema, out_schema)
    if reject:
        made["components"][1]["outputs"] = ["row2", "bad"]
        made["components"].append(writer(reject_schema, component_id="rej", path="rej.csv", inputs=("bad",)))
        made["flows"].append(flow("bad", "it", "rej", "reject"))
    return made


def same(tmp_path, config, data=DATA, fails=False, **kwargs):
    """Both engines do the same with the job; ``fails`` says the job is one neither finishes."""
    run = assert_matches_v1(filter_job(config, **kwargs), {"in.csv": data}, tmp_path)
    assert run.succeeded is not fails, run.error
    return run


def ids(data):
    """The first field of every data line of a file."""
    return ",".join(line.split(b";")[0].decode() for line in data.split(b"\n")[1:-1])


def kept(tmp_path, condition, data=DATA, **kwargs):
    """The ids one condition lets through, the same on both engines; every other row is rejected."""
    run = same(tmp_path, {"conditions": [condition]}, data=data, **kwargs)
    passed, rejected = ids(run.files["out.csv"]), ids(run.files["rej.csv"])
    seen = sorted(int(n) for n in (passed + "," + rejected).split(",") if n)
    assert seen == list(range(1, data.count(b"\n"))), "a row left by neither output, or by both"
    return passed


def v2(tmp_path, config, data=DATA, **kwargs):
    """Run on v2 only, inside tmp_path; returns (result, the folder)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(filter_job(config, **kwargs)), tmp_path
    finally:
        os.chdir(previous)


def v2_kept(tmp_path, config, data=DATA, **kwargs):
    """(ids kept, ids rejected) on v2 only."""
    result, folder = v2(tmp_path, config, data=data, **kwargs)
    assert result.status == "success", result.error
    return ids((folder / "out.csv").read_bytes()), ids((folder / "rej.csv").read_bytes())


def refused(config, **kwargs):
    """The refusal report v2 gives the job at load."""
    with pytest.raises(JobRefusedError) as caught:
        load_job(filter_job(config, **kwargs))
    return caught.value.report.format()


def cond(column, operator, value="", function=""):
    return {"column": column, "function": function, "operator": operator, "value": value}


# ------------------------------------------------------------------
# A value that reads as a number: the column is compared as a number
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "column, operator, value, want",
    [
        ("qty", "==", "25", "3,5"),
        ("qty", "!=", "25", "1,2,4,6,7,8"),
        ("qty", ">", "25", "1,2,8"),
        ("qty", "<", "25", "4,6,7"),
        ("qty", ">=", "25", "1,2,3,5,8"),
        ("qty", "<=", "25", "3,4,5,6,7"),
        ("amt", "==", "20", "2"),
        ("amt", "!=", "20", "1,3,4,5,6,7,8"),
        ("amt", ">", "0", "1,2,5,8"),
        ("amt", "<", "0", "4,7"),
        ("amt", ">=", "2.5", "1,2,5,8"),
        ("amt", "<=", "2.5", "4,6,7,8"),
        ("name", "==", "30", "6"),
        ("name", "!=", "30", "1,2,3,4,5,7,8"),
        ("name", ">", "7", "6"),
        ("name", "<=", "30", "6"),
        ("flag", "==", "1", "1,3,6,7"),
        ("flag", "==", "0", "2,4,5,8"),
        ("flag", "<", "1", "2,4,5,8"),
        ("flag", ">", "0.5", "1,3,6,7"),
        ("flag", "!=", "1", "2,4,5,8"),
        ("m", "==", "7", "2"),
        ("m", ">", "0", "1,2,4,6,8"),
        ("m", "<=", "-0.5", "3,7"),
        ("m", "!=", "100", "1,2,3,5,6,7,8"),
        ("m", "==", "-2.35", "3"),
        ("m", "==", "12345.68", "6"),
    ],
)
def test_comparison_with_a_number(tmp_path, column, operator, value, want):
    assert kept(tmp_path, cond(column, operator, value)) == want


@pytest.mark.parametrize(
    "operator, value, want",
    [("==", "8136260.824156095", "1"), ("<", "8136260.824156095", "3"), (">=", "8136260.824156095", "1,2"),
     ("==", "63291572428049200539", "2"), ("!=", "63291572428049200539", "1,3"), ("ABS", "9346536460034383.25", "3")],
)
def test_decimal_of_many_digits_compares_as_the_number_nearest_to_it(tmp_path, operator, value, want):
    data = b"id;m\n1;8136260.824156095\n2;63291572428049200539\n3;-9346536460034383.25\n"
    condition = cond("m", "==", value, "ABS") if operator == "ABS" else cond("m", operator, value)
    schema = "id:int!, m:Decimal!"
    assert kept(tmp_path, condition, data=data, schema=schema, reject_schema=schema + ", errorMessage:str") == want


@pytest.mark.parametrize(
    "column, operator, value, want",
    [
        ("qty", "==", " 25 ", "3,5"),
        ("qty", "==", "2.5e1", "3,5"),
        ("qty", "==", "25.0", "3,5"),
        ("qty", "==", 25, "3,5"),
        ("qty", "==", 25.0, "3,5"),
        ("qty", ">", "1_0", "1,2,3,5,8"),
        ("qty", "<", "inf", EVERY_ROW),
        ("qty", ">", "-Infinity", EVERY_ROW),
        ("qty", "<", True, "4,6"),
        ("flag", "==", True, "1,3,6,7"),
        ("flag", "==", False, "2,4,5,8"),
    ],
)
def test_every_way_of_writing_a_number_counts(tmp_path, column, operator, value, want):
    assert kept(tmp_path, cond(column, operator, value)) == want


@pytest.mark.parametrize(
    "column, operator, value, want",
    [
        ("qty", "==", "nan", ""),
        ("qty", "!=", "NaN", EVERY_ROW),
        ("qty", "<", "nan", ""),
        ("qty", ">", "nan", ""),
        ("qty", "<=", "nan", ""),
        ("qty", ">=", "nan", ""),
        ("amt", "!=", "nan", EVERY_ROW),
        ("amt", "<", "nan", ""),
        ("name", ">", "nan", ""),
    ],
)
def test_nothing_compares_with_not_a_number(tmp_path, column, operator, value, want):
    assert kept(tmp_path, cond(column, operator, value)) == want


# ------------------------------------------------------------------
# Any other value: the column is compared as text
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "column, operator, value, want",
    [
        ("name", "==", "bob", "2"),
        ("name", "!=", "bob", "1,3,4,5,6,7,8"),
        ("name", ">", "bob", "5,8"),
        ("name", "<", "bob", "1,3,4,6,7"),
        ("name", ">=", "bob", "2,5,8"),
        ("name", "<=", "bob", "1,2,3,4,6,7"),
        ("name", "==", "", "3"),
        ("name", "!=", "", "1,2,4,5,6,7,8"),
        ("name", ">", "", "1,2,4,5,6,7,8"),
        ("name", "<=", "", "3"),
        ("name", "==", "Bob", ""),
        ("name", "!=", None, EVERY_ROW),
        ("name", "==", None, ""),
        ("qty", "==", "abc", ""),
        ("qty", "!=", "abc", EVERY_ROW),
        ("qty", ">", "3x", "2,7"),
        ("qty", "<", "3x", "1,3,4,5,6,8"),
        ("qty", "<=", "", ""),
        ("age", "<", "abc", "1,3,4,5,6,7,8"),
        ("age", "!=", "abc", EVERY_ROW),
        ("age", ">", "", "1,3,4,5,6,7,8"),
        ("age", "==", "abc", ""),
        ("amt", ">", "1x", "2,8"),
        ("amt", "==", "", ""),
        ("amt", "!=", "", EVERY_ROW),
        ("amt", "<", "x", "1,2,4,5,6,7,8"),
        ("flag", "==", "True", "1,3,6,7"),
        ("flag", "==", "true", ""),
        ("flag", "!=", "False", "1,3,6,7"),
        ("flag", ">", "F", EVERY_ROW),
        ("flag", "<", "True", "2,4,5,8"),
        ("d", "==", "2024-01-31", "1,5"),
        ("d", "!=", "2024-01-31", "2,3,4,6,7,8"),
        ("d", ">", "2024-01-31", "4,6,8"),
        ("d", "<", "2024-01-01", "2"),
        ("d", ">=", "2024-02", "4,6,8"),
        ("d", "<=", "2024-01-31", "1,2,5,7"),
        ("d", "==", "2024-01-31 00:00:00", ""),
        ("d", "==", "", ""),
    ],
)
def test_comparison_with_text(tmp_path, column, operator, value, want):
    assert kept(tmp_path, cond(column, operator, value)) == want


# ------------------------------------------------------------------
# The text operators
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "operator, value, want",
    [
        ("MATCHES", "[a-z]+", "2,8"),
        ("MATCHES", ".*o.*", "2,4"),
        ("MATCHES", "", "3"),
        ("MATCHES", r"\w+", "1,2,5,6,8"),
        ("MATCHES", r"\d+", "6"),
        ("MATCHES", r"\s.*\s", "4,7"),
        ("MATCHES", "(?i)[a-z]+", "1,2,5,8"),
        ("MATCHES", "bob|x", "2,8"),
        ("MATCHES", "^bob$", "2"),
        ("MATCHES", "b", ""),
        ("MATCHES", r"[^\W\d]+", "1,2,5,8"),
        ("MATCHES", r"\S+\Z", "1,2,5,6,8"),
        ("MATCHES", r"[\w ]+", "1,2,4,5,6,8"),
        ("MATCHES", r"\D*", "1,2,3,4,5,7,8"),
        ("MATCHES", 30, "6"),
        ("CONTAINS", "o", "2,4"),
        ("CONTAINS", "", EVERY_ROW),
        ("CONTAINS", " ", "4"),
        ("CONTAINS", "A", "1,5"),
        ("CONTAINS", ".*", ""),
        ("CONTAINS", 3, "6"),
        ("NOT_CONTAINS", "o", "1,3,5,6,7,8"),
        ("NOT_CONTAINS", "", ""),
        ("STARTS_WITH", "A", "1"),
        ("STARTS_WITH", "", EVERY_ROW),
        ("STARTS_WITH", " ", "4"),
        ("STARTS_WITH", 3, "6"),
        ("ENDS_WITH", "e", "1"),
        ("ENDS_WITH", " ", "4"),
        ("ENDS_WITH", "", EVERY_ROW),
        ("LENGTH_LT", "4", "2,3,6,8"),
        ("LENGTH_GT", "4", "1,4,7"),
        ("LENGTH_LT", "0", ""),
        ("LENGTH_GT", "0", "1,2,4,5,6,7,8"),
        ("LENGTH_LT", " 4 ", "2,3,6,8"),
        ("LENGTH_LT", 3.9, "3,6,8"),
        ("LENGTH_GT", "-1", EVERY_ROW),
        ("LENGTH_GT", 4, "1,4,7"),
        ("LENGTH_LT", True, "3"),
    ],
)
def test_text_operators_on_text(tmp_path, operator, value, want):
    assert kept(tmp_path, cond("name", operator, value)) == want


@pytest.mark.parametrize(
    "column, operator, value, want",
    [
        ("qty", "MATCHES", r"-?\d\d", "1,2,3,5"),
        ("qty", "CONTAINS", "5", "3,5"),
        ("qty", "CONTAINS", 5, "3,5"),
        ("qty", "STARTS_WITH", "-", "4"),
        ("qty", "ENDS_WITH", "0", "1,6,8"),
        ("qty", "LENGTH_LT", "2", "6,7"),
        ("qty", "LENGTH_GT", "2", "8"),
        ("qty", "NOT_CONTAINS", "0", "2,3,4,5,7"),
        ("age", "CONTAINS", "5", "3,5"),
        ("age", "NOT_CONTAINS", "5", "1,2,4,6,7,8"),
        ("age", "MATCHES", ".*", "1,3,4,5,6,7,8"),
        ("age", "LENGTH_LT", "9", "1,3,4,5,6,7,8"),
        ("age", "LENGTH_GT", "0", "1,3,4,5,6,7,8"),
        ("age", "STARTS_WITH", "", "1,3,4,5,6,7,8"),
        ("age", "ENDS_WITH", "", "1,3,4,5,6,7,8"),
        ("amt", "ENDS_WITH", ".0", "2,5,6"),
        ("amt", "STARTS_WITH", "-", "4,7"),
        ("amt", "CONTAINS", ".", "1,2,4,5,6,7,8"),
        ("amt", "MATCHES", r"-?\d+\.\d+", "1,2,4,5,6,7,8"),
        ("amt", "LENGTH_GT", "4", "4,5"),
        ("amt", "NOT_CONTAINS", ".5", "2,3,4,5,6"),
        ("amt", "LENGTH_LT", "4", "6,8"),
        ("flag", "STARTS_WITH", "T", "1,3,6,7"),
        ("flag", "CONTAINS", "a", "2,4,5,8"),
        ("flag", "MATCHES", "True|False", EVERY_ROW),
        ("flag", "LENGTH_LT", "5", "1,3,6,7"),
        ("flag", "NOT_CONTAINS", "T", "2,4,5,8"),
        ("flag", "ENDS_WITH", "e", EVERY_ROW),
        ("flag", "MATCHES", "true", ""),
        ("d", "STARTS_WITH", "2024", "1,4,5,7,8"),
        ("d", "ENDS_WITH", "-31", "1,5,8"),
        ("d", "CONTAINS", "-01-", "1,5,7"),
        ("d", "NOT_CONTAINS", "-01-", "2,3,4,6,8"),
        ("d", "MATCHES", r"2024-\d\d-\d\d", "1,4,5,7,8"),
        ("d", "LENGTH_LT", "11", "1,2,4,5,6,7,8"),
        ("d", "LENGTH_GT", "10", ""),
        ("d", "LENGTH_GT", "9", "1,2,4,5,6,7,8"),
    ],
)
def test_text_operators_read_other_columns_as_python_prints_them(tmp_path, column, operator, value, want):
    assert kept(tmp_path, cond(column, operator, value)) == want


@pytest.mark.parametrize(
    "column, operator, value, want",
    [
        ("name", "IS_NULL", "", ""),
        ("name", "IS_NOT_NULL", "", EVERY_ROW),
        ("age", "IS_NULL", "", "2"),
        ("age", "IS_NOT_NULL", "", "1,3,4,5,6,7,8"),
        ("qty", "IS_NULL", "", ""),
        ("qty", "IS_NOT_NULL", "", EVERY_ROW),
        ("amt", "IS_NULL", "", "3"),
        ("amt", "IS_NOT_NULL", "", "1,2,4,5,6,7,8"),
        ("flag", "IS_NULL", "", ""),
        ("flag", "IS_NOT_NULL", "", EVERY_ROW),
        ("d", "IS_NULL", "", "3"),
        ("d", "IS_NOT_NULL", "", "1,2,4,5,6,7,8"),
        ("m", "IS_NULL", "", ""),
        ("m", "IS_NOT_NULL", "", EVERY_ROW),
        ("amt", "IS_NULL", None, "3"),
        ("amt", "IS_NOT_NULL", "ignored", "1,2,4,5,6,7,8"),
        ("age", "IS_NULL", 0, "2"),
    ],
)
def test_missing_values(tmp_path, column, operator, value, want):
    assert kept(tmp_path, cond(column, operator, value)) == want


# ------------------------------------------------------------------
# Functions applied to the column first
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "function, operator, value, want",
    [
        ("LOWER", "==", "alice", "1"),
        ("LOWER", "==", "dave", "5"),
        ("LOWER", "!=", "alice", "2,3,4,5,6,7,8"),
        ("LOWER", "CONTAINS", "a", "1,4,5"),
        ("LOWER", "==", "30", "6"),
        ("LOWER", "IS_NULL", "", ""),
        ("UPPER", "==", "ALICE", "1"),
        ("UPPER", "==", "DAVE", "5"),
        ("UPPER", "STARTS_WITH", "A", "1"),
        ("UPPER", "MATCHES", "[A-Z]+", "1,2,5,8"),
        ("lower", "==", "alice", "1"),
        (" Upper ", "==", "ALICE", "1"),
        ("LOWER_FIRST", "==", "a", "1"),
        ("LOWER_FIRST", "==", "d", "5"),
        ("LOWER_FIRST", "==", "", ""),
        ("LOWER_FIRST", "!=", "a", "2,3,4,5,6,7,8"),
        ("LOWER_FIRST", "IS_NULL", "", "3"),
        ("LOWER_FIRST", "IS_NOT_NULL", "", "1,2,4,5,6,7,8"),
        ("LOWER_FIRST", "==", " ", "4"),
        ("LOWER_FIRST", "==", "3", "6"),
        ("LOWER_FIRST", "LENGTH_LT", "1", ""),
        ("LOWER_FIRST", "LENGTH_GT", "0", "1,2,4,5,6,7,8"),
        ("LOWER_FIRST", "CONTAINS", "", "1,2,4,5,6,7,8"),
        ("LOWER_FIRST", "NOT_CONTAINS", "a", "2,3,4,5,6,7,8"),
        ("UPPER_FIRST", "==", "A", "1"),
        ("UPPER_FIRST", "==", "D", "5"),
        ("UPPER_FIRST", "==", "B", "2"),
        ("UPPER_FIRST", "==", "X", "8"),
        ("UPPER_FIRST", "==", "\t", "7"),
        ("UPPER_FIRST", "IS_NULL", "", "3"),
        ("LENGTH", "==", "5", "1,7"),
        ("LENGTH", ">", "3", "1,4,5,7"),
        ("LENGTH", "<", "1", "3"),
        ("LENGTH", "==", "0", "3"),
        ("LENGTH", "!=", "5", "2,3,4,5,6,8"),
        ("LENGTH", ">=", "7", "4"),
        ("LENGTH", "<=", 1, "3,8"),
        ("LENGTH", "IS_NULL", "", ""),
        ("LENGTH", "IS_NOT_NULL", "", EVERY_ROW),
        ("TRIM", "==", "Carol", "4"),
        ("TRIM", "==", "Eve", "7"),
        ("TRIM", "==", "", "3"),
        ("TRIM", "LENGTH_LT", "4", "2,3,6,7,8"),
        ("TRIM", "==", "30", "6"),
        ("LTRIM", "==", "Carol ", "4"),
        ("LTRIM", "==", "Eve\t", "7"),
        ("LTRIM", "STARTS_WITH", "C", "4"),
        ("LTRIM", "ENDS_WITH", " ", "4"),
        ("RTRIM", "==", " Carol", "4"),
        ("RTRIM", "==", "\tEve", "7"),
        ("RTRIM", "ENDS_WITH", "l", "4"),
        ("RTRIM", "STARTS_WITH", " ", "4"),
        ("ABS", "==", "30", "6"),
        ("ABS", ">", "0", "6"),
        ("ABS", "!=", "30", "1,2,3,4,5,7,8"),
        ("ABS", "IS_NULL", "", "1,2,3,4,5,7,8"),
        ("ABS", "IS_NOT_NULL", "", "6"),
        ("LEFT(2)", "==", "Al", "1"),
        ("LEFT(2)", "==", "bo", "2"),
        ("LEFT(2)", "==", "", "3"),
        ("LEFT(2)", "==", " C", "4"),
        ("LEFT(2)", "==", "x", "8"),
        ("LEFT(2)", "==", "30", "6"),
        ("LEFT(1)", "IS_NULL", "", ""),
        ("RIGHT(2)", "==", "ce", "1"),
        ("RIGHT(2)", "==", "ob", "2"),
        ("RIGHT(2)", "==", "", "3"),
        ("RIGHT(2)", "==", "l ", "4"),
        ("RIGHT(2)", "==", "x", "8"),
        ("LEFT(0)", "==", "", EVERY_ROW),
        ("RIGHT(0)", "==", "", "3"),
        ("RIGHT(0)", "==", "bob", "2"),
        ("left(3)", "==", "Ali", "1"),
        ("RIGHT(100)", "==", "bob", "2"),
        ("LEFT(100)", "==", "bob", "2"),
        (" right(1) ", "==", "e", "1"),
    ],
)
def test_functions_on_text(tmp_path, function, operator, value, want):
    assert kept(tmp_path, cond("name", operator, value, function)) == want


@pytest.mark.parametrize(
    "column, function, operator, value, want",
    [
        ("qty", "LOWER", "==", "25", "3,5"),
        ("qty", "LENGTH", "==", "2", "1,2,3,4,5"),
        ("qty", "LENGTH", ">", "2", "8"),
        ("qty", "TRIM", "==", "25", "3,5"),
        ("qty", "ABS", "==", "7", "4,7"),
        ("qty", "ABS", ">", "25", "1,2,8"),
        ("qty", "ABS", "<", "1", "6"),
        ("qty", "ABS", "!=", "25", "1,2,4,6,7,8"),
        ("qty", "LEFT(1)", "==", "2", "3,5"),
        ("qty", "RIGHT(1)", "==", "5", "3,5"),
        ("qty", "UPPER_FIRST", "==", "-", "4"),
        ("qty", "LOWER_FIRST", "==", "1", "8"),
        ("qty", "RIGHT(2)", "CONTAINS", "0", "1,6,8"),
        ("age", "LOWER", "IS_NULL", "", "2"),
        ("age", "LENGTH", "IS_NULL", "", "2"),
        ("age", "LENGTH", "==", "2", "1,3,4,5,6"),
        ("age", "UPPER", "==", "25", "3,5"),
        ("age", "ABS", "IS_NULL", "", "2"),
        ("age", "LEFT(1)", "!=", "2", "1,2,4,6,7,8"),
        ("age", "LOWER_FIRST", "IS_NULL", "", "2"),
        ("age", "RTRIM", "IS_NOT_NULL", "", "1,3,4,5,6,7,8"),
        ("amt", "LENGTH", ">", "3", "1,2,4,5,7"),
        ("amt", "LENGTH", "IS_NULL", "", "3"),
        ("amt", "ABS", ">", "3", "1,2,4,5"),
        ("amt", "ABS", "<", "1", "6,7"),
        ("amt", "ABS", "==", "0.5", "7"),
        ("amt", "ABS", "IS_NULL", "", "3"),
        ("amt", "ABS", "!=", "0", "1,2,3,4,5,7,8"),
        ("amt", "LOWER_FIRST", "==", "2", "2,8"),
        ("amt", "UPPER_FIRST", "==", "-", "4,7"),
        ("amt", "RIGHT(3)", "==", ".25", "4"),
        ("amt", "LEFT(2)", "==", "10", "1,5"),
        ("amt", "UPPER", "ENDS_WITH", ".0", "2,5,6"),
        ("flag", "LOWER", "==", "true", "1,3,6,7"),
        ("flag", "UPPER", "==", "TRUE", "1,3,6,7"),
        ("flag", "UPPER", "CONTAINS", "LS", "2,4,5,8"),
        ("flag", "LOWER_FIRST", "==", "t", "1,3,6,7"),
        ("flag", "UPPER_FIRST", "==", "F", "2,4,5,8"),
        ("flag", "LENGTH", "==", "4", "1,3,6,7"),
        ("flag", "LENGTH", ">", "4", "2,4,5,8"),
        ("flag", "ABS", "<", "1", "2,4,5,8"),
        ("flag", "ABS", "==", "1", "1,3,6,7"),
        ("flag", "ABS", "IS_NULL", "", ""),
        ("flag", "LEFT(1)", "==", "T", "1,3,6,7"),
        ("flag", "RIGHT(2)", "==", "se", "2,4,5,8"),
        ("d", "LEFT(4)", "==", "2024", "1,4,5,7,8"),
        ("d", "RIGHT(2)", "==", "31", "1,5,8"),
        ("d", "LENGTH", "==", "10", "1,2,4,5,6,7,8"),
        ("d", "LENGTH", "IS_NULL", "", "3"),
        ("d", "LOWER_FIRST", "==", "2", "1,2,4,5,6,7,8"),
        ("d", "LOWER", "STARTS_WITH", "2023", "2"),
        ("d", "RIGHT(5)", "==", "01-31", "1,5"),
        ("d", "TRIM", "==", "2024-01-31", "1,5"),
        ("m", "ABS", "==", "0.5", "7"),
        ("m", "ABS", ">", "3", "2,4,6,8"),
        ("m", "ABS", "<", "1", "5,7"),
        ("m", "ABS", "!=", "25", "1,2,3,4,5,6,7"),
        ("m", "ABS", "IS_NULL", "", ""),
    ],
)
def test_functions_on_other_columns(tmp_path, column, function, operator, value, want):
    assert kept(tmp_path, cond(column, operator, value, function)) == want


# ------------------------------------------------------------------
# Text beyond ASCII, blanks, and dates that carry a time
# ------------------------------------------------------------------

ACCENTS = "id;name\n1;caf\u00e9\n2;\u00c9lan\n3;na\u00efve\n4;\u00c0B\n5;\u65e5\u672c\n6;cafe\n".encode("utf-8")


@pytest.mark.parametrize(
    "function, operator, value, want",
    [
        ("", "MATCHES", r"\w+", "6"),
        ("", "MATCHES", "[a-z\u00e9]+", "1,6"),
        ("", "MATCHES", "(?i)\u00e9lan", "2"),
        ("", "MATCHES", r"\D+", "1,2,3,4,5,6"),
        ("", "MATCHES", ".{2}", "4,5"),
        ("UPPER", "==", "CAF\u00c9", "1"),
        ("LOWER", "==", "\u00e9lan", "2"),
        ("LENGTH", "==", "4", "1,2,6"),
        ("LENGTH", "==", "2", "4,5"),
        ("LEFT(1)", "==", "\u00c9", "2"),
        ("RIGHT(1)", "==", "\u00e9", "1"),
        ("LOWER_FIRST", "==", "\u00e9", "2"),
        ("LOWER_FIRST", "==", "\u00e0", "4"),
        ("UPPER_FIRST", "==", "N", "3"),
        ("", "LENGTH_LT", "3", "4,5"),
        ("", "LENGTH_GT", "4", "3"),
        ("", "CONTAINS", "\u00ef", "3"),
        ("", ">", "z", "2,4,5"),
        ("", "<", "d", "1,6"),
        ("", "STARTS_WITH", "\u65e5", "5"),
        ("", "ENDS_WITH", "\u672c", "5"),
        ("RIGHT(2)", "==", "\u65e5\u672c", "5"),
        ("", "==", "caf\u00e9", "1"),
        ("", "NOT_CONTAINS", "\u00e9", "2,3,4,5,6"),
    ],
)
def test_text_beyond_ascii(tmp_path, function, operator, value, want):
    assert kept(tmp_path, cond("name", operator, value, function), data=ACCENTS, schema="id:int!, name:str") == want


BLANKS = (
    "id;name\n1; Eve\t\n2;\u00a0Bob\u00a0\n3;\u3000Zed\u2007\n4;\ufeffKim\n"
    "5; 12 \n6;\u00a012\n7;12\t\n8;x y\n".encode("utf-8")
)


@pytest.mark.parametrize(
    "function, operator, value, want",
    [
        ("TRIM", "==", "Eve", "1"),
        ("TRIM", "==", "Bob", "2"),
        ("TRIM", "==", "Zed", "3"),
        ("TRIM", "==", "Kim", ""),
        ("TRIM", "==", "x y", "8"),
        ("LTRIM", "==", "Eve\t", "1"),
        ("LTRIM", "==", "Bob\u00a0", "2"),
        ("RTRIM", "==", " Eve", "1"),
        ("RTRIM", "==", "\u3000Zed", "3"),
        ("TRIM", "LENGTH_LT", "3", "5,6,7"),
        ("", "==", "12", "5,7"),
        ("TRIM", "==", "12", "5,6,7"),
        ("LTRIM", "==", "12", "5,6,7"),
        ("RTRIM", "==", "12", "5,7"),
        ("", "LENGTH_GT", "4", "1,2,3"),
    ],
)
def test_blanks_of_every_kind(tmp_path, function, operator, value, want):
    assert kept(tmp_path, cond("name", operator, value, function), data=BLANKS, schema="id:int!, name:str") == want


@pytest.mark.parametrize(
    "function, value, want",
    [("TRIM", "Eve", ("1,3", "2")), ("LTRIM", "Eve\x1c", ("1", "2,3")), ("RTRIM", "\x1fEve", ("1", "2,3"))],
)
def test_trim_strips_what_python_calls_blank(tmp_path, function, value, want):
    # v1's file input turns these control characters into spaces before any filter sees them.
    data = b"id;name\n1;\x1fEve\x1c\n2;\x1dAnn\x1e\n3;Eve\n"
    assert v2_kept(tmp_path, {"conditions": [cond("name", "==", value, function)]}, data=data,
                   schema="id:int!, name:str") == want


@pytest.mark.parametrize(
    "operator, value, want",
    [(">", "5", "3,4"), ("<", "5", "5"), ("!=", "5", "1,2,3,4,5,6"), ("==", "inf", "3"), (">=", "-inf", "3,4,5"),
     ("<=", "inf", "3,4,5")],
)
def test_text_that_spells_not_a_number_is_no_number(tmp_path, operator, value, want):
    data = b"id;t\n1;nan\n2;NaN\n3;inf\n4;7\n5;-inf\n6;x\n"
    assert kept(tmp_path, cond("t", operator, value), data=data, schema="id:int!, t:str") == want


def names(tmp_path, condition, data):
    return v2_kept(tmp_path, {"conditions": [condition]}, data=data, schema="id:int!, name:str")


def test_matches_always_means_the_whole_text(tmp_path):
    # pandas takes a pattern that starts with ^ and ends with $ as it stands, so v1 keeps "bob" as well.
    assert names(tmp_path, cond("name", "MATCHES", "^b|x$"), b"id;name\n1;bob\n2;x\n3;abx\n4;b\n") == ("2,4", "1,3")


def test_upper_of_sharp_s_is_double_s(tmp_path):
    # v1's text engine makes it a capital sharp s (U+1E9E) instead, which Java and Python do not.
    data = "id;name\n1;stra\u00dfe\n2;strasse\n".encode("utf-8")
    assert names(tmp_path, cond("name", "==", "STRASSE", "UPPER"), data) == ("1,2", "")


def test_text_of_many_digits_is_read_as_the_number_nearest_to_it(tmp_path):
    # pandas reads long numbers one step off, so in v1 this text does not even equal itself.
    data = b"id;name\n1;8653696845264.0361\n2;8653696845264.0360\n3;5\n"
    assert names(tmp_path, cond("name", "==", "8653696845264.0361"), data) == ("1,2", "3")


@pytest.mark.parametrize(
    "function, operator, value, want",
    [
        ("", "ENDS_WITH", "e-05", "1,2,3"),
        ("", "CONTAINS", "e-0", "1,2,3,4,6"),
        ("", "STARTS_WITH", "0.000", "5"),
        ("", "MATCHES", r"-?\d(\.\d+)?e-\d\d", "1,2,3,4,6,7"),
        ("LENGTH", "==", "5", "1,7"),
        ("RIGHT(2)", "==", "07", "4"),
        ("LEFT(3)", "==", "9.9", "6"),
        ("", "<", "1e-06", "3,4,7"),
    ],
)
def test_small_floats_read_as_text_the_way_python_prints_them(tmp_path, function, operator, value, want):
    # The floats are dropped before the file is written: v1 and v2 do not write the smallest ones alike.
    data = b"id;x\n1;0.00001\n2;0.000012345\n3;-0.00002\n4;1.5e-7\n5;0.0001\n6;9.9e-6\n7;1e-10\n8;0.5\n"
    undeclared = {"input": [], "output": []}
    components = [
        reader("id:int!, x:float", header_rows=1),
        {"id": "it", "type": "FilterRows", "config": {"conditions": [cond("x", operator, value, function)]},
         "schema": undeclared, "inputs": ["row1"], "outputs": ["kept"]},
        {"id": "ids", "type": "FilterColumns", "config": {}, "schema": {"input": [], "output": columns("id:int!")},
         "inputs": ["kept"], "outputs": ["row2"]},
        writer("id:int!"),
    ]
    made = job(components, [flow("row1", "in", "it"), flow("kept", "it", "ids"), flow("row2", "ids", "out")])
    run = assert_matches_v1(made, {"in.csv": data}, tmp_path)
    assert run.succeeded and ids(run.files["out.csv"]) == want


TIMES = b"id;ts\n1;2024-01-31 10:11:12\n2;2023-12-01 23:59:59\n3;\n4;2024-02-29 00:00:01\n"


@pytest.mark.parametrize(
    "function, operator, value, want",
    [
        ("", "==", "2024-01-31 10:11:12", "1"),
        ("", ">", "2024-01-31", "1,4"),
        ("", "<=", "2024-01-31 10:11:12", "1,2"),
        ("", "ENDS_WITH", ":12", "1"),
        ("", "LENGTH_LT", "20", "1,2,4"),
        ("RIGHT(8)", "==", "10:11:12", "1"),
        ("LENGTH", "==", "19", "1,2,4"),
        ("", "IS_NULL", "", "3"),
        ("", "CONTAINS", " 23:", "2"),
        ("", "MATCHES", r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", "1,2,4"),
        ("", "!=", "2024-01-31 10:11:12", "2,3,4"),
    ],
)
def test_date_with_a_time_reads_as_text_with_its_time(tmp_path, function, operator, value, want):
    schema = "id:int!, ts:datetime@%Y-%m-%d %H:%M:%S"
    assert kept(tmp_path, cond("ts", operator, value, function), data=TIMES, schema=schema) == want


MILLIS = b"id;ts\n1;2024-01-31 10:11:12.500\n2;2023-12-01 23:59:59.250\n3;\n"
MICROS = b"id;ts\n1;2024-01-31 10:11:12.500001\n2;2023-12-01 23:59:59.250999\n3;\n"


@pytest.mark.parametrize(
    "data, function, operator, value, want",
    [
        (MILLIS, "", "ENDS_WITH", ".500", "1"),
        (MILLIS, "", "LENGTH_LT", "24", "1,2"),
        (MILLIS, "", "==", "2024-01-31 10:11:12.500", "1"),
        (MILLIS, "LENGTH", "==", "23", "1,2"),
        (MILLIS, "RIGHT(4)", "==", ".250", "2"),
        (MICROS, "", "ENDS_WITH", ".500001", "1"),
        (MICROS, "", "LENGTH_GT", "25", "1,2"),
        (MICROS, "", "==", "2023-12-01 23:59:59.250999", "2"),
        (MICROS, "LENGTH", "==", "26", "1,2"),
    ],
)
def test_fractions_of_a_second_read_as_text(tmp_path, data, function, operator, value, want):
    schema = "id:int!, ts:datetime@%Y-%m-%d %H:%M:%S.%f"
    assert kept(tmp_path, cond("ts", operator, value, function), data=data, schema=schema) == want


def test_each_date_reads_as_text_by_itself(tmp_path):
    # v1 writes every value of a column alike: with the time as soon as one value has one.
    data = b"id;ts\n1;2024-01-31 10:11:12\n2;2023-12-01 00:00:00\n"
    schema = "id:int!, ts:datetime@%Y-%m-%d %H:%M:%S"
    same_day = {"conditions": [cond("ts", "==", "2023-12-01")]}
    longer = {"conditions": [cond("ts", "LENGTH_GT", "10")]}
    assert v2_kept(tmp_path / "a", same_day, data=data, schema=schema) == ("2", "1")
    assert v2_kept(tmp_path / "b", longer, data=data, schema=schema) == ("1", "2")


# ------------------------------------------------------------------
# Values no file read by v1 can hold: missing text, NaN, types the reader does not make
# ------------------------------------------------------------------

class Given(Source):
    """Rows a test hands over with their Polars types."""

    names = ("given",)
    keys = (Key("rows", required=True),)
    frames = {
        "floats": pl.DataFrame({"id": [1, 2, 3, 4], "x": [1.5, float("nan"), None, -2.0]}),
        "texts": pl.DataFrame({"id": [1, 2, 3], "x": ["a", None, ""]}),
        "days": pl.DataFrame({"id": [1, 2, 3], "x": [datetime.date(2024, 1, 31), None, datetime.date(2023, 12, 1)]}),
        "flags": pl.DataFrame({"id": [1, 2, 3], "x": [True, None, False]}),
        "nothing": pl.DataFrame({"id": [1, 2], "x": [None, None]}),
        "small": pl.DataFrame({"id": [1, 2, 3], "x": pl.Series([5, None, -12], dtype=pl.Int8)}),
        "spans": pl.DataFrame({"id": [1], "x": [datetime.timedelta(days=1)]}),
    }

    def read(self):
        return {"main": Given.frames[self.config["rows"]].lazy()}

    def declared_outputs(self):
        return {"main": Given.frames[self.config["rows"]].clear().lazy()}


TYPED = Registry()
for _cls in REGISTRY.classes() + [Given]:
    TYPED.register(_cls)


def typed_job(rows, condition):
    components = [
        {"id": "in", "type": "given", "config": {"rows": rows}, "inputs": [], "outputs": ["row1"]},
        {"id": "it", "type": "FilterRows", "config": {"conditions": [condition]}, "inputs": ["row1"],
         "outputs": ["row2", "bad"]},
        writer(None, inputs=("row2",)),
        writer(None, component_id="rej", path="rej.csv", inputs=("bad",)),
    ]
    return job(components, [flow("row1", "in", "it"), flow("row2", "it", "out"), flow("bad", "it", "rej", "reject")])


@pytest.mark.parametrize(
    "rows, function, operator, value, want",
    [
        # A float that is not a number is a missing value, as in v1.
        ("floats", "", ">", "0", ("1", "2,3,4")),
        ("floats", "", "!=", "0", ("1,2,3,4", "")),
        ("floats", "", "IS_NULL", "", ("2,3", "1,4")),
        ("floats", "", "IS_NOT_NULL", "", ("1,4", "2,3")),
        ("floats", "ABS", ">", "1", ("1,4", "2,3")),
        ("floats", "", "CONTAINS", ".", ("1,4", "2,3")),
        ("floats", "", "NOT_CONTAINS", "5", ("2,3,4", "1")),
        ("floats", "LENGTH", "IS_NULL", "", ("2,3", "1,4")),
        ("floats", "", "==", "", ("", "1,2,3,4")),
        ("floats", "", "!=", "", ("1,2,3,4", "")),
        # Missing text is not empty text.
        ("texts", "", "IS_NULL", "", ("2", "1,3")),
        ("texts", "", "==", "", ("3", "1,2")),
        ("texts", "", "!=", "a", ("2,3", "1")),
        ("texts", "", ">", "", ("1", "2,3")),
        ("texts", "", "==", "5", ("", "1,2,3")),
        ("texts", "", "!=", "5", ("1,2,3", "")),
        ("texts", "LOWER", "IS_NULL", "", ("2", "1,3")),
        ("texts", "UPPER_FIRST", "IS_NULL", "", ("2,3", "1")),
        ("texts", "LENGTH", "==", "0", ("3", "1,2")),
        ("texts", "", "CONTAINS", "", ("1,3", "2")),
        ("texts", "", "NOT_CONTAINS", "a", ("2,3", "1")),
        ("texts", "", "STARTS_WITH", "", ("1,3", "2")),
        ("texts", "", "ENDS_WITH", "", ("1,3", "2")),
        ("texts", "", "MATCHES", ".*", ("1,3", "2")),
        ("texts", "", "LENGTH_LT", "5", ("1,3", "2")),
        ("texts", "", "LENGTH_GT", "-1", ("1,3", "2")),
        # A date without a time, a true/false value that may be missing, a column of nothing, a narrow whole number.
        ("days", "", "==", "2024-01-31", ("1", "2,3")),
        ("days", "", "STARTS_WITH", "2023", ("3", "1,2")),
        ("days", "LENGTH", "==", "10", ("1,3", "2")),
        ("days", "", "IS_NULL", "", ("2", "1,3")),
        ("flags", "", "==", "True", ("1", "2,3")),
        ("flags", "", "!=", "True", ("2,3", "1")),
        ("flags", "", "==", 1, ("1", "2,3")),
        ("flags", "", "IS_NULL", "", ("2", "1,3")),
        ("flags", "LENGTH", "==", "5", ("3", "1,2")),
        ("flags", "ABS", "IS_NULL", "", ("2", "1,3")),
        ("nothing", "", "IS_NULL", "", ("1,2", "")),
        ("nothing", "", "==", "x", ("", "1,2")),
        ("nothing", "", "!=", "x", ("1,2", "")),
        ("nothing", "", ">", "5", ("", "1,2")),
        ("nothing", "", "CONTAINS", "x", ("", "1,2")),
        ("small", "", ">", "2", ("1", "2,3")),
        ("small", "", "CONTAINS", "1", ("3", "1,2")),
        ("small", "ABS", "==", "12", ("3", "1,2")),
    ],
)
def test_typed_values(tmp_path, rows, function, operator, value, want):
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(typed_job(rows, cond("x", operator, value, function)), registry=TYPED)
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    assert (ids((tmp_path / "out.csv").read_bytes()), ids((tmp_path / "rej.csv").read_bytes())) == want


@pytest.mark.parametrize(
    "rows, condition, said",
    [
        ("spans", cond("x", "CONTAINS", "1"), "conditions[0]: column 'x' is of type Duration"),
        ("spans", cond("x", ">", "5"), "and cannot be compared with the number 5"),
        ("days", cond("x", ">", "5"), "conditions[0]: column 'x' is a date and cannot be compared with the number 5"),
    ],
)
def test_typed_values_a_test_cannot_take(rows, condition, said):
    with pytest.raises(JobRefusedError) as caught:
        load_job(typed_job(rows, condition), registry=TYPED)
    assert said in caught.value.report.format()


# ------------------------------------------------------------------
# Several conditions
# ------------------------------------------------------------------

BIG = cond("qty", ">=", "25")
HAS_A = cond("name", "CONTAINS", "a", "LOWER")
NEGATIVE = cond("amt", "<", "0")


@pytest.mark.parametrize(
    "config, want",
    [
        ({"logical_op": "&&", "conditions": [BIG, HAS_A]}, "1,5"),
        ({"logical_op": "||", "conditions": [BIG, HAS_A]}, "1,2,3,4,5,8"),
        ({"logical_op": "AND", "conditions": [BIG, HAS_A]}, "1,5"),
        ({"logical_op": "OR", "conditions": [BIG, HAS_A]}, "1,2,3,4,5,8"),
        ({"conditions": [BIG, HAS_A]}, "1,5"),
        ({"logical_op": "&&", "conditions": [BIG, HAS_A, NEGATIVE]}, ""),
        ({"logical_op": "||", "conditions": [BIG, HAS_A, NEGATIVE]}, "1,2,3,4,5,7,8"),
        ({"logical_op": "||", "conditions": [NEGATIVE]}, "4,7"),
        ({"logical_op": "||", "conditions": []}, EVERY_ROW),
        ({}, EVERY_ROW),
    ],
)
def test_conditions_combine(tmp_path, config, want):
    assert ids(same(tmp_path, config).files["out.csv"]) == want


# ------------------------------------------------------------------
# The reject output
# ------------------------------------------------------------------

def message(run):
    return run.files["rej.csv"].split(b"\n")[1].split(b";")[-1].decode()


@pytest.mark.parametrize(
    "config, want",
    [
        ({"conditions": [BIG]}, "qty >= 25"),
        ({"conditions": [HAS_A]}, "name CONTAINS a"),
        ({"conditions": [BIG, HAS_A]}, "qty >= 25 && name CONTAINS a"),
        ({"logical_op": "OR", "conditions": [NEGATIVE, cond("name", "==", "zed")]}, "amt < 0 || name == zed"),
        ({"conditions": [cond("qty", "==", 25)]}, "qty == 25"),
        ({"conditions": [cond("qty", "==", 25.0)]}, "qty == 25.0"),
        ({"conditions": [cond("qty", "==", " 25 ")]}, "qty ==  25"),
        ({"conditions": [cond("name", "==", None)]}, "name == None"),
        ({"conditions": [{"column": "amt", "operator": "IS_NULL"}]}, "amt IS_NULL"),
        ({"conditions": [cond("amt", "IS_NULL", None)]}, "amt IS_NULL None"),
        ({"conditions": [cond("flag", "==", True)]}, "flag == True"),
    ],
)
def test_rejected_rows_say_which_filter_they_failed(tmp_path, config, want):
    assert message(same(tmp_path, config)) == "The row does not match the filter: " + want


def test_reject_output_carries_the_whole_row_and_the_reason(tmp_path):
    run = same(tmp_path, {"conditions": [cond("qty", ">", "40")]})
    assert run.files["out.csv"] == (
        b"id;name;age;qty;amt;flag;d;m\n"
        b"2;bob;;41;20.0;false;2023-12-01;7.00\n"
        b"8;x;100;100;2.5;false;2024-12-31;25.00\n"
    )
    assert run.files["rej.csv"].split(b"\n")[:3] == [
        b"id;name;age;qty;amt;flag;d;m;errorMessage",
        b"1;Alice;30;30;10.5;True;2024-01-31 00:00:00;1.50;The row does not match the filter: qty > 40",
        b"3;;25;25;;True;;-2.35;The row does not match the filter: qty > 40",
    ]


def test_reject_file_that_declares_its_columns(tmp_path):
    same(tmp_path, {"conditions": [BIG]}, reject_schema=SCHEMA + ", errorMessage:str")


def test_no_row_rejected_still_writes_the_reject_file(tmp_path):
    run = same(tmp_path, {"conditions": [cond("qty", "<", "1000")]})
    assert run.files["rej.csv"] == b"id;name;age;qty;amt;flag;d;m;errorMessage\n"


def test_every_row_rejected(tmp_path):
    run = same(tmp_path, {"conditions": [cond("qty", ">", "1000")]})
    assert run.files["out.csv"] == b"id;name;age;qty;amt;flag;d;m\n"
    assert ids(run.files["rej.csv"]) == EVERY_ROW


def test_both_outputs_keep_the_input_order_on_a_large_input(tmp_path):
    names = [b"Alice", b"bob", b"", b" Carol "]
    lines = [b"id;name;qty;amt"]
    for i in range(1, 20001):
        amt = b"" if i % 9 == 0 else str((i * 13 % 50) / 4).encode()
        lines.append(b"%d;%s;%d;%s" % (i, names[i % 4], i * 7 % 101, amt))
    config = {"logical_op": "||", "conditions": [cond("qty", ">", "60"), cond("name", "STARTS_WITH", "a", "LOWER"),
                                                 cond("amt", "<", "1", "ABS")]}
    run = same(tmp_path, config, data=b"\n".join(lines) + b"\n", schema="id:int!, name:str, qty:int!, amt:float")
    passed, rejected = run.files["out.csv"].count(b"\n") - 1, run.files["rej.csv"].count(b"\n") - 1
    assert passed + rejected == 20000 and 0 < rejected < passed


def test_filter_with_no_reject_flow(tmp_path):
    run = same(tmp_path, {"conditions": [BIG]}, reject=False)
    assert ids(run.files["out.csv"]) == "1,2,3,5,8" and list(run.files) == ["out.csv"]


def test_main_flow_of_type_filter(tmp_path):
    made = filter_job({"conditions": [BIG]})
    made["flows"][1]["type"] = "filter"
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.succeeded and ids(run.files["out.csv"]) == "1,2,3,5,8" and ids(run.files["rej.csv"]) == "4,6,7"


def test_column_and_value_can_come_from_the_context(tmp_path):
    conditions = [cond("${context.column}", ">=", "${context.least}"), cond("name", "!=", "context.who"),
                  cond("amt", "<", "${context.most}")]
    made = filter_job({"conditions": conditions})
    made["context"] = {"Default": {
        "column": {"value": "qty", "type": "str"}, "least": {"value": "25", "type": "int"},
        "who": {"value": "bob", "type": "str"}, "most": {"value": "999.5", "type": "float"},
    }}
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.succeeded and ids(run.files["out.csv"]) == "1,8"
    assert message(run) == "The row does not match the filter: qty >= 25 && name != bob && amt < 999.5"


def test_filter_that_declares_no_schema(tmp_path):
    made = filter_job({"conditions": [BIG]})
    made["components"][1]["schema"] = {"input": [], "output": []}
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.succeeded and ids(run.files["out.csv"]) == "1,2,3,5,8"


def test_no_input_rows_and_no_reject_flow(tmp_path):
    run = same(tmp_path, {"conditions": [BIG]}, data=DATA.split(b"\n")[0] + b"\n", reject=False)
    assert run.files["out.csv"] == b"id;name;age;qty;amt;flag;d;m\n"


def test_no_input_rows_writes_an_empty_reject_file(tmp_path):
    # v1 stalls here (status "error"): on empty input its filter hands the reject flow nothing.
    result, folder = v2(tmp_path, {"conditions": [BIG]}, data=DATA.split(b"\n")[0] + b"\n")
    assert result.status == "success"
    assert (folder / "out.csv").read_bytes() == b"id;name;age;qty;amt;flag;d;m\n"
    assert (folder / "rej.csv").read_bytes() == b"id;name;age;qty;amt;flag;d;m;errorMessage\n"


def test_missing_whole_number_is_not_lost(tmp_path):
    # v1 drops row 2 from both outputs: its comparison of a missing whole number is neither true nor false.
    assert v2_kept(tmp_path / "a", {"conditions": [cond("age", ">", "25")]}) == ("1,4,8", "2,3,5,6,7")
    assert v2_kept(tmp_path / "b", {"conditions": [cond("age", "!=", "25")]}) == ("1,2,4,6,7,8", "3,5")
    assert v2_kept(tmp_path / "c", {"conditions": [cond("age", "<", "8", "ABS")]}) == ("6,7", "1,2,3,4,5,8")


@pytest.mark.parametrize(
    "operator, want", [("IS_NULL", ("2", "1,3")), ("IS_NOT_NULL", ("1,3", "2")), ("<", ("1,3", "2")), ("!=", ("1,2,3", ""))]
)
def test_missing_decimal_is_missing(tmp_path, operator, want):
    # v1 keeps an empty Decimal field as empty text, which is not missing to it.
    config = {"conditions": [cond("m", operator, "5")]}
    assert v2_kept(tmp_path, config, data=b"id;m\n1;1.50\n2;\n3;-7\n", schema="id:int!, m:Decimal#2") == want


# ------------------------------------------------------------------
# The declared schema, and rows it does not allow
# ------------------------------------------------------------------

NO_MISSING_AGE = "id:int!, name:str, age:int!, qty:int!, amt:float, flag:bool, d:datetime@%Y-%m-%d, m:Decimal#2!"


@pytest.mark.parametrize("config", [{}, {"die_on_error": True}])
def test_missing_value_the_schema_forbids_fails_the_filter(tmp_path, config):
    same(tmp_path, dict(config, conditions=[cond("qty", ">", "0")]), out_schema=NO_MISSING_AGE, fails=True)
    result, _ = v2(tmp_path / "direct", dict(config, conditions=[cond("qty", ">", "0")]), out_schema=NO_MISSING_AGE)
    assert result.failed_component == "it" and result.error == "Column 'age' has NULL values but is not nullable"


def test_missing_value_the_schema_forbids_is_rejected_when_errors_are_not_fatal(tmp_path):
    run = same(tmp_path, {"die_on_error": False, "conditions": [cond("qty", ">", "25")]}, out_schema=NO_MISSING_AGE)
    assert ids(run.files["out.csv"]) == "1,8"
    assert run.files["rej.csv"].split(b"\n")[0] == b"id;name;age;qty;amt;flag;d;m;errorMessage;errorCode"
    assert run.files["rej.csv"].split(b"\n")[-2] == (
        b"2;bob;;41;20.0;False;2023-12-01 00:00:00;7.00;Column 'age': non-nullable column has null;SCHEMA_VIOLATION"
    )


def test_missing_value_the_schema_forbids_is_dropped_without_a_reject_flow(tmp_path):
    run = same(tmp_path, {"die_on_error": False, "conditions": [cond("qty", ">", "25")]}, out_schema=NO_MISSING_AGE,
               reject=False)
    assert ids(run.files["out.csv"]) == "1,8"


def test_reject_columns_do_not_depend_on_the_rows(tmp_path):
    # v1 adds errorCode only when a row breaks the schema, and puts it first when the filter rejected nothing.
    schema, forbids = "id:int!, name:str, age:int", "id:int!, name:str, age:int!"
    config = {"die_on_error": False, "conditions": [cond("id", ">", "1")]}
    wanted = {
        b"id;name;age\n1;a;30\n3;;25\n": b"1;a;30;The row does not match the filter: id > 1;\n",
        b"id;name;age\n2;a;\n3;;25\n": b"2;a;;Column 'age': non-nullable column has null;SCHEMA_VIOLATION\n",
        b"id;name;age\n2;a;30\n3;;25\n": b"",
    }
    for index, (data, rejected) in enumerate(wanted.items()):
        result, folder = v2(tmp_path / str(index), config, data=data, schema=schema, out_schema=forbids)
        assert result.status == "success"
        assert (folder / "out.csv").read_bytes().endswith(b"3;;25\n")
        assert (folder / "rej.csv").read_bytes() == b"id;name;age;errorMessage;errorCode\n" + rejected


def test_declared_columns_come_first(tmp_path):
    run = same(tmp_path, {"conditions": [BIG]}, schema="id:int!, name:str, qty:int!",
               data=b"id;name;qty\n1;a;30\n2;b;3\n", out_schema="qty:int!, id:int!")
    assert run.files["out.csv"] == b"qty;id;name\n30;1;a\n"


# ------------------------------------------------------------------
# The advanced condition: Java on v1, Python on v2
# ------------------------------------------------------------------

PEOPLE_SCHEMA = "id:int!, name:str, age:int!, amt:float, flag:bool"
PEOPLE = (
    b"id;name;age;amt;flag\n1;Alice;30;10.5;true\n2;bob;41;20;false\n3;;25;;true\n4; Carol ;41;-3.25;false\n"
    b"5;dave;25;1e3;false\n"
)


def advanced(java, python, reject=True, **config):
    """The same job twice: with the condition in Java for v1, and in Python for v2."""
    in_java = dict(config, use_advanced=True, advanced_cond="{{java}}" + java)
    v1_job = filter_job(in_java, schema=PEOPLE_SCHEMA, reject=reject)
    v1_job["java_config"] = {"enabled": True, "routines": [], "libraries": []}
    v2_job = filter_job(dict(in_java, advanced_cond=python), schema=PEOPLE_SCHEMA, reject=reject)
    for made in (v1_job, v2_job):
        made["context"] = {"Default": {"limit": {"value": "30", "type": "int"}}}
    return v1_job, v2_job


@pytest.mark.parametrize(
    "expression, want",
    [
        ("row1.age > 30", "2,4"),
        ("input_row.age > 30 ", "2,4"),
        ("context.limit < row1.age", "2,4"),
        ("row1.amt > 15", "2,5"),
    ],
)
def test_condition_that_reads_the_same_in_java_and_python(tmp_path, expression, want):
    v1_job, v2_job = advanced(expression, expression)
    run = assert_matches_v1(v1_job, {"in.csv": PEOPLE}, tmp_path, v2_job=v2_job)
    assert run.succeeded and ids(run.files["out.csv"]) == want
    assert message(run) == "The row does not match the filter: " + expression


@pytest.mark.parametrize(
    "java, python, want",
    [
        ("row1.name.length() > 3", "len(row1.name) > 3", "1,4,5"),
        ("row1.amt == null || row1.amt < 0", "row1.amt is None or row1.amt < 0", "3,4"),
        ("input_row.flag && input_row.age >= 30", "input_row.flag and input_row.age >= 30", "1"),
        ('row1.name.equals("bob") || row1.name.isEmpty()', "name == 'bob' or name == ''", "2,3"),
        ('row1.name.trim().toLowerCase().startsWith("c")', "row1['name'].strip().lower().startswith('c')", "4"),
    ],
)
def test_condition_rewritten_in_python(tmp_path, java, python, want):
    v1_job, v2_job = advanced(java, python, reject=False)
    run = assert_matches_v1(v1_job, {"in.csv": PEOPLE}, tmp_path, v2_job=v2_job)
    assert run.succeeded and ids(run.files["out.csv"]) == want


@pytest.mark.parametrize(
    "config, want, said",
    [
        ({"conditions": [cond("name", "!=", "bob")]}, "4", "row1.age > 30 && name != bob"),
        ({"logical_op": "||", "conditions": [cond("name", "==", "bob"), cond("amt", "<", "0")]}, "2,4",
         "row1.age > 30 && name == bob || amt < 0"),
    ],
)
def test_condition_and_the_simple_conditions_must_both_hold(tmp_path, config, want, said):
    v1_job, v2_job = advanced("row1.age > 30", "row1.age > 30", **config)
    run = assert_matches_v1(v1_job, {"in.csv": PEOPLE}, tmp_path, v2_job=v2_job)
    assert run.succeeded and ids(run.files["out.csv"]) == want
    assert message(run) == "The row does not match the filter: " + said


def people(tmp_path, config):
    return v2_kept(tmp_path, config, data=PEOPLE, schema=PEOPLE_SCHEMA)


@pytest.mark.parametrize(
    "expression, want",
    [
        ("age > 30", ("2,4", "1,3,5")),
        ("row1.age > 30", ("2,4", "1,3,5")),
        ("input_row.age > 30", ("2,4", "1,3,5")),
        ("row1['age'] > 30", ("2,4", "1,3,5")),
        ("row1.name.lower() in ('alice', 'bob')", ("1,2", "3,4,5")),
        ("not row1.flag", ("2,4,5", "1,3")),
        ("row1.amt > 0", ("1,2,5", "3,4")),
        ("row1.amt < 0", ("4", "1,2,3,5")),
        ("not row1.amt > 0", ("3,4", "1,2,5")),
        ("row1.amt is None", ("3", "1,2,4,5")),
        ("row1.name", ("1,2,4,5", "3")),
        ("row1.amt", ("1,2,4,5", "3")),
        ("row1.name and row1.age > 30", ("2,4", "1,3,5")),
        ("row1.age - 30", ("2,3,4,5", "1")),
        ("True", ("1,2,3,4,5", "")),
        ("None", ("", "1,2,3,4,5")),
        ("  row1.age > 30  # the older ones", ("2,4", "1,3,5")),
    ],
)
def test_python_condition(tmp_path, expression, want):
    assert people(tmp_path, {"use_advanced": True, "condition": expression}) == want


def test_python_condition_over_several_lines(tmp_path):
    result, folder = v2(tmp_path, {"use_advanced": True, "condition": "(row1.age > 30\n    or row1.flag)  # either\n"},
                        data=PEOPLE, schema=PEOPLE_SCHEMA)
    assert result.status == "success" and ids((folder / "out.csv").read_bytes()) == "1,2,3,4"


def test_python_condition_reads_context_and_global_map(tmp_path):
    made = filter_job({"use_advanced": True, "condition": "age > context.limit and globalMap.get('floor', 0) < age"},
                      schema=PEOPLE_SCHEMA)
    made["context"] = {"Default": {"limit": {"value": "30", "type": "int"}}}
    (tmp_path / "in.csv").write_bytes(PEOPLE)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert run_job(made).status == "success"
    finally:
        os.chdir(previous)
    assert ids((tmp_path / "out.csv").read_bytes()) == "2,4"


def test_python_condition_is_named_in_the_reject_message_as_written(tmp_path):
    config = {"use_advanced": True, "condition": " age > 30 ", "conditions": [cond("name", "!=", "bob")]}
    result, folder = v2(tmp_path, config, data=PEOPLE, schema=PEOPLE_SCHEMA)
    assert result.status == "success"
    assert (folder / "rej.csv").read_bytes().split(b"\n")[1] == (
        b"1;Alice;30;10.5;True;The row does not match the filter:  age > 30  && name != bob"
    )


@pytest.mark.parametrize("config", [{"use_advanced": False}, {}])
def test_condition_is_read_only_when_use_advanced_is_on(tmp_path, config):
    config = dict(config, advanced_cond="row1.age > 100", conditions=[cond("age", ">=", "30")])
    run = same(tmp_path, config, data=PEOPLE, schema=PEOPLE_SCHEMA)
    assert ids(run.files["out.csv"]) == "1,2,4"
    assert message(run) == "The row does not match the filter: age >= 30"


def test_condition_that_is_switched_off_need_not_be_python(tmp_path):
    run = same(tmp_path, {"use_advanced": False, "advanced_cond": "row1.name.equals(\"x\") && !done"},
               data=PEOPLE, schema=PEOPLE_SCHEMA)
    assert ids(run.files["out.csv"]) == "1,2,3,4,5"


def test_python_condition_runs_where_v1_would_pass_every_row(tmp_path):
    # Without its Java bridge v1 warns and lets every row through.
    assert people(tmp_path, {"use_advanced": True, "advanced_cond": "row1.age > 100"}) == ("", "1,2,3,4,5")


def test_use_advanced_without_a_condition_fails_on_both(tmp_path):
    same(tmp_path, {"use_advanced": True, "advanced_cond": "", "conditions": [BIG]}, fails=True)
    assert "condition: use_advanced is on but there is no condition" in refused({"use_advanced": True})


# ------------------------------------------------------------------
# What v2 says no to, and what it lets pass
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "condition",
    [
        {"column": "qty", "value": "25"},
        {"operator": "==", "value": "25"},
        cond("qty", "=", "25"),
        cond("name", "contains", "a"),
        cond("name", "LENGTH_LT", "abc"),
        cond("name", "LENGTH_GT", "3.0"),
        cond("name", "LENGTH_GT", ""),
        cond("name", "MATCHES", "("),
        cond("name", "MATCHES", "*a"),
        "qty > 25",
    ],
)
def test_condition_neither_engine_accepts(tmp_path, condition):
    same(tmp_path, {"conditions": [condition]}, fails=True)
    with pytest.raises(JobRefusedError):
        load_job(filter_job({"conditions": [condition]}))


def test_conditions_must_be_a_list(tmp_path):
    same(tmp_path, {"conditions": "qty > 25"}, fails=True)
    assert "conditions: expected a list" in refused({"conditions": "qty > 25"})


@pytest.mark.parametrize(
    "condition, said",
    [
        # v1 warns and tests the column as it is.
        (cond("name", "==", "bob", "BOGUS"), ".function: 'BOGUS' is not a function"),
        (cond("name", "==", "bo", "LEFT(2)x"), ".function: 'LEFT(2)x' is not a function"),
        (cond("name", "==", "bo", "LEFT( 2 )"), ".function: 'LEFT( 2 )' is not a function"),
        (cond("name", "==", "bo", "LEFT(-1)"), ".function: 'LEFT(-1)' is not a function"),
        # v1 counts a condition on a column that is not there as false for every row.
        (cond("nope", "==", "1"), ": there is no column 'nope' to test"),
        # v1 runs these with Python's regex engine.
        (cond("name", "MATCHES", "bo(?=b)b"), ".value: MATCHES cannot use this pattern (look-around"),
        (cond("name", "MATCHES", r"(b)o\1"), ".value: MATCHES cannot use this pattern (backreferences are not supported)"),
        # v1 compares the date's count of microseconds with the number.
        (cond("d", ">", "2024"), ": column 'd' is a date and cannot be compared with the number 2024"),
        (cond("d", ">", "0", "ABS"), ": column 'd' is a date and ABS needs a number"),
        # v1 keeps a Decimal's text as the file spelled it, and an empty field as empty text.
        (cond("m", "==", "abc"), ": column 'm' is a Decimal and cannot be compared with the text 'abc'"),
        (cond("m", "!=", ""), ": column 'm' is a Decimal and cannot be compared with the text ''"),
        (cond("m", "CONTAINS", ".5"), ": column 'm' is a Decimal and cannot be read as text for CONTAINS"),
        (cond("m", "==", "4", "LENGTH"), ": column 'm' is a Decimal and cannot be read as text for LENGTH"),
        (cond("m", "==", "1", "LEFT(1)"), ": column 'm' is a Decimal and cannot be read as text for LEFT(1)"),
        # v1's answer changes with what else is in the column: 5 or 5.0.
        (cond("name", "CONTAINS", "5", "LENGTH"), ": LENGTH gives a number; CONTAINS tests text"),
        (cond("qty", "STARTS_WITH", "2", "ABS"), ": ABS gives a number; STARTS_WITH tests text"),
        (cond("qty", "==", "x", "ABS"), ": ABS gives a number; compare it with a number, not 'x'"),
        (cond("name", "<", "", "LENGTH"), ": LENGTH gives a number; compare it with a number, not ''"),
        # v1 fails on these when it runs.
        (cond("name", "LENGTH_LT", "abc"), ".value: LENGTH_LT needs a whole number, not 'abc'"),
        (cond("name", "LENGTH_GT", float("inf")), ".value: LENGTH_GT needs a whole number, not inf"),
        (dict(BIG, colum="x"), ".colum: unknown config key"),
    ],
)
def test_refused_condition(condition, said):
    assert f"conditions[1]{said}" in refused({"conditions": [BIG, condition]})


@pytest.mark.parametrize(
    "config, said",
    [
        # v1 takes every other spelling, "or" included, to mean &&.
        ({"logical_op": "or", "conditions": [BIG]}, "logical_op: 'or' is not allowed; use one of '&&', '||', 'AND', 'OR'"),
        ({"logical_op": "xor", "conditions": [BIG]}, "logical_op: 'xor' is not allowed"),
        ({"bogus": 1}, "bogus: unknown config key"),
    ],
)
def test_refused_config(config, said):
    assert said in refused(config)


def test_condition_that_is_not_python_is_refused():
    report = refused({"use_advanced": True, "condition": "row1.age > 30 && row1.flag"}, schema=PEOPLE_SCHEMA)
    assert "write `and` instead of `&&`" in report
    report = refused({"use_advanced": True, "condition": "row1.nope > 30"}, schema=PEOPLE_SCHEMA)
    assert "row1 has no column 'nope'" in report


def test_java_condition_is_refused():
    report = refused({"use_advanced": True, "advanced_cond": "{{java}}row1.age > 30"}, schema=PEOPLE_SCHEMA)
    assert "advanced_cond: Java expressions are not run by v2; rewrite it in Python" in report


def test_both_spellings_of_the_condition_are_refused():
    report = refused({"use_advanced": True, "condition": "age > 30", "advanced_cond": "age > 30"}, schema=PEOPLE_SCHEMA)
    assert "advanced_cond: also given as 'condition'; use one spelling" in report


def test_keys_that_change_nothing_are_accepted(tmp_path):
    config = {"conditions": [BIG], "label": "Filter_Active", "tstatcatcher_stats": False, "execution_mode": "batch",
              "chunk_size": 10}
    assert ids(same(tmp_path, config).files["out.csv"]) == "1,2,3,5,8"
    load_job(filter_job(dict(config, reject_output=True)))


@pytest.mark.parametrize("name", ["FilterRows", "FilterRow", "tFilterRow", "tFilterRows"])
def test_v1_type_names(tmp_path, name):
    made = filter_job({"conditions": [BIG]})
    made["components"][1]["type"] = name
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.succeeded and ids(run.files["out.csv"]) == "1,2,3,5,8"


def test_v2_type_name():
    made = filter_job({"conditions": [BIG]})
    made["components"][1]["type"] = "filter_rows"
    load_job(made)


def test_converter_sample_loads():
    sample = next(c for c in json.loads(SAMPLE.read_text())["components"] if c["type"] == "FilterRows")
    schema = "id:int!, name:str!, age:int!, department:str!, salary:int!, status:str!"
    as_converted = through({"type": "FilterRows", "config": sample["config"], "schema": sample["schema"]}, schema)
    with pytest.raises(JobRefusedError) as caught:
        load_job(as_converted)
    assert [(refusal.key, refusal.reason) for refusal in caught.value.report] == [
        ("advanced_cond", "Java expressions are not run by v2; rewrite it in Python")
    ]

    rewritten = copy.deepcopy(as_converted)
    rewritten["components"][1]["config"]["advanced_cond"] = "input_row.age == input_row.salary"
    load_job(rewritten)


# ------------------------------------------------------------------
# Java the converter leaves in a condition that is switched off
# ------------------------------------------------------------------

def test_java_left_in_a_condition_that_is_off_does_not_refuse_the_job(tmp_path):
    """Talend stores a commented code sample in every filter; the converter passes it on marked as Java."""
    from src.v2 import load_job
    from src.v2.errors import JobRefusedError
    from tests.v2.components.kit import through

    sample = "{{java}}// code sample : use input_row to define the condition.\n// input_row.columnName1.equals(\"foo\")"
    config = {"logical_op": "&&", "use_advanced": False, "advanced_cond": sample,
              "conditions": [{"column": "n", "operator": ">", "value": "1", "function": ""}]}
    made = through({"type": "FilterRows", "config": config}, "n:int")
    made["flows"][1]["type"] = "filter"
    load_job(made)

    made["components"][1]["config"]["use_advanced"] = True
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    assert "advanced_cond: Java expressions are not run by v2" in caught.value.report.format()
