"""Join, against v1 on the same job config and bytes."""
import datetime
import json
import os
import random

import polars as pl
import pytest

from src.v2 import load_job, run_job
from src.v2.components.registry import Registry
from src.v2.components.transform.join import Join
from src.v2.engine.context import RunContext
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import REPO_ROOT, assert_matches_v1
from tests.v2.unit.kit import Rows, Save

from .kit import columns, flow, job, reader, writer

SAMPLE = REPO_ROOT / "tests" / "talend_xml_samples" / "converted_jsons" / "Job_tJoin_0.1.json"
V1_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "jobs" / "transform" / "join_with_reject.json"

MAIN, LOOKUP = "id:int, name:str, dept:str", "dept:str, dname:str, loc:str"
WIDE = MAIN + ", dname:str, loc:str"
PEOPLE = b"id;name;dept\n1;alice;D1\n2;bob;D2\n3;carol;D9\n4;dave;\n5;erin;D1\n"
DEPTS = b"dept;dname;loc\nD1;Sales;NY\nD2;Eng;SF\nD1;Dup;XX\nD3;Ops;LA\n;Blank;ZZ\n"
FILES = {"main.csv": PEOPLE, "lookup.csv": DEPTS}
ON_DEPT = [{"input_column": "dept", "lookup_column": "dept"}]
FETCH = {
    "join_key": ON_DEPT,
    "use_lookup_cols": True,
    "lookup_cols": [{"output_column": "dname", "lookup_column": "dname"},
                    {"output_column": "loc", "lookup_column": "loc"}],
}


def joined(config, main=MAIN, lookup=LOOKUP, out=None, reject=None, inputs=None, flows=("row1", "row2"),
           type_name="Join", written="same"):
    """main.csv and lookup.csv -> the join -> out.csv, and its reject output -> rej.csv when asked.

    ``out`` is the join's declared output schema: the main input's when not given, none when
    empty. ``reject`` is True for a reject flow, or the declared reject schema. ``written`` is
    the schema the writer of out.csv declares: the join's by default, None for none.
    """
    out = main if out is None else out
    schema = {"input": columns(lookup), "output": columns(out) if out else []}
    if isinstance(reject, str):
        schema["reject"] = columns(reject)
    main_flow, lookup_flow = flows
    components = [
        reader(main, component_id="main_in", path="main.csv", outputs=(main_flow,), header_rows=1),
        reader(lookup, component_id="lookup_in", path="lookup.csv", outputs=(lookup_flow,), header_rows=1),
        {"id": "it", "type": type_name, "config": config, "schema": schema,
         "inputs": list(inputs or flows), "outputs": ["out1"]},
        writer((out if written == "same" else written) or None, inputs=("out1",)),
    ]
    wires = [flow(main_flow, "main_in", "it"), flow(lookup_flow, "lookup_in", "it"), flow("out1", "it", "out")]
    if reject:
        components[2]["outputs"].append("rej1")
        components.append(writer(None, component_id="rej", path="rej.csv", inputs=("rej1",)))
        wires.append(flow("rej1", "it", "rej", "reject"))
    return job(components, wires)


def keyed(main_type, lookup_type=None, **config):
    """A join of ``id, k`` with ``k, v`` on ``k`` that fetches ``v`` and has its reject wired."""
    made = {"join_key": [{"input_column": "k", "lookup_column": "k"}], "use_lookup_cols": True,
            "lookup_cols": [{"output_column": "v", "lookup_column": "v"}]}
    made.update(config)
    return joined(made, main=f"id:int, k:{main_type}", lookup=f"k:{lookup_type or main_type}, v:str",
                  out=f"id:int, k:{main_type}, v:str", reject=True)


def rows(main_rows, lookup_rows):
    """The files of a ``keyed`` join."""
    return {"main.csv": b"id;k\n" + main_rows, "lookup.csv": b"k;v\n" + lookup_rows}


def same(tmp_path, made, files=None, fails=False):
    """Both engines do the same with the job; ``fails`` says the job is one neither finishes."""
    run = assert_matches_v1(made, FILES if files is None else files, tmp_path)
    assert run.succeeded is not fails, run.error
    return run


def v2(tmp_path, made, files=None):
    """Run on v2 only, inside tmp_path."""
    for name, data in (FILES if files is None else files).items():
        (tmp_path / name).write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def refused(made):
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    return caught.value.report.format()


# ------------------------------------------------------------------
# Left and inner
# ------------------------------------------------------------------

def test_join_keeps_every_main_row_and_fetches_nothing_by_default(tmp_path):
    run = same(tmp_path, joined({"join_key": ON_DEPT}, reject=True))
    assert run.files["out.csv"] == PEOPLE
    assert run.files["rej.csv"] == b"id;name;dept\n3;carol;D9\n"


def test_left_join_fetches_lookup_columns_from_the_first_matching_row(tmp_path):
    run = same(tmp_path, joined(FETCH, out=WIDE))
    assert run.files["out.csv"] == (
        b"id;name;dept;dname;loc\n1;alice;D1;Sales;NY\n2;bob;D2;Eng;SF\n3;carol;D9;;\n"
        b"4;dave;;Blank;ZZ\n5;erin;D1;Sales;NY\n"
    )


def test_left_join_that_fetches_nothing_hands_the_main_input_on_untouched():
    spec = load_job(joined({"join_key": ON_DEPT}, reject=True)).components["it"]
    main = pl.LazyFrame({"id": [1], "name": ["alice"], "dept": ["D1"]})
    lookup = pl.LazyFrame({"dept": ["D1"], "dname": ["Sales"], "loc": ["NY"]})
    built = Join(spec, spec.config, RunContext("t", {})).build({"row1": main, "row2": lookup})
    assert built["main"] is main
    assert "JOIN" in built["reject"].explain()


@pytest.mark.parametrize("inner", [False, True])
def test_use_inner_join(tmp_path, inner):
    run = same(tmp_path, joined(dict(FETCH, use_inner_join=inner), out=WIDE))
    assert (b"carol" in run.files["out.csv"]) is not inner


