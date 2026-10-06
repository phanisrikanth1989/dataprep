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
    "text",
    ["1", "1.50", "30200.00", "1e5", "+5", " 7 ", "007", "0.1", "2.50", "1e15", "1e16", "1e22", "0.0001", "inf", "-inf",
     "0.00001", "0.00005", "0.000012345", "1e-7", "-2.5e-9", "5e-324"],
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


def test_data_column_named_like_the_reject_reason_gives_its_place_to_it(tmp_path):
    run = same(tmp_path, b"1;mine\nx;theirs\n", "id:int, errorCode:str", reject_schema=True)
    assert run.files["rej.csv"] == (
        b"id;errorCode;errorMessage\nx;TYPE_CONVERSION;Column 'id': could not convert string to float: 'x'\n"
    )
    assert run.files["out.csv"] == b"id;errorCode_user\n1;mine\n"


def test_flow_with_no_columns_writes_an_empty_file(tmp_path):
    # What v1 writes when a component hands on a frame with nothing in it.
    import os

    import polars as pl

    from src.v2.components.base import Source
    from src.v2.components.registry import REGISTRY, Registry

    class Nothing(Source):
        names = ("nothing",)

        def read(self):
            return {"main": pl.LazyFrame()}

    registry = Registry()
    for cls in list(REGISTRY.classes()) + [Nothing]:
        registry.register(cls)
    made = job([{"id": "in", "type": "nothing", "config": {}}, writer(None, inputs=("row1",))], [flow("row1", "in", "out")])
    made["components"][1]["config"]["filepath"] = str(tmp_path / "out.csv")
    result = run_job(made, registry=registry)
    assert result.status == "success" and result.rows == {"out": 0}
    assert os.path.getsize(tmp_path / "out.csv") == 0


def test_two_outputs_of_one_subjob_can_append_to_the_same_file(tmp_path):
    made = copy("id:int, name:str", write={"append": True, "include_header": False}, reject_schema=True)
    made["components"][2]["config"].update({"filepath": "out.csv", "append": True, "include_header": False})
    run = assert_matches_v1(made, {"in.csv": b"1;a\nx;b\n2;c\n"}, tmp_path)
    assert run.succeeded
    assert run.files["out.csv"] == (
        b"1;a\n2;c\nx;b;TYPE_CONVERSION;Column 'id': could not convert string to float: 'x'\n"
    )


# ------------------------------------------------------------------
# Numbers are read by Polars itself where that is safe, and as text where it is not
# ------------------------------------------------------------------

def schemas_scanned(monkeypatch):
    """Record the column types every delimited scan is asked for."""
    import polars as pl

    seen = []
    real = pl.scan_csv

    def spy(source, **more):
        if "schema" in more:
            seen.append(list(more["schema"].values()))
        return real(source, **more)

    monkeypatch.setattr(pl, "scan_csv", spy)
    return seen


def test_clean_numbers_are_parsed_by_polars_directly(tmp_path, monkeypatch):
    import polars as pl

    # About the fast reader: it must be on, whatever the suite is run with.
    monkeypatch.delenv("V2_SAFE_READ", raising=False)
    seen = schemas_scanned(monkeypatch)
    result, folder = v2(tmp_path, b"1;a;1.5\n2;b;2.5\n", "id:int, name:str, amt:float")
    assert result.status == "success"
    assert seen == [[pl.Int64, pl.String, pl.Float64]]
    assert (folder / "out.csv").read_bytes() == b"id;name;amt\n1;a;1.5\n2;b;2.5\n"


def test_file_that_needs_the_tolerant_reader_is_read_again_as_text(tmp_path, monkeypatch):
    import polars as pl

    # About the fast reader: it must be on, whatever the suite is run with.
    monkeypatch.delenv("V2_SAFE_READ", raising=False)
    seen = schemas_scanned(monkeypatch)
    result, folder = v2(tmp_path, b"1;a;1.5\n 2 ;b;2,5\nx;c;3\n4.0;d;4\n", "id:int, name:str, amt:float")
    assert result.status == "success"
    assert seen == [[pl.Int64, pl.String, pl.Float64], [pl.String, pl.String, pl.String]]
    assert (folder / "out.csv").read_bytes() == b"id;name;amt\n1;a;1.5\n4;d;4.0\n"


