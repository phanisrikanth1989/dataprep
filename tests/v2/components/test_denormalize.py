"""Denormalize, against v1 on the same job config and bytes."""
import json
import os
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import through

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tDenormalize_0.1.json"
SCHEMA = "id:int, name:str, skill:str"
DATA = b"id;name;skill\n1;ann;sql\n2;bob;java\n1;ann;python\n1;ann;sql\n3;cy;\n2;bob;\n;nobody;x\n;nobody;y\n"


def column(name, delimiter=None, merge=None):
    made = {"input_column": name}
    if delimiter is not None:
        made["delimiter"] = delimiter
    if merge is not None:
        made["merge"] = merge
    return made


def denormalized(columns=(column("skill"),), schema=SCHEMA, out=None, **config):
    return through({"type": "Denormalize", "config": {"denormalize_columns": list(columns), **config}}, schema, out)


def same(tmp_path, data=DATA, **kwargs):
    run = assert_matches_v1(denormalized(**kwargs), {"in.csv": data}, tmp_path)
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


def test_rows_that_agree_in_the_other_columns_become_one_in_the_order_they_first_come(tmp_path):
    assert same(tmp_path) == ["1;ann;sql;python;sql", "2;bob;java;", "3;cy;", ";nobody;x;y"]


def test_merge_keeps_each_value_once(tmp_path):
    assert same(tmp_path, columns=[column("skill", ",", True)])[0] == "1;ann;sql,python"


def test_delimiter_of_several_characters(tmp_path):
    assert same(tmp_path, columns=[column("skill", " | ")])[0] == "1;ann;sql | python | sql"


def test_missing_values_are_left_out_or_kept_as_nothing(tmp_path):
    schema, data = "id:int, n:int", b"id;n\n1;5\n1;\n1;7\n2;\n"
    assert same(tmp_path, data, columns=[column("n", ",")], schema=schema, out="id:int, n:str") == ["1;5,7", "2;"]
    assert same(tmp_path / "b", data, columns=[column("n", ",")], schema=schema, out="id:int, n:str",
                null_as_empty=True) == ["1;5,,7", "2;"]


def test_several_columns_each_with_its_own_delimiter(tmp_path):
    data = b"id;name;skill\n1;a;x\n1;b;y\n1;a;z\n"
    assert same(tmp_path, data, columns=[column("name", "+", True), column("skill", "-")]) == ["1;a+b;x-y-z"]


@pytest.mark.parametrize("kind, data, got", [
    ("float", b"k;v\n1;1.5\n1;2.0\n", "1.5;2.0"),
    ("bool", b"k;v\n1;true\n1;false\n", "True;False"),
    ("Decimal#2", b"k;v\n1;1.5\n1;2\n", "1.50;2.00"),
    ("int", b"k;v\n1;3\n1;40\n", "3;40"),
], ids=["floats", "true or false", "Decimals", "whole numbers"])
def test_values_that_are_not_text_are_put_together_as_their_text(tmp_path, kind, data, got):
    rows = same(tmp_path, data, columns=[column("v")], schema=f"k:int, v:{kind}", out="k:int, v:str")
    assert rows == [f"1;{got}"]


def test_no_columns_named_hands_every_row_on(tmp_path):
    assert len(same(tmp_path, columns=[])) == 8


def test_no_rows_in(tmp_path):
    assert same(tmp_path, b"id;name;skill\n") == []


def test_whole_number_stays_whole_beside_a_missing_one(tmp_path):
    # v1 writes 3.0 here: pandas holds a whole-number column with a missing value as floats.
    made = denormalized([column("v", ",")], schema="k:int, v:int", out="k:int, v:str")
    assert v2(tmp_path, made, b"k;v\n1;3\n1;\n").status == "success"
    assert (tmp_path / "out.csv").read_bytes() == b"k;v\n1;3\n"


@pytest.mark.parametrize("columns, said", [
    ([column("nope")], "there is no column 'nope'"),
    ([column("id"), column("name"), column("skill")], "every column is named"),
    ([{"delimiter": ","}], "input_column"),
])
def test_columns_that_cannot_be_used_refuse_the_job(columns, said):
    with pytest.raises(JobRefusedError, match=said):
        load_job(denormalized(columns))


def test_converters_sample_loads():
    spec = next(c for c in json.loads(SAMPLE.read_text())["components"] if c["type"] == "Denormalize")
    load_job(denormalized(**{k: v for k, v in spec["config"].items() if k != "denormalize_columns"}))
