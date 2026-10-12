"""Multi-schema XML input: one document gone through once, its records of several kinds each to a flow of their own."""
import logging

import pytest

from src.v2 import load_job, xml_reader
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, writer

from .test_file_actions_kit import filled, on_v2

SHOP = b"""<?xml version="1.0" encoding="UTF-8"?>
<shop>
 <order id="1" region="north">
  <head><who> ann </who><day>2024-01-31</day></head>
  <line><sku>A</sku><qty>2</qty></line>
  <line><sku>B</sku><qty>1</qty></line>
  <note>first</note>
 </order>
 <order id="2" region="south">
  <head><who>bob</who><day>2024-02-01</day></head>
  <line><sku>C</sku><qty>5</qty></line>
 </order>
</shop>
"""
HEADS = "order:int, who:str, day:datetime@%Y-%m-%d"
LINES = "order:int, sku:str, qty:int"
NOTES = "order:int, text:str"
ENTRIES = [
    {"flow": "heads", "loop_path": "head", "columns": columns(HEADS), "mapping": "../@id,who,day"},
    {"flow": "lines", "loop_path": "line", "columns": columns(LINES), "mapping": ["../@id", "sku", "qty"]},
    {"flow": "notes", "loop_path": "note", "columns": columns(NOTES),
     "mapping": [{"column": "order", "xpath": "../@id"}, {"column": "text", "xpath": "."}]},
]


def reading(entries=None, schema=None, kind="FileInputMSXML", outputs=None, **config):
    entries = ENTRIES if entries is None else entries
    made = {"filename": "in.xml", "root_loop_query": "/shop/order", "schemas": entries}
    made.update(config)
    names = outputs if outputs is not None else [entry.get("flow") or "row1" for entry in entries]
    return {"id": "in", "type": kind, "config": made, "inputs": [], "outputs": list(names),
            "schema": {"input": [], "output": columns(schema) if schema else []}}


def reads(entries=None, schema=None, flows=None, **config):
    """The input, and a delimited file for each of its flows, named after the flow and with the flow's columns."""
    source = reading(entries, schema, **config)
    names = flows if flows is not None else source["outputs"]
    if flows is not None:
        source["outputs"] = list(flows)
    parts = [source]
    for name in names:
        to = writer(None, component_id=f"to_{name}", path=f"{name}.csv", inputs=(name,))
        said = [entry.get("columns") for entry in source["config"]["schemas"] if entry.get("flow", "") in (name, "")]
        to["schema"]["input"] = (said[0] if said and said[0] else None) or source["schema"]["output"]
        parts.append(to)
    return job(parts, [flow(name, "in", f"to_{name}") for name in names])


def ran(tmp_path, made=None, document=SHOP, **files):
    folder = filled(tmp_path, dict(files, **({"in.xml": document} if document is not None else {})))
    result = on_v2(reads() if made is None else made, folder)
    return result, {path.stem: path.read_text().splitlines() for path in sorted(folder.glob("*.csv"))}, folder


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [f"{refusal.key}: {refusal.reason}" for refusal in refused.value.report]


# ------------------------------------------------------------------
# Records of several kinds
# ------------------------------------------------------------------

def test_records_of_each_kind_go_to_the_flow_of_their_kind_in_the_order_of_the_document(tmp_path):
    result, written, _ = ran(tmp_path)
    assert result.status == "success", result.error
    assert written == {
        "heads": ["order;who;day", "1;ann;2024-01-31", "2;bob;2024-02-01"],
        "lines": ["order;sku;qty", "1;A;2", "1;B;1", "2;C;5"],
        "notes": ["order;text", "1;first"]}
    assert result.global_map["in_FILENAME"] == "in.xml"


def test_document_is_gone_through_once_for_all_the_flows(tmp_path, monkeypatch):
    walks, really = [], xml_reader.Several.__iter__
    monkeypatch.setattr(xml_reader.Several, "__iter__", lambda self: walks.append(1) or really(self))
    result, written, _ = ran(tmp_path)
    assert result.status == "success" and walks == [1] and len(written) == 3


