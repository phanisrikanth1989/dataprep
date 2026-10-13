"""XML file output: rows written as the elements of a document."""
import logging
import os

import pytest
from lxml import etree

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, reader, writer

from .test_file_actions_kit import filled, on_v2

SCHEMA = "id:int, name:str, amount:Decimal#2, day:datetime@%Y-%m-%d"
DATA = b"1;ann;10.5;2024-01-31\n2;bob;;\n3;;7;2024-02-01\n"


def writing(schema=SCHEMA, kind="FileOutputXML", **config):
    made = {"filename": "out.xml", "encoding": "UTF-8"}
    made.update(config)
    return {"id": "out", "type": kind, "config": made, "inputs": ["row1"], "outputs": [],
            "schema": {"input": columns(schema) if schema else [], "output": []}}


def written_by(tmp_path, data=DATA, schema=SCHEMA, **config):
    """Run in.csv -> the XML output; returns how it ended, the bytes of out.xml (None when not there) and the folder."""
    made = job([reader(schema), writing(schema, **config)], [flow("row1", "in", "out")])
    folder = filled(tmp_path, {"in.csv": data})
    result = on_v2(made, folder)
    target = folder / "out.xml"
    return result, target.read_bytes() if target.exists() else None, folder


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


def rows_of(written, path="/root/row"):
    """Every row element of a written document: its attributes, and its children as name and text (None for nil)."""
    nil = "{http://www.w3.org/2001/XMLSchema-instance}nil"
    return [(dict(row.attrib), [(child.tag, None if child.get(nil) == "true" else (child.text or "")) for child in row])
            for row in etree.fromstring(written).xpath(path)]


# ------------------------------------------------------------------
# Rows as elements
# ------------------------------------------------------------------

def test_row_is_an_element_and_its_columns_are_the_elements_in_it_one_row_a_line(tmp_path):
    result, written, _ = written_by(tmp_path)
    assert result.status == "success", result.error
    assert written == (
        b'<?xml version="1.0" encoding="UTF-8"?>\n<root>\n'
        b"<row><id>1</id><name>ann</name><amount>10.50</amount><day>2024-01-31</day></row>\n"
        b"<row><id>2</id><name>bob</name><amount></amount><day></day></row>\n"
        b"<row><id>3</id><name></name><amount>7.00</amount><day>2024-02-01</day></row>\n"
        b"</root>\n")
    assert result.rows["out"] == 3 and result.global_map["out_FILE_NAME"] == "out.xml"


def test_root_tags_are_nested_in_the_order_given_and_the_row_has_the_name_given(tmp_path):
    result, written, _ = written_by(tmp_path, row_tag="order", root_tags=[{"name": "orders"}, {"name": "of_today"}])
    assert result.status == "success", result.error
    assert written.startswith(b'<?xml version="1.0" encoding="UTF-8"?>\n<orders>\n<of_today>\n<order><id>1</id>')
    assert written.endswith(b"</order>\n</of_today>\n</orders>\n")
    assert len(etree.fromstring(written).xpath("/orders/of_today/order")) == 3


def test_column_may_be_an_attribute_of_the_row_and_may_have_another_name(tmp_path):
    mapping = [{"column": "id", "as_attribute": True}, {"column": "name", "as_attribute": False, "label": "called"},
               {"column": "day", "as_attribute": True, "label": "on"}]
    result, written, _ = written_by(tmp_path, mapping=mapping)
    assert result.status == "success", result.error
    assert written.splitlines()[2] == b'<row id="1" on="2024-01-31"><called>ann</called><amount>10.50</amount></row>'
    assert rows_of(written)[1] == ({"id": "2", "on": ""}, [("called", "bob"), ("amount", "")])


def test_columns_are_those_that_arrive_where_none_is_declared_and_numbers_alone_need_no_looking_at(tmp_path):
    made = job([reader("id:int, n:int"), writing(None)], [flow("row1", "in", "out")])
    made["components"][1]["schema"] = {"input": [], "output": []}
    folder = filled(tmp_path, {"in.csv": b"1;10\n2;\n"})
    result = on_v2(made, folder)
    assert result.status == "success", result.error
    assert rows_of((folder / "out.xml").read_bytes()) == [({}, [("id", "1"), ("n", "10")]), ({}, [("id", "2"), ("n", "")])]


