"""Unite, against v1 on the same job config and bytes."""
import json
import os

import polars as pl
import pytest

from src.v2 import load_job, run_job
from src.v2.components.registry import Registry
from src.v2.components.transform.unite import Unite
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import REPO_ROOT, assert_matches_v1
from tests.v2.unit.kit import Peek, Rows

from .kit import columns, flow, job, reader, writer

SAMPLE = REPO_ROOT / "tests" / "talend_xml_samples" / "converted_jsons" / "Job_tUnite_0.1.json"

PLAIN = "id:int, name:str, amt:float"
HEAD = b"id;name;amt\n"
A, B, C = HEAD + b"1;a;1.5\n2;b;2.5\n", HEAD + b"3;c;3.5\n", HEAD + b"4;d;\n5;;5.0\n"


def united(schemas, out, inputs=None, type_name="Unite", written="same", config=None):
    """in1.csv, in2.csv, ... -> the unite -> out.csv.

    ``schemas`` are the schemas the files are read with, one per input. ``out`` is the unite's
    declared output schema, none when empty. ``written`` is the schema the writer declares:
    the unite's by default, None for none.
    """
    names = [f"row{number}" for number in range(1, len(schemas) + 1)]
    components = [
        reader(schema, component_id=f"in{number}", path=f"in{number}.csv", outputs=(name,), header_rows=1)
        for number, (name, schema) in enumerate(zip(names, schemas), start=1)
    ]
    components.append({
        "id": "it", "type": type_name, "config": config or {},
        "schema": {"input": columns(schemas[0]), "output": columns(out) if out else []},
        "inputs": list(names if inputs is None else inputs), "outputs": ["out1"],
    })
    components.append(writer((out if written == "same" else written) or None, inputs=("out1",)))
    wires = [flow(name, f"in{number}", "it") for number, name in enumerate(names, start=1)]
    return job(components, wires + [flow("out1", "it", "out")])


def files(*contents):
    return {f"in{number}.csv": data for number, data in enumerate(contents, start=1)}


def same(tmp_path, made, inputs, fails=False):
    """Both engines do the same with the job; ``fails`` says the job is one neither finishes."""
    run = assert_matches_v1(made, inputs, tmp_path)
    assert run.succeeded is not fails, run.error
    return run


def v2_run(tmp_path, made, inputs):
    """Run on v2 only, inside tmp_path."""
    for name, data in inputs.items():
        (tmp_path / name).write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def v2(tmp_path, made, inputs):
    """What out.csv holds after a run on v2 only."""
    result = v2_run(tmp_path, made, inputs)
    assert result.status == "success", result.error
    return (tmp_path / "out.csv").read_bytes()


def mixed(first_type, first_rows, second_type, second_rows, declared, written="same"):
    """Two inputs ``k, v`` whose ``v`` is of two types; ``declared`` is the unite's type for it, or None."""
    out = f"k:str, v:{declared}" if declared else ""
    made = united([f"k:str, v:{first_type}", f"k:str, v:{second_type}"], out, written=written)
    return made, files(b"k;v\n" + first_rows, b"k;v\n" + second_rows)


# ------------------------------------------------------------------
# Rows, and the order they come in
# ------------------------------------------------------------------

def test_inputs_follow_one_another(tmp_path):
    run = same(tmp_path, united([PLAIN, PLAIN], PLAIN), files(A, B))
    assert run.files["out.csv"] == HEAD + b"1;a;1.5\n2;b;2.5\n3;c;3.5\n"


def test_inputs_come_in_the_order_of_the_components_own_list(tmp_path):
    made = united([PLAIN, PLAIN, PLAIN], PLAIN, inputs=["row3", "row1", "row2"])
    run = same(tmp_path, made, files(A, B, C))
    assert run.files["out.csv"] == HEAD + b"4;d;\n5;;5.0\n1;a;1.5\n2;b;2.5\n3;c;3.5\n"


def test_any_number_of_inputs(tmp_path):
    contents = [HEAD + f"{number};n{number};{number}.5\n".encode() for number in range(6)]
    run = same(tmp_path, united([PLAIN] * 6, PLAIN), files(*contents))
    assert run.files["out.csv"].count(b"\n") == 7


def test_rows_found_twice_are_kept_twice(tmp_path):
    run = same(tmp_path, united([PLAIN, PLAIN], PLAIN), files(B + b"3;c;3.5\n", B))
    assert run.files["out.csv"] == HEAD + b"3;c;3.5\n" * 3


def test_one_input_passes_through(tmp_path):
    # v1 hands a single input over in another shape, and its Unite then drops every row.
    assert v2(tmp_path, united([PLAIN], PLAIN), files(A)) == A


