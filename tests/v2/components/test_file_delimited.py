"""Delimited file input and output, against v1 on the same job config and bytes."""
import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import flow, job, reader, writer


def copy(schema, read=None, write=None, write_schema="same", reject_schema=None):
    """file -> file, optionally with the reader's reject output written to rej.csv."""
    components = [reader(schema, **(read or {})),
                  writer(schema if write_schema == "same" else write_schema, inputs=("row1",), **(write or {}))]
    flows = [flow("row1", "in", "out")]
    if reject_schema is not None:
        components[0]["outputs"].append("bad")
        components.append(writer(None, component_id="rej", path="rej.csv", inputs=("bad",)))
        flows.append(flow("bad", "in", "rej", "reject"))
    return job(components, flows)


def same(tmp_path, data, schema, fails=False, **kwargs):
    """Both engines do the same with the job; ``fails`` says the job is one neither finishes."""
    inputs = kwargs.pop("inputs", None) or {"in.csv": data}
    run = assert_matches_v1(copy(schema, **kwargs), inputs, tmp_path)
    assert run.succeeded is not fails, run.error
    return run


def v2(tmp_path, data, schema, **kwargs):
    """Run on v2 only, inside tmp_path; returns (result, the folder)."""
    import os

    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(copy(schema, **kwargs)), tmp_path
    finally:
        os.chdir(previous)


ALL_TYPES = "s:str, i:int, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2"

# ------------------------------------------------------------------
# Types, read and written back
# ------------------------------------------------------------------

def test_every_type_round_trips(tmp_path):
    run = same(tmp_path, b"a;1;1.5;true;2024-01-31;12.345\nb;-2;30200.00;false;1999-12-31;7\n", ALL_TYPES)
    assert run.files["out.csv"] == b"s;i;f;b;d;m\na;1;1.5;true;2024-01-31;12.35\nb;-2;30200.0;false;1999-12-31;7.00\n"


def test_empty_fields_of_every_type(tmp_path):
    run = same(tmp_path, b";;;;;y\n", "i:int, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2, s:str")
    assert run.files["out.csv"] == b"i;f;b;d;m;s\n;;false;;;y\n"


@pytest.mark.parametrize("text", "true false 1 0 yes no True False Yes No YES NO".split())
def test_bool_spellings(tmp_path, text):
    same(tmp_path, f"1;{text}\n".encode(), "k:str, v:bool")


@pytest.mark.parametrize(
    "pattern, text",
    [
        ("%d/%m/%Y", "31/01/2024"),
        ("%Y-%m-%d %H:%M:%S", "2024-01-31 10:11:12"),
        ("%Y-%m-%d %H:%M:%S.%f", "2024-01-31 10:11:12.123"),
        ("%d-%b-%Y", "01-FEB-2024"),
        ("%Y%m%d", "20240131"),
        ("%m/%d/%y", "01/31/24"),
        ("%Y-%m-%d", "2024-1-5"),
    ],
)
def test_date_patterns(tmp_path, pattern, text):
    same(tmp_path, f"1;{text}\n2;\n".encode(), f"k:str, v:datetime@{pattern}")


@pytest.mark.parametrize("text", ["1", "1.0", "+5", " 7 ", "007", "1e5", "-0", "1234567890123456789"])
def test_whole_numbers(tmp_path, text):
    same(tmp_path, f"x;{text}\ny;2\n".encode(), "k:str, v:int")


@pytest.mark.parametrize(
    "text", ["1", "1.50", "30200.00", "1e5", "+5", " 7 ", "007", "0.1", "2.50", "1e15", "1e16", "1e22", "0.0001", "inf", "-inf"],
)
def test_floats(tmp_path, text):
    same(tmp_path, f"x;{text}\ny;2.5\n".encode(), "k:str, v:float")


def test_float_that_is_not_a_number_is_written_empty(tmp_path):
    same(tmp_path, b"x;NaN\ny;2.5\n", "k:str, v:float")


@pytest.mark.parametrize("places, text", [(0, "0.5"), (0, "1.5"), (0, "2.5"), (2, "1.005"), (2, "2.675"), (2, "1.234567")])
def test_float_rounded_to_declared_places(tmp_path, places, text):
    same(tmp_path, f"x;{text}\n".encode(), f"k:str, v:float#{places}")