def test_one_entry_needs_no_flow_named_and_takes_its_columns_from_the_component_as_a_converted_job_has_it(tmp_path):
    entries = [{"loop_path": "/line", "mapping": '"../@id","sku","qty"', "create_empty_row": False}]
    result, written, _ = ran(tmp_path, reads(entries, schema=LINES, outputs=["row1"]))
    assert result.status == "success", result.error
    assert written == {"row1": ["order;sku;qty", "1;A;2", "1;B;1", "2;C;5"]}


def test_columns_with_no_path_are_the_children_of_their_names(tmp_path):
    entries = [{"flow": "lines", "loop_path": "line", "columns": columns("sku:str, qty:int"), "mapping": ""},
               {"flow": "heads", "loop_path": "head", "columns": columns("who:str")}]
    result, written, _ = ran(tmp_path, reads(entries))
    assert result.status == "success", result.error
    assert written == {"heads": ["who", "ann", "bob"], "lines": ["sku;qty", "A;2", "B;1", "C;5"]}


def test_paths_written_as_talend_writes_them_are_taken_apart_at_the_commas_that_stand_outside_brackets(tmp_path):
    entries = [{"flow": "lines", "loop_path": "line", "columns": columns("a:str, b:str, c:str"),
                "mapping": '"sku", "concat(sku, \'-\', qty)" ,../line[qty > 1 or sku = "B,C"]/sku'}]
    result, written, _ = ran(tmp_path / "quoted", reads(entries))
    assert result.status == "success", result.error
    assert written == {"lines": ["a;b;c", "A;A-2;A", "B;B-1;A", "C;C-5;C"]}
    # Without the quotes Talend puts round a path: a function keeps its commas, and so does a text in quotes.
    entries[0]["mapping"] = "sku,concat(sku, '-', qty),'x,y'"
    result, written, _ = ran(tmp_path / "bare", reads(entries))
    assert result.status == "success", result.error
    assert written == {"lines": ["a;b;c", "A;A-2;x,y", "B;B-1;x,y", "C;C-5;x,y"]}


def test_records_may_stand_deeper_than_one_step_and_a_record_may_hold_the_records_of_another_flow(tmp_path):
    entries = [{"flow": "orders", "loop_path": "order", "columns": columns("id:int, lines:int, first:str"),
                "mapping": "@id,count(line),line[1]/sku"},
               {"flow": "lines", "loop_path": "order/line", "columns": columns("order:int, sku:str"), "mapping": "../@id,sku"}]
    result, written, _ = ran(tmp_path, reads(entries, root_loop_query="/shop"))
    assert result.status == "success", result.error
    # The lines are read when each of them ends, and are still there when their order is read.
    assert written == {"orders": ["id;lines;first", "1;2;A", "2;1;C"], "lines": ["order;sku", "1;A", "1;B", "2;C"]}


def test_column_may_read_what_stands_above_its_record(tmp_path):
    entries = [{"flow": "lines", "loop_path": "line", "columns": columns("who:str, region:str, sku:str, note:str"),
                "mapping": "../head/who,../@region,sku,../note"}]
    result, written, _ = ran(tmp_path, reads(entries))
    assert result.status == "success", result.error
    # The note stands after the lines: a row is made when the order it looks into is whole.
    assert written == {"lines": ["who;region;sku;note", "ann;north;A;first", "ann;north;B;first", "bob;south;C;"]}


def test_flow_nobody_reads_is_no_fault_and_is_not_looked_for_in_the_document(tmp_path, monkeypatch):
    looked_for, really = [], xml_reader.Several.__init__
    monkeypatch.setattr(xml_reader.Several, "__init__",
                        lambda self, source, kinds, *more, **named: looked_for.append(len(kinds)) or really(self, source, kinds, *more, **named))
    result, written, _ = ran(tmp_path, reads(flows=["lines"]))
    assert result.status == "success", result.error
    assert written == {"lines": ["order;sku;qty", "1;A;2", "1;B;1", "2;C;5"]} and looked_for == [1]


