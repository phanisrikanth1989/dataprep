"""Python expressions translated to Polars: functions, methods and names."""
import datetime
from decimal import Decimal

import polars as pl
import pytest

from src.v2.errors import ExpressionError
from src.v2.expressions import Scope, translate


def ev(text, data, schema=None, **scope):
    """Translate ``text`` against one input row named row1 and evaluate it."""
    frame = pl.DataFrame(data, schema=schema)
    made = Scope.for_rows({"row1": dict(frame.schema)}, bare="row1", **scope)
    return frame.with_columns(translate(text, made).alias("r"))["r"].to_list()


def kind(text, data, schema=None, **scope):
    frame = pl.DataFrame(data, schema=schema)
    made = Scope.for_rows({"row1": dict(frame.schema)}, bare="row1", **scope)
    return frame.with_columns(translate(text, made).alias("r"))["r"].dtype


# ------------------------------------------------------------------
# Builtins
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, data, want",
    [
        ("len(row1.s)", {"s": ["abc", "", None]}, [3, 0, None]),
        ("str(row1.n)", {"n": [5, -3, None]}, ["5", "-3", None]),
        ("str(row1.f)", {"f": [1.5, 2.0]}, ["1.5", "2.0"]),
        ("str(row1.b)", {"b": [True, False, None]}, ["True", "False", None]),
        ("int(row1.f)", {"f": [1.9, -1.9]}, [1, -1]),
        ("int(row1.s)", {"s": [" 42 ", "-7"]}, [42, -7]),
        ("int(row1.b)", {"b": [True, False]}, [1, 0]),
        ("float(row1.s)", {"s": ["1.5", " 2 "]}, [1.5, 2.0]),
        ("float(row1.n)", {"n": [2]}, [2.0]),
        ("bool(row1.s)", {"s": ["x", "", None]}, [True, False, False]),
        ("round(row1.f)", {"f": [0.5, 1.5, 2.5, -0.5, 1.4]}, [0, 2, 2, 0, 1]),
        ("round(row1.f, 2)", {"f": [1.234, 1.236]}, [1.23, 1.24]),
        ("abs(row1.n)", {"n": [-3, 4]}, [3, 4]),
        ("min(row1.a, row1.b)", {"a": [1, 5], "b": [4, 2]}, [1, 2]),
        ("max(row1.a, row1.b, 3)", {"a": [1, 5], "b": [4, 2]}, [4, 5]),
    ],
)
def test_builtin_functions(text, data, want):
    assert ev(text, data) == want


def test_round_without_digits_gives_a_whole_number():
    assert kind("round(row1.f)", {"f": [1.5]}) == pl.Int64


def test_len_of_a_number_is_refused():
    with pytest.raises(ExpressionError, match="len"):
        ev("len(row1.n)", {"n": [1]})


# ------------------------------------------------------------------
# Text
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, want",
    [
        ("row1.s.upper()", ["  AB-CD  ", None]),
        ("row1.s.lower()", ["  ab-cd  ", None]),
        ("row1.s.strip()", ["Ab-Cd", None]),
        ("row1.s.lstrip()", ["Ab-Cd  ", None]),
        ("row1.s.rstrip()", ["  Ab-Cd", None]),
        ("row1.s.strip().strip('Ad')", ["b-C", None]),
        ("row1.s.strip().startswith('Ab')", [True, None]),
        ("row1.s.strip().endswith(('x', 'Cd'))", [True, None]),
        ("row1.s.strip().replace('-', '+')", ["Ab+Cd", None]),
        ("row1.s.strip().split('-')[0]", ["Ab", None]),
        ("row1.s.strip().split('-')[1]", ["Cd", None]),
        ("row1.s.strip().split('-')[5]", [None, None]),
        ("row1.s.strip().zfill(7)", ["00Ab-Cd", None]),
        ("row1.s.strip().rjust(7, '*')", ["**Ab-Cd", None]),
        ("row1.s.strip().ljust(7, '*')", ["Ab-Cd**", None]),
        ("row1.s.strip().count('b')", [1, None]),
        ("row1.s.strip().find('-')", [2, None]),
        ("row1.s.strip().find('zz')", [-1, None]),
        ("len(row1.s.strip())", [5, None]),
    ],
)
def test_text_methods(text, want):
    assert ev(text, {"s": ["  Ab-Cd  ", None]}) == want


@pytest.mark.parametrize(
    "text, want",
    [
        ("row1.s.title()", ["Hello World"]),
        ("row1.s.capitalize()", ["Hello world"]),
        ("row1.s.isdigit()", [False]),
        ("row1.s.isalpha()", [False]),
        ("row1.s.replace(' ', '').isalpha()", [True]),
        ("row1.s.replace(' ', '').isalnum()", [True]),
    ],
)
def test_more_text_methods(text, want):
    assert ev(text, {"s": ["hello WORLD"]}) == want