def test_reader_with_its_reject_output_wired_reads_text_from_the_start(tmp_path, monkeypatch):
    # The rejected rows carry the fields as they stand in the file, which only the text is.
    import polars as pl

    seen = schemas_scanned(monkeypatch)
    result, folder = v2(tmp_path, b"007;a\nx;b\n", "id:int, name:str", reject_schema=True)
    assert result.status == "success"
    assert seen == [[pl.String, pl.String]]
    assert (folder / "rej.csv").read_bytes().splitlines()[1].startswith(b"x;b;TYPE_CONVERSION")


def test_tolerant_reader_can_be_asked_for_outright(tmp_path, monkeypatch):
    import polars as pl

    monkeypatch.setenv("V2_SAFE_READ", "1")
    seen = schemas_scanned(monkeypatch)
    result, _ = v2(tmp_path, b"1;a\n", "id:int, name:str")
    assert result.status == "success" and seen == [[pl.String, pl.String]]


def test_a_failure_that_is_not_about_reading_is_still_reported_after_the_second_read(tmp_path):
    result, _ = v2(tmp_path, b"1;a\n", "id:int, name:str", write={"encoding": "ascii"}, read={"encoding": "UTF-8"})
    assert result.status == "success"
    (tmp_path / "in.csv").write_bytes("1;café\n".encode("utf-8"))
    import os

    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        failed = run_job(copy("id:int, name:str", write={"encoding": "ascii"}))
    finally:
        os.chdir(previous)
    assert failed.status == "failed" and failed.failed_component == "out"


def test_file_name_with_pattern_characters_is_one_file_not_a_pattern(tmp_path):
    made = copy("id:int, name:str")
    made["components"][0]["config"]["filepath"] = "in[1]*.csv"
    run = assert_matches_v1(made, {"in[1]*.csv": b"1;a\n", "in1x.csv": b"9;z\n"}, tmp_path)
    assert run.succeeded and run.files["out.csv"] == b"id;name\n1;a\n"


def test_bad_byte_in_a_file_read_line_by_line_becomes_a_replacement_character(tmp_path):
    result, folder = v2(tmp_path, b"1||caf\xe9\n2||ok\n", "id:int, name:str",
                        read={"fieldseparator": "||", "encoding": "UTF-8"}, write={"encoding": "UTF-8"})
    assert result.status == "success"
    assert (folder / "out.csv").read_bytes() == "id;name\n1;caf�\n2;ok\n".encode("utf-8")


# ------------------------------------------------------------------
# Several outputs of one subjob, and what a run that fails or is stopped leaves behind
# ------------------------------------------------------------------

def two_outputs(first=None, second=None, second_path="out2.csv", schema="id:int, name:str"):
    """in.csv -> out.csv and, by a second flow of the same rows, -> a second output."""
    components = [reader(schema, outputs=("row1", "row2")),
                  writer(schema, inputs=("row1",), **(first or {})),
                  writer(schema, component_id="out2", path=second_path, inputs=("row2",), **(second or {}))]
    return job(components, [flow("row1", "in", "out"), flow("row2", "in", "out2")])


def run_in(folder, made, files):
    """Run a job on v2 only, inside a folder holding ``files``."""
    import os

    for name, data in files.items():
        (folder / name).write_bytes(data)
    previous = os.getcwd()
    os.chdir(folder)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def test_failed_subjob_leaves_every_file_as_it_was(tmp_path):
    # The second output cannot be written in its encoding. The first is written by then, and must not
    # have taken the place of the file that was there.
    made = two_outputs(first={"file_exist_exception": False}, second={"encoding": "ascii"})
    result = run_in(tmp_path, made, {"in.csv": "1;café\n".encode("utf-8"), "out.csv": b"old\n"})
    assert result.status == "failed" and result.failed_component == "out2"
    assert (tmp_path / "out.csv").read_bytes() == b"old\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["in.csv", "out.csv"]
    assert result.rows == {}


def test_two_outputs_appending_to_one_new_file_write_one_header(tmp_path):
    made = two_outputs(first={"append": True}, second={"append": True}, second_path="out.csv")
    run = assert_matches_v1(made, {"in.csv": b"1;a\n2;b\n"}, tmp_path)
    assert run.succeeded and run.files["out.csv"] == b"id;name\n1;a\n2;b\n1;a\n2;b\n"


