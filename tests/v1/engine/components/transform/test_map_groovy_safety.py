"""Groovy-vs-Java expression safety live-bridge round-trip (R6 AC-05).

The original module also exercised ``Map._groovy_escape_expression``
(a legacy instance method) against every character class enumerated in
the D-07 audit. The function is now ``groovy_escape_expression`` at
module level in ``map/map_compiled_script.py`` and its unit-level
character-class coverage lives in
``tests/v1/engine/components/transform/map/test_map_compiled_script.py``
(``test_escape_*``). The legacy unit classes were therefore deleted in
the Phase 8 test triage.

What stays here is the live-bridge end-to-end round-trip (SPEC.md R6
AC-05): a tMap configured with a literal expression that contains a
GString-interpolation trigger (``$`` inside a double-quoted string)
must produce the literal string at the output, proving the helper
correctly neutralised the trigger before the expression reached the
Groovy compiler.

Per project memory ``feedback_test_real_bridge`` the compiled-path
contract has to be verified through the live JVM, not via mocks.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.v1.engine.components.transform.map import Map
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap


@pytest.mark.java
@pytest.mark.integration
class TestDollarEscapeE2e:
    """Closes the SPEC.md R6 AC-05 compiled-path round-trip gap.

    These tests configure a tMap output column with a literal expression
    such as ``"Total: $100"`` and run the component via the live JVM
    bridge. The output value must equal the literal string -- proving
    that ``groovy_escape_expression`` correctly neutralised the GString
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
        comp.schema_inputs_map = {
            "row1": [{"name": "id", "type": "int", "nullable": True}],
        }
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
            f"groovy_escape_expression helper did not neutralise the "
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
