"""Extract JSON fields, against v1 on the same job config and bytes."""
import json
import logging
import os
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2 import answer_key

from .kit import columns, flow, job, reader, writer

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tExtractJSONFields_0.1.json"
IN = "id:int, raw:str"
DATA = b'''id|raw
1|{"name": "ann", "age": 30, "ok": true, "tags": ["a", "b"], "addr": {"city": "X"}, "none": null, "f": 1.5}
2|{"name": "bob"}
3|not json
4|
5|[1, 2]
'''
PATHS = {"id": "", "name": "$.name", "age": "$.age", "ok": "$.ok", "tags": "$.tags", "city": "$.addr.city",
         "none": "$.none", "f": "$.f"}
OUT = "id:int, name:str, age:int, ok:bool, tags:str, city:str, none:str, f:float"
ITEMS = b'''id|raw
1|{"who": "x", "items": [{"n": 1, "v": "a"}, {"n": 2, "v": "b"}]}
2|{"who": "y", "items": []}
3|{"who": "z"}
4|{"who": "w", "items": [{"n": 3}]}
'''


def extract(out=OUT, paths=PATHS, schema=IN, reject=None, kind="ExtractJSONFields", **config):
    """file (fields separated by |) -> extract -> out.csv, and rej.csv for the reject output when asked."""
    made = {"read_by": "JSONPATH", "jsonfield": "raw", "json_loop_query": "$",
            "mapping_4_jsonpath": [{"schema_column": column, "query": path} for column, path in paths.items()]}
    made.update(config)
    step = {"id": "it", "type": kind, "config": made,
            "schema": {"input": columns(schema), "output": columns(out)},
            "inputs": ["row1"], "outputs": ["row2"] + (["bad"] if reject is not None else [])}
    parts = [reader(schema, header_rows=1, fieldseparator="|"), step, writer(out)]
    flows = [flow("row1", "in", "it"), flow("row2", "it", "out")]
    if reject is not None:
        parts.append(writer(reject or None, component_id="rej", path="rej.csv", inputs=("bad",)))
        flows.append(flow("bad", "it", "rej", kind="reject"))
    return job(parts, flows)


def same(tmp_path, data=DATA, **kwargs):
    """Both engines write the same files. Returns the lines of out.csv under its header, and rej.csv's lines."""
    made = extract(**kwargs)
    key = answer_key.run_job(made, {"in.csv": data}, tmp_path / "v1", answer_key.run_v1)
    run = answer_key.run_job(made, {"in.csv": data}, tmp_path / "v2", answer_key.run_v2)
    assert key.succeeded and run.succeeded, (key.error, run.error)
    assert run.files["out.csv"] == key.files["out.csv"]
    if "rej.csv" in run.files:
        # Where no row is turned away v1 leaves the reject file without its header line and v2 writes the line.
        header = ";".join(column["name"] for column in made["components"][1]["schema"]["input"])
        header += ";errorJSONField;errorCode;errorMessage\n"
        assert run.files["rej.csv"] == key.files["rej.csv"] or (
            key.files["rej.csv"] == b"" and run.files["rej.csv"].decode() == header)
    return (run.files["out.csv"].decode().splitlines()[1:], run.files.get("rej.csv", b"").decode().splitlines())


def v2(tmp_path, made, data=DATA):
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    return result, {path.name: path.read_text().splitlines() for path in sorted(tmp_path.glob("*.csv")) if path.name != "in.csv"}


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# Paths become columns
# ------------------------------------------------------------------

def test_what_each_path_finds_goes_to_its_column(tmp_path):
    kept, _ = same(tmp_path)
    assert kept == ['1;ann;30;true;["a", "b"];X;;1.5', "2;bob;;false;;;;", "5;;;false;;;;"]


def test_document_itself_is_the_one_item_when_there_is_no_loop_path(tmp_path):
    assert same(tmp_path, json_loop_query="")[0] == same(tmp_path / "b")[0]


def test_row_for_every_item_the_loop_path_finds_and_none_where_it_finds_none(tmp_path):
    kept, _ = same(tmp_path, ITEMS, out="id:int, n:int, v:str, who:str", json_loop_query="$.items[*]",
                   paths={"id": "", "n": "$.n", "v": "$.v", "who": "$.who"}, reject="")
    assert kept == ["1;1;a;", "1;2;b;", "4;3;;"]