def test_no_row_gives_a_document_with_nothing_in_its_root_or_no_file_where_none_is_wanted(tmp_path):
    result, written, _ = written_by(tmp_path / "empty", b"")
    assert result.status == "success" and written == b'<?xml version="1.0" encoding="UTF-8"?>\n<root>\n</root>\n'
    folder = filled(tmp_path / "none", {"out.xml": b"of an earlier run"})
    result, written, _ = written_by(tmp_path / "none", b"", delete_empty_file=True)
    assert result.status == "success" and written is None


# ------------------------------------------------------------------
# A value that is missing
# ------------------------------------------------------------------

@pytest.mark.parametrize("missing, second", [
    ("empty", ({"id": "2", "day": ""}, [("name", "bob"), ("amount", "")])),
    ("omit", ({"id": "2"}, [("name", "bob")])),
    ("nil", ({"id": "2"}, [("name", "bob"), ("amount", None)])),
])
def test_missing_value_is_written_empty_or_left_out_or_marked_as_missing(tmp_path, missing, second):
    mapping = [{"column": "id", "as_attribute": True}, {"column": "day", "as_attribute": True}]
    result, written, _ = written_by(tmp_path, mapping=mapping, missing=missing)
    assert result.status == "success", result.error
    assert rows_of(written)[1] == second
    assert (b'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' in written) is (missing == "nil")


def test_mark_of_a_missing_value_is_declared_once_on_the_outermost_element(tmp_path):
    result, written, _ = written_by(tmp_path, missing="nil", root_tags=[{"name": "a"}, {"name": "b"}])
    assert result.status == "success", result.error
    assert written.splitlines()[1:3] == [b'<a xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">', b"<b>"]
    assert rows_of(written, "/a/b/row")[1][1] == [("id", "2"), ("name", "bob"), ("amount", None), ("day", None)]


# ------------------------------------------------------------------
# What a value may hold
# ------------------------------------------------------------------

HARD = ["a < b & c > d", "it's \"quoted\"", "tab\there", "two\nlines", "back\r\nagain", " spaces  kept ", "]]> and <![CDATA[",
        "caf" + chr(233) + " " + chr(0x20AC) + " " + chr(0x1F600), "&amp; already", "<row>like a tag</row>"]


@pytest.mark.parametrize("encoding", ["UTF-8", "ISO-8859-15", "US-ASCII", "UTF-16", "windows-1252", "Shift_JIS"])
@pytest.mark.parametrize("as_attribute", [False, True], ids=["in an element", "in an attribute"])
def test_every_text_is_read_back_as_it_was_whatever_it_holds_and_whatever_the_encoding(tmp_path, as_attribute, encoding):
    text = "\n".join(f'{at};"{value.replace(chr(34), chr(34) * 2)}"' for at, value in enumerate(HARD)).encode("utf-8") + b"\n"
    made = job([reader("id:int, name:str", csv_option=True, text_enclosure='"', escape_char='"'),
                writing("id:int, name:str", encoding=encoding, mapping=[{"column": "name", "as_attribute": as_attribute}])],
               [flow("row1", "in", "out")])
    folder = filled(tmp_path, {"in.csv": text})
    result = on_v2(made, folder)
    assert result.status == "success", result.error
    written = (folder / "out.xml").read_bytes()
    read_back = [(row.get("name") if as_attribute else row.findtext("name")) for row in etree.fromstring(written).xpath("/root/row")]
    assert read_back == HARD
    assert written.count(b"\n") == len(HARD) + 3
    assert f'encoding="{encoding}"'.encode("utf-16" if encoding == "UTF-16" else "ascii")[2 if encoding == "UTF-16" else 0:] in written


def test_character_the_encoding_lacks_is_written_by_its_number(tmp_path):
    result, written, _ = written_by(tmp_path, ("1;5 " + chr(0x20AC) + ";;\n").encode("utf-8"), encoding="ISO-8859-1")
    assert result.status == "success", result.error
    assert b"<name>5 &#8364;</name>" in written and rows_of(written)[0][1][1] == ("name", "5 " + chr(0x20AC))


def test_character_xml_cannot_hold_fails_the_job_and_names_the_row(tmp_path):
    result, written, _ = written_by(tmp_path, b"1;ann;;\n2;b\x01b;;\n")
    assert (result.status, result.failed_component, written) == ("failed", "out", None)
    assert result.error == "column 'name' of row 2 holds a character XML cannot hold: 'b\\x01b'"


