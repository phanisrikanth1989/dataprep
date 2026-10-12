"""Advanced XML output: rows written into a document whose shape is a tree of root, group and loop elements."""
import itertools
import random

import pytest
from lxml import etree

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, reader, writer

from .test_file_actions_kit import filled, on_v2

SCHEMA = "region:str, city:str, id:int, name:str, amount:Decimal#2"
DATA = b"north;oslo;1;ann;10.5\nnorth;oslo;2;bob;\nnorth;bergen;3;cy;7\nsouth;rome;4;;1\n"


def row(path, kind="branch", column="", value="", order=""):
    return {"path": path, "column": column, "value": value, "attribute": kind, "order": order}


# The tables as Talend's editor writes them: an element by its full path, `main` for the element a table is about.
ROOT = [row("/sales", "main"), row("made", "attri", value="by v2")]
GROUP = [row("/sales/region", "main"), row("name", "attri", column="region")]
LOOP = [row("/sales/region/sale", "main"), row("id", "attri", column="id"), row("/sales/region/sale/who", column="name"),
        row("/sales/region/sale/amount", column="amount")]


def writing(schema=SCHEMA, kind="AdvancedFileOutputXML", **config):
    made = {"filename": "out.xml", "encoding": "UTF-8", "root": ROOT, "group": GROUP, "loop": LOOP}
    made.update(config)
    return {"id": "out", "type": kind, "config": made, "inputs": ["row1"], "outputs": [],
            "schema": {"input": columns(schema), "output": []}}


def written_by(tmp_path, data=DATA, schema=SCHEMA, **config):
    made = job([reader(schema), writing(schema, **config)], [flow("row1", "in", "out")])
    folder = filled(tmp_path, {"in.csv": data})
    result = on_v2(made, folder)
    target = folder / "out.xml"
    return result, target.read_bytes() if target.exists() else None, folder


def refusals(**config):
    with pytest.raises(JobRefusedError) as refused:
        load_job(job([reader(SCHEMA), writing(**config)], [flow("row1", "in", "out")]))
    return [f"{refusal.key}: {refusal.reason}" for refusal in refused.value.report]


def shape(element):
    """An element as a nest of (name, attributes, text, children), white space between elements left out."""
    return (element.tag, dict(element.attrib), (element.text or "").strip(), [shape(child) for child in element])


# ------------------------------------------------------------------
# The tree
# ------------------------------------------------------------------

def test_rows_are_the_loop_elements_inside_the_groups_inside_the_root(tmp_path):
    result, written, _ = written_by(tmp_path)
    assert result.status == "success", result.error
    assert written.decode() == (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sales made="by v2">\n'
        '<region name="north">\n'
        '<sale id="1"><who>ann</who><amount>10.50</amount></sale>\n'
        '<sale id="2"><who>bob</who><amount></amount></sale>\n'
        '<sale id="3"><who>cy</who><amount>7.00</amount></sale>\n'
        "</region>\n"
        '<region name="south">\n'
        '<sale id="4"><who></who><amount>1.00</amount></sale>\n'
        "</region>\n"
        "</sales>\n")
    assert result.rows["out"] == 4 and result.global_map["out_FILE_NAME"] == "out.xml"


def test_group_in_a_group_and_elements_of_a_group_that_are_not_the_next_group(tmp_path):
    group = [row("/sales/region", "main"), row("name", "attri", column="region"),
             row("/sales/region/city", "main"), row("/sales/region/city/called", column="city")]
    loop = [row("/sales/region/city/sale", "main", column="name")]
    result, written, _ = written_by(tmp_path, group=group, loop=loop)
    assert result.status == "success", result.error
    assert shape(etree.fromstring(written)) == ("sales", {"made": "by v2"}, "", [
        ("region", {"name": "north"}, "", [
            ("city", {}, "", [("called", {}, "oslo", []), ("sale", {}, "ann", []), ("sale", {}, "bob", [])]),
            ("city", {}, "", [("called", {}, "bergen", []), ("sale", {}, "cy", [])])]),
        ("region", {"name": "south"}, "", [("city", {}, "", [("called", {}, "rome", []), ("sale", {}, "", [])])])])


