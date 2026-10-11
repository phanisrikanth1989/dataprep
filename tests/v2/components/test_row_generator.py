"""Row generator, against v1 on the same job config."""
import json
import logging
import os
import random
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1, run_v2

from .kit import columns, flow, job, writer

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tRowGenerator_0.1.json"
SCHEMA = "id:int, name:str, amt:float"


def generator(schema=SCHEMA, out=None, context=None, reject=None, kind="RowGenerator", **config):
    """rows made from expressions -> file, and the rows turned away -> rej.csv when `reject` names its columns."""
    source = {"id": "in", "type": kind, "config": config, "inputs": [],
              "schema": {"input": [], "output": columns(schema)}, "outputs": ["row1"] + (["bad"] if reject else [])}
    parts, flows = [source, writer(out or schema, inputs=("row1",))], [flow("row1", "in", "out")]
    if reject:
        parts.append(writer(reject, component_id="rej", path="rej.csv", inputs=("bad",)))
        flows.append(flow("bad", "in", "rej", kind="reject"))
    made = job(parts, flows)
    if context:
        made["context"] = {"Default": {name: {"value": value, "type": "str"} for name, value in context.items()}}
    return made


def values(**held):
    return [{"schema_column": name, "array": text} for name, text in held.items()]


def seeded(runner, seed):
    """A runner that starts Python's random numbers at the same place every time."""
    def run(made):
        random.seed(seed)
        return runner(made)
    return run


def same(tmp_path, seed=5, **kwargs):
    random.seed(seed)
    run = assert_matches_v1(generator(**kwargs), {}, tmp_path, run_v2=seeded(run_v2, seed))
    assert run.succeeded, run.error
    return run.files["out.csv"].decode().splitlines()[1:]


def v2(tmp_path, made, seed=5):
    """Run on v2 alone, inside tmp_path; returns how it ended and the lines of each file written."""
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        random.seed(seed)
        result = run_job(made)
    finally:
        os.chdir(previous)
    return result, {path.name: path.read_text().splitlines() for path in sorted(tmp_path.glob("*.csv"))}


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# How many rows, and what each column holds
# ------------------------------------------------------------------

def test_every_row_holds_what_its_expressions_come_to(tmp_path):
    assert same(tmp_path, nb_rows="3", values=values(id="1+2", name="hello", amt="1.5")) == ["3;hello;1.5"] * 3


def test_a_hundred_rows_when_no_number_is_given_and_none_when_asked_for_none(tmp_path):
    assert same(tmp_path, values=values(id="1", name="x")) == ["1;x;"] * 100
    assert same(tmp_path / "b", nb_rows=0, values=values(id="1")) == []


def test_number_of_rows_as_a_number_or_from_the_context(tmp_path):
    assert same(tmp_path, nb_rows=2, values=values(id="7")) == ["7;;"] * 2
    assert same(tmp_path / "b", context={"n": "2"}, nb_rows="${context.n}", values=values(id="7")) == ["7;;"] * 2
    assert same(tmp_path / "c", context={"n": "2"}, nb_rows="context.n", values=values(id="7")) == ["7;;"] * 2


@pytest.mark.parametrize("asked, said", [
    ("-1", "-1 rows cannot be made; give 0 or more"),
    ("many", "'many' is not a whole number of rows"),
    ([3], "[3] is not a whole number of rows"),
])
def test_number_of_rows_that_is_none_refuses_the_job(asked, said):
    assert refusals(generator(nb_rows=asked, values=values(id="1"))) == [("nb_rows", said)]


def test_column_with_no_expression_is_missing(tmp_path):
    assert same(tmp_path, nb_rows=2, values=values(name="x")) == [";x;"] * 2
    assert same(tmp_path / "b", nb_rows=1, values=[{"schema_column": "name"}, {"schema_column": "id", "array": 5}]) == ["5;;"]


def test_text_that_is_not_python_is_the_value_itself(tmp_path):
    got = same(tmp_path, schema="a:str, b:str, c:str, d:str", nb_rows=1,
               values=values(a="hello world", b="007", c="  spaced  ", d="'unterminated"))
    assert got == ["hello world;007;spaced;'unterminated"]


