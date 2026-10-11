"""Aggregate sorted row: against v1 on sorted rows, and as Talend has it where the rows are not sorted."""
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2 import answer_key
from tests.v2.answer_key import assert_matches_v1

from .kit import through
from .test_aggregate_row import FUNCTIONS, group, op, v1_keeping

SCHEMA = "dept:str, item:str, qty:int, amt:Decimal#2"
# Sorted by dept; one row of "food" misses its numbers.
SORTED = b"dept;item;qty;amt\nfood;rice;1;2.20\nfood;;;0.25\nfood;salt;5;0.10\nmisc;x;7;7.00\ntoys;ball;3;1.10\ntoys;kite;2;3.30\n"


def sorted_job(config, schema=SCHEMA, out=None, kind="AggregateSortedRow"):
    return through({"type": kind, "config": config}, schema, out)


def by_dept(*operations, **more):
    return {"groupbys": [group("dept")], "operations": list(operations), **more}


def same(tmp_path, config, data=SORTED, **kwargs):
    run = assert_matches_v1(sorted_job(config, **kwargs), {"in.csv": data}, tmp_path)
    assert run.succeeded, run.error
    return run.files["out.csv"]


def v2(tmp_path, config, data, **kwargs):
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(sorted_job(config, **kwargs))
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    return (tmp_path / "out.csv").read_bytes()


def test_sorted_rows_give_one_row_for_each_group(tmp_path):
    written = same(tmp_path, by_dept(op("sum", "qty", "total"), op("count", "item", "n")), out="dept:str, total:int, n:int")
    assert written == b"dept;total;n\nfood;6;3\nmisc;7;1\ntoys;5;2\n"


@pytest.mark.parametrize("function", [name for name in FUNCTIONS if name not in ("list_object",)])
def test_every_function_of_the_aggregate(tmp_path, function):
    numbers = function in ("avg", "sum", "std", "population_std_dev", "median", "variance", "min", "max")
    out = "dept:str, r:float" if numbers else "dept:str, r:int" if "count" in function else "dept:str, r:str"
    same(tmp_path, by_dept(op(function, "qty")), out=out)


def test_several_group_columns_and_a_renamed_one(tmp_path):
    data = b"dept;item;qty;amt\na;x;1;1.00\na;x;2;1.00\na;y;3;1.00\nb;x;4;1.00\n"
    config = {"groupbys": [group("dept", "d"), group("item")], "operations": [op("sum", "qty", "total")]}
    assert same(tmp_path, config, data, out="d:str, item:str, total:int") == b"d;item;total\na;x;3\na;y;3\nb;x;4\n"


def test_no_group_columns_is_one_row(tmp_path):
    assert same(tmp_path, {"operations": [op("sum", "qty", "total")]}, out="total:int") == b"total\n18\n"


def test_list_delimiter_and_row_count_and_financial_precision_as_in_v1(tmp_path):
    config = by_dept(op("list", "item", "items"), op("avg", "amt", "mean"), list_delimiter="|", row_count="6",
                     use_financial_precision=False)
    same(tmp_path, config, out="dept:str, items:str, mean:float")


def test_rows_that_are_not_sorted_give_a_group_for_each_run_as_in_talend(tmp_path):
    # v1 groups the whole input and writes a;4 and b;2. Talend compares each row with the one before it.
    data = b"dept;item;qty;amt\na;x;1;1.00\nb;x;2;1.00\na;y;3;1.00\n"
    written = v2(tmp_path, by_dept(op("sum", "qty", "total")), data, out="dept:str, total:int")
    assert written == b"dept;total\na;1\nb;2\na;3\n"


def test_rows_that_miss_the_group_value_are_a_group_where_they_stand(tmp_path):
    # As in Talend, where two missing values are the same value. v1 leaves such rows out (ticket 51).
    data = b"k;qty\n1;1\n;2\n;40\n2;5\n"
    made = sorted_job({"groupbys": [group("k")], "operations": [op("sum", "qty", "total")]}, schema="k:int, qty:int",
                      out="k:int, total:int")
    # The answer key is v1 with pandas told to keep such rows, as for the aggregate row.
    key = answer_key.run_job(made, {"in.csv": data}, tmp_path / "v1", v1_keeping)
    actual = answer_key.run_job(made, {"in.csv": data}, tmp_path / "v2", answer_key.run_v2)
    assert answer_key.differences(key, actual) == [] and actual.files["out.csv"] == b"k;total\n1;1\n;42\n2;5\n"


def test_no_rows_in(tmp_path):
    assert same(tmp_path, by_dept(op("sum", "qty", "total")), b"dept;item;qty;amt\n", out="dept:str, total:int") == b"dept;total\n"


def test_operations_are_needed():
    with pytest.raises(JobRefusedError, match="operations: an aggregate of sorted rows needs at least one"):
        load_job(sorted_job({"groupbys": [group("dept")]}))


def test_talend_name_and_a_key_it_does_not_know():
    load_job(sorted_job(by_dept(op("sum", "qty", "t")), kind="tAggregateSortedRow"))
    with pytest.raises(JobRefusedError, match="unknown config key"):
        load_job(sorted_job(by_dept(op("sum", "qty", "t"), sorted=True)))


# ------------------------------------------------------------------
# What a second reader of this component found (ticket 65)
# ------------------------------------------------------------------

def test_die_on_error_is_the_engines_as_on_every_component(tmp_path):
    written = same(tmp_path, by_dept(op("sum", "qty", "total"), die_on_error=False), out="dept:str, total:int")
    assert written == b"dept;total\nfood;6\nmisc;7\ntoys;5\n"
    from .test_aggregate_row import aggregate
    assert_matches_v1(aggregate(by_dept(op("sum", "qty", "total"), die_on_error=False), schema=SCHEMA,
                                out="dept:str, total:int"), {"in.csv": SORTED}, tmp_path / "plain")


def test_column_may_be_named_like_anything_a_job_may_name_one(tmp_path):
    data = b"__sorted_run;qty\na;1\na;2\nb;3\n"
    config = {"groupbys": [group("__sorted_run")], "operations": [op("sum", "qty", "total")]}
    assert same(tmp_path, config, data, schema="__sorted_run:str, qty:int", out="__sorted_run:str, total:int") == (
        b"__sorted_run;total\na;3\nb;3\n")
