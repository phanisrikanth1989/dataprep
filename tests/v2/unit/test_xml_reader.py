"""The reader of XML: a parser that reads nothing but the document, records by a path, columns by XPath from them."""
import io
import os

import pytest
from lxml import etree

from src.v2 import xml_reader
from src.v2.xml_reader import Fault, Records, column_path, record_path


def rows(document, loop, paths, **settings):
    """Every record's values, read as a file is read; a path is written `name=xpath`, with `<` before a name for a node."""
    columns = []
    for written in paths:
        name, _, path = written.partition("=")
        columns.append(column_path(name.lstrip("<"), path, name.startswith("<"), settings.get("namespaces")))
    data = document if isinstance(document, bytes) else document.encode("utf-8")
    walk = Records(io.BytesIO(data), record_path(loop, settings.get("namespaces")), columns, **settings)
    return [values for _, values in walk], walk


ORDERS = """<orders region="north">
  <order id="1"><line><sku>A</sku><qty>2</qty></line><line><sku>B</sku><qty/></line><status>OPEN</status></order>
  <order id="2"><line><sku>C</sku></line><status>SHUT</status></order>
</orders>"""


# ------------------------------------------------------------------
# Records and what a path gives
# ------------------------------------------------------------------

def test_record_for_each_element_the_path_finds_in_the_order_of_the_document():
    found, _ = rows(ORDERS, "/orders/order/line", ["sku=sku", "qty=qty"])
    assert found == [["A", "2"], ["B", ""], ["C", None]]


def test_what_a_path_gives():
    document = """<r xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><rec code="7">
      <one>1</one><empty/><blank>  </blank><nil xsi:nil="true"/><deep>a<b>b</b>c<!-- no --><?no no?></deep>
      <many>first</many><many>second</many><cd><![CDATA[<kept> & as it is]]></cd></rec></r>"""
    paths = ["one=one", "none=nothing", "empty=empty", "blank=blank", "nil=nil", "deep=deep", "many=many", "attr=@code",
             "text=one/text()", "self=.", "count=count(many)", "is=one = '1'", "said=concat(one, '-', @code)", "cd=cd"]
    found, walk = rows(document, "/r/rec", paths)
    assert dict(zip([path.partition("=")[0] for path in paths], found[0])) == {
        "one": "1", "none": None, "empty": "", "blank": "  ", "nil": None, "deep": "abc", "many": "first", "attr": "7",
        "text": "1", "self": found[0][9], "count": "2", "is": "true", "said": "1-7", "cd": "<kept> & as it is"}
    assert "first" in found[0][9] and "second" in found[0][9]
    # Said once the reading is done: for which columns a path found more than one node, in how many records, and the first.
    assert walk.many == {"many": (1, 1)}


def test_node_itself_as_xml_text_when_asked_for():
    found, _ = rows(ORDERS, "/orders/order", ["<first=line", "id=@id"])
    assert found == [["<line><sku>A</sku><qty>2</qty></line>", "1"], ["<line><sku>C</sku></line>", "2"]]


def test_any_name_in_the_path_and_a_name_anywhere():
    document = "<r><a><x>1</x></a><b><x>2</x><deep><x>3</x></deep></b><x>4</x></r>"
    assert rows(document, "/r/*/x", ["v=."])[0] == [["1"], ["2"]]
    assert rows(document, "//x", ["v=."])[0] == [["1"], ["2"], ["3"], ["4"]]
    assert rows(document, "/r/x", ["v=."])[0] == [["4"]]
    assert rows(document, "/r", ["v=count(.//x)"])[0] == [["4"]]
    assert rows(document, "/other/x", ["v=."])[0] == []


def test_any_name_may_be_the_record_itself():
    assert rows("<r><a>1</a><b>2</b></r>", "/r/*", ["v=.", "name=name()"])[0] == [["1", "a"], ["2", "b"]]