def test_rows_are_the_same_however_many_wait_before_they_go_to_a_scratch_file(tmp_path, monkeypatch):
    from src.v2.components.file import file_input_msxml

    wrote, really = [], file_input_msxml.pl.DataFrame.write_ipc
    monkeypatch.setattr(file_input_msxml.pl.DataFrame, "write_ipc", lambda self, *a, **k: wrote.append(self.height) or really(self, *a, **k))
    monkeypatch.setattr(file_input_msxml, "_BATCH_ROWS", 2)
    result, written, _ = ran(tmp_path / "by rows")
    assert result.status == "success", result.error
    assert written["lines"] == ["order;sku;qty", "1;A;2", "1;B;1", "2;C;5"] and len(written["heads"]) == 3
    # Two lines are put away when the second has been read, and each flow's rest at the end.
    assert wrote == [2, 2, 1, 1]
    wrote.clear()
    monkeypatch.setattr(file_input_msxml, "_BATCH_ROWS", 50_000)
    monkeypatch.setattr(file_input_msxml, "_BATCH_CHARACTERS", 12)
    result, written, _ = ran(tmp_path / "by size")
    assert result.status == "success", result.error
    assert written["lines"] == ["order;sku;qty", "1;A;2", "1;B;1", "2;C;5"] and written["notes"] == ["order;text", "1;first"]
    # Every flow's rows go when the values of all of them together have grown large, and the count starts anew:
    # the first head, then two lines and the note, then the second head, and the last line at the end.
    assert wrote == [1, 2, 1, 1, 1]


def test_run_for_a_few_records_reads_those_whichever_flow_they_are_of(tmp_path):
    made = dict(reads(), run={"only": {"source": "in", "records": [3, 4]}})
    result, written, _ = ran(tmp_path, made)
    assert result.status == "success", result.error
    assert written == {"heads": ["order;who;day"], "lines": ["order;sku;qty", "1;B;1"], "notes": ["order;text", "1;first"]}


def test_document_is_gone_through_once_however_often_the_engine_reads_the_source(tmp_path, monkeypatch):
    from src.v2.components.file import file_input_msxml

    reads_made, walks = [], []
    really_read, really_walk = file_input_msxml.FileInputMSXML.read, xml_reader.Several.__iter__
    monkeypatch.setattr(file_input_msxml.FileInputMSXML, "read", lambda self: reads_made.append(1) or really_read(self))
    monkeypatch.setattr(xml_reader.Several, "__iter__", lambda self: walks.append(1) or really_walk(self))
    # Rows picked by what a column holds are looked for in a reading of their own.
    entries = [{"loop_path": "line", "mapping": "../@id,sku,qty"}]
    made = dict(reads(entries, schema=LINES, outputs=["row1"]), run={"only": {"source": "in", "where": {"sku": "B"}}})
    result, written, _ = ran(tmp_path, made)
    assert result.status == "success", result.error
    assert written == {"row1": ["order;sku;qty", "1;B;1"]} and len(reads_made) > 1 and walks == [1]


def test_rows_of_several_flows_are_picked_by_their_records_and_not_by_what_a_column_holds(tmp_path):
    # Which flow's column is meant has no answer: the component has no columns of its own to pick by.
    made = dict(reads(), run={"only": {"source": "in", "where": {"sku": "B"}}})
    with pytest.raises(JobRefusedError) as refused:
        ran(tmp_path, made)
    assert [f"{refusal.key}: {refusal.reason}" for refusal in refused.value.report] == [
        "run.only.where: 'in' has no column 'sku'; its columns are: none"]


def test_what_waits_for_what_is_above_it_waits_for_its_own_kind(tmp_path):
    # Both kinds look into their order, which is whole when it ends: each kind's records wait apart.
    entries = [{"flow": "lines", "loop_path": "line", "columns": columns("sku:str, note:str"), "mapping": "sku,../note"},
               {"flow": "heads", "loop_path": "head", "columns": columns("who:str, lines:int"), "mapping": "who,count(../line)"}]
    result, written, _ = ran(tmp_path, reads(entries))
    assert result.status == "success", result.error
    assert written == {"lines": ["sku;note", "A;first", "B;first", "C;"], "heads": ["who;lines", "ann;2", "bob;1"]}


