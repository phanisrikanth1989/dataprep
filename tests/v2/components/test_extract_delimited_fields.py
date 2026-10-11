"""Extract delimited fields, against v1 on the same job config and bytes."""
import json
import logging
import os
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2 import answer_key
from tests.v2.answer_key import assert_matches_v1

from .kit import columns, flow, job, reader, writer

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tExtractDelimitedFields_0.1.json"
IN = "id:int, raw:str"
OUT = "id:int, a:str, b:str, c:str"
DATA = b"id|raw\n1|a;b;c\n2|d;e\n3|f;g;h;i\n4|\n5| x ; y ;z \n6|;;\n"


def extract(schema=IN, out=OUT, reject=None, kind="ExtractDelimitedFields", **config):
    """file (fields separated by |) -> extract -> out.csv, and rej.csv for the reject output when asked."""
    step = {"id": "it", "type": kind, "config": {"field": "raw", **config},
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
        header = ";".join(column["name"] for column in made["components"][1]["schema"]["input"]) + ";errorCode;errorMessage\n"
        assert run.files["rej.csv"] == key.files["rej.csv"] or (
            key.files["rej.csv"] == b"" and run.files["rej.csv"].decode() == header)
    return (run.files["out.csv"].decode().splitlines()[1:],
            run.files.get("rej.csv", b"").decode().splitlines())


def v2(tmp_path, made, data=DATA):
    """Run on v2 alone, inside tmp_path; returns how it ended and the lines of each file written."""
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
# Pieces become columns
# ------------------------------------------------------------------

def test_pieces_go_to_the_columns_that_do_not_arrive_in_their_order(tmp_path):
    kept, _ = same(tmp_path)
    assert kept == ["1;a;b;c", "2;d;e;", "3;f;g;h", "4;;;", "5; x ; y ;z ", "6;;;"]


def test_source_column_is_handed_on_when_the_output_declares_it(tmp_path):
    kept, _ = same(tmp_path, out="id:int, raw:str, a:str, b:str, c:str")
    assert kept[:3] == ["1;a;b;c;a;b;c", "2;d;e;d;e;", "3;f;g;h;i;f;g;h"]


def test_output_columns_come_in_the_order_they_are_declared(tmp_path):
    kept, _ = same(tmp_path, out="a:str, id:int, b:str, raw:str")
    assert kept[:2] == ["a;1;b;a;b;c", "d;2;e;d;e"]


def test_nothing_is_extracted_when_every_output_column_arrives(tmp_path):
    kept, _ = same(tmp_path, out="id:int, raw:str")
    assert kept[:2] == ["1;a;b;c", "2;d;e"]


def test_blanks_around_a_piece_are_dropped_when_asked(tmp_path):
    kept, _ = same(tmp_path, trim=True)
    assert kept[4] == "5;x;y;z"


@pytest.mark.parametrize("separator, data, kept", [
    (",", b"id|raw\n1|a,b\n2|a::b::c\n", ["1;a;b;", "2;a::b::c;;"]),
    ("::", b"id|raw\n1|a,b\n2|a::b::c\n", ["1;a,b;;", "2;a;b;c"]),
    ('"."', b"id|raw\n1|a.b\n2|a,b\n", ["1;a;b;", "2;a,b;;"]),
    ("'.'", b"id|raw\n1|a.b\n", ["1;a;b;"]),
    ("", b"id|raw\n1|a;b\n", ["1;a;b;"]),
    ("|", b"id,raw\n1,a|b|c\n", ["1;a;b;c"]),
    (".*", b"id|raw\n1|a.*b\n2|ab\n", ["1;a;b;", "2;ab;;"]),
])
def test_separator_is_taken_as_it_is_written(tmp_path, separator, data, kept):
    made = extract(fieldseparator=separator)
    if separator == "|":
        made["components"][0]["config"]["fieldseparator"] = ","
    run = assert_matches_v1(made, {"in.csv": data}, tmp_path)
    assert run.files["out.csv"].decode().splitlines()[1:] == kept


def test_pieces_are_read_as_the_types_the_output_declares(tmp_path):
    out = "id:int, a:int, b:float, c:Decimal#2, d:datetime@%Y-%m-%d, e:bool"
    kept, _ = same(tmp_path, b"id|raw\n1|7;1.5;2.5;2024-01-31;true\n2|8;2;3;2024-02-01;1\n", out=out)
    assert kept == ["1;7;1.5;2.50;2024-01-31;true", "2;8;2.0;3.00;2024-02-01;true"]


def test_piece_that_cannot_be_read_as_its_type_goes_missing(tmp_path):
    # v1 has 7.0 for the whole number beside a missing one, writes text through in a Decimal column, takes
    # any text for true (the word false too) and an empty piece for false.
    out = "id:int, a:int, b:float, c:Decimal#2, d:datetime@%Y-%m-%d, e:bool"
    data = b"id|raw\n1|7;1.5;2.5;2024-01-31;true\n2|x;y;z;nope;maybe\n3|;;;;\n4|8;2;3;2024-02-01;false\n"
    result, files = v2(tmp_path, extract(out=out), data)
    assert result.status == "success", result.error
    assert files["out.csv"][1:] == ["1;7;1.5;2.50;2024-01-31;true", "2;;;;;", "3;;;;;", "4;8;2.0;3.00;2024-02-01;false"]


# ------------------------------------------------------------------
# A source that is not text, or is missing
# ------------------------------------------------------------------

def test_number_is_split_as_the_text_it_is_written_as(tmp_path):
    kept, _ = same(tmp_path, b"id|raw\n1|1.5\n2|2\n", schema="id:int, raw:float", out="id:int, a:str, b:str", fieldseparator=".")
    assert kept == ["1;1;5", "2;2;0"]


def test_date_is_split_as_the_text_its_pattern_writes(tmp_path):
    # v1 splits Python's text for it: 2024-01-31 00:00:00.
    made = extract(schema="id:int, raw:datetime@%d/%m/%Y", out="id:int, a:str, b:str, c:str", fieldseparator="/")
    result, files = v2(tmp_path, made, b"id|raw\n1|31/01/2024\n")
    assert result.status == "success" and files["out.csv"][1:] == ["1;31;01;2024"]


def test_row_with_no_source_is_left_out_without_a_word(tmp_path, caplog):
    data = b"id|raw\n1|1.5\n2|\n3|2.5\n"
    kept, rejected = same(tmp_path, data, schema="id:int, raw:float", out="id:int, a:str, b:str", fieldseparator=".", reject="")
    assert kept == ["1;1;5", "3;2;5"] and rejected in ([], ["id;raw;errorCode;errorMessage"])
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        (tmp_path / "b").mkdir()
        made = extract(schema="id:int, raw:float", out="id:int, a:str, b:str", fieldseparator=".")
        result, _ = v2(tmp_path / "b", made, data)
    assert result.status == "success" and not caplog.records


def test_row_with_no_source_leaves_by_the_reject_output_when_it_is_not_to_be_left_out(tmp_path):
    kept, rejected = same(tmp_path, b"id|raw\n1|1.5\n2|\n3|2.5\n", schema="id:int, raw:float", out="id:int, a:str, b:str",
                          fieldseparator=".", reject="", ignore_source_null=False)
    assert kept == ["1;1;5", "3;2;5"]
    assert rejected == ["id;raw;errorCode;errorMessage", "2;;NULL_SOURCE;Source column 'raw' is null"]


def test_row_with_no_source_never_fails_the_job(tmp_path):
    kept, rejected = same(tmp_path, b"id|raw\n1|1.5\n2|\n", schema="id:int, raw:float", out="id:int, a:str, b:str",
                          fieldseparator=".", reject="", ignore_source_null=False, die_on_error=True, check_fields_num=True)
    assert kept == ["1;1;5"] and rejected[1:] == ["2;;NULL_SOURCE;Source column 'raw' is null"]


def test_empty_text_is_one_empty_piece_and_no_missing_source(tmp_path):
    kept, rejected = same(tmp_path, reject="", ignore_source_null=False)
    assert "4;;;" in kept and len(rejected) <= 1


# ------------------------------------------------------------------
# The number of pieces
# ------------------------------------------------------------------

def test_row_with_more_or_fewer_pieces_than_columns_leaves_by_the_reject_output_when_asked(tmp_path):
    kept, rejected = same(tmp_path, reject="", check_fields_num=True)
    assert kept == ["1;a;b;c", "5; x ; y ;z ", "6;;;"]
    assert rejected == [
        "id;raw;errorCode;errorMessage",
        "2;d;e;FIELD_COUNT_MISMATCH;Expected 3 tokens, got 2",
        "3;f;g;h;i;FIELD_COUNT_MISMATCH;Expected 3 tokens, got 4",
        "4;;FIELD_COUNT_MISMATCH;Expected 3 tokens, got 1",
    ]


def test_wrong_number_of_pieces_fails_the_job_when_it_is_to_die(tmp_path):
    made = extract(check_fields_num=True, die_on_error=True)
    assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    (tmp_path / "x").mkdir()
    result, files = v2(tmp_path / "x", made)
    assert result.status == "failed" and files == {}
    assert result.error == "Expected 3 tokens, got 2 (the first of 3 such rows); the row is line 3 of in.csv"


def test_rows_turned_away_with_no_flow_to_take_them_are_told_in_the_log(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        result, files = v2(tmp_path, extract(check_fields_num=True))
    assert result.status == "success" and files["out.csv"][1:] == ["1;a;b;c", "5; x ; y ;z ", "6;;;"]
    assert [record.getMessage() for record in caplog.records] == [
        "[it] 3 rows were dropped (no flow takes this component's rejects); the first: "
        "Expected 3 tokens, got 2; the row is line 3 of in.csv"]


def test_missing_value_where_none_is_allowed_fails_the_job_or_drops_the_row(tmp_path):
    made = extract(out="id:int, a:str!, b:str!", die_on_error=True)
    assert_matches_v1(made, {"in.csv": b"id|raw\n1|7;x\n2|8\n"}, tmp_path)
    (tmp_path / "x").mkdir()
    result, _ = v2(tmp_path / "x", made, b"id|raw\n1|7;x\n2|8\n")
    assert result.status == "failed"
    assert result.error == "Column 'b' has NULL values but is not nullable; the row is line 3 of in.csv"
    kept, _ = same(tmp_path / "y", b"id|raw\n1|7;x\n2|8\n", out="id:int, a:str!, b:str!", die_on_error=False)
    assert kept == ["1;7;x"]


# ------------------------------------------------------------------
# What is refused, and what changes nothing
# ------------------------------------------------------------------

def test_source_column_that_is_not_there_refuses_the_job():
    assert refusals(extract(field="nope")) == [("field", "there is no column 'nope' (id, raw)")]
    made = extract()
    del made["components"][1]["config"]["field"]
    assert [key for key, _ in refusals(made)] == ["field"]


def test_source_column_is_looked_for_when_the_rows_arrive_where_the_input_declares_none(tmp_path):
    # The reader before it declares its columns, so the job is still refused before it runs.
    made = extract(field="nope")
    made["components"][1]["schema"]["input"] = []
    assert [reason for _, reason in refusals(made)] == ["field: there is no column 'nope' (id, raw)"]


def test_unknown_key_refuses_the_job():
    assert [key for key, _ in refusals(extract(separator=","))] == ["separator"]


def test_keys_v1_never_acts_on_change_nothing(tmp_path):
    unread = dict(advanced_separator=True, thousands_separator=".", decimal_separator=",", check_date=True)
    assert same(tmp_path, **unread) == same(tmp_path / "b")


def test_converters_sample_loads():
    made = json.loads(SAMPLE.read_text())
    assert load_job(made).components["tExtractDelimitedFields_1"].config["fieldseparator"] == ";"


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("extract_delimited_fields", "ExtractDelimitedFields", "tExtractDelimitedFields")):
        (tmp_path / str(at)).mkdir()
        result, files = v2(tmp_path / str(at), extract(kind=kind))
        assert result.status == "success" and files["out.csv"][1] == "1;a;b;c"