@pytest.mark.parametrize("contents", [(A, HEAD), (HEAD, A), (HEAD, HEAD), (HEAD, A, HEAD, B)])
def test_inputs_without_rows(tmp_path, contents):
    run = same(tmp_path, united([PLAIN] * len(contents), PLAIN), files(*contents))
    assert run.files["out.csv"] == HEAD + b"".join(data[len(HEAD):] for data in contents)


def test_row_order_is_kept_on_many_rows(tmp_path):
    def part(first):
        numbers = range(first, first + 9000)
        return HEAD + b"".join(f"{number};n{number % 7};{number}.25\n".encode() for number in numbers)

    contents = [part(first) for first in (0, 20000, 40000, 60000)]
    same(tmp_path, united([PLAIN] * 4, PLAIN, inputs=["row2", "row4", "row1", "row3"]), files(*contents))


# ------------------------------------------------------------------
# Columns that differ in order or in name
# ------------------------------------------------------------------

SHUFFLED = "amt:float, id:int, name:str"


@pytest.mark.parametrize("out, header", [(PLAIN, b"id;name;amt"), (SHUFFLED, b"amt;id;name"), ("", b"id;name;amt")])
def test_columns_are_matched_by_name_not_by_position(tmp_path, out, header):
    run = same(tmp_path, united([PLAIN, SHUFFLED], out), files(A, b"amt;id;name\n9.5;9;z\n"))
    assert run.files["out.csv"].splitlines()[0] == header
    assert run.files["out.csv"].splitlines()[-1] == (b"9.5;9;z" if out == SHUFFLED else b"9;z;9.5")


@pytest.mark.parametrize("out", ["id:int, name:str, amt:float, extra:str", PLAIN, ""])
def test_column_an_input_does_not_have_is_left_empty_for_its_rows(tmp_path, out):
    made = united([PLAIN, "id:int, name:str, extra:str"], out, written=None)
    run = same(tmp_path, made, files(A, b"id;name;extra\n9;z;E\n"))
    assert run.files["out.csv"] == b"id;name;amt;extra\n1;a;1.5;\n2;b;2.5;\n9;z;;E\n"


def test_inputs_with_no_column_in_common(tmp_path):
    made = united(["a:int, b:str", "c:int, d:str"], "", written=None)
    run = same(tmp_path, made, files(b"a;b\n1;x\n", b"c;d\n2;y\n"))
    assert run.files["out.csv"] == b"a;b;c;d\n1;x;;\n;;2;y\n"


def test_names_differing_in_case_are_different_columns(tmp_path):
    made = united(["id:int, name:str", "ID:int, Name:str"], "", written=None)
    run = same(tmp_path, made, files(b"id;name\n1;x\n", b"ID;Name\n2;y\n"))
    assert run.files["out.csv"] == b"id;name;ID;Name\n1;x;;\n;;2;y\n"


TYPED = "k:str, s:str, i:int, f:float, d:datetime@%Y-%m-%d"
TYPED_ROW = b"k;s;i;f;d\na;x;1;1.5;2024-01-31\n"


@pytest.mark.parametrize("first", [True, False])
def test_missing_column_of_every_type(tmp_path, first):
    schemas, contents = [TYPED, "k:str"], [TYPED_ROW, b"k\nz\n"]
    if not first:
        schemas, contents = schemas[::-1], contents[::-1]
    run = same(tmp_path, united(schemas, TYPED), files(*contents))
    assert sorted(run.files["out.csv"].splitlines()[1:]) == [b"a;x;1;1.5;2024-01-31", b"z;;;;"]


def test_missing_column_of_every_type_when_the_schema_does_not_declare_it(tmp_path):
    schema = TYPED + ", b:bool, m:Decimal#2"
    made = united([schema, "k:str"], "k:str", written=None)
    run = same(tmp_path, made, files(b"k;s;i;f;d;b;m\na;x;1;1.5;2024-01-31;true;12.345\n", b"k\nz\n"))
    assert run.files["out.csv"] == b"k;s;i;f;d;b;m\na;x;1;1.5;2024-01-31 00:00:00;True;12.35\nz;;;;;;\n"


def test_missing_bool_decimal_and_whole_number_stay_what_they_are(tmp_path):
    # v1 writes true for the missing bool and <NA> for the missing Decimal, and turns the whole
    # numbers of a column that may not be missing into 5.0 once another input lacks the column.
    schema = "k:str, b:bool, m:Decimal#2, n:int!"
    made = united([schema, "k:str"], "k:str, b:bool, m:Decimal#2", written=None)
    out = v2(tmp_path, made, files(b"k;b;m;n\na;true;12.345;5\n", b"k\nz\n"))
    assert out == b"k;b;m;n\na;True;12.35;5\nz;;;\n"