@pytest.mark.parametrize("places", [0, 2, 4])
def test_decimal_rounded_to_declared_places(tmp_path, places):
    data = b"a;1.005\nb;2.675\nc;-1.005\nd;1e5\ne;100\nf;1.50\ng;0.5\nh;2.5\ni;\n"
    same(tmp_path, data, f"k:str, v:Decimal#{places}")


def test_decimal_without_declared_places_drops_trailing_zeros(tmp_path):
    same(tmp_path, b"a;1.50\nb;0.00\nc;100\nd;30200.00\ne;7.125\n", "k:str, v:Decimal")


def test_text_is_never_missing(tmp_path):
    same(tmp_path, b"1;\n2;   \n3;NaN\n4;null\n5;NA\n6;None\n", "k:int, v:str")


# ------------------------------------------------------------------
# What the writer declares decides the text
# ------------------------------------------------------------------

def test_writer_that_declares_nothing_writes_python_style_values(tmp_path):
    same(tmp_path, b"a;1;1.5;true;2024-01-31;12.345\n", ALL_TYPES, write_schema=None)


def test_writer_date_pattern_decides_the_text(tmp_path):
    same(tmp_path, b"1;2024-01-31\n", "k:int, v:datetime@%Y-%m-%d", write_schema="k:int, v:datetime@%d/%m/%Y %H:%M:%S")


def test_writer_without_a_date_pattern(tmp_path):
    same(tmp_path, b"1;2024-01-31 10:11:12\n2;2024-01-31 00:00:00\n", "k:int, v:datetime@%Y-%m-%d %H:%M:%S",
         write_schema="k:int, v:datetime")


def test_writer_decimal_places_decide_the_text(tmp_path):
    same(tmp_path, b"1;1.01\n2;7.00\n", "k:int, v:Decimal#2", write_schema="k:int, v:Decimal#4")
    same(tmp_path / "b", b"1;1.01\n2;7.00\n3;30200.00\n", "k:int, v:Decimal#2", write_schema="k:int, v:Decimal")


def test_writer_schema_never_reorders_or_drops_columns(tmp_path):
    same(tmp_path, b"1;a;2.5\n", "k:int, s:str, f:float", write_schema="f:float, k:int")


# ------------------------------------------------------------------
# Rows that cannot be read
# ------------------------------------------------------------------

BAD = b"1;alice;2024-01-31;10.5\nx2;bob;2024-02-01;20\n3;carol;notadate;30\n4;dave;2024-03-01;\n5;erin;2024-03-02;1,5\n"
BAD_SCHEMA = "id:int, name:str, d:datetime@%Y-%m-%d, amt:float"


def test_unreadable_rows_leave_by_reject_with_the_reason(tmp_path):
    run = same(tmp_path, BAD, BAD_SCHEMA, reject_schema=True)
    assert run.files["rej.csv"].splitlines()[1] == (
        b"x2;bob;2024-02-01;20;TYPE_CONVERSION;Column 'id': could not convert string to float: 'x2'"
    )


def test_unreadable_rows_are_dropped_when_no_reject_is_wired(tmp_path):
    same(tmp_path, BAD, BAD_SCHEMA)


def test_unreadable_row_fails_the_job_when_errors_are_fatal(tmp_path):
    same(tmp_path, BAD, BAD_SCHEMA, read={"die_on_error": True}, fails=True)
    (tmp_path / "direct").mkdir()
    result, folder = v2(tmp_path / "direct", BAD, BAD_SCHEMA, read={"die_on_error": True})
    assert result.status == "failed" and result.failed_component == "in"
    assert result.error == (
        "Schema/coercion failed for 3 row(s); first error: Column 'id': could not convert string to float: 'x2'"
    )
    assert not (folder / "out.csv").exists()


def test_only_the_first_unreadable_column_of_a_row_is_named(tmp_path):
    same(tmp_path, b"x;a;notadate;zz\n1;b;2024-01-01;1\n", BAD_SCHEMA, reject_schema=True)


def test_missing_value_where_none_is_allowed_is_rejected(tmp_path):
    run = same(tmp_path, b"1;1.5;a\n2;;b\n3;2.5;c\n", "k:int, v:float!, s:str", reject_schema=True)
    assert run.files["rej.csv"].splitlines()[1] == b"2;;b;SCHEMA_VIOLATION;Column 'v': non-nullable column has null"


def test_missing_value_where_none_is_allowed_fails_when_errors_are_fatal(tmp_path):
    same(tmp_path, b"1;1.5\n2;\n", "k:int, v:float!", read={"die_on_error": True}, fails=True)