@pytest.mark.parametrize("inner", [False, True])
def test_rows_with_no_match_leave_by_reject_whatever_the_join(tmp_path, inner):
    run = same(tmp_path, joined(dict(FETCH, use_inner_join=inner), out=WIDE, reject=True))
    assert run.files["rej.csv"] == b"id;name;dept\n3;carol;D9\n"


def test_inner_join_without_lookup_columns_only_filters(tmp_path):
    same(tmp_path, joined({"join_key": ON_DEPT, "use_inner_join": True}, reject=True))


# ------------------------------------------------------------------
# Keys
# ------------------------------------------------------------------

def test_several_key_pairs_and_other_names_on_the_lookup(tmp_path):
    config = {
        "join_key": [{"input_column": "a", "lookup_column": "x"}, {"input_column": "b", "lookup_column": "y"}],
        "use_lookup_cols": True, "lookup_cols": [{"output_column": "v", "lookup_column": "v"}],
    }
    made = joined(config, main="id:int, a:str, b:int", lookup="x:str, y:int, v:str", out="id:int, a:str, b:int, v:str",
                  reject=True)
    files = {"main.csv": b"id;a;b\n1;p;1\n2;p;2\n3;q;1\n4;q;2\n5;p;1\n",
             "lookup.csv": b"x;y;v\np;1;P1\nq;2;Q2\np;1;DUP\n"}
    run = same(tmp_path, made, files)
    assert run.files["out.csv"] == b"id;a;b;v\n1;p;1;P1\n2;p;2;\n3;q;1;\n4;q;2;Q2\n5;p;1;P1\n"


def test_rows_never_multiply_and_main_rows_sharing_a_key_all_match(tmp_path):
    files = rows(b"1;a\n2;a\n3;b\n4;a\n5;zz\n", b"a;first\nb;only\na;second\na;third\n")
    run = same(tmp_path, keyed("str", use_inner_join=True), files)
    assert run.files["out.csv"] == b"id;k;v\n1;a;first\n2;a;first\n3;b;only\n4;a;first\n"


def test_text_keys_match_exactly_and_empty_text_is_a_value(tmp_path):
    files = rows(b"1; a\n2;a \n3;A\n4;a\n5;\n", b"a;plain\n;empty\n")
    run = same(tmp_path, keyed("str"), files)
    assert run.files["rej.csv"] == b"id;k\n1; a\n2;a \n3;A\n"


@pytest.mark.parametrize(
    "kind, main_rows, lookup_rows",
    [
        ("int", b"1;10\n2;20\n3;30\n4;10\n5;-7\n", b"10;a\n20;b\n10;dup\n-7;neg\n"),
        ("int!", b"1;10\n2;20\n3;30\n4;10\n", b"10;a\n20;b\n10;dup\n"),
        ("float", b"1;1.5\n2;2.5\n3;3.5\n4;-0.0\n5;1e3\n", b"1.5;a\n2.50;b\n0;zero\n1000;big\n"),
        ("datetime@%Y-%m-%d", b"1;2024-01-01\n2;2024-01-03\n3;1999-12-31\n",
         b"2024-01-01;a\n2024-01-02;n\n1999-12-31;old\n"),
        ("Decimal#2", b"1;10.5\n2;20\n3;30.25\n", b"10.50;a\n20.00;b\n"),
        ("bool", b"1;true\n2;false\n3;true\n", b"true;a\n"),
    ],
)
def test_keys_of_every_type(tmp_path, kind, main_rows, lookup_rows):
    run = same(tmp_path, keyed(kind), rows(main_rows, lookup_rows))
    assert run.files["out.csv"].splitlines()[1].endswith(b";a")
    assert run.files["rej.csv"].count(b"\n") == 2


@pytest.mark.parametrize(
    "main_type, lookup_type, main_rows, lookup_rows",
    [
        ("int", "float", b"1;10\n2;20\n3;30\n", b"10;a\n20.0;b\n30.5;c\n"),
        ("int!", "float", b"1;10\n2;20\n3;30\n", b"10;a\n20.0;b\n30.5;c\n"),
        ("float", "int", b"1;10\n2;20.0\n3;30.5\n", b"10;a\n20;b\n"),
        ("float", "int!", b"1;10\n2;20.0\n3;30.5\n", b"10;a\n20;b\n"),
        ("Decimal#2", "int", b"1;10\n2;20.5\n", b"10;a\n20;b\n"),
        ("int", "Decimal#2", b"1;10\n2;20\n", b"10.00;a\n20.50;b\n"),
        ("float", "Decimal#2", b"1;1.5\n2;0.25\n3;2\n4;7.75\n", b"1.50;a\n0.25;b\n2;c\n"),
        ("Decimal#2", "float", b"1;1.5\n2;0.25\n3;2\n4;7.75\n", b"1.50;a\n0.25;b\n2;c\n"),
        ("Decimal#2", "Decimal#4", b"1;1.5\n2;0.25\n", b"1.5000;a\n0.2501;b\n"),
        ("bool", "int", b"1;true\n2;false\n", b"1;one\n5;five\n"),
        ("int", "bool", b"1;1\n2;0\n3;5\n", b"true;yes\n"),
    ],
)
def test_number_keys_of_different_types_compare_as_numbers(tmp_path, main_type, lookup_type, main_rows, lookup_rows):
    run = same(tmp_path, keyed(main_type, lookup_type), rows(main_rows, lookup_rows))
    assert run.files["out.csv"].splitlines()[1].endswith(lookup_rows.split(b"\n")[0].split(b";")[1])


@pytest.mark.parametrize(
    "kind, held, other",
    [("float", b"1.5", b"2.5"), ("datetime@%Y-%m-%d", b"2024-01-01", b"2024-01-03")],
)
def test_missing_key_never_matches_a_missing_key(tmp_path, kind, held, other):
    files = rows(b"1;" + held + b"\n2;\n3;" + other + b"\n", held + b";a\n;n\n")
    run = same(tmp_path, keyed(kind, use_inner_join=True), files)
    assert run.files["out.csv"].count(b"\n") == 2
    assert run.files["rej.csv"].count(b"\n") == 3
    # A left join keeps the row, and rejects it too.
    left = joined({"join_key": [{"input_column": "k", "lookup_column": "k"}]}, main=f"id:int, k:{kind}",
                  lookup=f"k:{kind}, v:str", reject=True)
    assert same(tmp_path / "left", left, files).files["rej.csv"].count(b"\n") == 3