def test_first_row_with_such_a_character_is_the_one_named_whichever_column_it_is_in(tmp_path):
    data = b"a;fine;x\nb;fine;y\x02\nc;no\x01;z\nd;no\x01;w\x02\n"
    result, written, _ = written_by(tmp_path, data, "id:str, one:str, two:str")
    assert (result.status, written) == ("failed", None)
    assert result.error == "column 'two' of row 2 holds a character XML cannot hold: 'y\\x02'"


def test_document_is_written_and_read_back_where_the_library_that_reads_xml_is_not_there(tmp_path, monkeypatch):
    from src.v2 import xml_reader
    monkeypatch.setattr(xml_reader, "etree", None)
    result, written, _ = written_by(tmp_path / "fine")
    assert result.status == "success" and len(rows_of(written)) == 3
    result, written, _ = written_by(tmp_path / "broken", b"1;not xml\n", "id:int, doc:str", input_is_document=True, document_col="doc")
    assert (result.status, written) == ("failed", None)
    assert result.error.startswith("what was written to 'out.xml' is not well-formed XML: ")


# ------------------------------------------------------------------
# Groups
# ------------------------------------------------------------------

GROUPED = b"north;ann;1\nnorth;bob;2\nsouth;cy;3\nnorth;dee;4\n"


def test_rows_that_follow_each_other_with_one_value_stand_in_one_element_that_holds_the_value(tmp_path):
    result, written, _ = written_by(tmp_path, GROUPED, "region:str, name:str, n:int", use_dynamic_grouping=True,
                                    group_by=[{"column": "region", "label": "is"}])
    assert result.status == "success", result.error
    assert written.decode() == (
        '<?xml version="1.0" encoding="UTF-8"?>\n<root>\n'
        '<region is="north">\n<row><name>ann</name><n>1</n></row>\n<row><name>bob</name><n>2</n></row>\n</region>\n'
        '<region is="south">\n<row><name>cy</name><n>3</n></row>\n</region>\n'
        '<region is="north">\n<row><name>dee</name><n>4</n></row>\n</region>\n'
        "</root>\n")


def test_group_in_a_group_starts_anew_when_the_outer_one_does(tmp_path):
    data = b"a;x;1\na;x;2\na;y;3\nb;y;4\n"
    result, written, _ = written_by(tmp_path, data, "one:str, two:str, n:int", use_dynamic_grouping=True,
                                    group_by=[{"column": "one", "label": "v"}, {"column": "two", "label": "v"}])
    assert result.status == "success", result.error
    found = [(one.get("v"), two.get("v"), [row.findtext("n") for row in two]) for one in etree.fromstring(written) for two in one]
    assert found == [("a", "x", ["1", "2"]), ("a", "y", ["3"]), ("b", "y", ["4"])]


def test_groups_hold_together_over_many_rows_whatever_pieces_the_engine_goes_through_them_in(tmp_path):
    import itertools
    import random
    drawn = random.Random(3)
    rows = []
    for outer in range(4000):
        for inner in range(drawn.randint(1, 4)):
            # Now and then the same values come back at once in a new outer group, or as nothing at all.
            two = drawn.choice(["x", "y", ""])
            rows += [(f"o{outer % 7}" if outer % 5 else "", two, len(rows) + n) for n in range(drawn.randint(1, 30))]
    data = "".join(f"{one};{two};{n}\n" for one, two, n in rows).encode()
    result, written, _ = written_by(tmp_path, data, "one:str, two:str, n:int", use_dynamic_grouping=True,
                                    group_by=[{"column": "one", "label": "v"}, {"column": "two", "label": "v"}])
    assert result.status == "success", result.error
    found = [(one.get("v"), [(two.get("v"), [int(row.findtext("n")) for row in two]) for two in one])
             for one in etree.fromstring(written)]
    wanted = [(one, [(two, [n for _, _, n in inner]) for two, inner in itertools.groupby(outer, key=lambda row: row[1])])
              for one, outer in ((one, list(outer)) for one, outer in itertools.groupby(rows, key=lambda row: row[0]))]
    assert len(rows) > 100_000 and found == wanted


def test_missing_value_is_a_group_of_its_own_also_where_the_rows_start_with_it(tmp_path):
    data = b";a\n;b\n1;c\n;d\n2;e\n2;f\n"
    result, written, _ = written_by(tmp_path, data, "n:int, name:str", use_dynamic_grouping=True,
                                    group_by=[{"column": "n", "label": "is"}])
    assert result.status == "success", result.error
    found = [(group.get("is"), [row.findtext("name") for row in group]) for group in etree.fromstring(written)]
    assert found == [("", ["a", "b"]), ("1", ["c"]), ("", ["d"]), ("2", ["e", "f"])]


