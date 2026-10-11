"""Extract positional fields, against v1 on the same job config and bytes."""
import logging

import pytest

from src.v2 import load_job
from tests.v2.answer_key import assert_matches_v1

from .test_extract_delimited_fields import extract as extract_with, refusals, same as same_with, v2

OUT = "id:int, a:str, b:str, c:str"
DATA = b"id|raw\n1|abcdefghij\n2|abc\n3|abcdefghijklmn\n4|\n5| x  y z  \n"


def extract(**config):
    return extract_with(**{"kind": "ExtractPositionalFields", "pattern": "3,4,3", **config})


def same(tmp_path, data=DATA, **config):
    return same_with(tmp_path, data, **{"kind": "ExtractPositionalFields", "pattern": "3,4,3", **config})


def test_text_is_cut_at_the_widths_and_the_pieces_go_to_the_columns_that_do_not_arrive(tmp_path):
    kept, _ = same(tmp_path)
    assert kept == ["1;abc;defg;hij", "2;abc;;", "3;abc;defg;hij", "4;;;", "5; x ; y z;  "]


def test_widths_beyond_the_last_column_are_not_read_and_a_column_beyond_the_last_width_is_missing(tmp_path):
    kept, _ = same(tmp_path, out="id:int, raw:str, a:str, b:str")
    assert kept[0] == "1;abcdefghij;abc;defg"
    kept, _ = same(tmp_path / "b", pattern="3,4")
    assert kept[0] == "1;abc;defg;"


def test_blanks_around_a_piece_are_dropped_when_asked(tmp_path):
    kept, _ = same(tmp_path, trim=True)
    assert kept[4] == "5;x;y z;"


@pytest.mark.parametrize("pattern", [" 3 , 4 ,, 3 ", "3,4,3,", "3,4,3,9"])
def test_pattern_with_blanks_and_empty_places(tmp_path, pattern):
    kept, _ = same(tmp_path, pattern=pattern)
    assert kept[0] == "1;abc;defg;hij"


def test_pattern_that_is_one_number(tmp_path):
    kept, _ = same(tmp_path, pattern=3)
    assert kept[0] == "1;abc;;"


def test_pieces_are_read_as_the_types_the_output_declares(tmp_path):
    kept, _ = same(tmp_path, b"id|raw\n1|00712.520240131\n2|  7 1.520240201\n", out="id:int, a:int, b:float, c:datetime@%Y%m%d",
                   pattern="3,4,8")
    assert kept == ["1;7;12.5;20240131", "2;7;1.5;20240201"]


def test_width_counts_characters_and_a_byte_order_mark_is_no_part_of_the_text(tmp_path):
    kept, _ = same(tmp_path, "id|raw\n1|﻿abcdef\n2|日本語です。\n".encode(), pattern="2,2,2")
    assert kept == ["1;ab;cd;ef", "2;日本;語で;す。"]


def test_number_is_cut_as_the_text_it_is_written_as_and_a_row_with_no_source_is_left_out(tmp_path):
    kept, rejected = same(tmp_path, b"id|raw\n1|12.5\n2|\n3|7\n", schema="id:int, raw:float", pattern="1,1,2", reject="")
    assert kept == ["1;1;2;.5", "3;7;.;0"] and len(rejected) <= 1


def test_row_with_no_source_leaves_by_the_reject_output_when_it_is_not_to_be_left_out(tmp_path):
    kept, rejected = same(tmp_path, b"id|raw\n1|12.5\n2|\n3|7\n", schema="id:int, raw:float", pattern="1,1,2", reject="",
                          ignore_source_null=False)
    assert kept == ["1;1;2;.5", "3;7;.;0"]
    assert rejected == ["id;raw;errorCode;errorMessage", "2;;NULL_SOURCE;Source column 'raw' is null"]


def test_text_shorter_than_the_widths_together_leaves_by_the_reject_output_when_asked(tmp_path):
    kept, rejected = same(tmp_path, reject="", check_fields_num=True)
    assert kept == ["1;abc;defg;hij", "3;abc;defg;hij"]
    assert rejected == [
        "id;raw;errorCode;errorMessage",
        "2;abc;EXTRACTION_ERROR;Line length 3 < required total width 10",
        "4;;EXTRACTION_ERROR;Line length 0 < required total width 10",
        "5; x  y z  ;EXTRACTION_ERROR;Line length 9 < required total width 10",
    ]


def test_only_the_widths_that_are_read_count_for_the_length(tmp_path):
    kept, rejected = same(tmp_path, out="id:int, a:str, b:str", reject="", check_fields_num=True)
    assert kept == ["1;abc;defg", "3;abc;defg", "5; x ; y z"] and len(rejected) == 3


def test_short_text_fails_the_job_when_it_is_to_die(tmp_path):
    made = extract(check_fields_num=True, die_on_error=True)
    assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    (tmp_path / "x").mkdir()
    result, files = v2(tmp_path / "x", made, DATA)
    assert result.status == "failed" and files == {}
    assert result.error == (
        "Line length 3 < required total width 10 (the first of 3 such rows); the row is line 3 of in.csv")


