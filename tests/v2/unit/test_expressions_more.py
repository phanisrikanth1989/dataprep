"""Python expressions translated to Polars: the remaining functions and edges."""
import datetime
from decimal import Decimal

import pytest

from src.v2.errors import ExpressionError

from .test_expressions_functions import WHEN, ev


@pytest.mark.parametrize(
    "text, data, want",
    [
        ("row1.s.isspace()", {"s": ["  ", "a"]}, [True, False]),
        ("row1.s.isdecimal()", {"s": ["12", "x"]}, [True, False]),
        ("row1.s.split()[1]", {"s": ["a   b"]}, ["b"]),
        ("len(row1.s.split('-'))", {"s": ["a-b"]}, [2]),
        ("math.log(row1.n)", {"n": [1.0]}, [0.0]),
        ("math.log(row1.n, 10)", {"n": [100.0]}, [2.0]),
        ("math.log10(row1.n)", {"n": [100.0]}, [2.0]),
        ("math.exp(row1.n)", {"n": [0.0]}, [1.0]),
        ("math.isnan(row1.f)", {"f": [float("nan"), 1.0]}, [True, False]),
        ("int(row1.amt)", {"amt": [Decimal("1.99"), Decimal("-1.99")]}, [1, -1]),
        ("round(row1.n)", {"n": [3, -4]}, [3, -4]),
        ("decimal.Decimal('1.5')", {"n": [1]}, [Decimal("1.5")]),
        ("datetime.date(2024, 3, 15)", {"n": [1]}, [datetime.date(2024, 3, 15)]),
        ("datetime.date(row1.y, 1, 1)", {"y": [2024]}, [datetime.date(2024, 1, 1)]),
        ("date(2024, 3, 15)", {"n": [1]}, [datetime.date(2024, 3, 15)]),
        ("re.sub('a', 'b', row1.s, 1)", {"s": ["aaa"]}, ["baa"]),
        (r"re.sub(r'\d', 'x', row1.s, count=1)", {"s": ["a12"]}, ["ax2"]),
        (r"re.sub(r'\d', r'\g<0>!', row1.s)", {"s": ["a12"]}, ["a1!2!"]),
        (r"re.sub(r'\d', r'\\', row1.s)", {"s": ["a1"]}, ["a\\"]),
        (r"re.sub(r'\d', '$', row1.s)", {"s": ["a1"]}, ["a$"]),
        (r"bool(re.search(r'A', row1.s, re.I | re.M))", {"s": ["a12"]}, [True]),
    ],
)
def test_remaining_functions(text, data, want):
    assert ev(text, data) == want


@pytest.mark.parametrize(
    "text, want",
    [
        ("row1.d.isoweekday()", [5]),
        ("row1.d.time()", [datetime.time(13, 45, 30)]),
        ("row1.d.microsecond", [0]),
        ("(row1.d - datetime.datetime(2024, 3, 15)).total_seconds()", [49530.0]),
        ("row1.d + timedelta(1)", [datetime.datetime(2024, 3, 16, 13, 45, 30)]),
        ("row1.d + timedelta(days=1, hours=1)", [datetime.datetime(2024, 3, 16, 14, 45, 30)]),
    ],
)
def test_remaining_date_forms(text, want):
    assert ev(text, WHEN) == want


def test_today_is_a_date():
    assert isinstance(ev("date.today()", {"n": [1]})[0], datetime.date)


