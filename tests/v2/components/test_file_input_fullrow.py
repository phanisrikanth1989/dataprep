"""Full-row file input, against v1 on the same job config and bytes."""
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import columns, flow, job, writer


def read_lines(schema="line:str", write_schema="same", type_name="FileInputFullRowComponent", **config):
    """file -> file: every line of in.txt as one column, written to out.csv."""
    made = {"filename": "in.txt", "encoding": "UTF-8"}
    made.update(config)
    source = {"id": "in", "type": type_name, "config": made,
              "schema": {"input": [], "output": columns(schema) if schema else []}, "inputs": [], "outputs": ["row1"]}
    target = writer(schema if write_schema == "same" else write_schema, inputs=("row1",), include_header=False)
    return job([source, target], [flow("row1", "in", "out")])


def same(tmp_path, data, fails=False, inputs=None, **kwargs):
    """Both engines do the same with the job; ``fails`` says the job is one neither finishes."""
    run = assert_matches_v1(read_lines(**kwargs), inputs if inputs is not None else {"in.txt": data}, tmp_path)
    assert run.succeeded is not fails, run.error
    return run


def v2(tmp_path, data, **kwargs):
    """Run on v2 only, inside tmp_path; returns (result, the folder)."""
    if data is not None:
        (tmp_path / "in.txt").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(read_lines(**kwargs)), tmp_path
    finally:
        os.chdir(previous)


def refused(**config):
    with pytest.raises(JobRefusedError) as caught:
        load_job(read_lines(**config))
    return caught.value.report.format()


# ------------------------------------------------------------------
# What a line is
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "data",
    [
        b"a\nb\nc\n",
        b"a\nb\nc",
        b"a\r\nb\r\nc\r\n",
        b"a\rb\rc\r",
        b"a\rb\nc\r\nd",
        b"a\r\r\nb\n",
        b"\r",
        b"a\n\r",
    ],
)
@pytest.mark.parametrize("remove_empty_row", [True, False])
def test_lines_end_at_lf_crlf_or_cr(tmp_path, data, remove_empty_row):
    same(tmp_path, data, remove_empty_row=remove_empty_row)


def test_a_line_is_kept_as_it_is(tmp_path):
    data = b"  two spaces\n\ttab \x01 control\n;;quote\";\n" + "caf\u00e9 \u20ac5\n".encode("utf-8")
    assert same(tmp_path, data).files["out.csv"] == data


def test_empty_lines_are_removed_and_blank_ones_kept(tmp_path):
    run = same(tmp_path, b"a\n\nb\n  \n\tc \n")
    assert run.files["out.csv"] == b"a\nb\n  \n\tc \n"


def test_empty_lines_are_kept_when_asked_and_a_final_line_end_counts_as_one(tmp_path):
    run = same(tmp_path, b"a\n\nb\n", remove_empty_row=False)
    assert run.files["out.csv"] == b"a\n\nb\n\n"


@pytest.mark.parametrize("data", [b"", b"\n", b"\n\n"])
@pytest.mark.parametrize("remove_empty_row", [True, False])
def test_file_with_no_text(tmp_path, data, remove_empty_row):
    same(tmp_path, data, remove_empty_row=remove_empty_row)


# ------------------------------------------------------------------
# Which lines are read
# ------------------------------------------------------------------

HEADED = b"h1\nh2\na\nb\nc\nf1\nf2"


@pytest.mark.parametrize(
    "config",
    [
        {"header_rows": 2},
        {"header_rows": "2"},
        {"header_rows": 2, "footer_rows": 2},
        {"header_rows": 2, "footer_rows": "1"},
        {"footer_rows": 7},
        {"footer_rows": 8},
        {"header_rows": 7},
        {"header_rows": 5, "footer_rows": 2},
        {"header_rows": 5, "footer_rows": 3},
        {"header_rows": -1, "footer_rows": -1},
        {"header_rows": "", "footer_rows": None},
        {"header_rows": 2, "footer_rows": 2, "limit": "2"},
        {"header_rows": 2, "footer_rows": 2, "limit": "9"},
    ],
)
@pytest.mark.parametrize("ending", [b"", b"\n"])
@pytest.mark.parametrize("remove_empty_row", [True, False])
def test_header_and_footer(tmp_path, config, ending, remove_empty_row):
    same(tmp_path, HEADED + ending, remove_empty_row=remove_empty_row, **config)