def test_clean_file_with_a_reject_output_writes_an_empty_reject_file(tmp_path):
    # v1 stalls here (status "error") because the reject flow got nothing.
    result, folder = v2(tmp_path, b"1;alice;2024-01-31;10.5\n", BAD_SCHEMA, reject_schema=True)
    assert result.status == "success"
    assert (folder / "rej.csv").read_bytes() == b"id;name;d;amt;errorCode;errorMessage\n"
    assert (folder / "out.csv").read_bytes() == b"id;name;d;amt\n1;alice;2024-01-31;10.5\n"


def test_missing_file_fails_the_reader(tmp_path):
    (tmp_path / "v").mkdir()
    result, _ = v2(tmp_path / "v", b"", "k:int", read={"filepath": "nope.csv"})
    assert result.status == "failed" and result.failed_component == "in"
    assert result.error == "File not found: 'nope.csv'"


# ------------------------------------------------------------------
# Which rows are read
# ------------------------------------------------------------------

HEADED = b"h1;h2;h3\nH1;H2;H3\n1;x;z\n2;p;q\n3;r;s\nf1;f2;f3\n"


@pytest.mark.parametrize(
    "config",
    [
        {"header_rows": 2, "footer_rows": 1},
        {"header_rows": "2", "footer_rows": 1, "limit": "2"},
        {"header_rows": 2, "footer_rows": 1, "limit": 0},
        {"header_rows": 2, "footer_rows": 1, "limit": "-1"},
        {"header_rows": 2, "footer_rows": 1, "limit": ""},
        {"header_rows": 2, "footer_rows": 2},
        {"header_rows": 10},
        {"header_rows": 2, "footer_rows": 10},
    ],
)
def test_header_footer_and_limit(tmp_path, config):
    same(tmp_path, HEADED, "a:str, b:str, c:str", read=config)


def test_last_line_without_a_newline_is_read_and_can_be_the_footer(tmp_path):
    same(tmp_path, b"1;x\n2;y", "a:int, b:str")
    same(tmp_path / "f", b"1;x\n2;y\nf;f", "a:int, b:str", read={"footer_rows": 1})


@pytest.mark.parametrize("data", [b"", b"h;h\n"])
def test_file_with_no_data_rows(tmp_path, data):
    same(tmp_path, data, "a:int, b:str", read={"header_rows": 1})


def test_empty_rows_are_removed(tmp_path):
    same(tmp_path, b"1;x;1.5\n\n;;\n  ; ;\t\n \n2;p;2.5\n", "a:int, b:str, c:float")


def test_rows_of_empty_fields_are_kept_when_asked(tmp_path):
    same(tmp_path, b"1;x;1.5\n;;\n2;p;2.5\n", "a:int, b:str, c:float", read={"remove_empty_row": False})


@pytest.mark.parametrize(
    "config",
    [
        {"trim_all": False},
        {"trim_all": True},
        {"trim_select": [{"column": "b", "trim": True}, {"column": "a", "trim": False}]},
        {"trim_select": [{"column": "nope", "trim": True}]},
        {"trim_all": True, "trim_select": [{"column": "b", "trim": False}]},
    ],
)
def test_trimming(tmp_path, config):
    same(tmp_path, b" 1 ; x y ;  2.5 \n2;\tp\t;3\n3;   ;4\n", "a:int, b:str, c:float", read=config)


def test_short_rows_are_filled_and_extra_fields_dropped(tmp_path):
    same(tmp_path, b"1;x;1.5\n2;y\n3;z;3.5\n", "a:int, b:str, c:float")
    same(tmp_path / "wide", b"1;x;1.5;EXTRA\n2;y;2.5;MORE\n", "a:int, b:str, c:float")
    same(tmp_path / "narrow", b"1;x\n2;y\n", "a:int, b:str, c:float")


def test_column_names_come_from_the_schema_by_position(tmp_path):
    same(tmp_path, b"h1;h2\n1;alice\n", "name:str, id:str", read={"header_rows": 1})


# ------------------------------------------------------------------
# Separators, quotes, line ends
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "separator, data",
    [("\\t", b"1\tx\tz\n"), (",", b"1,x,z\n"), ("|", b"1|x|z\n"), ("||", b"1||x|y||z\n2||p||q\n"), (".*", b"1.*x.*z\n")],
)
def test_field_separators(tmp_path, separator, data):
    config = {"fieldseparator": separator}
    same(tmp_path, data, "a:int, b:str, c:str", read=config, write=config)


