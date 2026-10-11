"""Convert type. v1 on today's pandas turns away every row it converts in place, so most of this is v2 alone."""
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import columns, flow, job, reader, writer

IN = "id:str, n:str, f:str, b:str, d:str, s:str"
TYPED = "id:str, n:int, f:float, b:bool, d:datetime@%Y-%m-%d, s:str"
DATA = b"id;n;f;b;d;s\n1;10;1.5;true;2024-01-31;a\n2;x;2;false;2024-02-01;\n3;;;;;c\n4; 7 ;1e3;TRUE;31/01/2024;d\n"


def pairs(*names):
    return [{"input_column": name, "output_column": name} for name in names]


def converted(out=TYPED, rejects=True, schema=IN, **config):
    component = {"id": "it", "type": "ConvertType", "config": config,
                 "schema": {"input": columns(schema), "output": columns(out)}, "inputs": ["row1"], "outputs": ["row2"]}
    components = [reader(schema, header_rows=1), component, writer(out)]
    flows = [flow("row1", "in", "it"), flow("row2", "it", "out")]
    if rejects:
        components.append(writer(None, "rej", "rej.csv", ("row3",)))
        flows.append(flow("row3", "it", "rej", "reject"))
    return job(components, flows)


def ran(tmp_path, made, data=DATA):
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def lines(tmp_path, name="out.csv"):
    return (tmp_path / name).read_bytes().decode().splitlines()


def test_column_is_read_as_its_declared_type_and_a_row_that_cannot_be_goes_to_the_rejects(tmp_path):
    assert ran(tmp_path, converted(manualtable=pairs("n"))).status == "success"
    assert lines(tmp_path) == ["id;n;f;b;d;s", "1;10;1.5;true;2024-01-31;a", "3;;;;;c", "4;7;1000.0;true;;d"]
    assert lines(tmp_path, "rej.csv") == [
        "id;n;f;b;d;s;error_code;error_message",
        "2;x;2;false;2024-02-01;;CONVERSION_ERROR;Column 'n' -> 'n' (int): cannot read 'x'"]


@pytest.mark.parametrize("name, turned_away", [("f", []), ("b", []), ("d", ["4"]), ("s", [])])
def test_every_type(tmp_path, name, turned_away):
    ran(tmp_path, converted(manualtable=pairs(name)))
    assert [line.split(";")[0] for line in lines(tmp_path, "rej.csv")[1:]] == turned_away


def test_first_fault_of_a_row_is_the_one_said(tmp_path):
    ran(tmp_path, converted(manualtable=pairs("d", "n")), b"id;n;f;b;d;s\n1;x;;;y;\n")
    assert lines(tmp_path, "rej.csv")[1].endswith("Column 'd' -> 'd' (datetime): cannot read 'y'")


def test_die_on_error_fails_the_job_and_names_the_row(tmp_path):
    result = ran(tmp_path, converted(manualtable=pairs("n"), dieonerror=True))
    assert result.status == "failed" and result.failed_component == "it"
    assert result.error == ("Type conversion failed for 1 row(s); the first: Column 'n' -> 'n' (int): cannot read 'x'; "
                            "the row is line 3 of in.csv")
    assert not (tmp_path / "out.csv").exists()


def test_rows_turned_away_with_no_flow_to_take_them_are_told_in_the_log(tmp_path, caplog):
    result = ran(tmp_path, converted(rejects=False, manualtable=pairs("n")))
    assert result.status == "success" and len(lines(tmp_path)) == 4
    assert "[it] 1 row was dropped (no flow takes this component's rejects): Column 'n' -> 'n' (int): cannot read 'x'" in caplog.text


def test_pair_with_another_output_column_adds_it_as_in_v1(tmp_path):
    out = IN + ", n2:int"
    made = converted(out, rejects=False, manualtable=[{"input_column": "n", "output_column": "n2"}])
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.files["out.csv"].decode().splitlines()[1:] == [
        "1;10;1.5;true;2024-01-31;a;10", "3;;;;;c;", "4; 7 ;1e3;TRUE;31/01/2024;d;7"]


def test_empty_text_becomes_a_missing_value(tmp_path):
    made = converted("id:str, s:str!", rejects=False, emptytonull=True)
    made["components"][1]["config"]["dieonerror"] = False
    result = ran(tmp_path, made)
    assert result.status == "failed" and "Column 's' has NULL values but is not nullable" in result.error
    assert ran(tmp_path, converted("id:str, s:str!", rejects=False)).status == "success"


def test_number_column_is_converted_to_text_and_back(tmp_path):
    made = converted("id:int, n:str, amount:int", schema="id:int, n:float", manualtable=[
        {"input_column": "n", "output_column": "n"}, {"input_column": "id", "output_column": "amount"}])
    ran(tmp_path, made, b"id;n\n1;2.5\n2;\n")
    assert lines(tmp_path) == ["id;n;amount", "1;2.5;1", "2;;2"]


def test_autocast_and_a_pair_for_a_column_that_is_not_there_change_nothing(tmp_path):
    result = ran(tmp_path, converted(autocast=True, manualtable=pairs("nope")), b"id;n;f;b;d;s\n1;5;;;;\n")
    assert result.status == "success" and lines(tmp_path)[1] == "1;5;;;;"


def test_no_rows(tmp_path):
    ran(tmp_path, converted(manualtable=pairs("n")), b"id;n;f;b;d;s\n")
    assert lines(tmp_path) == ["id;n;f;b;d;s"] and lines(tmp_path, "rej.csv") == ["id;n;f;b;d;s;error_code;error_message"]


def test_v1_spellings_and_a_key_it_does_not_know():
    load_job(converted(die_on_error=True, empty_to_null=True))
    with pytest.raises(JobRefusedError, match="unknown config key"):
        load_job(converted(cast_all=True))


def test_row_is_turned_away_for_a_fault_in_any_of_the_pairs(tmp_path):
    ran(tmp_path, converted(manualtable=pairs("n", "d")))
    assert [line.split(";")[0] for line in lines(tmp_path, "rej.csv")[1:]] == ["2", "4"]
    assert lines(tmp_path, "rej.csv")[2].endswith("Column 'd' -> 'd' (datetime): cannot read '31/01/2024'")


def test_pair_to_a_text_column_of_another_name_hands_the_value_on_as_text(tmp_path):
    made = converted("id:int, n:float, shown:str", schema="id:int, n:float", rejects=False,
                     manualtable=[{"input_column": "n", "output_column": "shown"}])
    ran(tmp_path, made, b"id;n\n1;2.5\n2;\n")
    assert lines(tmp_path) == ["id;n;shown", "1;2.5;2.5", "2;;"]