def test_missing_text_key_never_matches_but_empty_text_does(tmp_path):
    # The second join's key is fetched by the first: missing where the first found no match.
    def fetch(name):
        return [{"output_column": name, "lookup_column": name}]

    components = [
        reader("id:int, a:str", component_id="main_in", path="main.csv", outputs=("row1",), header_rows=1),
        reader("a:str, code:str", component_id="codes_in", path="codes.csv", outputs=("row2",), header_rows=1),
        reader("code:str, v:str", component_id="lookup_in", path="lookup.csv", outputs=("row3",), header_rows=1),
        {"id": "first", "type": "Join",
         "config": {"join_key": [{"input_column": "a", "lookup_column": "a"}], "use_lookup_cols": True,
                    "lookup_cols": fetch("code")},
         "schema": {"input": [], "output": columns("id:int, a:str, code:str")},
         "inputs": ["row1", "row2"], "outputs": ["mid"]},
        {"id": "it", "type": "Join",
         "config": {"join_key": [{"input_column": "code", "lookup_column": "code"}], "use_lookup_cols": True,
                    "lookup_cols": fetch("v")},
         "schema": {"input": [], "output": columns("id:int, a:str, code:str, v:str")},
         "inputs": ["mid", "row3"], "outputs": ["out1", "rej1"]},
        writer("id:int, a:str, code:str, v:str", inputs=("out1",)),
        writer(None, component_id="rej", path="rej.csv", inputs=("rej1",)),
    ]
    wires = [flow("row1", "main_in", "first"), flow("row2", "codes_in", "first"), flow("mid", "first", "it"),
             flow("row3", "lookup_in", "it"), flow("out1", "it", "out"), flow("rej1", "it", "rej", "reject")]
    files = {"main.csv": b"id;a\n1;x\n2;y\n3;z\n", "codes.csv": b"a;code\nx;C1\nz;\n",
             "lookup.csv": b"code;v\nC1;one\n;empty\n"}
    run = same(tmp_path, job(components, wires), files)
    assert run.files["out.csv"] == b"id;a;code;v\n1;x;C1;one\n2;y;;\n3;z;;empty\n"
    assert run.files["rej.csv"] == b"id;a;code\n2;y;\n"


@pytest.mark.parametrize(
    "kind, main_rows, lookup_rows",
    [
        ("int", b"1;10\n2;\n3;30\n", b"10;a\n;n\n"),    # v1 fails: it cannot hold its marker in a whole-number column
        ("int", b"1;10\n2;\n3;30\n", b"10;a\n20;b\n"),
        ("float", b"1;10\n2;\n3;30\n", b"10;a\n20;b\n"),  # v1 fails: a missing key on one side only
        ("float", b"1;10\n2;\n3;30\n", b"10;a\n;n\n"),   # v1 hands row 2 the lookup's 'n' and rejects it as well
    ],
)
def test_missing_key_fetches_nothing(tmp_path, kind, main_rows, lookup_rows):
    result = v2(tmp_path, keyed(kind), rows(main_rows, lookup_rows))
    assert result.status == "success", result.error
    assert (tmp_path / "out.csv").read_bytes().splitlines()[1:] == [
        b"1;10.0;a" if kind == "float" else b"1;10;a", b"2;;", b"3;30.0;" if kind == "float" else b"3;30;",
    ]
    assert (tmp_path / "rej.csv").read_bytes().count(b"\n") == 3


def test_date_and_date_time_keys_compare_as_date_times(tmp_path):
    # v1 has no date type.
    files = rows(b"1;2024-01-01\n2;2024-01-02\n3;2024-01-03\n",
                 b"2024-01-01 00:00:00;a\n2024-01-02 10:00:00;b\n2024-01-03 00:00:00;c\n")
    result = v2(tmp_path, keyed("date@%Y-%m-%d", "datetime@%Y-%m-%d %H:%M:%S"), files)
    assert result.status == "success", result.error
    assert (tmp_path / "out.csv").read_bytes() == b"id;k;v\n1;2024-01-01;a\n2;2024-01-02;\n3;2024-01-03;c\n"


def held(tmp_path, main, lookup):
    """Join two sets of rows held in the job config on ``k``, fetching ``v``; returns what was written."""
    registry = Registry()
    for cls in (Rows, Save, Join):
        registry.register(cls)
    made = {
        "job_name": "t",
        "components": [
            {"id": "main_in", "type": "rows", "config": {"data": main}},
            {"id": "lookup_in", "type": "rows", "config": {"data": lookup}},
            {"id": "it", "type": "join", "inputs": ["row1", "row2"],
             "config": {"join_key": [{"input_column": "k", "lookup_column": "k"}], "use_lookup_cols": True,
                        "lookup_cols": [{"lookup_column": "v"}]}},
            {"id": "out", "type": "save", "config": {"path": str(tmp_path / "out.csv")}},
            {"id": "rej", "type": "save", "config": {"path": str(tmp_path / "rej.csv")}},
        ],
        "flows": [flow("row1", "main_in", "it"), flow("row2", "lookup_in", "it"), flow("out1", "it", "out"),
                  flow("rej1", "it", "rej", "reject")],
    }
    result = run_job(made, registry=registry)
    assert result.status == "success", result.error
    return (tmp_path / "out.csv").read_text().splitlines(), (tmp_path / "rej.csv").read_text().splitlines()


def test_float_key_that_is_not_a_number_is_a_missing_key(tmp_path):
    # No file holds such a value, but a component that computes can hand one on.
    nan = float("nan")
    out, rej = held(tmp_path, {"id": [1, 2, 3], "k": [1.5, nan, 2.5]}, {"k": [nan, 1.5], "v": ["n", "a"]})
    assert out == ["id,k,v", "1,1.5,a", "2,NaN,", "3,2.5,"]
    assert rej == ["id,k", "2,NaN", "3,2.5"]