def test_paths_are_followed_from_the_whole_document_when_the_item_is_not_the_root(tmp_path):
    kept, _ = same(tmp_path, ITEMS, out="id:int, n:int, v:str, who:str", json_loop_query="$.items[*]", use_loop_as_root=False,
                   paths={"id": "", "n": "$.items[0].n", "v": "$.items[*].v", "who": "$.who"})
    assert kept == ['1;1;["a", "b"];x', '1;1;["a", "b"];x', "4;3;;w"]


def test_path_written_without_its_root(tmp_path):
    kept, _ = same(tmp_path, ITEMS, out="id:int, n:int, v:str", json_loop_query="items[*]", paths={"id": "", "n": "n", "v": "v"})
    assert kept == ["1;1;a", "1;2;b", "4;3;"]


def test_several_values_are_written_as_a_list(tmp_path):
    kept, _ = same(tmp_path, ITEMS, out="id:int, n:str", paths={"id": "", "n": "$.items[*].n"})
    assert kept == ["1;[1, 2]", "2;", "3;", "4;3"]


def test_only_the_columns_of_the_mapping_are_filled(tmp_path):
    kept, _ = same(tmp_path, ITEMS, out="id:int, raw:str, n:str", paths={"n": "$.who"})
    assert kept == [";;x", ";;y", ";;z", ";;w"]


def test_document_that_is_one_value(tmp_path):
    kept, _ = same(tmp_path, b'id|raw\n1|5\n2|"x"\n3|null\n4|true\n5|"7"\n', out="id:int, n:int", paths={"id": "", "n": "$"}, reject="")
    assert kept == ["1;5", "2;", "3;", "4;1", "5;7"]


def test_values_are_read_as_the_types_the_output_declares(tmp_path):
    data = (b'id|raw\n1|{"d": "2024-01-31", "b": "yes", "n": "7", "m": "2.5", "big": 12345678901234567890, "t": 5, "u": "\\u00e9"}\n'
            b'2|{"d": "soon", "b": 0, "n": "x", "m": 3, "big": 1, "t": "x", "u": null}\n')
    paths = {name: f"$.{name}" for name in ("d", "b", "n", "m", "big", "t", "u")}
    kept, _ = same(tmp_path, data, out="id:int, d:datetime@%Y-%m-%d, b:bool, n:int, m:Decimal#2, big:str, t:str, u:str",
                   paths={"id": "", **paths})
    assert kept == ["1;2024-01-31;true;7;2.50;12345678901234567890;5;é", "2;;false;;3.00;1;x;"]


def test_number_with_a_fraction_in_a_whole_number_column_is_cut_as_everywhere(tmp_path):
    # v1 writes 2.0 and 1.7 through here.
    result, files = v2(tmp_path, extract(out="id:int, i:int", paths={"id": "", "i": "$.i"}), b'id|raw\n1|{"i": 2.0}\n2|{"i": 1.7}\n')
    assert result.status == "success" and files["out.csv"][1:] == ["1;2", "2;1"]


def test_source_that_is_a_number(tmp_path):
    kept, rejected = same(tmp_path, b"id|raw\n1|1.5\n2|\n", schema="id:int, raw:float", out="id:int, n:str",
                          paths={"id": "", "n": "$"}, reject="")
    assert kept == ["1;1.5"] and rejected[1:] == ["2;;;NO_JSON;column 'raw' is null"]


def test_first_column_is_read_when_no_source_is_named(tmp_path):
    made = dict(schema="raw:str, id:int", out="n:str", paths={"n": "$.who"}, jsonfield="")
    assert same(tmp_path, b'raw|id\n{"who": "x"}|1\n', **made)[0] == ["x"]


# ------------------------------------------------------------------
# What is turned away
# ------------------------------------------------------------------

