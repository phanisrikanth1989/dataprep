"""Pivot to columns delimited, against v1 on the same job config and bytes."""
import json
import os
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2 import answer_key

from .kit import columns, flow, job, reader

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tPivotToColumnsDelimited_0.1.json"
SCHEMA = "id:int, name:str, q:str, amt:float"
# Q2 comes before Q1; one cell holds two rows; cy has a quarter with no amount and an amount with no quarter.
DATA = b"id;name;q;amt\n1;ann;Q2;1.5\n1;ann;Q1;2\n2;bob;Q1;4\n1;ann;Q2;3\n3;cy;;7\n3;cy;Q3;\n"
BASE = dict(pivot_column="q", aggregation_column="amt", groupbys=["id", "name"])


def pivoted(schema=SCHEMA, **config):
    """file -> pivot, which writes out.csv itself."""
    component = {"id": "it", "type": "PivotToColumnsDelimited", "config": {"filename": "out.csv", **config},
                 "schema": {"input": columns(schema), "output": []}, "inputs": ["row1"], "outputs": []}
    return job([reader(schema, header_rows=1), component], [flow("row1", "in", "it")])


def on_both(tmp_path, made, data=DATA, files=None):
    key = answer_key.run_job(made, {"in.csv": data, **(files or {})}, tmp_path / "v1", answer_key.run_v1)
    run = answer_key.run_job(made, {"in.csv": data, **(files or {})}, tmp_path / "v2", answer_key.run_v2)
    assert key.succeeded and run.succeeded, (key.error, run.error)
    assert run.files == key.files
    return run.files


def same(tmp_path, data=DATA, **config):
    return on_both(tmp_path, pivoted(**{**BASE, **config}), data).get("out.csv")


def v2(tmp_path, made, data=DATA):
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    return result, (tmp_path / "out.csv").read_bytes() if (tmp_path / "out.csv").exists() else None


def test_values_of_the_pivot_column_become_columns_in_the_order_they_first_appear(tmp_path):
    assert same(tmp_path) == b"id;name;Q2;Q1;;Q3\n1;ann;4.5;2;;\n2;bob;;4;;\n3;cy;;;7;0\n"


@pytest.mark.parametrize("function, written", [
    ("count", b"id;name;Q2;Q1;;Q3\n1;ann;2;1;;\n2;bob;;1;;\n3;cy;;;1;0\n"),
    ("min", b"id;name;Q2;Q1;\n1;ann;1.5;2;\n2;bob;;4;\n3;cy;;;7\n"),
    ("max", b"id;name;Q2;Q1;\n1;ann;3;2;\n2;bob;;4;\n3;cy;;;7\n"),
    ("first", b"id;name;Q2;Q1;\n1;ann;1.5;2;\n2;bob;;4;\n3;cy;;;7\n"),
    ("last", b"id;name;Q2;Q1;\n1;ann;3;2;\n2;bob;;4;\n3;cy;;;7\n"),
])
def test_every_function(tmp_path, function, written):
    assert same(tmp_path, aggregation_function=function) == written


def test_column_of_floats_that_are_not_all_whole_is_written_as_floats(tmp_path):
    data = b"id;name;q;amt\n1;a;x;1.5\n2;b;x;2\n"
    assert same(tmp_path, data) == b"id;name;x\n1;a;1.5\n2;b;2.0\n"


def test_decimals_keep_their_places_and_text_is_written_as_it_is(tmp_path):
    made = pivoted("id:int, q:str, amt:Decimal#2", pivot_column="q", aggregation_column="amt", groupbys=["id"])
    assert on_both(tmp_path, made, b"id;q;amt\n1;a;1.5\n1;a;2\n2;b;3\n")["out.csv"] == b"id;a;b\n1;3.50;\n2;;3.00\n"
    made = pivoted("id:int, q:int, amt:str", pivot_column="q", aggregation_column="amt", groupbys=["id"],
                   aggregation_function="first")
    assert on_both(tmp_path / "b", made, b"id;q;amt\n1;10;x\n1;20;a,b\n2;10;z\n")["out.csv"] == b"id;10;20\n1;x;a,b\n2;z;\n"


