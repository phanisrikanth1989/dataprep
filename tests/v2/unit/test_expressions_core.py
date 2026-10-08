"""Python expressions translated to Polars: names, arithmetic, comparison, logic."""
import polars as pl
import pytest

from src.v2.errors import ExpressionError
from src.v2.expressions import Scope, translate


def ev(text, data, schema=None, **scope):
    """Translate ``text`` against one input row named row1 and evaluate it."""
    frame = pl.DataFrame(data, schema=schema)
    made = Scope.for_rows({"row1": dict(frame.schema)}, bare="row1", **scope)
    return frame.with_columns(translate(text, made).alias("r"))["r"].to_list()


PEOPLE = {
    "name": ["Ann", None, ""],
    "age": [30, 41, None],
    "pay": [1000.5, 2000.0, None],
    "active": [True, False, None],
}


# ------------------------------------------------------------------
# Names and literals
# ------------------------------------------------------------------

@pytest.mark.parametrize("text", ["row1.name", "row1['name']", 'row1["name"]', "name"])
def test_a_column_can_be_written_three_ways(text):
    assert ev(text, PEOPLE) == ["Ann", None, ""]


@pytest.mark.parametrize(
    "text, want",
    [("7", [7, 7, 7]), ("2.5", [2.5, 2.5, 2.5]), ("'x'", ["x", "x", "x"]),
     ("True", [True, True, True]), ("None", [None, None, None])],
)
def test_constants_become_a_value_for_every_row(text, want):
    assert ev(text, PEOPLE) == want


def test_string_constant_is_a_value_not_a_column_name():
    assert ev("'name'", PEOPLE) == ["name", "name", "name"]


def test_unknown_column_is_refused_with_the_columns_that_exist():
    with pytest.raises(ExpressionError) as caught:
        ev("row1.nmae", PEOPLE)
    assert "nmae" in str(caught.value)
    assert "name" in str(caught.value)


def test_unknown_row_is_refused():
    with pytest.raises(ExpressionError, match="row9"):
        ev("row9.name", PEOPLE)


# ------------------------------------------------------------------
# Arithmetic
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, want",
    [
        ("row1.a + row1.b", [9, -5]),
        ("row1.a - row1.b", [5, -9]),
        ("row1.a * row1.b", [14, -14]),
        ("row1.a / row1.b", [3.5, -3.5]),
        ("row1.a // row1.b", [3, -4]),
        ("row1.a % row1.b", [1, 1]),
        ("row1.a ** 2", [49, 49]),
        ("-row1.a", [-7, 7]),
        ("(row1.a + 1) * 2", [16, -12]),
    ],
)
def test_arithmetic_follows_python(text, want):
    assert ev(text, {"a": [7, -7], "b": [2, 2]}) == want


def test_adding_strings_joins_them():
    assert ev("row1.first + ' ' + row1.last", {"first": ["Ann"], "last": ["Lee"]}) == ["Ann Lee"]


def test_adding_text_and_a_number_is_refused_with_the_fix():
    with pytest.raises(ExpressionError, match=r"str\("):
        ev("row1.name + row1.age", PEOPLE)


def test_arithmetic_on_a_missing_value_gives_a_missing_value():
    assert ev("row1.age + 1", PEOPLE) == [31, 42, None]


# ------------------------------------------------------------------
# Comparison
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, want",
    [
        ("row1.age > 35", [False, True, None]),
        ("row1.age >= 30", [True, True, None]),
        ("row1.age < 35", [True, False, None]),
        ("row1.age <= 30", [True, False, None]),
    ],
)
def test_ordering_against_a_missing_value_is_missing(text, want):
    assert ev(text, PEOPLE) == want


def test_equality_treats_a_missing_value_as_a_value():
    assert ev("row1.name == 'Ann'", PEOPLE) == [True, False, False]
    assert ev("row1.name != 'Ann'", PEOPLE) == [False, True, True]


@pytest.mark.parametrize("text", ["row1.name == None", "row1.name is None"])
def test_missing_can_be_tested_with_equals_or_is(text):
    assert ev(text, PEOPLE) == [False, True, False]


@pytest.mark.parametrize("text", ["row1.name != None", "row1.name is not None"])
def test_present_can_be_tested_with_not_equals_or_is_not(text):
    assert ev(text, PEOPLE) == [True, False, True]


