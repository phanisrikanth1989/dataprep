"""Normalize, against v1 on the same job config and bytes."""
import json
from pathlib import Path

import pytest

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import through

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tNormalize_0.1.json"

SCHEMA = "id:int, tags:str"
# One value, several, none, empty ones between and after, blanks around, nothing but separators.
DATA = b"id;tags\n1;a,b,c\n2;\n3;x\n4;p,,q,,\n5; m , n ,m\n6;,,\n"


def normalize_job(schema=SCHEMA, out=None, column="tags", **config):
    """file -> normalize -> file."""
    return through({"type": "Normalize", "config": {"normalize_column": column, **config}}, schema, out)


def same(tmp_path, data=DATA, fails=False, **kwargs):
    """Both engines do the same with the job; ``fails`` says the job is one neither finishes."""
    run = assert_matches_v1(normalize_job(**kwargs), {"in.csv": data}, tmp_path)
    assert run.succeeded is not fails, run.error
    return run


def rows(run):
    return run.files["out.csv"].decode().splitlines()[1:]


# ------------------------------------------------------------------
# One row for each value
# ------------------------------------------------------------------

def test_each_value_of_the_cell_becomes_a_row_and_the_other_columns_are_repeated(tmp_path):
    assert rows(same(tmp_path)) == [
        "1;a", "1;b", "1;c", "2;", "3;x", "4;p", "4;", "4;q", "4;", "4;", "5; m ", "5; n ", "5;m", "6;", "6;", "6;",
    ]


def test_trim_strips_each_value(tmp_path):
    assert rows(same(tmp_path, trim=True))[10:13] == ["5;m", "5;n", "5;m"]


def test_discard_drops_the_empty_values_a_cell_ends_on_and_keeps_the_ones_inside(tmp_path):
    assert rows(same(tmp_path, discard_trailing_empty_str=True)) == [
        "1;a", "1;b", "1;c", "3;x", "4;p", "4;", "4;q", "5; m ", "5; n ", "5;m",
    ]


def test_deduplicate_keeps_the_first_of_each_value_in_a_cell(tmp_path):
    assert rows(same(tmp_path, deduplicate=True)) == [
        "1;a", "1;b", "1;c", "2;", "3;x", "4;p", "4;", "4;q", "5; m ", "5; n ", "5;m", "6;",
    ]


def test_discard_then_trim_then_deduplicate(tmp_path):
    run = same(tmp_path, trim=True, discard_trailing_empty_str=True, deduplicate=True)
    assert rows(run) == ["1;a", "1;b", "1;c", "3;x", "4;p", "4;", "4;q", "5;m", "5;n"]


def test_value_of_blanks_is_not_empty_until_it_is_trimmed(tmp_path):
    # Empty values are discarded before the trim, so a blank one stays and comes out empty.
    run = same(tmp_path, b"id;tags\n1;a, , \n2; \n", trim=True, discard_trailing_empty_str=True)
    assert rows(run) == ["1;a", "1;", "1;", "2;"]


@pytest.mark.parametrize("separator, data, want", [
    ("|", b"id;tags\n1;a|b.c\n", ["1;a", "1;b.c"]),
    (".", b"id;tags\n1;a|b.c\n", ["1;a|b", "1;c"]),
    ("--", b"id;tags\n1;a--b---c\n", ["1;a", "1;b", "1;-c"]),
    (" ", b"id;tags\n1;a b  c\n", ["1;a", "1;b", "1;", "1;c"]),
    ("$", b"id;tags\n1;a$b$\n", ["1;a", "1;b", "1;"]),
])
def test_separator_is_taken_as_it_is_written(tmp_path, separator, data, want):
    assert rows(same(tmp_path, data, itemseparator=separator)) == want


def test_separator_of_several_characters_with_discard(tmp_path):
    run = same(tmp_path, b"id;tags\n1;a--b----\n2;----\n", itemseparator="--", discard_trailing_empty_str=True)
    assert rows(run) == ["1;a", "1;b"]


def test_no_rows(tmp_path):
    assert rows(same(tmp_path, b"id;tags\n")) == []


def test_rows_keep_their_order(tmp_path):
    data = b"id;tags\n" + b"".join(b"%d;v%d,w%d\n" % (n, n, n) for n in range(1, 2001))
    out = rows(same(tmp_path, data))
    assert out[:2] == ["1;v1", "1;w1"] and out[-2:] == ["2000;v2000", "2000;w2000"] and len(out) == 4000


# ------------------------------------------------------------------
# Types
# ------------------------------------------------------------------

def test_values_take_the_type_the_output_declares(tmp_path):
    assert rows(same(tmp_path, b"id;tags\n1;1,2,3\n", out="id:int, tags:int")) == ["1;1", "1;2", "1;3"]


@pytest.mark.parametrize("kind, data, want", [
    ("int", b"id;tags\n1;12\n2;\n", ["1;12", "2;"]),
    ("float", b"id;tags\n1;1.5\n2;2\n", ["1;1.5", "2;2.0"]),
])
def test_column_that_is_a_number_is_split_as_its_text(tmp_path, kind, data, want):
    assert rows(same(tmp_path, data, schema=f"id:int, tags:{kind}")) == want


# ------------------------------------------------------------------
# What stops the job
# ------------------------------------------------------------------

def test_column_that_is_not_there_fails_on_both(tmp_path):
    same(tmp_path, column="nope", fails=True)
    with pytest.raises(JobRefusedError) as caught:
        load_job(normalize_job(column="nope"))
    assert "there is no column 'nope' to normalize" in caught.value.report.format()


def test_column_of_dates_is_refused():
    # v1 splits the text pandas prints for a date; v2 does not guess at that text.
    with pytest.raises(JobRefusedError) as caught:
        load_job(normalize_job(schema="id:int, tags:datetime@%Y-%m-%d"))
    assert "'tags' holds dates" in caught.value.report.format()


def test_empty_separator_fails_on_both(tmp_path):
    same(tmp_path, itemseparator="", fails=True)
    with pytest.raises(JobRefusedError) as caught:
        load_job(normalize_job(itemseparator=""))
    assert "itemseparator" in caught.value.report.format()


# ------------------------------------------------------------------
# Keys the converter writes
# ------------------------------------------------------------------

def test_enclosure_keys_change_nothing_as_in_v1(tmp_path):
    run = same(tmp_path, b'id;tags\n1;"a,b",c\n', csv_option=True, text_enclosure='"', escape_char="ESCAPE_MODE_DOUBLED")
    assert rows(run) == ['1;"a', '1;b"', "1;c"]


def test_converted_sample_job_is_not_refused_for_its_normalize():
    made = json.loads(SAMPLE.read_text())
    try:
        load_job(made)
    except JobRefusedError as refused:
        assert not [refusal for refusal in refused.report if "tNormalize_1" in refusal.where]
