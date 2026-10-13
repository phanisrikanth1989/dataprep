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
        header = ";".join([column["name"] for column in made["components"][1]["schema"]["input"]]
                          + ["errorCode", "errorMessage"]) + "\n"
        assert run.files["rej.csv"] == key.files["rej.csv"] or (
            key.files["rej.csv"] == b"" and run.files["rej.csv"].decode() == header)
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


# ------------------------------------------------------------------
# What an independent review found (ticket 67)
# ------------------------------------------------------------------

DATE_PATTERNS = [
    "%Y-%m-%d", "%Y%m%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%d-%m-%y",
    "%m/%d/%Y %I:%M %p", "%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S%z", "%H:%M", "%Y/%m/%d", "%d.%m.%Y", "%Y%m%d%H%M%S",
    "%Y-%m", "%y%m%d", "%Y-%m-%d %H:%M", "%d %m %Y", "%Y", "%Y %m %d", "%Y.%m.%d", "%Y-%m-%d %H", "%Y%m%d %H%M%S",
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S.%f", "%Y%m", "%Y-%m-%d %H:%M:%S.%f%z", "100%% %Y", "%Y-%m-%d (%H)",
]
DATE_VALUES = [
    "2024-01-31", "24-01-31", " 2024-01-31", "2024-01-31 ", "2024-1-5", "2024-1-05", "2024-01-5", "2024-02-30",
    "2023-02-29", "2024-02-29", "1900-02-29", "2000-02-29", "2024-13-01", "2024-00-10", "2024-01-00", "2024-01-32",
    "0000-01-01", "0000-02-29", "0001-01-01", "9999-12-31", "-2024-01-05", "+2024-01-31", "02024-01-05",
    "2024-001-05", "2024-01-005", "2024-01-31T", "2024-01-31Z", "2024-01-31x", "2024-01- 5", "2024- 1-05",
    "20240131", "240131", "2024131", "2024015", "202415", "202401311", "00000101", "202401", "20241",
    "31/01/2024", "1/1/2024", "31/1/24", "31/01/0000", "31/01/0001", " 1/01/2024",
    "2024-01-31 10:00:00", "2024-01-31  10:00:00", "2024-01-31\t10:00:00", "2024-01-31 10:00:00 ",
    "2024-01-31 1:2:3", "2024-01-31 10:00:5", "2024-01-31 010:00:00", "2024-01-31 10:000:00", "2024-01-31 10:00:000",
    "2024-01-31 24:00:00", "2024-01-31 10:60:00", "2024-01-31 10:00:60", "2024-01-31 10:00:61", "2024-01-31 10:00:62",
    "2024-01-31 10:00:00.", "2024-01-31 10:00:00.5", "2024-01-31 10:00:00.123456", "2024-01-31 10:00:00.123456789",
    "2024-01-31 10:00:00.1234567890", "2024-01-31 10:00:00.1x", "2024-01-31 10:00:00.5Z", "2024-01-31 10:00:00.+0100",
    "2024-01-31T10:00:00", "2024-01-31t10:00:00", "2024-01-31 10", "2024-01-31 1", "2024-01-31 24", "2024-01-31T10",
    "2024-01-31 10:00", "2024-01-31 10:5", "2024-01-31 1:05", "2024-01-31 (10)", "2024-01-31 (7)",
    "2024-01-  5", "2024- 1- 5", "2024 -01-05", "2024-01-5 ", "2024-01-\t5", "2024-01- 05", "2024-01- 31",
    "2024-01-31\n10:00:00", "2024-01-31 \t10:00:00", "2024-01-31 10: 5:00", "2024-01-31  1:05:00",
    "2024-01-31 10:05: 7", "2024 1 5", "202401 5", "2024 105", "2024/01/ 5", "2024/ 1/05", "2024-01-31T 1:05:00",
    "2024-01-31 T10:05:00", "2024-01-31T  10:05:00", "2024-01-31T\t10:05:00", "31/01/2024  10:00:00",
    "31-01-24", "31-01-69", "31-01-68", "29-02-00", "29-02-01", "1-1-24", "31-01-2024", "240131", "000229", "010229",
    "01/31/2024 10:00 AM", "01/31/2024 10:00 pm", "01/31/2024 12:00 am", "01/31/2024 13:00 PM", "01/31/2024 0:00 AM",
    "01/31/2024 00:00 AM", "01/31/2024 10:00  PM", "01/31/2024 10:00PM", "01/31/2024 10:00 a.m.",
    "2024-01-31 10:00:00 +0100", "2024-01-31 10:00:00+0100", "2024-01-31 10:00:00 +01:00", "2024-01-31 10:00:00+01:00",
    "2024-01-31 10:00:00 Z", "2024-01-31 10:00:00Z", "2024-01-31 10:00:00 z", "2024-01-31 10:00:00z",
    "2024-01-31 10:00:00 +01", "2024-01-31 10:00:00+01", "2024-01-31 10:00:00+01:00:30", "2024-01-31 10:00:00 +0160",
    "2024-01-31 10:00:00 UTC", "2024-01-31 10:00:00-0530", "2024-01-31 10:00:00 -05:30",
    "10:00", "9:5", "24:00", "09:60", "2024/01/31", "2024/1/5", "31.01.2024", "2024.1.5", "2024.01.31",
    "20240131100000", "20240131100060", "2024013110006", "20240131 100000", "2024-01", "2024-1", "2024-13",
    "31 01 2024", "31  01 2024", "31\t01 2024", "2024 01 31", "2024  01 31", "2024 1 5", "2024", "24", "-2024",
    "20245", "0000", "100% 2024", "100%% 2024", "abc", "2024-01-31\n", "5",
    "2024-01-31T 0:05:00", "2024-01-31T 10:05:00", "2024-01-31  0:05:00", "2024-01-31 10:05:0 ",
    "-202401", "000001", "20241", "2024-1", "-2024-01", "0000-01", "29-02-72", "29-02-00", "29-02-99",
    "720229", "990229",
]


