"""Extract regex fields, against v1 on the same job config and bytes."""
import logging

import pytest

from src.v2 import load_job
from tests.v2.answer_key import assert_matches_v1

from .test_extract_delimited_fields import extract as extract_with, refusals, same as same_with, v2

DATA = b"id|raw\n1|ann-30-x\n2|bob\n3|cy-7-yy-zz\n4|\n5|  di-5-q\n"
THREE = r"(\w+)-(\d+)-(\w+)"


def extract(**config):
    return extract_with(**{"kind": "ExtractRegexFields", "regex": THREE, "die_on_error": False, **config})


def same(tmp_path, data=DATA, **config):
    return same_with(tmp_path, data, **{"kind": "ExtractRegexFields", "regex": THREE, "die_on_error": False, **config})


def test_groups_of_the_first_place_the_pattern_is_found_go_to_the_columns_that_do_not_arrive(tmp_path):
    kept, _ = same(tmp_path)
    assert kept == ["1;ann;30;x", "3;cy;7;yy", "5;di;5;q"]


def test_pattern_is_looked_for_anywhere_in_the_text(tmp_path):
    kept, _ = same(tmp_path, regex=r"(\d+)-(\w)")
    assert kept == ["1;30;x;", "3;7;y;", "5;5;q;"]


@pytest.mark.parametrize("regex, first", [
    (r"(\w+)-(\d+)", "1;ann;30;"), (r"(\w+)-(\d+)-(\w)(\w?)", "1;ann;30;x"), (r"\w+-\d+", "1;;;"),
    (r"(?P<n>\w+)-(?P<a>\d+)-(\w+)", "1;ann;30;x"), (r"(?:\w+)-(\d+)-(\w+)", "1;30;x;"),
    ("(\\\\w+)-(\\\\d+)-(\\\\w+)", "1;ann;30;x"), (r"^(\w+)-(\d+)-(\w+)$", "1;ann;30;x"),
    (r"(?i)(ANN)-(\d+)", "1;ann;30;"), (r"((\w)\w*)-(\d+)", "1;ann;a;30"),
])
def test_groups_fewer_more_named_or_none(tmp_path, regex, first):
    kept, _ = same(tmp_path, regex=regex)
    assert kept[0] == first


def test_group_that_took_no_part_is_missing(tmp_path):
    kept, _ = same(tmp_path, regex=r"(\w+)-(\d+)-(\w+)(-\w+)?", out="id:int, a:str, b:str, c:str, d:str")
    assert kept == ["1;ann;30;x;", "3;cy;7;yy;-zz", "5;di;5;q;"]


def test_groups_are_read_as_the_types_the_output_declares(tmp_path):
    kept, _ = same(tmp_path, b"id|raw\n1|7 1.5 2024-01-31\n2|x y z\n", regex=r"(\S+) (\S+) (\S+)",
                   out="id:int, a:int, b:float, c:datetime@%Y-%m-%d")
    assert kept == ["1;7;1.5;2024-01-31", "2;;;"]


def test_text_of_another_script(tmp_path):
    kept, _ = same(tmp_path, "id|raw\n1|Ünï-5-x\n2|日本-٣-語\n".encode())
    assert kept == ["1;Ünï;5;x", "2;日本;٣;語"]


def test_text_the_pattern_is_not_found_in_leaves_by_the_reject_output(tmp_path):
    kept, rejected = same(tmp_path, reject="")
    assert rejected == ["id;raw;errorCode;errorMessage", "2;bob;NO_MATCH;Regex did not match: 'bob'",
                        "4;;NO_MATCH;Regex did not match: ''"]