def test_no_group_at_all_and_elements_of_the_root_before_and_after_the_rows(tmp_path):
    root = [row("/sales", "main"), row("/sales/head", order="1"), row("/sales/head/first", column="name"),
            row("/sales/body", "main", order="2"), row("/sales/foot", value="the end", order="3"),
            row("/sales/foot/last", column="id")]
    loop = [row("/sales/body/sale", "main"), row("/sales/body/sale/id", column="id")]
    result, written, _ = written_by(tmp_path, root=root, group=[], loop=loop)
    assert result.status == "success", result.error
    # What stands before the rows has the values of the first row, what stands after them those of the last.
    assert shape(etree.fromstring(written)) == ("sales", {}, "", [
        ("head", {}, "", [("first", {}, "ann", [])]),
        ("body", {}, "", [("sale", {}, "", [("id", {}, str(n), [])]) for n in range(1, 5)]),
        ("foot", {}, "the end", [("last", {}, "4", [])])])
    assert written.splitlines()[1:3] == [b"<sales><head><first>ann</first></head>", b"<body>"]
    assert written.splitlines()[-2:] == [b"</body>", b"<foot>the end<last>4</last></foot></sales>"]


def test_element_of_a_group_after_its_rows_and_group_that_holds_its_column_as_text(tmp_path):
    group = [row("/sales/region", "main", column="region"), row("/sales/region/end", column="region", order="99")]
    result, written, _ = written_by(tmp_path, group=group)
    assert result.status == "success", result.error
    assert [line.decode() for line in written.splitlines()[2:]] == [
        "<region>north",
        '<sale id="1"><who>ann</who><amount>10.50</amount></sale>',
        '<sale id="2"><who>bob</who><amount></amount></sale>',
        '<sale id="3"><who>cy</who><amount>7.00</amount></sale>',
        "<end>north</end></region>",
        "<region>south",
        '<sale id="4"><who></who><amount>1.00</amount></sale>',
        "<end>south</end></region>",
        "</sales>"]


def test_element_between_the_tables_that_no_table_is_about_is_written_with_the_one_around_it(tmp_path):
    group = [row("/sales/region", "main"), row("name", "attri", column="region"), row("/sales/region/all"),
             row("/sales/region/all/city", "main"), row("name", "attri", column="city")]
    loop = [row("/sales/region/all/city/list"), row("/sales/region/all/city/list/sale", "main", column="id")]
    result, written, _ = written_by(tmp_path, group=group, loop=loop)
    assert result.status == "success", result.error
    assert shape(etree.fromstring(written)) == ("sales", {"made": "by v2"}, "", [
        ("region", {"name": "north"}, "", [("all", {}, "", [
            ("city", {"name": "oslo"}, "", [("list", {}, "", [("sale", {}, "1", []), ("sale", {}, "2", [])])]),
            ("city", {"name": "bergen"}, "", [("list", {}, "", [("sale", {}, "3", [])])])])]),
        ("region", {"name": "south"}, "", [("all", {}, "", [
            ("city", {"name": "rome"}, "", [("list", {}, "", [("sale", {}, "4", [])])])])])])


def test_order_places_an_element_among_those_beside_it(tmp_path):
    loop = [row("/sales/region/sale", "main"), row("/sales/region/sale/b", column="name", order="2"),
            row("/sales/region/sale/a", column="id", order="1"), row("/sales/region/sale/c", value="fixed", order="3")]
    _, written, _ = written_by(tmp_path, loop=loop)
    assert written.splitlines()[3] == b"<sale><a>1</a><b>ann</b><c>fixed</c></sale>"


def test_element_with_no_order_has_its_place_in_the_tables_for_one(tmp_path):
    # `tail` is the second row of the tables, and the loop element is given the first place.
    root = [row("/sales", "main"), row("/sales/tail", value="t")]
    result, written, _ = written_by(tmp_path, root=root, group=[], loop=[row("/sales/sale", "main", column="id", order="1")])
    assert result.status == "success", result.error
    assert written.splitlines()[1:] == [b"<sales>", b"<sale>1</sale>", b"<sale>2</sale>", b"<sale>3</sale>", b"<sale>4</sale>",
                                        b"<tail>t</tail></sales>"]


def test_group_that_holds_no_column_is_one_element_around_all_the_rows(tmp_path):
    result, written, _ = written_by(tmp_path, group=[row("/sales/all", "main")], loop=[row("/sales/all/sale", "main", column="id")])
    assert result.status == "success", result.error
    assert written.splitlines()[1:] == [b'<sales made="by v2">', b"<all>", b"<sale>1</sale>", b"<sale>2</sale>", b"<sale>3</sale>",
                                        b"<sale>4</sale>", b"</all>", b"</sales>"]