def test_text_that_is_no_json_leaves_by_the_reject_output_with_the_text(tmp_path):
    _, rejected = same(tmp_path, reject="")
    assert rejected == [
        "id;raw;errorJSONField;errorCode;errorMessage",
        "3;not json;not json;PARSE_ERROR;Expecting value: line 1 column 1 (char 0)",
        "4;;;PARSE_ERROR;Expecting value: line 1 column 1 (char 0)",
    ]


@pytest.mark.parametrize("data, said", [
    (DATA, "PARSE_ERROR: Expecting value: line 1 column 1 (char 0) (the first of 2 such rows); the row is line 4 of in.csv"),
    (b'id|raw\n1|{"a": 1}\n2|{"a": }\n', "PARSE_ERROR: Expecting value: line 1 column 7 (char 6); the row is line 3 of in.csv"),
])
def test_text_that_is_no_json_fails_the_job_when_it_is_to_die(tmp_path, data, said):
    made = extract(die_on_error=True)
    key = answer_key.run_job(made, {"in.csv": data}, tmp_path / "v1", answer_key.run_v1)
    assert not key.succeeded
    result, files = v2(tmp_path, made, data)
    assert result.status == "failed" and files == {} and result.error == said


def test_missing_source_fails_the_job_when_it_is_to_die(tmp_path):
    made = extract(schema="id:int, raw:float", out="id:int, n:str", paths={"id": "", "n": "$"}, die_on_error=True)
    result, _ = v2(tmp_path, made, b"id|raw\n1|1.5\n2|\n")
    assert result.status == "failed" and result.error == "NO_JSON: column 'raw' is null; the row is line 3 of in.csv"


