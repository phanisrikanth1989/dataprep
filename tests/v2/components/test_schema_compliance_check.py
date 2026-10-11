"""Schema compliance check, against v1 on the same job config and bytes."""
import json
import os
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2 import answer_key
from tests.v2.answer_key import assert_matches_v1

from .kit import columns, flow, job, reader, writer

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tSchemaComplianceCheck_0.1.json"
TEXT = "id:str, name:str, amt:str, ok:str, day:str"
CHECKED = [
    {"name": "id", "type": "int", "nullable": False},
    {"name": "name", "type": "str", "nullable": False, "length": 5},
    {"name": "amt", "type": "Decimal", "nullable": True},
    {"name": "ok", "type": "bool", "nullable": True},
    {"name": "day", "type": "datetime", "nullable": True, "date_pattern": "%Y-%m-%d"},
]
DATA = (b"id;name;amt;ok;day\n"
        b"1;ann;1.5;true;2024-01-31\n"          # fits
        b";bob;2;false;2024-02-01\n"            # no id
        b"x;cy;3;yes;\n"                        # id is no number
        b"4;christopher;;1;\n"                  # name too long
        b"5;;abc;maybe;31/01/2024\n"            # no name, amt no number, ok no true/false
        b" 6 ;  ;1e3;;\n"                       # blanks: id fits, name is as good as missing
        b"7;di;nan;NO;2024-13-01\n")            # nan is no number here


def checked(schema=TEXT, checks=CHECKED, rejects=True, out=None, **config):
    """file -> schema compliance check -> out.csv, and rej.csv for the rows that do not fit."""
    component = {"id": "it", "type": "SchemaComplianceCheck", "config": {"schema": checks, **config},
                 "schema": {"input": columns(schema), "output": columns(out or schema)},
                 "inputs": ["row1"], "outputs": ["row2"]}
    components = [reader(schema, header_rows=1), component, writer(out or schema)]
    flows = [flow("row1", "in", "it"), flow("row2", "it", "out")]
    if rejects:
        component["outputs"].append("row3")
        components.append(writer(None, "rej", "rej.csv", ("row3",)))
        flows.append(flow("row3", "it", "rej", "reject"))
    return job(components, flows)


def same(tmp_path, data=DATA, **kwargs):
    """Both engines write the same rows to both files. Returns the ids kept, and what is wrong by id.

    Where no row is turned away v1 leaves the reject file without its header line and v2 writes the line.
    """
    made = checked(**kwargs)
    key = answer_key.run_job(made, {"in.csv": data}, tmp_path / "v1", answer_key.run_v1)
    run = answer_key.run_job(made, {"in.csv": data}, tmp_path / "v2", answer_key.run_v2)
    assert key.succeeded and run.succeeded, (key.error, run.error)
    assert run.files["out.csv"] == key.files["out.csv"]
    if "rej.csv" in run.files:
        assert run.files["rej.csv"] == key.files["rej.csv"] or (
            key.files["rej.csv"] == b"" and len(run.files["rej.csv"].splitlines()) == 1)
    kept = [line.split(";")[0] for line in run.files["out.csv"].decode().splitlines()[1:]]
    turned_away = {line.split(";")[0]: line.rsplit(";8;", 1)[1] if ";8;" in line else line
                   for line in run.files.get("rej.csv", b"").decode().splitlines()[1:]}
    return kept, turned_away


def v2(tmp_path, made, data=DATA):
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def test_rows_that_fit_go_on_and_the_others_leave_with_what_is_wrong(tmp_path):
    kept, turned_away = same(tmp_path)
    assert kept == ["1"]
    assert turned_away[" 6 "] == "name:cannot be null" and turned_away["7"] == "amt:invalid type"
    assert turned_away[""] == "id:cannot be null"
    assert turned_away["x"] == "id:invalid type"
    assert turned_away["4"] == "name:exceed max length"
    assert turned_away["5"] == "name:cannot be null;amt:invalid type;ok:invalid type"


def test_reject_output_has_the_rows_as_they_came_with_code_8(tmp_path):
    run = assert_matches_v1(checked(), {"in.csv": DATA}, tmp_path)
    lines = run.files["rej.csv"].decode().splitlines()
    assert lines[0] == "id;name;amt;ok;day;errorCode;errorMessage"
    assert lines[1] == ";bob;2;false;2024-02-01;8;id:cannot be null"


def test_date_is_held_to_its_pattern_only_when_asked(tmp_path):
    _, loose = same(tmp_path)
    assert "day" not in loose.get("5", "")
    _, strict = same(tmp_path / "b", strict_date_check=True)
    assert strict["5"].endswith("day:invalid date format") and strict["7"].endswith("day:invalid date format")