def test_footer_counts_the_empty_line_after_a_final_line_end(tmp_path):
    assert same(tmp_path, b"a\nb\nf\n", footer_rows=1).files["out.csv"] == b"a\nb\nf\n"
    assert same(tmp_path / "bare", b"a\nb\nf", footer_rows=1).files["out.csv"] == b"a\nb\n"


@pytest.mark.parametrize("limit", ["2", 2, " 2 ", "0", 0, "", None, "9"])
def test_limit(tmp_path, limit):
    same(tmp_path, b"a\nb\nc\nd\n", limit=limit)


@pytest.mark.parametrize("remove_empty_row", [True, False])
def test_limit_counts_the_lines_left_after_empty_ones_are_removed(tmp_path, remove_empty_row):
    same(tmp_path, b"\n\na\n\nb\nc\n", limit="2", remove_empty_row=remove_empty_row)


@pytest.mark.parametrize("limit", ["abc", "2.0"])
def test_limit_that_is_not_a_whole_number_fails_on_both(tmp_path, limit):
    same(tmp_path, b"a\nb\n", limit=limit, fails=True)
    assert "limit" in refused(limit=limit)


def test_negative_limit_reads_every_line(tmp_path):
    # v1 drops that many lines from the end: its slice takes the negative number as a position.
    result, folder = v2(tmp_path, b"a\nb\nc\nd\n", limit="-1")
    assert result.status == "success"
    assert (folder / "out.csv").read_bytes() == b"a\nb\nc\nd\n"


# ------------------------------------------------------------------
# Row separators
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "separator, data",
    [
        ("\\n", b"a\nb\r\nc\rd\n"),
        ("\n", b"a\nb\r\nc\rd\n"),
        ("\\r\\n", b"a\r\nb\r\nc\r\n"),
        ("\r\n", b"a\r\nb\r\nc"),
        ("\\r", b"a\rb\rc\r"),
        ("\r", b"a\rb\rc"),
    ],
)
@pytest.mark.parametrize("remove_empty_row", [True, False])
def test_row_separators(tmp_path, separator, data, remove_empty_row):
    same(tmp_path, data, row_separator=separator, remove_empty_row=remove_empty_row)


def test_crlf_separator_keeps_a_lone_cr_inside_the_line(tmp_path):
    run = same(tmp_path, b"a\rb\r\nc\r\n", row_separator="\\r\\n")
    assert run.files["out.csv"] == b"a\rb\nc\n"


@pytest.mark.parametrize("separator", [";", "@@", "\\t", ""])
def test_other_row_separators_are_refused(separator):
    assert "row_separator" in refused(row_separator=separator)


# ------------------------------------------------------------------
# Encodings
# ------------------------------------------------------------------

TEXT = "caf\u00e9 \u20ac5\nna\u00efve\n"


@pytest.mark.parametrize("encoding", ["UTF-8", "ISO-8859-15", "cp1252", "UTF-16", "latin1"])
def test_encodings(tmp_path, encoding):
    text = TEXT if encoding != "latin1" else "caf\u00e9\nna\u00efve\n"
    same(tmp_path, text.encode(encoding), encoding=encoding)


def test_default_encoding_is_iso_8859_15(tmp_path):
    made = read_lines()
    del made["components"][0]["config"]["encoding"]
    run = assert_matches_v1(made, {"in.txt": TEXT.encode("iso-8859-15")}, tmp_path)
    assert run.files["out.csv"] == TEXT.encode("utf-8")


def test_empty_encoding_means_the_default(tmp_path):
    same(tmp_path, TEXT.encode("iso-8859-15"), encoding="")


def test_byte_order_mark_is_text_unless_the_encoding_says_otherwise(tmp_path):
    kept = same(tmp_path, b"\xef\xbb\xbfa\nb\n", encoding="UTF-8")
    assert kept.files["out.csv"] == b"\xef\xbb\xbfa\nb\n"
    dropped = same(tmp_path / "sig", b"\xef\xbb\xbfa\nb\n", encoding="utf-8-sig")
    assert dropped.files["out.csv"] == b"a\nb\n"