def test_number_that_is_none_is_written_as_xpath_writes_it():
    found, _ = rows("<r><v>x</v></r>", "/r/v", ["nan=number(.)", "up=1 div 0", "down=-1 div 0", "half=1 div 2", "big=1000000 * 1000000"])
    assert found == [["NaN", "Infinity", "-Infinity", "0.5", "1000000000000"]]


def test_element_marked_as_missing_is_missing_also_with_something_in_it():
    document = '<r xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><v xsi:nil="true"><old>1</old></v><v xsi:nil="false">2</v></r>'
    assert rows(document, "/r", ["first=v[1]", "second=v[2]"])[0] == [[None, "2"]]


def test_path_from_the_root_is_not_found_deeper_down():
    document = "<r><r><x>deep</x></r><x>top</x></r>"
    assert rows(document, "/r/x", ["v=."])[0] == [["top"]]
    assert rows(document, "//r/x", ["v=."])[0] == [["deep"], ["top"]]


def test_what_was_read_is_let_go_of_once_for_each_element_the_rows_wait_for(monkeypatch):
    freed = []
    really = xml_reader._free
    monkeypatch.setattr(xml_reader, "_free", lambda element: freed.append(element.tag) or really(element))
    rows(ORDERS, "/orders/order/line", ["sku=sku"])
    assert freed == ["line", "line", "line"]
    freed.clear()
    rows(ORDERS, "/orders/order/line", ["sku=sku", "status=../status"])
    assert freed == ["order", "order"]


def test_record_inside_a_record_is_a_record_and_the_outer_one_still_holds_it():
    document = "<r><item n='1'><item n='2'><item n='3'/></item></item><item n='4'/></r>"
    found, _ = rows(document, "//item", ["n=@n", "inside=count(.//item)"])
    assert sorted(found) == [["1", "2"], ["2", "1"], ["3", "0"], ["4", "0"]]


def test_limit_stops_the_reading_and_nothing_at_all_is_read_for_none():
    assert rows(ORDERS, "/orders/order/line", ["sku=sku"], limit=2)[0] == [["A"], ["B"]]
    assert rows(ORDERS, "/orders/order/line", ["sku=sku"], limit=0)[0] == []


def test_record_says_the_line_it_starts_on():
    walk = Records(io.BytesIO(ORDERS.encode()), record_path("/orders/order", None), [column_path("id", "@id", False, None)])
    assert [(line, values) for line, values in walk] == [(2, ["1"]), (3, ["2"])]


# ------------------------------------------------------------------
# Columns that look above the record
# ------------------------------------------------------------------

class InPieces:
    """A document that is handed to the parser a piece at a time, however much it asks for."""

    def __init__(self, data, piece):
        self._held, self._piece = io.BytesIO(data), piece

    def read(self, size=-1):
        return self._held.read(self._piece if size is None or size < 0 else min(size, self._piece))

    def seek(self, *where):
        return self._held.seek(*where)


@pytest.mark.parametrize("piece", [16, 64, 4096, 1 << 20])
def test_column_that_climbs_sees_the_whole_of_what_it_climbs_to_whatever_the_parser_has_read(piece):
    # `status` is written after the lines of its order: a reader that makes a row when the line ends may or may not
    # have it, by how far the parser happens to have read.
    orders = "".join(f"<order id='{n}'>" + "".join(f"<line><sku>{n}-{m}</sku></line>" for m in range(3)) +
                     f"<status>S{n}</status></order>" for n in range(200))
    source = InPieces(f"<orders region='north'>{orders}<tail>T</tail></orders>".encode(), piece)
    columns = [column_path("sku", "sku", False, None), column_path("status", "../status", False, None),
               column_path("order", "../@id", False, None), column_path("region", "../../@region", False, None)]
    found = [values for _, values in Records(source, record_path("/orders/order/line", None), columns)]
    assert found == [[f"{n}-{m}", f"S{n}", str(n), "north"] for n in range(200) for m in range(3)]