def test_keys_of_one_type_compare_whatever_the_type(tmp_path):
    # A time of day is a type no schema can declare, but a component that computes can hand one on.
    noon, one = datetime.time(12, 0), datetime.time(13, 0)
    out, rej = held(tmp_path, {"id": [1, 2], "k": [noon, one]}, {"k": [one], "v": ["a"]})
    assert [line.split(",")[::2] for line in out] == [["id", "v"], ["1", ""], ["2", "a"]]
    assert len(rej) == 2


@pytest.mark.parametrize(
    "main_type, lookup_type, key",
    [("int", "str", b"10"), ("str", "int", b"10"), ("datetime@%Y-%m-%d", "str", b"2024-01-01")],
)
def test_keys_that_cannot_be_compared_stop_the_job(tmp_path, main_type, lookup_type, key):
    # v1 fails when it runs; v2 refuses the job when it loads.
    made = keyed(main_type, lookup_type)
    same(tmp_path, made, rows(b"1;" + key + b"\n", key + b";a\n"), fails=True)
    assert "cannot be compared" in refused(made)


@pytest.mark.parametrize("main_type, lookup_type", [("bool", "str"), ("datetime@%Y-%m-%d", "int"), ("str", "float")])
def test_keys_that_cannot_be_compared_are_refused(main_type, lookup_type):
    said = refused(keyed(main_type, lookup_type))
    assert "join_key" in said and "'k'" in said and "cannot be compared" in said


# ------------------------------------------------------------------
# Lookup columns
# ------------------------------------------------------------------

CLASH_MAIN, CLASH_LOOKUP = "id:int, name:str, dept:str", "dept_id:str, name:str, loc:str, id:int"
CLASH_FILES = {
    "main.csv": b"id;name;dept\n1;alice;D1\n2;bob;D2\n3;carol;D9\n",
    "lookup.csv": b"dept_id;name;loc;id\nD1;Sales;NY;100\nD2;Eng;SF;200\n",
}


def fetching(lookup_cols, out, **more):
    config = {"join_key": [{"input_column": "dept", "lookup_column": "dept_id"}], "use_lookup_cols": True,
              "lookup_cols": lookup_cols}
    return joined(config, main=CLASH_MAIN, lookup=CLASH_LOOKUP, out=out, **more)


def test_lookup_column_takes_the_output_name(tmp_path):
    made = fetching([{"output_column": "location", "lookup_column": "loc"}], CLASH_MAIN + ", location:str")
    run = same(tmp_path, made, CLASH_FILES)
    assert run.files["out.csv"] == b"id;name;dept;location\n1;alice;D1;NY\n2;bob;D2;SF\n3;carol;D9;\n"


@pytest.mark.parametrize("entry", [{"output_column": "", "lookup_column": "loc"}, {"lookup_column": "loc"},
                                   {"output_column": "loc", "lookup_column": "loc"}])
def test_lookup_column_keeps_its_name_when_no_other_is_given(tmp_path, entry):
    run = same(tmp_path, fetching([entry], CLASH_MAIN + ", loc:str"), CLASH_FILES)
    assert run.files["out.csv"].splitlines()[1] == b"1;alice;D1;NY"


def test_fetched_columns_follow_the_main_columns_in_the_order_they_are_listed(tmp_path):
    made = joined(dict(FETCH, lookup_cols=list(reversed(FETCH["lookup_cols"]))), out="", written=None)
    run = same(tmp_path, made)
    assert run.files["out.csv"].splitlines()[0] == b"id;name;dept;loc;dname"


@pytest.mark.parametrize("output", ["name", "dname"])
def test_lookup_column_named_like_a_main_column_is_not_fetched(tmp_path, output):
    out = CLASH_MAIN + (", dname:str" if output == "dname" else "")
    run = same(tmp_path, fetching([{"output_column": output, "lookup_column": "name"}], out), CLASH_FILES)
    assert run.files["out.csv"].splitlines()[1] == (b"1;alice;D1;" if output == "dname" else b"1;alice;D1")


def test_entry_that_fetches_nothing_is_logged(caplog):
    lookup_cols = [{"output_column": "dname", "lookup_column": "name"}, {"output_column": "x", "lookup_column": "nope"}]
    with caplog.at_level("WARNING", logger="src.v2.components.transform.join"):
        load_job(fetching(lookup_cols, CLASH_MAIN + ", dname:str, x:str"))
    assert "[it] lookup_cols: nothing is fetched for 'name': " in caplog.text and "'name_lookup'" in caplog.text
    assert "[it] lookup_cols: nothing is fetched for 'nope': " in caplog.text
    assert caplog.text.isascii()


def test_lookup_column_named_like_a_main_column_is_fetched_as_name_lookup(tmp_path):
    lookup_cols = [{"output_column": "dname", "lookup_column": "name_lookup"},
                   {"output_column": "id_lookup", "lookup_column": "id_lookup"}]
    run = same(tmp_path, fetching(lookup_cols, CLASH_MAIN + ", dname:str, id_lookup:int"), CLASH_FILES)
    assert run.files["out.csv"] == (
        b"id;name;dept;dname;id_lookup\n1;alice;D1;Sales;100\n2;bob;D2;Eng;200\n3;carol;D9;;\n"
    )


def test_lookup_column_really_named_name_lookup_comes_first(tmp_path):
    # v1 fails on a lookup that has both 'name' and 'name_lookup' beside a main input with 'name'.
    files = {"main.csv": CLASH_FILES["main.csv"], "lookup.csv": b"dept_id;name;name_lookup\nD1;Sales;REAL\n"}
    made = joined({"join_key": [{"input_column": "dept", "lookup_column": "dept_id"}], "use_lookup_cols": True,
                   "lookup_cols": [{"output_column": "got", "lookup_column": "name_lookup"}]},
                  main=CLASH_MAIN, lookup="dept_id:str, name:str, name_lookup:str", out=CLASH_MAIN + ", got:str")
    result = v2(tmp_path, made, files)
    assert result.status == "success", result.error
    assert (tmp_path / "out.csv").read_bytes().splitlines()[1] == b"1;alice;D1;REAL"