@pytest.mark.parametrize(
    "text, want",
    [
        ("row1.s[0:3]", ["abc"]),
        ("row1.s[2:4]", ["cd"]),
        ("row1.s[:2]", ["ab"]),
        ("row1.s[2:]", ["cdef"]),
        ("row1.s[-2:]", ["ef"]),
        ("row1.s[:-1]", ["abcde"]),
        ("row1.s[1]", ["b"]),
        ("row1.s[-1]", ["f"]),
        ("row1.s[::-1]", ["fedcba"]),
        ("row1.s[:10].strip().upper()", ["ABCDEF"]),
    ],
)
def test_slicing_text(text, want):
    assert ev(text, {"s": ["abcdef"]}) == want


def test_slice_with_a_step_other_than_reversal_is_refused():
    with pytest.raises(ExpressionError):
        ev("row1.s[::2]", {"s": ["abcdef"]})


def test_f_string_joins_text_and_numbers():
    data = {"first": ["Ann"], "n": [5], "f": [1.5]}
    assert ev("f'{row1.first}-{row1.n}/{row1.f}'", data) == ["Ann-5/1.5"]


def test_f_string_with_a_format_spec_is_refused():
    with pytest.raises(ExpressionError):
        ev("f'{row1.f:.2f}'", {"f": [1.5]})


def test_format_method_and_join():
    data = {"a": ["x"], "b": ["y"]}
    assert ev("'{}-{}'.format(row1.a, row1.b)", data) == ["x-y"]
    assert ev("'|'.join([row1.a, row1.b, 'z'])", data) == ["x|y|z"]


@pytest.mark.parametrize(
    "text, hint",
    [
        ("row1.s.equals('a')", "=="),
        ("row1.s.length()", "len("),
        ("row1.s.toUpperCase()", ".upper()"),
        ("row1.s.trim()", ".strip()"),
        ("row1.s == null", "None"),
    ],
)
def test_java_habits_are_refused_with_the_python_spelling(text, hint):
    with pytest.raises(ExpressionError) as caught:
        ev(text, {"s": ["a"]})
    assert hint in str(caught.value)


def test_text_method_on_a_number_is_refused():
    with pytest.raises(ExpressionError, match="text"):
        ev("row1.n.upper()", {"n": [1]})


# ------------------------------------------------------------------
# re
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, want",
    [
        (r"re.sub(r'\s+', '_', row1.s)", ["a_b_c", "ab@cd"]),
        (r"re.sub(r'(\w+)@(\w+)', r'\2 at \1', row1.s)", ["a  b c", "cd at ab"]),
        (r"re.sub('@', '$', row1.s)", ["a  b c", "ab$cd"]),
        (r"re.sub('B', 'x', row1.s, flags=re.I)", ["a  x c", "ax@cd"]),
        (r"'yes' if re.search(r'@', row1.s) else 'no'", ["no", "yes"]),
        (r"re.search(r'@', row1.s) is not None", [False, True]),
        (r"re.search(r'@', row1.s) is None", [True, False]),
        (r"bool(re.match(r'b', row1.s))", [False, False]),
        (r"bool(re.match(r'a', row1.s))", [True, True]),
        (r"bool(re.fullmatch(r'\w+@\w+', row1.s))", [False, True]),
        (r"re.search(r'(\w+)@', row1.s).group(1)", [None, "ab"]),
    ],
)
def test_regular_expressions(text, want):
    assert ev(text, {"s": ["a  b c", "ab@cd"]}) == want


def test_pattern_polars_cannot_run_is_refused_when_the_job_loads():
    with pytest.raises(ExpressionError, match="pattern"):
        ev(r"re.sub(r'a(?=b)', '', row1.s)", {"s": ["ab"]})


def test_pattern_must_be_a_constant():
    with pytest.raises(ExpressionError, match="constant"):
        ev("re.sub(row1.p, '', row1.s)", {"s": ["ab"], "p": ["a"]})


# ------------------------------------------------------------------
# math
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, want",
    [
        ("math.floor(row1.f)", [1, -2]),
        ("math.ceil(row1.f)", [2, -1]),
        ("math.trunc(row1.f)", [1, -1]),
        ("math.fabs(row1.f)", [1.7, 1.2]),
        ("math.pow(row1.f, 2) > 2", [True, False]),
    ],
)
def test_math_functions(text, want):
    assert ev(text, {"f": [1.7, -1.2]}) == want


def test_math_sqrt_and_constants():
    assert ev("math.sqrt(row1.n)", {"n": [9.0]}) == [3.0]
    assert ev("math.pi", {"n": [1]}) == [3.141592653589793]


# ------------------------------------------------------------------
# Dates
# ------------------------------------------------------------------

WHEN = {"d": [datetime.datetime(2024, 3, 15, 13, 45, 30)], "s": ["2024-03-15"]}