@pytest.mark.parametrize("pattern", DATE_PATTERNS)
def test_date_fits_its_pattern_where_v1_says_so(pattern):
    # v1's own call is the answer key: a date fits when pandas reads it by the pattern.
    import pandas
    import polars

    from src.v2.components.transform.schema_compliance_check import date_fits

    def on_v1(value):
        read = pandas.to_datetime(pandas.Series([value], dtype=object), format=pattern, errors="coerce")
        return bool(read.notna()[0])

    found = polars.DataFrame({"v": DATE_VALUES}).select(date_fits(polars.col("v"), pattern)).to_series().to_list()
    wrong = [(value, "v1 takes it" if on_v1(value) else "v1 does not") for value, fits in zip(DATE_VALUES, found)
             if fits != on_v1(value)]
    assert wrong == []


def test_pattern_with_a_month_by_name_is_read_by_polars():
    import polars

    from src.v2.components.transform.schema_compliance_check import date_fits

    values = ["31 Jan 2024", "31 01 2024", "31 Foo 2024"]
    found = polars.DataFrame({"v": values}).select(date_fits(polars.col("v"), "%d %b %Y")).to_series().to_list()
    assert found == [True, False, False]


def test_digits_of_another_script_are_no_date():
    # v1 takes a year written in Arabic-Indic digits and no month written so.
    import polars

    from src.v2.components.transform.schema_compliance_check import date_fits

    values = ["\u0662\u0660\u0662\u0664-01-31", "2024-\u0660\u0661-31", "2024-01-31"]
    found = polars.DataFrame({"v": values}).select(date_fits(polars.col("v"), "%Y-%m-%d")).to_series().to_list()
    assert found == [False, False, True]


ONE = "id:str, v:str"


def one(check, values, schema=ONE, **config):
    """One checked column `v`, a row for each value, numbered from 1. Returns (job config, file)."""
    data = "id;v\n" + "".join(f"{at};{value}\n" for at, value in enumerate(values, start=1))
    return dict(schema=schema, checks=[{"name": "v", **check}], **config), data.encode("utf-8")


def turned_away(tmp_path, check, values, **config):
    kwargs, data = one(check, values, **config)
    kept, away = same(tmp_path, data, **kwargs)
    return {values[int(at) - 1]: said for at, said in away.items()}