def test_record_that_looks_no_higher_than_itself_is_read_when_it_ends_whatever_another_kind_waits_for(tmp_path):
    # The lines wait for their order; a head does not, and is the first record of the document.
    entries = [{"flow": "lines", "loop_path": "line", "columns": columns("sku:str, note:str"), "mapping": "sku,../note"},
               {"flow": "heads", "loop_path": "head", "columns": columns("who:str, day:int"), "mapping": "who,day"}]
    result, _, _ = ran(tmp_path, reads(entries))
    assert result.error.endswith("; the row is record 1 of in.xml (heads), near line 4")


def test_of_several_nodes_the_first_is_the_value_and_a_warning_names_the_flow(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    entries = [{"flow": "orders", "loop_path": "order", "columns": columns("sku:str"), "mapping": "line/sku"}]
    result, written, _ = ran(tmp_path, reads(entries, root_loop_query="/shop/"))
    assert result.status == "success" and written == {"orders": ["sku", "A", "C"]}
    assert [record.getMessage() for record in caplog.records] == [
        "[in] the path of column 'sku' of 'orders' found more than one node in 1 record (the first: record 1); the "
        "first node is the value"]
    caplog.clear()
    entries = [{"flow": "heads", "loop_path": "order/head", "columns": columns("who:str"), "mapping": "who"}] + entries
    result, _, _ = ran(tmp_path / "second", reads(entries, root_loop_query="/shop"))
    assert [record.getMessage() for record in caplog.records] == [
        "[in] the path of column 'sku' of 'orders' found more than one node in 1 record (the first: record 2); the "
        "first node is the value"]


def test_node_itself_is_the_value_where_an_entry_of_the_mapping_asks_for_it(tmp_path):
    entries = [{"flow": "lines", "loop_path": "line", "columns": columns("sku:str, whole:str"),
                "mapping": [{"schema_column": "sku", "query": "sku"}, {"column": "whole", "xpath": ".", "nodecheck": True}]}]
    result, written, _ = ran(tmp_path, reads(entries))
    assert result.status == "success", result.error
    assert written["lines"][1] == "A;<line><sku>A</sku><qty>2</qty></line>"


def test_columns_of_the_one_entry_are_those_of_its_mapping_as_text_where_none_is_declared(tmp_path):
    entries = [{"loop_path": "line", "mapping": [{"column": "sku", "xpath": "sku"}, {"column": "n", "xpath": "qty"}]}]
    result, written, _ = ran(tmp_path, reads(entries, outputs=["row1"]))
    assert result.status == "success", result.error
    assert written == {"row1": ["sku;n", "A;2", "B;1", "C;5"]}


def test_key_column_of_a_flow_is_named_with_the_record_that_fails(tmp_path):
    entries = [dict(ENTRIES[1], columns=[dict(column, key=column["name"] == "sku") for column in columns(LINES)])]
    result, _, _ = ran(tmp_path, reads(entries), SHOP.replace(b"<qty>1</qty>", b"<qty>one</qty>"))
    assert result.error.endswith("; the row is record 2 of in.xml (lines), near line 6 (sku=B)")


# ------------------------------------------------------------------
# Values
# ------------------------------------------------------------------

def test_white_space_around_a_value_goes_unless_it_is_to_stay(tmp_path):
    entries = [{"flow": "heads", "loop_path": "head", "columns": columns("who:str"), "mapping": "who"}]
    _, written, _ = ran(tmp_path / "trimmed", reads(entries))
    assert written == {"heads": ["who", "ann", "bob"]}
    _, written, _ = ran(tmp_path / "as it is", reads(entries, trim_all=False))
    assert written == {"heads": ["who", " ann ", "bob"]}


def test_record_with_no_value_at_all_gives_no_row_unless_empty_rows_are_asked_for(tmp_path):
    document = b"<shop><order><line><sku>A</sku></line><line><sku/></line><line/><line><qty>1</qty></line></order></shop>"
    entries = [{"flow": "lines", "loop_path": "line", "columns": columns("sku:str, qty:int"), "mapping": "sku,qty"}]
    _, written, _ = ran(tmp_path / "left out", reads(entries), document)
    assert written == {"lines": ["sku;qty", "A;", ";1"]}
    entries[0]["create_empty_row"] = True
    _, written, _ = ran(tmp_path / "kept", reads(entries), document)
    assert written == {"lines": ["sku;qty", "A;", ";", ";", ";1"]}


def test_value_that_is_none_of_its_columns_type_fails_the_job_and_names_the_record_or_is_dropped_with_a_warning(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    document = SHOP.replace(b"<qty>1</qty>", b"<qty>one</qty>")
    result, written, _ = ran(tmp_path / "dies", reads(), document)
    assert (result.status, result.failed_component) == ("failed", "in")
    assert result.error == ("Schema/coercion failed for 1 row(s); first error: Column 'qty': could not convert string to "
                            "float: 'one'; the row is record 3 of in.xml (lines), near line 6")
    assert written == {}
    result, written, _ = ran(tmp_path / "goes on", reads(die_on_error=False), document)
    assert result.status == "success", result.error
    assert written["lines"] == ["order;sku;qty", "1;A;2", "2;C;5"] and len(written["heads"]) == 3
    assert [record.getMessage() for record in caplog.records if record.levelname == "WARNING"] == [
        "[in] 1 row was dropped: Column 'qty': could not convert string to float: 'one'; the row is record 3 of in.xml "
        "(lines), near line 6"]


def test_document_that_is_not_well_formed_fails_the_job_or_gives_no_row_where_the_job_is_to_go_on(tmp_path):
    result, written, _ = ran(tmp_path / "dies", reads(), SHOP[:-10])
    assert (result.status, written) == ("failed", {})
    assert result.error.startswith("'in.xml' is not well-formed XML: ")
    result, written, _ = ran(tmp_path / "goes on", reads(die_on_error=False), SHOP[:-10])
    assert result.status == "success", result.error
    assert written == {"heads": ["order;who;day"], "lines": ["order;sku;qty"], "notes": ["order;text"]}
    assert result.global_map["in_ERROR_MESSAGE"].startswith("'in.xml' is not well-formed XML: ")


@pytest.mark.parametrize("document, said", [
    (None, "File not found: 'in.xml'"),
    (b'<!DOCTYPE shop [<!ENTITY e "x">]><shop><order><line><sku>&e;</sku></line></order></shop>',
     "'in.xml' cannot be read: the document uses the entity '&e;' (near line 1): v2 reads no entity a document "
     "declares, since one may name another file"),
])
def test_document_that_cannot_be_read_fails_the_job_in_plain_words(tmp_path, document, said):
    result, written, _ = ran(tmp_path, reads(), document)
    assert (result.status, result.failed_component, result.error, written) == ("failed", "in", said, {})


def test_path_that_is_no_file_and_a_file_that_may_not_be_read_fail_the_job_in_plain_words(tmp_path):
    import os

    folder = filled(tmp_path / "folder", {"in.xml/": None})
    result = on_v2(reads(), folder)
    assert (result.status, result.error) == ("failed", "'in.xml' cannot be read: it is a folder")
    if os.geteuid() == 0:
        pytest.skip("root may read everything")
    folder = filled(tmp_path / "locked", {"in.xml": SHOP})
    os.chmod(folder / "in.xml", 0o000)
    try:
        result = on_v2(reads(), folder)
    finally:
        os.chmod(folder / "in.xml", 0o644)
    assert (result.status, result.error) == ("failed", "'in.xml' cannot be read: permission denied")


def test_record_is_found_for_a_message_also_where_a_flow_before_its_own_has_no_record(tmp_path):
    entries = [{"flow": "gone", "loop_path": "nope", "columns": columns("x:str"), "mapping": "x"}, dict(ENTRIES[1])]
    result, _, _ = ran(tmp_path, reads(entries), SHOP.replace(b"<qty>1</qty>", b"<qty>one</qty>"))
    assert result.error.endswith("; the row is record 2 of in.xml (lines), near line 6")


def test_rows_are_picked_by_their_records_and_a_record_that_is_not_there_is_said(tmp_path):
    made = dict(reads(), run={"only": {"source": "in", "rows": [2]}})
    with pytest.raises(JobRefusedError) as refused:
        ran(tmp_path / "rows", made)
    assert [f"{refusal.key}: {refusal.reason}" for refusal in refused.value.report] == [
        "run.only.rows: 'in' reads the records of a document: pick its rows with `records`"]
    result, written, _ = ran(tmp_path / "none", dict(reads(), run={"only": {"source": "in", "records": [99]}}))
    assert (result.status, result.failed_component) == ("failed", "in")
    assert result.error == "'in' has no row at record 99"


def test_document_that_says_nothing_of_its_encoding_is_read_in_the_jobs(tmp_path):
    document = "<shop><order><line><sku>caf\u00e9</sku></line></order></shop>".encode("iso-8859-1")
    entries = [{"flow": "lines", "loop_path": "line", "columns": columns("sku:str"), "mapping": "sku"}]
    _, written, _ = ran(tmp_path / "known", reads(entries, encoding="ISO-8859-1"), document)
    assert written == {"lines": ["sku", "caf\u00e9"]}
    result, _, _ = ran(tmp_path / "unknown", reads(entries, encoding="cp037"), document)
    assert result.error == (
        "'in.xml' says nothing of its encoding, and the parser of XML does not know 'cp037': name the encoding in a "
        "way it knows (UTF-8, ISO-8859-15, windows-1252 and the like)")


def test_names_are_matched_by_their_local_name_unless_namespaces_are_given(tmp_path):
    document = (b'<s:shop xmlns:s="urn:shop" xmlns="urn:lines"><s:order id="1"><line><sku>A</sku></line></s:order></s:shop>')
    entries = [{"flow": "lines", "loop_path": "line", "columns": columns("order:int, sku:str"), "mapping": "../@id,sku"}]
    _, written, _ = ran(tmp_path / "local", reads(entries), document)
    assert written == {"lines": ["order;sku", "1;A"]}
    entries = [{"flow": "lines", "loop_path": "l:line", "columns": columns("order:int, sku:str"), "mapping": "../@id,l:sku"}]
    given = {"s": "urn:shop", "l": "urn:lines"}
    _, written, _ = ran(tmp_path / "bound", reads(entries, root_loop_query="/s:shop/s:order", namespaces=given), document)
    assert written == {"lines": ["order;sku", "1;A"]}


def test_rows_are_counted_over_all_the_flows(tmp_path):
    made = reads()
    made["run"] = {"row_counts": True}
    result, _, _ = ran(tmp_path, made)
    assert result.status == "success", result.error
    assert result.global_map["in_NB_LINE"] == 6


# ------------------------------------------------------------------
# What is refused, a converted job, and the names it goes by
# ------------------------------------------------------------------

def changed(at, **entry):
    entries = [dict(one) for one in ENTRIES]
    entries[at].update(entry)
    return entries


@pytest.mark.parametrize("made, said", [
    (reads(filename=""), "path: the file to read has no name"),
    (reads(root_loop_query="/shop/order[1]"),
     "root_loop_query: holds a condition ([1]): the records are found by names alone; turn rows away with a filter "
     "after the reader"),
    (reads(root_loop_query="shop/order"), "root_loop_query: a record path starts at the root: write it as /shop/order"),
    (reads([]), "schemas: names no kind of record: an entry for each flow"),
    (reads(changed(1, loop_path="")), "schemas[1].loop_path: there is no path"),
    (reads(changed(1, loop_path="line[1]")),
     "schemas[1].loop_path: holds a condition ([1]): the records are found by names alone; turn rows away with a "
     "filter after the reader"),
    (reads(changed(1, loop_path="../line")), "schemas[1].loop_path: '..' is no element name"),
    (reads(changed(1, flow=""), flows=["heads", "notes"]),
     "schemas[1].flow: names no flow, and there are 3 entries: name the flow of each"),
    (reads(changed(1, flow="heads"), flows=["heads", "notes"]), "schemas[1].flow: 'heads' has an entry already (schemas[0])"),
    (reads(changed(1, columns=[]), schema=LINES),
     "schemas[1].columns: says no columns, and there are 3 entries: a component has one schema of its own, so each "
     "entry says the columns of its flow"),
    (reads(changed(1, columns=[], mapping=[{"column": "sku", "xpath": "sku"}])),
     "schemas[1].columns: says no columns, and there are 3 entries: a component has one schema of its own, so each "
     "entry says the columns of its flow"),
    (reads(changed(1, mapping="../@id,sku")), "schemas[1].mapping: 2 paths for 3 columns (order, sku, qty)"),
    (reads(changed(1, mapping=["../@id", "sku", "qty["])), "schemas[1].mapping[2]: is no XPath (Invalid expression)"),
    (reads(changed(1, mapping=[{"column": "nope", "xpath": "sku"}])),
     "schemas[1].mapping[0].column: there is no column 'nope'; the columns are: order, sku, qty"),
    (reads(changed(1, mapping=["/shop/order/@id", "sku", "qty"])),
     "schemas[1].mapping[0]: starts at the root: a column is found from its record, by a path without the leading /"),
    (reads(changed(1, mapping=["../../../x", "sku", "qty"])),
     "schemas[1].mapping[0]: climbs 3 levels above its record, and '/shop/order/line' is 3 deep"),
    (reads(changed(1, mapping=5)), "schemas[1].mapping: expected a text of paths with commas between, or a list"),
    (reads(changed(1, mapping=["sku", {"column": "qty"}, "x"])),
     "schemas[1].mapping: expected a text of paths with commas between, or a list"),
    (reads(changed(1, mapping=[{"column": "sku", "xpth": "sku"}])), "schemas[1].mapping[0].xpth: unknown config key"),
    (reads([{"loop_path": "line", "mapping": "sku"}], outputs=["row1"]),
     "schemas[0].columns: says no columns, and the component has no schema of its own"),
    (reads(changed(1, mapping=["../head/who", "sku", "qty"]), root_loop_query="//order"),
     "schemas[1].mapping[0]: climbs above its record, and '//order/line' may be at any depth: with //, a column reads "
     "its record and the attributes of what is above it"),
    (reads(root_loop_query="/"), "root_loop_query: names no element"),
    (reads(nope=1), "nope: unknown config key"),
])
def test_what_cannot_be_read_refuses_the_job(made, said):
    assert refusals(made) == [said]


def test_flow_leaves_by_no_entry_where_several_name_none():
    entries = [{"loop_path": "line", "columns": columns("sku:str")}, {"loop_path": "head", "columns": columns("who:str")}]
    # The job is refused for the flow, which is found first; what is wrong with the entries is said once that is put right.
    assert refusals(reads(entries, flows=["row1"])) == [
        "flows[0].type: a FileInputMSXML has no output named 'row1'; its outputs are: none"]


def test_flow_that_no_entry_names_refuses_the_job():
    made = reads(flows=["heads", "lines", "notes", "more"])
    assert refusals(made) == ["flows[3].type: a FileInputMSXML has no output named 'more'; its outputs are: heads, lines, notes"]


def test_columns_an_entry_says_itself_are_its_columns_whatever_the_component_has_for_a_schema(tmp_path):
    entries = [{"loop_path": "line", "columns": columns("sku:str"), "mapping": "sku"}]
    result, written, _ = ran(tmp_path, reads(entries, schema=LINES, outputs=["row1"]))
    assert result.status == "success" and written == {"row1": ["sku", "A", "B", "C"]}


def test_what_the_converter_writes_is_taken(tmp_path):
    entries = [{"loop_path": "line", "mapping": "../@id,sku,qty", "create_empty_row": False}]
    made = reads(entries, schema=LINES, outputs=["row1"], kind="tFileInputMSXML", ignore_order=False, die_on_error=False,
                 trim_all=True, check_date=False, ignore_dtd=False, generation_mode="Dom4j", encoding="ISO-8859-15",
                 tstatcatcher_stats=False, label="x")
    result, written, _ = ran(tmp_path, made)
    assert result.status == "success" and written == {"row1": ["order;sku;qty", "1;A;2", "1;B;1", "2;C;5"]}


def test_job_is_refused_in_plain_words_where_the_library_that_reads_xml_is_not_there(monkeypatch):
    monkeypatch.setattr(xml_reader, "etree", None)
    assert refusals(reads()) == ["config: reading XML needs the lxml package (pip install 'dataprep[v2]')"]


@pytest.mark.parametrize("kind", ["file_input_msxml", "FileInputMSXML", "tFileInputMSXML"])
def test_every_name_of_it(tmp_path, kind):
    result, written, _ = ran(tmp_path, reads(kind=kind))
    assert result.status == "success" and written["lines"] == ["order;sku;qty", "1;A;2", "1;B;1", "2;C;5"]