@pytest.mark.parametrize(
    "config",
    [{"header_rows": 1, "footer_rows": 1}, {"header_rows": 1, "limit": 2}, {"footer_rows": 2, "limit": 5},
     {"header_rows": 9}, {"footer_rows": 9}],
)
def test_header_footer_and_limit_with_a_separator_of_several_characters(tmp_path, config):
    data = b"h||h||h\n1||x||a\n2||y||b\n3||z||c\nf||f||f\n"
    read = dict(config, fieldseparator="||")
    same(tmp_path, data, "a:str, b:str, c:str", read=read, write={"fieldseparator": "||"})


def test_plain_ascii_in_the_default_encoding_is_read_and_written_in_place(tmp_path):
    made = copy("a:int, b:str")
    del made["components"][0]["config"]["encoding"]
    del made["components"][1]["config"]["encoding"]
    run = assert_matches_v1(made, {"in.csv": b"1;plain\n2;ascii\n"}, tmp_path)
    assert run.files["out.csv"] == b"a;b\n1;plain\n2;ascii\n"


def test_quotes_are_data_unless_csv_is_asked_for(tmp_path):
    same(tmp_path, b'1;"x";z\n2;say "hi";q\n3;"";""\n', "a:int, b:str, c:str")


@pytest.mark.parametrize("write_csv", [False, True])
def test_csv_fields_are_unquoted_on_read(tmp_path, write_csv):
    data = b'1;"x;y";z\n2;"say ""hi""";q\n3;"";""\n4;"l1\nl2";w\n'
    same(tmp_path, data, "a:int, b:str, c:str", read={"csv_option": True, "csv_row_separator": "\\n"},
         write={"csv_option": write_csv})


def test_csv_with_another_enclosure(tmp_path):
    config = {"csv_option": True, "text_enclosure": "'", "escape_char": "'"}
    same(tmp_path, b"1;'x;y';'it''s'\n2;\"dq\";z\n", "a:int, b:str, c:str", read=config, write=config)


def test_csv_output_quotes_every_field(tmp_path):
    same(tmp_path, b"a;1;1.5;true;2024-01-31;12.345\n;;;;;\n", ALL_TYPES, write={"csv_option": True})


@pytest.mark.parametrize("data", [b"1;x\r\n2;y\r\n", b"1;x\n2;y\n"])
@pytest.mark.parametrize("separator", ["\\n", "\\r\\n"])
def test_lines_ending_in_lf_or_crlf(tmp_path, data, separator):
    same(tmp_path, data, "a:int, b:str", read={"row_separator": separator})


def test_lines_ending_in_cr(tmp_path):
    same(tmp_path, b"1;x\r2;y\r", "a:int, b:str", read={"row_separator": "\\r"})


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"os_line_separator": True, "row_separator": "\\r\\n"},
        {"os_line_separator": False, "row_separator": "\\n"},
        {"os_line_separator": False, "row_separator": "\\r\\n"},
        {"os_line_separator": False, "row_separator": "\\r"},
        {"os_line_separator": False, "row_separator": "@@"},
        {"os_line_separator": False, "csv_option": True, "csvrowseparator": "CRLF"},
        {"os_line_separator": False, "csv_option": True, "csvrowseparator": "CR"},
        {"os_line_separator": False, "csv_option": True, "csvrowseparator": "LF"},
        {"os_line_separator": False, "csv_option": True, "csvrowseparator": "\\r\\n"},
        {"os_line_separator": False, "csv_option": True, "row_separator": "@@"},
        {"os_line_separator": False, "csvrowseparator": "CRLF"},
    ],
)
def test_line_ends_on_write(tmp_path, config):
    same(tmp_path, b"1;a\n2;b\n", "id:int, name:str", write=config)


# ------------------------------------------------------------------
# Encodings
# ------------------------------------------------------------------

UTF8, LATIN9 = "café;€5\n".encode("utf-8"), "café;€5\n".encode("iso-8859-15")


@pytest.mark.parametrize("read_as, data", [("UTF-8", UTF8), ("ISO-8859-15", LATIN9)])
@pytest.mark.parametrize("write_as", ["UTF-8", "ISO-8859-15"])
def test_encodings_convert(tmp_path, read_as, data, write_as):
    same(tmp_path, data, "a:str, b:str", read={"encoding": read_as}, write={"encoding": write_as})