@pytest.mark.parametrize("pattern, values, bad", [
    ("%Y-%m-%d", ["2024-01-31", "24-01-31", " 2024-01-31", "2024-1-5", "2024-02-30", "20240131"],
     ["24-01-31", " 2024-01-31", "2024-02-30", "20240131"]),
    ("yyyy-MM-dd", ["2024-01-31", "24-01-31", "2024-02-29", "2023-02-29"], ["24-01-31", "2023-02-29"]),
    ("yyyyMMdd", ["20240131", "240131", "2024-01-31"], ["2024-01-31"]),
    ("yyyy-MM-dd HH:mm:ss.SSS", ["2024-01-31 10:00:00.123", "2024-01-31 10:00:00", "2024-01-31 10:00:00."],
     ["2024-01-31 10:00:00"]),
    ("dd/MM/yyyy hh:mm a", ["31/01/2024 10:00 PM", "31/01/2024 13:00 PM", "31/01/2024 10:00"],
     ["31/01/2024 13:00 PM", "31/01/2024 10:00"]),
])
def test_date_is_held_to_its_pattern_as_v1_holds_it(tmp_path, pattern, values, bad):
    found = turned_away(tmp_path, {"type": "datetime", "date_pattern": pattern}, values, strict_date_check=True)
    assert found == {value: "v:invalid date format" for value in bad}


def test_date_pattern_is_held_to_whatever_type_the_column_arrives_as(tmp_path):
    # A whole number is no date by the pattern; a date that arrives as a date is one.
    check = {"type": "datetime", "date_pattern": "%Y-%m-%d"}
    assert turned_away(tmp_path, check, ["5", "20240131"], schema="id:str, v:int", strict_date_check=True) == {
        "5": "v:invalid date format", "20240131": "v:invalid date format"}
    assert turned_away(tmp_path / "b", check, ["2024-01-31"], schema="id:str, v:datetime@%Y-%m-%d",
                       strict_date_check=True) == {}


def test_date_that_arrives_as_a_date_is_not_held_to_the_pattern_of_the_check(tmp_path):
    check = {"type": "datetime", "date_pattern": "%Y-%m-%d"}
    assert turned_away(tmp_path, check, ["31/01/2024"], schema="id:str, v:datetime@%d/%m/%Y", strict_date_check=True) == {}


def test_pattern_that_is_no_pattern_refuses_the_job():
    # v1 fails when the rows arrive.
    kwargs, _ = one({"type": "datetime", "date_pattern": "%Q-%m"}, [], strict_date_check=True)
    with pytest.raises(JobRefusedError, match="date_pattern: '%Q-%m' is no pattern of a date: 'Q' is a bad directive"):
        load_job(checked(**kwargs))
    kwargs, _ = one({"type": "datetime", "date_pattern": "%Q-%m"}, [])
    load_job(checked(**kwargs))


def test_key_named_pattern_is_not_read_as_in_v1(tmp_path):
    check = {"type": "datetime", "pattern": "%Y-%m-%d"}
    assert turned_away(tmp_path, check, ["2024-01-31", "nope"], strict_date_check=True) == {}


def test_number_behind_a_blank_that_is_no_ascii_blank_is_no_number(tmp_path):
    values = ["5", " 5 ", "\u00a05", "5\u2003", "\t5"]
    assert turned_away(tmp_path, {"type": "int"}, values) == {"\u00a05": "v:invalid type", "5\u2003": "v:invalid type"}
    assert turned_away(tmp_path / "b", {"type": "float"}, ["1.5", "x", "1e3", "\u00a01.5"]) == {
        "x": "v:invalid type", "\u00a01.5": "v:invalid type"}


def test_length_is_of_the_text_a_typed_value_is_written_as(tmp_path):
    check = {"type": "str", "length": 3}
    # The same rows are turned away on both. (A reject file with no declared columns shows v2's ten places.)
    kwargs, data = one(check, ["5", "1.25", "100"], schema="id:str, v:Decimal")
    made = checked(**kwargs)
    ids = {}
    for engine, runner in (("v1", answer_key.run_v1), ("v2", answer_key.run_v2)):
        run = answer_key.run_job(made, {"in.csv": data}, tmp_path / engine, runner)
        assert run.succeeded, run.error
        ids[engine] = [[line.split(";")[0] for line in run.files[name].decode().splitlines()[1:]]
                       for name in ("out.csv", "rej.csv")]
    assert ids["v2"] == ids["v1"] == [["1", "3"], ["2"]]
    check = {"type": "str", "length": 10}
    assert turned_away(tmp_path / "b", check, ["2024-01-31", "2024-02-01"], schema="id:str, v:datetime") == {}
    assert turned_away(tmp_path / "c", check, ["2024-01-31 10:00:00"], schema="id:str, v:datetime") == {
        "2024-01-31 10:00:00": "v:exceed max length"}