def test_second_output_writes_over_the_first_when_allowed(tmp_path):
    made = two_outputs(first={"file_exist_exception": False},
                       second={"file_exist_exception": False, "include_header": False}, second_path="out.csv")
    run = assert_matches_v1(made, {"in.csv": b"1;a\n2;b\n"}, tmp_path)
    assert run.succeeded and run.files["out.csv"] == b"1;a\n2;b\n"


def test_second_output_to_the_file_the_first_made_fails_when_an_existing_file_is_an_error(tmp_path):
    from tests.v2 import answer_key

    made = two_outputs(first={"file_exist_exception": True}, second={"file_exist_exception": True},
                       second_path="out.csv")
    inputs = {"in.csv": b"1;a\n"}
    on_v1 = answer_key.run_job(made, inputs, tmp_path / "v1", answer_key.run_v1)
    on_v2 = answer_key.run_job(made, inputs, tmp_path / "v2", answer_key.run_v2)
    assert not on_v1.succeeded and not on_v2.succeeded
    assert "File already exists" in on_v2.error
    # v1 leaves the first output behind; v2 leaves nothing of a subjob that failed.
    assert "out.csv" in on_v1.files and "out.csv" not in on_v2.files


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
@pytest.mark.parametrize("existing", [None, "", "id;name\n9;z\n"])
def test_appending_writes_one_byte_order_mark(tmp_path, encoding, existing):
    inputs = {"in.csv": b"1;a\n"}
    if existing is not None:
        inputs["out.csv"] = existing.encode(encoding) if existing else b""
    run = same(tmp_path, None, "id:int, name:str", write={"append": True, "encoding": encoding}, inputs=inputs)
    assert run.files["out.csv"] == ((existing or "id;name\n") + "1;a\n").encode(encoding)


def test_stopped_run_leaves_no_file_half_written(tmp_path, monkeypatch):
    import polars as pl

    collect_all = pl.collect_all

    def stopped(plans, **kwargs):
        collect_all(plans, **kwargs)
        raise KeyboardInterrupt

    monkeypatch.setattr(pl, "collect_all", stopped)
    with pytest.raises(KeyboardInterrupt):
        run_in(tmp_path, copy("id:int, name:str"), {"in.csv": b"1;a\n"})
    assert [path.name for path in tmp_path.iterdir()] == ["in.csv"]


@pytest.mark.parametrize(
    "write",
    [{}, {"os_line_separator": False, "row_separator": "\\r\\n"}, {"os_line_separator": False, "row_separator": "|"},
     {"os_line_separator": False, "row_separator": ""}, {"csv_option": True}],
)
def test_row_count_is_the_rows_written_whatever_the_values_hold(tmp_path, write):
    # A value that holds a line break is still one row, though it is two lines of the file without csv_option.
    made = copy("id:int, name:str", read={"csv_option": True}, write=write)
    result = run_in(tmp_path, made, {"in.csv": b'1;"two\nlines"\n2;"a|b"\n3;c\n'})
    assert result.status == "success" and result.rows["out"] == 3
    assert result.global_map["out_NB_LINE"] == 3


def test_output_written_over_a_link_writes_the_file_the_link_points_at(tmp_path):
    import os

    (tmp_path / "real.csv").write_bytes(b"old\n")
    os.symlink("real.csv", tmp_path / "out.csv")
    result = run_in(tmp_path, copy("id:int, name:str", write={"file_exist_exception": False}), {"in.csv": b"1;a\n"})
    assert result.status == "success"
    assert (tmp_path / "out.csv").is_symlink() and (tmp_path / "real.csv").read_bytes() == b"id;name\n1;a\n"


def test_output_written_over_a_file_keeps_its_permissions(tmp_path):
    import os
    import stat

    (tmp_path / "out.csv").write_bytes(b"old\n")
    os.chmod(tmp_path / "out.csv", 0o640)
    result = run_in(tmp_path, copy("id:int, name:str", write={"file_exist_exception": False}), {"in.csv": b"1;a\n"})
    assert result.status == "success" and (tmp_path / "out.csv").read_bytes() == b"id;name\n1;a\n"
    assert stat.S_IMODE(os.stat(tmp_path / "out.csv").st_mode) == 0o640


# ------------------------------------------------------------------
# Blank lines, and lines around a separator of several characters
# ------------------------------------------------------------------

TWO, THREE = "a:str, b:str", "a:str, b:str, c:str"