@pytest.mark.parametrize("output", ["dept_id", "did"])
def test_lookup_key_of_another_name_can_be_fetched(tmp_path, output):
    made = fetching([{"output_column": output, "lookup_column": "dept_id"}], CLASH_MAIN + f", {output}:str")
    run = same(tmp_path, made, CLASH_FILES)
    assert run.files["out.csv"].splitlines()[1:] == [b"1;alice;D1;D1", b"2;bob;D2;D2", b"3;carol;D9;"]


@pytest.mark.parametrize("asked", ["dept", "dept_lookup"])
def test_lookup_key_of_the_same_name_is_the_main_column(tmp_path, asked):
    lookup_cols = [{"output_column": "d2", "lookup_column": asked}, {"output_column": "loc", "lookup_column": "loc"}]
    run = same(tmp_path, joined(dict(FETCH, lookup_cols=lookup_cols), out=MAIN + ", d2:str, loc:str"))
    assert run.files["out.csv"].splitlines()[1] == b"1;alice;D1;;NY"


@pytest.mark.parametrize("entry", [{"output_column": "nope", "lookup_column": "nope"}, {"output_column": "nope"}])
def test_entry_naming_no_lookup_column_fetches_nothing(tmp_path, entry):
    run = same(tmp_path, fetching([entry], CLASH_MAIN + ", nope:str"), CLASH_FILES)
    assert run.files["out.csv"].splitlines()[1] == b"1;alice;D1;"


def test_lookup_column_is_fetched_once(tmp_path):
    lookup_cols = [{"output_column": "a", "lookup_column": "loc"}, {"output_column": "b", "lookup_column": "loc"}]
    run = same(tmp_path, fetching(lookup_cols, CLASH_MAIN + ", a:str, b:str"), CLASH_FILES)
    assert run.files["out.csv"].splitlines()[1] == b"1;alice;D1;NY;"


@pytest.mark.parametrize(
    "config",
    [
        {"use_lookup_cols": True, "lookup_cols": []},
        {"use_lookup_cols": True},
        {"use_lookup_cols": False, "lookup_cols": FETCH["lookup_cols"]},
        {"lookup_cols": FETCH["lookup_cols"]},
    ],
)
def test_nothing_is_fetched_unless_asked_and_listed(tmp_path, config):
    run = same(tmp_path, joined(dict(config, join_key=ON_DEPT), out=WIDE))
    assert run.files["out.csv"].splitlines()[1] == b"1;alice;D1;;"


TYPED_LOOKUP = "k:str, s:str, i:int, n:int!, f:float, d:datetime@%Y-%m-%d, b:bool, m:Decimal#2"
TYPED_ROWS = {
    "main.csv": b"id;k\n1;a\n2;b\n3;zz\n",
    "lookup.csv": b"k;s;i;n;f;d;b;m\na;x;1;5;1.5;2024-01-31;true;12.345\nb;y;;6;;;false;\n",
}


def typed(names, out, **more):
    config = {"join_key": [{"input_column": "k", "lookup_column": "k"}], "use_lookup_cols": True,
              "lookup_cols": [{"output_column": name, "lookup_column": name} for name in names]}
    config.update(more.pop("config", {}))
    return joined(config, main="id:int, k:str", lookup=TYPED_LOOKUP, out=out, **more)


def test_fetched_columns_keep_their_types(tmp_path):
    made = typed("sinfd", "id:int, k:str, s:str, i:int, n:int, f:float, d:datetime@%Y-%m-%d")
    run = same(tmp_path, made, TYPED_ROWS)
    assert run.files["out.csv"] == b"id;k;s;i;n;f;d\n1;a;x;1;5;1.5;2024-01-31\n2;b;y;;6;;\n3;zz;;;;;\n"


def test_fetched_bool_and_decimal_columns_when_every_row_matches(tmp_path):
    made = typed("bm", "id:int, k:str, b:bool, m:Decimal#2", config={"use_inner_join": True})
    run = same(tmp_path, made, TYPED_ROWS)
    assert run.files["out.csv"] == b"id;k;b;m\n1;a;true;12.35\n2;b;false;\n"


def test_fetched_columns_the_schema_does_not_declare(tmp_path):
    same(tmp_path, typed("sifdbm", "", written=None, config={"use_inner_join": True}), TYPED_ROWS)


def test_row_with_no_match_has_no_value_in_any_fetched_column(tmp_path):
    # v1 writes true for the bool and <NA> for the Decimal of the row with no match, and turns the
    # whole number column the schema does not declare into 5.0 and 6.0.
    result = v2(tmp_path, typed("bmn", "id:int, k:str, b:bool, m:Decimal#2", written=None), TYPED_ROWS)
    assert result.status == "success", result.error
    assert (tmp_path / "out.csv").read_bytes() == b"id;k;b;m;n\n1;a;True;12.35;5\n2;b;False;;6\n3;zz;;;\n"


@pytest.mark.parametrize(
    "lookup_cols, taken",
    [
        ([{"output_column": "name", "lookup_column": "loc"}], "name"),
        ([{"output_column": "z", "lookup_column": "loc"}, {"output_column": "z", "lookup_column": "dept_id"}], "z"),
    ],
)
def test_output_name_already_taken_is_refused(lookup_cols, taken):
    # v1 goes on with two columns of one name.
    said = refused(fetching(lookup_cols, CLASH_MAIN))
    assert "lookup_cols" in said and f"'{taken}'" in said


# ------------------------------------------------------------------
# Reject
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "reject_schema, header, first",
    [
        (MAIN + ", errorCode:str, errorMessage:str", b"id;name;dept;errorCode;errorMessage",
         b"3;carol;D9;JOIN_REJECT;No matching lookup row"),
        (WIDE, b"id;name;dept;dname;loc", b"3;carol;D9;;"),
        ("name:str, errorMessage:str, id:int", b"name;errorMessage;id", b"carol;No matching lookup row;3"),
        ("id:int, errorCode:str, extra:int", b"id;errorCode;extra", b"3;JOIN_REJECT;"),
    ],
)
def test_reject_schema_decides_the_reject_columns(tmp_path, reject_schema, header, first):
    run = same(tmp_path, joined(FETCH, out=WIDE, reject=reject_schema))
    assert run.files["rej.csv"].splitlines() == [header, first]


