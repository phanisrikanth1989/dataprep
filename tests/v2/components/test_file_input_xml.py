"""XML file input: the records a path finds in a document, as rows."""
import copy
import json
import logging
import os
from pathlib import Path

import pytest

from src.v2 import load_job, run_job, xml_reader
from src.v2.components.file import file_input_xml
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, writer

from .test_file_actions_kit import filled, on_v2

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tFileInputXML_0.1.json"
ORDERS = b"""<orders region="north">
  <order id="1"><line><sku>A</sku><qty>2</qty><price>1.50</price></line><line><sku>B</sku><qty>10</qty><price>0.25</price></line><day>2024-01-31</day></order>
  <order id="2"><line><sku>C</sku><qty>1</qty><price>9</price></line><day>2024-02-01</day></order>
</orders>
"""
SCHEMA = "order:int, sku:str, qty:int, price:Decimal#2, day:datetime@%Y-%m-%d"
PATHS = {"order": "../@id", "sku": "sku", "qty": "qty", "price": "price", "day": "../day"}


def reading(schema=SCHEMA, paths=None, kind="FileInputXML", outputs=("row1",), **config):
    if paths is None:
        # The paths of the columns that are declared.
        declared = [column["name"] for column in columns(schema)] if schema else list(PATHS)
        paths = {name: PATHS[name] for name in declared if name in PATHS}
    made = {"filepath": "in.xml", "loop_query": "/orders/order/line", "encoding": "UTF-8",
            "mapping": [{"column": name, "xpath": path, "nodecheck": False} for name, path in paths.items()]}
    made.update(config)
    return {"id": "in", "type": kind, "config": made, "inputs": [], "outputs": list(outputs),
            "schema": {"input": [], "output": columns(schema) if schema else []}}


def read_to_file(schema=SCHEMA, rejects=False, paths=None, **config):
    """the XML input -> out.csv; with rejects, its reject output -> bad.csv."""
    parts = [reading(schema, paths, outputs=("row1", "bad") if rejects else ("row1",), **config), writer(schema, inputs=("row1",))]
    flows = [flow("row1", "in", "out")]
    if rejects:
        parts.append(writer(None, component_id="rej", path="bad.csv", inputs=("bad",)))
        flows.append(flow("bad", "in", "rej", "reject"))
    return job(parts, flows)


def ran(tmp_path, made, document=ORDERS, **files):
    folder = filled(tmp_path, dict(files, **({"in.xml": document} if document is not None else {})))
    result = on_v2(made, folder)
    return result, {path.name: path.read_text() for path in folder.glob("*.csv")}, folder


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# Records as rows
# ------------------------------------------------------------------

def test_record_is_a_row_with_each_value_in_the_type_its_column_declares(tmp_path):
    result, written, _ = ran(tmp_path, read_to_file())
    assert result.status == "success", result.error
    assert written["out.csv"] == ("order;sku;qty;price;day\n1;A;2;1.50;2024-01-31\n1;B;10;0.25;2024-01-31\n"
                                  "2;C;1;9.00;2024-02-01\n")
    assert result.rows["out"] == 3 and result.global_map["in_FILENAME"] == "in.xml"


def test_column_without_a_path_is_the_child_of_its_own_name_and_no_schema_gives_the_columns_of_the_mapping(tmp_path):
    made = read_to_file("sku:str, qty:int", paths={"qty": ""})
    _, written, _ = ran(tmp_path / "named", made)
    assert written["out.csv"] == "sku;qty\nA;2\nB;10\nC;1\n"
    made = job([reading(None, paths={"sku": "sku", "order": "../@id"}), writer(None)], [flow("row1", "in", "out")])
    _, written, _ = ran(tmp_path / "none", made)
    assert written["out.csv"] == "sku;order\nA;1\nB;1\nC;2\n"