@pytest.mark.parametrize(
    "schema, read, data",
    [
        (TWO, {"limit": 2}, b"1;a\n\n\n2;b\n3;c\n"),
        (TWO, {"limit": 2, "remove_empty_row": False}, b"1;a\n\n\n2;b\n3;c\n"),
        (TWO, {"limit": 2}, b"1;a\n   \n2;b\n3;c\n"),
        (TWO, {"limit": 2}, b"1;a\n;\n;\n2;b\n3;c\n"),
        (TWO, {"limit": 2, "footer_rows": 1}, b"1;a\n\n\n2;b\n3;c\nEND;x\n"),
        (TWO, {"remove_empty_row": False}, b"1;a\n\n\n2;b\n;\n3;c\n"),
        (TWO, {"remove_empty_row": False}, b"1;a\n   \n \t \n2;b\n"),
        (TWO, {"remove_empty_row": False, "fieldseparator": "\\t"}, b"1\ta\n   \n\t\n \t \n2\tb\n"),
        (TWO, {"remove_empty_row": False, "fieldseparator": " "}, b"1 a\n\t\n \n2 b\n"),
        (THREE, {"remove_empty_row": False}, b"1;a;x\n\n2\n;\n;;\n3;c;z\n"),
        ("a:str", {"remove_empty_row": False}, b"1\n\n2\n"),
        ("a:int, b:str", {"limit": 2}, b"1;a\n\n\n2;b\n3;c\n"),
        ("a:int, b:str", {"remove_empty_row": False}, b"1;a\n\n2;b\n"),
        (TWO, {"limit": 2, "header_rows": 1, "footer_rows": 1}, b"H;h\n\n1;a\n\n2;b\n3;c\n\nEND;x\n"),
        (TWO, {"remove_empty_row": False, "header_rows": 1, "footer_rows": 1}, b"H;h\n\n1;a\n\n2;b\n\nEND;x\n"),
        (TWO, {"remove_empty_row": False, "row_separator": "\\r\\n"}, b"1;a\r\n\r\n2;b\r\n"),
        (TWO, {"remove_empty_row": False, "fieldseparator": "\u00a6", "encoding": "UTF-8"},
         "1\u00a6a\n\n   \n2\u00a6b\n".encode("utf-8")),
    ],
)
def test_blank_line_is_never_a_row_and_does_not_count_toward_the_limit(tmp_path, schema, read, data):
    same(tmp_path, data, schema, read=read, write={"include_header": False})


@pytest.mark.parametrize(
    "read, data",
    [
        ({"fieldseparator": "||"}, b"  1||a  \n\t2||b\t\n3|| c \n"),
        ({"fieldseparator": "||", "remove_empty_row": False}, b"  1||a  \n\n   \n2||  \n"),
        ({"fieldseparator": "||", "check_fields_num": True}, b"  1||a  \n2||b\n"),
    ],
)
def test_line_loses_the_blanks_around_it_before_a_separator_of_several_characters_splits_it(tmp_path, read, data):
    same(tmp_path, data, TWO, read=read, write={"include_header": False})


# ------------------------------------------------------------------
# Enclosures that do not pair up, footers
# ------------------------------------------------------------------

@pytest.mark.parametrize("line", [b'2;b"c', b'2;"bc', b'2;bc"'])
@pytest.mark.parametrize("footer", [0, 1])
def test_enclosure_that_does_not_pair_up_fails_the_reader_and_never_drops_rows(tmp_path, line, footer):
    # v1 reads such a file as pandas does. v2 reads enclosed fields strictly: it must then fail, not go on
    # with the rows it could count.
    data = b"1;a\n" + line + b"\n3;d\n4;e\n" + (b"END;x\n" if footer else b"")
    result, folder = v2(tmp_path, data, TWO, read={"csv_option": True, "footer_rows": footer})
    assert result.status == "failed" and result.failed_component == "in"
    assert "enclos" in result.error
    assert not (folder / "out.csv").exists()


def test_file_with_a_footer_is_read_once(tmp_path, caplog):
    # Polars parses the lines after the last row it is asked for, so a footer of text under a number
    # column fails the fast reader every time. Such a file is read as text from the start.
    import logging

    caplog.set_level(logging.INFO)
    result, folder = v2(tmp_path, b"1;a\n2;b\nTOTAL;2\n", "n:int, name:str", read={"footer_rows": 1})
    assert result.status == "success" and (folder / "out.csv").read_bytes() == b"n;name\n1;a\n2;b\n"
    assert not [record for record in caplog.records if "reading again" in record.getMessage()]