def test_how_far_a_column_climbs():
    def climb(path):
        return column_path("c", path, False, None).climb
    assert [climb(path) for path in ("sku", "@id", ".", "a/b/@c", "../status", "../../x/y", "../../../z")] == [0, 0, 0, 0, 1, 2, 3]
    # The start tag of an element is whole before anything in it is read: its attributes need no waiting for.
    assert [climb(path) for path in ("../@id", "../../@region", "concat(../@id, '-', sku)")] == [0, 0, 0]
    # A path may climb wherever one starts inside it; the highest climb counts. Dots in a text are no climb.
    assert [climb(path) for path in ("concat(../../a, '-', b)", "../a | ../../../b", "concat(sku, '../..')", "..", "../..")] == [
        2, 3, 0, 1, 2]
    # A climb inside a condition starts from the step it stands on, not from the record. It is counted as if
    # from the record all the same: more than is needed is held, never less.
    assert climb("sku[. = ../code]") == 1


def test_value_found_above_a_record_is_the_one_of_its_own_element_above(tmp_path):
    document = ("<r><g n='1'><name>one</name><i>a</i><i>b</i></g><g n='2'><i>c</i><name>two</name></g>"
                "<g n='3'><i>d</i></g></r>")
    paths = ["i=.", "name=../name", "n=../@n", "both=concat(../name, '/', .)", "count=count(../i)"]
    assert rows(document, "/r/g/i", paths)[0] == [
        ["a", "one", "1", "one/a", "2"], ["b", "one", "1", "one/b", "2"], ["c", "two", "2", "two/c", "1"],
        ["d", None, "3", "/d", "1"]]


def test_column_that_climbs_above_a_record_that_may_be_anywhere_is_refused():
    with pytest.raises(Fault, match="the column 'c' climbs above its record, and '//line' may be at any depth"):
        list(Records(io.BytesIO(ORDERS.encode()), record_path("//line", None), [column_path("c", "../status", False, None)]))
    assert rows(ORDERS, "//line", ["order=../@id", "sku=sku"])[0] == [["1", "A"], ["1", "B"], ["2", "C"]]


def test_column_that_climbs_above_the_document_is_refused():
    with pytest.raises(Fault, match="climbs 3 levels above its record, and '/orders/order' is 2 deep"):
        list(Records(io.BytesIO(ORDERS.encode()), record_path("/orders/order", None),
                     [column_path("c", "../../../x", False, None)]))


def test_freeing_takes_away_what_stands_before_at_every_level_and_keeps_what_comes_after():
    root = etree.fromstring("<r a='1'><g a='2'><x/><x/><here>t<in/></here><x/></g><g/></r>")
    here = root[0][2]
    other = etree.fromstring("<r><before/><g><x/><here/></g></r>")
    xml_reader._free(here)
    assert etree.tostring(root).decode() == '<r a="1"><g a="2"><here/><x/></g><g/></r>'
    xml_reader._free(other[1][1])
    assert etree.tostring(other).decode() == "<r><g><here/></g></r>"


# ------------------------------------------------------------------
# Paths that are refused
# ------------------------------------------------------------------

@pytest.mark.parametrize("written, said", [
    ("", "there is no path"),
    ("orders/order", "starts at the root: write it as /orders/order"),
    ("/orders/order[@id='1']", "holds a condition ([@id='1'])"),
    ("/orders//order", "holds // in its middle"),
    ("/orders/order/text()", "'text()' is no element name"),
    ("/orders/@id", "'@id' is no element name"),
    ("/", "names no element"),
    ("//", "names no element"),
    ("/p:orders/order", "the prefix 'p' is bound to no namespace"),
])
def test_record_path_that_is_no_plain_path_is_refused(written, said):
    with pytest.raises(ValueError) as refused:
        record_path(written, {"q": "urn:q"})
    assert said in str(refused.value)


