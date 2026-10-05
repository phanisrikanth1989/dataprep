"""Column types: reading text into them, writing them as text, and making a
frame match a declared schema. The expected values are what v1 was observed
to produce for the same text (see the v1 delimited-bytes digest)."""
import datetime as dt
from decimal import Decimal

import polars as pl
import pytest

from src.v2.job.model import Column
from src.v2.types import chrono_format, conform, from_text, polars_type, to_text


def read(texts, column):
    """Parse texts as one column; returns (values, which were unreadable)."""
    frame = pl.DataFrame({"t": texts}, schema={"t": pl.String})
    value, bad = from_text(pl.col("t"), column)
    out = frame.select(value.alias("v"), bad.alias("bad"))
    return out["v"].to_list(), out["bad"].to_list()


def written(values, dtype, declared=None):
    frame = pl.DataFrame({"v": values}, schema={"v": dtype})
    return frame.select(to_text(pl.col("v"), dtype, declared))["v"].to_list()


# ------------------------------------------------------------------
# Reading text
# ------------------------------------------------------------------

def test_int_reads_whole_numbers_however_they_are_spelled():
    values, bad = read(["1", "1.0", "+5", " 7 ", "007", "1e5", "-0"], Column("v", "int"))
    assert values == [1, 1, 5, 7, 7, 100000, 0]
    assert not any(bad)


def test_int_drops_the_fraction_toward_zero():
    values, bad = read(["1.50", "2.9", "-2.9"], Column("v", "int"))
    assert values == [1, 2, -2]
    assert not any(bad)


def test_int_keeps_nineteen_digit_numbers_exact():
    values, _ = read(["1234567890123456789", "9223372036854775807"], Column("v", "int"))
    assert values == [1234567890123456789, 9223372036854775807]


def test_empty_or_blank_number_is_missing_not_unreadable():
    for type_name in ("int", "float", "datetime", "Decimal"):
        values, bad = read(["", "   "], Column("v", type_name))
        assert values == [None, None], type_name
        assert bad == [False, False], type_name


@pytest.mark.parametrize("text", ["abc", "1,000", "0x1A", "null", "NA", "None", "NaN", "inf"])
def test_int_marks_what_it_cannot_read(text):
    values, bad = read([text], Column("v", "int"))
    assert values == [None] and bad == [True]


def test_float_reads_numbers():
    values, bad = read(["1", "1.50", "30200.00", "1e5", " 7 ", "+5", "007", "-0.0"], Column("v", "float"))
    assert values == [1.0, 1.5, 30200.0, 100000.0, 7.0, 5.0, 7.0, -0.0]
    assert not any(bad)


def test_float_nan_text_is_missing_and_infinity_is_kept():
    values, bad = read(["NaN", "nan", "inf", "-inf"], Column("v", "float"))
    assert values == [None, None, float("inf"), float("-inf")]
    assert not any(bad)


@pytest.mark.parametrize("text", ["abc", "1,000", "null", "NA", "None"])
def test_float_marks_what_it_cannot_read(text):
    values, bad = read([text], Column("v", "float"))
    assert values == [None] and bad == [True]


def test_float_precision_rounds_half_to_even_as_v1_does():
    values, _ = read(["1.005", "2.675", "1.234567", "-0.004"], Column("v", "float", precision=2))
    assert values == [1.0, 2.68, 1.23, -0.0]
    values, _ = read(["0.5", "1.5", "2.5", "2.675"], Column("v", "float", precision=0))
    assert values == [0.0, 2.0, 2.0, 3.0]


def test_bool_reads_the_spellings_v1_reads():
    texts = "true false 1 0 yes no True False Yes No YES NO TRUE FALSE".split() + [" true "]
    values, bad = read(texts, Column("v", "bool"))
    assert values == [True, False] * 7 + [True]
    assert not any(bad)


def test_empty_bool_is_false_when_it_may_be_missing():
    assert read(["", "  "], Column("v", "bool")) == ([False, False], [False, False])


def test_empty_bool_is_missing_when_it_may_not_be():
    assert read([""], Column("v", "bool", nullable=False)) == ([None], [False])


@pytest.mark.parametrize("text", ["Y", "N", "t", "f", "on", "2", "NaN", "null"])
def test_bool_marks_what_it_cannot_read(text):
    assert read([text], Column("v", "bool")) == ([None], [True])


def test_datetime_reads_by_its_pattern():
    column = Column("v", "datetime", date_pattern="%Y-%m-%d")
    values, bad = read(["2024-01-31", "2024-1-5", " 2024-02-01 "], column)
    assert values == [dt.datetime(2024, 1, 31), dt.datetime(2024, 1, 5), dt.datetime(2024, 2, 1)]
    assert not any(bad)