def test_missing_value_where_none_is_allowed_fails_the_unite(tmp_path):
    made = united([PLAIN, "id:int, name:str"], "id:int, name:str, amt:float!")
    inputs = files(A, b"id;name\n9;z\n")
    same(tmp_path, made, inputs, fails=True)
    (tmp_path / "direct").mkdir()
    result = v2_run(tmp_path / "direct", made, inputs)
    assert result.failures == {"it": "Column 'amt' has NULL values but is not nullable"}


# ------------------------------------------------------------------
# Columns that differ in type
# ------------------------------------------------------------------

@pytest.mark.parametrize("declared", ["int", "float", "str", None])
def test_whole_number_meets_float(tmp_path, declared):
    made, inputs = mixed("int", b"a;1\nb;\n", "float", b"c;2.5\nd;3\n", declared)
    run = same(tmp_path, made, inputs)
    assert run.files["out.csv"].splitlines()[1] == (b"a;1" if declared == "int" else b"a;1.0")


@pytest.mark.parametrize(
    "first_type, first_rows, second_type, second_rows, declared",
    [
        ("int", b"a;1\nb;\n", "int!", b"c;7\n", "int"),
        ("int", b"a;1\nb;\n", "int!", b"c;7\n", None),
        ("int!", b"a;1\n", "float", b"c;2.5\nd;3\n", "float"),
        ("Decimal#2", b"a;1.5\nb;\n", "int", b"c;7\n", "Decimal#2"),
        ("int", b"c;7\n", "Decimal#2", b"a;1.5\nb;\n", "Decimal#2"),
        ("Decimal#2", b"a;1.5\n", "float", b"c;7.25\n", "Decimal#2"),
        ("Decimal#2", b"a;1.5\n", "float", b"c;7.25\n", "float"),
        ("Decimal#2", b"a;1.5\n", "Decimal#4", b"c;7.12345\n", "Decimal#2"),
        ("Decimal#2", b"a;1.5\n", "Decimal#4", b"c;7.12345\n", "Decimal#4"),
        ("Decimal#2", b"a;1.5\n", "Decimal#4", b"c;7.12345\n", "Decimal"),
        ("datetime@%Y-%m-%d", b"a;2024-01-31\n", "datetime@%d/%m/%Y %H:%M:%S", b"c;01/02/2024 10:11:12\n",
         "datetime@%Y-%m-%d %H:%M:%S"),
        ("datetime@%Y-%m-%d", b"a;2024-01-31\n", "datetime@%d/%m/%Y %H:%M:%S", b"c;01/02/2024 10:11:12\n", None),
    ],
)
def test_numbers_and_dates_of_different_types(tmp_path, first_type, first_rows, second_type, second_rows, declared):
    # A Decimal beside another number type is united as text, which the declared type then reads.
    made, inputs = mixed(first_type, first_rows, second_type, second_rows, declared)
    same(tmp_path, made, inputs)


def test_date_meets_date_time(tmp_path):
    # v1 has no date type.
    made, inputs = mixed("date@%Y-%m-%d", b"a;2024-01-31\n", "datetime@%Y-%m-%d %H:%M:%S",
                         b"c;2024-02-01 10:11:12\n", None)
    assert v2(tmp_path, made, inputs) == b"k;v\na;2024-01-31 00:00:00\nc;2024-02-01 10:11:12\n"


def test_column_of_no_type_takes_the_type_of_the_others():
    # A column of nothing but missing values that was never given a type: a component that computes can make one.
    registry = Registry()
    for cls in (Rows, Peek, Unite):
        registry.register(cls)
    Peek.seen.clear()
    made = {
        "job_name": "t",
        "components": [
            {"id": "in1", "type": "rows", "config": {"data": {"k": ["a"], "v": [None]}}},
            {"id": "in2", "type": "rows", "config": {"data": {"k": ["b"], "v": [7]}}},
            {"id": "in3", "type": "rows", "config": {"data": {"k": ["c"], "v": [1.5]}}},
            {"id": "it", "type": "unite", "config": {}, "inputs": ["row1", "row2", "row3"]},
            {"id": "seen", "type": "peek", "config": {}},
        ],
        "flows": [flow("row1", "in1", "it"), flow("row2", "in2", "it"), flow("row3", "in3", "it"),
                  flow("out1", "it", "seen")],
    }
    result = run_job(made, registry=registry)
    assert result.status == "success", result.error
    assert Peek.seen[0].schema["v"] == pl.Float64
    assert Peek.seen[0]["v"].to_list() == [None, 7.0, 1.5]