def test_empty_text_is_missing_unless_told_otherwise(tmp_path):
    kept, turned_away = same(tmp_path, all_empty_are_null=False)
    assert "5" in turned_away and "name:cannot be null" not in turned_away["5"]
    by_column = [{"column": "name", "empty_is_null": True}, {"column": "id", "empty_is_null": False}]
    _, turned_away = same(tmp_path / "b", all_empty_are_null=False, empty_null_table=by_column)
    assert turned_away["5"].startswith("name:cannot be null")


def test_only_the_columns_listed_are_checked_and_the_list_says_what_may_be_missing(tmp_path):
    listed = [{"column": "name", "selected_type": "String", "date_pattern": "", "nullable": True, "max_length": False}]
    kept, turned_away = same(tmp_path, check_another=True, check_all=False, checkcols=listed)
    assert turned_away == {"4": "name:exceed max length"}


def test_length_in_bytes(tmp_path):
    data = "id;name;amt;ok;day\n1;héllo;;;\n2;hello;;;\n".encode("utf-8")
    kept, _ = same(tmp_path, data)
    assert kept == ["1", "2"]
    kept, turned_away = same(tmp_path / "b", data, check_string_by_byte_length=True, charset="UTF-8")
    assert kept == ["2"] and turned_away["1"] == "name:exceed max length"
    kept, _ = same(tmp_path / "c", data, check_string_by_byte_length=True, charset="ISO-8859-1")
    assert kept == ["1", "2"]


def test_typed_columns_are_checked_as_they_arrive(tmp_path):
    kept, turned_away = same(tmp_path, b"id;name;amt;ok;day\n1;ann;1.5;true;2024-01-31\n;bob;;;\n2;christopher;2;false;\n",
                             schema="id:int, name:str, amt:Decimal#2, ok:bool, day:datetime@%Y-%m-%d")
    assert kept == ["1"] and set(turned_away) == {"", "2"}


def test_column_of_the_schema_that_is_not_in_the_rows_is_passed_over(tmp_path):
    kept, turned_away = same(tmp_path, checks=CHECKED + [{"name": "nope", "type": "int", "nullable": False}])
    assert kept[0] == "1" and turned_away[""] == "id:cannot be null"


def test_no_rows_and_nothing_to_check(tmp_path):
    assert same(tmp_path, b"id;name;amt;ok;day\n") == ([], {})
    kept, turned_away = same(tmp_path / "b", checks=[{"name": "name", "type": "str", "nullable": True}], rejects=False)
    assert len(kept) == 7 and turned_away == {}


def test_switches_v1_only_warns_of_change_nothing(tmp_path):
    kept, _ = same(tmp_path, customer=True, sub_string=True, fast_date_check=True, ignore_timezone=True)
    assert kept[0] == "1"


def test_rows_turned_away_with_no_flow_to_take_them_are_told_in_the_log(tmp_path, caplog):
    result = v2(tmp_path, checked(rejects=False))
    assert result.status == "success"
    assert "[it] 6 rows were dropped (no flow takes this component's rejects); the first: id:cannot be null" in caplog.text
    assert "the row is line 3 of in.csv" in caplog.text


@pytest.mark.parametrize("config, said", [
    ({}, "schema: required"), ({"schema": [{"name": "id"}]}, r"schema\[0\].type"), ({"schema": "id:int"}, "schema: expected"),
    ({"schema": CHECKED, "check_string_by_byte_length": True, "charset": "UTF-16"}, "charset"),
    ({"schema": CHECKED, "charset": "nope"}, "is no character set Python knows"),
    ({"schema": CHECKED, "strict": True}, "unknown config key"),
])
def test_what_cannot_be_read_refuses_the_job(config, said):
    made = checked()
    made["components"][1]["config"] = config
    with pytest.raises(JobRefusedError, match=said):
        load_job(made)


def test_converters_sample_loads():
    spec = next(c for c in json.loads(SAMPLE.read_text())["components"] if c["type"] == "SchemaComplianceCheck")
    made = checked()
    made["components"][1]["config"] = spec["config"]
    load_job(made)


def test_column_by_column_table_is_not_read_while_every_empty_text_counts_as_missing(tmp_path):
    # Talend writes the table for every column with "false"; read under the switch, it would undo the switch.
    _, turned_away = same(tmp_path, empty_null_table=[{"column": "name", "empty_is_null": False}])
    assert turned_away["5"].startswith("name:cannot be null")