@pytest.mark.parametrize(
    "text, want",
    [
        ("row1.d.year", [2024]),
        ("row1.d.month", [3]),
        ("row1.d.day", [15]),
        ("row1.d.hour", [13]),
        ("row1.d.minute", [45]),
        ("row1.d.second", [30]),
        ("row1.d.weekday()", [4]),
        ("row1.d.strftime('%d/%m/%Y')", ["15/03/2024"]),
        ("datetime.datetime.strptime(row1.s, '%Y-%m-%d')", [datetime.datetime(2024, 3, 15)]),
        ("datetime.strptime(row1.s, '%Y-%m-%d').date()", [datetime.date(2024, 3, 15)]),
        ("row1.d.date()", [datetime.date(2024, 3, 15)]),
        ("row1.d + datetime.timedelta(days=1)", [datetime.datetime(2024, 3, 16, 13, 45, 30)]),
        ("row1.d - timedelta(hours=2)", [datetime.datetime(2024, 3, 15, 11, 45, 30)]),
        ("(row1.d - datetime.datetime(2024, 3, 1)).days", [14]),
        ("row1.d > datetime.datetime(2024, 1, 1)", [True]),
    ],
)
def test_dates(text, want):
    assert ev(text, WHEN) == want


def test_now_is_fixed_once_for_the_run():
    values = ev("datetime.datetime.now()", {"n": [1, 2]})
    assert values[0] == values[1]
    assert isinstance(values[0], datetime.datetime)


# ------------------------------------------------------------------
# Decimal and missing values the pandas way
# ------------------------------------------------------------------

def test_decimal_constant_keeps_its_scale():
    assert ev("row1.amt + Decimal('0.10')", {"amt": [Decimal("1.25")]}) == [Decimal("1.35")]


@pytest.mark.parametrize(
    "text, want",
    [
        ("pd.isna(row1.s)", [False, True]),
        ("pd.notna(row1.s)", [True, False]),
        ("pd.isnull(row1.f)", [False, True]),
        ("'none' if pd.isna(row1.s) else row1.s", ["a", "none"]),
    ],
)
def test_pandas_missing_value_tests(text, want):
    assert ev(text, {"s": ["a", None], "f": [1.0, None]}) == want


def test_isna_counts_a_float_nan_as_missing():
    assert ev("pd.isna(row1.f)", {"f": [1.0, float("nan"), None]}) == [False, True, True]


# ------------------------------------------------------------------
# Context, globalMap, variables, rows and routines
# ------------------------------------------------------------------

def test_context_values_are_read_three_ways():
    data = {"n": [1, 5]}
    assert ev("row1.n > context.limit", data, context={"limit": 3}) == [False, True]
    assert ev("row1.n > context['limit']", data, context={"limit": 3}) == [False, True]
    assert ev("str(row1.n) + context.suffix", data, context={"suffix": "x"}) == ["1x", "5x"]


def test_unknown_context_variable_is_refused_by_name():
    with pytest.raises(ExpressionError, match="limt"):
        ev("row1.n > context.limt", {"n": [1]}, context={"limit": 3})


def test_global_map_get_with_and_without_a_default():
    data = {"n": [1]}
    assert ev("globalMap.get('rows')", data, global_map={"rows": 7}) == [7]
    assert ev("globalMap.get('missing', 5)", data, global_map={}) == [5]
    assert ev("globalMap['rows'] + row1.n", data, global_map={"rows": 7}) == [8]


def test_variable_is_read_through_var():
    data = {"n": [2, 3]}
    assert ev("Var.double + 1", data, variables={"double": pl.col("n") * 2}) == [5, 7]
    assert ev("Var['double']", data, variables={"double": pl.col("n") * 2}) == [4, 6]


def test_undefined_variable_is_refused():
    with pytest.raises(ExpressionError, match="total"):
        ev("Var.total", {"n": [1]})


def test_lookup_row_columns_are_held_under_the_row_name():
    frame = pl.DataFrame({"id": [1], "row2.name": ["x"]})
    scope = Scope.for_rows({"row1": {"id": pl.Int64}, "row2": {"name": pl.String}})
    out = frame.with_columns(translate("row2.name + str(row1.id)", scope).alias("r"))
    assert out["r"].to_list() == ["x1"]


def test_routine_is_called_with_expressions_and_returns_one():
    routines = {"Tax": {"vat": lambda amount, rate=0.2: amount * rate}}
    data = {"n": [10.0]}
    assert ev("Tax.vat(row1.n)", data, routines=routines) == [2.0]
    assert ev("routines.Tax.vat(row1.n, 0.5)", data, routines=routines) == [5.0]


def test_unknown_routine_function_is_refused():
    with pytest.raises(ExpressionError, match="gst"):
        ev("Tax.gst(row1.n)", {"n": [1.0]}, routines={"Tax": {"vat": lambda a: a}})


@pytest.mark.filterwarnings("ignore::polars.exceptions.PolarsInefficientMapWarning")
def test_routine_that_runs_python_per_row_is_refused():
    routines = {"Slow": {"twice": lambda value: value.map_elements(lambda v: v * 2, return_dtype=pl.Float64)}}
    with pytest.raises(ExpressionError, match="row by row"):
        ev("Slow.twice(row1.n)", {"n": [1.0]}, routines=routines)


def test_routine_that_does_not_return_an_expression_is_refused():
    with pytest.raises(ExpressionError, match="Polars expression"):
        ev("Bad.f(row1.n)", {"n": [1.0]}, routines={"Bad": {"f": lambda value: 3}})