def test_bytes_the_encoding_cannot_read_fail_the_reader(tmp_path):
    same(tmp_path, b"ok\ncaf\xe9\n", encoding="UTF-8", fails=True)


def test_unknown_encoding_is_refused():
    assert "encoding" in refused(encoding="NOPE-1")


# ------------------------------------------------------------------
# The column
# ------------------------------------------------------------------

def test_column_is_named_by_the_schema(tmp_path):
    made = read_lines(schema="content:str")
    made["components"][1]["config"]["include_header"] = True
    run = assert_matches_v1(made, {"in.txt": b"a\nb\n"}, tmp_path)
    assert run.files["out.csv"] == b"content\na\nb\n"


def test_column_is_named_line_without_a_schema(tmp_path):
    made = read_lines(schema=None, write_schema=None)
    made["components"][1]["config"]["include_header"] = True
    run = assert_matches_v1(made, {"in.txt": b"a\nb\n"}, tmp_path)
    assert run.files["out.csv"] == b"line\na\nb\n"


def test_further_declared_columns_are_added_empty(tmp_path):
    made = read_lines(schema="line:str, n:int, s:str")
    made["components"][1]["config"]["include_header"] = True
    run = assert_matches_v1(made, {"in.txt": b"a\nb\n"}, tmp_path)
    assert run.files["out.csv"] == b"line;n;s\na;;\nb;;\n"


def test_first_column_declared_as_a_number_is_read_as_one(tmp_path):
    same(tmp_path, b"1\n 22 \n3\n", schema="n:int")


# ------------------------------------------------------------------
# Files
# ------------------------------------------------------------------

def test_missing_file_fails_the_reader(tmp_path):
    same(tmp_path, None, inputs={}, fails=True)
    (tmp_path / "direct").mkdir()
    result, _ = v2(tmp_path / "direct", None)
    assert result.status == "failed" and result.failed_component == "in"
    assert result.error == "File not found: 'in.txt'"


def test_path_can_come_from_the_context(tmp_path):
    made = read_lines(filename="${context.dir}/context.name")
    made["context"] = {"Default": {"dir": {"value": ".", "type": "str"}, "name": {"value": "in.txt", "type": "str"}}}
    assert_matches_v1(made, {"in.txt": b"a\nb\n"}, tmp_path)


def test_path_is_not_a_pattern(tmp_path):
    made = read_lines(filename="we[i]rd*.txt")
    run = assert_matches_v1(made, {"we[i]rd*.txt": b"a\nb\n", "weird.txt": b"no\n"}, tmp_path)
    assert run.files["out.csv"] == b"a\nb\n"


def test_large_file_keeps_every_line_in_order(tmp_path):
    data = b"\r\n".join(b"line %d" % number for number in range(50000))
    run = same(tmp_path, data, header_rows=1, footer_rows=1)
    assert run.files["out.csv"] == b"".join(b"line %d\n" % number for number in range(1, 49999))


# ------------------------------------------------------------------
# What v2 says no to, and what it lets pass
# ------------------------------------------------------------------

def test_random_lines_are_refused():
    assert "random" in refused(random=True)
    load_job(read_lines(random=False, nb_random=10))


def test_unknown_key_is_refused():
    assert "bogus" in refused(bogus=1)
    assert "filepath" in refused(filepath="in.txt")


def test_path_is_required():
    made = read_lines()
    del made["components"][0]["config"]["filename"]
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    assert "path" in caught.value.report.format()


@pytest.mark.parametrize(
    "type_name", ["FileInputFullRowComponent", "FileInputFullRow", "tFileInputFullRow", "file_input_full_row"]
)
def test_type_names(tmp_path, type_name):
    result, folder = v2(tmp_path, b"a\nb\n", type_name=type_name)
    assert result.status == "success"
    assert (folder / "out.csv").read_bytes() == b"a\nb\n"


def test_v2_spelling_of_the_path(tmp_path):
    made = read_lines()
    made["components"][0]["config"]["path"] = made["components"][0]["config"].pop("filename")
    load_job(made)


def test_every_key_the_converter_writes_is_accepted():
    load_job(read_lines(
        filename="in.txt", row_separator="\\n", header_rows=0, footer_rows=0, limit="", remove_empty_row=True,
        encoding="ISO-8859-15", random=False, nb_random=10, tstatcatcher_stats=False, label="",
    ))
