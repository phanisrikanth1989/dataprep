"""Filter columns, against v1 on the same job config and bytes."""
import json
import os
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import columns, flow, through, writer

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tFilterColumns_0.1.json"

SCHEMA = "id:int!, name:str, age:int, amt:float, flag:bool, d:datetime@%Y-%m-%d, m:Decimal#2"
DATA = (
    b"id;name;age;amt;flag;d;m\n"
    b"1;Alice;30;10.5;true;2024-01-31;1.50\n"
    b"2;bob;;20;false;2023-12-01;7\n"
    b"3;;25;;true;;\n"
)
HEADER_ONLY = b"id;name;age;amt;flag;d;m\n"
EVERY_COLUMN = (
    HEADER_ONLY + b"1;Alice;30;10.5;true;2024-01-31;1.50\n2;bob;;20.0;false;2023-12-01;7.00\n3;;25;;true;;\n"
)


def columns_job(out_schema, schema=SCHEMA, **config):
    """file -> filter columns -> file; the filter and the file after it declare ``out_schema``."""
    return through({"type": "FilterColumns", "config": config}, schema, out_schema)


def same(tmp_path, out_schema, data=DATA, fails=False, **kwargs):
    """Both engines do the same with the job; ``fails`` says the job is one neither finishes."""
    run = assert_matches_v1(columns_job(out_schema, **kwargs), {"in.csv": data}, tmp_path)
    assert run.succeeded is not fails, run.error
    return run


