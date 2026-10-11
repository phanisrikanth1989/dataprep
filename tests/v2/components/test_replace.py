"""Replace, against v1 on the same job config and bytes."""
import json
from pathlib import Path

import pytest

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import through

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tReplace_0.1.json"
SCHEMA = "id:int, status:str, note:str, amt:float"
DATA = (b"id;status;note;amt\n1;ACTIVE;Sr. dev (a+b) cat;1.5\n2;active;the cat sat. Jr.;2.0\n"
        b"3;INACTIVE;concat cat's CAT;\n4;;;10.25\n5;x$1;a\\b c;3.0\n")


def rule(column, search, replace, **more):
    made = {"input_column": column, "search_pattern": search, "replace_string": replace, "whole_word": False,
            "case_sensitive": False, "use_glob": False, "comment": ""}
    made.update(more)
    return made


def replaced(rules=(), schema=SCHEMA, out=None, **config):
    return through({"type": "Replace", "config": {"substitutions": list(rules), **config}}, schema, out)


def same(tmp_path, rules=(), data=DATA, column=1, **kwargs):
    run = assert_matches_v1(replaced(rules, **kwargs), {"in.csv": data}, tmp_path)
    assert run.succeeded, run.error
    return [line.split(";")[column] for line in run.files["out.csv"].decode().splitlines()[1:]]


def test_whole_value_is_replaced_whatever_its_case_by_default(tmp_path):
    assert same(tmp_path, [rule("status", "ACTIVE", "A")]) == ["A", "A", "INACTIVE", "", "x$1"]


def test_case_sensitive(tmp_path):
    assert same(tmp_path, [rule("status", "ACTIVE", "A", case_sensitive=True)])[:2] == ["A", "active"]


def test_every_occurrence_inside_the_value_when_not_strict(tmp_path):
    got = same(tmp_path, [rule("note", "cat", "dog")], column=2, strict_match=False)
    assert got[:3] == ["Sr. dev (a+b) dog", "the dog sat. Jr.", "condog dog's dog"]


def test_whole_word(tmp_path):
    got = same(tmp_path, [rule("note", "cat", "dog", whole_word=True)], column=2, strict_match=False)
    assert got[2] == "concat dog's dog"


def test_what_is_searched_for_is_text_not_a_pattern(tmp_path):
    got = same(tmp_path, [rule("note", "(a+b)", "[x]"), rule("note", "sat.", "sat!")], column=2, strict_match=False)
    assert got[:2] == ["Sr. dev [x] cat", "the cat sat! Jr."]


@pytest.mark.parametrize("search, strict, got", [
    ("S*cat", True, "X"), ("?r. dev*", True, "X"), ("c?t", False, "Sr. dev (a+b) X"), ("d*b", False, "Sr. X) cat"),
])
def test_glob(tmp_path, search, strict, got):
    assert same(tmp_path, [rule("note", search, "X", use_glob=True)], column=2, strict_match=strict)[0] == got


def test_rules_apply_one_after_another(tmp_path):
    rules = [rule("status", "ACTIVE", "A"), rule("status", "A", "on"), rule("status", "INACTIVE", "off")]
    assert same(tmp_path, rules) == ["on", "on", "off", "", "x$1"]


def test_dollar_and_backslash_in_the_value_and_in_the_replacement(tmp_path):
    assert same(tmp_path, [rule("status", "x$1", "$0 & $1")])[4] == "$0 & $1"
    assert same(tmp_path / "b", [rule("note", "a\\b", "c\\\\d")], column=2, strict_match=False)[4] == "c\\d c"


def test_group_of_the_match_can_be_put_back(tmp_path):
    got = same(tmp_path, [rule("note", "c?t", "<\\g<0>>", use_glob=True)], column=2, strict_match=False)
    assert got[1] == "the <cat> sat. Jr."


def test_number_column_is_replaced_as_its_text(tmp_path):
    assert same(tmp_path, [rule("amt", "2.0", "9.5")], column=3)[:2] == ["1.5", "9.5"]
    assert same(tmp_path / "b", [rule("id", "3", "30")], column=0)[2] == "30"


def test_rule_for_a_column_that_is_not_there_is_passed_over(tmp_path):
    assert same(tmp_path, [rule("nope", "a", "b")]) == ["ACTIVE", "active", "INACTIVE", "", "x$1"]


def test_no_rules_and_no_rows(tmp_path):
    assert same(tmp_path)[0] == "ACTIVE"
    assert same(tmp_path / "b", [rule("status", "a", "b")], b"id;status;note;amt\n") == []


def test_advanced_rules_are_patterns(tmp_path):
    rules = [{"input_column": "note", "search_column": "\\\\bc(a)t\\\\b", "replace_column": "[\\1]", "comment": ""},
             {"input_column": "status", "search_column": "(?i)^in", "replace_column": "", "comment": ""}]
    made = dict(simple_mode=False, advanced_subst=rules)
    assert same(tmp_path, column=2, **made)[:3] == ["Sr. dev (a+b) [a]", "the [a] sat. Jr.", "concat [a]'s CAT"]


def test_empty_search_text(tmp_path):
    assert same(tmp_path, [rule("status", "", "none")]) == ["ACTIVE", "active", "INACTIVE", "none", "x$1"]


@pytest.mark.parametrize("config, said", [
    ({"substitutions": [{"input_column": "a"}]}, "search_pattern"),
    ({"substitutions": [rule("status", "a", "b\\q")]}, "replace_string"),
    ({"simple_mode": False, "advanced_subst": [{"input_column": "note", "search_column": "(", "replace_column": "x"}]},
     "search_column"),
    ({"simple_mode": False, "advanced_subst": [{"input_column": "note", "search_column": "(?<=a)b", "replace_column": "x"}]},
     "search_column"),
])
def test_what_cannot_be_read_refuses_the_job(config, said):
    made = replaced()
    made["components"][1]["config"] = config
    with pytest.raises(JobRefusedError, match=said):
        load_job(made)


def test_converters_sample_loads():
    spec = next(c for c in json.loads(SAMPLE.read_text())["components"] if c["type"] in ("tReplace", "Replace"))
    made = replaced()
    made["components"][1]["config"] = spec["config"]
    load_job(made)


def test_backslash_before_a_sign_stays_and_two_digits_name_one_group(tmp_path):
    assert same(tmp_path, [rule("status", "ACTIVE", "a\\.b")])[0] == "a\\.b"
    rules = [{"input_column": "status", "search_column": "(A)(C)(T)(I)(V)(E)()()()()()(.*)", "replace_column": "\\12\\1"}]
    assert same(tmp_path / "b", simple_mode=False, advanced_subst=rules)[0] == "A"


@pytest.mark.parametrize("config, said", [
    ({"substitutions": [rule("status", "a", "b\\")]}, "bad escape"),
    ({"substitutions": [rule("status", "a", "\\gx")]}, "missing <"),
    ({"substitutions": [rule("status", "a", "\\1")]}, "invalid group reference"),
    ({"simple_mode": False, "advanced_subst": [{"input_column": "note", "search_column": "(a)", "replace_column": "\\2"}]},
     "invalid group reference"),
    ({"simple_mode": False, "advanced_subst": [{"input_column": "note", "search_column": "\\x", "replace_column": ""}]},
     "is not a pattern"),
    ({"simple_mode": False, "advanced_subst": [{"input_column": "note", "search_column": 5, "replace_column": ""}]},
     "search_column"),
])
def test_replacement_or_pattern_python_would_not_take_refuses_the_job(config, said):
    made = replaced()
    made["components"][1]["config"] = config
    with pytest.raises(JobRefusedError, match=said):
        load_job(made)