def test_separators_and_encoding(tmp_path):
    data = "id;name;q;amt\n1;caf\u00e9;Q1;2\n".encode("utf-8")
    written = same(tmp_path, data, fieldseparator=",", rowseparator="\\r\\n", encoding="ISO-8859-15")
    assert written == "id,name,Q1\r\n1,caf\u00e9,2\r\n".encode("iso-8859-15")
    assert same(tmp_path / "b", fieldseparator="\\t").startswith(b"id\tname\tQ2")


def test_field_that_holds_the_separator_is_enclosed(tmp_path):
    made = pivoted("id:int, q:str, amt:str", pivot_column="q", aggregation_column="amt", groupbys=["id"],
                   aggregation_function="first")
    assert on_both(tmp_path, made, b'id;q;amt\n1;a,b;x\n2;c;say "hi"\n')["out.csv"] is not None
    made["components"][1]["config"]["fieldseparator"] = ","
    assert on_both(tmp_path / "b", made, b'id;q;amt\n1;a,b;x\n2;c;say "hi"\n')["out.csv"] == (
        b'id,"a,b",c\n1,x,\n2,,"say ""hi"""\n')


def test_no_rows_in_writes_no_file_and_neither_does_create_off(tmp_path):
    assert same(tmp_path, b"id;name;q;amt\n") is None
    assert same(tmp_path / "b", create=False) is None


def test_folder_that_is_not_there_is_made(tmp_path):
    files = on_both(tmp_path, pivoted(**{**BASE, "filename": "deep/er/out.csv"}))
    assert files["deep/er/out.csv"].startswith(b"id;name;Q2;Q1")


def test_whole_numbers_with_no_empty_cell_are_written(tmp_path):
    # v1 fails here: "Invalid value '' for dtype 'Int64'".
    made = pivoted("id:int, q:str, amt:int", pivot_column="q", aggregation_column="amt", groupbys=["id"])
    result, written = v2(tmp_path, made, b"id;q;amt\n1;a;1\n1;b;2\n2;a;3\n2;b;4\n1;a;10\n")
    assert result.status == "success" and written == b"id;a;b\n1;11;2\n2;3;4\n"


def test_rows_that_miss_a_group_value_are_a_group_of_their_own_as_in_talend(tmp_path):
    # v1 leaves such rows out (ticket 51).
    result, written = v2(tmp_path, pivoted(**BASE), b"id;name;q;amt\n1;ann;Q1;2\n;nobody;Q1;9\n;nobody;Q2;1\n")
    assert result.status == "success" and written == b"id;name;Q1;Q2\n1;ann;2;\n;nobody;9;1\n"


def test_rows_read_and_groups_written_are_in_globalmap(tmp_path):
    result, _ = v2(tmp_path, pivoted(**BASE))
    assert result.global_map["it_NB_LINE"] == 6 and result.global_map["it_NB_LINE_OUT"] == 3


def test_failure_further_on_in_the_subjob_leaves_no_file(tmp_path):
    made = pivoted(**BASE)
    made["components"][0]["config"]["die_on_error"] = True
    result, written = v2(tmp_path, made, b"id;name;q;amt\n1;ann;Q1;2\nx;bob;Q1;4\n")
    assert result.status == "failed" and written is None


@pytest.mark.parametrize("config, said", [
    ({"pivot_column": "nope"}, "pivot_column: there is no column 'nope'"),
    ({"aggregation_column": "nope"}, "aggregation_column: there is no column 'nope'"),
    ({"groupbys": []}, "groupbys"), ({"groupbys": ["nope"]}, "groupbys: there is no column 'nope'"),
    ({"aggregation_function": "avg"}, "aggregation_function"), ({"fieldseparator": "||"}, "fieldseparator"),
    ({"aggregation_column": "name"}, "sum needs a column of numbers"), ({"filename": ""}, "path: the file to write has no name"),
    ({"nope": 1}, "unknown config key"),
])
def test_what_cannot_be_used_refuses_the_job(config, said):
    with pytest.raises(JobRefusedError, match=said):
        load_job(pivoted(**{**BASE, **config}))


def test_columns_are_checked_when_the_rows_arrive_where_the_input_declares_none(tmp_path):
    made = pivoted(**{**BASE, "pivot_column": "nope"})
    made["components"][1]["schema"]["input"] = []
    result, written = v2(tmp_path, made)
    assert result.status == "failed" and "pivot_column: there is no column 'nope'" in result.error and written is None