def test_reject_schema_that_names_no_main_column_still_has_a_row_for_each_rejected_one(tmp_path):
    made = joined(FETCH, out=WIDE, reject="x:int, y:str")
    run = same(tmp_path, made, {"main.csv": PEOPLE + b"6;fay;D7\n", "lookup.csv": DEPTS})
    assert run.files["rej.csv"] == b"x;y\n;\n;\n"
    # v1 stalls when nothing is rejected.
    (tmp_path / "none").mkdir()
    result = v2(tmp_path / "none", made, {"main.csv": b"id;name;dept\n1;alice;D1\n2;bob;D2\n", "lookup.csv": DEPTS})
    assert result.status == "success", result.error
    assert (tmp_path / "none" / "rej.csv").read_bytes() == b"x;y\n"


def test_reject_holds_every_row_when_the_lookup_is_empty(tmp_path):
    run = same(tmp_path, joined(FETCH, out=WIDE, reject=True), {"main.csv": PEOPLE, "lookup.csv": b"dept;dname;loc\n"})
    assert run.files["rej.csv"] == PEOPLE


@pytest.mark.parametrize(
    "reject_schema, header",
    [(True, b"id;name;dept\n"), (MAIN + ", errorCode:str, errorMessage:str", b"id;name;dept;errorCode;errorMessage\n")],
)
def test_wired_reject_with_nothing_rejected_writes_an_empty_file(tmp_path, reject_schema, header):
    # v1 stalls here (status "error") because the reject flow got nothing.
    files = {"main.csv": b"id;name;dept\n1;alice;D1\n", "lookup.csv": DEPTS}
    result = v2(tmp_path, joined(FETCH, out=WIDE, reject=reject_schema), files)
    assert result.status == "success", result.error
    assert (tmp_path / "rej.csv").read_bytes() == header
    assert (tmp_path / "out.csv").read_bytes() == b"id;name;dept;dname;loc\n1;alice;D1;Sales;NY\n"


def test_no_main_rows(tmp_path):
    run = same(tmp_path, joined(FETCH, out=WIDE), {"main.csv": b"id;name;dept\n", "lookup.csv": DEPTS})
    assert run.files["out.csv"] == b"id;name;dept;dname;loc\n"


# ------------------------------------------------------------------
# The declared output schema
# ------------------------------------------------------------------

STRICT = MAIN + ", dname:str!, loc:str"


def test_missing_lookup_value_where_none_is_allowed_fails_the_join(tmp_path):
    same(tmp_path, joined(FETCH, out=STRICT, reject=True), fails=True)
    (tmp_path / "direct").mkdir()
    result = v2(tmp_path / "direct", joined(FETCH, out=STRICT, reject=True))
    assert result.status == "failed" and result.failed_component == "it"
    assert result.error == "Column 'dname' has NULL values but is not nullable"
    assert not (tmp_path / "direct" / "out.csv").exists()


@pytest.mark.parametrize("die_on_error", [True, False])
def test_die_on_error(tmp_path, die_on_error):
    made = joined(dict(FETCH, die_on_error=die_on_error), out=STRICT, reject=True)
    run = same(tmp_path, made, fails=die_on_error)
    if die_on_error:
        (tmp_path / "direct").mkdir()
        assert v2(tmp_path / "direct", made).failures == {"it": "Column 'dname' has NULL values but is not nullable"}
    else:
        assert run.files["rej.csv"].splitlines() == [
            b"id;name;dept;dname;loc;errorCode;errorMessage",
            b"3;carol;D9;;;;",
            b"3;carol;D9;;;SCHEMA_VIOLATION;Column 'dname': non-nullable column has null",
        ]


def test_row_rejected_for_a_missing_value_follows_the_reject_schema(tmp_path):
    made = joined(dict(FETCH, die_on_error=False), out=STRICT, reject=MAIN + ", errorCode:str, errorMessage:str")
    run = same(tmp_path, made)
    assert run.files["rej.csv"].splitlines() == [
        b"id;name;dept;errorCode;errorMessage;dname;loc",
        b"3;carol;D9;JOIN_REJECT;No matching lookup row;;",
        b"3;carol;D9;SCHEMA_VIOLATION;Column 'dname': non-nullable column has null;;",
    ]


def test_inner_join_never_meets_the_missing_value(tmp_path):
    same(tmp_path, joined(dict(FETCH, use_inner_join=True), out=STRICT, reject=True))


def test_declared_columns_the_join_does_not_fetch_are_filled_in(tmp_path):
    run = same(tmp_path, joined({"join_key": ON_DEPT}, out=MAIN + ", n:int!, s:str!, f:float"))
    assert run.files["out.csv"].splitlines()[1] == b"1;alice;D1;0;;"


@pytest.mark.parametrize("order", [(3, 2, 1), (2, 3, 1), (2, 1, 3)])
def test_inner_join_fills_in_declared_columns_it_does_not_fetch(tmp_path, order):
    # v1 fails here ("Column 'n' has NULL values") unless every row it leaves out comes last.
    people = {1: b"1;alice;D1\n", 2: b"2;bob;D2\n", 3: b"3;carol;D9\n"}
    files = {"main.csv": b"id;name;dept\n" + b"".join(people[number] for number in order), "lookup.csv": DEPTS}
    made = joined({"join_key": ON_DEPT, "use_inner_join": True}, out=MAIN + ", n:int!, s:str!")
    if order[-1] == 3:
        same(tmp_path, made, files)
    else:
        result = v2(tmp_path, made, files)
        assert result.status == "success", result.error
        assert (tmp_path / "out.csv").read_bytes().count(b";0;\n") == 2


# ------------------------------------------------------------------
# Which input is which
# ------------------------------------------------------------------

