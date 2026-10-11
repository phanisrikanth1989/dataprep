"""File input properties: a row for every property, as in Talend; and v1's one wide row for a job written for v1."""
import logging
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import columns, flow, job, writer

PAIRS = "key:str, value:str"
FILE = b"# a comment\n! another\nhost = localhost\nport:8080\n\nname=ann = bob\nempty=\n"
INI = b"; a comment\n[db]\nhost = h1\nport=1\n\n# another\n[web]\nhost: h2\nextra=x\n"


def properties(out=PAIRS, kind="FileInputProperties", **config):
    """properties file -> file."""
    source = {"id": "in", "type": kind, "config": {"filename": "app.properties", **config},
              "schema": {"input": [], "output": columns(out)}, "inputs": [], "outputs": ["row1"]}
    return job([source, writer(out, inputs=("row1",))], [flow("row1", "in", "out")])


def v2(tmp_path, made, data=FILE):
    """Run on v2 alone, inside tmp_path; returns how it ended and the lines of out.csv under its header."""
    if data is not None:
        (tmp_path / "app.properties").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    written = tmp_path / "out.csv"
    return result, written.read_text().splitlines()[1:] if written.exists() else None


def rows(tmp_path, data=FILE, **kwargs):
    result, lines = v2(tmp_path, properties(**kwargs), data)
    assert result.status == "success", result.error
    return lines


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# A properties file, as Java reads one
# ------------------------------------------------------------------

def test_row_for_every_property_in_the_order_of_the_file(tmp_path):
    assert rows(tmp_path) == ["host;localhost", "port;8080", "name;ann = bob", "empty;"]


@pytest.mark.parametrize("line, row", [
    (b"a=b", "a;b"), (b"a:b", "a;b"), (b"a b", "a;b"), (b"a\tb", "a;b"), (b"  a  =  b  ", "a;b  "), (b"a = = b", "a;= b"),
    (b"a", "a;"), (b"a=", "a;"), (b"a\\=b=c", "a=b;c"), (b"a\\:b:c", "a:b;c"), (b"a\\ b=c", "a b;c"),
    (b"a=x\\ty", "a;x\ty"), (b"a=\\u00e9\\u20ac", "a;\u00e9\u20ac"), (b"a=c:\\\\dir", "a;c:\\dir"), (b"a=\\q", "a;q"),
    (b"a=one \\\n     two", "a;one two"), (b"a=one\\\\", "a;one\\"), (b"a=caf\xe9", "a;caf\u00e9"),
    (b"a=1\r\nb=2", "a;1|b;2"), (b"a=1\rb=2", "a;1|b;2"), (b"a=x # no comment", "a;x # no comment"),
    (b"#a=1\n  !b=2\n c=3", "c;3"), (b"a=1\\\n#b", "a;1#b"), (b"a=1\na=2\nb=3", "a;2|b;3"), (b"=v", ";v"),
])
def test_line_of_a_properties_file(tmp_path, line, row):
    assert "|".join(rows(tmp_path, line + b"\n")) == row


def test_backslash_the_file_ends_on_goes_on_into_nothing(tmp_path):
    (tmp_path / "app.properties").write_bytes(b"a=x\\")
    result, lines = v2(tmp_path, properties(), None)
    assert result.status == "success" and lines == ["a;x"]


def test_entry_before_the_first_section_of_an_ini_file_is_of_no_section(tmp_path):
    got = rows(tmp_path, b"stray=1\n[s]\na=2\n", out="key:str, value:str, section:str", file_format="INI_FORMAT",
               retrive_mode="RETRIVE_ALL")
    assert got == ["a;2;s"]


def test_file_with_no_property(tmp_path):
    assert rows(tmp_path, b"# only a comment\n\n") == [] and rows(tmp_path, b"") == []


def test_encoding_is_not_read_for_a_properties_file_as_in_java(tmp_path):
    assert rows(tmp_path, "a=caf\u00e9\n".encode("utf-8"), encoding="UTF-8") == ["a;caf\u00c3\u00a9"]


