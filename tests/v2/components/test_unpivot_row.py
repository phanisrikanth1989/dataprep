"""Unpivot row, against v1 on the same job config and bytes."""
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import through

SCHEMA = "id:int, name:str, q1:float, q2:float, note:str"
OUT = "id:int, pivot_key:str, pivot_value:str"
DATA = b"id;name;q1;q2;note\n1;ann;1.5;2.0;a\n2;bob;;4.25;\n3;cy;7.0;;c\n"


def unpivoted(keys=("id",), schema=SCHEMA, out=OUT, **config):
    return through({"type": "UnpivotRow", "config": {"row_keys": list(keys), **config}}, schema, out)


def same(tmp_path, data=DATA, **kwargs):
    run = assert_matches_v1(unpivoted(**kwargs), {"in.csv": data}, tmp_path)
    assert run.succeeded, run.error
    return run.files["out.csv"].decode().splitlines()[1:]


def v2(tmp_path, made, data=DATA):
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def test_every_column_that_is_no_key_becomes_rows_of_its_name_and_value_column_by_column(tmp_path):
    assert same(tmp_path) == [
        "1;name;ann", "2;name;bob", "3;name;cy", "1;q1;1.5", "2;q1;", "3;q1;7.0",
        "1;q2;2.0", "2;q2;4.25", "3;q2;", "1;note;a", "2;note;", "3;note;c",
    ]


def test_rows_with_no_value_can_be_left_out_and_empty_text_is_a_value(tmp_path):
    got = same(tmp_path, include_empty_values=False)
    assert "2;q1;" not in got and "3;q2;" not in got and "2;note;" in got and len(got) == 10


def test_several_keys_and_other_names_for_the_two_columns(tmp_path):
    got = same(tmp_path, keys=("name", "id"), out="name:str, id:int, what:str, held:str", pivot_key="what",
               pivot_value="held")
    assert got[:2] == ["ann;1;q1;1.5", "bob;2;q1;"] and len(got) == 9


@pytest.mark.parametrize("kind, data, values", [
    ("int", b"k;v\n1;3\n2;40\n", ["3", "40"]),
    ("bool", b"k;v\n1;true\n2;false\n", ["True", "False"]),
    ("Decimal#2", b"k;v\n1;1.5\n2;2\n", ["1.50", "2.00"]),
    ("str", b"k;v\n1; a \n2;\n", [" a ", ""]),
], ids=["whole numbers", "true or false", "Decimals", "text"])
def test_value_is_the_text_of_what_the_column_holds(tmp_path, kind, data, values):
    got = same(tmp_path, data, keys=("k",), schema=f"k:int, v:{kind}", out="k:int, pivot_key:str, pivot_value:str")
    assert [line.split(";")[2] for line in got] == values


def test_date_is_written_with_its_time(tmp_path):
    got = same(tmp_path, b"k;v\n1;2024-01-31\n", keys=("k",), schema="k:int, v:datetime@%Y-%m-%d",
               out="k:int, pivot_key:str, pivot_value:str")
    assert got == ["1;v;2024-01-31 00:00:00"]


def test_whole_number_stays_whole_beside_a_missing_one(tmp_path):
    # v1 writes 3.0 here: pandas turns a whole-number column with a missing value into floats.
    made = unpivoted(keys=("k",), schema="k:int, v:int", out="k:int, pivot_key:str, pivot_value:str")
    assert v2(tmp_path, made, b"k;v\n1;3\n2;\n").status == "success"
    assert (tmp_path / "out.csv").read_bytes() == b"k;pivot_key;pivot_value\n1;v;3\n2;v;\n"


def test_nothing_but_keys_gives_no_rows(tmp_path):
    assert same(tmp_path, b"id;name\n1;a\n", keys=("id", "name"), schema="id:int, name:str") == []


def test_no_rows_in(tmp_path):
    assert same(tmp_path, b"id;name;q1;q2;note\n") == []


def test_key_that_is_not_a_column_fails_the_job_or_gives_no_rows(tmp_path):
    with pytest.raises(JobRefusedError, match="row_keys: there is no column 'nope'"):
        load_job(unpivoted(keys=("id", "nope")))
    assert same(tmp_path, keys=("nope",), die_on_error=False) == []


def test_no_keys_fails_the_job_or_gives_no_rows(tmp_path):
    with pytest.raises(JobRefusedError, match="row_keys: names no column"):
        load_job(unpivoted(keys=()))
    assert same(tmp_path, keys=(), die_on_error=False) == []


def test_keys_are_needed():
    made = unpivoted()
    del made["components"][1]["config"]["row_keys"]
    with pytest.raises(JobRefusedError, match="row_keys"):
        load_job(made)


# ------------------------------------------------------------------
# What a second reader of this component found (ticket 65)
# ------------------------------------------------------------------

def test_whole_number_stays_whole_beside_a_column_of_floats(tmp_path):
    # v1 writes 3.0 and 4.0: pandas makes one column of all the values, and a float among them makes all floats.
    made = unpivoted(keys=("k",), schema="k:int, a:int, b:float", out="k:int, pivot_key:str, pivot_value:str")
    assert v2(tmp_path, made, b"k;a;b\n1;3;1.5\n2;4;2.5\n").status == "success"
    assert (tmp_path / "out.csv").read_bytes().decode().splitlines()[1:] == ["1;a;3", "2;a;4", "1;b;1.5", "2;b;2.5"]


def test_decimal_with_no_declared_places_is_written_without_padding(tmp_path):
    # v1 writes each as it stood in the file (1.50).
    made = unpivoted(keys=("k",), schema="k:int, v:Decimal", out="k:int, pivot_key:str, pivot_value:str")
    assert v2(tmp_path, made, b"k;v\n1;1.50\n2;3\n").status == "success"
    assert (tmp_path / "out.csv").read_bytes() == b"k;pivot_key;pivot_value\n1;v;1.5\n2;v;3\n"


def test_name_for_the_names_column_may_be_that_of_a_column_that_is_unpivoted(tmp_path):
    got = same(tmp_path, b"k;v;w\n1;a;b\n", keys=("k",), schema="k:int, v:str, w:str", out="k:int, v:str, pivot_value:str",
               pivot_key="v")
    assert got == ["1;v;a", "1;w;b"]


@pytest.mark.parametrize("config, said", [
    (dict(keys=("id", "id")), "row_keys: 'id' is named twice"),
    (dict(pivot_value="name"), "pivot_value: the input has a column 'name' already"),
    (dict(pivot_key="id"), "pivot_key: 'id' is one of the keys"),
    (dict(pivot_key="x", pivot_value="x"), "pivot_value: 'x' is the name of the names column too"),
])
def test_names_that_clash_refuse_the_job_in_words(config, said):
    with pytest.raises(JobRefusedError, match=said):
        load_job(unpivoted(**config))