def test_blanks_in_front_of_an_expression_do_not_make_it_text(tmp_path):
    assert same(tmp_path, schema="a:int, b:str", nb_rows=1, values=values(a="  1 + 2", b="\t'x' * 2 ")) == ["3;xx"]


def test_quotes_around_text_are_not_part_of_it(tmp_path):
    got = same(tmp_path, schema="a:str, b:str, c:str", nb_rows=1, values=values(a="'a b'", b='"q"', c="\"it's\""))
    assert got == ["a b;q;it's"]


def test_quotes_around_text_that_is_not_python_are_not_part_of_it_either(tmp_path):
    got = same(tmp_path, schema="a:str, b:str, c:str", nb_rows=1, values=values(a="'don't'", b='"say "hi""', c="'mixed\""))
    assert got == ["don't;say \"hi\";'mixed\""]


def test_name_that_is_not_in_reach_makes_the_whole_text_the_value(tmp_path):
    # Only `random` is in reach: no len, no str.
    got = same(tmp_path, schema="a:str, b:str", nb_rows=1, values=values(a="len('abc')", b="str(5)"))
    assert got == ["len('abc');str(5)"]


def test_value_in_a_text_column_is_written_as_python_writes_it(tmp_path):
    got = same(tmp_path, schema="a:str, b:str, c:str, d:str, e:str", nb_rows=1,
               values=values(a="True", b="[1, 2]", c="1/3", d="1e20", e="(1, 'a')"))
    assert got == ["True;[1, 2];0.3333333333333333;1e+20;(1, 'a')"]


def test_none_is_a_missing_value(tmp_path):
    assert same(tmp_path, schema="a:int, b:str, c:float", nb_rows=1, values=values(a="None", b="None", c="None")) == [";;"]


def test_context_value_in_an_expression(tmp_path):
    got = same(tmp_path, context={"who": "ann", "n": "42"}, nb_rows=1,
               values=values(id="${context.n} + 1", name="context.who"))
    assert got == ["43;ann;"]


def test_space_and_len_of_string_handling(tmp_path):
    got = same(tmp_path, schema="a:str, b:int, c:str, d:str", nb_rows=1, values=values(
        a="'[' + StringHandling.SPACE(3) + ']'", b='StringHandling.LEN("abcd") + 1', c="StringHandling.LEN(xy)",
        d="'[' + StringHandling.SPACE(x) + ']'"))
    assert got == ["[   ];5;len(xy);[]"]


# ------------------------------------------------------------------
# Random values
# ------------------------------------------------------------------

RANDOM = dict(schema="a:int, b:float, c:str", nb_rows=4,
              values=values(a="random.randint(1, 100)", b="random.random()", c="random.choice(['x', 'y', 'z'])"))


def test_random_values_are_drawn_row_by_row_in_the_order_of_the_columns(tmp_path):
    # From the same start Python's random numbers come out the same, so v1's file is the answer key here too.
    first = same(tmp_path, seed=5, **RANDOM)
    assert len(set(first)) == 4
    assert same(tmp_path / "b", seed=6, **RANDOM) != first


def test_rows_of_a_run_are_made_once_however_often_the_source_is_read(tmp_path):
    # Picking rows reads the source to find them and then again to run them: both must see the same rows.
    whole = same(tmp_path, **RANDOM)
    (tmp_path / "b").mkdir()
    picked = dict(generator(**RANDOM), run={"only": {"source": "in", "rows": [3]}})
    result, files = v2(tmp_path / "b", picked)
    assert result.status == "success", result.error
    assert files["out.csv"][1:] == [whole[2]]


def test_expression_is_read_once_and_evaluated_for_every_row(tmp_path):
    result, files = v2(tmp_path, generator(schema="a:int", nb_rows=50, values=values(a="random.randint(1, 10**9)")))
    assert result.status == "success" and len(set(files["out.csv"][1:])) == 50


# ------------------------------------------------------------------
# Typed columns
# ------------------------------------------------------------------

TYPED = "d:datetime@%Y-%m-%d, ok:bool, m:Decimal#2, n:int!, f:float, s:str"


