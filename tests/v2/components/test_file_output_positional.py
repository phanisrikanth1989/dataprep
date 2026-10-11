"""Positional output: against v1 where v1 does what Talend does, and to Talend's own rule where it does not."""
import os
import zipfile

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2 import answer_key

from .kit import columns, flow, job, reader

SCHEMA = "id:int, name:str"
DATA = b"id;name\n1;ab\n22;abcdefgh\n333;abc\n"


def positional(formats, schema=SCHEMA, kind="FileOutputPositional", **config):
    """file -> positional output, which writes out.txt."""
    sink = {"id": "out", "type": kind, "config": {"filepath": "out.txt", "formats": formats, **config},
            "schema": {"input": columns(schema), "output": []}, "inputs": ["row1"], "outputs": []}
    return job([reader(schema, header_rows=1), sink], [flow("row1", "in", "out")])


def field(column, size, pad=" ", align="L", keep="A"):
    return {"schema_column": column, "size": str(size), "padding_char": pad, "align": align, "keep": keep}


def on_both(tmp_path, made, data=DATA, files=None):
    """Both engines leave the same files. Returns out.txt, None when there is none."""
    inputs = {"in.csv": data, **(files or {})}
    key = answer_key.run_job(made, inputs, tmp_path / "v1", answer_key.run_v1)
    run = answer_key.run_job(made, inputs, tmp_path / "v2", answer_key.run_v2)
    assert key.succeeded and run.succeeded, (key.error, run.error)
    assert run.files == key.files
    return run.files.get("out.txt")


def v2(tmp_path, made, data=DATA, files=None):
    """Run on v2 alone, inside tmp_path; returns how it ended and out.txt, None when there is none."""
    (tmp_path / "in.csv").write_bytes(data)
    for name, held in (files or {}).items():
        (tmp_path / name).write_bytes(held)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    written = tmp_path / "out.txt"
    return result, written.read_bytes() if written.exists() else None


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# Padded and cut, as v1 and Talend both have it
# ------------------------------------------------------------------

@pytest.mark.parametrize("align, written", [
    ("L", b"10000ab***\n22000abcdefgh\n33300abc**\n"),
    ("R", b"00001***ab\n00022abcdefgh\n00333**abc\n"),
])
def test_value_shorter_than_its_size_is_padded_and_a_longer_one_is_kept_whole(tmp_path, align, written):
    formats = [field("id", 5, "0", align), field("name", 5, "*", align)]
    assert on_both(tmp_path, positional(formats)) == written


@pytest.mark.parametrize("keep, kept", [("A", b"abcdefgh"), ("L", b"abcde"), ("M", b"bcdef"), ("R", b"defgh")])
def test_what_is_kept_of_a_value_longer_than_its_size(tmp_path, keep, kept):
    formats = [field("id", 3, " ", "R", keep), field("name", 5, "*", "L", keep)]
    assert on_both(tmp_path, positional(formats)) == b"  1ab***\n 22" + kept + b"\n333abc**\n"


def test_middle_of_a_value_whose_surplus_is_odd(tmp_path):
    made = positional([field("name", 4, " ", "L", "M")])
    assert on_both(tmp_path, made, b"id;name\n1;abcde\n2;abcdefg\n3;abcd\n") == b"abcd\nbcde\nabcd\n"


def test_centred_where_the_padding_divides_evenly_or_the_size_is_even(tmp_path):
    made = positional([field("name", 6, "-", "C"), field("id", 4, "-", "C")])
    data = b"id;name\n1;a\n22;ab\n333;abc\n4444;abcd\n55555;abcde\n"
    assert on_both(tmp_path, made, data) == b"--a----1--\n--ab---22-\n-abc--333-\n-abcd-4444\nabcde-55555\n"


def test_centred_with_one_pad_too_many_has_it_on_the_right_as_in_talend(tmp_path):
    # v1 has it on the left when the size is odd: **ab*.
    result, written = v2(tmp_path, positional([field("name", 5, "*", "C"), field("id", 3, "0", "C")]))
    assert result.status == "success" and written == b"*ab**010\nabcdefgh220\n*abc*333\n"
    # The column names too: "id" in five is *id**.
    (tmp_path / "b").mkdir()
    made = positional([field("id", 5, "*", "C"), field("name", 7, "-", "C")], include_header=True)
    result, written = v2(tmp_path / "b", made, b"id;name\n1;ab\n")
    assert result.status == "success" and written == b"*id**-name--\n**1**--ab---\n"