def test_tables_of_bare_names_as_a_job_made_by_hand_has_them_are_read_the_same(tmp_path):
    root = [row("sales", "false"), row("made", "true", value="by v2")]
    group = [row("region", "false"), row("name", "true", column="region")]
    loop = [row("sale", False), row("id", True, column="id"), row("who", "false", column="name"),
            row("amount", "false", column="amount")]
    result, written, _ = written_by(tmp_path / "bare", root=root, group=group, loop=loop)
    assert result.status == "success", result.error
    _, by_path, _ = written_by(tmp_path / "paths")
    assert written == by_path


def test_fixed_value_stands_where_no_column_is_named_and_the_column_is_written_where_both_are(tmp_path):
    loop = [row("/sales/region/sale", "main"), row("kind", "attri", value="a sale"), row("paid", "attri", column="amount", value="0"),
            row("/sales/region/sale/who", column="name"), row("/sales/region/sale/amount", column="amount", value="0"),
            row("/sales/region/sale/unit", value="NOK")]
    _, written, _ = written_by(tmp_path, loop=loop)
    assert written.splitlines()[3] == (b'<sale kind="a sale" paid="10.50"><who>ann</who><amount>10.50</amount>'
                                       b"<unit>NOK</unit></sale>")
    # A column that holds nothing writes nothing: the fixed value is for where no column is named.
    assert written.splitlines()[4] == b'<sale kind="a sale"><who>bob</who><amount></amount><unit>NOK</unit></sale>'


def test_namespaces_are_declared_on_the_element_they_are_given_for(tmp_path):
    root = [row("/s:sales", "main"), row("s", "ns", value="urn:sales"), row("", "ns", value="urn:default")]
    group = [row("/s:sales/region", "main"), row("name", "attri", column="region")]
    loop = [row("/s:sales/region/s:sale", "main", column="name")]
    result, written, _ = written_by(tmp_path, root=root, group=group, loop=loop)
    assert result.status == "success", result.error
    assert written.splitlines()[1] == b'<s:sales xmlns:s="urn:sales" xmlns="urn:default">'
    parsed = etree.fromstring(written)
    assert parsed.tag == "{urn:sales}sales" and parsed[0].tag == "{urn:default}region" and parsed[0][0].tag == "{urn:sales}sale"


def test_prefix_xml_needs_no_namespace_and_namespace_with_no_value_declares_nothing(tmp_path):
    root = [row("/sales", "main"), row("unused", "ns"), row("xml:lang", "attri", value="en")]
    result, written, _ = written_by(tmp_path, root=root)
    assert result.status == "success", result.error
    assert written.splitlines()[1] == b'<sales xml:lang="en">'


def test_element_stands_in_the_last_one_written_with_the_path_it_names(tmp_path):
    loop = [row("/sales/region/sale", "main"), row("/sales/region/sale/part"), row("/sales/region/sale/part/a", column="id"),
            row("/sales/region/sale/part"), row("/sales/region/sale/part/b", column="name"),
            row("/sales/region/sale/note", value="n"), row("/sales/region/sale/part/c", value="late")]
    _, written, _ = written_by(tmp_path, loop=loop)
    assert written.splitlines()[3] == (b"<sale><part><a>1</a></part><part><b>ann</b><c>late</c></part>"
                                       b"<note>n</note></sale>")


def test_root_may_be_a_bare_name_and_order_may_be_a_number_or_nothing(tmp_path):
    root = [row("sales", "main", value=None, order=None)]
    loop = [row("/sales/sale", "main"), row("/sales/sale/b", column="name", order=2), row("/sales/sale/a", column="id", order=1),
            row("/sales/sale/n", value=5, order=3)]
    result, written, _ = written_by(tmp_path, root=root, group=[], loop=loop)
    assert result.status == "success", result.error
    assert written.splitlines()[1:3] == [b"<sales>", b"<sale><a>1</a><b>ann</b><n>5</n></sale>"]


