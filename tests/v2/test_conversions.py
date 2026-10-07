"""Conversions written in an expression: which rows they fail on, and what the failure says.

v1 works an expression out row by row, in Python. A conversion fails the
job there when Python reaches it on a row whose value cannot be converted,
and never on a row where an ``and``, an ``or`` or an ``if`` keeps Python
from reaching it. v2 has to fail on the same rows, and name the first.
"""
import pytest

from tests.v2.answer_key import assert_matches_v1

from .components.kit import columns, flow, writer
from .components.test_filter_rows import filter_job
from .components.test_map import config, lookup, mapping, out, same, v2

CODES = "id:int, code:str"
# Row 2 (line 3 of the file) holds a code that is no number; row 4 an empty one.
DATA = b"id;code\n1;10\n2;x320\n3;30\n4;\n5;7\n"
CLEAN = b"id;code\n1;10\n2;20\n3;30\n"


def one_column(expression, kind="int", **more):
    """A map of one input whose one computed column is ``n``."""
    made = mapping(config([out("o", [("id", "row1.id", "int"), ("n", expression, kind)])], **more),
                   {"row1": CODES}, {"o": f"id:int, n:{kind}"})
    for component in made["components"]:
        if component["id"] == "in_row1":
            component["schema"]["output"][0]["key"] = True
    return made


def lines_of(run, name="o.csv"):
    return run.files[name].decode().splitlines()


def neither_finishes(tmp_path, made, inputs):
    """Both engines fail the job."""
    run = assert_matches_v1(made, inputs, tmp_path)
    assert not run.succeeded


# ------------------------------------------------------------------
# Rows Python never reaches do not fail
# ------------------------------------------------------------------

@pytest.mark.parametrize("expression, want", [
    ("row1.code.isdigit() and int(row1.code) > 5", ["true", "false", "true", "false", "true"]),
    ("not row1.code.isdigit() or int(row1.code) > 5", ["true", "true", "true", "true", "true"]),
    ("row1.code != '' and row1.code.isdigit() and int(row1.code) > 9", ["true", "false", "true", "false", "false"]),
    ("row1.code == '' or not row1.code.isdigit() or int(row1.code) > 9", ["true", "true", "true", "true", "false"]),
    ("row1.code.isdigit() and float(row1.code) > 5.5", ["true", "false", "true", "false", "true"]),
])
def test_conversion_behind_an_and_or_an_or_is_worked_out_only_where_python_reaches_it(tmp_path, expression, want):
    run = same(tmp_path, one_column(expression, "bool"), {"row1.csv": DATA})
    assert [line.split(";")[1] for line in lines_of(run)[1:]] == want


@pytest.mark.parametrize("expression, want", [
    ("int(row1.code) if row1.code.isdigit() else -1", ["10", "-1", "30", "-1", "7"]),
    ("-1 if not row1.code.isdigit() else int(row1.code)", ["10", "-1", "30", "-1", "7"]),
    ("(int(row1.code) if row1.code.isdigit() else 0) + 1", ["11", "1", "31", "1", "8"]),
])
def test_conversion_in_a_branch_not_taken_does_not_fail(tmp_path, expression, want):
    run = same(tmp_path, one_column(expression), {"row1.csv": DATA})
    assert [line.split(";")[1] for line in lines_of(run)[1:]] == want


def test_conversion_guarded_in_an_output_filter(tmp_path):
    outputs = [out("o", [("id", "row1.id", "int")], filter="row1.code.isdigit() and int(row1.code) > 9",
                   activate_filter=True)]
    made = mapping(config(outputs), {"row1": CODES}, {"o": "id:int"})
    assert lines_of(same(tmp_path, made, {"row1.csv": DATA}))[1:] == ["1", "3"]


def filtered(tmp_path, condition):
    """Filter rows with an advanced condition, on v2 alone: v1 reads that condition as Java."""
    import os

    from src.v2 import run_job

    made = filter_job({"conditions": [], "use_advanced": True, "advanced_cond": condition}, schema=CODES, reject=False)
    (tmp_path / "in.csv").write_bytes(DATA)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def test_conversion_guarded_in_a_filter_rows_condition(tmp_path):
    result = filtered(tmp_path, "input_row.code.isdigit() and int(input_row.code) > 9")
    assert result.status == "success", result.error
    assert (tmp_path / "out.csv").read_text().splitlines()[1:] == ["1;10", "3;30"]


def test_conversion_in_a_filter_rows_condition_fails_with_its_place(tmp_path):
    result = filtered(tmp_path, "int(input_row.code) > 9")
    assert result.status == "failed" and result.failed_component == "it"
    assert result.error == ("condition: int() could not read 'x320' (in: int(input_row.code) > 9); 2 rows failed; "
                            "the row is line 3 of in.csv")


# ------------------------------------------------------------------
# Rows Python does reach fail the job, on both engines
# ------------------------------------------------------------------

@pytest.mark.parametrize("expression", [
    "int(row1.code)",
    "float(row1.code) * 2",
    "row1.id > 0 and int(row1.code) > 5",
    "int(row1.code) if row1.id > 1 else 0",
    "datetime.strptime(row1.code, '%Y%m%d').year",
])
def test_conversion_python_reaches_on_a_bad_value_fails_both_engines(tmp_path, expression):
    neither_finishes(tmp_path, one_column(expression, "str"), {"row1.csv": DATA})