def test_default_encoding_is_iso_8859_15_on_both_sides(tmp_path):
    made = copy("a:str, b:str")
    del made["components"][0]["config"]["encoding"]
    del made["components"][1]["config"]["encoding"]
    run = assert_matches_v1(made, {"in.csv": LATIN9}, tmp_path)
    assert run.files["out.csv"] == b"a;b\n" + LATIN9


@pytest.mark.parametrize("encoding", ["latin1", "utf8", "cp1252", "UTF-16"])
def test_other_encodings(tmp_path, encoding):
    data = "café;x\nnaïve;y\n".encode(encoding)
    same(tmp_path, data, "a:str, b:str", read={"encoding": encoding}, write={"encoding": encoding})


def test_text_the_output_encoding_cannot_hold_fails_the_writer(tmp_path):
    result, folder = v2(tmp_path, "ok;fine\n中文;x\n".encode("utf-8"), "a:str, b:str",
                        write={"encoding": "ISO-8859-15"})
    assert result.status == "failed" and result.failed_component == "out"
    assert not (folder / "out.csv").exists()


# ------------------------------------------------------------------
# Output file rules
# ------------------------------------------------------------------

@pytest.mark.parametrize("header", [True, False])
def test_header_line(tmp_path, header):
    same(tmp_path, b"1;a\n", "id:int, name:str", write={"include_header": header})


@pytest.mark.parametrize(
    "existing, config",
    [
        (None, {"append": True}),
        (b"", {"append": True}),
        (b"id;name\n9;z\n", {"append": True}),
        (b"old;line-without-newline", {"append": True}),
        (b"old;line\n", {"append": True, "file_exist_exception": True}),
        (b"old\nold\nold\n", {"file_exist_exception": False}),
        (b"old;line\n", {"append": True, "include_header": False}),
    ],
)
def test_existing_output_file(tmp_path, existing, config):
    inputs = {"in.csv": b"1;a\n2;b\n"}
    if existing is not None:
        inputs["out.csv"] = existing
    same(tmp_path, None, "id:int, name:str", write=config, inputs=inputs)


def test_existing_output_file_fails_the_job_when_asked(tmp_path):
    inputs = {"in.csv": b"1;a\n", "out.csv": b"old;line\n"}
    same(tmp_path, None, "id:int, name:str", write={"file_exist_exception": True}, inputs=inputs, fails=True)
    assert (tmp_path / "v2" / "out.csv").read_bytes() == b"old;line\n"


@pytest.mark.parametrize("create", [True, False])
def test_output_folder(tmp_path, create):
    same(tmp_path, b"1;a\n", "id:int, name:str", write={"filepath": "p/q/out.csv", "create_directory": create},
         fails=not create)


@pytest.mark.parametrize("delete_empty", [True, False])
@pytest.mark.parametrize("header", [True, False])
@pytest.mark.parametrize("existing", [None, b"old\n"])
@pytest.mark.parametrize("append", [True, False])
def test_output_of_no_rows(tmp_path, delete_empty, header, existing, append):
    inputs = {"in.csv": b""}
    if existing is not None:
        inputs["out.csv"] = existing
    config = {"delete_empty_file": delete_empty, "include_header": header, "append": append}
    same(tmp_path, None, "id:int, name:str", write=config, inputs=inputs)


def test_output_of_no_rows_with_csv_header(tmp_path):
    same(tmp_path, b"", "id:int, name:str", write={"csv_option": True})


# ------------------------------------------------------------------
# What v2 says no to, and what it lets pass
# ------------------------------------------------------------------

def refused(component_index, **config):
    made = copy("a:int, b:str")
    made["components"][component_index]["config"].update(config)
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    return caught.value.report.format()


