"""XML map: a document a column holds taken apart into rows, or the columns of a row handed on under other names."""
import copy
import json
import logging
import os
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError

from .kit import columns, flow, job, reader, writer

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tXMLMap_0.1.json"
IN = "id:int, doc:str, note:str"
OUT = "row:int, order:int, sku:str, qty:int, price:Decimal#2, note:str"
DATA = (b'id|doc|note\n'
        b'1|<order id="7"><line price="1.5"><sku>A</sku><qty>2</qty></line><line price="2"><sku>B</sku><qty>1</qty></line></order>|n1\n'
        b'2|<order id="8"><line price="3"><sku>C</sku><qty>5</qty></line></order>|n2\n')


def node(name, path="", *children, kind="ELEMENT", loop=False, expression="", type_name="str"):
    """A node of a tree, as the converter writes one."""
    return {"name": name, "expression": expression, "type": type_name, "xpath": path, "nodeType": kind, "loop": loop,
            "main": False, "outgoingConnections": "", "children": list(children)}


def document(loop=True):
    """The tree of the document in `doc`: an order with an id, and lines with a price, a sku and a quantity."""
    return node("doc", "row1/doc", node(
        "order", "row1.doc:/order",
        node("id", "row1.doc:/order/@id", kind="ATTRIBUT"),
        node("line", "row1.doc:/order/line",
             node("price", "row1.doc:/order/line/@price", kind="ATTRIBUT"),
             node("sku", "row1.doc:/order/line/sku"), node("qty", "row1.doc:/order/line/qty"), loop=loop)))


def tree(name="row1", *nodes, lookup=False):
    return {"name": name, "matchingMode": "UNIQUE_MATCH" if lookup else "ALL_ROWS", "lookupMode": "LOAD_ONCE", "lookup": lookup,
            "activateGlobalMap": False, "nodes": list(nodes)}


MAIN = tree("row1", node("id", "row1/id", type_name="int"), document(), node("note", "row1/note"))
TAKEN = {"row": "row1.id", "order": "[row1.doc:/order/@id]", "sku": "[row1.doc:/order/line/sku]",
         "qty": "[row1.doc:/order/line/qty]", "price": "[row1.doc:/order/line/@price]", "note": "row1.note"}


def out_tree(taken=TAKEN, name="row2", **more):
    made = {"name": name, "expressionFilter": "", "activateExpressionFilter": False, "allInOne": False,
            "nodes": [node(column, f"{name}/{column}", expression=expression) for column, expression in taken.items()]}
    made.update(more)
    return made


def mapping(taken=TAKEN, out=OUT, schema=IN, inputs=None, outputs=None, kind="XMLMap", data_schema=None, **config):
    """file (fields separated by |) -> the map -> out.csv."""
    made = {"input_trees": [MAIN] if inputs is None else inputs,
            "output_trees": [out_tree(taken)] if outputs is None else outputs, "die_on_error": True}
    made.update(config)
    step = {"id": "it", "type": kind, "config": made, "schema": {"input": columns(schema), "output": columns(out) if out else []},
            "inputs": ["row1"], "outputs": ["row2"]}
    return job([reader(data_schema or schema, header_rows=1, fieldseparator="|"), step, writer(out or None)],
               [flow("row1", "in", "it"), flow("row2", "it", "out")])


def ran(tmp_path, made=None, data=DATA):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(mapping() if made is None else made)
    finally:
        os.chdir(previous)
    written = tmp_path / "out.csv"
    return result, written.read_text().splitlines()[1:] if written.exists() else None


def rows(tmp_path, made=None, data=DATA):
    result, written = ran(tmp_path, made, data)
    assert result.status == "success", result.error
    return written


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [f"{refusal.key}: {refusal.reason}" for refusal in refused.value.report]


# ------------------------------------------------------------------
# A document taken apart
# ------------------------------------------------------------------

def test_every_loop_element_of_a_rows_document_is_a_row_with_the_rows_own_columns_beside_it(tmp_path):
    assert rows(tmp_path) == ["1;7;A;2;1.50;n1", "1;7;B;1;2.00;n1", "2;8;C;5;3.00;n2"]


