"""Fixed flow input, against v1 on the same job config and bytes."""
import json
import os
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import columns, flow, job, writer

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tFixedFlowInput_0.1.json"
SCHEMA = "id:int, name:str, amt:float"


def fixed(schema=SCHEMA, out=None, context=None, kind="FixedFlowInputComponent", **config):
    """rows written in the config -> file."""
    source = {"id": "in", "type": kind, "config": config,
              "schema": {"input": [], "output": columns(schema)}, "inputs": [], "outputs": ["row1"]}
    made = job([source, writer(out or schema, inputs=("row1",))], [flow("row1", "in", "out")])
    if context:
        made["context"] = {"Default": {name: {"value": value, "type": "str"} for name, value in context.items()}}
    return made


def values(**held):
    return [{"schema_column": name, "value": value} for name, value in held.items()]


def table(*rows, names=("id", "name", "amt")):
    return [{"element_ref": name, "value": value} for row in rows for name, value in zip(names, row)]


def same(tmp_path, **kwargs):
    run = assert_matches_v1(fixed(**kwargs), {}, tmp_path)
    assert run.succeeded, run.error
    return run.files["out.csv"].decode().splitlines()[1:]


def v2(tmp_path, made):
    """Run on v2 alone, inside tmp_path; returns how it ended and the file written."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    written = (tmp_path / "out.csv").read_bytes() if (tmp_path / "out.csv").exists() else None
    return result, written


def inline(content, **more):
    return dict(use_singlemode=False, use_inlinecontent=True, inline_content=content, **more)


def test_one_row_of_values_is_repeated(tmp_path):
    assert same(tmp_path, nb_rows=3, values_config=values(id="7", name="ann", amt="1.5")) == ["7;ann;1.5"] * 3


def test_one_row_by_default_and_none_when_asked_for_none(tmp_path):
    assert same(tmp_path, values_config=values(id="7", name="ann", amt="2")) == ["7;ann;2"]
    assert same(tmp_path / "b", nb_rows=0, values_config=values(id="7")) == []


def test_column_without_a_value_is_missing(tmp_path):
    assert same(tmp_path, values_config=values(name="x")) == [";x;"]


def test_table_gives_a_row_for_every_run_of_as_many_entries_as_there_are_columns(tmp_path):
    rows = table(("1", "ann", "1.5"), ("2", "bob", "2.25"), ("3", "", ""))
    assert same(tmp_path, use_singlemode=False, use_intable=True, intable=rows, nb_rows=9) == [
        "1;ann;1.5", "2;bob;2.25", "3;;"]


def test_table_whose_last_row_is_short_and_an_entry_for_no_column(tmp_path):
    rows = table(("1", "ann", "1.5")) + [{"element_ref": "id", "value": "2"}, {"element_ref": "nope", "value": "x"}]
    assert same(tmp_path, use_singlemode=False, use_intable=True, intable=rows) == ["1;ann;1.5", "2;;"]


def test_inline_content_gives_a_row_for_every_line_that_is_not_blank(tmp_path):
    assert same(tmp_path, **inline("1;ann;1.5\n\n2;bob\n   \n3;cy;3;extra\n", nb_rows=1)) == [
        "1;ann;1.5", "2;bob;", "3;cy;3.0"]


@pytest.mark.parametrize("rows, fields, content", [
    ("\\r\\n", "\\t", "1\tann\t1.5\r\n2\tbob\t2"), ("|", ",", "1,ann,1.5|2,bob,2"), ("\\|", "::", "1::ann::1.5|2::bob::2"),
])
def test_separators_of_inline_content(tmp_path, rows, fields, content):
    assert same(tmp_path, **inline(content, row_separator=rows, field_separator=fields)) == ["1;ann;1.5", "2;bob;2.0"]


def test_line_end_the_separator_does_not_take_stays_in_the_last_field(tmp_path):
    run = assert_matches_v1(fixed(schema="id:int, name:str", **inline("1;ann\r\n2;bob")), {}, tmp_path)
    assert run.files["out.csv"] == b"id;name\n1;ann\r\n2;bob\n"


def test_inline_content_wins_over_the_table_and_the_table_over_the_single_row(tmp_path):
    config = dict(inline("1;a;1"), use_intable=True, intable=table(("2", "b", "2")), values_config=values(id="3"))
    assert same(tmp_path, **config) == ["1;a;1"]
    assert same(tmp_path / "b", **dict(config, use_inlinecontent=False, use_singlemode=True)) == ["2;b;2"]


def test_no_way_chosen_is_the_single_row(tmp_path):
    assert same(tmp_path, use_singlemode=False, values_config=values(id="5", name="x")) == ["5;x;"]


def test_plain_number_written_as_text_is_the_number_also_in_a_text_column(tmp_path):
    got = same(tmp_path, schema="a:str, b:str, c:str, d:str", values_config=values(a="007", b="1.50", c="-3", d="1e3"))
    assert got == ["7;1.5;-3;1e3"]


def test_column_of_numbers_and_text_is_written_as_each_stands(tmp_path):
    assert same(tmp_path, schema="a:str", out="a:str", **inline("1\nx\n2.5")) == ["1", "x", "2.5"]


def test_context_value_in_a_value_and_in_the_content(tmp_path):
    assert same(tmp_path, context={"who": "ann", "n": "42"},
                values_config=values(id="${context.n}", name="context.who")) == ["42;ann;"]
    assert same(tmp_path / "b", context={"who": "ann"}, **inline("1;${context.who};2")) == ["1;ann;2"]


def test_typed_columns(tmp_path):
    schema = "d:datetime@%Y-%m-%d, ok:bool, m:Decimal#2, f:float"
    got = same(tmp_path, schema=schema, **inline("2024-01-31;true;1.5;2.5\n2024-02-01;;2;3\n"))
    assert got == ["2024-01-31;true;1.50;2.5", "2024-02-01;false;2.00;3.0"]


def test_true_or_false_with_nothing_written_is_false_as_for_every_reader(tmp_path):
    assert same(tmp_path, schema="id:int, ok:bool", **inline("1;true\n2;\n3;0\n4")) == [
        "1;true", "2;false", "3;false", "4;false"]
    assert same(tmp_path / "b", schema="id:int, ok:bool", values_config=values(id="1")) == ["1;false"]


def test_the_text_false_is_false(tmp_path):
    # v1 takes any text that is not empty for true here, the words false and no among it.
    result, written = v2(tmp_path, fixed(schema="id:int, ok:bool", **inline("1;false\n2;FALSE\n3;true\n")))
    assert result.status == "success" and written == b"id;ok\n1;false\n2;false\n3;true\n"


def test_value_can_be_an_entry_of_globalmap_set_by_an_earlier_stage(tmp_path):
    # Stage one reads two rows; stage two writes how many they were. v1 counts the same.
    from .kit import reader
    made = fixed(schema="n:int", values_config=values(n='((Integer)globalMap.get("first_NB_LINE"))'))
    made["components"] += [reader("id:int", "first", "first.csv", ("row9",)), writer("id:int", "copy", "copy.csv", ("row9",))]
    made["flows"].append(flow("row9", "first", "copy"))
    made["triggers"] = [{"type": "OnSubjobOk", "from": "first", "to": "in"}]
    run = assert_matches_v1(made, {"first.csv": b"1\n2\n"}, tmp_path)
    assert run.succeeded, run.error
    assert run.files["out.csv"] == b"n\n2\n"


def after_entries(made, **held):
    """The job, run after a stage that puts these entries into globalMap."""
    made["components"].insert(0, {"id": "set", "type": "SetGlobalVar",
                                  "config": {"variables": [{"key": key, "value": value} for key, value in held.items()]}})
    made["triggers"] = [{"type": "OnSubjobOk", "from": "set", "to": "in"}]
    return made


LOOKED_UP = ['globalMap.get("k")', '((String)globalMap.get("k"))', '{{java}}((String)globalMap.get("k"))',
             '{{java}}"" + ((String)globalMap.get("k"))']
WAYS = ["plain", "with a cast", "as the converter marks it", "joined to text"]


@pytest.mark.parametrize("written", LOOKED_UP, ids=WAYS)
def test_what_an_entry_of_globalmap_holds_is_handed_on_as_it_is_and_is_not_read_as_a_number(tmp_path, written):
    # An account number keeps its zeros: what was looked up is data. What is written in the config itself is
    # still read as v1 reads it (007 is 7).
    made = after_entries(fixed(schema="acct:str, amt:str", values_config=values(acct=written, amt="007")), k="00123")
    result, got = v2(tmp_path, made)
    assert result.status == "success", result.error
    assert got == b"acct;amt\n00123;7\n"


@pytest.mark.parametrize("written", LOOKED_UP[:2], ids=WAYS[:2])
def test_v1_hands_an_entry_on_as_it_is_too(tmp_path, written):
    made = after_entries(fixed(schema="acct:str, amt:str", values_config=values(acct=written, amt="007")), k="00123")
    run = assert_matches_v1(made, {}, tmp_path)
    assert run.succeeded, run.error
    assert run.files["out.csv"] == b"acct;amt\n00123;7\n"


@pytest.mark.parametrize("written", LOOKED_UP, ids=WAYS)
def test_entry_is_handed_on_as_it_is_in_a_table_and_as_the_whole_inline_content_too(tmp_path, written):
    in_table = fixed(schema="a:str, b:str", use_singlemode=False, use_intable=True,
                     intable=table((written, "007"), names=("a", "b")))
    result, got = v2(tmp_path / "table", after_entries(in_table, k="00123"))
    assert result.status == "success" and got == b"a;b\n00123;7\n"
    result, got = v2(tmp_path / "inline", after_entries(fixed(schema="a:str, b:str", **inline(written)), k="2.50"))
    assert result.status == "success" and got == b"a;b\n2.50;\n"


def test_entry_named_in_a_field_of_the_inline_content_is_handed_on_as_it_is_as_in_v1(tmp_path):
    # A line of several fields is no one value the engine looks up: the component reads each field, as v1 does.
    made = after_entries(fixed(schema="a:str, b:str", **inline('globalMap.get("k");007\n((String)globalMap.get("k"));x')),
                         k="00123")
    run = assert_matches_v1(made, {}, tmp_path)
    assert run.succeeded, run.error
    assert run.files["out.csv"] == b"a;b\n00123;7\n00123;x\n"


def test_entry_that_holds_nothing_is_a_missing_value(tmp_path):
    # v1 writes the reference's own text there: `globalMap.get("k")`, as data.
    made = after_entries(fixed(schema="v:str, w:str", values_config=values(v='globalMap.get("k")', w="x")), k=None)
    result, got = v2(tmp_path, made)
    assert result.status == "success" and got == b"v;w\n;x\n"


def test_value_that_is_not_of_the_declared_type_goes_missing(tmp_path):
    # v1 writes such values through as they are (abc in a Decimal column, 1.5 in a whole-number column),
    # <NA> for a missing Decimal, and 3.0 for a whole number beside a missing one. A date written day first
    # is read under a pattern that has the year first, as v1 reads it.
    made = fixed(schema="m:Decimal#2, n:int, d:datetime@%Y-%m-%d", **inline("1.5;3;2024-01-31\nabc;1.5;31/01/2024\n;;\n"))
    result, written = v2(tmp_path, made)
    assert result.status == "success" and written == b"m;n;d\n1.50;3;2024-01-31\n;1;2024-01-31\n;;\n"


def test_no_columns_declared_refuses_the_job():
    made = fixed(values_config=[])
    made["components"][0]["schema"]["output"] = []
    with pytest.raises(JobRefusedError, match="schema: a fixed flow input needs its columns declared"):
        load_job(made)


@pytest.mark.parametrize("config, said", [
    ({"nb_rows": -1}, "nb_rows"), ({"nb_rows": "many"}, "nb_rows"), ({"rows": 3}, "unknown config key"),
    ({"field_separator": ""}, "a separator of nothing"),
])
def test_what_cannot_be_read_refuses_the_job(config, said):
    with pytest.raises(JobRefusedError, match=said):
        load_job(fixed(**config))


def test_converters_sample_loads_and_runs_as_on_v1(tmp_path):
    spec = next(c for c in json.loads(SAMPLE.read_text())["components"] if "Fixed" in c["type"])
    made = fixed(**spec["config"])
    made["components"][0]["schema"] = spec["schema"]
    made["components"][1]["schema"]["input"] = spec["schema"]["output"]
    run = assert_matches_v1(made, {}, tmp_path)
    assert run.succeeded and len(run.files["out.csv"].splitlines()) == 6


def test_die_on_error_is_the_engines_as_on_every_component():
    load_job(fixed(values_config=values(id="1"), die_on_error=False))


# ------------------------------------------------------------------
# What a second reader of this component found (ticket 65)
# ------------------------------------------------------------------

@pytest.mark.parametrize("schema, content, got", [
    ("d:datetime@%Y%m%d, s:str", "20240131;a\n20240201;b\n", ["20240131;a", "20240201;b"]),
    ("t:datetime@%H%M, s:str", "1030;a\n", ["1030;a"]),
    ("s:str", "12345678901234567890\n1\n", ["12345678901234567890", "1"]),
    ("m:Decimal#2", "12345678901234567890\n1\n", ["12345678901234567890.00", "1.00"]),
], ids=["a date written in digits", "a time written in digits", "a number too long for a whole number, as text",
        "the same as a Decimal"])
def test_digits_in_a_column_that_is_no_number_column(tmp_path, schema, content, got):
    assert same(tmp_path, schema=schema, **inline(content)) == got


def test_single_row_of_digits_in_a_date_column(tmp_path):
    assert same(tmp_path, schema="d:datetime@%Y%m%d", values_config=values(d="20240131")) == ["20240131"]


def test_whole_number_too_long_for_64_bits_goes_missing_in_a_whole_number_column(tmp_path):
    # v2 holds whole numbers in 64 bits. v1 writes this one through; in a text or Decimal column so does v2.
    result, written = v2(tmp_path, fixed(schema="n:int", **inline("12345678901234567890\n7\n")))
    assert result.status == "success" and written == b"n\n\n7\n"


def test_true_or_false_that_may_not_be_missing_is_false_when_nothing_is_given(tmp_path):
    # Ticket 71: as v1 has it, for a column that may be missing and for one that may not.
    assert same(tmp_path, schema="id:int, ok:bool!", **inline("1;true\n2;\n3;0\n")) == ["1;true", "2;false", "3;false"]