def failure(tmp_path, made, data=DATA):
    result, files = v2(tmp_path, made, {"row1.csv": data})
    assert result.status == "failed" and files == {}
    return result


def test_failed_conversion_says_what_could_not_be_read_how_often_and_which_row(tmp_path):
    result = failure(tmp_path, one_column("int(row1.code) + 1"))
    assert result.failed_component == "map"
    assert result.error == ("outputs[0].columns[1].expression: int() could not read 'x320' (in: int(row1.code) + 1); "
                            "2 rows failed; the row is line 3 of row1.csv (id=2)")


def test_one_failed_row_is_said_as_one(tmp_path):
    result = failure(tmp_path, one_column("float(row1.code)", "float"), b"id;code\n1;1.5\n2;abc\n")
    assert result.error == ("outputs[0].columns[1].expression: float() could not read 'abc' (in: float(row1.code)); "
                            "1 row failed; the row is line 3 of row1.csv (id=2)")


def test_failed_date_conversion_is_named_too(tmp_path):
    result = failure(tmp_path, one_column("datetime.strptime(row1.code, '%Y%m%d').year"),
                     b"id;code\n1;20240131\n2;notadate\n")
    assert result.error.startswith("outputs[0].columns[1].expression: strptime() could not read 'notadate' (in: ")
    assert result.error.endswith("1 row failed; the row is line 3 of row1.csv (id=2)")


def test_value_shown_is_the_one_the_conversion_was_handed(tmp_path):
    # Not the cell as it stands in the file: what the expression made of it before converting.
    result = failure(tmp_path, one_column("int(row1.code[1:])"), b"id;code\n1;A10\n2;Ax20\n")
    assert "int() could not read 'x20' (in: int(row1.code[1:]))" in result.error
    assert result.error.endswith("the row is line 3 of row1.csv (id=2)")


def test_long_value_is_cut_in_the_message(tmp_path):
    result = failure(tmp_path, one_column("int(row1.code)"), b"id;code\n1;" + b"z" * 300 + b"\n")
    assert "could not read '" + "z" * 100 + "...'" in result.error


def test_missing_value_is_not_a_failed_conversion(tmp_path):
    # An operation on a missing value gives a missing value, here as everywhere in an expression.
    made = one_column("int(row1.code)")
    for component in made["components"]:
        if component["id"] == "in_row1":
            component["config"]["csv_option"] = False
    result, files = v2(tmp_path, made, {"row1.csv": CLEAN})
    assert result.status == "success", result.error


# ------------------------------------------------------------------
# Wherever a map works an expression out
# ------------------------------------------------------------------

def test_conversion_in_a_column_nothing_reads_fails_the_job_as_in_v1(tmp_path):
    # The writer takes every column, so the column is put out of reach by a second map that leaves it.
    first = config([out("mid", [("id", "row1.id", "int"), ("n", "int(row1.code)", "int")])])
    second = config([out("o", [("id", "mid.id", "int")])])
    second["inputs"]["main"]["name"] = "mid"
    made = mapping(first, {"row1": CODES}, {"mid": None})
    made["components"] = [c for c in made["components"] if c["id"] != "out_mid"]
    made["flows"] = [f for f in made["flows"] if f["to"] != "out_mid"]
    made["components"].append({"id": "map2", "type": "PyMap", "config": second,
                               "schema": {"inputs": {"mid": columns("id:int, n:int")}}, "inputs": ["mid"],
                               "outputs": ["o"]})
    made["components"].append(writer("id:int", component_id="out_o", path="o.csv", inputs=("o",)))
    made["flows"] += [flow("mid", "map", "map2"), flow("o", "map2", "out_o")]
    neither_finishes(tmp_path, made, {"row1.csv": DATA})


def test_conversion_in_a_variable_fails_with_its_place(tmp_path):
    made = one_column("Var.n + 1", variables=[("n", "int(row1.code)")])
    result = failure(tmp_path, made)
    assert result.error.startswith("variables[0].expression: int() could not read 'x320' (in: int(row1.code)); ")
    assert result.error.endswith("the row is line 3 of row1.csv (id=2)")


def test_conversion_in_an_output_filter_fails_with_its_place(tmp_path):
    outputs = [out("o", [("id", "row1.id", "int")], filter="int(row1.code) > 9", activate_filter=True)]
    made = mapping(config(outputs), {"row1": CODES}, {"o": "id:int"})
    result = failure(tmp_path, made)
    assert result.error.startswith("outputs[0].filter: int() could not read 'x320' (in: int(row1.code) > 9); ")


def test_conversion_in_a_lookup_key_fails_with_its_place(tmp_path):
    made = mapping(config([out("o", [("id", "row1.id", "int"), ("name", "names.name", "str")])],
                          lookups=[lookup("names", [("n", "int(row1.code)")])]),
                   {"row1": CODES, "names": "n:int, name:str"}, {"o": "id:int, name:str"})
    result, files = v2(tmp_path, made, {"row1.csv": DATA, "names.csv": b"n;name\n10;ten\n"})
    assert result.status == "failed"
    assert result.error.startswith("inputs.lookups[0].join_keys[0].expression: int() could not read 'x320' ")


def test_conversion_in_a_main_input_filter_fails_with_its_place(tmp_path):
    made = one_column("row1.id", main_filter="int(row1.code) > 9")
    result = failure(tmp_path, made)
    assert result.error.startswith("inputs.main.filter: int() could not read 'x320' (in: int(row1.code) > 9); ")