def test_header_is_the_column_names_padded_like_the_values(tmp_path):
    formats = [field("id", 5, "0", "R"), field("name", 6, "*", "L")]
    assert on_both(tmp_path, positional(formats, include_header=True)) == (
        b"000idname**\n00001ab****\n00022abcdefgh\n00333abc***\n")


@pytest.mark.parametrize("keep, name", [("A", b"name"), ("L", b"nam"), ("M", b"nam"), ("R", b"ame")])
def test_column_name_longer_than_its_size_is_kept_as_a_value_would_be(tmp_path, keep, name):
    # v1 cuts it to the size whatever is to be kept.
    made = positional([field("id", 3), field("name", 3, " ", "L", keep)], include_header=True)
    result, written = v2(tmp_path, made, b"id;name\n1;ab\n")
    assert result.status == "success" and written == b"id " + name + b"\n1  ab \n"


@pytest.mark.parametrize("keep, name", [("A", b"name"), ("L", b"na"), ("M", b"am"), ("R", b"me")])
def test_middle_of_a_column_name_is_its_middle(tmp_path, keep, name):
    made = positional([field("name", 2, " ", "L", keep)], include_header=True)
    result, written = v2(tmp_path, made, b"id;name\n1;ab\n")
    assert result.status == "success" and written == name + b"\nab\n"


def test_column_name_is_written_in_the_files_encoding(tmp_path):
    made = positional([field("prénom", 8, ".", "R")], schema="id:int, prénom:str", include_header=True)
    assert on_both(tmp_path, made, "id;prénom\n1;zoé\n".encode("utf-8")) == "..prénom\n.....zoé\n".encode("iso-8859-15")


def test_missing_value_is_all_padding_and_a_column_that_does_not_arrive_too(tmp_path):
    formats = [field("id", 3), field("nope", 3, "."), field("name", 3, "_")]
    assert on_both(tmp_path, positional(formats), b"id;name\n1;ab\n3;\n") == b"1  ...ab_\n3  ...___\n"


def test_columns_are_written_in_the_order_of_formats_and_only_those(tmp_path):
    assert on_both(tmp_path, positional([field("name", 4)])) == b"ab  \nabcdefgh\nabc \n"
    assert on_both(tmp_path / "b", positional([field("name", 4), field("id", 3), field("name", 2)])) == (
        b"ab  1  ab\nabcdefgh22 abcdefgh\nabc 333abc\n")


def test_padding_in_quotes_or_left_out_and_keys_in_capitals(tmp_path):
    formats = [field("id", 3, "'x'"), field("name", 3, "")]
    assert on_both(tmp_path, positional(formats)) == b"1xxab \n22xabcdefgh\n333abc\n"
    formats = [{"SCHEMA_COLUMN": "id", "SIZE": "3"}, {"schema_column": "name", "size": 4, "align": "right", "keep": "c"}]
    assert on_both(tmp_path / "b", positional(formats)) == b"1    ab\n22 abcd\n333 abc\n"


@pytest.mark.parametrize("separator, written", [("\\r\\n", b"1  ab \r\n"), ("|", b"1  ab |"), ("\\t", b"1  ab \t")])
def test_row_separator(tmp_path, separator, written):
    made = positional([field("id", 3), field("name", 3)], row_separator=separator)
    assert on_both(tmp_path, made, b"id;name\n1;ab\n") == written


def test_encoding(tmp_path):
    data = "id;name\n1;é€\n".encode("utf-8")
    assert on_both(tmp_path, positional([field("name", 4)]), data) == "é€  \n".encode("iso-8859-15")
    assert on_both(tmp_path / "b", positional([field("name", 4)], encoding="UTF-8"), data) == "é€  \n".encode("utf-8")