@pytest.mark.parametrize(
    "first_type, first_rows, second_type, second_rows",
    [
        ("int", b"a;1\nb;\n", "str", b"c;x\nd;\ne;7\n"),
        ("str", b"c;x\nd;\ne;7\n", "int", b"a;1\nb;\n"),
        ("float", b"a;1.5\nb;2\nb2;\n", "str", b"c;x\nd;7\n"),
        ("bool", b"a;true\nb;false\n", "str", b"c;x\nd;true\n"),
        ("datetime@%Y-%m-%d", b"a;2024-01-31\nb;\n", "str", b"c;2024-02-01\nd;x\n"),
        ("Decimal#2", b"a;1.5\nb;\n", "str", b"c;x\n"),
        ("Decimal#2", b"a;1.5\nb;\n", "int", b"c;7\n"),
        ("int", b"c;7\n", "Decimal#2", b"a;1.5\nb;\n"),
        ("Decimal#2", b"a;1.5\n", "float", b"c;7.25\nd;2\n"),
        ("Decimal#2", b"a;1.5\n", "Decimal#4", b"c;7.12345\n"),
        ("bool", b"a;true\nb;false\n", "int", b"c;5\nd;0\n"),
        ("datetime@%Y-%m-%d", b"a;2024-01-31\n", "int", b"c;5\n"),
    ],
)
@pytest.mark.parametrize("declared", ["str", None])
def test_other_types_meet_as_text(tmp_path, first_type, first_rows, second_type, second_rows, declared):
    made, inputs = mixed(first_type, first_rows, second_type, second_rows, declared)
    same(tmp_path, made, inputs)


@pytest.mark.parametrize(
    "first_type, first_rows, second_type, second_rows, declared, out",
    [
        ("int", b"a;1\nb;\n", "str", b"c;x\nd;\ne;7\n", "int", b"a;1\nb;\nc;\nd;\ne;7\n"),
        ("float", b"a;1.5\nb;2\n", "str", b"c;x\nd;7\n", "float", b"a;1.5\nb;2.0\nc;\nd;7.0\n"),
        ("datetime@%Y-%m-%d", b"a;2024-01-31\nb;\n", "str", b"c;2024-02-01\nd;x\n", "datetime@%Y-%m-%d",
         b"a;2024-01-31\nb;\nc;2024-02-01\nd;\n"),
    ],
)
def test_text_is_read_as_the_declared_type(tmp_path, first_type, first_rows, second_type, second_rows, declared, out):
    made, inputs = mixed(first_type, first_rows, second_type, second_rows, declared)
    run = same(tmp_path, made, inputs)
    assert run.files["out.csv"] == b"k;v\n" + out


# ------------------------------------------------------------------
# Names, the converter's sample, and what v2 says no to
# ------------------------------------------------------------------

def test_v1_type_name_tunite(tmp_path):
    same(tmp_path, united([PLAIN, PLAIN], PLAIN, type_name="tUnite"), files(A, B))


def test_v2_type_name(tmp_path):
    assert v2(tmp_path, united([PLAIN, PLAIN], PLAIN, type_name="unite"), files(A, B)) == A + B[len(HEAD):]


def sample_job():
    """The converter's sample, its log output replaced by a file."""
    with open(SAMPLE, encoding="utf-8") as handle:
        sample = json.load(handle)
    components = [component for component in sample["components"] if component["type"] != "LogRow"]
    for component in components:
        if component["type"] == "FileInputDelimited":
            component["config"]["filepath"] = "in" + component["id"][-1] + ".csv"
    components.append(writer(None, inputs=("row3",)))
    wires = [wire for wire in sample["flows"] if wire["to"] == "tUnite_1"] + [flow("row3", "tUnite_1", "out")]
    return dict(sample, components=components, flows=wires)


def test_converter_sample_loads():
    load_job(sample_job())


def test_converter_sample_runs_as_on_v1(tmp_path):
    head = b"id;name;department;salary\n"
    run = same(tmp_path, sample_job(), files(head + b"1;alice;Sales;100\n2;bob;Eng;200\n", head + b"3;chen;Ops;300\n"))
    assert run.files["out.csv"] == head + b"1;alice;Sales;100\n2;bob;Eng;200\n3;chen;Ops;300\n"


def test_keys_v1_reads_are_accepted():
    config = {"label": "Merge_All_Regions", "tstatcatcher_stats": False, "component_type": "Unite"}
    load_job(united([PLAIN, PLAIN], PLAIN, config=config))


def test_unknown_key_is_refused():
    with pytest.raises(JobRefusedError) as caught:
        load_job(united([PLAIN, PLAIN], PLAIN, config={"remove_duplicates": True}))
    assert "remove_duplicates" in caught.value.report.format()


def test_unite_needs_an_input():
    made = united([PLAIN], PLAIN)
    made["flows"] = [wire for wire in made["flows"] if wire["to"] != "it"]
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    assert "component it (Unite):\n  - inputs: needs 1 input(s), but 0 flows arrive" in caught.value.report.format()