def test_fixed_texts_of_the_job_are_read_back_as_they_were(tmp_path):
    hard = 'a < b & "c" > d'
    root = [row("/sales", "main"), row("s", "ns", value="urn:a&b"), row("made", "attri", value=hard),
            row("/sales/head", value=hard, order="1")]
    result, written, _ = written_by(tmp_path, root=root, file_valid=True, dtd_valid=False, xsl_valid=True, xsl_type='t"x',
                                    xsl_href="a&b.xsl")
    assert result.status == "success", result.error
    assert written.splitlines()[1] == b'<?xml-stylesheet type="t&quot;x" href="a&amp;b.xsl"?>'
    assert written.splitlines()[2] == (b'<sales xmlns:s="urn:a&amp;b" made="a &lt; b &amp; &quot;c&quot; &gt; d">'
                                       b'<head>a &lt; b &amp; "c" &gt; d</head>')
    parsed = etree.fromstring(written)
    assert (parsed.nsmap["s"], parsed.get("made"), parsed[0].text) == ("urn:a&b", hard, hard)
    _, written, _ = written_by(tmp_path / "dtd", file_valid=True, dtd_name="sales", dtd_systemid='a"b.dtd')
    assert written.splitlines()[1] == b'<!DOCTYPE sales SYSTEM "a&quot;b.dtd">'


def test_fixed_text_xml_cannot_hold_fails_the_job_when_the_file_is_read_back(tmp_path):
    loop = [row("/sales/region/sale", "main"), row("/sales/region/sale/note", value="a\x01b")]
    filled(tmp_path, {"out.xml": b"of an earlier run"})
    result, written, _ = written_by(tmp_path, loop=loop)
    assert (result.status, result.failed_component, written) == ("failed", "out", b"of an earlier run")
    assert result.error.startswith("what was written to 'out.xml' is not well-formed XML: ")


# ------------------------------------------------------------------
# What is written for nothing
# ------------------------------------------------------------------

def test_element_with_nothing_to_say_and_attribute_with_no_value_are_written_or_left_out_as_the_job_says(tmp_path):
    loop = [row("/sales/region/sale", "main"), row("id", "attri", column="id"), row("paid", "attri", column="amount"),
            row("unmapped", "attri"), row("/sales/region/sale/who", column="name"),
            row("/sales/region/sale/amount", column="amount"), row("/sales/region/sale/note"),
            row("/sales/region/sale/box"), row("/sales/region/sale/box/in", column="amount"),
            row("/sales/region/sale/tag"), row("at", "attri", column="amount"),
            row("/sales/region/sale/mark"), row("is", "attri", value="set"),
            row("/sales/region/sale/both", column="amount", value="0"),
            row("/sales/region/sale/space"), row("n", "ns", value="urn:n"),
            row("/sales/region/sale/pair", column="amount"), row("of", "attri", column="name")]
    _, written, _ = written_by(tmp_path / "as given", loop=loop)
    assert written.splitlines()[4] == (b'<sale id="2"><who>bob</who><amount></amount><note></note><box><in></in></box>'
                                       b'<tag></tag><mark is="set"></mark><both></both><space xmlns:n="urn:n"></space>'
                                       b'<pair of="bob"></pair></sale>')
    _, written, _ = written_by(tmp_path / "none", loop=loop, create_empty_element=False)
    # Left out: the element whose column holds nothing, the one that names nothing, and the one with only such in it.
    # Written: the one with something fixed in it, and the one where any column in it holds a value.
    assert written.splitlines()[4] == (b'<sale id="2"><who>bob</who><mark is="set"></mark><space xmlns:n="urn:n"></space>'
                                       b'<pair of="bob"></pair></sale>')
    # An empty text is a value, and is written.
    assert written.splitlines()[-3] == (b'<sale id="4" paid="1.00"><who></who><amount>1.00</amount><box><in>1.00</in></box>'
                                        b'<tag at="1.00"></tag><mark is="set"></mark><both>1.00</both>'
                                        b'<space xmlns:n="urn:n"></space><pair of="">1.00</pair></sale>')
    _, written, _ = written_by(tmp_path / "all", loop=loop, add_empty_attribute=True, add_unmapped_attribute=True)
    assert written.splitlines()[4] == (b'<sale id="2" paid="" unmapped=""><who>bob</who><amount></amount><note></note>'
                                       b'<box><in></in></box><tag at=""></tag><mark is="set"></mark><both></both>'
                                       b'<space xmlns:n="urn:n"></space><pair of="bob"></pair></sale>')
    # An attribute written empty is nothing to say: the element it stands on is still left out.
    _, written, _ = written_by(tmp_path / "both", loop=loop, create_empty_element=False, add_empty_attribute=True,
                               add_unmapped_attribute=True)
    assert written.splitlines()[4] == (b'<sale id="2" paid="" unmapped=""><who>bob</who><mark is="set"></mark>'
                                       b'<space xmlns:n="urn:n"></space><pair of="bob"></pair></sale>')