@pytest.mark.parametrize("side", ["read", "write"])
def test_enclosed_fields_with_a_separator_of_more_than_one_byte_are_refused(side):
    made = copy(TWO, **{side: {"csv_option": True, "fieldseparator": "¦"}})
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    assert "one byte" in caught.value.report.format()


# ------------------------------------------------------------------
# A column written under another type than it arrives with
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "arriving, data",
    [
        ("int", b"1\n-2\n0\n\n123456789012\n"),
        ("bool", b"true\nfalse\n"),
        # 2.675 and 1.115 are a little less than they look, 0.125 and 0.375 are exactly halfway.
        ("float", b"1\n2.5\n2.675\n1.115\n0.125\n0.375\n1.005\n-2.5\n-0.004\n1e-7\n123456789.125\n0\n\n"),
    ],
)
@pytest.mark.parametrize("places", [0, 2, 4])
def test_number_written_as_a_decimal_gets_the_declared_places(tmp_path, arriving, data, places):
    same(tmp_path, data, f"v:{arriving}", write_schema=f"v:Decimal#{places}", write={"include_header": False})


def test_float_written_as_a_decimal_of_no_declared_places_is_written_plainly(tmp_path):
    run = same(tmp_path, b"1\n2.5\n2.675\n-0.004\n\n", "v:float", write_schema="v:Decimal",
               write={"include_header": False})
    assert run.files["out.csv"] == b"1\n2.5\n2.675\n-0.004\n"


# ------------------------------------------------------------------
# The UTF-8 copy a file in another encoding is read through
# ------------------------------------------------------------------

def test_file_in_another_encoding_is_copied_once_when_the_subjob_is_read_again(tmp_path, monkeypatch):
    # "1.0" is a whole number the fast reader does not take, so the subjob is read a second time.
    from src.v2.engine.context import RunContext

    copies = []
    temp_path = RunContext.temp_path

    def noted(self, suffix=""):
        copies.append(temp_path(self, suffix))
        return copies[-1]

    monkeypatch.setattr(RunContext, "temp_path", noted)
    result, folder = v2(tmp_path, "1.0;café\n2;b\n".encode("latin-1"), "n:int, name:str",
                        read={"encoding": "ISO-8859-1"})
    assert result.status == "success"
    assert (folder / "out.csv").read_bytes() == "n;name\n1;café\n2;b\n".encode("utf-8")
    assert len(copies) == 1


def test_copies_one_subjob_read_through_are_gone_when_the_next_one_starts(tmp_path, monkeypatch):
    import os

    from src.v2.engine import runner as engine

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setenv("V2_TEMP_DIR", str(scratch))
    left = []
    attempt = engine.Runner._attempt

    def watched(self, component_ids):
        left.append(os.listdir(scratch))
        return attempt(self, component_ids)

    monkeypatch.setattr(engine.Runner, "_attempt", watched)
    latin = {"encoding": "ISO-8859-1"}
    made = job(
        [reader("a:str", **latin), writer("a:str", inputs=("row1",)),
         reader("a:str", component_id="in2", path="in2.csv", outputs=("row2",), **latin),
         writer("a:str", component_id="out2", path="out2.csv")],
        [flow("row1", "in", "out"), flow("row2", "in2", "out2")],
        triggers=[{"type": "OnSubjobOk", "from": "in", "to": "in2"}],
    )
    work = tmp_path / "work"
    work.mkdir()
    result = run_in(work, made, {"in.csv": "café\n".encode("latin-1"), "in2.csv": "naïve\n".encode("latin-1")})
    assert result.status == "success" and (work / "out2.csv").read_bytes() == "a\nnaïve\n".encode("utf-8")
    assert left == [[], []] and os.listdir(scratch) == []


@pytest.mark.parametrize("key", ["header_rows", "footer_rows"])
def test_negative_count_of_lines_is_refused_at_load(key):
    with pytest.raises(JobRefusedError) as caught:
        load_job(copy(TWO, read={key: -1}))
    assert "must not be negative" in caught.value.report.format()


# ------------------------------------------------------------------
# What the log says at DEBUG
# ------------------------------------------------------------------

def debug_lines(caplog, tmp_path, data, schema, **kwargs):
    """Run file -> file on v2 at DEBUG; returns (the DEBUG lines, how the run ended)."""
    import logging

    caplog.set_level(logging.DEBUG, logger="src.v2")
    caplog.clear()
    result, _ = v2(tmp_path, data, schema, **kwargs)
    return [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG], result