def test_chained_comparison_checks_both_bounds():
    assert ev("18 <= row1.n < 65", {"n": [17, 18, 64, 65]}) == [False, True, True, False]


def test_in_a_list_of_constants():
    assert ev("row1.code in ('A', 'B')", {"code": ["A", "C", None]}) == [True, False, False]
    assert ev("row1.code not in ['A', 'B']", {"code": ["A", "C", None]}) == [False, True, True]


def test_in_a_list_holding_none_matches_a_missing_value():
    assert ev("row1.code in ('A', None)", {"code": ["A", "C", None]}) == [True, False, True]


def test_text_in_text_is_a_substring_test_not_a_pattern():
    assert ev("'a.c' in row1.s", {"s": ["xa.cx", "xabcx", None]}) == [True, False, None]


# ------------------------------------------------------------------
# Logic and conditionals
# ------------------------------------------------------------------

def test_and_or_not_on_conditions():
    data = {"a": [1, 5, 9, None]}
    assert ev("row1.a > 2 and row1.a < 8", data) == [False, True, False, False]
    assert ev("row1.a < 2 or row1.a > 8", data) == [True, False, True, False]
    assert ev("not row1.a > 2", data) == [True, False, False, True]


def test_keyword_logic_on_whole_numbers_is_not_bitwise():
    # Python: 1 and 2 -> 2, 0 and 2 -> 0, 1 or 2 -> 1, 0 or 2 -> 2.
    data = {"x": [1, 0], "y": [2, 2]}
    assert ev("row1.x and row1.y", data) == [2, 0]
    assert ev("row1.x or row1.y", data) == [1, 2]
    assert ev("not row1.x", data) == [False, True]


def test_or_supplies_a_fallback_for_missing_and_empty_text():
    assert ev("row1.name or 'unknown'", PEOPLE) == ["Ann", "unknown", "unknown"]


def test_bare_value_as_a_condition_uses_python_truthiness():
    data = {"s": ["x", "", None], "n": [3, 0, None], "b": [True, False, None]}
    assert ev("'yes' if row1.s else 'no'", data) == ["yes", "no", "no"]
    assert ev("'yes' if row1.n else 'no'", data) == ["yes", "no", "no"]
    assert ev("'yes' if row1.b else 'no'", data) == ["yes", "no", "no"]


def test_conditional_expression_picks_a_branch_per_row():
    data = {"grade": ["A", "B", None], "pay": [100.0, 100.0, 100.0]}
    assert ev("row1.pay * 1.5 if row1.grade == 'A' else row1.pay", data) == [150.0, 100.0, 100.0]


def test_nested_conditionals():
    text = "'high' if row1.n > 10 else ('mid' if row1.n > 5 else 'low')"
    assert ev(text, {"n": [11, 6, 1]}) == ["high", "mid", "low"]


def test_guarded_expression_does_not_fail_on_the_rows_it_guards():
    assert ev("int(row1.s) if row1.s.isdigit() else 0", {"s": ["12", "x", None]}) == [12, 0, 0]


def test_conditional_mixing_text_and_number_gives_text():
    assert ev("row1.n if row1.n > 1 else 'n/a'", {"n": [5, 1]}) == ["5", "n/a"]


# ------------------------------------------------------------------
# What is refused
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "[x for x in row1.name]",
        "lambda v: v",
        "row1.name.encode('utf8')",
        "open('f')",
        "__import__('os')",
        "row1.age := 3",
        "x = 1",
        "row1.age +",
    ],
)
def test_python_that_cannot_become_polars_is_refused(text):
    with pytest.raises(ExpressionError):
        ev(text, PEOPLE)


def test_refusal_quotes_the_part_that_cannot_be_translated():
    with pytest.raises(ExpressionError) as caught:
        ev("row1.age + len([v for v in row1.name])", PEOPLE)
    assert "[v for v in row1.name]" in str(caught.value)


def test_java_leftover_gets_a_hint_instead_of_a_syntax_error():
    with pytest.raises(ExpressionError, match="Python"):
        ev("row1.age > 3 ? 'a' : 'b'", PEOPLE)
    with pytest.raises(ExpressionError, match="and"):
        ev("row1.age > 3 && row1.active", PEOPLE)