def test_node_itself_is_handed_on_as_xml_text_where_asked_for(tmp_path):
    made = read_to_file("order:int, lines:str", loop_query="/orders/order", mapping=[
        {"column": "order", "xpath": "@id"}, {"column": "lines", "xpath": "line", "nodecheck": True}])
    _, written, _ = ran(tmp_path, made)
    assert written["out.csv"].splitlines()[1] == "1;<line><sku>A</sku><qty>2</qty><price>1.50</price></line>"


@pytest.mark.parametrize("limit, rows", [("", 3), ("2", 2), (2, 2), ("0", 0), (5, 3)])
def test_limit_is_the_most_records_read(tmp_path, limit, rows):
    result, written, _ = ran(tmp_path, read_to_file(limit=limit))
    assert result.status == "success" and len(written["out.csv"].splitlines()) == rows + 1


def test_converted_sample_job_reads_what_stands_after_a_record_as_well(tmp_path):
    made = copy.deepcopy(json.loads(SAMPLE.read_text()))
    reader = next(part for part in made["components"] if part["type"] == "FileInputXML")
    reader["config"]["filepath"] = "orders.xml"
    made["components"] = [reader, writer(None)]
    made["flows"] = [flow("row2", reader["id"], "out")]
    reader["outputs"] = ["row2"]
    made["triggers"] = []
    orders = "".join(
        f"<order><orderId>O{n}</orderId><customer><name>N{n}</name><email>e{n}@x.org</email><address><city>C{n}</city>"
        f"</address></customer><items>" + "".join(
            f"<item><productId>P{n}{m}</productId><productName>thing</productName><quantity>{m + 1}</quantity>"
            f"<unitPrice>2.5</unitPrice></item>" for m in range(2)) +
        f"</items><orderDate>2024-01-0{n + 1}</orderDate><status>S{n}</status></order>" for n in range(3))
    folder = filled(tmp_path, {"orders.xml": f"<orders>{orders}</orders>".encode()})
    result = on_v2(made, folder)
    assert result.status == "success", result.error
    rows = (folder / "out.csv").read_text().splitlines()
    assert len(rows) == 7 and rows[0].split(";")[:2] == ["orderId", "customerName"]
    # `status` is written after the items of its order, and is there for every item.
    assert [row.split(";")[-1] for row in rows[1:]] == ["S0", "S0", "S1", "S1", "S2", "S2"]


# ------------------------------------------------------------------
# A value that is not what its column declares
# ------------------------------------------------------------------

BAD = ORDERS.replace(b"<qty>10</qty>", b"<qty>ten</qty>")


def test_value_that_does_not_fit_its_column_fails_the_job_and_names_the_record(tmp_path):
    result, written, _ = ran(tmp_path, read_to_file(), BAD)
    assert (result.status, result.failed_component, written) == ("failed", "in", {})
    assert result.error == ("Schema/coercion failed for 1 row(s); first error: Column 'qty': could not convert string to "
                            "float: 'ten'; the row is record 2 of in.xml, near line 2")


def test_with_die_on_error_off_such_a_row_leaves_by_the_reject_output_with_why(tmp_path):
    result, written, _ = ran(tmp_path, read_to_file(rejects=True, die_on_error=False), BAD)
    assert result.status == "success", result.error
    assert written["out.csv"].splitlines()[1:] == ["1;A;2;1.50;2024-01-31", "2;C;1;9.00;2024-02-01"]
    assert written["bad.csv"] == ("order;sku;qty;price;day;errorCode;errorMessage\n"
                                  "1;B;ten;0.25;2024-01-31;TYPE_CONVERSION;Column 'qty': could not convert string to "
                                  "float: 'ten'\n")