def test_text_with_a_quote_is_said_as_python_says_it(tmp_path):
    _, rejected = same(tmp_path, b"id|raw\n1|it's\n2|say \"hi\"\n3|both ' and \"\n4|back\\slash\n", reject="")
    assert rejected[1:] == ['1;it\'s;NO_MATCH;Regex did not match: "it\'s"', "2;say \"hi\";NO_MATCH;Regex did not match: 'say \"hi\"'",
                            "3;both ' and \";NO_MATCH;Regex did not match: 'both \\' and \"'",
                            "4;back\\slash;NO_MATCH;Regex did not match: 'back\\\\slash'"]


def test_text_the_pattern_is_not_found_in_fails_the_job_unless_told_otherwise(tmp_path):
    made = extract()
    del made["components"][1]["config"]["die_on_error"]
    assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    (tmp_path / "x").mkdir()
    result, files = v2(tmp_path / "x", made, DATA)
    assert result.status == "failed" and files == {}
    assert result.error == "Regex did not match: 'bob' (the first of 2 such rows); the row is line 3 of in.csv"


def test_row_with_no_source_leaves_by_the_reject_output_and_never_fails_the_job(tmp_path):
    for at, die in enumerate((False, True)):
        kept, rejected = same(tmp_path / str(at), b"id|raw\n1|1.5\n2|\n", schema="id:int, raw:float", regex=r"(\d)\.(\d)",
                              out="id:int, a:str, b:str", reject="", die_on_error=die)
        assert kept == ["1;1;5"] and rejected[1:] == ["2;;NULL_SOURCE;Source column 'raw' is null"]


def test_pattern_whose_groups_are_not_as_many_as_the_columns_turns_every_row_away_when_asked(tmp_path):
    kept, rejected = same(tmp_path, regex=r"(\w+)-(\d+)", check_fields_num=True, reject="")
    assert kept == [] and rejected[1:3] == [
        "1;ann-30-x;FIELD_COUNT_MISMATCH;Expected 3 capture groups, got 2", "2;bob;NO_MATCH;Regex did not match: 'bob'"]
    kept, _ = same(tmp_path / "b", check_fields_num=True, reject="")
    assert kept == ["1;ann;30;x", "3;cy;7;yy", "5;di;5;q"]


def test_rows_turned_away_with_no_flow_to_take_them_are_told_in_the_log(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result, files = v2(tmp_path, extract(), DATA)
    assert result.status == "success" and len(files["out.csv"]) == 4
    assert [record.getMessage() for record in caplog.records] == [
        "[it] 2 rows were dropped (no flow takes this component's rejects); the first: "
        "Regex did not match: 'bob'; the row is line 3 of in.csv"]


@pytest.mark.parametrize("config, key, said", [
    ({"regex": r"(\w+"}, "regex", None),
    ({"regex": ""}, "regex", "there is no pattern"),
    ({"regex": r"(\w+)(?=-)-(\d+)"}, "regex", None),
    ({"regex": r"(\w)\1-(\d+)"}, "regex", None),
    ({"field": "nope"}, "field", "there is no column 'nope' (id, raw)"),
    ({"ignore_source_null": True}, "ignore_source_null", None),
])
def test_what_cannot_be_read_refuses_the_job(config, key, said):
    found = refusals(extract(**config))
    assert [path for path, _ in found] == [key]
    assert said is None or found[0][1] == said


def test_pattern_polars_cannot_look_for_is_said_so():
    (_, said), = refusals(extract(regex=r"(\w+)(?=-)-(\d+)"))
    assert said.startswith("v2 cannot look for this pattern (no lookaround and no backreferences): ")
    # A pattern Polars reads and Python does not is none either: the patterns are Python's.
    (_, said), = refusals(extract(regex=r"(\p{L}+)-(\d+)"))
    assert said.startswith("this is no pattern: bad escape")


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("extract_regex_fields", "ExtractRegexFields", "tExtractRegexFields")):
        (tmp_path / str(at)).mkdir()
        result, files = v2(tmp_path / str(at), extract(kind=kind), DATA)
        assert result.status == "success" and files["out.csv"][1] == "1;ann;30;x"
        load_job(extract(kind=kind))
