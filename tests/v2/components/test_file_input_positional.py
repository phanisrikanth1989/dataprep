"""Positional (fixed-width) file input, against v1 on the same job config and bytes.

v1 reads the file with pandas and gives up on the whole file at the first
value it cannot read; the cases compared with v1 hold values it can read.
What v2 does with the rest is tested on v2 alone, further down.
"""
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import columns, flow, job, writer

TEXT = "a:str, b:str, c:str"
ABSENT = ...  # as a config value: leave the key out


def cut(schema=TEXT, pattern="3,4,2", write_schema="same", reject=False, header=True, type_name="FileInputPositional",
        **config):
    """file -> file, optionally with the reader's reject output written to rej.csv."""
    made = {"filepath": "in.txt", "pattern": pattern, "encoding": "UTF-8", "die_on_error": False}
    made.update(config)
    config = {key: value for key, value in made.items() if value is not ABSENT}
    source = {"id": "in", "type": type_name, "config": config,
              "schema": {"input": [], "output": columns(schema) if schema else []}, "inputs": [], "outputs": ["row1"]}
    components = [source, writer(schema if write_schema == "same" else write_schema, inputs=("row1",),
                                 include_header=header)]
    flows = [flow("row1", "in", "out")]
    if reject:
        source["outputs"].append("bad")
        components.append(writer(None, component_id="rej", path="rej.csv", inputs=("bad",)))
        flows.append(flow("bad", "in", "rej", "reject"))
    return job(components, flows)


def same(tmp_path, data, fails=False, inputs=None, **kwargs):
    """Both engines do the same with the job; ``fails`` says the job is one neither finishes."""
    run = assert_matches_v1(cut(**kwargs), inputs if inputs is not None else {"in.txt": data}, tmp_path)
    assert run.succeeded is not fails, run.error
    return run


