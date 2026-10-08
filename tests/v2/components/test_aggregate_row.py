"""Aggregate row, against v1 on the same job config and bytes.

One thing is held against Talend and not against v1: rows that miss a group
value are a group of their own. v1 leaves them out (see ``kept``).
"""
import json
import os
from pathlib import Path

import pandas as pd
import pytest

from src.v2 import load_job, run_job
from src.v2.components.registry import REGISTRY, Registry
from src.v2.errors import JobRefusedError
from tests.v2 import answer_key
from tests.v2.answer_key import assert_matches_v1
from tests.v2.unit import kit as stand_ins

from .kit import columns, flow, job, reader, writer

SCHEMA = "dept:str, item:str, qty:int, price:float, amt:Decimal#2, day:datetime@%Y-%m-%d, ok:bool"
# One row of "food" and the only row of "misc" hold a missing value in every column that can miss one.
ROWS = (
    b"toys;ball;3;1.1;1.10;2024-01-03;true\n"
    b"food;rice;1;2.2;2.20;2024-01-01;false\n"
    b"toys;kite;2;3.3;3.30;2024-01-02;true\n"
    b"food;;;;0.25;;\n"
    b"misc;;;;7.00;;\n"
    b"food;salt;5;0.1;0.10;2024-01-05;true\n"
)
# The same rows with numbers a float holds exactly, so that float arithmetic has one answer.
EVEN = (
    b"toys;ball;3;1.5;1.50;2024-01-03;true\n"
    b"food;rice;1;2.25;2.25;2024-01-01;false\n"
    b"toys;kite;2;3.5;3.50;2024-01-02;true\n"
    b"food;;;;0.25;;\n"
    b"misc;;;;7.00;;\n"
    b"food;salt;5;0.5;0.50;2024-01-05;true\n"
)
# A second schema for numbers that are awkward to add: a float, a whole number and a Decimal per row.
NUMBERS_SCHEMA = "g:str, f:float, i:int, m:Decimal#3"
FUNCTIONS = ("count", "min", "max", "avg", "sum", "first", "last", "list", "list_object", "count_distinct", "std",
             "population_std_dev", "median", "variance", "union")
LISTS = ("list", "list_object", "union")
SPREAD = ("std", "population_std_dev", "variance")
NUMBERS = ("qty", "price", "amt")
DAY = "datetime@%Y-%m-%d"


def group(column, output=None):
    return {"input_column": column, "output_column": output or column}


def op(function, column, output="r", **more):
    made = {"output_column": output, "function": function, "input_column": column}
    made.update(more)
    return made


def by(column, *operations, **more):
    """The config that groups by one column."""
    made = {"groupbys": [group(column)], "operations": list(operations)}
    made.update(more)
    return made


def by_dept(*operations, **more):
    return by("dept", *operations, **more)


def by_g(*operations, **more):
    return by("g", *operations, **more)


def aggregate(config, schema=SCHEMA, out=None, written="same"):
    """file -> aggregate row -> file.

    ``out`` is the declared output schema; None declares none. ``written`` is
    what the file writer declares: the same columns unless given.
    """
    component = {"id": "it", "type": "AggregateRow", "config": config,
                 "schema": {"input": columns(schema), "output": columns(out) if out else []},
                 "inputs": ["row1"], "outputs": ["row2"]}
    return job([reader(schema), component, writer(out if written == "same" else written)],
               [flow("row1", "in", "it"), flow("row2", "it", "out")])


def same(tmp_path, config, data=ROWS, **kwargs):
    """Both engines finish the job and write the same file; returns the file."""
    run = assert_matches_v1(aggregate(config, **kwargs), {"in.csv": data}, tmp_path)
    assert run.succeeded, run.error
    return run.files["out.csv"]


def v1_keeping(made):
    """Run a job on v1 with pandas told not to drop the rows that miss a group value."""
    stock = pd.DataFrame.groupby

    def groupby(self, *args, **kwargs):
        kwargs.setdefault("dropna", False)
        return stock(self, *args, **kwargs)

    pd.DataFrame.groupby = groupby
    try:
        return answer_key.run_v1(made)
    finally:
        pd.DataFrame.groupby = stock


def kept(tmp_path, config, data=ROWS, **kwargs):
    """v2 writes what v1 writes once it keeps the rows that miss a group value; returns the file.

    Talend keeps such rows as a group of their own: the key its tAggregateRow
    generates holds a missing value like any other. v1 as it stands leaves
    them out, because pandas' ``groupby`` drops them unless it is told
    ``dropna=False``. Told so, v1 is the answer key for everything else about
    that group: where it comes, how its key is written, what its results are.
    """
    made = aggregate(config, **kwargs)
    key = answer_key.run_job(made, {"in.csv": data}, tmp_path / "v1", v1_keeping)
    actual = answer_key.run_job(made, {"in.csv": data}, tmp_path / "v2", answer_key.run_v2)
    assert key.succeeded and actual.succeeded, (key.error, actual.error)
    assert answer_key.differences(key, actual) == []
    return actual.files["out.csv"]