def test_elements_on_the_way_to_the_loop_and_the_loop_element_are_written_with_nothing_to_say(tmp_path):
    group = [row("/sales/region", "main"), row("/sales/region/of", column="amount")]
    loop = [row("/sales/region/sale", "main"), row("/sales/region/sale/amount", column="amount")]
    result, written, _ = written_by(tmp_path, b"north;oslo;1;ann;\nnorth;oslo;2;bob;\n", root=[row("/sales", "main")],
                                    group=group, loop=loop, create_empty_element=False)
    assert result.status == "success", result.error
    assert written.splitlines()[1:] == [b"<sales>", b"<region>", b"<sale></sale>", b"<sale></sale>", b"</region>", b"</sales>"]


def test_no_row_gives_the_root_alone_or_no_file(tmp_path):
    result, written, _ = written_by(tmp_path / "empty", b"")
    assert result.status == "success", result.error
    assert written == b'<?xml version="1.0" encoding="UTF-8"?>\n<sales made="by v2">\n</sales>\n'
    root = [row("/sales", "main"), row("/sales/head", value="h", order="1"), row("/sales/head/first", column="name"),
            row("/sales/body", "main", order="2"), row("/sales/foot", value="the end", order="3")]
    group = [row("/sales/body/region", "main"), row("name", "attri", column="region")]
    result, written, _ = written_by(tmp_path / "more", b"", root=root, group=group, loop=[row("/sales/body/region/sale", "main")])
    assert result.status == "success", result.error
    assert written.splitlines()[1:] == [b"<sales><head>h<first></first></head>", b"<body>", b"</body>",
                                        b"<foot>the end</foot></sales>"]
    result, written, _ = written_by(tmp_path / "less", b"", root=root + [row("/sales/tail", column="name", order="4")],
                                    group=group, loop=[row("/sales/body/region/sale", "main")], create_empty_element=False,
                                    file_valid=True, dtd_name="sales", dtd_systemid="s.dtd")
    assert written.splitlines()[1:] == [b'<!DOCTYPE sales SYSTEM "s.dtd">', b"<sales><head>h</head>", b"<body>", b"</body>",
                                        b"<foot>the end</foot></sales>"]
    filled(tmp_path / "none", {"out.xml": b"of an earlier run"})
    result, written, _ = written_by(tmp_path / "none", b"", delete_empty_file=True)
    assert result.status == "success" and written is None


# ------------------------------------------------------------------
# Values, groups at size, and the lines after the declaration
# ------------------------------------------------------------------

def test_whatever_a_value_holds_is_read_back_as_it_was_in_elements_attributes_and_groups(tmp_path):
    hard = 'a < b & "c" > d\ttab'
    data = f'1;"{hard.replace(chr(34), chr(34) * 2)}"\n'.encode()
    made = job([reader("id:int, name:str", csv_option=True, text_enclosure='"', escape_char='"'),
                writing("id:int, name:str", root=[row("/r", "main")], group=[row("/r/g", "main"), row("is", "attri", column="name")],
                        loop=[row("/r/g/l", "main"), row("as", "attri", column="name"), row("/r/g/l/e", column="name")],
                        encoding="US-ASCII")], [flow("row1", "in", "out")])
    folder = filled(tmp_path, {"in.csv": data})
    assert on_v2(made, folder).status == "success"
    parsed = etree.fromstring((folder / "out.xml").read_bytes())
    assert (parsed[0].get("is"), parsed[0][0].get("as"), parsed[0][0][0].text) == (hard, hard, hard)


def test_character_xml_cannot_hold_fails_the_job(tmp_path):
    result, written, _ = written_by(tmp_path, b"north;oslo;1;a\x01b;1\n")
    assert (result.status, written) == ("failed", None)
    assert result.error == "column 'name' of row 1 holds a character XML cannot hold: 'a\\x01b'"


