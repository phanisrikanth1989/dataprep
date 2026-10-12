"""Extract XML field: the records a path finds in the document a column holds, as rows."""
import json
import logging
import os
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError

from .kit import columns, flow, job, reader, writer

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tExtractXMLFields_0.1.json"
IN = "id:int, doc:str"
OUT = "id:int, sku:str, qty:int, price:Decimal#2"
PATHS = {"id": "", "sku": "sku", "qty": "qty", "price": "@price"}
DATA = (b'id|doc\n'
        b'1|<order><line price="1.5"><sku>A</sku><qty>2</qty></line><line price="2"><sku>B</sku><qty>1</qty></line></order>\n'
        b'2|<order><line price="3"><sku>C</sku><qty>5</qty></line></order>\n')


def extract(out=OUT, paths=PATHS, schema=IN, reject=None, kind="ExtractXMLField", checks=(), **config):
    """file (fields separated by |) -> extract -> out.csv, and rej.csv for the reject output when its columns are given."""
    made = {"xmlfield": "doc", "loop_query": "/order/line",
            "mapping": [{"schema_column": column, "query": path, "nodecheck": column in checks} for column, path in paths.items()]}
    made.update(config)
    step = {"id": "it", "type": kind, "config": made, "schema": {"input": columns(schema), "output": columns(out)},
            "inputs": ["row1"], "outputs": ["row2"] + (["bad"] if reject is not None else [])}
    parts = [reader(schema, header_rows=1, fieldseparator="|"), step, writer(out)]
    flows = [flow("row1", "in", "it"), flow("row2", "it", "out")]
    if reject is not None:
        parts.append(writer(reject or None, component_id="rej", path="rej.csv", inputs=("bad",)))
        flows.append(flow("bad", "it", "rej", kind="reject"))
    return job(parts, flows)


