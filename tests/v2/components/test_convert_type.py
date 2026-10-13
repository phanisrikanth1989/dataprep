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
        "id;n;f;b;d;s;errorCode;errorMessage",
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
    assert lines(tmp_path) == ["id;n;f;b;d;s"] and lines(tmp_path, "rej.csv") == ["id;n;f;b;d;s;errorCode;errorMessage"]


def test_a_key_it_does_not_know():
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


# ------------------------------------------------------------------
# What a second reader of this component found (ticket 62)
# ------------------------------------------------------------------

MIXED = "id:int, n:int, f:float, b:bool, d:datetime@%Y-%m-%d, dec:Decimal#2, s:str"
MIXED_DATA = b"id;n;f;b;d;dec;s\n1;10;2.0;true;2024-01-31;2.00;7\n2;;;;;;\n3;-3;2.5;false;2024-02-01;1.50;x\n"


def to_another(tmp_path, source, kind, rejects=False):
    """Both engines, for a pair that reads a typed column into the new column x2; returns x2 of every row kept."""
    made = converted(f"{MIXED}, x2:{kind}", rejects=rejects, schema=MIXED,
                     manualtable=[{"input_column": source, "output_column": "x2"}])
    run = assert_matches_v1(made, {"in.csv": MIXED_DATA}, tmp_path)
    assert run.succeeded, run.error
    return [line.split(";")[0] + ":" + line.split(";")[-1] for line in run.files["out.csv"].decode().splitlines()[1:]]


@pytest.mark.parametrize("source, kind, got", [
    ("d", "datetime@%Y-%m-%d", ["1:2024-01-31", "2:", "3:2024-02-01"]),
    ("d", "str", ["1:2024-01-31", "2:", "3:2024-02-01"]),
    ("b", "int", ["1:1", "2:0", "3:0"]),
    ("n", "float", ["1:10.0", "2:", "3:-3.0"]),
    ("n", "str", ["1:10", "2:", "3:-3"]),
    ("f", "int", ["1:2", "2:"]),
    ("dec", "int", ["1:2", "2:"]),
    ("dec", "float", ["1:2.0", "2:", "3:1.5"]),
], ids=["date to date", "date to text", "true or false to a whole number", "whole number to float",
        "whole number to text", "float to a whole number", "Decimal to a whole number", "Decimal to float"])
def test_column_that_is_not_text_is_converted_as_in_v1(tmp_path, source, kind, got):
    assert to_another(tmp_path, source, kind) == got


def on_both(tmp_path, made, data):
    """Both engines: the same rows kept and the same rows turned away (the two word a fault differently)."""
    from tests.v2 import answer_key
    key = answer_key.run_job(made, {"in.csv": data}, tmp_path / "v1", answer_key.run_v1)
    actual = answer_key.run_job(made, {"in.csv": data}, tmp_path / "v2", answer_key.run_v2)
    assert key.succeeded and actual.succeeded, (key.error, actual.error)
    assert key.files["out.csv"] == actual.files["out.csv"]
    turned_away = [[line.rsplit(";", 2)[0] for line in run.files["rej.csv"].decode().splitlines()] for run in (key, actual)]
    assert turned_away[0] == turned_away[1]
    return actual.files["out.csv"].decode().splitlines()[1:], turned_away[1][1:]


def test_fraction_written_as_text_is_no_whole_number(tmp_path):
    made = converted(IN + ", x2:int", manualtable=[{"input_column": "f", "output_column": "x2"}])
    kept, turned_away = on_both(tmp_path, made, b"id;n;f;b;d;s\n1;;1.5;;;\n2;;.5;;;\n3;;4;;;\n4;;2.0;;;\n")
    assert [line.split(";")[0] for line in turned_away] == ["1", "2"]
    assert [line.split(";")[-1] for line in kept] == ["4", "2"]


def test_die_on_error_is_the_engines_and_another_key_than_dieonerror(tmp_path):
    # v1's base class reads die_on_error, for a value that may not be missing; the component reads dieonerror.
    made = converted("id:str, n:str, a:int", schema="id:str, n:str", die_on_error=True,
                     manualtable=[{"input_column": "n", "output_column": "a"}])
    kept, turned_away = on_both(tmp_path, made, b"id;n\n1;10\n2;x\n3;\n")
    assert kept == ["1;10;10", "3;;"] and turned_away == ["2;x"]
    # A row that misses a value it may not miss goes to the same reject output, as on v1 (which writes the
    # whole number beside it as 10.0).
    made = converted("id:str, n:str, a:int!", schema="id:str, n:str", die_on_error=False,
                     manualtable=[{"input_column": "n", "output_column": "a"}])
    assert ran(tmp_path, made, b"id;n\n1;10\n2;x\n3;\n").status == "success"
    assert lines(tmp_path) == ["id;n;a", "1;10;10"]
    rejected = lines(tmp_path, "rej.csv")
    assert rejected[0].split(";")[:4] == ["id", "n", "errorCode", "errorMessage"]
    assert [line.split(";")[:3] for line in rejected[1:]] == [["2", "x", "CONVERSION_ERROR"], ["3", "", "SCHEMA_VIOLATION"]]


def test_empty_to_null_is_no_spelling_of_v1s():
    with pytest.raises(JobRefusedError, match="empty_to_null: unknown config key"):
        load_job(converted(empty_to_null=True))


def test_pair_whose_output_column_is_not_declared_is_read_as_the_type_of_its_own_column(tmp_path):
    made = converted("id:str, n:int", schema="id:str, n:str", manualtable=[{"input_column": "n", "output_column": "other"}])
    ran(tmp_path, made, b"id;n\n1;5\n2;x\n")
    assert lines(tmp_path, "rej.csv")[1:] == ["2;x;CONVERSION_ERROR;Column 'n' -> 'other' (int): cannot read 'x'"]


def test_missing_text_is_a_missing_value_and_no_fault(tmp_path):
    made = converted("id:str, n:int", schema="id:str, n:str", emptytonull=True, manualtable=pairs("n"))
    ran(tmp_path, made, b"id;n\n1;5\n2;\n")
    assert lines(tmp_path) == ["id;n", "1;5", "2;"] and lines(tmp_path, "rej.csv") == ["id;n;errorCode;errorMessage"]


def test_input_column_named_like_a_reject_column_keeps_its_values_under_the_engines_name_for_it(tmp_path):
    made = converted("id:str, n:int", schema="id:str, n:str, errorCode:str, errorMessage:str", manualtable=pairs("n"))
    ran(tmp_path, made, b"id;n;errorCode;errorMessage\n1;x;old;older\n")
    assert lines(tmp_path, "rej.csv") == [
        "id;n;errorCode_user;errorMessage_user;errorCode;errorMessage",
        "1;x;old;older;CONVERSION_ERROR;Column 'n' -> 'n' (int): cannot read 'x'"]
