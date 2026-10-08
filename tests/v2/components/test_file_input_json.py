"""JSON file input, against v1 on the same job config and bytes.

Where a test runs v2 alone, v1 does something v2 does not follow; the comment
on the test says what.
"""
import json
import os
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import columns, flow, job, writer

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tFileInputJSON_0.1.json"

# Every kind of value JSON has, a missing key (the third item has no tags, who or day), and text where a number belongs.
ITEMS = {"items": [
    {"id": 1, "name": "ann", "amt": 1.5, "ok": True, "tags": ["a", "b"], "who": {"x": 1}, "day": "2024-01-31"},
    {"id": 2, "name": None, "amt": 2.25, "ok": False, "tags": [], "who": {}, "day": None},
    {"id": 3, "name": "cy", "amt": "x", "ok": "yes", "day": "bad"},
]}
FIELDS = ("id", "name", "amt", "ok", "tags", "who", "day")


def json_job(schema, mapping, loop="$.items[*]", reject=False, **config):
    """document -> file, optionally with the reader's reject output written to rej.csv.

    ``reject`` is True, or the columns the writer of rej.csv declares.
    """
    made = {"filename": "in.json", "json_loop_query": loop, "encoding": "UTF-8",
            "mapping": [{"column": column, "jsonpath": path} for column, path in mapping]}
    made.update(config)
    source = {"id": "in", "type": "FileInputJSON", "config": made,
              "schema": {"input": [], "output": columns(schema)}, "inputs": [], "outputs": ["row1"]}
    components = [source, writer(schema, inputs=("row1",))]
    flows = [flow("row1", "in", "out")]
    if reject:
        source["outputs"].append("bad")
        declared = reject if isinstance(reject, str) else None
        components.append(writer(declared, component_id="rej", path="rej.csv", inputs=("bad",)))
        flows.append(flow("bad", "in", "rej", "reject"))
    return job(components, flows)


def paths(*names):
    return [(name, f"$.{name}") for name in names]


def as_bytes(document):
    return document if isinstance(document, bytes) else json.dumps(document).encode()


def same(tmp_path, document, schema, mapping, fails=False, **kwargs):
    """Both engines do the same with the job; ``fails`` says the job is one neither finishes."""
    inputs = {} if document is None else {"in.json": as_bytes(document)}
    run = assert_matches_v1(json_job(schema, mapping, **kwargs), inputs, tmp_path)
    assert run.succeeded is not fails, run.error
    return run


def rows(run, name="out.csv"):
    return run.files[name].decode().splitlines()[1:]