def test_row_that_is_dropped_with_nowhere_to_go_is_said_in_the_log(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    result, written, _ = ran(tmp_path, read_to_file(die_on_error=False), BAD)
    assert result.status == "success" and len(written["out.csv"].splitlines()) == 3
    assert any("Column 'qty'" in record.getMessage() and "record 2 of in.xml" in record.getMessage()
               for record in caplog.records)


def test_missing_value_where_none_may_be_missing_is_a_fault_of_the_row(tmp_path):
    document = ORDERS.replace(b"<sku>B</sku>", b"")
    result, _, _ = ran(tmp_path / "dies", read_to_file("order:int, sku:str!, qty:int"), document)
    assert result.status == "failed" and "sku" in result.error and "record 2 of in.xml" in result.error
    result, written, _ = ran(tmp_path / "goes on", read_to_file("order:int, sku:str!, qty:int", rejects=True, die_on_error=False),
                             document)
    assert result.status == "success" and written["out.csv"].splitlines()[1:] == ["1;A;2", "2;C;1"]
    assert "SCHEMA_VIOLATION" in written["bad.csv"]


def test_path_that_finds_more_than_one_node_gives_the_first_and_a_warning_says_so(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    made = read_to_file("order:int, sku:str", loop_query="/orders/order", mapping=[
        {"column": "order", "xpath": "@id"}, {"column": "sku", "xpath": "line/sku"}])
    result, written, _ = ran(tmp_path, made)
    assert result.status == "success" and written["out.csv"] == "order;sku\n1;A\n2;C\n"
    assert [record.getMessage() for record in caplog.records] == [
        "[in] the path of column 'sku' found more than one node in 1 record (the first: record 1); the first node is "
        "the value"]


# ------------------------------------------------------------------
# A document that cannot be read
# ------------------------------------------------------------------

@pytest.mark.parametrize("document, said", [
    (b"<orders><order id='1'><line><sku>A</sku></line></order><order>", "'in.xml' is not well-formed XML: "),
    (b"", "'in.xml' is not well-formed XML: "),
    (b"just text", "'in.xml' is not well-formed XML: "),
    (b'<!DOCTYPE orders [<!ENTITY co "ACME">]><orders><order id="1"><line><sku>&co;</sku></line></order></orders>',
     "'in.xml' cannot be read: the document uses the entity '&co;' (near line 1): v2 reads no entity a document "
     "declares, since one may name another file"),
], ids=["cut short", "empty", "no XML", "an entity of its own"])
def test_document_that_cannot_be_read_fails_the_job_and_no_row_of_it_is_written(tmp_path, document, said):
    result, written, _ = ran(tmp_path, read_to_file("sku:str"), document)
    assert (result.status, result.failed_component, written) == ("failed", "in", {})
    assert result.error.startswith(said)
    if b"cut" in document or document.endswith(b"<order>"):
        assert "line 1" in result.error


def test_file_that_is_not_there_a_folder_and_a_pipe_fail_the_job(tmp_path):
    result, _, _ = ran(tmp_path / "none", read_to_file(), None)
    assert (result.status, result.error) == ("failed", "File not found: 'in.xml'")
    result, _, _ = ran(tmp_path / "folder", read_to_file(), None, **{"in.xml/": None})
    assert (result.status, result.error) == ("failed", "'in.xml' cannot be read: it is a folder")
    folder = filled(tmp_path / "pipe", {})
    os.mkfifo(folder / "in.xml")
    result = on_v2(read_to_file(), folder)
    assert (result.status, result.error) == ("failed", "'in.xml' cannot be read: it is no file, but a pipe or a device")


def test_file_that_may_not_be_read_fails_the_job_in_plain_words(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root may read everything")
    folder = filled(tmp_path, {"in.xml": ORDERS})
    os.chmod(folder / "in.xml", 0o000)
    result = on_v2(read_to_file(), folder)
    assert (result.status, result.error) == ("failed", "'in.xml' cannot be read: permission denied")


def test_encoding_the_parser_does_not_know_fails_the_job_for_a_document_that_says_none(tmp_path):
    result, _, _ = ran(tmp_path / "silent", read_to_file("sku:str", encoding="cp037"), b"<orders><order><line><sku>A</sku></line></order></orders>")
    assert (result.status, result.error) == (
        "failed", "'in.xml' says nothing of its encoding, and the parser of XML does not know 'cp037': name the encoding "
                  "in a way it knows (UTF-8, ISO-8859-15, windows-1252 and the like)")
    # A document that says its own is read by that, whatever the job names.
    said = b'<?xml version="1.0" encoding="UTF-8"?><orders><order><line><sku>A</sku></line></order></orders>'
    result, written, _ = ran(tmp_path / "said", read_to_file("sku:str", encoding="cp037"), said)
    assert result.status == "success" and written["out.csv"] == "sku\nA\n"


def test_job_that_is_not_to_die_goes_on_with_no_row_after_a_document_it_cannot_read(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    broken = b"<orders><order id='1'><line><sku>A</sku><qty>1</qty></line></order><order>"
    result, written, _ = ran(tmp_path, read_to_file("sku:str, qty:int", die_on_error=False), broken)
    assert result.status == "success", result.error
    assert written["out.csv"] == "sku;qty\n" and result.global_map["in_ERROR_MESSAGE"].startswith("'in.xml' is not well-formed XML")
    assert caplog.records[0].getMessage().endswith("; the job goes on with no row")


# ------------------------------------------------------------------
# Namespaces and the encoding
# ------------------------------------------------------------------

SPACED = b"""<o:orders xmlns:o="urn:orders" xmlns="urn:default"><o:order id="1"><line><sku>A</sku></line></o:order></o:orders>"""


def test_names_are_matched_by_their_local_name_unless_the_namespaces_are_given(tmp_path):
    plain = read_to_file("order:int, sku:str", paths={"order": "../@id", "sku": "sku"})
    _, written, _ = ran(tmp_path / "local", plain, SPACED)
    assert written["out.csv"] == "order;sku\n1;A\n"
    given = read_to_file("order:int, sku:str", paths={"order": "../@id", "sku": "d:sku"}, loop_query="/o:orders/o:order/d:line",
                         namespaces={"o": "urn:orders", "d": "urn:default"})
    _, written, _ = ran(tmp_path / "given", given, SPACED)
    assert written["out.csv"] == "order;sku\n1;A\n"
    other = read_to_file("order:int, sku:str", paths={"order": "../@id", "sku": "sku"}, loop_query="/o:orders/o:order/d:line",
                         namespaces={"o": "urn:orders", "d": "urn:default"})
    _, written, _ = ran(tmp_path / "strict", other, SPACED)
    assert written["out.csv"] == "order;sku\n1;\n"


def test_what_the_document_says_of_its_encoding_decides_and_the_jobs_is_for_one_that_says_nothing(tmp_path):
    word = "caf" + chr(233)
    said = f'<?xml version="1.0" encoding="UTF-8"?><orders><order><line><sku>{word}</sku></line></order></orders>'.encode("utf-8")
    _, written, folder = ran(tmp_path / "said", read_to_file("sku:str", encoding="ISO-8859-15"), said)
    assert (folder / "out.csv").read_bytes() == f"sku\n{word}\n".encode("utf-8")
    silent = f"<orders><order><line><sku>{word}</sku></line></order></orders>".encode("iso-8859-15")
    _, written, folder = ran(tmp_path / "silent", read_to_file("sku:str", encoding="ISO-8859-15"), silent)
    assert (folder / "out.csv").read_bytes() == f"sku\n{word}\n".encode("utf-8")


# ------------------------------------------------------------------
# Read once, held on disk, and put away
# ------------------------------------------------------------------

def test_document_is_gone_through_once_however_often_the_engine_reads_the_source(tmp_path, monkeypatch):
    walks = []
    really = xml_reader.Records.__iter__
    monkeypatch.setattr(xml_reader.Records, "__iter__", lambda self: walks.append(1) or really(self))
    made = dict(read_to_file(rejects=True, die_on_error=False), run={"row_counts": True})
    result, written, _ = ran(tmp_path, made, BAD)
    assert result.status == "success" and len(written["out.csv"].splitlines()) == 3 and walks == [1]
    assert result.counts["in"] == {"NB_LINE": 3, "NB_LINE_OK": 2, "NB_LINE_REJECT": 1}


def test_rows_wait_in_scratch_files_a_batch_each_and_none_is_left_behind(tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setenv("V2_TEMP_DIR", str(scratch))
    monkeypatch.setattr(file_input_xml, "_BATCH_ROWS", 2)
    seen = []
    really = file_input_xml.pl.scan_ipc
    monkeypatch.setattr(file_input_xml.pl, "scan_ipc", lambda files, *more, **kept: seen.append(len(files)) or really(files, *more, **kept))
    document = b"<orders><order id='7'>" + b"".join(b"<line><sku>S%d</sku></line>" % n for n in range(5)) + b"</order></orders>"
    result, written, _ = ran(tmp_path / "job", read_to_file("order:int, sku:str", paths={"order": "../@id", "sku": "sku"}), document)
    assert result.status == "success", result.error
    assert written["out.csv"] == "order;sku\n" + "".join(f"7;S{n}\n" for n in range(5))
    assert seen and set(seen) == {3} and list(scratch.iterdir()) == []


def test_run_for_picked_records_names_them_by_their_number(tmp_path):
    made = dict(read_to_file(), run={"only": {"source": "in", "records": [2]}})
    result, written, _ = ran(tmp_path, made)
    assert result.status == "success", result.error
    assert written["out.csv"].splitlines()[1:] == ["1;B;10;0.25;2024-01-31"]
    assert result.summary()["only"] == {"source": "in", "rows": ["record 2 of in.xml, near line 2"]}


def test_document_is_gone_through_once_also_where_the_engine_reads_the_source_twice(tmp_path, monkeypatch):
    # A run for picked rows reads the source once to find them and once more to run.
    reads, walks = [], []
    really_read, really_walk = file_input_xml.FileInputXML.read, xml_reader.Records.__iter__
    monkeypatch.setattr(file_input_xml.FileInputXML, "read", lambda self: reads.append(1) or really_read(self))
    monkeypatch.setattr(xml_reader.Records, "__iter__", lambda self: walks.append(1) or really_walk(self))
    made = dict(read_to_file(), run={"only": {"source": "in", "where": {"sku": "B"}}})
    result, written, _ = ran(tmp_path, made)
    assert result.status == "success", result.error
    assert len(reads) > 1 and walks == [1]


def test_document_deeper_than_the_parser_allows_fails_and_names_the_key_that_lifts_it(tmp_path):
    deep = ("<orders>" + "<a>" * 300 + "<order><sku>A</sku></order>" + "</a>" * 300 + "</orders>").encode()
    result, written, _ = ran(tmp_path / "held", read_to_file("sku:str", loop_query="//order"), deep)
    assert result.status == "failed" and "out.csv" not in written
    assert result.error.startswith("'in.xml' is not well-formed XML: Excessive depth in document: 256")
    assert "XML_PARSE_HUGE" not in result.error and "set `large_values` to read it" in result.error
    result, written, _ = ran(tmp_path / "lifted", read_to_file("sku:str", loop_query="//order", large_values=True), deep)
    assert result.status == "success" and written["out.csv"] == "sku\nA\n"


def test_value_larger_than_the_parser_allows_is_read_where_large_values_are_asked_for(tmp_path):
    big = b"<orders><order><line><sku>" + b"x" * (11 * 1024 * 1024) + b"</sku></line></order></orders>"
    result, _, _ = ran(tmp_path / "refused", read_to_file("sku:str", paths={"sku": "string-length(sku)"}), big)
    assert result.status == "failed" and result.error.startswith("'in.xml' is not well-formed XML: ")
    result, written, _ = ran(tmp_path / "asked", read_to_file("sku:str", paths={"sku": "string-length(sku)"}, large_values=True), big)
    assert result.status == "success" and written["out.csv"] == f"sku\n{11 * 1024 * 1024}\n"


# ------------------------------------------------------------------
# What is refused, a converted job, and the names it goes by
# ------------------------------------------------------------------

@pytest.mark.parametrize("config, said", [
    ({"loop_query": "/orders/order[@id='1']/line"},
     "loop_query: holds a condition ([@id='1']): the records are found by names alone; turn rows away with a filter "
     "after the reader"),
    ({"loop_query": "orders/order"}, "loop_query: a record path starts at the root: write it as /orders/order"),
    ({"mapping": [{"column": "sku", "xpath": "/orders/order/day"}]},
     "mapping[0].xpath: starts at the root: a column is found from its record, by a path without the leading /"),
    ({"mapping": [{"column": "sku", "xpath": "sku["}]}, "mapping[0].xpath: is no XPath (Invalid expression)"),
    ({"mapping": [{"column": "sku", "xpath": "../../../../x"}]},
     "mapping[0].xpath: climbs 4 levels above its record, and '/orders/order/line' is 3 deep"),
    ({"loop_query": "//line", "mapping": [{"column": "sku", "xpath": "../day"}]},
     "mapping[0].xpath: climbs above its record, and '//line' may be at any depth: with //, a column reads its record "
     "and the attributes of what is above it"),
    ({"mapping": [{"column": "nope", "xpath": "x"}]}, "mapping[0].column: there is no column 'nope'; the columns are: sku"),
    ({"limit": "some"}, "limit: 'some' is no number of records"),
    ({"limit": -1}, "limit: -1 is no number of records"),
    ({"use_separator": True}, "use_separator: v2 reads a node's text as it is: split it with a step after the reader"),
    ({"namespaces": {"o": 5}}, "namespaces: the namespace of the prefix 'o' is no text"),
    ({"nope": 1}, "nope: unknown config key"),
])
def test_what_cannot_be_read_refuses_the_job(config, said):
    found = refusals(job([reading("sku:str", **config), writer("sku:str", inputs=("row1",))], [flow("row1", "in", "out")]))
    assert [f"{key}: {reason}" for key, reason in found] == [said]


def test_rows_are_picked_by_the_number_of_their_record_and_by_nothing_else():
    made = dict(read_to_file(), run={"only": {"source": "in", "rows": [2]}})
    with pytest.raises(JobRefusedError) as refused:
        run_job(made)
    assert [(refusal.key, refusal.reason) for refusal in refused.value.report] == [
        ("run.only.rows", "'in' reads the records of a document: pick its rows with `records`")]


def test_job_is_refused_in_plain_words_where_the_library_that_reads_xml_is_not_there(monkeypatch):
    monkeypatch.setattr(xml_reader, "etree", None)
    assert refusals(read_to_file()) == [("config", "reading XML needs the lxml package (pip install 'dataprep[v2]')")]


def test_what_the_converter_writes_is_taken(tmp_path):
    made = read_to_file(
        kind="tFileInputXML", limit="", die_on_error=False, ignore_ns=False, ignore_dtd=False, generation_mode="Dom4j",
        advanced_separator=False, thousands_separator=",", decimal_separator=".", check_date=False, use_separator=False,
        field_separator=",", tstatcatcher_stats=False, label="x")
    result, written, _ = ran(tmp_path, made)
    assert result.status == "success" and len(written["out.csv"].splitlines()) == 4


@pytest.mark.parametrize("kind", ["file_input_xml", "FileInputXML", "tFileInputXML"])
def test_every_name_of_it(tmp_path, kind):
    result, written, _ = ran(tmp_path, read_to_file(kind=kind))
    assert result.status == "success" and len(written["out.csv"].splitlines()) == 4