def test_typed_columns(tmp_path):
    got = same(tmp_path, schema=TYPED, nb_rows=2,
               values=values(d="2024-01-31", ok="True", m="1.5", n="3", f="2.5", s="007"))
    assert got == ["2024-01-31;true;1.50;3;2.5;007"] * 2


def test_typed_columns_from_quoted_text(tmp_path):
    got = same(tmp_path, schema=TYPED, nb_rows=1,
               values=values(d="'2024-01-31'", ok="true", m="'1.5'", n="'12'", f="", s=""))
    assert got == ["2024-01-31;true;1.50;12;;"]


def test_date_with_a_time_and_columns_with_no_pattern_or_places(tmp_path):
    got = same(tmp_path, schema="d:datetime, ok:bool!, n:int!", nb_rows=1,
               values=values(d="'2024-01-31 10:11:12'", ok="0", n="5"))
    assert got == ["2024-01-31 10:11:12;false;5"]


def test_true_or_false_with_nothing_given_is_false_as_for_every_reader(tmp_path):
    assert same(tmp_path, schema="id:int, ok:bool", nb_rows=1, values=values(id="1", ok="None")) == ["1;false"]
    # With no expression at all v1 writes <na>.
    (tmp_path / "b").mkdir()
    result, files = v2(tmp_path / "b", generator(schema="id:int, ok:bool", nb_rows=1, values=values(id="1")))
    assert result.status == "success" and files["out.csv"][1:] == ["1;false"]


def test_the_text_false_is_false(tmp_path):
    # v1 takes any text that is not empty for true here, the words false and no among it.
    result, files = v2(tmp_path, generator(schema="a:bool, b:bool, c:bool", nb_rows=1,
                                           values=values(a="'false'", b="no", c="False")))
    assert result.status == "success" and files["out.csv"][1:] == ["false;false;false"]


def test_value_that_is_not_of_its_columns_type_goes_missing(tmp_path):
    # v1 writes 1970-01-01 for the date and <NA> for the Decimal.
    made = generator(schema="a:int, d:datetime@%Y-%m-%d, m:Decimal#2", nb_rows=1, values=values(a="abc", d="20240131", m="None"))
    result, files = v2(tmp_path, made)
    assert result.status == "success" and files["out.csv"][1:] == [";;"]


def test_number_with_a_fraction_is_cut_in_a_whole_number_column_as_everywhere(tmp_path):
    # v1 writes 1.7 through here, though it cuts it wherever else a whole-number column is filled.
    result, files = v2(tmp_path, generator(schema="a:int, b:int", nb_rows=1, values=values(a="1.7", b="2.0")))
    assert result.status == "success" and files["out.csv"][1:] == ["1;2"]


def test_whole_number_in_a_float_or_decimal_column(tmp_path):
    got = same(tmp_path, schema="f:float, m:Decimal#2, g:float", nb_rows=1, values=values(f="3", m="2", g="1e3"))
    assert got == ["3;2.00;1000.0"]


def test_column_whose_rows_hold_numbers_and_text(tmp_path):
    made = dict(schema="a:int, b:str", nb_rows=40, values=values(a="random.choice([1, None])", b="random.choice([1, 'x', 2.5])"))
    result, files = v2(tmp_path, generator(**made), seed=3)
    assert result.status == "success"
    rows = [line.split(";") for line in files["out.csv"][1:]]
    assert {row[0] for row in rows} == {"1", ""} and {row[1] for row in rows} == {"1", "x", "2.5"}


def test_number_too_long_for_64_bits_is_kept_as_text(tmp_path):
    got = same(tmp_path, schema="a:str, b:str", nb_rows=1, values=values(a="12345678901234567890", b="10**30"))
    assert got == ["12345678901234567890;1000000000000000000000000000000"]


# ------------------------------------------------------------------
# An expression that fails
# ------------------------------------------------------------------