@pytest.mark.parametrize("written, said", [
    ("/orders/status", "starts at the root"),
    ("//status", "starts at the root"),
    ("a/../b", "climbs (..) after going down"),
    ("../x/../../y", "climbs (..) after going down"),
    ("ancestor::order/@id", "the axis 'ancestor'"),
    ("preceding-sibling::line/sku", "the axis 'preceding-sibling'"),
    ("following::x", "the axis 'following'"),
    ("parent::order/status", "the axis 'parent'"),
    ("sku[", "is no XPath"),
    ("nosuch()", "is no XPath"),
])
def test_column_path_whose_answer_would_depend_on_what_is_in_memory_is_refused(written, said):
    with pytest.raises(ValueError) as refused:
        column_path("c", written, False, None)
    assert said in str(refused.value)


def test_column_with_no_path_is_the_child_of_its_own_name():
    assert rows(ORDERS, "/orders/order/line", ["sku="])[0] == [["A"], ["B"], ["C"]]


# ------------------------------------------------------------------
# Namespaces
# ------------------------------------------------------------------

SPACED = """<o:orders xmlns:o="urn:orders" xmlns="urn:default" xmlns:x="urn:extra">
  <o:order x:id="1"><sku>A</sku><x:sku>other A</x:sku></o:order>
</o:orders>"""


def test_names_are_matched_by_their_local_name_whatever_the_namespace_and_whatever_prefix_the_path_has():
    assert rows(SPACED, "/orders/order", ["sku=sku", "id=@id"])[0] == [["A", "1"]]
    assert rows(SPACED, "/any:orders/thing:order", ["sku=p:sku"])[0] == [["A"]]


def test_with_the_namespaces_given_a_path_is_read_as_xpath_says():
    given = {"o": "urn:orders", "d": "urn:default", "e": "urn:extra"}
    found, _ = rows(SPACED, "/o:orders/o:order", ["plain=sku", "default=d:sku", "extra=e:sku", "id=@e:id"], namespaces=given)
    assert found == [[None, "A", "other A", "1"]]
    assert rows(SPACED, "/orders/order", ["sku=d:sku"], namespaces=given)[0] == []


def test_node_as_xml_text_carries_no_namespace_unless_the_namespaces_are_given():
    assert rows(SPACED, "/orders/order", ["<node=sku"])[0] == [["<sku>A</sku>"]]
    declared_on_it = '<r><rec xmlns:x="urn:x" x:a="1"><x:v>1</x:v></rec></r>'
    assert rows(declared_on_it, "/r/rec", ["<node=."])[0] == [['<rec a="1"><v>1</v></rec>']]
    given = {"o": "urn:orders", "d": "urn:default"}
    found, _ = rows(SPACED, "/o:orders/o:order", ["<node=d:sku"], namespaces=given)
    assert etree.fromstring(found[0][0]).tag == "{urn:default}sku"


# ------------------------------------------------------------------
# What a document may not do
# ------------------------------------------------------------------

def asking(tmp_path):
    """Three documents that each try to have another file read, in the three ways there are."""
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET")
    outside = tmp_path / "outside.dtd"
    outside.write_text(f'<!ENTITY leaked SYSTEM "file://{secret}"><!ENTITY inner "FROM-OUTSIDE">')
    return [
        f'<!DOCTYPE r [<!ENTITY x SYSTEM "file://{secret}">]><r><v>&x;</v></r>',
        f'<!DOCTYPE r [<!ENTITY % ext SYSTEM "file://{outside}"> %ext;]><r><v>&inner;</v></r>',
        f'<!DOCTYPE r SYSTEM "file://{outside}"><r><v>&inner;</v></r>',
    ]


def test_document_cannot_make_the_reader_read_another_file(tmp_path, monkeypatch):
    asked = []

    class Notes(etree.Resolver):
        def resolve(self, url, public_id, context):
            asked.append(url)

    monkeypatch.setattr(xml_reader, "_refusing", Notes)
    for document in asking(tmp_path):
        with pytest.raises(Fault) as refused:
            rows(document, "/r/v", ["v=."])
        assert "the document uses the entity" in str(refused.value) and "SECRET" not in str(refused.value)
    # Not only was nothing read: nothing was asked for.
    assert asked == []


