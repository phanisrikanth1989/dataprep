"""Groovy-vs-Java expression safety unit tests (Plan 05.4-07).

Locks the disposition table in 05.4-GROOVY-AUDIT.md (D-07) by exercising
``Map._groovy_escape_expression`` against every character class enumerated
in the audit:

Classes audited:
  - ``$`` inside a double-quoted string literal  -> escape to ``\\$``
  - ``$`` in an identifier (outside string)      -> leave alone
  - backslash escape sequences inside strings    -> leave alone (tokenizer
    consumes both chars of ``\\"`` / ``\\\\`` so the string boundary is
    not mis-detected)
  - no string literal at all                     -> leave alone

R6 ("Total: $100" literal must round-trip through the compiled path)
is exercised end-to-end via the ``TestDollarEscapeE2e`` class which sends
``"Total: $100"`` through the live JVM bridge. This closes the
compiled-path coverage gap called out in SPEC.md R6 AC-05 (and the plan's
plan-checker warning that mandates a live-bridge round-trip).

Phase 05.4 plan 07 deliverable -- final character of the D-08 test matrix.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.v1.engine.components.transform.map import Map
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_map_instance():
    """Create a Map component with a minimal config (helper tests don't
    need to execute; they just call the helper method directly).
    """
    cfg = {
        "component_type": "Map",
        "die_on_error": True,
        "inputs": {
            "main": {
                "name": "row1", "filter": "", "activate_filter": False,
                "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE",
            },
            "lookups": [],
        },
        "variables": [],
        "outputs": [
            {
                "name": "out1", "is_reject": False,
                "inner_join_reject": False, "filter": "",
                "activate_filter": False,
                "columns": [
                    {"name": "id", "expression": "row1.id", "type": "int"},
                ],
                "catch_output_reject": False,
            },
        ],
    }
    return Map(
        component_id="tMap_groovy_safety",
        config=cfg,
        global_map=GlobalMap(),
        context_manager=ContextManager(),
    )


# ---------------------------------------------------------------------------
# TestDollarEscape -- D-07 audit row "$ inside a double-quoted string"
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDollarEscape:
    """`$` inside a double-quoted string literal must be escaped to `\\$`.

    Without this, Groovy interprets `"Total: $100"` as a GString that
    triggers identifier resolution on `100` (which is not a valid Groovy
    identifier and raises a parse error).
    """

    def test_dollar_in_string_literal_escaped(self):
        comp = _make_map_instance()
        result = comp._groovy_escape_expression('"Total: $100"')
        assert result == '"Total: \\$100"', (
            f"Expected '\"Total: \\$100\"'; got {result!r}"
        )

    def test_dollar_in_identifier_not_escaped(self):
        """`$` in identifier position (outside string) -- left alone."""
        comp = _make_map_instance()
        result = comp._groovy_escape_expression('$tmp + 1')
        assert result == '$tmp + 1', (
            f"Expected '$tmp + 1'; got {result!r}"
        )

    def test_dollar_at_string_end(self):
        """`$` immediately before the closing quote -- still escaped."""
        comp = _make_map_instance()
        result = comp._groovy_escape_expression('"price: $"')
        assert result == '"price: \\$"', (
            f"Expected '\"price: \\$\"'; got {result!r}"
        )

    def test_multiple_dollars(self):
        """Every `$` inside the string region is escaped."""
        comp = _make_map_instance()
        result = comp._groovy_escape_expression('"$a and $b"')
        assert result == '"\\$a and \\$b"', (
            f"Expected '\"\\$a and \\$b\"'; got {result!r}"
        )


# ---------------------------------------------------------------------------
# TestBackslashEscape -- D-07 audit row "backslash escape sequences"
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBackslashEscape:
    """Backslash escape sequences inside strings are passed through unchanged.

    The tokenizer consumes BOTH characters of an escape sequence as a
    unit so it cannot mis-detect the closing quote of the string. The
    test for ``\\"`` therefore proves the escape sequence is not eating
    a subsequent ``$``.
    """

    def test_backslash_sequence_in_string(self):
        """`\\n` inside a string is preserved as-is."""
        comp = _make_map_instance()
        # Python literal: '"line\\nbreak"'  -> 11 chars: " l i n e \\ n b r e a k "
        result = comp._groovy_escape_expression('"line\\nbreak"')
        # Result must equal the input (no change).
        assert result == '"line\\nbreak"', (
            f"Expected '\"line\\\\nbreak\"'; got {result!r}"
        )

    def test_escaped_quote_in_string(self):
        """`\\"` does NOT mis-detect string boundary -- subsequent `$` IS escaped."""
        comp = _make_map_instance()
        # Input: '"say \"hi\" $now"'  -- the \" pairs MUST NOT close the
        # string region; the $ must still get escaped.
        in_expr = '"say \\"hi\\" $now"'
        result = comp._groovy_escape_expression(in_expr)
        # The $now must be escaped because it is still inside the string.
        assert result == '"say \\"hi\\" \\$now"', (
            f"Expected backslash-escaped quote not to close string; "
            f"got {result!r}"
        )


# ---------------------------------------------------------------------------
# TestNoEscape -- D-07 audit rows that explicitly require leave-alone
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNoEscape:
    """Expressions without `$`-in-string content must round-trip unchanged."""

    def test_plain_string_no_special_chars(self):
        comp = _make_map_instance()
        assert comp._groovy_escape_expression('"hello"') == '"hello"'

    def test_empty_string(self):
        comp = _make_map_instance()
        assert comp._groovy_escape_expression('""') == '""'

    def test_no_string_literal(self):
        """No string literal in the expression -- nothing to escape."""
        comp = _make_map_instance()
        assert comp._groovy_escape_expression('row1.id + row2.code') == \
            'row1.id + row2.code'


# ---------------------------------------------------------------------------
# TestDollarEscapeE2e -- live-bridge round trip (R6 AC-05)
# ---------------------------------------------------------------------------


@pytest.mark.java
@pytest.mark.integration
class TestDollarEscapeE2e:
    """Closes the SPEC.md R6 AC-05 compiled-path round-trip gap.

    These tests configure a tMap output column with a literal expression
    such as ``"Total: $100"`` and run the component via the live JVM
    bridge. The output value must equal the literal string -- proving
    that ``_groovy_escape_expression`` correctly neutralised the GString
    interpolation trigger before the expression reached the Groovy
    compiler.
    """

    def _run_with_expr(self, java_bridge, col_expression):
        """Run a 1-row, 1-col map config and return the (single) output value."""
        config = {
            "component_type": "Map",
            "die_on_error": True,
            "inputs": {
                "main": {
                    "name": "row1", "filter": "", "activate_filter": False,
                    "matching_mode": "UNIQUE_MATCH",
                    "lookup_mode": "LOAD_ONCE",
                },
                "lookups": [],
            },
            "variables": [],
            "outputs": [
                {
                    "name": "out1", "is_reject": False,
                    "inner_join_reject": False, "filter": "",
                    "activate_filter": False,
                    "columns": [
                        {"name": "val", "expression": col_expression,
                         "type": "str"},
                    ],
                    "catch_output_reject": False,
                },
            ],
        }
        comp = Map(
            component_id="tMap_dollar_e2e",
            config=config,
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        comp.java_bridge = java_bridge
        main_df = pd.DataFrame([{"id": 1}])
        result = comp.execute({"row1": main_df})
        out = result.get("out1")
        assert out is not None and len(out) == 1
        return out["val"].iloc[0]

    def test_dollar_string_literal_round_trips(self, java_bridge):
        """SPEC.md R6 AC-05: ``"Total: $100"`` must produce the literal string."""
        val = self._run_with_expr(java_bridge,
                                  '{{java}}"Total: $100"')
        assert val == "Total: $100", (
            f"Expected 'Total: $100' (literal); got {val!r} -- the "
            f"_groovy_escape_expression helper did not neutralise the "
            f"GString interpolation trigger"
        )

    def test_dollar_multi_position_round_trips(self, java_bridge):
        """`$` at prefix, middle, end positions all round-trip."""
        cases = [
            ('{{java}}"prefix$value"', "prefix$value"),
            ('{{java}}"$start"', "$start"),
            ('{{java}}"middle$end"', "middle$end"),
        ]
        for expr, expected in cases:
            val = self._run_with_expr(java_bridge, expr)
            assert val == expected, (
                f"expr={expr!r}: expected {expected!r}, got {val!r}"
            )