def run_in(folder, made, data, **kwargs):
    """Run a job on v2 inside a folder holding its input; returns the result."""
    folder.mkdir(exist_ok=True)
    (folder / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(folder)
    try:
        return run_job(made, **kwargs)
    finally:
        os.chdir(previous)


def v2(tmp_path, config, data=ROWS, **kwargs):
    """Run on v2 only, inside tmp_path; returns the file written."""
    result = run_in(tmp_path, aggregate(config, **kwargs), data)
    assert result.status == "success", result.error
    return (tmp_path / "out.csv").read_bytes()


def refused(config, **kwargs):
    with pytest.raises(JobRefusedError) as caught:
        load_job(aggregate(config, **kwargs))
    return caught.value.report.format()


def decimal(kind):
    return kind is not None and kind.startswith("Decimal")


def rows_for(kind, rows=ROWS):
    """The rows a test of an output column of this kind can compare with v1 on.

    v1 writes ``<NA>`` for a missing value in a column declared Decimal, so
    such a column gets rows that give every group a number.
    """
    return rows.replace(b"misc;;;;", b"misc;;7;7.5;") if decimal(kind) else rows


def cases(functions, kinds, columns=NUMBERS, ignore_null=(True, False)):
    """Every combination v1's output can be compared on byte for byte.

    Left out: a Decimal column with a missing result (v1 writes ``<NA>``),
    and a column declared int whose results are not all whole (v1 then
    leaves the whole column as floats).
    """
    return [
        (function, column, kind, ignore)
        for function in functions for column in columns for kind in kinds for ignore in ignore_null
        if not (decimal(kind) and not ignore) and not (kind == "int" and column != "qty")
    ]


# ------------------------------------------------------------------
# Groups
# ------------------------------------------------------------------

def test_groups_come_out_in_the_order_they_are_first_seen(tmp_path):
    written = same(tmp_path, by_dept(op("sum", "qty", "total")), out="dept:str, total:int")
    assert written == b"dept;total\ntoys;5\nfood;6\nmisc;0\n"


def test_group_column_can_be_renamed(tmp_path):
    config = {"groupbys": [group("dept", "department")], "operations": [op("count", "qty", "n")]}
    assert same(tmp_path, config, out="department:str, n:int") == b"department;n\ntoys;2\nfood;2\nmisc;0\n"


def test_several_group_columns(tmp_path):
    config = {"groupbys": [group("ok"), group("dept", "d")],
              "operations": [op("count", "item", "n"), op("list", "item", "items")]}
    assert same(tmp_path, config, out="ok:bool, d:str, n:int, items:str") == (
        b"ok;d;n;items\ntrue;toys;2;ball,kite\nfalse;food;2;rice,\nfalse;misc;1;\ntrue;food;1;salt\n"
    )


def test_no_row_is_lost_to_a_missing_group_value(tmp_path):
    # Two of the five rows have no dept. They are a group, as in Talend: v1 writes 1;4 and 2;5 and loses 42.
    written = kept(tmp_path, by_dept(op("sum", "amount", "total")), b"1;1\n;2\n1;3\n;40\n2;5\n",
                   schema="dept:int, amount:int", out="dept:int, total:int")
    assert written == b"dept;total\n1;4\n;42\n2;5\n"


def test_group_of_the_missing_value_is_counted_among_the_rows_handed_on(tmp_path):
    made = aggregate(by_dept(op("sum", "amount", "total")), schema="dept:int, amount:int", out="dept:int, total:int")
    result = run_in(tmp_path, made, b"1;1\n;2\n1;3\n;40\n2;5\n", row_counts=True)
    assert result.counts["it"] == {"NB_LINE": 5, "NB_LINE_OK": 3, "NB_LINE_REJECT": 0}


@pytest.mark.parametrize("key, kind", [("qty", "int"), ("price", "float"), ("day", DAY)])
def test_rows_with_a_missing_group_value_are_a_group_of_their_own(tmp_path, key, kind):
    config = {"groupbys": [group(key, "k")], "operations": [op("count", "dept", "n")]}
    written = kept(tmp_path, config, out=f"k:{kind}, n:int").splitlines()
    # The group comes where its first row arrives, like any other, and its key is written as nothing.
    assert len(written) == 6 and written[4] == b";2"


def test_missing_group_value_in_one_of_several_group_columns(tmp_path):
    config = {"groupbys": [group("dept"), group("qty")], "operations": [op("sum", "amt", "total")]}
    written = kept(tmp_path, config, out="dept:str, qty:int, total:Decimal#2")
    assert b"\nfood;;0.25\nmisc;;7.00\n" in written


def test_group_of_the_rows_that_miss_the_group_value_is_computed_like_any_other(tmp_path):
    operations = [op("count", "amt", "n"), op("sum", "amt", "total"), op("min", "amt", "low"), op("max", "amt", "high"),
                  op("first", "amt", "a"), op("last", "amt", "z"), op("list", "amt", "every"),
                  op("count_distinct", "amt", "kinds")]
    out = "qty:int, n:int, total:Decimal#2, low:Decimal#2, high:Decimal#2, a:Decimal#2, z:Decimal#2, every:str, kinds:int"
    assert b"\n;2;7.25;0.25;7.00;0.25;7.00;0.25,7.00;2\n" in kept(tmp_path, by("qty", *operations), out=out)


@pytest.mark.parametrize(
    "key, kind", [("item", "str"), ("amt", "Decimal#2"), ("ok", "bool"), ("price", "float"), ("qty", "int")]
)
def test_group_by_every_type(tmp_path, key, kind):
    data = ROWS + b"toys;ball;3;3.30;1.1;2024-01-03;true\nfood;;5;;0.250;;false\n"
    kept(tmp_path, by(key, op("count", "dept", "n")), data=data, out=f"{key}:{kind}, n:int")


def test_empty_text_is_a_group_of_its_own(tmp_path):
    assert b"\n;7.25\n" in same(tmp_path, by("item", op("sum", "amt", "total")), out="item:str, total:Decimal#2")


def test_a_group_column_can_also_be_aggregated(tmp_path):
    config = by_dept(op("count", "dept", "n"), op("list", "dept", "all"))
    assert same(tmp_path, config, out="dept:str, n:int, all:str") == (
        b"dept;n;all\ntoys;2;toys,toys\nfood;3;food,food,food\nmisc;1;misc\n"
    )


def test_group_columns_alone_give_each_group_once(tmp_path):
    # v1 fails here: pandas will not aggregate without an operation.
    assert v2(tmp_path, {"groupbys": [group("dept")]}, out="dept:str") == b"dept\ntoys\nfood\nmisc\n"


def test_group_column_without_an_output_name_keeps_its_own(tmp_path):
    # v1 fails here with a KeyError.
    config = {"groupbys": [{"input_column": "dept"}], "operations": [op("count", "qty", "n")]}
    assert v2(tmp_path, config, out="dept:str, n:int") == b"dept;n\ntoys;2\nfood;2\nmisc;0\n"


# ------------------------------------------------------------------
# Without group columns, and without rows
# ------------------------------------------------------------------

@pytest.mark.parametrize("financial", [True, False])
@pytest.mark.parametrize("column", ["qty", "price"])
@pytest.mark.parametrize("function", [name for name in FUNCTIONS if name not in ("first", "last")])
def test_no_group_columns_gives_one_row(tmp_path, function, column, financial):
    config = {"operations": [op(function, column)], "use_financial_precision": financial}
    written = same(tmp_path, config, data=EVEN, out="r:str" if function in LISTS else "r:float")
    assert len(written.splitlines()) == 2


def test_no_group_columns_several_operations(tmp_path):
    config = {"groupbys": [],
              "operations": [op("sum", "qty", "t"), op("count", "item", "n"), op("max", "price", "top")]}
    assert same(tmp_path, config, out="t:int, n:int, top:float") == b"t;n;top\n11;6;3.3\n"


def test_first_and_last_without_group_columns(tmp_path):
    # v1 fails here: it calls Series.first(), which pandas 3 does not have.
    config = {"operations": [op("first", "qty", "a"), op("last", "qty", "z"), op("first", "item", "b")]}
    assert v2(tmp_path, config, out="a:int, z:int, b:str") == b"a;z;b\n3;5;ball\n"


@pytest.mark.parametrize(
    "groups, out, header", [([group("dept")], "dept:str, t:int, n:int", b"dept;t;n\n"), ([], "t:int, n:int", b"t;n\n")]
)
def test_no_rows_in_gives_no_rows_out(tmp_path, groups, out, header):
    config = {"groupbys": groups, "operations": [op("sum", "qty", "t"), op("count", "qty", "n")]}
    assert same(tmp_path, config, data=b"", out=out) == header


def test_no_rows_in_and_no_declared_columns_still_names_the_columns(tmp_path):
    # v1 writes an empty file: it has forgotten its columns by then.
    assert v2(tmp_path, by_dept(op("sum", "qty", "t")), data=b"", written=None) == b"dept;t\n"


# ------------------------------------------------------------------
# Output columns
# ------------------------------------------------------------------

def test_operation_without_an_output_column_is_named_after_its_input(tmp_path):
    config = by_dept({"function": "sum", "input_column": "qty"})
    assert same(tmp_path, config, written=None).splitlines()[0] == b"dept;qty"


def test_operation_without_ignore_null_ignores_missing_values(tmp_path):
    config = by_dept({"function": "sum", "input_column": "qty", "output_column": "r"})
    assert same(tmp_path, config, out="dept:str, r:int") == b"dept;r\ntoys;5\nfood;6\nmisc;0\n"


def test_two_operations_on_one_output_column_the_last_one_counts(tmp_path):
    config = by_dept(op("sum", "qty", "r"), op("count", "qty", "n"), op("max", "qty", "r"))
    assert same(tmp_path, config, out="dept:str, r:int, n:int") == b"dept;r;n\ntoys;3;2\nfood;5;2\nmisc;;0\n"


def test_declared_columns_decide_the_order_and_undeclared_ones_follow(tmp_path):
    config = {"groupbys": [group("dept", "grp")], "operations": [op("sum", "qty", "r"), op("count", "qty", "n")]}
    assert same(tmp_path, config, out="r:int").splitlines()[:2] == [b"r;grp;n", b"5;toys;2"]
    more = same(tmp_path / "more", config, out="n:int, grp:str, zz:str, yy:int!, r:int")
    assert more.splitlines()[:2] == [b"n;grp;zz;yy;r", b"2;toys;;0;5"]


def test_function_names_are_read_in_any_case(tmp_path):
    config = by_dept(op("SUM", "qty", "r"), op("Count_Distinct", "item", "n"))
    assert same(tmp_path, config, out="dept:str, r:int, n:int") == b"dept;r;n\ntoys;5;2\nfood;6;3\nmisc;0;1\n"


def test_list_delimiter_can_come_from_the_context(tmp_path):
    made = aggregate(by_dept(op("list", "item"), list_delimiter="${context.between}"), out="dept:str, r:str")
    made["context"] = {"Default": {"between": {"value": " + ", "type": "str"}}}
    run = assert_matches_v1(made, {"in.csv": ROWS}, tmp_path)
    assert run.files["out.csv"] == b"dept;r\ntoys;ball + kite\nfood;rice +  + salt\nmisc;\n"


def test_aggregated_rows_go_on_through_the_job(tmp_path):
    made = aggregate(by_dept(op("sum", "qty", "total"), op("count", "item", "n")), out="dept:str, total:int, n:int")
    declared = {"input": columns("dept:str, total:int, n:int"), "output": columns("dept:str, total:int, n:int")}
    kept = {"id": "keep", "type": "FilterRows", "schema": declared, "inputs": ["row2"], "outputs": ["row3"],
            "config": {"conditions": [{"column": "n", "operator": ">", "value": "1"}]}}
    ordered = {"id": "order", "type": "SortRow", "schema": declared, "inputs": ["row3"], "outputs": ["row4"],
               "config": {"criteria": [{"column": "total", "sort_type": "num", "order": "desc"}]}}
    made["components"][2]["inputs"] = ["row4"]
    made["components"] += [kept, ordered]
    made["flows"] = [flow("row1", "in", "it"), flow("row2", "it", "keep"), flow("row3", "keep", "order", "filter"),
                     flow("row4", "order", "out")]
    run = assert_matches_v1(made, {"in.csv": ROWS}, tmp_path)
    assert run.files["out.csv"] == b"dept;total;n\nfood;6;3\ntoys;5;2\n"


def test_missing_result_in_a_column_that_allows_none_fails_the_job(tmp_path):
    made = aggregate(by_dept(op("max", "qty")), out="dept:str, r:int!")
    run = assert_matches_v1(made, {"in.csv": ROWS}, tmp_path)
    assert not run.succeeded
    assert "Column 'r' has NULL values but is not nullable" in run.error


# ------------------------------------------------------------------
# Every function on every type, missing values ignored or not
# ------------------------------------------------------------------

@pytest.mark.parametrize("ignore_null", [True, False])
@pytest.mark.parametrize("column", ["item", "qty", "price", "day", "ok", "amt"])
@pytest.mark.parametrize("function", ["count", "count_distinct"])
def test_counts(tmp_path, function, column, ignore_null):
    same(tmp_path, by_dept(op(function, column, ignore_null=ignore_null)), out="dept:str, r:int")


def test_counts_in_columns_of_other_types(tmp_path):
    config = by_dept(op("count", "qty", "f"), op("count_distinct", "item", "d"), op("count", "qty", "s"))
    assert same(tmp_path, config, out="dept:str, f:float, d:Decimal#2, s:str") == (
        b"dept;f;d;s\ntoys;2;2.00;2\nfood;2;3.00;2\nmisc;0;1.00;0\n"
    )


@pytest.mark.parametrize("ignore_null", [True, False])
@pytest.mark.parametrize(
    "column, kind",
    [("item", "str"), ("qty", "int"), ("price", "float"), ("day", DAY), ("ok", "bool"), ("amt", "Decimal#2")],
)
@pytest.mark.parametrize("function", ["first", "last"])
def test_first_and_last_value_that_is_not_missing(tmp_path, function, column, kind, ignore_null):
    same(tmp_path, by_dept(op(function, column, ignore_null=ignore_null)), out=f"dept:str, r:{kind}")


def test_first_and_last_skip_the_rows_that_miss_the_value(tmp_path):
    data = b"a;;;;1.00;;\na;x;1;1.5;1.00;2024-01-01;\na;y;2;2.5;1.00;2024-01-02;\na;;;;1.00;;\n"
    config = by_dept(op("first", "qty", "a"), op("last", "qty", "z"), op("first", "price", "b"), op("last", "day", "y"),
                     op("first", "item", "text"))
    out = f"dept:str, a:int, z:int, b:float, y:{DAY}, text:str"
    assert same(tmp_path, config, data=data, out=out) == b"dept;a;z;b;y;text\na;1;2;1.5;2024-01-02;\n"


@pytest.mark.parametrize(
    "function, column, kind, ignore_null",
    cases(["sum", "min", "max"], ["float", "int", "Decimal#2", "Decimal", "Decimal#0", "float#1"]),
)
def test_sum_min_and_max_of_numbers(tmp_path, function, column, kind, ignore_null):
    config = by_dept(op(function, column, ignore_null=ignore_null))
    same(tmp_path, config, data=rows_for(kind), out=f"dept:str, r:{kind}")


@pytest.mark.parametrize(
    "function, column, kind, ignore_null", cases(["avg"], ["float", "Decimal#2", "Decimal#4", "Decimal#0", "float#2"])
)
def test_average(tmp_path, function, column, kind, ignore_null):
    config = by_dept(op(function, column, ignore_null=ignore_null))
    same(tmp_path, config, data=rows_for(kind), out=f"dept:str, r:{kind}")


@pytest.mark.parametrize("column", ["qty", "amt"])
@pytest.mark.parametrize("function", ["sum", "min", "max"])
def test_whole_and_decimal_results_look_the_same_in_a_column_declared_text_or_not_at_all(tmp_path, function, column):
    config = by_dept(op(function, column))
    same(tmp_path, config, out="dept:str, r:str")
    same(tmp_path / "undeclared", config, written=None)


@pytest.mark.parametrize("function", ["sum", "min", "max", "avg"])
def test_results_from_a_float_column_are_floats_in_a_column_not_declared(tmp_path, function):
    same(tmp_path, by_dept(op(function, "price")), data=ROWS.replace(b"misc;;;;", b"misc;;;4.5;"), written=None)


@pytest.mark.parametrize(
    "function, column, kind, ignore_null", cases(["median"], ["float", "Decimal#2", "Decimal", "int"])
)
def test_median(tmp_path, function, column, kind, ignore_null):
    config = by_dept(op(function, column, ignore_null=ignore_null))
    same(tmp_path, config, data=rows_for(kind), out=f"dept:str, r:{kind}")


def test_median_of_an_even_number_of_values_is_halfway_between_the_middle_two(tmp_path):
    data = b"a;x;1;0.1;0.10;;\na;x;2;2.2;2.25;;\na;x;10;7.7;9.99;;\na;x;4;3.3;3.30;;\n"
    config = by_dept(op("median", "qty", "q"), op("median", "price", "p"), op("median", "amt", "a"))
    written = same(tmp_path, config, data=data, out="dept:str, q:float, p:float, a:float")
    assert written == b"dept;q;p;a\na;3.0;2.75;2.775\n"


def test_median_skips_missing_values_unless_use_financial_precision_is_off(tmp_path):
    config = by_dept(op("median", "qty", ignore_null=False))
    assert same(tmp_path, config, out="dept:str, r:float") == b"dept;r\ntoys;2.5\nfood;3.0\nmisc;\n"
    config["use_financial_precision"] = False
    assert same(tmp_path / "off", config, out="dept:str, r:float") == b"dept;r\ntoys;2.5\nfood;\nmisc;\n"


# With missing values kept, v1 fails on a missing whole number and changes the way it writes dates: v2's own tests.
@pytest.mark.parametrize(
    "column, ignore_null",
    [(column, True) for column in ("item", "qty", "price", "ok", "amt", "day")]
    + [(column, False) for column in ("item", "price", "ok", "amt")],
)
@pytest.mark.parametrize("function", LISTS)
def test_lists(tmp_path, function, column, ignore_null):
    same(tmp_path, by_dept(op(function, column, ignore_null=ignore_null)), out="dept:str, r:str")


def test_lists_look_like_this(tmp_path):
    config = by_dept(op("list", "item", "l"), op("list_object", "qty", "o"), op("union", "item", "u"),
                     op("list", "price", "n", ignore_null=False), op("list", "day", "d"), op("union", "ok", "b"))
    assert same(tmp_path, config, out="dept:str, l:str, o:str, u:str, n:str, d:str, b:str") == (
        b"dept;l;o;u;n;d;b\n"
        b"toys;ball,kite;[3, 2];ball,kite;1.1,3.3;2024-01-03,2024-01-02;True\n"
        b"food;rice,,salt;[1, 5];,rice,salt;2.2,null,0.1;2024-01-01,2024-01-05;False,True\n"
        b"misc;;[];;null;;False\n"
    )


@pytest.mark.parametrize("delimiter", [";", " | ", "", "\\t"])
def test_list_delimiter_separates_list_and_union_but_not_list_object(tmp_path, delimiter):
    config = by_dept(op("list", "item", "l"), op("union", "item", "u"), op("list_object", "item", "o"),
                     list_delimiter=delimiter)
    same(tmp_path, config, written=None)


def test_union_sorts_values_as_text(tmp_path):
    data = b"a;b;10;;1.00;;\na;B;9;;1.00;;\na;a;100;;1.00;;\na;b;9;;1.00;;\n"
    config = by_dept(op("union", "qty", "q"), op("union", "item", "i"))
    assert same(tmp_path, config, data=data, out="dept:str, q:str, i:str") == b"dept;q;i\na;10,100,9;B,a,b\n"


def test_dates_in_a_list_show_no_more_of_their_time_than_they_have(tmp_path):
    schema = "g:str, d:datetime@%Y-%m-%d %H:%M:%S.%f"
    data = (b"a;2024-01-03 00:00:00.000000\na;2024-01-01 00:00:00.000000\n"
            b"b;2024-01-02 10:00:00.000000\nb;2024-01-02 11:30:15.000000\n"
            b"c;2024-01-03 10:30:00.500000\nc;2024-01-03 10:30:00.250000\n"
            b"d;2024-01-03 10:30:00.123456\nd;2024-01-03 10:30:00.000001\n")
    assert same(tmp_path, by_g(op("list", "d", "l")), data=data, schema=schema, out="g:str, l:str") == (
        b"g;l\na;2024-01-03,2024-01-01\nb;2024-01-02 10:00:00,2024-01-02 11:30:15\n"
        b"c;2024-01-03 10:30:00.500,2024-01-03 10:30:00.250\nd;2024-01-03 10:30:00.123456,2024-01-03 10:30:00.000001\n"
    )


# ------------------------------------------------------------------
# Decimal arithmetic (use_financial_precision, the default)
# ------------------------------------------------------------------

AWKWARD = (
    b"a;0.1;1;0.005\na;0.2;2;0.005\n"
    b"b;1;10;1.005\nb;1;0;1\nb;1;0;1\n"
    b"c;2.675;7;2.675\n"
    b"d;999999999999.25;5;1\nd;0.125;5;1\n"
    b"e;123456789.125;1;1\ne;0.125;2;1\ne;0.0001;3;1\n"
    b"f;-1.5;-1;-1.005\nf;-2.5;-2;-1\n"
    b"h;0.7;3;0.7\nh;0.1;3;0.1\nh;0.3;4;0.3\nh;0.3;4;0.3\nh;0.3;4;0.3\nh;0.3;4;0.3\nh;0.3;4;0.3\n"
)


def numbers(tmp_path, config, data, out):
    """`same` for a job over the awkward-numbers schema."""
    return same(tmp_path, config, data=data, schema=NUMBERS_SCHEMA, out=out)


@pytest.mark.parametrize("kind", ["float", "Decimal#2", "Decimal#6", "Decimal#0", "float#3"])
@pytest.mark.parametrize("column", ["f", "i", "m"])
@pytest.mark.parametrize("function", ["sum", "avg", "min", "max"])
def test_numbers_are_added_and_divided_as_decimals(tmp_path, function, column, kind):
    numbers(tmp_path, by_g(op(function, column)), AWKWARD, f"g:str, r:{kind}")


@pytest.mark.parametrize("column", ["f", "i", "m"])
@pytest.mark.parametrize("function", ["sum", "min", "max"])
def test_decimal_column_without_declared_places_shows_the_places_a_result_has(tmp_path, function, column):
    numbers(tmp_path, by_g(op(function, column)), AWKWARD, "g:str, r:Decimal")


def test_sum_of_floats_is_the_sum_of_the_decimals_they_are_written_as(tmp_path):
    config = by_g(op("sum", "f", "s"), op("avg", "f", "a"))
    written = numbers(tmp_path, config, b"x;0.1;;\nx;0.2;;\nx;0.3;;\n", "g:str, s:float, a:float")
    assert written == b"g;s;a\nx;0.6;0.2\n"


def test_half_way_values_round_away_from_zero_at_the_declared_places(tmp_path):
    config = by_g(op("sum", "f", "s"), op("avg", "m", "a"), op("sum", "m", "t"))
    data = b"x;1000.125;;0.005\nx;1000;;0.005\ny;-0.125;;-1.005\ny;-2000;;-1\n"
    written = numbers(tmp_path, config, data, "g:str, s:Decimal#2, a:Decimal#2, t:Decimal#2")
    assert written == b"g;s;a;t\nx;2000.13;0.01;0.01\ny;-2000.13;-1.00;-2.01\n"


@pytest.mark.parametrize("kind", ["float", "Decimal#2", "Decimal#10", "float#4"])
@pytest.mark.parametrize("rows", [3, 6, 7, 9, 11, 13])
def test_average_that_does_not_terminate(tmp_path, rows, kind):
    data = b"".join(b"x;%d.%d;%d;%d.5\n" % (n * 7, n, n * n, n) for n in range(1, rows + 1))
    config = by_g(op("avg", "f", "f"), op("avg", "i", "i"), op("avg", "m", "m"))
    numbers(tmp_path, config, data, f"g:str, f:{kind}, i:{kind}, m:{kind}")


def test_average_in_a_decimal_column_without_declared_places(tmp_path):
    config = by_g(op("avg", "f", "f"), op("avg", "i", "i"), op("avg", "m", "m"))
    data = b"x;0.5;1;1.005\nx;0.25;2;1\ny;7;7;7\nz;1;1;1\nz;2;2;2\nz;3;4;3\nz;5;5;5\n"
    written = numbers(tmp_path, config, data, "g:str, f:Decimal, i:Decimal, m:Decimal")
    assert written == b"g;f;i;m\nx;0.375;1.5;1.0025\ny;7;7;7\nz;2.75;3;2.75\n"


def test_quotients_are_kept_to_the_declared_places_when_they_are_more_than_18(tmp_path):
    data = b"x;;10;0.5\nx;;0;0.25\nx;;0;0.75\ny;;1;0.5\ny;;2;0.25\ny;;4;0.5\ny;;0;0.75\n"
    config = by_g(op("avg", "i", "a"), op("variance", "m", "v"))
    assert numbers(tmp_path, config, data, "g:str, a:Decimal#20, v:Decimal#20") == (
        b"g;a;v\nx;3.33333333333333333333;0.06250000000000000000\ny;1.75000000000000000000;0.04166666666666666667\n"
    )


def test_average_that_does_not_terminate_is_kept_to_18_places_in_a_decimal_column(tmp_path):
    # v1 keeps 28 significant digits: 3.333333333333333333333333333 and 0.6666666666666666666666666667.
    config, data = by_g(op("avg", "i", "i"), op("avg", "f", "f")), b"x;1;10;\nx;1;0;\nx;0;0;\n"
    written = v2(tmp_path, config, data=data, schema=NUMBERS_SCHEMA, out="g:str, i:Decimal, f:Decimal")
    assert written == b"g;i;f\nx;3.333333333333333333;0.666666666666666667\n"


def test_large_and_small_floats_add_up_exactly(tmp_path):
    data = b"x;123456789012.345;;\nx;0.0001;;\nx;-123456789012.345;;\ny;99999999999999.9;;\ny;0.1;;\n"
    assert numbers(tmp_path, by_g(op("sum", "f", "s"), op("avg", "f", "a")), data, "g:str, s:float, a:Decimal#8") == (
        b"g;s;a\nx;0.0001;0.00003333\ny;100000000000000.0;50000000000000.00000000\n"
    )


def test_sum_of_floats_keeps_more_digits_than_a_float_holds_in_a_decimal_column(tmp_path):
    config, data = by_g(op("sum", "f", "s"), op("avg", "f", "a")), b"x;123456789012.345;;\nx;0.000001;;\nx;0.000002;;\n"
    written = numbers(tmp_path, config, data, "g:str, s:Decimal#6, a:Decimal#8")
    assert written == b"g;s;a\nx;123456789012.345003;41152263004.11500100\n"


def test_decimal_in_a_float_column_is_the_nearest_float_and_float_in_a_decimal_column_the_one_it_prints_as(tmp_path):
    # Polars' own casts give 12345678901234.568 for the Decimal, and 123456789.124999987 for the float, which
    # then rounds to 123456789.12.
    config = by_g(op("max", "m", "a"), op("first", "m", "b"), op("sum", "m", "c"),
                  op("max", "f", "d"), op("first", "f", "e"), op("median", "f", "h"))
    out = "g:str, a:float, b:float, c:float, d:Decimal#2, e:Decimal, h:Decimal#2"
    assert numbers(tmp_path, config, b"x;123456789.125;;12345678901234.567\n", out) == (
        b"g;a;b;c;d;e;h\n"
        b"x;12345678901234.566;12345678901234.566;12345678901234.566;123456789.13;123456789.125;123456789.13\n"
    )


def test_floats_of_a_quadrillion_and_more_are_added_as_floats(tmp_path):
    # The three of "w" would each fit the exact sum and together outgrow it.
    data = b"x;1e25;;\nx;1;;\ny;inf;;\ny;1;;\nz;1e15;;\nz;0.25;;\nw;9e19;;\nw;9e19;;\nw;9e19;;\n"
    config = by_g(op("sum", "f", "s"), op("avg", "f", "a"), op("max", "f", "x"))
    assert numbers(tmp_path, config, data, "g:str, s:float, a:float, x:float") == (
        b"g;s;a;x\nx;1e+25;5e+24;1e+25\ny;inf;inf;inf\nz;1000000000000000.2;500000000000000.1;1000000000000000.0\n"
        b"w;2.7e+20;9e+19;9e+19\n"
    )


def test_sum_of_whole_numbers_is_a_float_in_a_float_column(tmp_path):
    config = by_dept(op("sum", "qty", "s"), op("max", "qty", "x"), op("avg", "qty", "a"))
    assert same(tmp_path, config, out="dept:str, s:float, x:float, a:float") == (
        b"dept;s;x;a\ntoys;5.0;3.0;2.5\nfood;6.0;5.0;3.0\nmisc;0.0;;\n"
    )


# ------------------------------------------------------------------
# The column's own arithmetic (use_financial_precision off)
# ------------------------------------------------------------------

def plain(*operations):
    return by_dept(*operations, use_financial_precision=False)


@pytest.mark.parametrize(
    "function, column, kind, ignore_null",
    cases(["sum", "avg", "min", "max", "median"], ["float", "Decimal#2", "Decimal", None], columns=["qty", "price"]),
)
def test_arithmetic_of_the_columns_own_type(tmp_path, function, column, kind, ignore_null):
    config = plain(op(function, column, ignore_null=ignore_null))
    same(tmp_path, config, data=rows_for(kind, EVEN), out=f"dept:str, r:{kind}" if kind else None,
         written="same" if kind else None)


@pytest.mark.parametrize("kind", ["float", "Decimal#2", "Decimal"])
@pytest.mark.parametrize("function", ["sum", "avg", "min", "max", "median"])
def test_arithmetic_of_the_columns_own_type_on_a_decimal_column(tmp_path, function, kind):
    same(tmp_path, plain(op(function, "amt")), out=f"dept:str, r:{kind}")


@pytest.mark.parametrize("ignore_null", [True, False])
@pytest.mark.parametrize("column, kind", [("item", "str"), ("day", DAY), ("ok", "bool")])
@pytest.mark.parametrize("function", ["min", "max"])
def test_smallest_and_largest_of_text_dates_and_booleans(tmp_path, function, column, kind, ignore_null):
    same(tmp_path, plain(op(function, column, ignore_null=ignore_null)), out=f"dept:str, r:{kind}")


def test_sum_of_whole_numbers_stays_whole_in_a_float_column_without_financial_precision(tmp_path):
    config = plain(op("sum", "qty", "s"), op("max", "qty", "x"), op("avg", "qty", "a"))
    assert same(tmp_path, config, out="dept:str, s:float, x:float, a:float") == (
        b"dept;s;x;a\ntoys;5;3;2.5\nfood;6;5;3.0\nmisc;0;;\n"
    )


def test_average_is_the_sum_divided_as_a_float_without_financial_precision(tmp_path):
    data = b"a;;;;2.20;;\na;;;;0.50;;\na;;;;0.10;;\n"
    off = same(tmp_path, plain(op("avg", "amt")), data=data, out="dept:str, r:float")
    assert off == b"dept;r\na;0.9333333333333332\n"
    on = same(tmp_path / "on", by_dept(op("avg", "amt")), data=data, out="dept:str, r:float")
    assert on == b"dept;r\na;0.9333333333333333\n"


def test_sum_of_floats_is_exact_without_financial_precision_too(tmp_path):
    # v1 adds floats in the order pandas takes them and gives 0.6000000000000001 and 0.20000000000000004.
    config = by_g(op("sum", "f", "s"), op("avg", "f", "a"), use_financial_precision=False)
    data = b"x;0.1;;\nx;0.2;;\nx;0.3;;\n"
    written = v2(tmp_path, config, data=data, schema=NUMBERS_SCHEMA, out="g:str, s:float, a:float")
    assert written == b"g;s;a\nx;0.6;0.19999999999999998\n"


# ------------------------------------------------------------------
# Spread: std, population_std_dev and variance
# ------------------------------------------------------------------

# Without use_financial_precision v1 fails on the spread of a Decimal column: that is one of v2's own tests.
@pytest.mark.parametrize(
    "function, column, kind, ignore_null, financial",
    [case + (True,) for case in cases(SPREAD, ["float", "Decimal"])]
    + [case + (False,) for case in cases(SPREAD, ["float", "Decimal"], columns=["qty", "price"])],
)
def test_spread_of_numbers_a_float_holds_exactly(tmp_path, function, column, kind, ignore_null, financial):
    # A second row of "misc" gives a Decimal column a result for every group; v1 writes <NA> where there is none.
    data = EVEN.replace(b"misc;;;;", b"misc;;7;7.5;") + b"misc;;9;8.5;9.00;;\n" if decimal(kind) else EVEN
    config = by_dept(op(function, column, ignore_null=ignore_null), use_financial_precision=financial)
    same(tmp_path, config, data=data, out=f"dept:str, r:{kind}")


def test_spread_looks_like_this(tmp_path):
    config = by_dept(op("variance", "price", "v"), op("std", "price", "s"), op("population_std_dev", "amt", "p"))
    assert same(tmp_path, config, data=EVEN, out="dept:str, v:float, s:float, p:float") == (
        b"dept;v;s;p\ntoys;2.0;1.4142135623730951;1.0\nfood;1.53125;1.2374368670764582;0.8897565210026093\nmisc;;;0.0\n"
    )


@pytest.mark.parametrize("kind", ["float#6", "Decimal#6"])
@pytest.mark.parametrize("column", NUMBERS)
@pytest.mark.parametrize("function", SPREAD)
def test_spread_equals_v1_at_six_places(tmp_path, function, column, kind):
    data = ROWS.replace(b"misc;;;;", b"misc;;4;4.5;") + b"misc;;9;0.7;1.15;;\n"
    same(tmp_path, by_dept(op(function, column)), data=data, out=f"dept:str, r:{kind}")


# Groups whose mean terminates: v1's Decimal arithmetic is exact on them, and so is v2's.
TERMINATING = (
    b"pair;1.1;1;0.005\npair;3.3;4;1.115\n"
    b"three;1.1;3;1.1\nthree;2.2;5;2.2\nthree;4.5;10;4.5\n"
    b"close;1000000.01;7;1000000.01\nclose;1000000.02;8;1000000.02\n"
    b"close;1000000.04;9;1000000.04\nclose;1000000.09;12;1000000.09\n"
    b"large;250000000.75;250000000;250000000.75\nlarge;750000000.25;750000001;750000000.25\n"
    b"mixed;123456789.01;-42;123456789.01\nmixed;987654321.99;123456789;987654321.99\n"
    b"mixed;555555555.55;1;555555555.55\nmixed;1.45;8;1.45\n"
)


@pytest.mark.parametrize("kind", ["float", "Decimal#2", "Decimal#4", "float#2", "float#3"])
@pytest.mark.parametrize("column", ["f", "i", "m"])
@pytest.mark.parametrize("function", SPREAD)
def test_spread_of_decimal_numbers_is_exact_when_their_mean_terminates(tmp_path, function, column, kind):
    numbers(tmp_path, by_g(op(function, column)), TERMINATING, f"g:str, r:{kind}")


def test_spread_of_decimal_numbers_looks_like_this(tmp_path):
    config = by_g(op("variance", "f", "v"), op("std", "f", "s"), op("variance", "f", "d"))
    assert numbers(tmp_path, config, TERMINATING, "g:str, v:float, s:float, d:Decimal#2") == (
        b"g;v;s;d\n"
        b"pair;2.42;1.5556349186104046;2.42\n"
        b"three;3.01;1.7349351572897471;3.01\n"
        b"close;0.0012666666666666666;0.03559026084010437;0.00\n"
        b"large;1.2499999975e+17;353553390.23972034;124999999750000000.13\n"
        b"mixed;2.0163338941503328e+17;449036066.94232625;201633389415033278.75\n"
    )


def test_spread_of_numbers_too_large_to_square_exactly_is_a_float_computation(tmp_path):
    data = b"x;;9000000000000000000;\nx;;-9000000000000000000;\ny;;4000000000;\ny;;1;\n"
    config = by_g(op("variance", "i", "v"), op("std", "i", "s"))
    assert numbers(tmp_path, config, data, "g:str, v:float, s:float") == (
        b"g;v;s\nx;1.62e+38;1.2727922061357855e+19\ny;7.999999996e+18;2828427124.0390835\n"
    )


def test_spread_around_a_mean_that_does_not_terminate_is_a_float_computation(tmp_path):
    # v1 computes these in Decimals of 28 digits and gives 4.333333333333333 and 2.0816659994661326.
    config, data = by_g(op("variance", "i", "v"), op("std", "i", "s")), b"x;;1;\nx;;4;\nx;;5;\n"
    written = v2(tmp_path, config, data=data, schema=NUMBERS_SCHEMA, out="g:str, v:float, s:float")
    assert written == b"g;v;s\nx;4.333333333333334;2.081665999466133\n"
    # At declared places the two agree.
    rounded = numbers(tmp_path / "rounded", config, data, "g:str, v:float#6, s:Decimal#6")
    assert rounded == b"g;v;s\nx;4.333333;2.081666\n"


def test_spread_is_computed_the_same_way_without_financial_precision(tmp_path):
    # v1 then adds floats as pandas takes them and gives 2.4199999999999995 and 1.5556349186104044.
    config = by_g(op("variance", "f", "v"), op("std", "f", "s"), use_financial_precision=False)
    written = v2(tmp_path, config, data=b"x;1.1;;\nx;3.3;;\n", schema=NUMBERS_SCHEMA, out="g:str, v:float, s:float")
    assert written == b"g;v;s\nx;2.42;1.5556349186104046\n"


def test_spread_of_a_decimal_column_without_financial_precision(tmp_path):
    # v1 fails here.
    config = plain(op("variance", "amt", "v"), op("std", "amt", "s"), op("population_std_dev", "amt", "p"))
    assert v2(tmp_path, config, data=EVEN, out="dept:str, v:float, s:float, p:float") == (
        b"dept;v;s;p\ntoys;2.0;1.4142135623730951;1.0\nfood;1.1875;1.0897247358851685;0.8897565210026093\nmisc;;;0.0\n"
    )


# ------------------------------------------------------------------
# The same file from run to run
# ------------------------------------------------------------------

@pytest.mark.parametrize("groups", [[group("dept")], []])
def test_both_polars_engines_write_the_same_file_whatever_the_order_of_rows(tmp_path, groups):
    # 19999 rows: no mean terminates, so that the spread is the one computed in floats.
    lines = [
        b"%s;i%d;%d;%d.%02d;%d.%02d;2024-01-%02d;true\n" % (
            b"abc"[n % 3:n % 3 + 1], n % 11, n * 7 % 1000 - 300,
            n * 31 % 977, n % 100, n * 13 % 500, n * 7 % 100, n % 28 + 1,
        )
        for n in range(19999)
    ]
    of_numbers = [
        op(function, column, f"{function}_{column}")
        for function in ("sum", "avg", "min", "max", "median") + SPREAD for column in NUMBERS
    ]
    others = [op("first", "item", "a"), op("last", "item", "z"), op("union", "item", "u"),
              op("count_distinct", "day", "d")]
    made = aggregate({"groupbys": groups, "operations": of_numbers + others})
    runs = {"streaming": (lines, "streaming"), "memory": (lines, "in-memory"), "turned": (lines[::-1], None)}
    written = {}
    for name, (data, engine) in runs.items():
        assert run_in(tmp_path / name, made, b"".join(data), engine=engine).status == "success"
        written[name] = (tmp_path / name / "out.csv").read_bytes()
    assert written["streaming"] == written["memory"]
    if not groups:
        numbers_of = {name: written[name].splitlines()[1].split(b";")[:len(of_numbers)] for name in written}
        assert numbers_of["streaming"] == numbers_of["turned"]


# ------------------------------------------------------------------
# Where v1 fails or gives nothing, and v2 does the sensible thing
# ------------------------------------------------------------------

def test_missing_result_in_a_decimal_column_is_written_empty(tmp_path):
    # v1 writes <NA> for each of the three missing results.
    config = by_dept(op("sum", "qty", "s", ignore_null=False), op("max", "price", "x"))
    written = v2(tmp_path, config, out="dept:str, s:Decimal#2, x:Decimal")
    assert written == b"dept;s;x\ntoys;5.00;3.3\nfood;;2.2\nmisc;;\n"


def test_missing_decimal_is_a_missing_value(tmp_path):
    # v1 reads an empty Decimal field as empty text: it counts it, lists it, and never sees it as missing.
    data = b"a;;;;1.50;;\na;;;;;;\nb;;;;;;\n"
    config = by_dept(op("count", "amt", "n"), op("count_distinct", "amt", "d"), op("list", "amt", "l"),
                     op("first", "amt", "f"), op("sum", "amt", "s"), op("sum", "amt", "strict", ignore_null=False))
    out = "dept:str, n:int, d:int, l:str, f:Decimal#2, s:Decimal#2, strict:Decimal#2"
    assert v2(tmp_path, config, data=data, out=out) == b"dept;n;d;l;f;s;strict\na;1;1;1.50;1.50;1.50;\nb;0;0;;;0.00;\n"


def test_missing_whole_number_in_a_list_that_keeps_missing_values(tmp_path):
    # v1 fails here: it cannot put the text "null" into a column of whole numbers.
    config = by_dept(op("list", "qty", "l", ignore_null=False), op("list_object", "qty", "o", ignore_null=False),
                     op("union", "qty", "u", ignore_null=False))
    assert v2(tmp_path, config, out="dept:str, l:str, o:str, u:str") == (
        b"dept;l;o;u\ntoys;3,2;[3, 2];2,3\nfood;1,null,5;[1, null, 5];1,5,null\nmisc;null;[null];null\n"
    )


def test_each_date_in_a_list_is_written_the_same_way_whatever_else_is_in_its_group(tmp_path):
    # v1 picks one way for a whole group: every date gets a time as soon as one has one, or one is missing.
    schema = "g:str, d:datetime@%Y-%m-%d %H:%M:%S.%f"
    data = (b"a;2024-01-03 00:00:00.000000\na;2024-01-01 10:30:00.000000\nb;2024-01-02 00:00:00.000000\nb;\n"
            b"c;2024-01-03 10:30:00.500000\nc;2024-01-03 10:30:00.000000\n")
    config = by_g(op("list", "d", "l", ignore_null=False))
    assert v2(tmp_path, config, data=data, schema=schema, out="g:str, l:str") == (
        b"g;l\na;2024-01-03,2024-01-01 10:30:00\nb;2024-01-02,null\nc;2024-01-03 10:30:00.500,2024-01-03 10:30:00\n"
    )


def test_smallest_and_largest_of_text_dates_and_booleans_with_financial_precision(tmp_path):
    # v1 gives nothing here: it tries to read every value as a Decimal.
    config = by_dept(op("min", "item", "a"), op("max", "item", "z"), op("min", "day", "d"), op("max", "ok", "b"))
    assert v2(tmp_path, config, out=f"dept:str, a:str, z:str, d:{DAY}, b:bool") == (
        b"dept;a;z;d;b\ntoys;ball;kite;2024-01-02;true\nfood;;salt;2024-01-01;true\nmisc;;;;false\n"
    )


def test_results_in_a_column_that_declares_no_number_type(tmp_path):
    # v1 writes Python's Decimals here: 2.20, 5.333333333333333333333333333, 0 for the empty sum, 7.00.
    config = by_dept(op("avg", "qty", "a"), op("sum", "price", "s"), op("avg", "amt", "m"))
    assert v2(tmp_path, config, data=ROWS.replace(b"food;;;;", b"food;;10;;"), written=None) == (
        b"dept;a;s;m\ntoys;2.5;4.4;2.2\nfood;5.333333333333333;2.3;0.85\nmisc;;0.0;7.0\n"
    )


def test_a_float_that_is_not_a_number_is_a_missing_value(tmp_path):
    # No file holds one: a file input reads the text NaN as a missing value. Rows written in the config can.
    # As a group value it is the missing value too: its row is in the group of the rows that miss it.
    registry = Registry()
    for cls in (stand_ins.Rows, stand_ins.Save, REGISTRY.get("aggregate_row")):
        registry.register(cls)
    nan = float("nan")
    config = {"groupbys": [{"input_column": "k"}],
              "operations": [op("count", "x", "n"), op("sum", "x", "s"), op("list", "g", "l"),
                             op("max", "x", "strict", ignore_null=False)]}
    made = stand_ins.job(
        [("in", "rows", {"data": {"g": ["a", "a", "b", "c"], "x": [1.5, nan, nan, 2.0], "k": [1.0, 1.0, nan, 2.0]}}),
         ("it", "aggregate_row", config), ("out", "save", {"path": str(tmp_path / "out.csv")})],
        [("row1", "in", "it", "flow"), ("row2", "it", "out", "flow")],
    )
    assert run_job(made, registry=registry).status == "success"
    assert stand_ins.lines(tmp_path / "out.csv") == [
        "k,n,s,l,strict", '1.0,1,1.5,"a,a",', ",0,0.0,b,", "2.0,1,2.0,c,2.0"]


# ------------------------------------------------------------------
# What v2 says no to, and what it lets pass
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "config, said",
    [
        ({}, "nothing to aggregate"),
        (by_dept(op("distinct", "qty")), "operations[0].function"),
        (by_dept(op("sum", "nope")), "there is no column 'nope'"),
        (by("nope", op("sum", "qty")), "there is no column 'nope'"),
        (by_dept(op("sum", "item")), "sum needs a column of numbers"),
        (by_dept(op("avg", "day")), "avg needs a column of numbers"),
        (by_dept(op("std", "ok")), "std needs a column of numbers"),
        (by_dept(op("median", "item")), "median needs a column of numbers"),
        (by_dept(op("count", "qty", "dept")), "'dept' is also a group column"),
        ({"groupbys": [group("dept"), group("item", "dept")], "operations": [op("count", "qty")]},
         "two group columns are named 'dept'"),
        (by_dept({"function": "sum", "output_column": "r"}), "operations[0].input_column"),
        (by_dept({"input_column": "qty", "output_column": "r"}), "operations[0].function"),
        (by_dept(dict(op("sum", "qty"), bogus=1)), "operations[0].bogus"),
        ({"groupbys": [{"output_column": "dept"}], "operations": [op("sum", "qty")]}, "groupbys[0].input_column"),
        (by_dept(op("sum", "qty"), bogus=1), "bogus"),
        ({"groupbys": "dept", "operations": [op("sum", "qty")]}, "groupbys"),
        (by_dept(op("sum", "qty"), use_financial_precision="maybe"), "use_financial_precision"),
    ],
)
def test_refused_config(config, said):
    assert said in refused(config)