def test_were_the_parser_set_to_read_other_files_whatever_asks_for_one_is_still_refused(tmp_path, monkeypatch):
    # The settings as lxml has them when none is given, which read a file a parameter entity names.
    monkeypatch.setattr(xml_reader, "settings", lambda large_values=False: {})
    read = []
    for document in asking(tmp_path):
        try:
            read += rows(document, "/r/v", ["v=."])[0]
        except (Fault, etree.XMLSyntaxError):
            pass
    assert not [values for values in read if values[0] and ("SECRET" in values[0] or "OUTSIDE" in values[0])]


def test_whatever_asks_for_another_file_is_refused_by_name():
    with pytest.raises(Fault) as refused:
        xml_reader._refusing().resolve("file:///etc/passwd", None, None)
    assert str(refused.value) == ("the document asks for another file (file:///etc/passwd): v2 reads the document and "
                                  "nothing else")


def test_entity_the_document_declares_itself_fails_the_reading_by_its_name():
    document = '<!DOCTYPE r [<!ENTITY co "ACME">]><r><v>&co; ltd</v></r>'
    with pytest.raises(Fault) as refused:
        rows(document, "/r/v", ["v=."])
    assert str(refused.value) == ("the document uses the entity '&co;' (near line 1): v2 reads no entity a document "
                                  "declares, since one may name another file")


def test_the_five_entities_of_xml_and_a_character_by_its_number_are_read():
    assert rows("<r><v>&lt;a&gt; &amp; &quot;b&quot; &apos;c&apos; &#233;&#x20AC;</v></r>", "/r/v", ["v=."])[0] == [
        ["<a> & \"b\" 'c' " + chr(233) + chr(0x20AC)]]


def test_document_that_blows_itself_up_is_stopped_by_the_parser():
    laughs = ['<!ENTITY l0 "ha">'] + [f'<!ENTITY l{n} "{("&l%d;" % (n - 1)) * 10}">' for n in range(1, 10)]
    with pytest.raises((Fault, etree.XMLSyntaxError)):
        rows(f"<!DOCTYPE r [{''.join(laughs)}]><r><v>&l9;</v></r>", "/r/v", ["v=."])


def test_document_that_is_not_well_formed_fails_with_the_place():
    with pytest.raises(etree.XMLSyntaxError) as broken:
        rows("<r><v>1</v><v>2</r>", "/r/v", ["v=."])
    assert broken.value.lineno == 1


def test_value_larger_than_the_parser_allows_fails_unless_large_values_are_asked_for():
    big = "<r><v>" + "x" * (11 * 1024 * 1024) + "</v></r>"
    with pytest.raises(etree.XMLSyntaxError):
        rows(big, "/r/v", ["v=string-length(.)"])
    assert rows(big, "/r/v", ["v=string-length(.)"], large_values=True)[0] == [[str(11 * 1024 * 1024)]]


# ------------------------------------------------------------------
# The encoding
# ------------------------------------------------------------------

TEXT = "caf" + chr(233) + " " + chr(0x20AC)


@pytest.mark.parametrize("data", [
    f'<?xml version="1.0" encoding="UTF-8"?><r><v>{TEXT}</v></r>'.encode("utf-8"),
    f'<?xml version="1.0" encoding="ISO-8859-15"?><r><v>{TEXT}</v></r>'.encode("iso-8859-15"),
    b"\xef\xbb\xbf" + f"<r><v>{TEXT}</v></r>".encode("utf-8"),
    f'<?xml version="1.0" encoding="UTF-16"?><r><v>{TEXT}</v></r>'.encode("utf-16"),
    f'<?xml version="1.0" encoding="UTF-16LE"?><r><v>{TEXT}</v></r>'.encode("utf-16-le"),
], ids=["declared UTF-8", "declared ISO-8859-15", "a byte order mark", "UTF-16", "UTF-16 without a mark"])
def test_what_the_document_says_of_its_encoding_decides_whatever_the_job_says(data):
    for of_the_job in ("ISO-8859-1", "UTF-8", "windows-1252"):
        assert rows(data, "/r/v", ["v=."], encoding=of_the_job)[0] == [[TEXT]]