def v2(tmp_path, data, **kwargs):
    """Run on v2 only, inside tmp_path; returns (result, the folder)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    if data is not None:
        (tmp_path / "in.txt").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(cut(**kwargs)), tmp_path
    finally:
        os.chdir(previous)


def written(tmp_path, data, name="out.csv", **kwargs):
    """What v2 alone writes for the job."""
    result, folder = v2(tmp_path, data, **kwargs)
    assert result.status == "success", result.error
    return (folder / name).read_bytes()


def refused(**kwargs):
    with pytest.raises(JobRefusedError) as caught:
        load_job(cut(**kwargs))
    return caught.value.report.format()


def fixed(*widths):
    """A function that lays values out in columns of the given widths."""
    def line(*values):
        return "".join(str(value).ljust(width) for value, width in zip(values, widths)).encode() + b"\n"
    return line


# ------------------------------------------------------------------
# Cutting a line into fields
# ------------------------------------------------------------------

def test_fields_are_cut_by_width(tmp_path):
    run = same(tmp_path, b"abcdefghi\n123456789\n")
    assert run.files["out.csv"] == b"a;b;c\nabc;defg;hi\n123;4567;89\n"


def test_short_lines_give_empty_fields_and_long_ones_are_cut(tmp_path):
    run = same(tmp_path, b"ab\nabcd\nabcdefg\nabcdefghijklmnop\n")
    assert run.files["out.csv"] == b"a;b;c\nab;;\nabc;d;\nabc;defg;\nabc;defg;hi\n"


@pytest.mark.parametrize("trim_all", [True, False, ABSENT])
@pytest.mark.parametrize("data", [b"a  b   c \n 1  22 3\n", b"a\tb\t\tc\t\n\t1\t22\t3\n", b"a b c d e\n"])
def test_blanks_and_tabs_around_a_field_are_always_dropped(tmp_path, data, trim_all):
    same(tmp_path, data, trim_all=trim_all)


@pytest.mark.parametrize("pattern", ["3,4,2", " 3 , 4,2 ", "3,,4,2,"])
def test_pattern_spellings(tmp_path, pattern):
    same(tmp_path, b"abcdefghi\n", pattern=pattern)


@pytest.mark.parametrize("pattern", ["3,0,2", "3,-1,2", "3,x,2", "3.0,4,2", "", "  ", ","])
def test_pattern_that_is_not_widths_fails_on_both(tmp_path, pattern):
    same(tmp_path, b"abcdefghi\n", pattern=pattern, fails=True)
    assert "pattern" in refused(pattern=pattern)


def test_pattern_is_required(tmp_path):
    same(tmp_path, b"abcdefghi\n", pattern=ABSENT, fails=True)


@pytest.mark.parametrize(
    "data",
    [b"abcdefghi\r\n123456789\r\n", b"abcdefghi\r123456789\r", b"abcdefghi\r123456789\nxyzxyzxyz\r\nqqqqqqqqq"],
)
def test_lines_end_at_lf_crlf_or_cr(tmp_path, data):
    same(tmp_path, data)


# ------------------------------------------------------------------
# Which lines are read
# ------------------------------------------------------------------

HEADED = b"HHHHHHHHH\nhhhhhhhhh\nabcdefghi\n123456789\nxyzxyzxyz\nFFFFFFFFF\n"
GAPPED = b"abcdefghi\n\n         \n   \n\t\t\n123456789\n"


@pytest.mark.parametrize(
    "config",
    [
        {"header_rows": 2},
        {"header_rows": "2"},
        {"header_rows": 2, "footer_rows": 1},
        {"header_rows": 2, "footer_rows": "2"},
        {"header_rows": 10},
        {"footer_rows": 10},
        {"header_rows": 6},
        {"header_rows": 2, "limit": "2"},
        {"header_rows": 2, "limit": 2},
        {"limit": " 2 "},
        {"limit": 0},
        {"limit": ""},
        {"limit": None},
        {"limit": "9"},
    ],
)
def test_header_footer_and_limit(tmp_path, config):
    same(tmp_path, HEADED, **config)


@pytest.mark.parametrize(
    "config",
    [{"limit": "0"}, {"limit": "-1"}, {"limit": "abc"}, {"header_rows": -1}, {"header_rows": "abc"},
     {"footer_rows": -1}],
)
def test_counts_that_cannot_be_fail_on_both(tmp_path, config):
    same(tmp_path, HEADED, fails=True, **config)
    assert next(iter(config)) in refused(**config)


def test_footer_counts_lines_as_they_are_in_the_file(tmp_path):
    kept = same(tmp_path, b"abcdefghi\n123456789\nFFFFFFFFF\n\n", footer_rows=1)
    assert kept.files["out.csv"] == b"a;b;c\nabc;defg;hi\n123;4567;89\nFFF;FFFF;FF\n"
    same(tmp_path / "bare", b"abcdefghi\n123456789\nFFFFFFFFF", footer_rows=1)


def test_header_counts_lines_as_they_are_in_the_file(tmp_path):
    same(tmp_path, b"\n\nabcdefghi\n\n123456789\nxyzxyzxyz\n", header_rows=3)


@pytest.mark.parametrize("data", [b"", b"HHHHHHHHH\n", b"HHHHHHHHH"])
def test_file_with_no_data_rows(tmp_path, data):
    same(tmp_path, data, header_rows=1)


@pytest.mark.parametrize("remove_empty_row", [True, False, ABSENT])
@pytest.mark.parametrize("trim_all", [True, False])
def test_rows_of_blank_fields_are_always_dropped(tmp_path, remove_empty_row, trim_all):
    run = same(tmp_path, GAPPED, remove_empty_row=remove_empty_row, trim_all=trim_all)
    assert run.files["out.csv"] == b"a;b;c\nabc;defg;hi\n123;4567;89\n"


@pytest.mark.parametrize("limit", ["1", "2", "3", "4"])
def test_limit_counts_rows_that_are_not_blank(tmp_path, limit):
    same(tmp_path, b"\n\nabcdefghi\n\n123456789\nxyzxyzxyz\nqqqqqqqqq\n", limit=limit)


def test_limit_is_not_used_up_by_blank_lines(tmp_path):
    # v1 (pandas) counts the blank lines that come after the second data row against the limit.
    out = written(tmp_path, b"aaaaaaaaa\nbbbbbbbbb\nccccccccc\n\n\nddddddddd\neeeeeeeee\n", limit="5", header=False)
    assert out == b"aaa;aaaa;aa\nbbb;bbbb;bb\nccc;cccc;cc\nddd;dddd;dd\neee;eeee;ee\n"


def test_limit_and_footer_together(tmp_path):
    # v1 reads nothing here: pandas refuses the two together and v1 swallows the refusal.
    out = written(tmp_path, HEADED, header_rows=2, footer_rows=1, limit="2", header=False)
    assert out == b"abc;defg;hi\n123;4567;89\n"


# ------------------------------------------------------------------
# Types
# ------------------------------------------------------------------

ALL_TYPES = "s:str, i:int, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2"
WIDTHS = "5,5,8,5,10,8"
typed = fixed(5, 5, 8, 5, 10, 8)


def test_every_type_is_read(tmp_path):
    data = typed("abc", 12, "1.5", "true", "2024-01-31", "12.345") + typed("de", -7, "30200.00", "1", "1999-12-31", 7)
    run = same(tmp_path, data, schema=ALL_TYPES, pattern=WIDTHS)
    assert run.files["out.csv"] == (
        b"s;i;f;b;d;m\nabc;12;1.5;true;2024-01-31;12.35\nde;-7;30200.0;true;1999-12-31;7.00\n"
    )


def test_empty_fields_of_every_type(tmp_path):
    data = typed("abc", 12, "1.5", "true", "2024-01-31", "12.345") + typed("x", "", "", "", "", "0")
    run = same(tmp_path, data, schema=ALL_TYPES, pattern=WIDTHS)
    assert run.files["out.csv"].splitlines()[2] == b"x;;;false;;0.00"


def test_empty_decimal_is_missing(tmp_path):
    data = typed("abc", 12, "1.5", "true", "2024-01-31", "12.345") + typed("x", "", "", "", "", "")
    same(tmp_path, data, schema=ALL_TYPES, pattern=WIDTHS, write_schema=None)
    # With a writer that declares the column v1 writes the text <NA>.
    out = written(tmp_path / "declared", data, schema=ALL_TYPES, pattern=WIDTHS, header=False)
    assert out.splitlines()[1] == b"x;;;false;;"


@pytest.mark.parametrize("text", ["true", "1", "yes", "True", "TRUE", "Yes", "YES"])
def test_bool_spellings_of_true(tmp_path, text):
    same(tmp_path, fixed(3, 5)("a", text) + fixed(3, 5)("b", ""), schema="k:str, v:bool", pattern="3,5")


@pytest.mark.parametrize("text", ["false", "0", "no", "False", "NO"])
def test_bool_spellings_of_false(tmp_path, text):
    # v1 leaves the text for its base class, which takes any text at all as true.
    out = written(tmp_path, fixed(3, 5)("a", text), schema="k:str, v:bool", pattern="3,5", header=False)
    assert out == b"a;false\n"


@pytest.mark.parametrize("text", ["1", "007", "+5", "1.0", "1e3", "12345", "-0", " 7"])
def test_whole_numbers(tmp_path, text):
    same(tmp_path, fixed(3, 6)("a", text) + fixed(3, 6)("b", 2), schema="k:str, v:int", pattern="3,6")


@pytest.mark.parametrize(
    "text", ["1", "1.50", "30200.00", "1e5", "+5", "007", "0.1", "inf", "-inf", "NaN", "nan", "-0", "1e16", ".5", "5."]
)
def test_floats(tmp_path, text):
    same(tmp_path, fixed(3, 9)("a", text) + fixed(3, 9)("b", 2.5), schema="k:str, v:float", pattern="3,9")


@pytest.mark.parametrize("places, text", [(0, "0.5"), (0, "2.5"), (2, "1.005"), (2, "2.675"), (2, "1.234567")])
def test_float_rounded_to_declared_places(tmp_path, places, text):
    same(tmp_path, fixed(3, 9)("a", text), schema=f"k:str, v:float#{places}", pattern="3,9")


@pytest.mark.parametrize("places", [0, 2, 4])
def test_decimal_rounded_to_declared_places(tmp_path, places):
    line = fixed(3, 9)
    texts = ["1.005", "2.675", "-1.005", "1e5", "100", "+5", "007", ".5"]
    data = b"".join(line(key, text) for key, text in zip("abcdefgh", texts))
    same(tmp_path, data, schema=f"k:str, v:Decimal#{places}", pattern="3,9")


def test_decimal_without_declared_places(tmp_path):
    line = fixed(3, 9)
    data = line("a", "1.50") + line("b", "0.00") + line("c", "100") + line("d", "7.125")
    same(tmp_path, data, schema="k:str, v:Decimal", pattern="3,9")


@pytest.mark.parametrize(
    "pattern, text",
    [
        ("%Y-%m-%d", "2024-01-31"),
        ("%Y-%m-%d", "2024-1-5"),
        ("%d/%m/%Y", "31/01/2024"),
        ("%Y-%m-%d %H:%M:%S", "2024-01-31 10:11:12"),
        ("%Y%m%d", "20240131"),
        ("", "2024-01-31"),
        ("", "2024-01-31 10:11:12"),
    ],
)
def test_dates(tmp_path, pattern, text):
    schema = f"k:str, v:datetime@{pattern}" if pattern else "k:str, v:datetime"
    same(tmp_path, fixed(3, 20)("a", text) + fixed(3, 20)("b", ""), schema=schema, pattern="3,20")


def test_text_that_looks_like_a_number_stays_text(tmp_path):
    line = fixed(5, 5)
    run = same(tmp_path, line("007", "1.50") + line("1e3", "+5"), schema="a:str, b:str", pattern="5,5", header=False)
    assert run.files["out.csv"] == b"007;1.50\n1e3;+5\n"


# ------------------------------------------------------------------
# Advanced separators
# ------------------------------------------------------------------

def test_number_separators_apply_to_decimal_columns_only_among_text(tmp_path):
    schema = "m:Decimal#2, n:Decimal, f:str, s:str"
    run = same(tmp_path, b"1.234,56   7,5  1.000abc\n", schema=schema, pattern="8,6,7,3", advanced_separator=True,
               thousands_separator=".", decimal_separator=",", header=False)
    assert run.files["out.csv"] == b"1234.56;7.5;1.000;abc\n"


@pytest.mark.parametrize(
    "data, config",
    [
        (b"1,234.56  7.5\n", {}),
        (b"1 234,56  7,5\n", {"thousands_separator": " ", "decimal_separator": ","}),
        (b"1234.56   7.5\n", {"thousands_separator": "", "decimal_separator": "."}),
    ],
)
def test_number_separators(tmp_path, data, config):
    same(tmp_path, data, schema="m:Decimal#2, n:Decimal", pattern="8,5", advanced_separator=True, **config)


def test_number_separators_leave_floats_that_need_none_alone(tmp_path):
    same(tmp_path, b"1234.56  7.5\n", schema="m:float, n:float", pattern="7,5", advanced_separator=True)


def test_number_separators_apply_to_float_columns(tmp_path):
    # v1 has pandas read float columns before it looks at the separators, and reads nothing.
    out = written(tmp_path, b"1.234,56  7,5\n", schema="m:float, n:float", pattern="8,5", advanced_separator=True,
                  thousands_separator=".", decimal_separator=",", header=False)
    assert out == b"1234.56;7.5\n"


def test_number_separators_are_left_alone_unless_asked_for(tmp_path):
    out = written(tmp_path, b"1,234.56  7.5\n", schema="m:Decimal#2, n:Decimal", pattern="8,5", reject=True,
                  thousands_separator=",", name="rej.csv")
    assert out.splitlines()[1].startswith(b"1,234.56;7.5;TYPE_CONVERSION;")


# ------------------------------------------------------------------
# Rows that cannot be read
# ------------------------------------------------------------------

BAD_SCHEMA = "i:int, s:str, d:datetime@%Y-%m-%d, f:float"
BAD_WIDTHS = "3,5,10,5"
bad = fixed(3, 5, 10, 5)
BAD = b"".join([
    bad(1, "alice", "2024-01-31", "10.5"), bad("x2", "bob", "2024-02-01", "20"), bad(3, "carol", "notadate", "30"),
    bad(4, "dave", "2024-03-01", ""), bad(5, "erin", "2024-03-02", "1,5"),
])


def test_unreadable_rows_leave_by_reject_with_the_reason(tmp_path):
    # v1 reads no row at all from this file: pandas fails on the first bad value and v1 swallows that.
    result, folder = v2(tmp_path, BAD, schema=BAD_SCHEMA, pattern=BAD_WIDTHS, reject=True)
    assert result.status == "success", result.error
    assert (folder / "out.csv").read_bytes() == b"i;s;d;f\n1;alice;2024-01-31;10.5\n4;dave;2024-03-01;\n"
    assert (folder / "rej.csv").read_bytes() == (
        b"i;s;d;f;errorCode;errorMessage\n"
        b"x2;bob;2024-02-01;20;TYPE_CONVERSION;Column 'i': could not convert string to float: 'x2'\n"
        b"3;carol;notadate;30;TYPE_CONVERSION;Column 'd': time data 'notadate' does not match format '%Y-%m-%d'\n"
        b"5;erin;2024-03-02;1,5;TYPE_CONVERSION;Column 'f': could not convert string to float: '1,5'\n"
    )


def test_unreadable_rows_are_dropped_when_no_reject_is_wired(tmp_path):
    out = written(tmp_path, BAD, schema=BAD_SCHEMA, pattern=BAD_WIDTHS)
    assert out == b"i;s;d;f\n1;alice;2024-01-31;10.5\n4;dave;2024-03-01;\n"


def test_unreadable_row_fails_the_job_when_errors_are_fatal(tmp_path):
    same(tmp_path, BAD, schema=BAD_SCHEMA, pattern=BAD_WIDTHS, die_on_error=True, fails=True)
    result, folder = v2(tmp_path / "direct", BAD, schema=BAD_SCHEMA, pattern=BAD_WIDTHS, die_on_error=True)
    assert result.status == "failed" and result.failed_component == "in"
    assert result.error == (
        "Schema/coercion failed for 3 row(s); first error: Column 'i': could not convert string to float: 'x2'"
        "; the row is line 2 of in.txt"
    )
    assert not (folder / "out.csv").exists()


def test_only_the_first_unreadable_column_of_a_row_is_named(tmp_path):
    out = written(tmp_path, bad("x", "a", "notadate", "zz"), schema=BAD_SCHEMA, pattern=BAD_WIDTHS, reject=True,
                  name="rej.csv")
    assert out.splitlines()[1] == b"x;a;notadate;zz;TYPE_CONVERSION;Column 'i': could not convert string to float: 'x'"


@pytest.mark.parametrize(
    "kind, text, reason",
    [
        ("bool", "maybe", "Column 'v': Cannot convert 'maybe' to bool"),
        ("Decimal#2", "abc", "Column 'v': could not convert string to Decimal: 'abc'"),
        ("datetime", "31.01.24", "Column 'v': time data '31.01.24' does not match format 'any known date format'"),
        ("int", "NA", "Column 'v': could not convert string to float: 'NA'"),
    ],
)
def test_reasons_by_type(tmp_path, kind, text, reason):
    data = fixed(3, 9)("a", text)
    out = written(tmp_path, data, schema=f"k:str, v:{kind}", pattern="3,9", reject=True, name="rej.csv")
    assert out.splitlines()[1] == f"a;{text};TYPE_CONVERSION;{reason}".encode()


def test_missing_value_where_none_is_allowed_is_rejected(tmp_path):
    data = b"  1abc 1.5\n   def 2.5\n  3ghi    \n"
    run = same(tmp_path, data, schema="i:int!, s:str, f:float!", pattern="3,3,4", reject=True)
    assert run.files["out.csv"] == b"i;s;f\n1;abc;1.5\n"
    assert run.files["rej.csv"] == (
        b"i;s;f;errorCode;errorMessage\n"
        b";def;2.5;SCHEMA_VIOLATION;Column 'i': non-nullable column has null\n"
        b"3;ghi;;SCHEMA_VIOLATION;Column 'f': non-nullable column has null\n"
    )


def test_missing_value_where_none_is_allowed_fails_when_errors_are_fatal(tmp_path):
    same(tmp_path, b"  1abc 1.5\n   def 2.5\n", schema="i:int!, s:str, f:float!", pattern="3,3,4", die_on_error=True,
         fails=True)


def test_missing_value_where_none_is_allowed_is_rejected_when_the_key_is_left_out(tmp_path):
    # v1 fails the job here: its base class takes errors as fatal when the key is absent.
    out = written(tmp_path, b"  1abc 1.5\n   def 2.5\n", schema="i:int!, s:str, f:float!", pattern="3,3,4",
                  die_on_error=ABSENT, reject=True, name="rej.csv")
    assert out.splitlines()[1] == b";def;2.5;SCHEMA_VIOLATION;Column 'i': non-nullable column has null"


@pytest.mark.parametrize("kind", ["datetime!@%Y-%m-%d", "bool!"])
def test_missing_date_or_bool_where_none_is_allowed_is_rejected(tmp_path, kind):
    # v1 lets an empty date or bool through: they are text when its base class looks for missing values.
    data = fixed(3, 10)("a", "")
    out = written(tmp_path, data, schema=f"k:str, v:{kind}", pattern="3,10", reject=True, name="rej.csv")
    assert out.splitlines()[1] == b"a;;SCHEMA_VIOLATION;Column 'v': non-nullable column has null"


def test_missing_decimal_where_none_is_allowed_is_rejected(tmp_path):
    line = fixed(3, 10)
    run = same(tmp_path, line("a", "1.5") + line("b", ""), schema="k:str, v:Decimal!#2", pattern="3,10", reject=True)
    assert run.files["out.csv"] == b"k;v\na;1.50\n"
    assert run.files["rej.csv"].splitlines()[1] == b"b;;SCHEMA_VIOLATION;Column 'v': non-nullable column has null"


def test_blank_text_where_none_may_be_missing_is_not_missing(tmp_path):
    run = same(tmp_path, b"abc   \nabcdef\n", schema="a:str!, b:str!", pattern="3,3")
    assert run.files["out.csv"] == b"a;b\nabc;\nabc;def\n"
    # When every field of the column is blank v1 holds the column as missing values and rejects every row.
    assert written(tmp_path / "all", b"abc   \n", schema="a:str!, b:str!", pattern="3,3") == b"a;b\nabc;\n"


def test_clean_file_with_a_reject_output_writes_an_empty_reject_file(tmp_path):
    # v1 stalls here (status "error") because the reject flow got nothing.
    result, folder = v2(tmp_path, b"  1abc 1.5\n", schema="i:int, s:str, f:float", pattern="3,3,4", reject=True)
    assert result.status == "success", result.error
    assert (folder / "rej.csv").read_bytes() == b"i;s;f;errorCode;errorMessage\n"
    assert (folder / "out.csv").read_bytes() == b"i;s;f\n1;abc;1.5\n"


def test_column_of_blank_fields_only_is_read_field_by_field(tmp_path):
    # v1 holds a column whose every field is blank as missing values: its bool reads true, not false.
    out = written(tmp_path, b"abc     \nxyz     \n", schema="s:str, b:bool", pattern="3,5", header=False)
    assert out == b"abc;false\nxyz;false\n"


def test_text_v1_takes_for_missing_is_kept(tmp_path):
    # v1 (pandas) empties NA, N/A, null, NULL, NaN, None and their like in every column.
    line = fixed(5, 5)
    out = written(tmp_path, line("NA", "null") + line("N/A", "None") + line("NULL", "NaN"), schema="a:str, b:str",
                  pattern="5,5", header=False)
    assert out == b"NA;null\nN/A;None\nNULL;NaN\n"


# ------------------------------------------------------------------
# Characters
# ------------------------------------------------------------------

def test_width_is_counted_in_characters(tmp_path):
    # v1 turns every character outside printable ASCII into a blank; v2 keeps the text.
    text = "\u00e9\u00e0\u00fc456789\nabcdefghi\n"
    for encoding in ("UTF-8", "ISO-8859-15"):
        out = written(tmp_path / encoding, text.encode(encoding), encoding=encoding, header=False)
        assert out == "\u00e9\u00e0\u00fc;4567;89\nabc;defg;hi\n".encode("utf-8")


@pytest.mark.parametrize("pattern_units", ["SYMBOLS", "BYTES"])
def test_pattern_units_are_ignored(tmp_path, pattern_units):
    same(tmp_path, b"abcdefghi\n", pattern_units=pattern_units)
    wide = "\u00e9\u00e0\u00fc456789\n".encode("utf-8")
    out = written(tmp_path / "wide", wide, pattern_units=pattern_units, header=False)
    assert out == "\u00e9\u00e0\u00fc;4567;89\n".encode("utf-8")


def test_control_characters_are_kept(tmp_path):
    out = written(tmp_path, b"a\x01cdefghi\n", header=False)
    assert out == b"a\x01c;defg;hi\n"


def test_trim_all_also_drops_other_white_space(tmp_path):
    data = "\u00a0bcdefg\u3000i\n".encode("utf-8")
    assert written(tmp_path / "on", data, trim_all=True, header=False) == b"bc;defg;i\n"
    assert written(tmp_path / "off", data, trim_all=False, header=False) == "\u00a0bc;defg;\u3000i\n".encode("utf-8")


def test_default_encoding_is_iso_8859_15(tmp_path):
    same(tmp_path, b"abcdefghi\n", encoding=ABSENT)
    out = written(tmp_path / "wide", "\u00e9bcdefg\u20aci\n".encode("iso-8859-15"), encoding=ABSENT, header=False)
    assert out == "\u00e9bc;defg;\u20aci\n".encode("utf-8")


@pytest.mark.parametrize("encoding", ["utf-8-sig", "UTF-16", "cp1252", "latin1"])
def test_other_encodings(tmp_path, encoding):
    same(tmp_path, "abcdefghi\n123456789\n".encode(encoding), encoding=encoding)


def test_byte_order_mark_is_not_part_of_the_first_field(tmp_path):
    # v1 counts the mark as the first character of the first line and cuts that line one place off.
    assert written(tmp_path, b"\xef\xbb\xbfabcdefghi\n123456789\n", header=False) == b"abc;defg;hi\n123;4567;89\n"
    same(tmp_path / "skipped", b"\xef\xbb\xbfHHHHHHHHH\nabcdefghi\n", header_rows=1)


def test_byte_that_is_not_utf_8_is_read_as_a_replacement_character(tmp_path):
    # v1 reads each such byte as a blank; either way the byte takes one place in its field.
    result, folder = v2(tmp_path, b"abcdefghi\ncaf\xe9efghi\n", encoding="UTF-8")
    assert result.status == "success", result.error
    assert (folder / "out.csv").read_bytes().splitlines()[-1].decode("utf-8", "replace").startswith("caf")


def test_unknown_encoding_is_refused():
    assert "encoding" in refused(encoding="NOPE-1")


# ------------------------------------------------------------------
# Files
# ------------------------------------------------------------------

@pytest.mark.parametrize("die_on_error", [False, ABSENT])
def test_missing_file_reads_no_rows(tmp_path, die_on_error):
    run = same(tmp_path, None, inputs={}, die_on_error=die_on_error)
    assert run.files["out.csv"] == b"a;b;c\n"


def test_missing_file_fails_the_reader_when_errors_are_fatal(tmp_path):
    same(tmp_path, None, inputs={}, die_on_error=True, fails=True)
    result, folder = v2(tmp_path / "direct", None, die_on_error=True)
    assert result.status == "failed" and result.failed_component == "in"
    assert result.error == "Input file not found: in.txt"
    assert not (folder / "out.csv").exists()


def test_missing_file_with_a_reject_output_writes_two_empty_files(tmp_path):
    result, folder = v2(tmp_path, None, reject=True)
    assert result.status == "success", result.error
    assert (folder / "out.csv").read_bytes() == b"a;b;c\n"
    assert (folder / "rej.csv").read_bytes() == b"a;b;c;errorCode;errorMessage\n"


def test_path_pattern_and_counts_can_come_from_the_context(tmp_path):
    made = cut(filepath="${context.dir}/context.name", pattern="${context.widths}", header_rows="${context.skip}",
               limit="context.most")
    made["context"] = {"Default": {
        "dir": {"value": ".", "type": "str"}, "name": {"value": "in.txt", "type": "str"},
        "widths": {"value": "3,4,2", "type": "str"}, "skip": {"value": "1", "type": "int"},
        "most": {"value": "1", "type": "str"},
    }}
    run = assert_matches_v1(made, {"in.txt": b"HHHHHHHHH\nabcdefghi\n123456789\n"}, tmp_path)
    assert run.files["out.csv"] == b"a;b;c\nabc;defg;hi\n"


def test_path_is_not_a_pattern(tmp_path):
    inputs = {"we[i]rd*.txt": b"abcdefghi\n", "weird.txt": b"zzzzzzzzz\n"}
    run = assert_matches_v1(cut(filepath="we[i]rd*.txt"), inputs, tmp_path)
    assert run.files["out.csv"] == b"a;b;c\nabc;defg;hi\n"


def test_large_file_keeps_every_row_in_order(tmp_path):
    line = fixed(8, 6, 10)
    data = b"".join(line(number, "name", "2024-01-31") for number in range(30000))
    schema = "n:int, s:str, d:datetime@%Y-%m-%d"
    run = same(tmp_path, data, schema=schema, pattern="8,6,10", header_rows=1, footer_rows=1, header=False)
    assert run.files["out.csv"] == b"".join(b"%d;name;2024-01-31\n" % number for number in range(1, 29999))


# ------------------------------------------------------------------
# What v2 says no to, and what it lets pass
# ------------------------------------------------------------------

def test_last_width_may_be_the_rest_of_the_line(tmp_path):
    # v1 refuses the star.
    out = written(tmp_path, b"abcdefghi and more  \nabc\n", pattern="3,4,*", header=False)
    assert out == b"abc;defg;hi and more\nabc;;\n"
    assert "pattern" in refused(pattern="3,*,2")


@pytest.mark.parametrize("pattern", ["3,4", "3,2,2,2", "3"])
def test_pattern_and_schema_must_agree(tmp_path, pattern):
    # v1 reads nothing: pandas refuses widths and names of different counts and v1 swallows the refusal.
    assert "pattern" in refused(pattern=pattern)


def test_reader_without_a_schema_is_refused():
    assert "schema" in refused(schema=None, write_schema=None)


def test_unknown_key_is_refused():
    assert "bogus" in refused(bogus=1)


def test_keys_v1_ignores_are_accepted(tmp_path):
    formats = [{"schema_column": "a", "size": "3", "padding_char": "' '", "align": "'L'"}]
    run = same(tmp_path, b"abcdefghi@@123456789\n", row_separator="@@", uncompress=True, process_long_row=True,
               advanced_option=True, formats=formats, trim_select=[{"column": "a", "trim": False}], check_date=True,
               header=False)
    assert run.files["out.csv"] == b"abc;defg;hi\n"


@pytest.mark.parametrize("type_name", ["FileInputPositional", "tFileInputPositional", "file_input_positional"])
def test_type_names(tmp_path, type_name):
    assert written(tmp_path, b"abcdefghi\n", type_name=type_name, header=False) == b"abc;defg;hi\n"


def test_v2_spelling_of_the_path():
    made = cut()
    made["components"][0]["config"]["path"] = made["components"][0]["config"].pop("filepath")
    load_job(made)


def test_every_key_the_converter_writes_is_accepted():
    load_job(cut(
        filepath="in.txt", row_separator="\\n", pattern="3,4,2", pattern_units="SYMBOLS", advanced_option=False,
        remove_empty_row=True, trim_all=True, encoding="ISO-8859-15", header_rows=0, footer_rows=0, limit="",
        die_on_error=False, process_long_row=False, advanced_separator=False, thousands_separator=",",
        decimal_separator=".", check_date=False, uncompress=False, formats=[], trim_select=[],
        tstatcatcher_stats=False, label="",
    ))