def test_length_is_asked_of_text_columns_only_and_never_of_a_missing_value(tmp_path):
    assert turned_away(tmp_path, {"type": "int", "length": 2}, ["12345", ""]) == {}
    # Blanks alone are as good as missing: their number is not held against the length.
    assert turned_away(tmp_path / "b", {"type": "str", "length": 2, "nullable": True}, ["ab", "", "abc", "    "]) == {
        "abc": "v:exceed max length"}
    typed = turned_away(tmp_path / "c", {"type": "str", "length": 2}, ["12", "123"], schema="id:str, v:int")
    assert typed == {"123": "v:exceed max length"}


@pytest.mark.parametrize("charset", ["ISO-8859-15", "cp1252", "latin-1", "ascii"])
def test_length_in_bytes_of_a_one_byte_character_set(tmp_path, charset):
    values = ["ab", "abc", "a\u00e9"] if charset != "ascii" else ["ab", "abc"]
    found = turned_away(tmp_path, {"type": "str", "length": 2}, values, check_string_by_byte_length=True, charset=charset)
    assert found == {"abc": "v:exceed max length"}


def test_several_faults_of_a_row_are_joined_whichever_columns_they_are_in(tmp_path):
    schema = "a:str, b:str, c:str, d:str, e:str"
    checks = [{"name": name, "type": "int", "nullable": False} for name in "abcde"]
    data = b"a;b;c;d;e\nx;1;2;3;y\n1;2;3;4;\n;1;1;1;1\nx;;x;;x\n"
    made = checked(schema=schema, checks=checks)
    run = assert_matches_v1(made, {"in.csv": data}, tmp_path)
    assert [line.split(";8;")[1] for line in run.files["rej.csv"].decode().splitlines()[1:]] == [
        "a:invalid type;e:invalid type", "e:cannot be null", "a:cannot be null",
        "a:invalid type;b:cannot be null;c:invalid type;d:cannot be null;e:invalid type"]


def test_code_of_a_row_turned_away_is_a_whole_number_to_what_follows(tmp_path):
    made = checked()
    condition = {"column": "errorCode", "function": "", "operator": ">", "value": "7"}
    step = {"id": "codes", "type": "FilterRows", "config": {"conditions": [condition]}, "inputs": ["row3"],
            "outputs": ["row4"], "schema": {"input": [], "output": []}}
    made["components"][3:3] = [step]
    made["components"][-1]["inputs"] = ["row4"]
    made["flows"][-1] = flow("row3", "it", "codes", "reject")
    made["flows"].append(flow("row4", "codes", "rej"))
    result = v2(tmp_path, made)
    assert result.status == "success", result.error
    assert len((tmp_path / "rej.csv").read_text().splitlines()) == 7


def test_code_of_a_row_turned_away_can_be_reckoned_with(tmp_path):
    made = checked()
    step = {"id": "codes", "type": "Map", "inputs": ["row3"], "outputs": ["row4"],
            "config": {"inputs": {"main": {"name": "row3"}}, "outputs": [{"name": "row4", "columns": [
                {"name": "id", "expression": "row3.id"}, {"name": "next", "expression": "row3.errorCode + 1"}]}]},
            "schema": {"inputs": {"row3": []}}}
    made["components"][3:3] = [step]
    made["components"][-1]["inputs"] = ["row4"]
    made["flows"][-1] = flow("row3", "it", "codes", "reject")
    made["flows"].append(flow("row4", "codes", "rej"))
    result = v2(tmp_path, made)
    assert result.status == "success", result.error
    assert (tmp_path / "rej.csv").read_text().splitlines()[:2] == ["id;next", ";9"]


def test_missing_decimal_is_missing_whatever_empty_text_counts_as(tmp_path):
    # v1 holds a missing Decimal as empty text, and with `all_empty_are_null` off says it is of an invalid type.
    kwargs, data = one({"type": "Decimal", "nullable": True}, ["2.5", ""], schema="id:str, v:Decimal#2",
                       all_empty_are_null=False)
    result = v2(tmp_path, checked(**kwargs), data)
    assert result.status == "success" and (tmp_path / "out.csv").read_text() == "id;v\n1;2.50\n2;\n"