def test_size_counts_characters(tmp_path):
    made = positional([field("name", 3, " ", "L", "L")], encoding="UTF-8")
    assert on_both(tmp_path, made, "id;name\n1;é\n2;日本語です\n".encode("utf-8")) == "é  \n日本語\n".encode("utf-8")


# ------------------------------------------------------------------
# What a value is written as
# ------------------------------------------------------------------

TYPED = "id:int, amt:float, m:Decimal#2, plain:Decimal, ok:bool, day:datetime@%d/%m/%Y, at:datetime"
TYPED_DATA = (b"id;amt;m;plain;ok;day;at\n"
              b"1;1.5;2.5;3.25;true;31/01/2024;2024-01-31 10:11:12\n"
              b"22;2;13.255;4;false;01/02/2024;2024-02-01\n"
              b"3;;;;;;\n")


def test_every_type_is_written_as_talend_writes_it(tmp_path):
    # v1 fails on this job. Talend: a float as it prints, a Decimal to its declared places, true and false, a
    # date by its pattern (tFileOutputPositional_begin.javajet, lines 473 to 495).
    formats = [field("id", 3, " ", "R"), field("amt", 5), field("m", 7, " ", "R"), field("plain", 5), field("ok", 6),
               field("day", 11), field("at", 20)]
    result, written = v2(tmp_path, positional(formats, TYPED), TYPED_DATA)
    assert result.status == "success", result.error
    assert written.decode().splitlines() == [
        "  11.5     2.503.25 true  31/01/2024 2024-01-31 10:11:12 ",
        " 222.0    13.264    false 01/02/2024 2024-02-01 00:00:00 ",
        # True or false with nothing written is false, as for every reader.
        "  3" + " " * 17 + "false" + " " * 32,
    ]


def test_whole_number_column_with_a_missing_value_stays_whole(tmp_path):
    # v1 fails on a missing whole number ("Invalid value '' for dtype 'Int64'").
    result, written = v2(tmp_path, positional([field("id", 4, "0", "R")]), b"id;name\n7;a\n;b\n")
    assert result.status == "success" and written == b"0007\n0000\n"


# ------------------------------------------------------------------
# The file
# ------------------------------------------------------------------

TWO = [field("id", 3), field("name", 3)]


def test_file_that_is_there_is_replaced_or_added_to(tmp_path):
    there = {"out.txt": b"old\n"}
    assert on_both(tmp_path, positional(TWO), files=there) == b"1  ab \n22 abcdefgh\n333abc\n"
    assert on_both(tmp_path / "b", positional(TWO, append=True), files=there) == b"old\n1  ab \n22 abcdefgh\n333abc\n"
    assert on_both(tmp_path / "c", positional(TWO, append=True)) == b"1  ab \n22 abcdefgh\n333abc\n"


def test_header_goes_into_a_new_or_empty_file_only_as_in_talend(tmp_path):
    # v1 writes it again under what is there.
    made = positional(TWO, append=True, include_header=True)
    result, written = v2(tmp_path, made, b"id;name\n1;ab\n", files={"out.txt": b"old\n"})
    assert result.status == "success" and written == b"old\n1  ab \n"
    (tmp_path / "b").mkdir()
    result, written = v2(tmp_path / "b", made, b"id;name\n1;ab\n", files={"out.txt": b""})
    assert written == b"id name\n1  ab \n"
    assert on_both(tmp_path / "c", positional([field("id", 3), field("name", 4)], append=True, include_header=True),
                   b"id;name\n1;ab\n") == b"id name\n1  ab  \n"


def test_no_rows_leave_an_empty_file_or_its_header_as_in_talend(tmp_path):
    # v1 touches no file when there is no row and no header to write: one that is there stays as it was.
    result, written = v2(tmp_path, positional(TWO), b"id;name\n", files={"out.txt": b"old\n"})
    assert result.status == "success" and written == b""
    assert on_both(tmp_path / "b", positional([field("id", 3), field("name", 4)], include_header=True), b"id;name\n") == (
        b"id name\n")