@pytest.mark.parametrize("text", ["2024-02-30", "2024-01-31 10:00:00", "31/01/2024", "null", "junk"])
def test_datetime_marks_text_that_does_not_match_its_pattern(text):
    assert read([text], Column("v", "datetime", date_pattern="%Y-%m-%d")) == ([None], [True])


def test_datetime_nan_text_is_missing():
    assert read(["NaN"], Column("v", "datetime", date_pattern="%Y-%m-%d")) == ([None], [False])


def test_datetime_patterns_with_time_fraction_and_month_names():
    values, _ = read(["31/01/2024"], Column("v", "datetime", date_pattern="%d/%m/%Y"))
    assert values == [dt.datetime(2024, 1, 31)]
    values, _ = read(["2024-01-31 10:11:12.123", "2024-01-31 10:11:12.5"],
                     Column("v", "datetime", date_pattern="%Y-%m-%d %H:%M:%S.%f"))
    assert values == [dt.datetime(2024, 1, 31, 10, 11, 12, 123000), dt.datetime(2024, 1, 31, 10, 11, 12, 500000)]
    values, _ = read(["01-FEB-2024"], Column("v", "datetime", date_pattern="%d-%b-%Y"))
    assert values == [dt.datetime(2024, 2, 1)]


def test_datetime_without_a_pattern_tries_the_usual_ones():
    values, bad = read(["2024-01-31 10:11:12", "2024-01-31", "31/01/2024"], Column("v", "datetime"))
    assert values == [dt.datetime(2024, 1, 31, 10, 11, 12), dt.datetime(2024, 1, 31), dt.datetime(2024, 1, 31)]
    assert not any(bad)


def test_java_style_date_pattern_is_understood():
    values, _ = read(["31/01/2024 10:11:12"], Column("v", "datetime", date_pattern="dd/MM/yyyy HH:mm:ss"))
    assert values == [dt.datetime(2024, 1, 31, 10, 11, 12)]


def test_decimal_with_precision_rounds_half_up():
    values, bad = read(["1.005", "2.675", "-1.005", "1e5", "1E-7", "100", "1.50", "12.345"],
                       Column("v", "Decimal", precision=2))
    assert [str(v) for v in values] == ["1.01", "2.68", "-1.01", "100000.00", "0.00", "100.00", "1.50", "12.35"]
    assert not any(bad)
    values, _ = read(["1.50", "0.5", "2.5", "-1.005"], Column("v", "Decimal", precision=0))
    assert [str(v) for v in values] == ["2", "1", "3", "-1"]


def test_decimal_without_precision_keeps_ten_places():
    values, _ = read(["1.50", "100", "0.1234567891"], Column("v", "Decimal"))
    assert values == [Decimal("1.5"), Decimal("100"), Decimal("0.1234567891")]


def test_decimal_marks_what_it_cannot_read():
    assert read(["abc"], Column("v", "Decimal", precision=2)) == ([None], [True])


def test_str_is_kept_as_it_is():
    values, bad = read(["", "  ", "NaN", "null", " x "], Column("v", "str"))
    assert values == ["", "  ", "NaN", "null", " x "]
    assert not any(bad)


# ------------------------------------------------------------------
# Writing as text
# ------------------------------------------------------------------

def test_numbers_are_written_as_v1_writes_them():
    assert written([1, None, -7], pl.Int64) == ["1", None, "-7"]
    floats = [0.1, 2.5, 1e15, 1e16, 1e22, 0.0001, 30200.0, 100000.0, None]
    assert written(floats, pl.Float64) == [
        "0.1", "2.5", "1000000000000000.0", "1e+16", "1e+22", "0.0001", "30200.0", "100000.0", None,
    ]


def test_small_floats_are_written_with_an_exponent_as_python_writes_them():
    values = [1e-05, 5e-05, 1.2e-05, 9.99e-05, 1e-07, 1.5e-07, 5e-324, -3e-05, -2e-09, 0.0001, 0.00012345, 0.0, -0.0]
    assert written(values, pl.Float64) == [repr(value) for value in values]


def test_not_a_number_is_written_as_missing():
    assert written([float("nan"), 1.5], pl.Float64) == [None, "1.5"]


def test_bool_is_lower_case_when_declared_and_python_style_when_not():
    assert written([True, False, None], pl.Boolean, Column("v", "bool")) == ["true", "false", None]
    assert written([True, False, None], pl.Boolean) == ["True", "False", None]