def test_first_input_of_the_components_own_list_is_the_main_one(tmp_path):
    config = {"join_key": ON_DEPT, "use_lookup_cols": True,
              "lookup_cols": [{"output_column": "name", "lookup_column": "name"}]}
    made = joined(config, out=LOOKUP + ", name:str", inputs=("row2", "row1"))
    run = same(tmp_path, made)
    assert run.files["out.csv"].splitlines()[:3] == [b"dept;dname;loc;name", b"D1;Sales;NY;alice", b"D2;Eng;SF;bob"]


def test_flows_named_main_and_lookup_say_which_is_which(tmp_path):
    made = joined(FETCH, out=WIDE, flows=("main", "lookup"), inputs=("lookup", "main"))
    run = same(tmp_path, made)
    assert run.files["out.csv"].splitlines()[1] == b"1;alice;D1;Sales;NY"


def test_flow_named_main_alone_decides_nothing(tmp_path):
    made = joined({"join_key": ON_DEPT}, out=LOOKUP, flows=("main", "row9"), inputs=("row9", "main"))
    run = same(tmp_path, made)
    assert run.files["out.csv"] == DEPTS


def test_v1_type_name_tjoin(tmp_path):
    same(tmp_path, joined(FETCH, out=WIDE, type_name="tJoin"))


def test_v2_type_name(tmp_path):
    result = v2(tmp_path, joined(FETCH, out=WIDE, type_name="join"))
    assert result.status == "success", result.error
    assert (tmp_path / "out.csv").read_bytes().splitlines()[1] == b"1;alice;D1;Sales;NY"


# ------------------------------------------------------------------
# Case
# ------------------------------------------------------------------

def test_keys_differing_in_case_do_not_match_by_default(tmp_path):
    files = rows(b"1;abc\n2;ABC\n3;Abc\n", b"AbC;first\nabc;second\n")
    for index, config in enumerate(({}, {"case_sensitive": True})):
        run = same(tmp_path / str(index), keyed("str", **config), files)
        assert run.files["out.csv"] == b"id;k;v\n1;abc;second\n2;ABC;\n3;Abc;\n"


def test_keys_can_match_whatever_their_case(tmp_path):
    files = rows(b"1;abc\n2;x\n3;zz\n4;\n", b"AbC;first\nX;ex\nQ;no\n")
    run = same(tmp_path, keyed("str", case_sensitive=False), files)
    assert run.files["out.csv"] == b"id;k;v\n1;abc;first\n2;x;ex\n3;zz;\n4;;\n"
    assert run.files["rej.csv"] == b"id;k\n3;zz\n4;\n"


def test_matching_whatever_the_case_leaves_the_data_alone_and_takes_the_first_lookup_row(tmp_path):
    # v1 writes the main keys in lower case, and gives each main row both 'AbC' and 'abc'.
    files = rows(b"1;abc\n2;ABC\n3;Abc\n4;other\n", b"AbC;first\nabc;second\n")
    result = v2(tmp_path, keyed("str", case_sensitive=False), files)
    assert result.status == "success", result.error
    assert (tmp_path / "out.csv").read_bytes() == b"id;k;v\n1;abc;first\n2;ABC;first\n3;Abc;first\n4;other;\n"
    assert (tmp_path / "rej.csv").read_bytes() == b"id;k\n4;other\n"


def test_text_keys_beyond_ascii(tmp_path):
    files = rows("1;\u00e9\n2;\u00c9\n3;e\n4;stra\u00dfe\n".encode(),
                 "\u00e9;acute\nE;plain\nSTRASSE;street\n".encode())
    run = same(tmp_path, keyed("str"), files)
    assert run.files["out.csv"].splitlines()[1] == "1;\u00e9;acute".encode()
    assert run.files["rej.csv"].count(b"\n") == 4
    any_case = rows("1;\u00e9\n2;stra\u00dfe\n3;i\n".encode(), "\u00c9;acute\nSTRASSE;street\nI;eye\n".encode())
    run = same(tmp_path / "any_case", keyed("str", case_sensitive=False), any_case)
    assert run.files["rej.csv"] == "id;k\n2;stra\u00dfe\n".encode()


def test_case_only_matters_to_text(tmp_path):
    files = rows(b"1;10\n2;20\n3;30\n", b"10;a\n20;b\n")
    same(tmp_path, keyed("int", case_sensitive=False), files)


# ------------------------------------------------------------------
# Many rows
# ------------------------------------------------------------------


@pytest.mark.parametrize("inner", [False, True])
def test_row_order_is_kept_on_many_rows(tmp_path, inner):
    pick = random.Random(7)
    main_rows = b"".join(f"{index};{pick.randrange(400)}\n".encode() for index in range(20000))
    lookup_rows = b"".join(f"{pick.randrange(300)};v{index}\n".encode() for index in range(700))
    same(tmp_path, keyed("int", use_inner_join=inner), rows(main_rows, lookup_rows))


# ------------------------------------------------------------------
# What v2 says no to, and what it lets pass
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "config, said",
    [
        ({}, "join_key: required config key is missing"),
        ({"join_key": []}, "join_key: at least one pair of key columns is needed"),
        ({"join_key": None}, "join_key: at least one pair of key columns is needed"),
        ({"join_key": "dept"}, "join_key: expected a list"),
        ({"join_key": [{"input_column": "dept"}]}, "join_key[0].lookup_column: required config key is missing"),
        ({"join_key": [{"lookup_column": "dept"}]}, "join_key[0].input_column: required config key is missing"),
        ({"join_key": [{"input_column": "dept", "lookup_column": 5}]}, "join_key[0].lookup_column: expected text"),
        ({"join_key": [{"input_column": "nope", "lookup_column": "dept"}]}, "no column 'nope' in the main input"),
        ({"join_key": [{"input_column": "dept", "lookup_column": "nope"}]}, "no column 'nope' in the lookup input"),
        ({"join_key": ON_DEPT, "bogus": 1}, "bogus: unknown config key"),
        ({"join_key": ON_DEPT, "use_inner_join": "maybe"}, "use_inner_join: expected true or false"),
        ({"join_key": ON_DEPT, "lookup_cols": [{"output_column": "x", "column": "loc"}]}, "lookup_cols[0].column"),
    ],
)
def test_refused_config(config, said):
    assert said in refused(joined(config))