def test_row_whose_expression_fails_leaves_by_the_reject_output_with_the_column_empty(tmp_path):
    random.seed(1)
    made = generator(schema="id:int, name:str", reject="id:int, name:str", nb_rows=6,
                     values=values(id="10 // random.randint(0, 1)", name="'x'"))
    run = assert_matches_v1(made, {}, tmp_path, run_v2=seeded(run_v2, 1))
    kept, turned_away = (run.files[name].decode().splitlines()[1:] for name in ("out.csv", "rej.csv"))
    assert set(kept) == {"10;x"} and set(turned_away) == {";x"} and len(kept) + len(turned_away) == 6


def test_log_says_how_many_rows_failed_and_what_failed_in_the_first(tmp_path, caplog):
    made = generator(schema="id:int, name:str", reject="id:int, name:str", nb_rows=3,
                     values=values(id="1/0", name="'a' + 1"))
    with caplog.at_level(logging.INFO, logger="src.v2"):
        result, files = v2(tmp_path, made)
    assert result.status == "success", result.error
    assert files["out.csv"] == ["id;name"] and files["rej.csv"][1:] == [";"] * 3
    said = [record for record in caplog.records if "failed" in record.getMessage()]
    assert [(record.levelname, record.getMessage()) for record in said] == [("INFO", (
        "[in] an expression failed in 3 of 3 rows; the first is row 1: "
        'id: division by zero; name: can only concatenate str (not "int") to str'))]


def test_no_row_fails_and_the_reject_output_is_empty(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger="src.v2"):
        result, files = v2(tmp_path, generator(schema="id:int", reject="id:int", nb_rows=2, values=values(id="1")))
    assert result.status == "success" and files["rej.csv"] == ["id"] and files["out.csv"][1:] == ["1", "1"]
    assert not [record for record in caplog.records if "failed" in record.getMessage()]


def test_missing_value_where_none_is_allowed_fails_the_job_as_in_v1(tmp_path):
    made = generator(schema="a:int!, b:str", nb_rows=2, values=values(a="None", b="1"))
    assert_matches_v1(made, {}, tmp_path)
    result, _ = v2(tmp_path / "v2", made)
    assert result.status == "failed"
    assert result.error == "Column 'a' has NULL values but is not nullable; the row is row 1 of in"


def test_missing_value_where_none_is_allowed_drops_the_row_when_the_job_is_not_to_fail(tmp_path, caplog):
    made = generator(schema="a:int!, b:str", die_on_error=False, nb_rows=2, values=values(a="None", b="1"))
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result, files = v2(tmp_path, made)
    assert result.status == "success" and files["out.csv"] == ["a;b"]
    assert ["2 rows were dropped" in record.getMessage() for record in caplog.records] == [True]


# ------------------------------------------------------------------
# What is refused
# ------------------------------------------------------------------

def test_java_expression_is_refused():
    found = refusals(generator(values=values(id="{{java}}Numeric.sequence(\"s1\",1,1)", name="x")))
    assert len(found) == 1 and "values[0].array" in found[0][0] and "Java" in found[0][1]


def test_entry_for_no_column_and_two_for_one_are_refused():
    assert refusals(generator(values=values(id="1", nope="2"))) == [
        ("values[1].schema_column", "'nope' is not a column of the schema (id, name, amt)")]
    assert refusals(generator(values=values(id="1") + values(id="2"))) == [
        ("values[1].schema_column", "'id' already has an expression (values[0])")]


def test_values_have_to_be_given_and_the_columns_declared():
    assert [path for path, _ in refusals(generator())] == ["values"]
    made = generator(values=values(id="1"))
    made["components"][0]["schema"] = {"input": [], "output": []}
    assert ("schema", "a row generator needs its columns declared") in [
        (path.split(".")[-1], reason) for path, reason in refusals(made)]


def test_converted_sample_is_refused_for_its_java_alone():
    found = refusals(json.loads(SAMPLE.read_text()))
    assert found and all("Java" in reason for _, reason in found)


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("row_generator", "RowGenerator", "tRowGenerator")):
        folder = tmp_path / str(at)
        folder.mkdir()
        result, files = v2(folder, generator(kind=kind, nb_rows=1, values=values(id="1")))
        assert result.status == "success" and files["out.csv"][1:] == ["1;;"]