# ------------------------------------------------------------------
# An ini file
# ------------------------------------------------------------------

def test_one_section_of_an_ini_file(tmp_path):
    assert rows(tmp_path, INI, file_format="INI_FORMAT", section_name="web") == ["host;h2", "extra;x"]
    assert rows(tmp_path, INI, file_format="INI_FORMAT", section_name="nope") == []
    assert rows(tmp_path, INI, file_format="INI_FORMAT", retrive_mode="RETRIVE_BY_SECTION", section_name="db") == ["host;h1", "port;1"]


def test_every_section_of_an_ini_file_with_its_name(tmp_path):
    got = rows(tmp_path, INI, out="key:str, value:str, section:str", file_format="INI_FORMAT", retrive_mode="RETRIVE_ALL")
    assert got == ["host;h1;db", "port;1;db", "host;h2;web", "extra;x;web"]


def test_names_of_the_sections_of_an_ini_file(tmp_path):
    got = rows(tmp_path, INI + b"[empty]\n", out="section:str", file_format="INI_FORMAT", retrive_mode="RETRIVE_SECTIONS")
    assert got == ["db", "web", "empty"]


@pytest.mark.parametrize("text, got", [
    ("[s]\na=1\na=2\n", ["a;2"]), ("[s]\n a = b c \n", ["a;b c"]), ("[ s ]\na=1\n", ["a;1"]), ("[s]\na\n", ["a;"]),
    ("[s]\na=\n", ["a;"]), ("[s]\na=x=y:z\n", ["a;x=y:z"]), ("[t]\nb=2\n[s]\na=1\n[t]\nc=3\n", ["a;1"]),
    ("[s]\r\na=1\r\n", ["a;1"]), ("[s]\na=caf\u00e9\n", ["a;caf\u00e9"]),
])
def test_line_of_an_ini_file(tmp_path, text, got):
    assert rows(tmp_path, text.encode("utf-8"), file_format="INI_FORMAT", section_name="s", encoding="UTF-8") == got


def test_byte_order_mark_is_no_part_of_an_ini_file(tmp_path):
    assert rows(tmp_path, "[s]\na=1\n".encode("utf-8-sig"), file_format="INI_FORMAT", section_name="s", encoding="UTF-8") == ["a;1"]


def test_ini_file_that_is_not_in_its_encoding_fails_in_plain_words(tmp_path):
    result, _ = v2(tmp_path, properties(file_format="INI_FORMAT", section_name="s", encoding="UTF-8"), b"[s]\na=\xff\xfe\n")
    assert result.status == "failed"
    assert result.error == "'app.properties' is not written in UTF-8: a byte in it is no character there"


def test_ini_file_is_read_in_its_encoding(tmp_path):
    assert rows(tmp_path, "[s]\na=caf\u00e9\u20ac\n".encode("iso-8859-15"), file_format="INI_FORMAT", section_name="s") == [
        "a;caf\u00e9\u20ac"]


# ------------------------------------------------------------------
# Rows, their numbers and their types
# ------------------------------------------------------------------

def test_row_is_named_by_the_line_its_property_is_on(tmp_path):
    # A comment, a blank line and a value that goes on over two lines come before it.
    made = dict(properties(), run={"only": {"source": "in", "where": {"key": ["c"]}}, "trace": True})
    result, lines = v2(tmp_path, made, b"# c\na=1 \\\n  more\n\nb=\nc=3\n")
    assert result.status == "success" and lines == ["c;3"]
    assert result.summary()["only"]["rows"] == ["line 6 of app.properties"]
    assert result.summary()["trace"][0]["outputs"]["main"]["from"] == ["line 6 of app.properties"]


def test_run_for_a_few_properties_by_line_or_by_key(tmp_path):
    made = dict(properties(), run={"only": {"source": "in", "lines": [4]}})
    result, lines = v2(tmp_path, made)
    assert result.status == "success" and lines == ["port;8080"]
    assert result.summary()["only"]["rows"] == ["line 4 of app.properties"]
    made = dict(properties(), run={"only": {"source": "in", "where": {"key": ["name", "host"]}}})
    assert v2(tmp_path, made)[1] == ["host;localhost", "name;ann = bob"]