def test_encoding_of_the_job_is_used_for_a_document_that_says_none():
    data = f"<r><v>{TEXT}</v></r>".encode("iso-8859-15")
    assert rows(data, "/r/v", ["v=."], encoding="ISO-8859-15")[0] == [[TEXT]]
    with pytest.raises(etree.XMLSyntaxError):
        rows(data, "/r/v", ["v=."], encoding="UTF-8")


# ------------------------------------------------------------------
# What the review of the XML group found (ticket 120)
# ------------------------------------------------------------------

GROUPS = ("<r><g><rate>2</rate><code>K1</code><i><qty>3</qty><code>L1</code></i><i><qty>5</qty></i></g>"
          "<g><i><qty>7</qty><code>L3</code></i><rate>10</rate><code>K2</code></g></r>")


def whole(document, loop, paths):
    """The same values asked of the document held whole: what a path means."""
    root = etree.fromstring(document.encode())
    found = []
    for record in root.xpath(loop):
        found.append([xml_reader.value(xml_reader.path(written.partition("=")[2])(record), False, False)[0]
                      for written in paths])
    return found


@pytest.mark.parametrize("path", [
    "../rate * qty", "../code = code", "../rate - qty", "../zzz | code", "../rate + ../rate", "../rate div qty",
    "../rate > qty", "../code[. = 'K1']", "../rate", "../rate/text()", "../*", "concat(../code, '-', code)",
])
def test_a_climb_that_is_one_part_of_an_expression_is_worked_out_from_the_record(path):
    """It was worked out wholly from the element above: `../rate * qty` as `rate * qty` up there, which is NaN."""
    found = rows(GROUPS, "/r/g/i", [f"v={path}"])[0]
    assert found == whole(GROUPS, "/r/g/i", [f"v={path}"])


def test_what_a_climb_and_an_operator_come_to():
    assert rows(GROUPS, "/r/g/i", ["times=../rate * qty", "same=../code = code", "either=../zzz | code"])[0] == [
        ["6", "false", "L1"], ["10", "false", None], ["70", "false", "L3"]]


def test_a_plain_path_down_from_above_is_still_found_once_for_all_the_records_under_one_element():
    def up(path):
        return column_path("c", path, False, None).up
    assert [up(path) for path in ("../rate", "../../a/b", "../@n", "../a/@b", "../*", "../a/text()", "../p:a/b")] == [
        1, 2, 1, 1, 1, 1, 1]
    assert [up(path) for path in ("../rate * qty", "../a | b", "../a = b", "../a[1]", "../a[b]/c", "concat(../a, b)",
                                  "../a + ../b", "..", "../a div 2", "../a and b")] == [0] * 10


@pytest.mark.parametrize("written, at", [
    ("string(/orders/header/date)", "/orders/header/date"),
    ("count(//line)", "//line"),
    ("(//status)[1]", "//status"),
    ("sku | /orders/x", "/orders/x"),
    ("concat(sku, '-', /orders/@region)", "/orders/@region"),
    ("qty + //rate", "//rate"),
    ("qty * /orders/rate", "/orders/rate"),
    ("qty div /orders/rate", "/orders/rate"),
    ("sku and //x", "//x"),
    ("sku or //x", "//x"),
    ("qty mod /orders/n", "/orders/n"),
    ("sku[. = /orders/first]", "/orders/first"),
    ("sku = /orders/first", "/orders/first"),
    ("- /orders/n", "/orders/n"),
    ("count( / )", "/"),
])
def test_a_path_from_the_root_anywhere_in_a_column_is_refused(written, at):
    """Inside a function it was let through, and read a tree that was being let go of."""
    with pytest.raises(ValueError) as refused:
        column_path("c", written, False, None)
    assert str(refused.value) == (
        f"holds a path that starts at the root ({at}): a column is found from its record, and what a path from the "
        "root would find depends on how much of the document is in memory")