def test_join_takes_exactly_two_inputs():
    one = joined({"join_key": ON_DEPT})
    one["flows"] = [wire for wire in one["flows"] if wire["name"] != "row2"]
    assert "needs 2 input(s)" in refused(one)

    three = joined({"join_key": ON_DEPT})
    three["components"].append(reader(LOOKUP, component_id="third_in", path="third.csv", outputs=("row3",)))
    three["components"][2]["inputs"].append("row3")
    three["flows"].append(flow("row3", "third_in", "it"))
    assert "takes at most 2 input(s)" in refused(three)


def test_keys_v1_reads_are_accepted():
    config = dict(FETCH, case_sensitive=True, die_on_error=True, use_inner_join="false", component_type="Join",
                  label="Join_Emp_Dept", tstatcatcher_stats=False)
    load_job(joined(config, out=WIDE))


def sample_job():
    """The converter's sample, its two log outputs replaced by files."""
    with open(SAMPLE, encoding="utf-8") as handle:
        sample = json.load(handle)
    paths = {"tFileInputDelimited_1": "main.csv", "tFileInputDelimited_2": "lookup.csv"}
    components = [component for component in sample["components"] if component["type"] != "LogRow"]
    for component in components:
        if component["id"] in paths:
            component["config"]["filepath"] = paths[component["id"]]
    components += [writer(None, inputs=("row2",)), writer(None, component_id="rej", path="rej.csv", inputs=("row3",))]
    wires = [wire for wire in sample["flows"] if wire["to"] == "tJoin_1"]
    wires += [flow("row2", "tJoin_1", "out"), flow("row3", "tJoin_1", "rej", "reject")]
    return dict(sample, components=components, flows=wires)


def test_converter_sample_loads():
    load_job(sample_job())


def test_converter_sample_runs_as_on_v1(tmp_path):
    files = {
        "main.csv": b"emp_id;name;dept_id;salary\n1;alice;D1;100\n2;bob;D9;200\n3;carol;D2;300\n",
        "lookup.csv": b"dept_id;dept_name;location\nD1;Sales;NY\nD2;Eng;SF\n",
    }
    run = same(tmp_path, sample_job(), files)
    assert run.files["out.csv"] == (
        b"emp_id;name;dept_id;salary;dept_name;location\n1;alice;D1;100;;\n2;bob;D9;200;;\n3;carol;D2;300;;\n"
    )
    assert run.files["rej.csv"] == b"emp_id;name;dept_id;salary;dept_name;location\n2;bob;D9;200;;\n"


def test_v1s_own_join_job_runs_as_on_v1(tmp_path):
    with open(V1_FIXTURE, encoding="utf-8") as handle:
        made = json.load(handle)
    paths = {"tFileInputDelimited_main": "main.csv", "tFileInputDelimited_lookup": "lookup.csv",
             "tFileOutputDelimited_main": "out.csv", "tFileOutputDelimited_reject": "rej.csv"}
    for component in made["components"]:
        if component["id"] in paths:
            component["config"]["filepath"] = paths[component["id"]]
    files = {"main.csv": b"id;name\n1;alice\n2;bob\n", "lookup.csv": b"ref_id;city\n1;NYC\n"}
    run = same(tmp_path, made, files)
    assert run.files["out.csv"] == b"id;name;city\n1;alice;NYC\n2;bob;\n"
    assert run.files["rej.csv"] == b"id;name;errorCode;errorMessage\n2;bob;JOIN_REJECT;No matching lookup row\n"


def test_line_count_covers_the_main_input_only_as_in_v1(tmp_path):
    """A RunIf on the join's NB_LINE fires on both engines exactly when it equals the main input's rows."""
    from tests.v2.answer_key import assert_matches_v1
    from tests.v2.components.kit import flow, job, reader, writer

    def made(expected):
        join = {"id": "it", "type": "Join",
                "config": {"use_inner_join": False, "join_key": [{"input_column": "k", "lookup_column": "k"}]},
                "schema": {"input": [], "output": []}, "inputs": ["row1", "row2"], "outputs": ["row3"]}
        components = [
            reader("k:str, v:str", component_id="main_in", path="main.csv", outputs=("row1",)),
            reader("k:str, w:str", component_id="look_in", path="look.csv", outputs=("row2",)),
            join, writer(None, inputs=("row3",)),
            reader("k:str, v:str", component_id="again", path="main.csv", outputs=("row4",)),
            writer(None, component_id="marker", path="marker.csv", inputs=("row4",)),
        ]
        flows = [flow("row1", "main_in", "it"), flow("row2", "look_in", "it"), flow("row3", "it", "out"),
                 flow("row4", "again", "marker")]
        condition = f'((Integer)globalMap.get("it_NB_LINE")) == {expected}'
        return job(components, flows, triggers=[{"type": "RunIf", "from": "it", "to": "again", "condition": condition}])

    inputs = {"main.csv": b"a;1\nb;2\nc;3\n", "look.csv": b"a;x\nb;y\n"}
    fired = assert_matches_v1(made(3), inputs, tmp_path / "three")
    assert fired.succeeded and "marker.csv" in fired.files
    silent = assert_matches_v1(made(5), inputs, tmp_path / "five")
    assert silent.succeeded and "marker.csv" not in silent.files


def test_decimal_key_meets_the_float_nearest_to_it(tmp_path):
    # Compared as floats: the Decimal becomes the float its digits read as, not Polars' own cast of it,
    # which can land one step away and miss.
    made = joined({"use_inner_join": True, "join_key": [{"input_column": "k", "lookup_column": "k"}]},
                  main="k:float, v:str", lookup="k:Decimal#3, w:str")
    result = v2(tmp_path, made, {"main.csv": b"k;v\n12345678901234.567;a\n0.1;b\n",
                                "lookup.csv": b"k;w\n12345678901234.567;x\n0.100;y\n"})
    assert result.status == "success" and result.rows["out"] == 2