def test_place_outside_the_loop_element_is_read_from_where_the_loop_element_stands(tmp_path):
    data = (b'id|doc|note\n1|<order id="7"><head><who>ann</who></head><line><sku>A</sku></line><line><sku>B</sku></line>'
            b'<foot>f</foot></order>|n\n')
    taken = {"who": "[row1.doc:/order/head/who]", "sku": "[row1.doc:/order/line/sku]", "foot": "[row1.doc:/order/foot]",
             "line": "[row1.doc:/order/line]", "order": "[row1.doc:/order/@id]"}
    assert rows(tmp_path, mapping(taken, out="who:str, sku:str, foot:str, line:str, order:int"), data) == [
        "ann;A;f;A;7", "ann;B;f;B;7"]


def test_document_whose_tree_marks_no_loop_element_gives_one_row(tmp_path):
    made = mapping({"order": "[row1.doc:/order/@id]", "sku": "[row1.doc:/order/line/sku]"}, out="order:int, sku:str",
                   inputs=[tree("row1", node("id", "row1/id", type_name="int"), document(loop=False))])
    # The first line of each: a place that holds several is its first.
    assert rows(tmp_path, made) == ["7;A", "8;C"]


def test_value_that_is_not_there_is_missing_and_a_column_with_no_expression_too(tmp_path):
    data = b"id|doc|note\n1|<order><line><sku/></line><line/></order>|\n"
    taken = {"order": "[row1.doc:/order/@id]", "sku": "[row1.doc:/order/line/sku]", "qty": "[row1.doc:/order/line/qty]", "more": ""}
    assert rows(tmp_path, mapping(taken, out="order:int, sku:str, qty:int, more:str"), data) == [";;;", ";;;"]


def test_names_are_matched_by_their_local_name(tmp_path):
    data = (b'id|doc|note\n1|<o:order xmlns:o="urn:o" id="7"><o:line><o:sku>A</o:sku></o:line><o:line><o:sku>B</o:sku></o:line>'
            b'</o:order>|n\n')
    # The tree draws the names without a prefix; a place may be written with one on any of its steps.
    taken = {"order": "[row1.doc:/o:order/@id]", "sku": "[row1.doc:/o:order/x:line/o:sku]", "same": "[row1.doc:/order/line/sku]"}
    assert rows(tmp_path, mapping(taken, out="order:int, sku:str, same:str"), data) == ["7;A;A", "7;B;B"]


def test_document_itself_may_be_handed_on_beside_what_is_read_from_it(tmp_path):
    data = b'id|doc|note\n1|<order id="7"><line><sku>A</sku></line></order>|n\n'
    taken = {"sku": "[row1.doc:/order/line/sku]", "whole": "row1.doc"}
    assert rows(tmp_path, mapping(taken, out="sku:str, whole:str"), data) == ['A;<order id="7"><line><sku>A</sku></line></order>']


def test_with_namespaces_given_a_place_is_read_as_xpath_says(tmp_path):
    data = b'id|doc|note\n1|<o:order xmlns:o="urn:o" xmlns:p="urn:p" p:id="7"><o:line><sku>A</sku></o:line></o:order>|n\n'
    spaced = node("doc", "row1/doc", node("o:order", "row1.doc:/o:order", node("o:line", "row1.doc:/o:order/o:line", loop=True)))
    taken = {"order": "[row1.doc:/o:order/@p:id]", "sku": "[row1.doc:/o:order/o:line/sku]", "none": "[row1.doc:/o:order/o:line/o:sku]"}
    made = mapping(taken, out="order:int, sku:str, none:str", inputs=[tree("row1", node("id"), spaced, node("note"))],
                   namespaces={"o": "urn:o", "p": "urn:p"})
    assert rows(tmp_path, made, data) == ["7;A;"]


def test_missing_value_in_a_column_that_may_not_be_missing_fails_the_job_and_names_the_row(tmp_path):
    # The engine's own check of what a component hands on: it names the row by what is carried with it.
    data = b"id|doc|note\n1|<order><line><sku>A</sku></line></order>|n\n2|<order><line/></order>|n\n"
    result, _ = ran(tmp_path / "document", mapping({"sku": "[row1.doc:/order/line/sku]"}, out="sku:str!"), data)
    assert result.error == "Column 'sku' has NULL values but is not nullable; the row is line 3 of in.csv"
    result, _ = ran(tmp_path / "flat", mapping({"text": "row1.note"}, out="text:str!", inputs=[FLAT], schema="id:int, doc:str, note:int"),
                    b"id|doc|note\n1|x|5\n2|y|\n")
    assert result.error == "Column 'text' has NULL values but is not nullable; the row is line 3 of in.csv"