def test_datetime_is_written_by_the_declared_pattern():
    values = [dt.datetime(2024, 1, 31), dt.datetime(1999, 12, 31, 1, 2, 3, 500000), None]
    assert written(values, pl.Datetime("us"), Column("v", "datetime", date_pattern="%d/%m/%Y %H:%M:%S")) == [
        "31/01/2024 00:00:00", "31/12/1999 01:02:03", None,
    ]
    assert written(values, pl.Datetime("us"), Column("v", "datetime", date_pattern="%Y-%m-%d %H:%M:%S.%f")) == [
        "2024-01-31 00:00:00.000000", "1999-12-31 01:02:03.500000", None,
    ]


def test_datetime_without_a_pattern_is_written_as_python_prints_it():
    values = [dt.datetime(2024, 1, 31), dt.datetime(1999, 12, 31, 1, 2, 3, 500000)]
    assert written(values, pl.Datetime("us")) == ["2024-01-31 00:00:00", "1999-12-31 01:02:03.500000"]


def test_decimal_is_written_to_the_declared_places():
    values = [Decimal("1.01"), Decimal("7.00"), None]
    assert written(values, pl.Decimal(38, 2), Column("v", "Decimal", precision=4)) == ["1.0100", "7.0000", None]
    assert written(values, pl.Decimal(38, 2), Column("v", "Decimal", precision=2)) == ["1.01", "7.00", None]


def test_decimal_without_declared_places_drops_trailing_zeros():
    values = [Decimal("1.50"), Decimal("7.00"), Decimal("30200.00"), Decimal("0.00"), Decimal("100")]
    assert written(values, pl.Decimal(38, 2), Column("v", "Decimal")) == ["1.5", "7", "30200", "0", "100"]
    assert written([Decimal("100"), Decimal("7")], pl.Decimal(38, 0), Column("v", "Decimal")) == ["100", "7"]


def test_decimal_nobody_declared_is_written_as_held():
    assert written([Decimal("1.50")], pl.Decimal(38, 2)) == ["1.50"]


# ------------------------------------------------------------------
# Patterns
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "pattern, parsing, expected",
    [
        ("%Y-%m-%d", True, "%Y-%m-%d"),
        ("%Y-%m-%d %H:%M:%S.%f", True, "%Y-%m-%d %H:%M:%S%.f"),
        ("%Y-%m-%d %H:%M:%S.%f", False, "%Y-%m-%d %H:%M:%S.%6f"),
        ("%H%M%S%f", False, "%H%M%S%6f"),
        ("yyyy-MM-dd HH:mm:ss", True, "%Y-%m-%d %H:%M:%S"),
        ("dd/MM/yy", True, "%d/%m/%y"),
        ("100%% %Y", False, "100%% %Y"),
    ],
)
def test_python_date_pattern_becomes_the_one_polars_wants(pattern, parsing, expected):
    assert chrono_format(pattern, parsing=parsing) == expected


# ------------------------------------------------------------------
# Matching a declared schema
# ------------------------------------------------------------------

def shaped(data, columns, **kwargs):
    frame, violation = conform(pl.LazyFrame(data), columns, **kwargs)
    return frame.collect(), violation


def test_declared_columns_come_first_in_declared_order_and_others_follow():
    out, _ = shaped({"b": [1], "extra": ["x"], "a": ["y"]}, [Column("a", "str"), Column("b", "int")])
    assert out.columns == ["a", "b", "extra"]


def test_declared_column_nobody_produced_is_added_empty():
    out, _ = shaped({"a": ["y"]}, [Column("a", "str"), Column("n", "int"), Column("d", "datetime")])
    assert out.rows() == [("y", None, None)]
    assert out.schema["n"] == pl.Int64 and out.schema["d"] == pl.Datetime("us")


def test_column_that_may_not_be_missing_is_added_as_zero():
    columns = [Column(name, type_name, nullable=False) for name, type_name in
               [("i", "int"), ("f", "float"), ("b", "bool"), ("s", "str"), ("d", "datetime"), ("m", "Decimal")]]
    out, _ = shaped({"a": ["y"]}, columns)
    assert out.select("i", "f", "b", "s", "d").rows() == [(0, 0.0, False, "", dt.datetime(1970, 1, 1))]
    assert out["m"].to_list() == [Decimal("0")]


def test_text_is_turned_into_the_declared_type():
    out, _ = shaped({"i": ["1", " 7 ", "x"], "f": ["1.5", "", "2"], "d": ["2024-01-31", "", "bad"]},
                    [Column("i", "int"), Column("f", "float"), Column("d", "datetime", date_pattern="%Y-%m-%d")])
    assert out.rows() == [(1, 1.5, dt.datetime(2024, 1, 31)), (7, None, None), (None, 2.0, None)]