def test_groups_hold_together_over_many_rows(tmp_path):
    drawn = random.Random(5)
    rows = []
    for outer in range(3000):
        for inner in range(drawn.randint(1, 4)):
            rows += [(f"r{outer % 9}", f"c{inner}", len(rows) + n) for n in range(drawn.randint(1, 20))]
    data = "".join(f"{region};{city};{n};x;1\n" for region, city, n in rows).encode()
    group = [row("/sales/region", "main"), row("name", "attri", column="region"),
             row("/sales/region/city", "main"), row("name", "attri", column="city")]
    result, written, _ = written_by(tmp_path, data, group=group, loop=[row("/sales/region/city/sale", "main", column="id")])
    assert result.status == "success", result.error
    found = [(region.get("name"), [(city.get("name"), [int(sale.text) for sale in city]) for city in region])
             for region in etree.fromstring(written)]
    wanted = [(region, [(city, [n for _, _, n in inner]) for city, inner in itertools.groupby(outer, key=lambda r: r[1])])
              for region, outer in ((region, list(outer)) for region, outer in itertools.groupby(rows, key=lambda r: r[0]))]
    assert len(rows) > 50_000 and found == wanted


def test_missing_value_is_a_group_of_its_own_also_where_the_rows_start_with_it(tmp_path):
    data = b";a\n;b\n1;c\n;d\n2;e\n2;f\n"
    result, written, _ = written_by(
        tmp_path, data, "n:int, name:str", root=[row("/r", "main")], group=[row("/r/g", "main"), row("is", "attri", column="n")],
        loop=[row("/r/g/l", "main", column="name")], add_empty_attribute=True)
    assert result.status == "success", result.error
    found = [(group.get("is"), [one.text for one in group]) for group in etree.fromstring(written)]
    assert found == [("", ["a", "b"]), ("1", ["c"]), ("", ["d"]), ("2", ["e", "f"])]


def test_groups_are_told_apart_by_the_text_that_is_written(tmp_path):
    data = b"north ;oslo;1;a;1\nnorth;oslo;2;b;1\n north;oslo;3;c;1\n"
    _, written, _ = written_by(tmp_path / "trimmed", data, trim=True)
    assert [len(region) for region in etree.fromstring(written)] == [3]
    _, written, _ = written_by(tmp_path / "as it is", data)
    assert [len(region) for region in etree.fromstring(written)] == [1, 1, 1]


def test_date_and_number_are_written_as_the_schema_says(tmp_path):
    result, written, _ = written_by(
        tmp_path, b"2024-01-31;1.5;7\n", "d:datetime@%Y-%m-%d, f:float, n:Decimal#2", root=[row("/r", "main")], group=[],
        loop=[row("/r/l", "main"), row("on", "attri", column="d"), row("/r/l/f", column="f"), row("/r/l/n", column="n")])
    assert result.status == "success", result.error
    assert written.splitlines()[2] == b'<l on="2024-01-31"><f>1.5</f><n>7.00</n></l>'


def test_line_that_names_a_dtd_or_a_stylesheet_follows_the_declaration(tmp_path):
    _, written, _ = written_by(tmp_path / "dtd", file_valid=True, dtd_valid=True, dtd_name="sales", dtd_systemid="sales.dtd")
    assert written.splitlines()[:3] == [b'<?xml version="1.0" encoding="UTF-8"?>', b'<!DOCTYPE sales SYSTEM "sales.dtd">',
                                        b'<sales made="by v2">']
    _, written, _ = written_by(tmp_path / "xsl", file_valid=True, dtd_valid=False, xsl_valid=True, xsl_type="text/xsl",
                               xsl_href="look.xsl")
    assert written.splitlines()[1] == b'<?xml-stylesheet type="text/xsl" href="look.xsl"?>'
    # A DTD is named where both are asked for, and neither where the line is not asked for: what it would say is not looked at.
    _, written, _ = written_by(tmp_path / "both", file_valid=True, dtd_valid=True, xsl_valid=True, dtd_name="sales",
                               dtd_systemid="sales.dtd")
    assert written.splitlines()[1:3] == [b'<!DOCTYPE sales SYSTEM "sales.dtd">', b'<sales made="by v2">']
    for at, asked in enumerate([{"dtd_valid": True, "dtd_name": "no name"}, {"dtd_valid": False, "xsl_valid": True}]):
        result, written, _ = written_by(tmp_path / f"off {at}", file_valid=False, **asked)
        assert result.status == "success" and written.splitlines()[1] == b'<sales made="by v2">'
    # And no line where neither is asked for.
    _, written, _ = written_by(tmp_path / "neither", file_valid=True, dtd_valid=False, xsl_valid=False)
    assert written.splitlines()[1] == b'<sales made="by v2">'


def test_values_are_trimmed_where_asked(tmp_path):
    _, written, _ = written_by(tmp_path, b"north;oslo;1;  ann  ;1\n", trim=True)
    assert b"<who>ann</who>" in written
    _, written, _ = written_by(tmp_path / "not", b"north;oslo;1;  ann  ;1\n")
    assert b"<who>  ann  </who>" in written