def test_rows_that_lack_a_column_the_tree_draws_fail_the_job_in_plain_words(tmp_path):
    said = "the rows that arrive have no column '{}', which the tree of the input draws; their columns are: id, text"

    def arriving(made):
        made["components"][0]["schema"]["output"] = columns("id:int, text:str")
        made["components"][1]["schema"]["input"] = columns("id:int, text:str")
        return made

    # Where a document is taken apart, the rows are looked at when they are there.
    for at, (made, lacking) in enumerate([(mapping(), "note"), (mapping({"row": "row1.id", "sku": "[row1.doc:/order/line/sku]"},
                                                                         out="row:int, sku:str"), "doc")]):
        result, _ = ran(tmp_path / str(at), arriving(made), b"id|text\n1|x\n")
        assert (result.status, result.failed_component, result.error) == ("failed", "it", said.format(lacking))
    # Where rows are only handed on, it is seen before anything runs.
    assert refusals(arriving(mapping({"n": "row1.note"}, out="n:str", inputs=[FLAT]))) == ["config: " + said.format("note")]


def test_columns_are_those_of_the_output_tree_with_its_types_where_none_is_declared(tmp_path):
    data = b'id|doc|note\n1|<order id=" 7 " ok="TRUE"><line><sku>A</sku></line></order>|n\n'
    made = mapping({"order": "[row1.doc:/order/@id]", "ok": "[row1.doc:/order/@ok]", "sku": "[row1.doc:/order/line/sku]"}, out=None)
    nodes = made["components"][1]["config"]["output_trees"][0]["nodes"]
    nodes[0]["type"], nodes[1]["type"] = "int", "bool"
    # Read as the tree says: a whole number, and true or false (which an output that declares no columns writes so).
    assert rows(tmp_path / "tree", made, data) == ["7;True;A"]
    # `output_schema` says the columns where it is given: the same values, read as it says them.
    made["components"][1]["config"]["output_schema"] = columns("order:str, ok:str, sku:str")
    assert rows(tmp_path / "said", made, data) == [" 7 ;TRUE;A"]


# ------------------------------------------------------------------
# What is wrong in the data
# ------------------------------------------------------------------