@pytest.mark.parametrize("written", [
    "a/b", "a//b", ".//x", "*/b", "div/p", "mod/x", "and/or", "or//x", "a | b/c", "count(.//line)", "../a//b",
    "concat('/x', a, \"//y\")", "concat('namespace::', a)", "a[b/c]", "@*", "text()", "a/text()", "sku[../code]/x", "a div b", "a*b",
    "q:a/q:b", "a [ b ]/c", "(a)/b", "(a | b)//c", "a[1]/b", "string(a)/b" if False else "string(a/b)",
])
def test_a_path_that_stays_with_its_record_is_taken(written):
    column_path("c", written, False, {"q": "urn:q"})


def test_a_record_that_is_the_root_has_nothing_above_it():
    """A column that climbs from it finds nothing, as in XPath. It failed with words nobody could use."""
    document = "<node id='1'><node id='2'><node id='3'/></node></node>"
    assert rows(document, "//node", ["id=@id", "up=../@id"])[0] == [["3", "2"], ["2", "1"], ["1", None]]
    assert rows("<a id='7'><b/></a>", "//a", ["up=../@id", "more=../../@id"])[0] == [[None, None]]


@pytest.mark.parametrize("written", ["namespace::*", "sku/namespace::p", "count(namespace::*)"])
def test_the_namespace_axis_is_refused_wherever_a_path_is_read(written):
    said = "uses the axis 'namespace', which hands back namespaces and no value"
    with pytest.raises(ValueError) as refused:
        column_path("c", written, False, None)
    assert said in str(refused.value)
    with pytest.raises(ValueError) as refused:
        xml_reader.path(written)
    assert said in str(refused.value)


@pytest.mark.parametrize("path, written", [
    ("a * 1000000000000000", "3000000000000000"),
    ("a * 1000000000000000000000", "3000000000000000000000"),
    ("(a - 2) * 100000000000000000000000", "100000000000000000000000"),
    # The digits are the fewest that say the number the machine holds: three times that one is a little less.
    ("a * 100000000000000000000000", "299999999999999970000000"),
    ("a div 10000000", "0.0000003"),
    ("a div 7", "0.42857142857142855"),
    ("a * 0.5", "1.5"),
    ("a - 3", "0"),
    ("0 - a", "-3"),
    ("(0 - a) * 1000000000000000", "-3000000000000000"),
    ("a div 0", "Infinity"),
    ("(0 - a) div 0", "-Infinity"),
    ("number('x')", "NaN"),
    ("a * 0 * -1", "0"),
])
def test_a_number_is_written_as_xpath_writes_one(path, written):
    """With no exponent, and a whole one with no point, however large."""
    assert rows("<r><x><a>3</a></x></r>", "/r/x", [f"v={path}"])[0] == [[written]]


def test_nil_may_be_said_with_a_one():
    document = """<r xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><x>
      <a xsi:nil="1"/><b xsi:nil="true">kept out</b><c xsi:nil="0">c</c><d xsi:nil="false"/><e xsi:nil="1"><in/></e>
      <f xsi:nil=" true "/></x></r>"""
    assert rows(document, "/r/x", ["a=a", "b=b", "c=c", "d=d", "e=e", "f=f"])[0] == [[None, None, "c", "", None, None]]


# ------------------------------------------------------------------
# What is no record that is read is let go of as well
# ------------------------------------------------------------------

def test_what_has_ended_is_let_go_of_down_to_the_first_element_a_record_is_read_from():
    # The open elements are the last ones, level by level: r, g, here.
    root = etree.fromstring("<r a='1'><skip><a/><b/></skip><g><x/>t<y/><here><in/><open/></here></g></r>")
    xml_reader._sweep(root, [(("r", "g", "here"), False)], False)
    assert etree.tostring(root).decode() == '<r a="1"><g><here><in/><open/></here></g></r>'