@pytest.mark.parametrize(
    "text, data",
    [
        ("row1.s[-3:-1]", {"s": ["abcdef"]}),
        ("row1.n[0]", {"n": [1]}),
        ("row1.s.split('-')[0:1]", {"s": ["a-b"]}),
        ("min(row1.n)", {"n": [1]}),
        ("round(row1.f, -1)", {"f": [15.0]}),
        ("round(row1.s)", {"s": ["a"]}),
        ("row1.n in row1.s", {"n": [1], "s": ["a"]}),
        ("row1.s in ('a', 1)", {"s": ["a"]}),
        ("row1.n is 1", {"n": [1]}),
        ("row1.s == row1.n", {"n": [1], "s": ["a"]}),
        ("row1.s * 2", {"s": ["a"]}),
        ("-row1.s", {"s": ["a"]}),
        ("~row1.n", {"n": [1]}),
        ("row1.n @ row1.n", {"n": [1]}),
        ("row1", {"n": [1]}),
        ("b'x'", {"n": [1]}),
        ("row1.n.year", {"n": [1]}),
        ("row1.n.days", {"n": [1]}),
        ("row1.n.nothing", {"n": [1]}),
        ("row1.n.strftime('%Y')", {"n": [1]}),
        ("row1.s.strip(row1.s)", {"s": ["a"]}),
        ("row1.s.startswith(1)", {"s": ["a"]}),
        ("row1.s.zfill('x')", {"s": ["a"]}),
        ("row1.s.join(['a'])", {"s": ["a"]}),
        ("'-'.join(row1.s)", {"s": ["a"]}),
        ("row1.s.format(1)", {"s": ["a"]}),
        ("'{0}'.format(row1.s)", {"s": ["a"]}),
        ("len(row1.s, 1)", {"s": ["a"]}),
        ("len(s=row1.s)", {"s": ["a"]}),
        ("Decimal('abc')", {"n": [1]}),
        ("Decimal(row1.n)", {"n": [1]}),
        ("math.sqrt(row1.s)", {"s": ["a"]}),
        ("math.cos(row1.n)", {"n": [1.0]}),
        ("re.sub('a', 'b')", {"s": ["a"]}),
        ("re.sub('a', 'b', row1.n)", {"n": [1]}),
        (r"re.sub(r'\d', 'x', row1.s, count=2)", {"s": ["a12"]}),
        ("re.sub('a', 'b', row1.s, flags=re.DEBUG)", {"s": ["a"]}),
        ("re.sub('a', 'b', row1.s, bogus=1)", {"s": ["a"]}),
        ("re.search('a')", {"s": ["a"]}),
        ("re.search('a', row1.n)", {"n": [1]}),
        ("datetime.date(2024, 2, 30)", {"n": [1]}),
        ("datetime.datetime.strptime(row1.n, '%Y')", {"n": [1]}),
        ("timedelta(1, days=2)", {"n": [1]}),
        ("timedelta(1, 2, 3, 4)", {"n": [1]}),
        ("(lambda: 1)()", {"n": [1]}),
        ("os.getcwd()", {"n": [1]}),
        ("row1.s.group(1)", {"s": ["a"]}),
        ("row1.d if row1.n else 1", {"n": [1], "d": [datetime.date(2024, 1, 1)]}),
        ("row1.n and row1.d", {"n": [1], "d": [datetime.date(2024, 1, 1)]}),
        ("'x' if row1.xs else 'y'", {"xs": [[1]]}),
        ("{{java}}row1.n + 1", {"n": [1]}),
    ],
)
def test_more_python_that_is_refused(text, data):
    with pytest.raises(ExpressionError):
        ev(text, data)


def test_date_used_as_a_condition_is_true_unless_missing():
    data = {"d": [datetime.date(2024, 1, 1), None]}
    assert ev("'set' if row1.d else 'unset'", data) == ["set", "unset"]


def test_none_as_a_condition_is_false():
    assert ev("1 if None else 2", {"n": [1]}) == [2]


def test_mixed_value_logic_is_refused_when_the_types_cannot_be_one_column():
    with pytest.raises(ExpressionError):
        ev("row1.s or row1.d", {"s": ["a"], "d": [datetime.date(2024, 1, 1)]})


def test_text_on_the_left_of_a_text_and_number_conditional_stays_text():
    assert ev("'n/a' if row1.n > 1 else row1.n", {"n": [5, 1]}) == ["n/a", "1"]


def test_global_map_attribute_form():
    assert ev("globalMap.rows + 1", {"n": [1]}, global_map={"rows": 7}) == [8]


def test_empty_f_string_is_empty_text():
    assert ev("f''", {"n": [1]}) == [""]


def test_routine_failure_is_reported_with_the_routine_name():
    def boom(value):
        raise ValueError("bad rate")

    with pytest.raises(ExpressionError, match="Rates.fx"):
        ev("Rates.fx(row1.n)", {"n": [1.0]}, routines={"Rates": {"fx": boom}})


def test_routine_takes_named_arguments():
    routines = {"Tax": {"vat": lambda amount, rate=0.2: amount * rate}}
    assert ev("Tax.vat(row1.n, rate=0.5)", {"n": [10.0]}, routines=routines) == [5.0]


def test_error_carries_the_expression_and_the_reason():
    with pytest.raises(ExpressionError) as caught:
        ev("row1.n + open('f')", {"n": [1]})
    assert caught.value.expression == "row1.n + open('f')"
    assert "open" in caught.value.reason