def test_grouping_is_not_done_unless_it_is_switched_on(tmp_path):
    result, written, _ = written_by(tmp_path, GROUPED, "region:str, name:str, n:int", use_dynamic_grouping=False,
                                    group_by=[{"column": "region", "label": "is"}])
    assert len(rows_of(written)) == 4 and rows_of(written)[0][1][0] == ("region", "north")


# ------------------------------------------------------------------
# A column that holds the document
# ------------------------------------------------------------------

def test_column_that_holds_a_document_is_written_as_the_file_under_the_jobs_own_declaration(tmp_path):
    document = '<?xml version="1.0" encoding="ISO-8859-1"?><a><b>caf' + chr(233) + "</b></a>"
    result, written, _ = written_by(tmp_path, ("1;" + document + "\n").encode("utf-8"), "id:int, doc:str", input_is_document=True,
                                    document_col="doc")
    assert result.status == "success", result.error
    assert written == ('<?xml version="1.0" encoding="UTF-8"?>\n<a><b>caf' + chr(233) + "</b></a>\n").encode("utf-8")


def test_white_space_around_the_document_goes_where_it_is_to_be_trimmed(tmp_path):
    for trim, body in ((False, b"  <a>x</a> \n"), (True, b"<a>x</a>\n")):
        result, written, _ = written_by(tmp_path / str(trim), b"1;  <a>x</a> \n", "id:int, doc:str", input_is_document=True,
                                        document_col="doc", trim=trim)
        assert result.status == "success", result.error
        assert written == b'<?xml version="1.0" encoding="UTF-8"?>\n' + body


def test_document_that_is_none_fails_the_job_also_in_an_encoding_only_lxml_reads(tmp_path):
    result, written, _ = written_by(tmp_path, b"1;<a><b></a>\n", "id:int, doc:str", input_is_document=True, document_col="doc",
                                    encoding="Shift_JIS")
    assert (result.status, written) == ("failed", None)
    assert result.error.startswith("what was written to 'out.xml' is not well-formed XML: ")


def test_more_than_one_document_and_a_column_that_holds_none_fail_the_job(tmp_path):
    result, written, _ = written_by(tmp_path / "two", b"1;<a/>\n2;<b/>\n", "id:int, doc:str", input_is_document=True, document_col="doc")
    assert (result.status, written) == ("failed", None)
    assert result.error == "2 rows arrive, and a file holds one document: `input_is_document` writes the document of one row"
    result, written, _ = written_by(tmp_path / "none", b"1;not xml\n", "id:int, doc:str", input_is_document=True, document_col="doc")
    assert (result.status, written) == ("failed", None)
    assert result.error.startswith("what was written to 'out.xml' is not well-formed XML: ")


# ------------------------------------------------------------------
# The file
# ------------------------------------------------------------------

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
    result, written, _ = written_by(tmp_path / "kept", b"1;b\x01b;;\n")
    assert result.status == "failed" and written == b"of an earlier run"


# ------------------------------------------------------------------
# What is refused, a converted job, and the names it goes by
# ------------------------------------------------------------------

@pytest.mark.parametrize("config, said", [
    ({"row_tag": "a row"}, "row_tag: 'a row' is no name an element may have"),
    ({"root_tags": [{"name": "1st"}]}, "root_tags[0].name: '1st' is no name an element may have"),
    ({"mapping": [{"column": "nope"}]}, "mapping[0].column: there is no column 'nope'; the columns are: id, name"),
    ({"mapping": [{"column": "name", "label": "x:y"}]}, "mapping[0].label: 'x:y' is no name an element may have"),
    ({"use_dynamic_grouping": True, "group_by": [{"column": "nope", "label": "v"}]},
     "group_by[0].column: there is no column 'nope'; the columns are: id, name"),
    ({"use_dynamic_grouping": True, "group_by": [{"column": "id", "label": "a b"}]},
     "group_by[0].label: 'a b' is no name an attribute may have"),
    ({"input_is_document": True, "document_col": "nope"}, "document_col: there is no column 'nope'; the columns are: id, name"),
    ({"split": True}, "split: v2 writes one file: split the rows before the output"),
    ({"advanced_separator": True},
     "advanced_separator: v2 writes a number one way: write it as text of the form wanted before the output"),
    ({"missing": "zero"}, "missing: 'zero' is not allowed; use one of 'empty', 'omit', 'nil'"),
    ({"filename": ""}, "path: the file to write has no name"),
    ({"nope": 1}, "nope: unknown config key"),
])
def test_what_cannot_be_written_refuses_the_job(config, said):
    found = refusals(job([reader("id:int, name:str"), writing("id:int, name:str", **config)], [flow("row1", "in", "out")]))
    assert [f"{key}: {reason}" for key, reason in found] == [said]