def test_rows_turned_away_with_no_flow_to_take_them_are_told_in_the_log(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result, files = v2(tmp_path, extract(check_fields_num=True), DATA)
    assert result.status == "success" and len(files["out.csv"]) == 3
    assert [record.getMessage() for record in caplog.records] == [
        "[it] 3 rows were dropped (no flow takes this component's rejects); the first: "
        "Line length 3 < required total width 10; the row is line 3 of in.csv"]


def test_first_column_is_cut_when_no_source_is_named(tmp_path):
    made = extract(schema="raw:str, id:int", out="id:int, a:str, b:str, c:str", field="")
    run = assert_matches_v1(made, {"in.csv": b"raw|id\nabcdefghij|1\n"}, tmp_path)
    assert run.files["out.csv"] == b"id;a;b;c\n1;abc;defg;hij\n"
    del made["components"][1]["config"]["field"]
    assert assert_matches_v1(made, {"in.csv": b"raw|id\nabcdefghij|1\n"}, tmp_path / "b").files["out.csv"] == (
        b"id;a;b;c\n1;abc;defg;hij\n")


@pytest.mark.parametrize("config, key, said", [
    ({"pattern": "3,x"}, "pattern", "'x' is no width: give whole numbers, 1 or more, separated by commas"),
    ({"pattern": "3,0,2"}, "pattern", "0 is no width: give whole numbers, 1 or more, separated by commas"),
    ({"pattern": ""}, "pattern", "names no width"),
    ({"pattern": "3,*"}, "pattern", None),
    ({"field": "nope"}, "field", "there is no column 'nope' (id, raw)"),
    ({"nope": 1}, "nope", None),
])
def test_what_cannot_be_read_refuses_the_job(config, key, said):
    found = refusals(extract(**config))
    assert [path for path, _ in found] == [key]
    assert said is None or found[0][1] == said


def test_pattern_has_to_be_given():
    made = extract()
    del made["components"][1]["config"]["pattern"]
    assert [key for key, _ in refusals(made)] == ["pattern"]


def test_keys_v1_never_reads_change_nothing(tmp_path):
    unread = dict(formats=[{"schema_column": "a", "size": "3"}], advanced_separator=True, thousands_separator=".",
                  decimal_separator=",", advanced_option=True)
    assert same(tmp_path, **unread) == same(tmp_path / "b")


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("extract_positional_fields", "ExtractPositionalFields", "tExtractPositionalFields")):
        (tmp_path / str(at)).mkdir()
        result, files = v2(tmp_path / str(at), extract(kind=kind), DATA)
        assert result.status == "success" and files["out.csv"][1] == "1;abc;defg;hij"
        load_job(extract(kind=kind))


# ------------------------------------------------------------------
# What an independent review found (ticket 77)
# ------------------------------------------------------------------

def test_columns_are_named_field_1_and_so_on_when_the_output_declares_none(tmp_path):
    made = extract(reject="", check_fields_num=True)
    made["components"][1]["schema"]["output"] = []
    made["components"][2]["schema"]["input"] = []
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.files["out.csv"].decode().splitlines() == [
        "id;raw;field_1;field_2;field_3", "1;abcdefghij;abc;defg;hij", "3;abcdefghijklmn;abc;defg;hij"]
    assert len(run.files["rej.csv"].splitlines()) == 4


def test_width_beyond_any_text_is_the_rest_of_the_text(tmp_path):
    kept, _ = same(tmp_path, pattern="2,99999999999999999999,1")
    assert kept[0] == "1;ab;cdefghij;"


def test_only_one_byte_order_mark_and_only_at_the_start_is_no_part_of_the_text(tmp_path):
    data = "id|raw\n1|\ufeff\ufeffabcdef\n2|ab\ufeffcdef\n".encode("utf-8")
    kept, _ = same(tmp_path, data, pattern="2,2,2")
    assert kept == ["1;\ufeffa;bc;de", "2;ab;\ufeffc;de"]


def test_length_is_counted_in_characters(tmp_path):
    data = "id|raw\n1|日本語です。日本語で\n2|日本語です。日本語\n".encode("utf-8")
    kept, rejected = same(tmp_path, data, reject="", check_fields_num=True)
    assert kept == ["1;日本語;です。日;本語で"] and rejected[1].endswith("Line length 9 < required total width 10")


def test_place_of_blanks_between_two_commas_is_no_width(tmp_path):
    kept, _ = same(tmp_path, pattern="3, ,4,\t,3")
    assert kept[0] == "1;abc;defg;hij"


def test_every_blank_python_strips_is_trimmed(tmp_path):
    data = "id|raw\n1|\ta\u00a0\u2003bc\x1cd  \n".encode("utf-8")
    kept, _ = same(tmp_path, data, pattern="3,4,2", trim=True)
    assert kept == ["1;a;bc;d"]


def test_pattern_given_as_nothing_refuses_the_job_by_its_key():
    assert refusals(extract(pattern=None)) == [("pattern", "names no width")]