def test_debug_says_when_polars_parses_the_numbers_itself(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("V2_SAFE_READ", raising=False)
    lines, result = debug_lines(caplog, tmp_path, b"1;a;1.5\n", "id:int, name:str, amt:float")
    assert result.status == "success"
    assert "[in] Polars parses the numbers of id, amt itself; every other column is read as text" in lines


@pytest.mark.parametrize("schema, changes, why", [
    ("id:int, name:str", {"reject_schema": True},
     "its reject output is wired, and a rejected row carries its fields as they stand in the file"),
    ("id:int, name:str", {"read": {"footer_rows": 1}},
     "the file has a footer, and Polars would parse its lines as numbers too"),
    ("id:str, name:str", {}, "no column is declared int or float"),
    ("id:int, name:str", {"read": {"check_fields_num": True}},
     "v2 splits the rows itself (a field count, a delimiter of several bytes, a limit, or empty rows that are kept)"),
])
def test_debug_says_why_a_delimited_reader_reads_every_column_as_text(tmp_path, monkeypatch, caplog, schema, changes, why):
    monkeypatch.delenv("V2_SAFE_READ", raising=False)
    lines, result = debug_lines(caplog, tmp_path, b"1;a\n2;b\n", schema, **changes)
    assert result.status == "success"
    assert f"[in] every column is read as text: {why}" in lines


def test_debug_says_when_the_engine_asked_for_the_tolerant_reader(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("V2_SAFE_READ", "1")
    lines, result = debug_lines(caplog, tmp_path, b"1;a\n", "id:int, name:str")
    assert result.status == "success"
    assert "[in] every column is read as text: the engine asked for the tolerant reader in this subjob" in lines


def test_debug_shows_in_full_what_made_a_subjob_be_read_a_second_time(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("V2_SAFE_READ", raising=False)
    lines, result = debug_lines(caplog, tmp_path, b"1;a\n 2 ;b\n", "id:int, name:str")
    assert result.status == "success"
    (said,) = [line for line in lines if line.startswith("[t] what the fast reader said, in full:\n")]
    # More than the one line the INFO level gives: Polars' own message with its line breaks.
    assert len(said.splitlines()) > 2 and said.isascii()
    # The reader says how it read, once for each time the subjob was read.
    assert [line for line in lines if line.startswith("[in] ")
            and ("Polars parses" in line or "read as text" in line)] == [
        "[in] Polars parses the numbers of id itself; every other column is read as text",
        "[in] every column is read as text: the engine asked for the tolerant reader in this subjob",
    ]


def test_debug_says_which_encoding_an_output_is_put_in(tmp_path, caplog):
    lines, result = debug_lines(caplog, tmp_path, b"1;a\n", "id:int, name:str", write={"encoding": "ISO-8859-15"})
    assert result.status == "success"
    assert "[out] the written file is put in the encoding ISO-8859-15" in lines


# ------------------------------------------------------------------
# The check goes on past a reader with a fault
# ------------------------------------------------------------------

def test_fault_after_a_reader_whose_config_has_one_is_reported_with_it(tmp_path):
    from .kit import through

    made = through({"type": "FilterRows", "config": {"conditions": [
        {"column": "nam", "operator": "==", "function": "", "value": "x"}]}},
        "id:int, name:str", csv_option=True, text_enclosure="ab")
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    found = [(refusal.where.split()[1], refusal.key, refusal.reason) for refusal in caught.value.report]
    assert [(component_id, key) for component_id, key, _ in found][0] == ("in", "text_enclosure")
    assert found[1][0] == "it" and "nam" in found[1][2]
    assert found[1][2].endswith("(checked against the columns 'in' declares, because 'in' has a fault of its own)")
    assert len(found) == 2


def test_what_follows_a_reader_that_declares_no_columns_stays_unchecked(tmp_path):
    # The reader's fault is that it has no columns. There is nothing to check the filter against,
    # and a filter held against no columns at all would be reported for every column it names.
    from .kit import through

    made = through({"type": "FilterRows", "config": {"conditions": [
        {"column": "name", "operator": "==", "function": "", "value": "x"}]}}, "id:int, name:str")
    made["components"][0]["schema"] = {"input": [], "output": []}
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    assert [(refusal.where.split()[1], refusal.key) for refusal in caught.value.report] == [("in", "schema")]