def test_no_rows_leave_no_file_when_asked_and_a_file_that_is_added_to_stays(tmp_path):
    made = positional(TWO, delete_empty_file=True, include_header=True)
    assert on_both(tmp_path, made, b"id;name\n") is None
    on_both(tmp_path / "b", made, b"id;name\n", files={"out.txt": b"old\n"})
    assert not (tmp_path / "b" / "v2" / "out.txt").exists() and not (tmp_path / "b" / "v1" / "out.txt").exists()
    made = positional(TWO, delete_empty_file=True, append=True)
    on_both(tmp_path / "c", made, b"id;name\n", files={"out.txt": b"old\n"})
    assert (tmp_path / "c" / "v2" / "out.txt").read_bytes() == b"old\n"


def test_folder_that_is_not_there_is_made_or_fails_the_job(tmp_path):
    made = positional(TWO, filepath="deep/er/out.txt")
    files = answer_key.run_job(made, {"in.csv": DATA}, tmp_path / "v2", answer_key.run_v2).files
    assert files == {"deep/er/out.txt": b"1  ab \n22 abcdefgh\n333abc\n"}
    result, _ = v2(tmp_path, positional(TWO, filepath="deep/out.txt", create=False))
    assert result.status == "failed" and result.error == "Failed to write file 'deep/out.txt': folder 'deep' does not exist"


def test_compressed_is_a_zip_beside_the_name_as_in_talend(tmp_path):
    # v1 writes gzip under the file's own name.
    made = positional(TWO, filepath="out.txt", compress=True, include_header=True)
    result, written = v2(tmp_path, made)
    assert result.status == "success" and written is None
    with zipfile.ZipFile(tmp_path / "out.zip") as held:
        assert held.namelist() == ["out.txt"]
        assert held.read("out.txt") == b"id nam\n1  ab \n22 abcdefgh\n333abc\n".replace(b"nam\n", b"name\n")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["in.csv", "out.zip"]


def test_compressed_file_with_no_extension_or_in_a_folder_with_a_dot(tmp_path):
    result, _ = v2(tmp_path, positional(TWO, filepath="d.ir/out", compress=True))
    assert result.status == "success" and zipfile.ZipFile(tmp_path / "d.ir" / "out.zip").namelist() == ["out"]


def test_adding_to_a_file_is_never_compressed_as_in_talend(tmp_path):
    result, written = v2(tmp_path, positional(TWO, compress=True, append=True), files={"out.txt": b"old\n"})
    assert result.status == "success" and written == b"old\n1  ab \n22 abcdefgh\n333abc\n"
    assert not (tmp_path / "out.zip").exists()


def test_character_the_encoding_cannot_write_fails_the_job_and_leaves_the_file(tmp_path):
    result, written = v2(tmp_path, positional(TWO), "id;name\n1;日本\n".encode("utf-8"), files={"out.txt": b"old\n"})
    assert result.status == "failed" and written == b"old\n"
    assert result.error == "'\\u65e5\\u672c' cannot be written in the file's encoding"


def test_rows_written_are_counted(tmp_path):
    made = dict(positional(TWO, include_header=True), run={"row_counts": True})
    result, _ = v2(tmp_path, made)
    assert result.status == "success" and result.rows == {"out": 3}
    assert result.counts["out"] == {"NB_LINE": 3, "NB_LINE_OK": 3, "NB_LINE_REJECT": 0}


# ------------------------------------------------------------------
# What is refused
# ------------------------------------------------------------------

@pytest.mark.parametrize("config, key, said", [
    ({"formats": []}, "formats", None),
    ({"formats": [field("id", 0)]}, "formats[0].size", "0 is no width: give 1 or more"),
    ({"formats": [field("id", "wide")]}, "formats[0].size", "'wide' is no width: give a whole number, 1 or more"),
    ({"formats": [field("id", 3, "ab")]}, "formats[0].padding_char", "'ab' is 2 characters, and a value is padded with one"),
    ({"formats": [field("id", 3, " ", "X")]}, "formats[0].align", None),
    ({"formats": [field("id", 3, " ", "L", "Z")]}, "formats[0].keep", None),
    ({"formats": [{"size": 3}]}, "formats[0].schema_column", None),
    ({"formats": [{"schema_column": "id"}]}, "formats[0].size", None),
    ({"use_byte": True}, "use_byte", None),
    ({"usestream": True}, "usestream", None),
    ({"use_existing_dynamic": True}, "use_existing_dynamic", None),
    ({"filepath": ""}, "path", "the file to write has no name"),
    ({"nope": 1}, "nope", None),
])
def test_what_cannot_be_done_refuses_the_job(config, key, said):
    made = positional(**{"formats": TWO, **config})
    found = refusals(made)
    assert [path for path, _ in found] == [key]
    assert said is None or found[0][1] == said


