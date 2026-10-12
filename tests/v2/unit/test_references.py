"""An item in a config string: a globalMap entry or a context variable, alone or joined to text.

The converter leaves such a value as Talend wrote it, often under its
`{{java}}` mark: `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`,
`context.out_dir + "/" + ((String)globalMap.get("tFileList_1_CURRENT_FILE"))`.
It is a lookup and a join, and v2 reads it; anything more is Java and stays
refused.
"""
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.engine.references import parsed, value_of
from src.v2.errors import ConfigurationError, JobRefusedError
from tests.v2.components.kit import flow, job, reader, writer

HELD = {"p": "in.csv", "n": 5, "none": None, "row1.path": "/data/a.csv", "f": 1.5, "ok": True}
CONTEXT = {"dir": "/out", "count": 3}


def read(text):
    terms = parsed(text)
    assert terms is not None, f"{text!r} was not read as an item reference"
    return value_of(terms, CONTEXT, HELD)


# ------------------------------------------------------------------
# What is read
# ------------------------------------------------------------------

@pytest.mark.parametrize("text, value", [
    ('((String)globalMap.get("p"))', "in.csv"), ('(String)globalMap.get("p")', "in.csv"), ('globalMap.get("p")', "in.csv"),
    ("globalMap.get('p')", "in.csv"), ('  (( String ) globalMap.get( "p" ))  ', "in.csv"),
    ('((String)globalMap.get("row1.path"))', "/data/a.csv"),
    ('((Integer)globalMap.get("n"))', 5), ('((Object)globalMap.get("none"))', None), ('((Boolean)globalMap.get("ok"))', True),
    ("context.dir", "/out"), ("context.count", 3), ('"plain text"', "plain text"), ('""', ""),
], ids=["cast in brackets", "cast", "bare", "single quotes", "blanks", "a key with a dot", "a number", "nothing",
        "true or false", "a context variable", "a context number", "text", "empty text"])
def test_one_reference_is_the_value_itself(text, value):
    held = read(text)
    assert held == value and type(held) is type(value)


@pytest.mark.parametrize("text, value", [
    ('context.dir + "/" + ((String)globalMap.get("p"))', "/out/in.csv"),
    ('context.dir+"/"+globalMap.get("p")', "/out/in.csv"),
    ('"n=" + ((Integer)globalMap.get("n")) + ", f=" + globalMap.get("f")', "n=5, f=1.5"),
    ('"a" + ((String)globalMap.get("none")) + "b"', "ab"),
    ('(context.dir + "/x")', "/out/x"),
    (r'"say \"hi\" \\ " + context.count', 'say "hi" \\ 3'),
    ('"tab\\there" + "\\n"', "tab\there\n"),
    ('"a + b" + " (c)"', "a + b (c)"),
], ids=["path", "no blanks", "numbers", "nothing joins as nothing", "brackets round it all", "escaped quotes", "escapes",
        "signs inside text"])
def test_references_joined_to_text_are_text(text, value):
    assert read(text) == value


@pytest.mark.parametrize("text", [
    '((String)globalMap.get("p")).substring(1)', 'globalMap.get("p").trim()', "context.dir.replace(\"a\", \"b\")",
    'context.dir + 1', "TalendDate.getDate(\"yyyy\")", 'context.dir + other', '"unclosed', 'globalMap.get(p)',
    'context.dir +', '+ context.dir', "", "   ", 'a" + context.dir + "b', "globalMap.get(\"p\") globalMap.get(\"p\")",
    '"a" "b"', "context.", 'globalMap.put("p", 1)', '"bad \\q escape"',
])
def test_anything_more_is_not_an_item_reference(text):
    assert parsed(text) is None


def test_entry_that_is_not_there_is_said_by_name():
    with pytest.raises(ConfigurationError, match="globalMap has no entry 'nope'"):
        value_of(parsed('"a" + globalMap.get("nope")'), CONTEXT, HELD)
    with pytest.raises(ConfigurationError, match="context has no variable 'nope'"):
        value_of(parsed("context.nope"), CONTEXT, HELD)


# ------------------------------------------------------------------
# In a job
# ------------------------------------------------------------------

def pointed(path, **more):
    """A set global var puts `p` (a file's name) and `sub` (a folder's); the reader that follows reads the path given."""
    setter = {"id": "set", "type": "SetGlobalVar", "inputs": [], "outputs": [], "schema": {"input": [], "output": []},
              "config": {"variables": [{"key": "p", "value": "in.csv"}, {"key": "sub", "value": "sub"}]}}
    made = job([setter, reader("id:int", path=path), writer("id:int", inputs=("row1",))], [flow("row1", "in", "out")],
               triggers=[{"type": "OnSubjobOk", "from": "set", "to": "in"}], **more)
    made["context"] = {"Default": {"dir": {"value": "sub", "type": "str"}}}
    return made


def ran(tmp_path, made):
    (tmp_path / "sub").mkdir(exist_ok=True)
    (tmp_path / "in.csv").write_bytes(b"1\n")
    (tmp_path / "sub/in.csv").write_bytes(b"2\n")
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    return result, (tmp_path / "out.csv").read_bytes() if (tmp_path / "out.csv").exists() else None


@pytest.mark.parametrize("path, written", [
    ('{{java}}((String)globalMap.get("p"))', b"id\n1\n"), ('((String)globalMap.get("p"))', b"id\n1\n"),
    ('{{java}}context.dir + "/" + ((String)globalMap.get("p"))', b"id\n2\n"),
    ('((String)globalMap.get("sub")) + "/" + ((String)globalMap.get("p"))', b"id\n2\n"),
    ('{{java}}context.dir + "/in.csv"', b"id\n2\n"), ('{{java}}"in.csv"', b"id\n1\n"),
], ids=["marked", "not marked", "marked, joined", "not marked, joined", "marked, no entry in it", "marked, text alone"])
def test_reader_reads_the_file_an_earlier_subjob_named(tmp_path, path, written):
    result, out = ran(tmp_path, pointed(path))
    assert result.status == "success", result.error
    assert out == written


def test_job_with_an_item_under_the_java_mark_loads_and_other_java_is_still_refused():
    load_job(pointed('{{java}}((String)globalMap.get("p"))'))
    with pytest.raises(JobRefusedError) as refused:
        load_job(pointed('{{java}}((String)globalMap.get("p")).substring(1)'))
    assert [(refusal.key, refusal.reason) for refusal in refused.value.report] == [
        ("filepath", "Java expressions are not run by v2; rewrite it in Python")]


def test_marked_reference_to_an_entry_that_is_not_there_fails_the_job_and_names_it(tmp_path):
    result, out = ran(tmp_path, pointed('{{java}}((String)globalMap.get("nope"))'))
    assert (result.status, result.failed_component, out) == ("failed", "in", None)
    assert result.error == "globalMap has no entry 'nope'"


def test_reference_that_is_not_marked_to_an_entry_that_is_not_there_is_left_as_written(tmp_path):
    # As before v2 read such values at all: a component that reads them its own way (a die's message) still does.
    result, _ = ran(tmp_path, pointed('((String)globalMap.get("nope"))'))
    assert result.status == "failed" and "((String)globalMap.get(\"nope\"))" in result.error


def test_join_without_the_mark_and_without_an_entry_means_what_it_meant_before(tmp_path):
    # Read as an item only under the mark or when it names a globalMap entry: no value that loaded before means
    # something else now. Here the variable is put in where it stands and the rest stays as written.
    result, _ = ran(tmp_path, pointed('context.dir + "/in.csv"'))
    assert result.status == "failed" and 'sub + "/in.csv"' in result.error