def test_reject_output_does_not_exist():
    made = aggregate(by_dept(op("sum", "qty")))
    made["flows"][1]["type"] = "reject"
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    assert "no 'reject' output" in caught.value.report.format()


def test_keys_v1_ignores_are_accepted():
    load_job(aggregate({
        "groupbys": [group("dept")], "operations": [dict(op("list", "item"), delimiter=",")], "list_delimiter": ",",
        "use_financial_precision": True, "check_type_overflow": True, "check_ulp": True, "tstatcatcher_stats": False,
        "label": "Aggregate_By_Dept",
    }))


def converted_sample():
    """The job of this file's tests, around the component the converter wrote for its tAggregateRow sample."""
    sample = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tAggregateRow_0.1.json"
    converted = next(c for c in json.loads(sample.read_text())["components"] if c["type"] == "AggregateRow")
    made = aggregate(converted["config"])
    made["components"][0]["schema"]["output"] = converted["schema"]["input"]
    made["components"][1]["schema"] = converted["schema"]
    made["components"][2]["schema"]["input"] = converted["schema"]["output"]
    return made


def test_the_converters_sample_loads():
    load_job(converted_sample())


def test_the_converters_sample_gives_what_v1_gives(tmp_path):
    data = (b"toys;ball;19.99;3;2024-01-03\nfood;rice;2.45;10;2024-01-01\ntoys;kite;0.01;1;2024-01-02\n"
            b"food;salt;0.1;7;2024-01-05\nfood;tea;0.2;1;2024-01-06\n")
    run = assert_matches_v1(converted_sample(), {"in.csv": data}, tmp_path)
    assert run.files["out.csv"] == (
        b"department;total_sales;num_transactions;avg_sale;min_sale;max_sale;total_quantity\n"
        b"toys;20.0;2;10.0;0.01;19.99;4\nfood;2.75;3;0.9166666666666666;0.1;2.45;18\n"
    )