def test_rows_are_counted(tmp_path):
    result, _ = v2(tmp_path, dict(properties(), run={"row_counts": True}))
    assert result.counts["in"] == {"NB_LINE": 4, "NB_LINE_OK": 4, "NB_LINE_REJECT": 0}


def test_value_is_read_as_the_type_its_column_declares(tmp_path):
    assert rows(tmp_path, b"a=7\nb= 8 \nc=x\n", out="key:str, value:int") == ["a;7", "b;8", "c;"]


def test_declared_column_that_is_none_of_the_three_is_missing_and_the_order_is_the_schemas(tmp_path):
    got = rows(tmp_path, INI, out="section:str, value:str, key:str", file_format="INI_FORMAT", retrive_mode="RETRIVE_ALL")
    assert got[0] == "db;h1;host"
    assert rows(tmp_path, out="value:str") == ["localhost", "8080", "ann = bob", ""]


# ------------------------------------------------------------------
# A job written for v1: one row, a column for each property the schema names
# ------------------------------------------------------------------

WIDE = "host:str, port:int, name:str, empty:str, nope:str"


def test_schema_of_other_columns_gets_v1s_one_row(tmp_path):
    run = assert_matches_v1(properties(out=WIDE), {"app.properties": FILE}, tmp_path)
    assert run.files["out.csv"] == b"host;port;name;empty;nope\nlocalhost;8080;ann = bob;;\n"


def test_one_row_for_each_section_of_an_ini_file_read_whole(tmp_path):
    made = properties(out="host:str, port:int, extra:str, __section__:str", file_format="INI_FORMAT", retrive_mode="RETRIVE_ALL")
    run = assert_matches_v1(made, {"app.properties": INI}, tmp_path)
    assert run.files["out.csv"] == b"host;port;extra;__section__\nh1;1;;db\nh2;;x;web\n"


def test_one_row_for_one_section_and_a_row_of_nothing_for_one_that_is_not_there(tmp_path):
    made = properties(out="host:str, port:int", file_format="INI_FORMAT", section_name="web")
    assert assert_matches_v1(made, {"app.properties": INI}, tmp_path).files["out.csv"] == b"host;port\nh2;\n"
    made = properties(out="host:str, port:int", file_format="INI_FORMAT", section_name="nope")
    assert assert_matches_v1(made, {"app.properties": INI}, tmp_path / "b").files["out.csv"] == b"host;port\n;\n"


def test_wide_row_is_named_by_the_file(tmp_path):
    result, _ = v2(tmp_path, properties(out="host:str, port:int!"), b"host=h\n")
    assert result.status == "failed"
    assert result.error == "Column 'port' has NULL values but is not nullable; the row is line 1 of app.properties"


# ------------------------------------------------------------------
# What is refused, and what fails
# ------------------------------------------------------------------

def test_file_that_is_not_there_fails_the_job(tmp_path):
    result, _ = v2(tmp_path, properties(), None)
    assert result.status == "failed" and result.error == "File not found: 'app.properties'"


@pytest.mark.parametrize("config, key", [
    ({"file_format": "XML"}, "file_format"), ({"retrive_mode": "RETRIVE_SOME"}, "retrive_mode"),
    ({"encoding": "nope-8"}, "encoding"), ({"filename": ""}, "path"), ({"nope": 1}, "nope"),
])
def test_what_cannot_be_read_refuses_the_job(config, key):
    assert [path for path, _ in refusals(properties(**config))] == [key]


def test_columns_have_to_be_declared():
    made = properties()
    made["components"][0]["schema"]["output"] = []
    assert ("schema", "a properties reader needs its columns declared: key and value, as Talend has them") in refusals(made)


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("file_input_properties", "FileInputProperties", "tFileInputProperties")):
        (tmp_path / str(at)).mkdir()
        result, lines = v2(tmp_path / str(at), properties(kind=kind))
        assert result.status == "success" and lines[0] == "host;localhost"