def test_character_the_encoding_lacks_is_written_by_its_number(tmp_path):
    result, written, _ = written_by(tmp_path, ("north;oslo;1;5 " + chr(0x20AC) + ";1\n").encode("utf-8"), encoding="ISO-8859-1")
    assert result.status == "success", result.error
    assert b'<?xml version="1.0" encoding="ISO-8859-1"?>' in written and b"<who>5 &#8364;</who>" in written
    assert etree.fromstring(written).findtext(".//who") == "5 " + chr(0x20AC)


def test_engine_is_told_whether_a_file_is_left_when_no_row_arrives(tmp_path):
    # A later output of the same subjob, to which a file that is there is an error, finds one or none.
    def run(folder, **config):
        made = job([reader(SCHEMA, outputs=("row1", "row2")), writing(SCHEMA, **config),
                    writer(SCHEMA, component_id="out2", path="out.xml", inputs=("row2",), file_exist_exception=True)],
                   [flow("row1", "in", "out"), flow("row2", "in", "out2")])
        return on_v2(made, filled(folder, {"in.csv": b""}))

    result = run(tmp_path / "left")
    assert result.status == "failed" and "File already exists" in result.error
    assert run(tmp_path / "none", delete_empty_file=True).status == "success"


def test_folder_is_made_unless_it_is_not_to_be_and_a_job_that_fails_leaves_the_file_that_was_there(tmp_path):
    result, _, folder = written_by(tmp_path / "made", filename="deep/er/out.xml")
    assert result.status == "success" and (folder / "deep/er/out.xml").exists()
    result, _, folder = written_by(tmp_path / "not", filename="deep/out.xml", create=False)
    assert (result.status, result.error) == ("failed", "Failed to write file 'deep/out.xml': folder 'deep' does not exist")
    filled(tmp_path / "kept", {"out.xml": b"of an earlier run"})
    result, written, _ = written_by(tmp_path / "kept", b"north;oslo;1;b\x01b;1\n")
    assert result.status == "failed" and written == b"of an earlier run"


def test_columns_are_those_that_arrive_where_none_is_declared(tmp_path):
    made = job([reader(SCHEMA), writing()], [flow("row1", "in", "out")])
    made["components"][1]["schema"] = {"input": [], "output": []}
    folder = filled(tmp_path / "there", {"in.csv": DATA})
    result = on_v2(made, folder)
    assert result.status == "success", result.error
    assert (folder / "out.xml").read_bytes().splitlines()[3] == b'<sale id="1"><who>ann</who><amount>10.50</amount></sale>'
    made["components"][1]["config"]["loop"] = [row("/sales/region/sale", "main", column="nope")]
    result = on_v2(made, filled(tmp_path / "not there", {"in.csv": DATA}))
    assert (result.status, result.failed_component) == ("failed", "out")
    assert result.error == "loop[0].column: there is no column 'nope'; the columns are: region, city, id, name, amount"


# ------------------------------------------------------------------
# What is refused, a converted job, and the names it goes by
# ------------------------------------------------------------------