@pytest.mark.parametrize(
    "index, config, said",
    [
        (0, {"row_separator": "@@"}, "row_separator"),
        (0, {"limit": "abc"}, "limit"),
        (0, {"bogus": 1}, "bogus"),
        (0, {"encoding": "NOPE-1"}, "unknown encoding: NOPE-1"),
        (0, {"fieldseparator": ""}, "must not be empty"),
        (0, {"csv_option": True, "text_enclosure": "''"}, "text_enclosure: must be one character"),
        (0, {"csv_option": True, "escape_char": "\\"}, "escape_char"),
        (0, {"csv_option": True, "check_fields_num": True}, "check_fields_num"),
        (0, {"fieldseparator": "||", "row_separator": "\\r"}, "row_separator"),
        (1, {"split": True}, "split"),
        (1, {"bogus": 1}, "bogus"),
        (1, {"encoding": "NOPE-1"}, "unknown encoding: NOPE-1"),
        (1, {"csv_option": True, "text_enclosure": ""}, "text_enclosure: must be one character"),
        (1, {"csv_option": True, "escape_char": "\\"}, "escape_char"),
    ],
)
def test_refused_config(index, config, said):
    assert said in refused(index, **config)


def test_keys_v1_ignores_are_accepted():
    made = copy("a:int, b:str")
    made["components"][0]["config"].update({
        "uncompress": True, "advanced_separator": True, "thousands_separator": ",", "decimal_separator": ".",
        "random": False, "nb_random": 10, "check_date": False, "split_record": False, "enable_decode": False,
        "decode_cols": [{"column": "a", "decode": False}], "tstatcatcher_stats": False, "label": "",
    })
    made["components"][1]["config"].update({
        "compress": False, "usestream": False, "streamname": "outputStream", "advanced_separator": False,
        "thousands_separator": ",", "decimal_separator": ".", "flushonrow": False, "flush_row_count": "1",
        "row_mode": False, "split": False, "split_every": "1000", "escape_char": "\"", "text_enclosure": "\"",
    })
    load_job(made)


def test_reader_without_a_schema_is_refused():
    made = copy("a:int")
    made["components"][0]["schema"]["output"] = []
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    assert "schema" in caught.value.report.format()


def test_field_count_check_rejects_rows_of_the_wrong_width(tmp_path):
    result, folder = v2(tmp_path, b"1;x;1.5\n2;y\n3;z;3.5;EXTRA\n\n4;;\n", "a:int, b:str, c:float",
                        read={"check_fields_num": True}, reject_schema=True)
    assert result.status == "success"
    assert (folder / "out.csv").read_bytes() == b"a;b;c\n1;x;1.5\n4;;\n"
    assert (folder / "rej.csv").read_bytes() == (
        b"a;b;c;errorCode;errorMessage\n"
        b"2;y;;FIELD_COUNT;Field count mismatch: expected 3, got 2 - Line: 2\n"
        b"3;z;3.5;FIELD_COUNT;Field count mismatch: expected 3, got 4 - Line: 3\n"
    )


def test_path_can_come_from_the_context(tmp_path):
    made = copy("a:int, b:str")
    made["context"] = {"Default": {"dir": {"value": ".", "type": "str"}, "name": {"value": "in.csv", "type": "str"}}}
    made["components"][0]["config"]["filepath"] = "${context.dir}/context.name"
    assert_matches_v1(made, {"in.csv": b"1;a\n"}, tmp_path)


# ------------------------------------------------------------------
# Rows written, as the job reports them
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "write",
    [
        {},
        {"include_header": False},
        {"os_line_separator": False, "row_separator": "\\r\\n"},
        {"os_line_separator": False, "row_separator": "\\r"},
        {"os_line_separator": False, "row_separator": "@@"},
        {"fieldseparator": "||"},
        {"csv_option": True},
        {"csv_option": True, "os_line_separator": False, "csvrowseparator": "CRLF"},
        {"csv_option": True, "os_line_separator": False, "csvrowseparator": "@@", "include_header": False},
    ],
)
def test_rows_written_are_counted(tmp_path, write):
    result, _ = v2(tmp_path, b"1;a\n2;b\n3;c\n", "id:int, name:str", write=write)
    assert result.status == "success"
    assert result.rows == {"out": 3} and result.global_map["out_NB_LINE"] == 3


def test_rows_written_are_counted_when_a_field_holds_a_line_break(tmp_path):
    data = b'1;"l1\nl2"\n2;"x"\n'
    result, folder = v2(tmp_path, data, "id:int, name:str", read={"csv_option": True}, write={"csv_option": True})
    assert result.rows == {"out": 2}
    assert (folder / "out.csv").read_bytes() == b'"id";"name"\n"1";"l1\nl2"\n"2";"x"\n'


def test_no_rows_written_is_counted_as_zero(tmp_path):
    result, _ = v2(tmp_path, b"", "id:int, name:str")
    assert result.rows == {"out": 0}