def test_nothing_in_an_element_some_record_waits_for_is_let_go_of():
    document = "<r><old/><g><i>1</i><i>2</i><late/></g></r>"
    for steps, anywhere in ((("r", "g"), False), (("g",), True), (("r", "*"), False)):
        root = etree.fromstring(document)
        xml_reader._sweep(root, [(("r", "x", "y"), False), (steps, anywhere)], False)
        assert etree.tostring(root).decode() == "<r><g><i>1</i><i>2</i><late/></g></r>"


def test_letting_go_reads_names_as_the_reader_does_and_stops_at_what_is_no_element():
    spaced = etree.fromstring("<r xmlns:p='urn:p'><a/><p:g><x/><y/></p:g></r>")
    xml_reader._sweep(spaced, [(("r", "g"), False)], False)
    assert len(spaced) == 1 and len(spaced[0]) == 2
    xml_reader._sweep(spaced, [(("r", "{urn:p}g"), False)], True)
    assert len(spaced[0]) == 2
    xml_reader._sweep(spaced, [(("r", "g"), False)], True)
    assert len(spaced[0]) == 1
    remark = etree.fromstring("<r><a/><b/><!-- the last thing so far --></r>")
    xml_reader._sweep(remark, [(("r", "x"), False)], False)
    assert etree.tostring(remark).decode() == "<r><!-- the last thing so far --></r>"
    alone = etree.fromstring("<r/>")
    xml_reader._sweep(alone, [(("r", "x"), False)], False)
    assert etree.tostring(alone).decode() == "<r/>"


HELD = r'''
import io, resource, sys
from src.v2.xml_reader import Records, Several, column_path, record_path

def most():
    held = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return held / (1 << 20) if sys.platform == "darwin" else held / 1024

class Made:
    """A document made as it is read, so that none of it is held but by the reader."""
    def __init__(self, parts):
        self._parts, self._left = iter(parts), b""
    def read(self, size=-1):
        while len(self._left) < size:
            piece = next(self._parts, None)
            if piece is None:
                break
            self._left += piece
        handed, self._left = self._left[:size], self._left[size:]
        return handed
    def seek(self, where):
        assert where == 0

def bulk(megabytes):
    piece = b"".join(b"<note><n>%d</n><t>some words that are no record</t></note>" % n for n in range(1000))
    for _ in range(megabytes * (1 << 20) // len(piece)):
        yield piece

RECORDS = [b"<line><sku>A</sku></line><line><sku>B</sku></line><line><sku>C</sku></line>"]
SHAPES = {
    "after": lambda: [b"<orders>", *RECORDS, b"<summary>", *bulk(24), b"</summary></orders>"],
    "before": lambda: [b"<orders><summary>", *bulk(24), b"</summary>", *RECORDS, b"</orders>"],
    "beside": lambda: [b"<orders>", *RECORDS, *bulk(24), *RECORDS, b"</orders>"],
    "no record": lambda: [b"<nothing><summary>", *bulk(24), b"</summary></nothing>"],
}
class Whole(Made):
    """The head of the document is read once to see how it is written, and then from its start again."""
    def __init__(self, shape):
        self._shape = shape
        super().__init__(shape())
    def seek(self, where):
        super().__init__(self._shape())

before = most()
walk = Records(Whole(SHAPES[sys.argv[1]]), record_path("/orders/line", None), [column_path("sku", "sku", False, None)])
found = [values[0] for _, values in walk]
print(round(most() - before), "".join(found))
'''


@pytest.mark.parametrize("shape, records", [("after", "ABC"), ("before", "ABC"), ("beside", "ABCABC"), ("no record", "")])
def test_a_document_whose_bulk_is_no_record_is_not_held(shape, records):
    """24 MB that are no record were held whole, as a tree of twelve times their size. Memory follows the largest
    record, as the docs say, whatever else the document holds."""
    import subprocess
    import sys
    done = subprocess.run([sys.executable, "-c", HELD, shape], capture_output=True, text=True, timeout=120,
                          cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    assert done.returncode == 0, done.stderr[-800:]
    grown, _, found = done.stdout.strip().partition(" ")
    assert found == records
    assert int(grown) < 40, f"{grown} MB were held for a document of 24 MB that are no record"