@pytest.mark.parametrize("config, said", [
    ({"loop": []}, "loop: names no element: the loop element is the one written for each row"),
    ({"root": []}, "root: names no element: a document has one root element"),
    ({"loop": [row("/sales/region/sale", "main", column="nope")]},
     "loop[0].column: there is no column 'nope'; the columns are: region, city, id, name, amount"),
    ({"loop": [row("/sales/region/a sale", "main")]}, "loop[0].path: 'a sale' is no name an element may have"),
    ({"loop": [row("/sales/region/sale", "main"), row("my id", "attri", column="id")]},
     "loop[1].path: 'my id' is no name an attribute may have"),
    ({"loop": [row("/sales/elsewhere/sale", "main")]},
     "loop[0].path: '/sales/elsewhere/sale' stands in '/sales/elsewhere', and no element before it has that path"),
    ({"root": [row("made", "attri", value="x"), row("/sales", "main")]},
     "root[0].path: the attribute 'made' stands before any element it could belong to"),
    ({"loop": [row("/sales/region/p:sale", "main")]},
     "loop[0].path: the prefix of 'p:sale' is declared on no element at or above it: declare it with a row whose "
     "`attribute` is `ns`"),
    ({"root": [row("/sales", "main"), row("/other", "branch")]},
     "root[1].path: '/other' is a second root, and a document has one"),
    ({"group": [row("/sales/region", "main"), row("/sales/other", "main")]},
     "group[1].path: the group '/sales/other' does not stand above the loop element '/sales/region/sale'"),
    ({"root": [row("/sales", "main"), row("s", "ns", column="name")]},
     "root[1].column: a namespace is what its `value` says, the same for every row: it cannot come from a column"),
    ({"root": [row("/sales", "main"), row("a b", "ns", value="urn:x")]},
     "root[1].path: 'a b' is no prefix a namespace may have"),
    ({"root": [row("/sales", "main"), row("xmlns", "ns", value="urn:x")]},
     "root[1].path: 'xmlns' is no prefix a namespace may have"),
    ({"loop": [row("/sales/region/sale", "main", order="first")]},
     "loop[0].order: 'first' is no place among elements: give a whole number"),
    ({"loop": [row("/sales/region/sale", "main"), row("/sales/region/sale/a:b:c", column="id")]},
     "loop[1].path: 'a:b:c' is no name an element may have"),
    ({"loop": [row("/sales/region/sale", "main"), row("p:id", "attri", column="id")]},
     "loop[1].path: the prefix of 'p:id' is declared on no element at or above it: declare it with a row whose "
     "`attribute` is `ns`"),
    ({"group": [row("region", "ns", value="urn:x")], "root": []},
     "root: names no element: a document has one root element"),
    ({"loop": [row("/sales/region/sale", "main"), row("/sales/region/other", "main")]},
     "loop[1].path: '/sales/region/other' is a second loop element, and the rows are written as one"),
    ({"loop": [row("/sales/region/sale", "main"), row("id", "attri", column="id"), row("id", "attri", value="x")]},
     "loop[0].path: the attribute 'id' is given twice for 'sale'"),
    ({"root": [row("/sales", "main"), row("s", "ns", value="urn:a"), row("s", "ns", value="urn:b")]},
     "root[0].path: the namespace 's' is given twice for 'sales'"),
    ({"filename": ""}, "path: the file to write has no name"),
    ({"merge": True}, "merge: v2 writes a file whole and beside its place; it does not add to a document that is there"),
    ({"output_as_xsd": True}, "output_as_xsd: v2 writes no XSD"),
    ({"usestream": True}, "usestream: v2 writes files, not streams a job holds"),
    ({"add_document_as_node": True},
     "add_document_as_node: a column that holds a document is written as text; v2 does not put it in as elements"),
    ({"split": True}, "split: v2 writes one file: split the rows before the output"),
    ({"advanced_separator": True},
     "advanced_separator: v2 writes a number one way: write it as text of the form wanted before the output"),
    ({"file_valid": True, "dtd_valid": True, "dtd_name": "a b"}, "dtd_name: 'a b' is no name an element may have"),
    ({"nope": 1}, "nope: unknown config key"),
])
def test_what_cannot_be_written_refuses_the_job(config, said):
    assert refusals(**config) == [said]


def test_every_table_that_names_no_element_is_said():
    assert refusals(root=[], loop=[]) == ["root: names no element: a document has one root element",
                                          "loop: names no element: the loop element is the one written for each row"]


def test_what_the_converter_writes_is_taken(tmp_path):
    result, written, _ = written_by(
        tmp_path, kind="tAdvancedFileOutputXML", usestream=False, streamname="outputStream", map="", merge=False,
        pretty_compact=False, file_valid=False, dtd_valid=True, dtd_name="Root", dtd_systemid="Talend.dtd", xsl_valid=False,
        xsl_type="text/xsl", xsl_href="Talend.xsl", split=False, split_every="1000", trim=False, create=True,
        create_empty_element=True, add_empty_attribute=False, add_unmapped_attribute=False, add_document_as_node=False,
        output_as_xsd=False, advanced_separator=False, thousands_separator=",", decimal_separator=".",
        generation_mode="Dom4j", delete_empty_file=False, tstatcatcher_stats=False, label="x")
    assert result.status == "success" and len(etree.fromstring(written).xpath("//sale")) == 4


@pytest.mark.parametrize("kind", ["advanced_file_output_xml", "AdvancedFileOutputXML", "tAdvancedFileOutputXML"])
def test_every_name_of_it(tmp_path, kind):
    result, written, _ = written_by(tmp_path, kind=kind)
    assert result.status == "success" and len(etree.fromstring(written).xpath("//sale")) == 4