def test_rows_turned_away_with_no_flow_to_take_them_are_told_in_the_log(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result, files = v2(tmp_path, extract())
    assert result.status == "success" and len(files["out.csv"]) == 4
    assert [record.getMessage() for record in caplog.records] == [
        "[it] 2 rows were dropped (no flow takes this component's rejects); the first: "
        "Expecting value: line 1 column 1 (char 0); the row is line 4 of in.csv"]


def test_nothing_is_told_when_no_row_is_turned_away_or_a_flow_takes_them(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        v2(tmp_path, extract(), b'id|raw\n1|{"name": "ann"}\n')
        (tmp_path / "b").mkdir()
        v2(tmp_path / "b", extract(reject=""))
    assert not caplog.records


def test_later_component_that_fails_names_the_row_the_item_came_from(tmp_path):
    made = extract(out="id:int, n:int!, v:str", json_loop_query="$.items[*]", paths={"id": "", "n": "$.n", "v": "$.v"},
                   die_on_error=True)
    result, _ = v2(tmp_path, made, ITEMS.replace(b'{"n": 3}', b'{"n": null, "v": "c"}'))
    assert result.status == "failed"
    assert result.error == "Column 'n' has NULL values but is not nullable; the row is line 5 of in.csv"


def test_one_row_turned_away_is_told_as_one(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        v2(tmp_path, extract(), b'id|raw\n1|{"name": "ann"}\n2|nope\n')
    assert [record.getMessage() for record in caplog.records] == [
        "[it] 1 row was dropped (no flow takes this component's rejects): "
        "Expecting value: line 1 column 1 (char 0); the row is line 3 of in.csv"]


def test_path_that_finds_nothing_gives_empty_text_and_no_missing_value(tmp_path):
    kept, _ = same(tmp_path, ITEMS, out="id:int, n:str!", paths={"id": "", "n": "$.nope"}, die_on_error=True)
    assert kept == ["1;", "2;", "3;", "4;"]


def test_way_of_reading_in_small_letters(tmp_path):
    assert same(tmp_path, read_by="jsonpath")[0][1] == "2;bob;;false;;;;"


def test_source_column_is_looked_for_when_the_rows_arrive_where_nothing_declares_the_columns(tmp_path):
    made = extract(jsonfield="nope")
    made["components"][1]["schema"]["input"] = []
    result, _ = v2(tmp_path, made)
    assert result.status == "failed" and result.error == "jsonfield: there is no column 'nope' (id, raw)"


def test_output_columns_have_to_be_declared():
    made = extract()
    made["components"][1]["schema"]["output"] = []
    assert ("schema", "extract JSON fields needs its output columns declared") in refusals(made)


def test_path_that_cannot_be_followed_on_an_item_finds_nothing_there_and_the_log_says_so_once(tmp_path, caplog):
    data = b'id|raw\n1|{"a": [7, 8]}\n2|{"a": 5}\n3|{"a": 6}\n'
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        kept, _ = same(tmp_path, data, out="id:int, n:str", paths={"id": "", "n": "$.a[0]"})
    assert kept == ["1;7", "2;", "3;"]
    said = [record.getMessage() for record in caplog.records if record.name.startswith("src.v2")]
    assert said == ["[it] the path $.a[0] could not be followed on 2 item(s); it found nothing there"]


def test_no_rows_in(tmp_path):
    kept, rejected = same(tmp_path, b"id|raw\n", reject="")
    assert kept == [] and len(rejected) <= 1


# ------------------------------------------------------------------
# What is refused
# ------------------------------------------------------------------

@pytest.mark.parametrize("config, key, said", [
    ({"read_by": "XPATH", "loop_query": "/a/b"}, "read_by", None),
    ({"paths": {"id": "", "n": "$.[["}}, "mapping_4_jsonpath[1].query", None),
    ({"json_loop_query": "$.[["}, "json_loop_query", None),
    ({"jsonfield": "nope"}, "jsonfield", "there is no column 'nope' (id, raw)"),
    ({"paths": {}}, "mapping_4_jsonpath", "names no column to fill"),
    ({"nope": 1}, "nope", None),
])
def test_what_cannot_be_read_refuses_the_job(config, key, said):
    kwargs = {"out": "id:int, n:str", "paths": {"id": "", "n": "$.who"}, **config}
    found = refusals(extract(**kwargs))
    assert [path for path, _ in found] == [key]
    assert said is None or found[0][1] == said


def test_converters_sample_is_refused_for_reading_by_xpath():
    found = refusals(json.loads(SAMPLE.read_text()))
    assert [key for key, _ in found] == ["read_by"]


def test_keys_that_change_nothing(tmp_path):
    unread = dict(json_path_version="2_1_0", encoding="UTF-8", loop_query="/a", mapping=[])
    assert same(tmp_path, **unread) == same(tmp_path / "b")


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("extract_json_fields", "ExtractJSONFields", "tExtractJSONFields")):
        (tmp_path / str(at)).mkdir()
        result, files = v2(tmp_path / str(at), extract(kind=kind))
        assert result.status == "success" and files["out.csv"][2] == "2;bob;;false;;;;"


# ------------------------------------------------------------------
# What an independent review found (ticket 77)
# ------------------------------------------------------------------

def test_loop_path_that_cannot_be_followed_on_a_document_turns_its_row_away(tmp_path):
    data = b'id|raw\n1|[5]\n2|{"x": 1}\n3|7\n'
    kept, rejected = same(tmp_path, data, out="id:int, a:str", paths={"id": "", "a": "$"}, json_loop_query="$[0]", reject="")
    assert kept == ["1;5"]
    assert rejected[1:] == ['2;{"x": 1};{"x": 1};PARSE_ERROR;loop query error: 0',
                            "3;7;7;PARSE_ERROR;loop query error: object of type 'int' has no len()"]


def test_job_that_is_to_die_names_the_first_row_turned_away(tmp_path):
    made = extract(out="id:int, a:str", paths={"id": "", "a": "$"}, json_loop_query="$[0]", die_on_error=True)
    result, _ = v2(tmp_path, made, b'id|raw\n1|[5]\n2|{"x": 1}\n3|nope\n')
    assert result.error == "PARSE_ERROR: loop query error: 0 (the first of 2 such rows); the row is line 3 of in.csv"


def test_object_and_list_are_written_as_json_with_their_own_characters_escaped(tmp_path):
    data = '1|{"o": {"k": "é", "n": [1, 2.5, null, true]}, "l": ["日本", "x"]}\n'.encode("utf-8")
    kept, _ = same(tmp_path, b"id|raw\n" + data, out="id:int, o:str, l:str", paths={"id": "", "o": "$.o", "l": "$.l"})
    assert kept == ['1;{"k": "\\u00e9", "n": [1, 2.5, null, true]};["\\u65e5\\u672c", "x"]']


def test_number_that_is_none_is_missing(tmp_path):
    kept, _ = same(tmp_path, b'id|raw\n1|{"a": NaN}\n2|{"a": 1.5}\n', out="id:int, a:str", paths={"id": "", "a": "$.a"})
    assert kept == ["1;", "2;1.5"]


def test_source_that_is_true_or_false_is_no_json(tmp_path):
    kept, rejected = same(tmp_path, b"id|raw\n1|true\n2|false\n", schema="id:int, raw:bool", out="id:int, a:str",
                          paths={"id": "", "a": "$"}, reject="")
    assert kept == [] and [line.split(";")[3] for line in rejected[1:]] == ["PARSE_ERROR", "PARSE_ERROR"]


@pytest.mark.parametrize("pattern, written, got", [
    ("@%Y-%m-%d", "2024-01-31T10:11:12", "2024-01-31"), ("@%Y-%m-%d", "2024-01-31 10:11:12", "2024-01-31"),
    ("@%Y-%m-%d", "31/01/2024", "2024-01-31"), ("@%d/%m/%Y", "2024-01-31", "31/01/2024"),
    ("", "2024-01-31T10:11:12", "2024-01-31 10:11:12"),
])
def test_date_written_one_of_the_usual_ways_is_read(tmp_path, pattern, written, got):
    data = ('id|raw\n1|{"a": "%s"}\n' % written).encode()
    kept, _ = same(tmp_path, data, out=f"id:int, a:datetime{pattern}", paths={"id": "", "a": "$.a"})
    assert kept == [f"1;{got}"]


def test_moment_with_a_fraction_of_a_second_goes_missing_in_a_column_with_no_pattern(tmp_path):
    # v1 writes 2024-01-31 10:11:12.250000.
    data = b'id|raw\n1|{"a": "2024-01-31T10:11:12.250000"}\n2|{"a": "2024-01-31T10:11:12.25"}\n'
    made = extract(out="id:int, a:datetime, b:datetime@%Y-%m-%d %H:%M:%S.%f", paths={"id": "", "a": "$.a", "b": "$.a"})
    result, files = v2(tmp_path, made, data)
    assert result.status == "success"
    assert files["out.csv"][1:] == ["1;;2024-01-31 10:11:12.250000", "2;;2024-01-31 10:11:12.250000"]


def test_dates_of_one_column_written_in_two_ways_are_both_read(tmp_path):
    # v1 reads the usual ways only when no date of the column is written by its pattern.
    data = b'id|raw\n1|{"a": "2024-01-31"}\n2|{"a": "31/01/2024"}\n3|{"a": "soon"}\n'
    result, files = v2(tmp_path, extract(out="id:int, a:datetime@%Y-%m-%d", paths={"id": "", "a": "$.a"}), data)
    assert result.status == "success" and files["out.csv"][1:] == ["1;2024-01-31", "2;2024-01-31", "3;"]


def test_nothing_is_told_of_dropped_rows_when_the_subjob_fails(tmp_path, caplog):
    made = extract(out="id:int, n:str", paths={"id": "", "n": "$.n"})
    check = {"id": "then", "type": "ExtractDelimitedFields", "inputs": ["row2"], "outputs": ["row9"],
             "config": {"field": "n", "check_fields_num": True, "die_on_error": True},
             "schema": {"input": made["components"][1]["schema"]["output"],
                        "output": made["components"][1]["schema"]["output"] + [{"name": "p", "type": "str", "nullable": True}]}}
    made["components"].insert(2, check)
    made["components"][3]["inputs"] = ["row9"]
    made["flows"] = [flow("row1", "in", "it"), flow("row2", "it", "then"), flow("row9", "then", "out")]
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result, _ = v2(tmp_path, made, b'id|raw\n1|{"n": "a;b"}\n2|nope\n')
    assert result.status == "failed"
    assert not [record for record in caplog.records if "dropped" in record.getMessage()]


def test_mapping_given_as_nothing_refuses_the_job_by_its_key():
    made = extract()
    made["components"][1]["config"]["mapping_4_jsonpath"] = None
    assert [key for key, _ in refusals(made)] == ["mapping_4_jsonpath"]