def test_column_whose_name_is_no_name_of_xml_needs_another(tmp_path):
    made = job([reader("id:int, the name:str"), writing("id:int, the name:str")], [flow("row1", "in", "out")])
    assert refusals(made) == [("schema", "the column 'the name' has no name an element may have: give it one with a `label` "
                                         "in `mapping`")]


def test_what_the_converter_writes_is_taken(tmp_path):
    result, written, _ = written_by(
        tmp_path, kind="tFileOutputXML", input_is_document=False, document_col="", row_tag="row", root_tags=[{"name": "root"}],
        mapping=[{"column": "id", "as_attribute": True}], use_dynamic_grouping=False, group_by=[], flushonrow=False,
        flushonrow_num="1", split=False, split_every="1000", create=True, trim=False, advanced_separator=False,
        thousands_separator=",", decimal_separator=".", delete_empty_file=False, tstatcatcher_stats=False, label="x")
    assert result.status == "success" and len(rows_of(written)) == 3


@pytest.mark.parametrize("kind", ["file_output_xml", "FileOutputXML", "tFileOutputXML"])
def test_every_name_of_it(tmp_path, kind):
    result, written, _ = written_by(tmp_path, kind=kind)
    assert result.status == "success" and len(rows_of(written)) == 3


# ------------------------------------------------------------------
# What the review of the XML group found (ticket 120)
# ------------------------------------------------------------------

READ_BACK = r'''
import resource, sys
from src.v2 import xml_writer

def most():
    held = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return held / (1 << 20) if sys.platform == "darwin" else held / 1024

path, encoding, tags = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
row = "<row><id>%d</id><name>\u540d\u524d %d</name><note>some words of a row</note></row>"
with open(path, "w", encoding=encoding) as out:
    out.write(f'<?xml version="1.0" encoding="{encoding}"?>' + "".join(f"<{tag}>" for tag in tags))
    for at in range(0, 200_000, 1000):
        out.write("".join(row % (n, n) for n in range(at, at + 1000)))
    out.write("".join(f"</{tag}>" for tag in reversed(tags)))
before = most()
xml_writer.read_back(path, "out.xml")
print(round(most() - before))
'''


@pytest.mark.parametrize("tags", ["sales", "sales,body", "sales,body,rows"])
def test_reading_back_holds_no_tree_however_deep_the_rows_stand(tmp_path, tags):
    """In an encoding only lxml reads, the rows were let go of only where they stood right under the root: under
    two root tags the whole document was held as a tree."""
    import subprocess
    import sys
    done = subprocess.run([sys.executable, "-c", READ_BACK, str(tmp_path / "out.xml"), "GBK", tags],
                          capture_output=True, text=True, timeout=120,
                          cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
    assert done.returncode == 0, done.stderr[-800:]
    grown = int(done.stdout.strip())
    # Emptied and not taken out of the tree, the rows still held 26 MB here.
    assert grown < 12, f"{grown} MB were held to read back a document of {os.path.getsize(tmp_path / 'out.xml') >> 20} MB"


def test_reading_back_in_such_an_encoding_still_finds_what_is_not_well_formed(tmp_path):
    from src.v2 import xml_reader, xml_writer
    for body, wrong in (("<a><b>\u540d</b></a>", None), ("<a><b>\u540d</a>", "Opening and ending tag mismatch"),
                        ("<a><b>\u540d</b></a><c/>", "Extra content")):
        (tmp_path / "out.xml").write_text(f'<?xml version="1.0" encoding="GBK"?>{body}', encoding="GBK")
        if wrong is None:
            xml_writer.read_back(str(tmp_path / "out.xml"), "out.xml")
            continue
        with pytest.raises(xml_reader.Fault, match=f"what was written to 'out.xml' is not well-formed XML: {wrong}"):
            xml_writer.read_back(str(tmp_path / "out.xml"), "out.xml")