def test_whole_numbers_declared_float_stay_whole_as_in_v1():
    out, _ = shaped({"f": [1, 2]}, [Column("f", "float")])
    assert out.schema["f"] == pl.Int64


def test_declared_str_leaves_the_values_alone():
    out, _ = shaped({"s": [1, 2]}, [Column("s", "str")])
    assert out.schema["s"] == pl.Int64


def test_fractions_declared_int_are_cut():
    out, _ = shaped({"i": [1.9, -1.9, None]}, [Column("i", "int")])
    assert out["i"].to_list() == [1, -1, None]


def test_declared_places_round_floats_and_decimals():
    out, _ = shaped({"f": [2.675, 1.005], "m": ["2.675", "1.005"]},
                    [Column("f", "float", precision=2), Column("m", "Decimal", precision=2)])
    assert out["f"].to_list() == [2.68, 1.0]
    assert [str(v) for v in out["m"].to_list()] == ["2.68", "1.01"]


def test_missing_value_where_none_is_allowed_is_reported_per_row():
    columns = [Column("a", "int", nullable=False), Column("b", "str", nullable=False), Column("c", "str")]
    frame, violation = conform(pl.LazyFrame({"a": [1, None, 3], "b": ["x", "y", None], "c": [None, None, None]}), columns)
    assert violation is not None
    assert frame.select(violation.alias("why")).collect()["why"].to_list() == [
        None,
        "Column 'a': non-nullable column has null",
        "Column 'b': non-nullable column has null",
    ]


def test_schema_that_allows_missing_values_reports_nothing():
    _, violation = conform(pl.LazyFrame({"a": [1]}), [Column("a", "int")])
    assert violation is None


def test_error_columns_passing_through_are_renamed_as_v1_renames_them():
    out, _ = shaped({"id": [1], "errorCode": ["E"], "errorMessage": ["m"]}, [Column("id", "int")], rename_errors=True)
    assert out.columns == ["id", "errorCode_user", "errorMessage_user"]


def test_polars_type_of_each_declared_type():
    assert polars_type(Column("v", "str")) == pl.String
    assert polars_type(Column("v", "int")) == pl.Int64
    assert polars_type(Column("v", "float")) == pl.Float64
    assert polars_type(Column("v", "bool")) == pl.Boolean
    assert polars_type(Column("v", "datetime")) == pl.Datetime("us")
    assert polars_type(Column("v", "date")) == pl.Date
    assert polars_type(Column("v", "Decimal", precision=2)) == pl.Decimal(38, 2)
    assert polars_type(Column("v", "Decimal")) == pl.Decimal(38, 10)


@pytest.mark.parametrize(
    "dtype, declared",
    [
        (pl.Decimal(38, 2), Column("v", "datetime")), (pl.Int64, Column("v", "datetime")), (pl.Float64, Column("v", "date")),
        (pl.Boolean, Column("v", "datetime")), (pl.Datetime("us"), Column("v", "int")), (pl.Date, Column("v", "float")),
        (pl.Datetime("us"), Column("v", "Decimal", precision=2)), (pl.Date, Column("v", "bool")),
    ],
)
def test_declared_type_the_values_cannot_become_is_an_error_when_the_plan_is_built(dtype, declared):
    from src.v2.errors import ConfigurationError

    with pytest.raises(ConfigurationError, match="column 'v' is declared"):
        conform(pl.LazyFrame(schema={"v": dtype}), [declared])


def test_frame_with_no_columns_gets_the_declared_columns_and_no_rows():
    frame, _ = conform(pl.LazyFrame(), [Column("a", "int"), Column("b", "str", nullable=False)])
    out = frame.collect()
    assert out.columns == ["a", "b"] and out.height == 0


def test_floats_and_decimals_are_turned_into_each_other_through_their_digits():
    # Polars' own casts between the two are off by the last digit; v1 goes through the printed number.
    def conformed(value, dtype, column):
        frame, _ = conform(pl.LazyFrame({"v": [value]}, schema={"v": dtype}), [column])
        return frame.collect()["v"].to_list()[0]

    assert conformed(1000.125, pl.Float64, Column("v", "Decimal", precision=2)) == Decimal("1000.13")
    assert conformed(123456789.125, pl.Float64, Column("v", "Decimal")) == Decimal("123456789.125")
    assert conformed(Decimal("12345678901234.567"), pl.Decimal(38, 3), Column("v", "float")) == 12345678901234.566
    assert conformed(float("nan"), pl.Float64, Column("v", "Decimal", precision=2)) is None