def test_switches_v1_does_not_act_on_change_nothing(tmp_path):
    extra = dict(csv_option=True, advanced_separator=True, thousands_separator=".", decimal_separator=",",
                 escape_char="\\", text_enclosure="'")
    assert same(tmp_path, **extra) == b"id;name;Q2;Q1;;Q3\n1;ann;4.5;2;;\n2;bob;;4;;\n3;cy;;;7;0\n"


def test_flow_that_leaves_it_is_refused():
    from .kit import writer
    made = pivoted(**BASE)
    made["components"].append(writer(SCHEMA, "after", "after.csv", ("row2",)))
    made["flows"].append(flow("row2", "it", "after"))
    with pytest.raises(JobRefusedError, match="has no 'flow' output"):
        load_job(made)


def test_converters_sample_loads():
    spec = next(c for c in json.loads(SAMPLE.read_text())["components"] if c["type"] == "PivotToColumnsDelimited")
    made = pivoted("employee_id:int, name:str, quarter:str, sales_amount:float")
    made["components"][1]["config"] = spec["config"]
    load_job(made)


@pytest.mark.parametrize("schema, config, data", [
    ("d:datetime@%Y-%m-%d, q:str, amt:float", dict(groupbys=["d"]), b"d;q;amt\n2024-01-31;a;1\n2024-01-31;b;2\n2024-02-01;a;3.5\n"),
    ("d:datetime, q:str, amt:float", dict(groupbys=["d"]), b"d;q;amt\n2024-01-31 10:20:30;a;1\n2024-02-01 00:00:00;b;2.5\n"),
    ("id:int, q:float, amt:float", dict(groupbys=["id"]), b"id;q;amt\n1;1.5;1\n1;2;2.5\n2;1.5;4\n"),
    ("id:int, q:bool, amt:float", dict(groupbys=["id"]), b"id;q;amt\n1;true;1\n1;false;2.5\n"),
    ("id:int, q:str, amt:bool", dict(groupbys=["id"], aggregation_function="first"), b"id;q;amt\n1;a;true\n1;b;false\n"),
    ("id:int, q:str, amt:datetime@%Y-%m-%d", dict(groupbys=["id"], aggregation_function="max"),
     b"id;q;amt\n1;a;2024-01-31\n1;a;2024-03-01\n2;b;2024-02-01\n"),
    ("m:Decimal#2, q:str, amt:float", dict(groupbys=["m"]), b"m;q;amt\n1.5;a;1\n1.50;a;2.5\n2;b;3\n"),
], ids=["group by a date with a pattern", "group by a date and time", "pivot on a float", "pivot on true or false",
        "cells of true or false", "cells of dates", "group by a Decimal"])
def test_columns_of_every_kind_as_in_v1(tmp_path, schema, config, data):
    made = pivoted(schema, **{"pivot_column": "q", "aggregation_column": "amt", **config})
    on_both(tmp_path, made, data)


def test_true_or_false_to_group_by_and_a_date_to_pivot_on_are_written_as_talend_writes_them(tmp_path):
    # Talend writes a date by its column's pattern and true as "true". v1 writes the date with its time of
    # day (2024-01-31 00:00:00) and the word as "True".
    made = pivoted("ok:bool, q:datetime@%d/%m/%Y, amt:float", pivot_column="q", aggregation_column="amt", groupbys=["ok"])
    result, written = v2(tmp_path, made, b"ok;q;amt\ntrue;31/01/2024;1\nfalse;01/02/2024;2.5\n")
    assert result.status == "success" and written == b"ok;31/01/2024;01/02/2024\ntrue;1;\nfalse;;2.5\n"


def test_row_with_no_pivot_value_takes_no_part(tmp_path):
    made = pivoted("id:int, q:int, amt:float", pivot_column="q", aggregation_column="amt", groupbys=["id"])
    assert on_both(tmp_path, made, b"id;q;amt\n1;10;1.5\n1;;99\n2;10;2\n2;20;3\n")["out.csv"] == b"id;10;20\n1;1.5;\n2;2.0;3\n"


@pytest.mark.parametrize("function, cell", [("first", b"5"), ("last", b"7")])
def test_first_and_last_are_of_the_values_that_are_there(tmp_path, function, cell):
    written = same(tmp_path, b"id;name;q;amt\n1;a;x;\n1;a;x;5\n1;a;x;7\n1;a;x;\n", aggregation_function=function)
    assert written == b"id;name;x\n1;a;" + cell + b"\n"