def ran(tmp_path, data=DATA, **kwargs):
    """Run on v2 inside tmp_path; returns how it ended and the lines of each file written, under their headers."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(extract(**kwargs))
    finally:
        os.chdir(previous)
    return result, {path.name: path.read_text().splitlines()[1:] for path in sorted(tmp_path.glob("*.csv")) if path.name != "in.csv"}


def rows(tmp_path, data=DATA, **kwargs):
    result, files = ran(tmp_path, data, **kwargs)
    assert result.status == "success", result.error
    return files["out.csv"]


def refusals(**kwargs):
    with pytest.raises(JobRefusedError) as refused:
        load_job(extract(**kwargs))
    return [f"{refusal.key}: {refusal.reason}" for refusal in refused.value.report]


def lines_of(*documents):
    """The documents, each as a row with its number."""
    return b"id|doc\n" + b"".join(f"{at}|{document}\n".encode("utf-8") for at, document in enumerate(documents, start=1))


# ------------------------------------------------------------------
# Records to rows
# ------------------------------------------------------------------

def test_every_record_of_a_rows_document_is_a_row_with_the_rows_own_columns_beside_it(tmp_path):
    result, files = ran(tmp_path)
    assert result.status == "success", result.error
    assert files["out.csv"] == ["1;A;2;1.50", "1;B;1;2.00", "2;C;5;3.00"]
    assert result.rows["out"] == 3


def test_document_with_no_record_gives_no_row_and_neither_does_a_row_with_no_document(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    data = lines_of("<order/>", "", "<order><line><sku>A</sku></line></order>", "<other><line/></other>")
    made = dict(paths={"id": "", "sku": "sku"}, out="id:int, sku:str",
                reject="id:str, sku:str, errorXMLField:str, errorCode:str, errorMessage:str")
    result, files = ran(tmp_path / "text", data, **made)
    assert result.status == "success", result.error
    assert files["out.csv"] == ["3;A"]
    # Empty text is no document, and that row is turned away. (A text column of a delimited file holds empty text
    # for an empty field, not nothing; the column is read as a number below to have nothing in it.)
    assert [line.split(";")[0] for line in files["rej.csv"]] == ["2"]
    result, files = ran(tmp_path / "nothing", b"id|doc\n1|\n2|7\n", schema="id:int, doc:int", **made)
    assert result.status == "success", result.error
    assert files["out.csv"] == [] and [line.split(";")[0] for line in files["rej.csv"]] == ["2"]
    assert "[it] 1 row holds no document in 'doc' and gives no row" in [record.getMessage() for record in caplog.records]
    ran(tmp_path / "two", b"id|doc\n1|\n2|\n", schema="id:int, doc:int", **made)
    assert "[it] 2 rows hold no document in 'doc' and give no row" in [record.getMessage() for record in caplog.records]


def test_path_of_a_column_is_followed_from_the_record_or_from_the_root_and_may_be_any_xpath(tmp_path):
    paths = {"id": "", "sku": "/order/line[1]/sku", "qty": "count(../line)", "price": "sum(../line/@price)",
             "both": "concat(sku, '-', qty)", "up": "../@region", "last": "../line[last()]/sku",
             "before": "preceding-sibling::line[1]/sku"}
    data = DATA.replace(b"<order>", b'<order region="north">')
    got = rows(tmp_path, data, paths=paths, out=OUT + ", both:str, up:str, last:str, before:str")
    assert got == ["1;A;2;3.50;A-2;north;B;", "1;A;2;3.50;B-1;north;B;A", "2;C;1;3.00;C-5;north;C;"]


def test_loop_query_may_be_any_xpath_that_finds_elements(tmp_path):
    for at, (query, found) in enumerate([
            ("/order/line[qty > 1]", ["1;A;2;1.50", "2;C;5;3.00"]), ("//line[last()]", ["1;B;1;2.00", "2;C;5;3.00"]),
            ("(/order/line)[position() < 3]", ["1;A;2;1.50", "1;B;1;2.00", "2;C;5;3.00"]),
            ("/order/line | /order/nope", ["1;A;2;1.50", "1;B;1;2.00", "2;C;5;3.00"]),
            ('"/order/line"', ["1;A;2;1.50", "1;B;1;2.00", "2;C;5;3.00"])]):
        assert rows(tmp_path / str(at), loop_query=query) == found, query


def test_records_are_the_same_however_many_wait_before_they_are_put_into_a_frame(tmp_path, monkeypatch, caplog):
    from src.v2.components.transform import extract_xml_field

    caplog.set_level(logging.WARNING, logger="src.v2")
    monkeypatch.setattr(extract_xml_field, "_BATCH", 2)
    put_together, really = [], extract_xml_field.pl.concat
    monkeypatch.setattr(extract_xml_field.pl, "concat", lambda frames, **more: put_together.append(len(frames)) or really(frames, **more))
    documents = [f"<order>{''.join(f'<line><sku>{at}-{n}</sku><sku>x</sku></line>' for n in range(at % 4))}</order>"
                 for at in range(1, 12)]
    got = rows(tmp_path, lines_of(*documents), paths={"id": "", "sku": "sku"}, out="id:int, sku:str")
    assert got == [f"{at};{at}-{n}" for at in range(1, 12) for n in range(at % 4)]
    # Sixteen records, put into a frame whenever two or more wait when a document is done.
    assert put_together[0] > 4
    assert [record.getMessage() for record in caplog.records] == [
        f"[it] the path of column 'sku' found more than one node in {len(got)} records (the first: record 1); the first "
        "node is the value"]


def test_missing_value_in_a_column_that_may_not_be_missing_is_turned_away_or_fails_the_job_and_names_the_row(tmp_path):
    # The engine's own check of what a component hands on; it names the row of the document by what is carried.
    data = lines_of("<order><line><sku>A</sku></line></order>", "<order><line><sku>B</sku></line><line/></order>")
    made = dict(paths={"id": "", "sku": "sku"}, out="id:int, sku:str!")
    result, files = ran(tmp_path / "away", data, reject="", **made)
    assert result.status == "success", result.error
    assert files["out.csv"] == ["1;A", "2;B"] and len(files["rej.csv"]) == 1 and "SCHEMA_VIOLATION" in files["rej.csv"][0]
    result, _ = ran(tmp_path / "die", data, die_on_error=True, **made)
    assert (result.status, result.failed_component) == ("failed", "it")
    assert result.error == "Column 'sku' has NULL values but is not nullable; the row is line 3 of in.csv"


def test_node_that_is_not_there_is_a_missing_value_and_an_empty_one_is_empty_text_or_a_missing_number(tmp_path):
    nil = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:nil="true"'
    data = lines_of(f"<order><line><sku/><qty/></line><line/><line><sku {nil}/><qty {nil}/></line>"
                    "<line><sku> a b </sku><qty>7</qty></line></order>")
    result, files = ran(tmp_path, data, paths={"id": "", "sku": "sku", "qty": "qty"}, out="id:int, sku:str, qty:int",
                        reject="")
    assert result.status == "success", result.error
    # The delimited output writes nothing for both: the second row is told apart by the test below.
    assert files["out.csv"] == ["1;;", "1;;", "1;;", "1; a b ;7"] and files["rej.csv"] == []


def test_missing_is_told_from_empty(tmp_path):
    data = lines_of("<order><line><sku/></line><line/></order>")
    paths = {"id": "", "sku": "sku", "is": "boolean(sku)"}
    made = extract(paths=paths, out="id:int, sku:str, is:str")
    made["components"][2] = {"id": "out", "type": "FileOutputXML", "inputs": ["row2"], "outputs": [],
                             "config": {"filename": "out.xml", "encoding": "UTF-8", "missing": "omit"},
                             "schema": {"input": columns("id:int, sku:str, is:str"), "output": []}}
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    assert (tmp_path / "out.xml").read_text().splitlines()[2:4] == [
        "<row><id>1</id><sku></sku><is>true</is></row>", "<row><id>1</id><is>false</is></row>"]


def test_of_several_nodes_the_first_is_the_value_and_a_warning_says_so(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    data = lines_of("<order><line><sku>A</sku><sku>B</sku></line><line><sku>C</sku></line><line><sku>D</sku><sku>E</sku></line></order>")
    assert rows(tmp_path, data, paths={"id": "", "sku": "sku"}, out="id:int, sku:str") == ["1;A", "1;C", "1;D"]
    assert [record.getMessage() for record in caplog.records] == [
        "[it] the path of column 'sku' found more than one node in 2 records (the first: record 1); the first node "
        "is the value"]


def test_node_itself_is_the_value_as_xml_text_where_it_is_asked_for(tmp_path):
    data = lines_of('<order><line a="1"><sku>A &amp; B</sku><part><n>1</n></part></line><line/></order>')
    paths = {"id": "", "sku": "sku", "part": "part", "whole": "."}
    got = rows(tmp_path, data, paths=paths, out="id:int, sku:str, part:str, whole:str", checks=("sku", "part", "whole"))
    assert got == ['1;<sku>A &amp; B</sku>;<part><n>1</n></part>;<line a="1"><sku>A &amp; B</sku><part><n>1</n></part></line>',
                   "1;;;<line/>"]


def test_column_with_no_path_is_the_input_column_of_its_name_and_missing_where_there_is_none(tmp_path):
    paths = {"id": "", "sku": "sku", "note": ""}
    assert rows(tmp_path / "entry", paths=paths, out="id:int, sku:str, note:str") == ["1;A;", "1;B;", "2;C;"]
    # No entry at all is the same as an entry with no path.
    assert rows(tmp_path / "none", paths={"sku": "sku"}, out="id:int, sku:str, note:str") == ["1;A;", "1;B;", "2;C;"]
    # The document's own column may be handed on too.
    got = rows(tmp_path / "doc", b"id|doc\n1|<order><line><sku>A</sku></line></order>\n", paths={"sku": "sku"},
               out="sku:str, doc:str")
    assert got == ["A;<order><line><sku>A</sku></line></order>"]


def test_columns_are_those_of_the_mapping_as_text_where_none_is_declared(tmp_path):
    made = extract(paths={"sku": "sku", "qty": "qty"})
    made["components"][1]["schema"] = {"input": [], "output": []}
    made["components"][2]["schema"] = {"input": [], "output": []}
    (tmp_path / "in.csv").write_bytes(DATA)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    assert (tmp_path / "out.csv").read_text().splitlines() == ["sku;qty", "A;2", "B;1", "C;5"]


def test_document_column_is_the_first_when_none_is_named_and_any_kind_of_column_is_read_as_its_text(tmp_path):
    data = b"doc|id\n<order><line><sku>A</sku></line></order>|1\n"
    assert rows(tmp_path, data, schema="doc:str, id:int", xmlfield="", paths={"id": "", "sku": "sku"},
                out="id:int, sku:str") == ["1;A"]


# ------------------------------------------------------------------
# The most rows
# ------------------------------------------------------------------

@pytest.mark.parametrize("limit, made", [("", 3), (None, 3), ("2", 2), (1, 1), ("0", 0), ("3", 3), ("9", 3)])
def test_limit_is_the_most_rows_of_the_whole_flow(tmp_path, limit, made):
    assert rows(tmp_path, limit=limit) == ["1;A;2;1.50", "1;B;1;2.00", "2;C;5;3.00"][:made]


def test_rows_after_the_limit_are_not_read(tmp_path):
    data = lines_of("<order><line><sku>A</sku></line></order>", "this is no document")
    result, files = ran(tmp_path, data, paths={"id": "", "sku": "sku"}, out="id:int, sku:str", limit="1", die_on_error=True)
    assert result.status == "success" and files["out.csv"] == ["1;A"]


# ------------------------------------------------------------------
# What is turned away
# ------------------------------------------------------------------

REJECT = "id:str, sku:str, qty:str, price:str, errorXMLField:str, errorCode:str, errorMessage:str"


def test_document_that_is_not_well_formed_is_turned_away_with_what_is_wrong_and_the_rows_around_it_go_on(tmp_path):
    data = lines_of("<order><line><sku>A</sku></line></order>", "<order><line></order>", "", "plain text",
                    "<order><line><sku>B</sku></line></order>")
    result, files = ran(tmp_path, data, reject=REJECT)
    assert result.status == "success", result.error
    assert files["out.csv"] == ["1;A;;", "5;B;;"]
    turned = [line.split(";") for line in files["rej.csv"]]
    assert [(row[0], row[4], row[5]) for row in turned] == [
        ("2", "<order><line></order>", "PARSE_ERROR"), ("3", "", "PARSE_ERROR"), ("4", "plain text", "PARSE_ERROR")]
    assert turned[0][6].startswith("the document is not well-formed XML: Opening and ending tag mismatch: line")
    assert turned[1][6] == "the document is empty"
    assert turned[2][6] == "the document is not well-formed XML: Start tag expected, '<' not found, line 1, column 1"
    assert result.rows["rej"] == 3


def test_value_that_is_none_of_its_columns_type_turns_its_record_away_and_the_other_records_go_on(tmp_path):
    data = lines_of('<order><line price="1"><sku>A</sku><qty>two</qty></line><line price="x"><sku>B</sku><qty>1</qty></line>'
                    '<line price="3"><sku>C</sku><qty>4</qty></line></order>')
    result, files = ran(tmp_path, data, reject=REJECT)
    assert result.status == "success", result.error
    assert files["out.csv"] == ["1;C;4;3.00"]
    assert files["rej.csv"] == [
        '1;A;two;1;<line price="1"><sku>A</sku><qty>two</qty></line>;TYPE_CONVERSION;'
        "Column 'qty': could not convert string to float: 'two'",
        '1;B;1;x;<line price="x"><sku>B</sku><qty>1</qty></line>;TYPE_CONVERSION;'
        "Column 'price': could not convert string to Decimal: 'x'"]


def test_what_is_turned_away_keeps_the_order_of_the_rows_whether_a_document_or_a_record_is_at_fault(tmp_path):
    data = lines_of("<order><line><sku>A</sku><qty>x</qty></line></order>", "<order>",
                    "<order><line><sku>B</sku><qty>1</qty></line><line><sku>C</sku><qty>y</qty></line></order>", "no")
    result, files = ran(tmp_path / "all", data, reject=REJECT)
    assert result.status == "success", result.error
    assert [(line.split(";")[0], line.split(";")[-2]) for line in files["rej.csv"]] == [
        ("1", "TYPE_CONVERSION"), ("2", "PARSE_ERROR"), ("3", "TYPE_CONVERSION"), ("4", "PARSE_ERROR")]
    assert files["rej.csv"][2].split(";")[4] == "<line><sku>C</sku><qty>y</qty></line>"
    # The first fault is the first in the order of the rows, whichever kind it is.
    result, _ = ran(tmp_path / "die", data, die_on_error=True)
    assert result.error == "Column 'qty': could not convert string to float: 'x'; the row is line 2 of in.csv"


def test_column_that_a_path_fills_is_not_the_input_column_of_its_name_also_where_the_document_cannot_be_read(tmp_path):
    data = b"id|sku|doc\n1|IN|<order><line><sku>A</sku></line></order>\n2|IN|<order>\n"
    result, files = ran(tmp_path, data, schema="id:int, sku:str, doc:str", paths={"id": "", "sku": "sku"},
                        out="id:int, sku:str", reject="id:str, sku:str, errorXMLField:str, errorCode:str, errorMessage:str")
    assert result.status == "success", result.error
    assert files["out.csv"] == ["1;A"] and files["rej.csv"][0].startswith("2;;<order>;PARSE_ERROR;")


def test_rows_that_carry_nothing_of_where_they_came_from_are_turned_away_all_the_same():
    # Rows a step of the job's own code made: no column of them is handed on, and none says where a row came from.
    import polars as pl

    from src.v2.components.transform.extract_xml_field import ExtractXMLField
    from src.v2.engine.context import RunContext

    spec = load_job(extract(paths={"sku": "sku", "qty": "qty"}, out="sku:str, qty:int", reject="")).components["it"]
    rows_in = pl.DataFrame({"doc": ["<order><line><sku>A</sku><qty>x</qty></line></order>", "<order>", "no"]})
    made = ExtractXMLField(spec, spec.config, RunContext("t", {})).run({"row1": rows_in})
    assert made["main"].height == 0
    assert made["reject"].select("sku", "qty", "errorCode").rows() == [
        ("A", "x", "TYPE_CONVERSION"), (None, None, "PARSE_ERROR"), (None, None, "PARSE_ERROR")]


def test_output_column_named_as_a_reason_is_gives_its_place_to_the_reason_among_what_is_turned_away(tmp_path):
    data = lines_of("<order><line><errorCode>E1</errorCode><qty>1</qty></line><line><errorCode>E2</errorCode><qty>x</qty></line></order>")
    result, files = ran(tmp_path, data, paths={"id": "", "errorCode": "errorCode", "qty": "qty"},
                        out="id:int, errorCode:str, qty:int", reject="")
    assert result.status == "success", result.error
    assert files["out.csv"] == ["1;E1;1"]
    assert files["rej.csv"] == ["1;x;<line><errorCode>E2</errorCode><qty>x</qty></line>;TYPE_CONVERSION;"
                                "Column 'qty': could not convert string to float: 'x'"]


def test_rows_turned_away_with_no_flow_to_take_them_are_dropped_with_a_warning_that_names_the_first(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    data = lines_of("<order><line><sku>A</sku></line></order>", "<order>", "<order><line><qty>x</qty></line></order>")
    result, files = ran(tmp_path, data)
    assert result.status == "success" and files["out.csv"] == ["1;A;;"]
    said = [record.getMessage() for record in caplog.records]
    assert len(said) == 1 and said[0].startswith(
        "[it] 2 rows were dropped (no flow takes this component's rejects); the first: the document is not "
        "well-formed XML: ")
    assert said[0].endswith("; the row is line 3 of in.csv")


def test_job_that_is_to_die_fails_on_the_first_document_or_value_that_is_wrong_and_names_the_row(tmp_path):
    data = lines_of("<order><line><sku>A</sku></line></order>", "<order>")
    result, files = ran(tmp_path / "document", data, die_on_error=True)
    assert (result.status, result.failed_component) == ("failed", "it")
    assert result.error.startswith("the document is not well-formed XML: ")
    assert result.error.endswith("; the row is line 3 of in.csv") and "out.csv" not in files
    data = lines_of("<order><line><qty>1</qty></line><line><qty>x</qty></line></order>")
    result, files = ran(tmp_path / "value", data, die_on_error=True)
    assert result.status == "failed" and "out.csv" not in files
    assert result.error == "Column 'qty': could not convert string to float: 'x'; the row is line 2 of in.csv"


def test_nothing_but_the_document_is_read_whatever_it_says(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET")
    inner = f'<!DOCTYPE order [<!ENTITY e SYSTEM "file://{secret}">]><order><line><sku>&e;</sku></line></order>'
    laughs = ('<!DOCTYPE order [<!ENTITY a "ha"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;"><!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;">]>'
              "<order><line><sku>&c;</sku></line></order>")
    outer = f'<!DOCTYPE order SYSTEM "file://{tmp_path}/nope.dtd"><order><line><sku>A</sku></line></order>'
    result, files = ran(tmp_path / "run", lines_of(inner, laughs, outer), paths={"id": "", "sku": "sku"},
                        out="id:int, sku:str", reject="id:str, sku:str, errorXMLField:str, errorCode:str, errorMessage:str")
    assert result.status == "success", result.error
    # A document that names a DTD it does not use is read; no DTD is.
    assert files["out.csv"] == ["3;A"]
    turned = [line.split(";") for line in files["rej.csv"]]
    assert [row[0] for row in turned] == ["1", "2"] and "TOP-SECRET" not in "".join(files["rej.csv"] + files["out.csv"])
    said = "(near line 1): v2 reads no entity a document declares, since one may name another file"
    assert files["rej.csv"][0].endswith(f";PARSE_ERROR;the document uses the entity '&e;' {said}")
    assert files["rej.csv"][1].endswith(f";PARSE_ERROR;the document uses the entity '&c;' {said}")


def test_parsers_own_limits_hold_unless_large_values_are_asked_for(tmp_path):
    deep = "<order>" + "<a>" * 300 + "<line><sku>A</sku></line>" + "</a>" * 300 + "</order>"
    made = dict(loop_query="//line", paths={"id": "", "sku": "sku"}, out="id:int, sku:str")
    result, files = ran(tmp_path / "held", lines_of(deep), reject="id:str, errorCode:str, errorMessage:str", **made)
    assert result.status == "success" and files["out.csv"] == []
    # The parser's own advice names a switch of its own; the message names the job's key.
    assert ";PARSE_ERROR;the document is not well-formed XML: Excessive depth in document: 256" in files["rej.csv"][0]
    assert "XML_PARSE_HUGE" not in files["rej.csv"][0] and "set `large_values` to read it" in files["rej.csv"][0]
    assert rows(tmp_path / "lifted", lines_of(deep), large_values=True, **made) == ["1;A"]


# ------------------------------------------------------------------
# Namespaces, and how a document says it is written
# ------------------------------------------------------------------

SPACED = ('<o:order xmlns:o="urn:orders" xmlns="urn:lines"><line p:price="1.5" xmlns:p="urn:prices"><sku>A</sku>'
          '<o:qty>2</o:qty></line></o:order>')


def test_names_are_matched_by_their_local_name_whatever_prefix_the_document_or_the_path_has(tmp_path):
    for at, (loop, paths) in enumerate([
            ("/order/line", {"id": "", "sku": "sku", "qty": "qty", "price": "@price"}),
            ("/x:order/y:line", {"id": "", "sku": "z:sku", "qty": "o:qty", "price": "@p:price"})]):
        assert rows(tmp_path / str(at), lines_of(SPACED), loop_query=loop, paths=paths) == ["1;A;2;1.50"]


def test_with_namespaces_given_a_path_is_read_as_xpath_says(tmp_path):
    given = {"o": "urn:orders", "l": "urn:lines", "p": "urn:prices"}
    paths = {"id": "", "sku": "l:sku", "qty": "o:qty", "price": "@p:price"}
    assert rows(tmp_path / "bound", lines_of(SPACED), loop_query="/o:order/l:line", paths=paths, namespaces=given) == ["1;A;2;1.50"]
    # A name without a prefix is in no namespace, and finds nothing here.
    assert rows(tmp_path / "bare", lines_of(SPACED), loop_query="/order/line", paths=paths, namespaces=given) == []
    paths = dict(paths, sku="sku")
    assert rows(tmp_path / "half", lines_of(SPACED), loop_query="/o:order/l:line", paths=paths, namespaces=given) == ["1;;2;1.50"]


def test_what_a_documents_declaration_says_of_its_encoding_is_not_read_again(tmp_path):
    # The text is text already: a declaration of another encoding in it is what the document was once written in.
    document = '<?xml version="1.0" encoding="ISO-8859-1"?><order><line><sku>caf' + chr(233) + "</sku></line></order>"
    assert rows(tmp_path, lines_of(document), paths={"id": "", "sku": "sku"}, out="id:int, sku:str") == ["1;caf" + chr(233)]


# ------------------------------------------------------------------
# What is refused, a converted job, and the names it goes by
# ------------------------------------------------------------------

@pytest.mark.parametrize("config, said", [
    ({"xmlfield": "nope"}, "xmlfield: there is no column 'nope'; the columns are: id, doc"),
    ({"loop_query": ""}, "loop_query: there is no path"),
    ({"loop_query": "/order/line["}, "loop_query: is no XPath (Invalid expression)"),
    ({"loop_query": "/o:order", "namespaces": {"x": "urn:x"}}, "loop_query: is no XPath (Undefined namespace prefix)"),
    ({"paths": {"sku": "sku[", "id": ""}}, "mapping[0].query: is no XPath (Invalid expression)"),
    ({"paths": {"sku": "position()"}}, "mapping[0].query: is no XPath (Invalid context position)"),
    ({"loop_query": "order/line"},
     "loop_query: does not start at the root, where the records of a document are found from: write it as /order/line"),
    ({"loop_query": "line"},
     "loop_query: does not start at the root, where the records of a document are found from: write it as /line"),
    ({"paths": {"sku": "$v"}}, "mapping[0].query: is no XPath (Undefined variable)"),
    ({"paths": {"nope": "sku"}}, "mapping[0].schema_column: there is no column 'nope'; the columns are: id, sku, qty, price"),
    ({"limit": "many"}, "limit: 'many' is no number of rows"),
    ({"limit": -1}, "limit: -1 is no number of rows"),
    ({"namespaces": {"o": ""}}, "namespaces: the namespace of the prefix 'o' is no text"),
    ({"nope": 1}, "nope: unknown config key"),
])
def test_what_cannot_be_read_refuses_the_job(config, said):
    assert refusals(**config) == [said]


def test_job_is_refused_in_plain_words_where_the_library_that_reads_xml_is_not_there(monkeypatch):
    from src.v2 import xml_reader

    monkeypatch.setattr(xml_reader, "etree", None)
    assert refusals() == ["config: reading XML needs the lxml package (pip install 'dataprep[v2]')"]


def test_two_entries_for_one_column_and_an_entry_with_no_column_among_ones_that_have_theirs_refuse_the_job():
    made = extract()
    made["components"][1]["config"]["mapping"] = [{"schema_column": "sku", "query": "sku"}, {"schema_column": "sku", "query": "x"},
                                                  {"schema_column": "sku", "query": "y"}]
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    assert [f"{r.key}: {r.reason}" for r in refused.value.report] == [
        "mapping[1].schema_column: 'sku' has an entry already (mapping[0])",
        "mapping[2].schema_column: 'sku' has an entry already (mapping[0])"]
    made["components"][1]["config"]["mapping"] = [{"schema_column": "sku", "query": "sku"}, {"query": "qty"}]
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    assert [f"{r.key}: {r.reason}" for r in refused.value.report] == [
        "mapping[1].schema_column: this entry names no column, and others do: name the column of each"]


def test_entries_that_name_no_column_are_those_of_the_output_columns_in_their_order(tmp_path):
    # How an older converted job has them.
    made = extract()
    made["components"][1]["config"]["mapping"] = [{"query": "", "nodecheck": False}, {"query": "sku"}, {"query": "qty"},
                                                  {"query": "@price"}]
    (tmp_path / "in.csv").write_bytes(DATA)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    assert (tmp_path / "out.csv").read_text().splitlines()[1:] == ["1;A;2;1.50", "1;B;1;2.00", "2;C;5;3.00"]
    made["components"][1]["config"]["mapping"].append({"query": "more"})
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    assert [f"{r.key}: {r.reason}" for r in refused.value.report] == [
        "mapping: 5 entries that name no column, and the output has 4 columns: an entry for each, in their order"]


@pytest.mark.parametrize("query", ["/order/line/@price", "/order/line/sku/text()", "count(/order/line)", "//comment()",
                                   "string(/order)", "/order/line | /order/line/@price"])
def test_loop_query_that_finds_what_is_no_element_fails_the_job(tmp_path, query):
    data = DATA.replace(b"<order>", b"<order><!-- a note -->")
    result, files = ran(tmp_path, data, loop_query=query)
    assert (result.status, result.failed_component) == ("failed", "it")
    assert result.error == (f"loop_query: '{query}' finds what is no element (an attribute, a text, a number): "
                            "a record is an element")


def test_document_column_that_is_not_there_fails_the_job_where_no_columns_are_declared(tmp_path):
    made = extract(xmlfield="nope")
    made["components"][1]["schema"]["input"] = []
    (tmp_path / "in.csv").write_bytes(DATA)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    assert (result.status, result.error) == ("failed", "xmlfield: there is no column 'nope'; the columns are: id, doc")


def test_converted_sample_job_runs(tmp_path, caplog):
    # An older converted job: its entries name no column, and its paths start at the root.
    sample = json.loads(SAMPLE.read_text())
    by_id = {component["id"]: component for component in sample["components"]}
    by_id["tFileInputDelimited_1"]["config"]["filepath"] = "people.csv"
    (tmp_path / "people.csv").write_text(
        "id;xml_payload\n"
        "1;<person><name>Ann</name><age>41</age><city>Oslo</city></person>\n"
        "2;<person><name>Bob</name><age>x</age><city>Rome</city></person>\n")
    caplog.set_level(logging.INFO, logger="src.v2")
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(sample)
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    printed = [record.getMessage() for record in caplog.records if record.name.endswith("log_row")]
    assert any("1|Ann|41|Oslo" in line for line in printed) and not any("Bob" in line for line in printed)


@pytest.mark.parametrize("kind", ["extract_xml_field", "ExtractXMLField", "tExtractXMLField"])
def test_every_name_of_it(tmp_path, kind):
    assert rows(tmp_path, kind=kind) == ["1;A;2;1.50", "1;B;1;2.00", "2;C;5;3.00"]
