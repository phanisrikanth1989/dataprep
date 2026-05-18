"""Groovy script generation for tMap (active + reject scripts, $ escape)."""
from src.v1.engine.components.transform.map.map_compiled_script import (
    groovy_escape_expression,
)


def test_escape_no_strings_passes_through():
    assert groovy_escape_expression("row1.amount + 5") == "row1.amount + 5"


def test_escape_dollar_inside_double_quoted_string():
    # Groovy GString interpolation: $identifier triggers eval. Escape it.
    assert groovy_escape_expression('"Total: $100"') == '"Total: \\$100"'


def test_escape_dollar_outside_string_unchanged():
    # $ outside a string is a legal Java/Groovy identifier char; leave alone
    assert groovy_escape_expression("var.$amount + 5") == "var.$amount + 5"


def test_escape_handles_escaped_quotes_inside_string():
    # \" inside a string is a 2-char escape; must not break out of string
    src = '"he said \\"hi\\" and $5"'
    assert groovy_escape_expression(src) == '"he said \\"hi\\" and \\$5"'


def test_escape_handles_single_quoted_strings_as_non_strings():
    # Single quotes are Groovy char literals; treat as outside-string region
    assert groovy_escape_expression("'$abc'") == "'$abc'"