def test_document_that_is_not_well_formed_fails_the_job_and_names_the_row_or_is_dropped_with_a_warning(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    data = DATA + b"3|<order>|n3\n4||n4\n"
    result, written = ran(tmp_path / "dies", data=data)
    assert (result.status, result.failed_component, written) == ("failed", "it", None)
    assert result.error.startswith("the document is not well-formed XML: ") and result.error.endswith("; the row is line 4 of in.csv")
    result, written = ran(tmp_path / "goes on", mapping(die_on_error=False), data)
    assert result.status == "success", result.error
    assert written == ["1;7;A;2;1.50;n1", "1;7;B;1;2.00;n1", "2;8;C;5;3.00;n2"]
    said = [record.getMessage() for record in caplog.records if record.levelname == "WARNING"]
    assert len(said) == 1 and said[0].startswith("[it] 2 rows were dropped; the first: the document is not well-formed XML: ")


def test_value_that_is_none_of_its_columns_type_fails_the_job_or_drops_its_row(tmp_path):
    data = DATA.replace(b"<qty>1</qty>", b"<qty>one</qty>")
    result, written = ran(tmp_path / "dies", data=data)
    assert (result.status, written) == ("failed", None)
    assert result.error == "Column 'qty': could not convert string to float: 'one'; the row is line 2 of in.csv"
    assert rows(tmp_path / "goes on", mapping(die_on_error=False), data) == ["1;7;A;2;1.50;n1", "2;8;C;5;3.00;n2"]


def test_rows_that_are_dropped_are_not_written_down_for_a_reject_output_the_map_has_not(tmp_path, monkeypatch):
    from src.v2.components.transform import extract_xml_field

    def never(self, *given):
        raise AssertionError("the rows that are turned away were made ready, and nobody takes them")

    monkeypatch.setattr(extract_xml_field.Extraction, "_turned_away", never)
    data = DATA.replace(b"<qty>1</qty>", b"<qty>one</qty>")
    assert rows(tmp_path, mapping(die_on_error=False), data) == ["1;7;A;2;1.50;n1", "2;8;C;5;3.00;n2"]


def test_row_with_no_document_gives_no_row(tmp_path):
    made = mapping({"row": "row1.id", "sku": "[row1.doc:/order/line/sku]"}, out="row:int, sku:str", schema="id:int, doc:int, note:str")
    assert rows(tmp_path, made, b"id|doc|note\n1||n\n") == []


# ------------------------------------------------------------------
# Rows handed on, with no document
# ------------------------------------------------------------------

FLAT = tree("row1", node("id", "row1/id", type_name="int"), node("doc", "row1/doc"), node("note", "row1/note"))


def test_columns_of_a_row_are_handed_on_under_the_names_of_the_output(tmp_path):
    made = mapping({"number": "row1.id", "text": "row1.note", "again": "row1.id", "nothing": ""},
                   out="number:int, text:str, again:int, nothing:str", inputs=[FLAT])
    assert rows(tmp_path, made) == ["1;n1;1;", "2;n2;2;"]


def test_rows_with_no_document_are_not_held_in_memory():
    from src.v2.engine.context import RunContext
    from src.v2.components.transform.xml_map import XMLMap

    spec = load_job(mapping({"number": "row1.id"}, out="number:int", inputs=[FLAT])).components["it"]
    assert XMLMap(spec, spec.config, RunContext("t", {})).needs_rows() is False
    spec = load_job(mapping()).components["it"]
    assert XMLMap(spec, spec.config, RunContext("t", {})).needs_rows() is True


# ------------------------------------------------------------------
# What is refused, a converted job, and the names it goes by
# ------------------------------------------------------------------

LOOKUP = tree("row9", node("code", "row9/code", expression="row1.id"), lookup=True)


def taking(**changed):
    return dict(TAKEN, **changed)


@pytest.mark.parametrize("made, said", [
    (mapping(inputs=[]), "input_trees: names no input: the tree of the rows that arrive"),
    (mapping(inputs=[MAIN, LOOKUP]),
     "input_trees[1]: 'row9' is a lookup. A lookup has to say whether a row with no match is kept, and a converted job "
     "does not say it: join with a map before this step"),
    (mapping(outputs=[]), "output_trees: names no output: the tree of the rows that are handed on"),
    (mapping(outputs=[out_tree(), out_tree(name="row3")]),
     "output_trees[1]: a second output ('row3'). v2 takes a document apart into one flow: what more is wanted of it is "
     "a step after this one"),
    (mapping(outputs=[out_tree(activateExpressionFilter=True, expressionFilter="row1.id > 1")]),
     "output_trees[0].expressionFilter: a filter is not read here: filter the rows with a step after this one"),
    (mapping(outputs=[dict(out_tree(), nodes=[node("built", "row2/built", node("root", "row2.built:/root"))])]),
     "output_trees[0].nodes[0]: 'built' is a document to build. v2 builds documents with the XML outputs, not here"),
    (mapping(taking(sku='[row1.doc:/order/line/sku] + "x"')),
     "output_trees[0].nodes[2].expression: '[row1.doc:/order/line/sku] + \"x\"' is more than a place in the document "
     "or a column of the row: work it out with a map after this step"),
    (mapping(taking(sku="Var.total")),
     "output_trees[0].nodes[2].expression: 'Var.total' is a variable of the map, and a converted job does not say what "
     "it holds: work it out with a map after this step"),
    (mapping(taking(sku="row1.nope")),
     "output_trees[0].nodes[2].expression: there is no column 'nope' in 'row1'; its columns are: id, doc, note"),
    (mapping(taking(sku="row7.id")),
     "output_trees[0].nodes[2].expression: 'row7' is not the input of this map, which is 'row1'"),
    (mapping(taking(sku="[row1.note:/order/line/sku]")),
     "output_trees[0].nodes[2].expression: 'note' holds no document in the tree of 'row1'; the document is in 'doc'"),
    (mapping(taking(sku="[row1.doc:order/line/sku]")),
     "output_trees[0].nodes[2].expression: 'order/line/sku' does not start at the root of the document: a place is "
     "written from the root, as /order/line/sku"),
    (mapping(taking(sku="[row1.doc:/order/line/sku[]")),
     "output_trees[0].nodes[2].expression: is no XPath (Invalid expression)"),
    (mapping(taking(nope="row1.id")),
     "output_trees[0].nodes[6].name: there is no column 'nope'; the columns are: row, order, sku, qty, price, note"),
    (mapping(taking(sku="[row1.doc:/order/line/q:sku]"), namespaces={"o": "urn:o"}),
     "output_trees[0].nodes[2].expression: is no XPath (Undefined namespace prefix)"),
    (mapping(nope=1), "nope: unknown config key"),
])
def test_what_cannot_be_mapped_refuses_the_job(made, said):
    assert refusals(made) == [said]


def test_document_with_more_than_one_loop_element_or_with_no_root_element_refuses_the_job():
    twice = node("doc", "row1/doc", node("order", "", node("line", "", node("part", "", loop=True), loop=True)))
    assert refusals(mapping({"sku": "[row1.doc:/order/line/sku]"}, out="sku:str", inputs=[tree("row1", twice)])) == [
        "input_trees[0].nodes[0]: the document 'doc' has 2 loop elements (/order/line, /order/line/part). v2 takes a "
        "document apart by one"]
    rootless = node("doc", "row1/doc", node("version", "", kind="ATTRIBUT"))
    assert refusals(mapping({"row": "row1.id"}, out="row:int", inputs=[tree("row1", node("id"), rootless)])) == [
        "input_trees[0].nodes[1]: the document 'doc' has no root element in its tree"]


def test_more_flows_than_the_trees_draw_and_a_filter_said_beside_the_trees_refuse_the_job():
    made = mapping()
    made["components"].append(reader("id:int", component_id="more", path="more.csv", outputs=("row9",)))
    made["flows"].append(flow("row9", "more", "it"))
    made["components"][1]["inputs"].append("row9")
    assert refusals(made) == ["inputs: 2 flows arrive, and the trees draw one: a map takes its rows from one flow"]
    assert refusals(mapping(activate_expression_filter=True, expression_filter="row1.id > 1")) == [
        "activate_expression_filter: a filter is not read here: filter the rows with a step after this one"]


def test_two_documents_in_the_tree_of_the_input_refuse_the_job():
    second = node("doc2", "row1/doc2", node("root", "row1.doc2:/root", loop=True))
    made = mapping(inputs=[tree("row1", node("id", "row1/id"), document(), second, node("note", "row1/note"))],
                   schema="id:int, doc:str, doc2:str, note:str")
    assert refusals(made) == [
        "input_trees[0].nodes[2]: 'doc2' is a second document ('doc' is the first). v2 takes one document apart in a "
        "step: take the other apart in a step of its own"]


def test_converted_sample_job_is_refused_for_its_lookup_and_says_what_to_do():
    assert refusals(json.loads(SAMPLE.read_text())) == [
        "input_trees[1]: 'row2' is a lookup. A lookup has to say whether a row with no match is kept, and a converted "
        "job does not say it: join with a map before this step"]


def test_what_the_converter_writes_is_taken(tmp_path):
    made = mapping(kind="tXMLMap", keep_order_for_document=False, connections=[{"source": "a", "target": "b", "sourceExpression": ""}],
                   var_tables=[{"name": "Var", "minimized": True}], output_schema=columns(OUT),
                   expressions={"sku": "./ancestor::sku"}, looping_element="line", expression_filter="",
                   activate_expression_filter=False, tstatcatcher_stats=False, label="x")
    assert rows(tmp_path, made) == ["1;7;A;2;1.50;n1", "1;7;B;1;2.00;n1", "2;8;C;5;3.00;n2"]


@pytest.mark.parametrize("kind", ["xml_map", "XMLMap", "tXMLMap"])
def test_every_name_of_it(tmp_path, kind):
    assert rows(tmp_path, mapping(kind=kind)) == ["1;7;A;2;1.50;n1", "1;7;B;1;2.00;n1", "2;8;C;5;3.00;n2"]


def test_tree_is_not_changed_by_being_read():
    made = mapping()
    before = copy.deepcopy(made)
    load_job(made)
    assert made == before