def v2(tmp_path, out_schema, data=DATA, **kwargs):
    """Run on v2 only, inside tmp_path; returns (result, the folder)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(columns_job(out_schema, **kwargs)), tmp_path
    finally:
        os.chdir(previous)


def refused(made):
    """The refusal report v2 gives the job at load."""
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    return caught.value.report.format()


# ------------------------------------------------------------------
# Which columns leave, and in what order
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "out_schema, want",
    [
        ("id:int!, name:str, amt:float", b"id;name;amt\n1;Alice;10.5\n2;bob;20.0\n3;;\n"),
        ("amt:float, id:int!", b"amt;id\n10.5;1\n20.0;2\n;3\n"),
        ("d:datetime@%Y-%m-%d", b"d\n2024-01-31\n2023-12-01\n\n"),
        ("m:Decimal#2, flag:bool, name:str", b"m;flag;name\n1.50;true;Alice\n7.00;false;bob\n;true;\n"),
        (SCHEMA, EVERY_COLUMN),
    ],
)
def test_declared_columns_leave_in_declared_order(tmp_path, out_schema, want):
    assert same(tmp_path, out_schema).files["out.csv"] == want


def test_every_row_is_kept(tmp_path):
    data = b"id;name;age;amt;flag;d;m\n" + b"".join(b"%d;n%d;%d;;true;;\n" % (i, i % 3, i) for i in range(1, 501))
    run = same(tmp_path, "name:str, id:int!", data=data)
    assert run.files["out.csv"].split(b"\n")[:3] == [b"name;id", b"n1;1", b"n2;2"]
    assert run.files["out.csv"].count(b"\n") == 501


@pytest.mark.parametrize(
    "out_schema, want",
    [
        ("name:str, n1:int, n2:float, n4:datetime@%Y-%m-%d, n6:str, id:int!",
         b"name;n1;n2;n4;n6;id\nAlice;;;;;1\nbob;;;;;2\n;;;;;3\n"),
        ("name:str, n1:int!, n2:float!, n3:bool!, n4:datetime!@%Y-%m-%d, n5:Decimal#2!, n6:str!",
         b"name;n1;n2;n3;n4;n5;n6\nAlice;0;0.0;false;1970-01-01;0.00;\nbob;0;0.0;false;1970-01-01;0.00;\n"
         b";0;0.0;false;1970-01-01;0.00;\n"),
        ("ID:int, Name:str, name:str", b"ID;Name;name\n;;Alice\n;;bob\n;;\n"),
    ],
)
def test_declared_column_the_input_lacks_is_added(tmp_path, out_schema, want):
    assert same(tmp_path, out_schema).files["out.csv"] == want


def test_no_declared_columns_passes_every_column(tmp_path):
    made = columns_job(SCHEMA)
    made["components"][1]["schema"] = {"input": columns(SCHEMA), "output": []}
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.succeeded and run.files["out.csv"] == EVERY_COLUMN


@pytest.mark.parametrize(
    "out_schema, want",
    [
        ("id:str, age:float", b"id;age\n1;30\n2;\n3;25\n"),
        ("amt:float#0, m:Decimal#1, id:int!", b"amt;m;id\n10.0;1.5;1\n20.0;7.0;2\n;;3\n"),
        ("d:datetime@%d/%m/%Y, id:int!", b"d;id\n31/01/2024;1\n01/12/2023;2\n;3\n"),
    ],
)
def test_declared_types_and_places_are_the_engines_to_apply(tmp_path, out_schema, want):
    assert same(tmp_path, out_schema).files["out.csv"] == want


def test_no_input_rows(tmp_path):
    assert same(tmp_path, SCHEMA, data=HEADER_ONLY).files["out.csv"] == HEADER_ONLY


def test_no_input_rows_still_leaves_the_declared_columns_only(tmp_path):
    # v1 passes an empty input on untouched, so its output then has every input column.
    result, folder = v2(tmp_path, "name:str, id:int!", data=HEADER_ONLY)
    assert result.status == "success"
    assert (folder / "out.csv").read_bytes() == b"name;id\n"


# ------------------------------------------------------------------
# Rows the declared schema does not allow
# ------------------------------------------------------------------

@pytest.mark.parametrize("config", [{}, {"die_on_error": True}])
def test_missing_value_the_schema_forbids_fails_the_component(tmp_path, config):
    same(tmp_path, "id:int!, age:int!", fails=True, **config)
    result, _ = v2(tmp_path / "direct", "id:int!, age:int!", **config)
    assert result.failed_component == "it"
    assert result.error == "Column 'age' has NULL values but is not nullable; the row is line 3 of in.csv"


def test_missing_value_the_schema_forbids_drops_the_row_when_errors_are_not_fatal(tmp_path):
    assert same(tmp_path, "id:int!, age:int!", die_on_error=False).files["out.csv"] == b"id;age\n1;30\n3;25\n"


# ------------------------------------------------------------------
# What v2 says no to, and what it lets pass
# ------------------------------------------------------------------

def test_keys_that_change_nothing_are_accepted(tmp_path):
    run = same(tmp_path, "amt:float, id:int!", label="Keep_2_Columns", tstatcatcher_stats=False,
               execution_mode="batch", chunk_size=2)
    assert run.files["out.csv"] == b"amt;id\n10.5;1\n20.0;2\n;3\n"


@pytest.mark.parametrize("name", ["FilterColumns", "tFilterColumns"])
def test_v1_type_names(tmp_path, name):
    made = columns_job("amt:float, id:int!")
    made["components"][1]["type"] = name
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.succeeded and run.files["out.csv"] == b"amt;id\n10.5;1\n20.0;2\n;3\n"


def test_v2_type_name():
    made = columns_job("amt:float, id:int!")
    made["components"][1]["type"] = "filter_columns"
    load_job(made)


def test_schema_that_shares_no_column_with_the_input_is_refused():
    # v1 writes one row of missing values for every input row.
    report = refused(columns_job("x:str, y:int"))
    assert "schema: none of the declared columns (x, y) is among the input's columns" in report


@pytest.mark.parametrize("config, said", [({"mode": "exclude"}, "mode: unknown config key"),
                                           ({"columns": ["id"]}, "columns: unknown config key")])
def test_unknown_keys_are_refused(config, said):
    assert said in refused(columns_job("id:int!", **config))


def test_reject_flow_is_refused():
    made = columns_job("id:int!")
    made["components"].append(writer(None, component_id="rej", path="rej.csv", inputs=("bad",)))
    made["flows"].append(flow("bad", "it", "rej", "reject"))
    assert "has no 'reject' output" in refused(made)


def test_converter_sample_loads():
    component = next(c for c in json.loads(SAMPLE.read_text())["components"] if c["type"] == "FilterColumns")
    schema = ", ".join(
        "{name}:{type}{nullable}{pattern}".format(
            name=column["name"], type=column["type"], nullable="" if column["nullable"] else "!",
            pattern="@" + column["date_pattern"] if column.get("date_pattern") else "",
        )
        for column in component["schema"]["input"]
    )
    load_job(through({"type": "FilterColumns", "config": component["config"], "schema": component["schema"]}, schema))