def test_keys_that_change_nothing(tmp_path):
    unread = dict(flushonrow=True, flushonrow_num="10", row_mode=True, streamname="outputStream", dynamic="",
                  advanced_separator=True, thousands_separator=".", decimal_separator=",", use_byte=False,
                  usestream=False, use_existing_dynamic=False)
    assert on_both(tmp_path, positional(TWO, **unread)) == on_both(tmp_path / "b", positional(TWO))


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("file_output_positional", "FileOutputPositional", "tFileOutputPositional")):
        (tmp_path / str(at)).mkdir()
        result, written = v2(tmp_path / str(at), positional(TWO, kind=kind))
        assert result.status == "success" and written.startswith(b"1  ab \n")


# ------------------------------------------------------------------
# What an independent review found (ticket 71)
# ------------------------------------------------------------------

def test_every_row_is_written_also_when_no_column_of_formats_arrives(tmp_path):
    made = positional([field("NAME", 4, "."), field("nope", 2, "-")])
    assert on_both(tmp_path, made, b"id;name\n1;ab\n2;cd\n3;ef\n") == b"....--\n" * 3
    (tmp_path / "b").mkdir()
    result, written = v2(tmp_path / "b", dict(made, run={"row_counts": True}), b"id;name\n1;ab\n2;cd\n3;ef\n")
    assert result.counts["out"]["NB_LINE"] == 3
    (tmp_path / "c").mkdir()
    result, written = v2(tmp_path / "c", made, b"id;name\n")
    assert result.status == "success" and written == b""


def test_fit_given_as_nothing_is_the_default(tmp_path):
    formats = [{"schema_column": "name", "size": 4, "align": None, "keep": None, "padding_char": None}]
    assert on_both(tmp_path, positional(formats)) == b"ab  \nabcdefgh\nabc \n"


def test_value_that_holds_a_quote_or_a_comma_is_written_as_it_is(tmp_path):
    data = b'id;name\n1;a"b\n2;c,d\n3;"q"\n'
    assert on_both(tmp_path, positional([field("name", 5, "_")]), data) == b'a"b__\nc,d__\n"q"__\n'


def test_zip_of_a_file_in_an_encoding_with_a_byte_order_mark(tmp_path):
    made = positional(TWO, compress=True, include_header=True, encoding="UTF-16")
    result, _ = v2(tmp_path, made, b"id;name\n1;ab\n")
    assert result.status == "success", result.error
    with zipfile.ZipFile(tmp_path / "out.zip") as held:
        assert held.read("out.txt") == "id name\n1  ab \n".encode("utf-16")


def test_two_outputs_of_one_subjob_add_to_one_file(tmp_path):
    made = positional(TWO, append=True)
    second = dict(made["components"][1], id="out2", inputs=["row2"])
    made["components"][0]["outputs"] = ["row1", "row2"]
    made["components"].append(second)
    made["flows"].append(flow("row2", "in", "out2"))
    assert on_both(tmp_path, made, b"id;name\n1;ab\n") == b"1  ab \n1  ab \n"


def test_trace_shows_a_row_as_the_file_holds_it(tmp_path):
    made = dict(positional([field("id", 3, "0", "R"), field("name", 4, " ", "L", "L"), field("id", 5, "*")]),
                run={"only": {"source": "in", "where": {"id": [22]}}, "trace": True})
    result, written = v2(tmp_path, made)
    assert result.status == "success" and written == b"022abcd22***\n"
    entry = [entry for entry in result.summary()["trace"] if entry["id"] == "out"][0]
    assert entry["data"] == [["022", "abcd"]]