def v2(tmp_path, document, schema, mapping, **kwargs):
    """Run on v2 only, inside tmp_path; returns (result, the rows written)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    if document is not None:
        (tmp_path / "in.json").write_bytes(as_bytes(document))
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(json_job(schema, mapping, **kwargs))
    finally:
        os.chdir(previous)
    out = tmp_path / "out.csv"
    return result, out.read_text().splitlines()[1:] if out.exists() else None


# ------------------------------------------------------------------
# Values
# ------------------------------------------------------------------

def test_every_kind_of_value_as_text(tmp_path):
    schema = "name:str, ok:str, tags:str, who:str, day:str"
    assert rows(same(tmp_path, ITEMS, schema, paths("name", "ok", "tags", "who", "day"))) == [
        'ann;True;["a", "b"];{"x": 1};2024-01-31',
        ";False;[];{};",
        # A key that is not there reads as a list of nothing, as in v1.
        "cy;yes;[];[];bad",
    ]


def test_values_take_the_declared_types_and_what_cannot_be_read_goes_missing(tmp_path):
    run = same(tmp_path, ITEMS, "id:int, name:str, amt:float, ok:bool", paths("id", "name", "amt", "ok"))
    assert rows(run) == ["1;ann;1.5;true", "2;;2.25;false", "3;cy;;true"]


def test_number_written_as_text_is_read_as_a_number(tmp_path):
    document = {"items": [{"n": " 12 "}, {"n": "1,5"}, {"n": ""}, {"n": "7"}]}
    assert rows(same(tmp_path, document, "n:float", paths("n"))) == ["12.0", "", "", "7.0"]


def test_dates_are_read_by_the_columns_pattern(tmp_path):
    run = same(tmp_path, ITEMS, "id:int, day:datetime@%Y-%m-%d", paths("id", "day"), die_on_error=False)
    assert rows(run) == ["1;2024-01-31", "2;", "3;"]


def test_decimals_are_written_with_the_declared_places(tmp_path):
    document = {"items": [{"m": 1.5}, {"m": "2.25"}, {"m": 3}]}
    assert rows(same(tmp_path, document, "m:Decimal#2", paths("m"))) == ["1.50", "2.25", "3.00"]


def test_text_beyond_ascii(tmp_path):
    document = {"items": [{"n": "Zürich ✓", "t": ["é", "z"]}]}
    # Inside a list the characters are written as JSON escapes, as v1's json.dumps writes them.
    assert rows(same(tmp_path, document, "n:str, t:str", paths("n", "t"))) == ['Zürich ✓;["\\u00e9", "z"]']


def test_file_in_another_encoding(tmp_path):
    document = '{"items": [{"n": "Zürich"}]}'.encode("iso-8859-1")
    assert rows(same(tmp_path, document, "n:str", paths("n"), encoding="ISO-8859-1")) == ["Zürich"]


# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

def test_path_with_a_star_always_gives_a_list(tmp_path):
    assert rows(same(tmp_path, ITEMS, "id:int, tags:str", [("id", "$.id"), ("tags", "$.tags[*]")])) == [
        '1;["a", "b"]', "2;[]", "3;[]",
    ]


def test_path_that_finds_several_values_gives_a_list(tmp_path):
    document = {"items": [{"a": {"x": 1, "y": {"x": 2}}}]}
    assert rows(same(tmp_path, document, "v:str", [("v", "$..x")])) == ["[1, 2]"]


def test_path_into_a_nested_object(tmp_path):
    document = {"items": [{"a": {"b": 5}}, {"a": {}}]}
    assert rows(same(tmp_path, document, "v:str", [("v", "$.a.b")])) == ["5", "[]"]


def test_paths_may_be_written_in_double_quotes(tmp_path):
    run = same(tmp_path, ITEMS, "id:int", [("id", '"$.id"')], loop='"$.items[*]"')
    assert rows(run) == ["1", "2", "3"]


def test_document_that_is_a_list(tmp_path):
    assert rows(same(tmp_path, [{"id": 1}, {"id": 2}], "id:int", paths("id"), loop="$[*]")) == ["1", "2"]


def test_loop_over_values_that_are_not_objects(tmp_path):
    assert rows(same(tmp_path, {"items": [1, 2, 3]}, "v:int", [("v", "$")])) == ["1", "2", "3"]


@pytest.mark.parametrize("as_root, want", [(True, ["1", "2"]), (False, ["[]"])])
def test_loop_that_finds_one_list_is_gone_through_only_with_use_loop_as_root(tmp_path, as_root, want):
    document = {"items": [{"id": 1}, {"id": 2}]}
    assert rows(same(tmp_path, document, "id:str", paths("id"), loop="$.items", use_loop_as_root=as_root)) == want


@pytest.mark.parametrize("document", [{"items": []}, {"other": 1}])
def test_loop_that_finds_nothing_gives_no_rows(tmp_path, document):
    assert rows(same(tmp_path, document, "id:int", paths("id"))) == []


def test_loop_that_is_the_document_itself_gives_one_row(tmp_path):
    document = {"id": 7, "n": None}
    assert rows(same(tmp_path, document, "id:int", paths("id"), loop="$")) == ["7"]
    result, _ = v2(tmp_path / "direct", document, "id:int, n:int!", paths("id", "n"), loop="$")
    # The one record is the document: its path is the bare `$`.
    assert result.error == "Column 'n' has NULL values but is not nullable; the row is record 1 ($) of in.json"


# ------------------------------------------------------------------
# Columns
# ------------------------------------------------------------------

def test_declared_column_without_a_path_is_empty(tmp_path):
    assert rows(same(tmp_path, ITEMS, "id:int, extra:str", paths("id"))) == ["1;", "2;", "3;"]


def test_no_path_at_all_gives_no_rows(tmp_path):
    # Without a path there is no column, and a table without columns has no rows.
    assert rows(same(tmp_path, ITEMS, "id:int, name:str", [])) == []


def test_path_for_a_column_the_schema_lacks_still_gives_the_column(tmp_path):
    run = same(tmp_path, ITEMS, "id:int", paths("id", "name"))
    assert run.files["out.csv"].decode().splitlines() == ["id;name", "1;ann", "2;", "3;cy"]


# ------------------------------------------------------------------
# What stops the job, and what does not
# ------------------------------------------------------------------

def test_file_that_is_not_json_fails_the_job(tmp_path):
    same(tmp_path, b"{not json", "id:int", paths("id"), fails=True)


def test_file_that_is_not_json_reads_as_no_rows_when_errors_are_not_fatal(tmp_path):
    assert rows(same(tmp_path, b"{not json", "id:int", paths("id"), die_on_error=False)) == []


def test_file_that_is_not_there_fails_the_job(tmp_path):
    same(tmp_path, None, "id:int", paths("id"), fails=True)


def test_file_that_is_not_there_reads_as_no_rows_when_errors_are_not_fatal(tmp_path):
    assert rows(same(tmp_path, None, "id:int", paths("id"), die_on_error=False)) == []


def test_missing_value_where_none_is_allowed_fails_the_job(tmp_path):
    document = {"items": [{"id": 1, "n": 5}, {"id": 2, "n": None}]}
    same(tmp_path, document, "id:int, n:int!", paths("id", "n"), fails=True)
    result, _ = v2(tmp_path / "direct", document, "id:int, n:int!", paths("id", "n"))
    assert result.failed_component == "in"
    assert result.error == ("Column 'n' has NULL values but is not nullable; "
                            "the row is record 2 ($.items[1]) of in.json")


def test_missing_value_where_none_is_allowed_drops_the_row_when_errors_are_not_fatal(tmp_path):
    document = {"items": [{"id": 1, "n": "a"}, {"id": 2, "n": None}, {"id": 3, "n": "c"}]}
    assert rows(same(tmp_path, document, "id:int, n:str!", paths("id", "n"), die_on_error=False)) == ["1;a", "3;c"]


# ------------------------------------------------------------------
# Where v2 does not follow v1
# ------------------------------------------------------------------

def test_whole_number_is_written_as_one_whatever_else_its_column_holds(tmp_path):
    # v1 lets pandas pick one type for the column: beside a fraction or a missing value its whole
    # numbers come out as 1.0. v2 reads every value by itself.
    _, out = v2(tmp_path, {"items": [{"n": 1}, {"n": None}, {"n": 2.5}]}, "n:str", paths("n"))
    assert out == ["1", "", "2.5"]


def test_path_that_is_no_jsonpath_refuses_the_job(tmp_path):
    # v1 runs, rejects every record with "Parse error" and writes nothing.
    with pytest.raises(JobRefusedError) as caught:
        load_job(json_job("id:int", [("id", "$..[")]))
    assert "mapping[0].jsonpath" in caught.value.report.format()
    with pytest.raises(JobRefusedError) as caught:
        load_job(json_job("id:int", paths("id"), loop="$.items["))
    assert "json_loop_query" in caught.value.report.format()


def test_machine_without_the_jsonpath_library_is_told_what_to_install(tmp_path, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "jsonpath_ng.ext", None)
    with pytest.raises(JobRefusedError) as caught:
        load_job(json_job("id:int, name:str", paths("id", "name")))
    # Said once, and not as a fault of each path.
    assert [refusal.reason for refusal in caught.value.report] == [
        "reading JSON files needs the jsonpath-ng package (pip install 'dataprep[v2]')"
    ]


def test_reading_from_a_url_is_refused():
    with pytest.raises(JobRefusedError) as caught:
        load_job(json_job("id:int", paths("id"), useurl=True, urlpath="http://localhost/x.json"))
    assert "useurl" in caught.value.report.format()
    assert load_job(json_job("id:int", paths("id"), useurl=False, urlpath="http://localhost/x.json")).name == "t"


def test_wired_reject_output_with_nothing_to_reject_is_written_empty(tmp_path):
    # v1 stalls on a wired flow that gets no rows.
    result, out = v2(tmp_path, ITEMS, "id:int", paths("id"), reject=True)
    assert result.status == "success" and out == ["1", "2", "3"]
    assert (tmp_path / "rej.csv").read_text().splitlines() == ["id;errorCode;errorMessage"]


# ------------------------------------------------------------------
# Keys the converter writes
# ------------------------------------------------------------------

def test_keys_v1_never_acts_on_change_nothing(tmp_path):
    extra = {"read_by": "XPATH", "loop_query": "/bills/bill/line", "json_path_version": "2_1_0",
             "advanced_separator": True, "thousands_separator": ".", "decimal_separator": ",", "check_date": True,
             "tstatcatcher_stats": False, "label": "Read"}
    run = same(tmp_path, {"items": [{"n": "1.234,5"}]}, "n:str", paths("n"), **extra)
    assert rows(run) == ["1.234,5"]


def test_converted_sample_job_is_refused_only_for_what_its_paths_lack():
    # The sample was converted from a job that reads by XPath: its JSONPaths came out empty.
    with pytest.raises(JobRefusedError) as caught:
        load_job(json.loads(SAMPLE.read_text()))
    ours = [refusal for refusal in caught.value.report if "tFileInputJSON_1" in refusal.where]
    assert ours and all(refusal.key.endswith(".jsonpath") for refusal in ours)


# ---------------------------------------------------------------------------
# A record a path cannot be followed on
# ---------------------------------------------------------------------------

# `$.tags[0]` asks for the first item of a list. On a number or an object the library raises instead of
# finding nothing, and v1 turns the record away for it.
ODD = {"items": [
    {"id": 1, "tags": ["a"], "name": "ann"},
    {"id": 2, "tags": 5, "name": "bob"},
    {"id": 3, "tags": {"x": 1}, "name": "cy"},
    {"id": 4, "tags": ["d"], "name": "di"},
]}
ODD_SCHEMA = "id:int, tag:str, name:str"
ODD_PATHS = [("id", "$.id"), ("tag", "$.tags[0]"), ("name", "$.name")]


def test_record_a_path_cannot_be_followed_on_is_left_out(tmp_path):
    run = same(tmp_path, ODD, ODD_SCHEMA, ODD_PATHS)
    assert rows(run) == ["1;a;ann", "4;d;di"]


def test_record_turned_away_is_written_with_what_the_library_said(tmp_path):
    # Both paths fill one column, so that v1's reject output has the columns v2's has (see the next test).
    run = same(tmp_path, ODD, "tag:str", [("tag", "$.name"), ("tag", "$.tags[0]")], reject=True)
    assert rows(run) == ["a", "d"]
    assert rows(run, "rej.csv") == ["bob;PARSE_ERROR;object of type 'int' has no len()", "cy;PARSE_ERROR;0"]


def test_record_turned_away_keeps_every_column_with_those_not_read_empty(tmp_path):
    # v1 writes these two rows with the columns read before the path that failed and no others: here, id alone.
    result, out = v2(tmp_path, ODD, ODD_SCHEMA, ODD_PATHS, reject=True)
    assert result.status == "success" and out == ["1;a;ann", "4;d;di"]
    assert (tmp_path / "rej.csv").read_text().splitlines() == [
        "id;tag;name;errorCode;errorMessage",
        "2;;;PARSE_ERROR;object of type 'int' has no len()",
        "3;;;PARSE_ERROR;0",
    ]


def test_record_turned_away_is_turned_away_whatever_die_on_error_says(tmp_path):
    assert rows(same(tmp_path, ODD, ODD_SCHEMA, ODD_PATHS, die_on_error=False)) == ["1;a;ann", "4;d;di"]


def test_records_turned_away_are_counted_in_a_later_records_number(tmp_path):
    document = {"items": [{"id": 1, "tags": ["a"]}, {"id": 2, "tags": 5}, {"id": None, "tags": ["c"]}]}
    result, _ = v2(tmp_path, document, "id:int!, tag:str", [("id", "$.id"), ("tag", "$.tags[0]")])
    assert result.error == ("Column 'id' has NULL values but is not nullable; "
                            "the row is record 3 ($.items[2]) of in.json")


def test_column_named_like_a_reject_column_is_read_as_any_other(tmp_path):
    # v1's base class renames such a column on the main flow; the reader itself has to hand it on.
    document = {"items": [{"id": 1, "errorCode": "E7", "errorMessage": "m1"}, {"id": 2, "errorCode": "E9", "errorMessage": "m2"}]}
    run = same(tmp_path, document, "id:int, errorCode:str, errorMessage:str", paths("id", "errorCode", "errorMessage"))
    assert run.files["out.csv"] == b"id;errorCode_user;errorMessage_user\n1;E7;m1\n2;E9;m2\n"
