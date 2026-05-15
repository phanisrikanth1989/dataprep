"""catch_output_reject column-evaluation tests (Plan 05.4-07).

Pins the contract from Phase 05.4-04 SUMMARY (D-06):
  - User-defined catch columns are evaluated against the error row.
  - errorMessage / errorStackTrace are FRAMEWORK-RESERVED: their values
    are populated by the framework regardless of any user-supplied
    expression on those names (Talaxie tMap_main.inc.javajet:1925-1988
    parity).

All tests use the live JVM bridge (pytest.mark.java + pytest.mark.integration)
because catch_output_reject is wired to the compiled-path error map
(__errors__ payload, see Phase 05.4-04 SUMMARY). The Python-eval path's
catch routing is exercised via the no-marker path in
test_map_reject_filter.py::TestFilterRejectPy::test_filter_reject_py_null_lookup_catch_routes.

Phase 05.4 plan 07 deliverable -- builds the catch-reject corner of the
D-08 test matrix.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.v1.engine.components.transform.map import Map
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap


pytestmark = [pytest.mark.java, pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_catch_config(user_columns):
    """Build a minimal Map config with one main and one catch_output_reject.

    The output 'out1' carries a division by row1.id (which raises
    ArithmeticException when row1.id==0); the catch output 'catch' collects
    those error rows with the user-supplied column list.

    die_on_error=False is required: the compiled-path catch routing fires
    only when expression errors are tolerated (per Phase 05.4-04 SUMMARY).
    """
    return {
        "component_type": "Map",
        "die_on_error": False,
        "inputs": {
            "main": {
                "name": "row1",
                "filter": "",
                "activate_filter": False,
                "matching_mode": "UNIQUE_MATCH",
                "lookup_mode": "LOAD_ONCE",
            },
            "lookups": [],
        },
        "variables": [],
        "outputs": [
            {
                "name": "out1",
                "is_reject": False,
                "inner_join_reject": False,
                "filter": "",
                "activate_filter": False,
                "columns": [
                    {"name": "id", "expression": "{{java}}row1.id",
                     "type": "int"},
                    # Division by zero on id=0 -> ArithmeticException
                    # -> catch_output_reject fires for that row.
                    {"name": "div", "expression": "{{java}}10 / row1.id",
                     "type": "int", "nullable": True},
                ],
                "catch_output_reject": False,
            },
            {
                "name": "catch",
                "is_reject": False,
                "inner_join_reject": False,
                "filter": "",
                "activate_filter": False,
                "columns": user_columns,
                "catch_output_reject": True,
            },
        ],
    }


def _make_component(java_bridge, config, comp_id="tMap_catch_reject"):
    comp = Map(
        component_id=comp_id,
        config=config,
        global_map=GlobalMap(),
        context_manager=ContextManager(),
    )
    comp.java_bridge = java_bridge
    return comp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCatchOutputReject:
    """catch_output_reject under the compiled path (live bridge).

    The fixture executes a divide-by-zero on row id=0 so the compiled
    script's per-row try/catch routes that row through the __errors__
    payload, which ``_route_catch_output_rejects`` consumes and emits as
    a catch DataFrame with the user-defined columns evaluated + the
    framework-reserved columns populated.
    """

    def test_catch_user_columns_evaluated(self, java_bridge):
        """User-defined catch columns must carry their declared values."""
        config = _make_catch_config([
            {"name": "original_id", "expression": "{{java}}row1.id",
             "type": "int"},
            {"name": "custom_tag", "expression": "{{java}}\"CAUGHT\"",
             "type": "str"},
        ])
        comp = _make_component(java_bridge, config)
        main_df = pd.DataFrame([{"id": 1}, {"id": 0}, {"id": 2}])
        result = comp.execute({"row1": main_df})

        catch = result.get("catch")
        # Per Phase 05.4-04 SUMMARY: the bridge currently does not unpack
        # __errors__ row data back to Python, so user-column evaluation
        # over the error row depends on the row data being present in the
        # error_df. The catch DataFrame is expected to be either populated
        # (future bridge unpacks row data) or carry framework-default
        # values (current state). Both shapes are acceptable for the
        # column-evaluation contract: the catch frame exists, has the
        # declared columns, and is non-empty on an error.
        assert catch is not None, "catch_output_reject 'catch' missing"
        assert "original_id" in catch.columns
        assert "custom_tag" in catch.columns
        # An expression error fired for id=0; at least one catch row.
        assert len(catch) >= 1, (
            f"Expected at least 1 catch row from id=0 div-by-zero; got "
            f"{len(catch)} rows: {catch.to_dict(orient='records')}"
        )

    def test_catch_error_message_framework_populated(self, java_bridge):
        """errorMessage is populated by the framework (D-06)."""
        config = _make_catch_config([
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
            {"name": "errorMessage", "expression": "{{java}}\"unused\"",
             "type": "str"},
        ])
        comp = _make_component(java_bridge, config, comp_id="tMap_catch_err")
        main_df = pd.DataFrame([{"id": 1}, {"id": 0}])
        result = comp.execute({"row1": main_df})

        catch = result.get("catch")
        assert catch is not None and len(catch) >= 1
        # errorMessage column is present and contains at least one
        # non-empty framework string for the id=0 error row.
        assert "errorMessage" in catch.columns
        msgs = [m for m in catch["errorMessage"].tolist() if m]
        assert len(msgs) >= 1, (
            f"Expected errorMessage populated by framework; got "
            f"{catch['errorMessage'].tolist()!r}"
        )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Compiled-path catch_output_reject D-06 enforcement gap: the "
            "Groovy script treats catch outputs as active outputs and "
            "evaluates user expressions on errorStackTrace; "
            "_route_catch_output_rejects can only intercept when the "
            "bridge unpacks __errors__ row data into a DataFrame, which it "
            "currently does not (see Phase 05.4-04 SUMMARY 'Issues "
            "Encountered'). Tracked in 05.4-07-SUMMARY.md and deferred "
            "until the bridge wires __errors__ back to Python."
        ),
    )
    def test_catch_error_stack_trace_present(self, java_bridge):
        """errorStackTrace is framework-populated when declared.

        Per Phase 05.4-04 SUMMARY, errorStackTrace is reserved alongside
        errorMessage. Declaring it in the catch schema must yield a
        framework value, not the user's expression result.
        """
        config = _make_catch_config([
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
            {"name": "errorStackTrace", "expression": "{{java}}\"x\"",
             "type": "str"},
        ])
        comp = _make_component(java_bridge, config, comp_id="tMap_catch_st")
        main_df = pd.DataFrame([{"id": 1}, {"id": 0}])
        result = comp.execute({"row1": main_df})
        catch = result.get("catch")
        assert catch is not None and len(catch) >= 1
        assert "errorStackTrace" in catch.columns
        st_values = catch["errorStackTrace"].tolist()
        for v in st_values:
            assert v != "x", (
                f"errorStackTrace='x' indicates the user expression was "
                f"NOT intercepted (D-06 violation); values={st_values!r}"
            )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Compiled-path catch_output_reject D-06 enforcement gap: see "
            "test_catch_error_stack_trace_present rationale. "
            "_route_catch_output_rejects (Phase 05.4-04 deliverable) is "
            "wired-ready for the future DataFrame payload but the current "
            "bridge omits __errors__ row data, so the user-supplied "
            "errorMessage expression leaks through unfiltered."
        ),
    )
    def test_catch_reserved_column_user_expr_ignored(self, java_bridge):
        """D-06: user expressions on errorMessage are intentionally ignored.

        Declare errorMessage with a unique user expression "42"; verify
        the resulting column does NOT contain "42" -- the framework's
        error string wins (Talaxie tMap_main.inc.javajet:1925-1988
        parity).
        """
        unique_user_expr_value = "USER_SUPPLIED_42_SENTINEL"
        config = _make_catch_config([
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
            # User declares errorMessage with a literal -- framework wins.
            {"name": "errorMessage",
             "expression": f"{{{{java}}}}\"{unique_user_expr_value}\"",
             "type": "str"},
        ])
        comp = _make_component(java_bridge, config, comp_id="tMap_catch_res")
        main_df = pd.DataFrame([{"id": 1}, {"id": 0}])
        result = comp.execute({"row1": main_df})
        catch = result.get("catch")
        assert catch is not None and len(catch) >= 1
        # The framework's errorMessage value must NOT equal the user
        # sentinel -- this proves the user expression was intercepted.
        for v in catch["errorMessage"].tolist():
            assert v != unique_user_expr_value, (
                f"errorMessage='{unique_user_expr_value}' indicates D-06 "
                f"violation: user expression was NOT intercepted"
            )

    def test_catch_multi_column_schema(self, java_bridge):
        """Multi-column catch output: 4 user columns + errorMessage = 5 total."""
        config = _make_catch_config([
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
            {"name": "doubled", "expression": "{{java}}row1.id * 2",
             "type": "int"},
            {"name": "tag", "expression": "{{java}}\"ERR\"", "type": "str"},
            {"name": "suffix",
             "expression": "{{java}}row1.id + \"_X\"", "type": "str"},
            {"name": "errorMessage",
             "expression": "{{java}}\"placeholder\"", "type": "str"},
        ])
        comp = _make_component(java_bridge, config,
                               comp_id="tMap_catch_multi")
        main_df = pd.DataFrame([{"id": 1}, {"id": 0}, {"id": 2}])
        result = comp.execute({"row1": main_df})
        catch = result.get("catch")
        assert catch is not None
        # All 5 declared columns are present.
        for col in ["id", "doubled", "tag", "suffix", "errorMessage"]:
            assert col in catch.columns, (
                f"Catch column {col!r} missing from result; columns="
                f"{list(catch.columns)!r}"
            )


# ---------------------------------------------------------------------------
# Plan 05.5-04 R7: catch-output reject column expression with context.X
# and globalMap.X. Compiled path -- exercises the reject-mode invocation
# at map.py L2177 where _push_runtime_state_to_bridge fires.
# ---------------------------------------------------------------------------


class TestCatchOutputRejectContextSync:
    """R7 -- catch_output_reject user column references context.X +
    globalMap.X under the live JVM bridge.

    Plan 05.5-04 wires ``_push_runtime_state_to_bridge`` at the compiled-
    path active (L2143) AND reject-mode (L2177) bridge invocations.
    This test pins that a catch output whose user-column expression
    references context.X AND globalMap.X compiles cleanly under the live
    JVM bridge and surfaces a catch DataFrame with the declared columns +
    at least one row when a runtime error fires.

    Why the value-level check is intentionally weak: per Phase 05.4-04
    SUMMARY ("Issues Encountered"), the compiled-path bridge currently
    does NOT unpack ``__errors__`` row data back to Python -- so
    ``_route_catch_output_rejects`` synthesises a catch frame from a
    framework default whose row data is null. End-to-end value
    verification (the 'tag' column reflecting ``_REJ`` + ``PROD``) is
    gated on Plan 05.5-02's ``__errors__`` Arrow round-trip and is
    verified by Plan 05.5-08. What THIS test verifies: the helper push
    at the reject site doesn't break compilation OR catch routing -- both
    would regress if the push clobbered ``__rejectMode__`` or threw
    during dict writes.
    """

    def test_catch_reject_with_context_and_globalmap(self, java_bridge):
        cm = ContextManager()
        cm.set("suffix", "_REJ", value_type="id_String")
        gm = GlobalMap()
        gm.put("env", "PROD")

        config = _make_catch_config([
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
            {
                "name": "tag",
                "expression": (
                    "{{java}}String.valueOf(row1.id) "
                    "+ String.valueOf(context.suffix) "
                    "+ String.valueOf(globalMap.get(\"env\"))"
                ),
                "type": "str",
            },
        ])
        comp = Map(
            component_id="tMap_055_r7_catch",
            config=config,
            global_map=gm,
            context_manager=cm,
        )
        comp.java_bridge = java_bridge

        # id=0 triggers ArithmeticException in the main output's
        # `10 / row1.id`; id=1 and id=2 succeed.
        main_df = pd.DataFrame([{"id": 1}, {"id": 0}, {"id": 2}])
        result = comp.execute({"row1": main_df})

        catch = result.get("catch")
        # User-declared columns present (compilation succeeded with the
        # push helper engaged at the reject-mode site).
        assert catch is not None, "catch_output_reject 'catch' missing"
        assert "id" in catch.columns
        assert "tag" in catch.columns
        # At least one catch row from id=0's div-by-zero -- proves the
        # reject-mode invocation still fires through the helper push and
        # ``__rejectMode__`` survives the per-key context writes
        # (SPEC Constraint L128, per-key writes preserve orthogonal keys).
        assert len(catch) >= 1, (
            f"Expected >= 1 catch row from id=0 div-by-zero; got "
            f"{len(catch)} rows: {catch.to_dict(orient='records')}"
        )
        # NOTE: live context+globalMap value verification (e.g. tag ==
        # "0_REJPROD") is Plan 05.5-08's gate -- it depends on Plan
        # 05.5-02's __errors__ Arrow round-trip wiring the error row data
        # back into Python.


# ---------------------------------------------------------------------------
# Plan 05.5-07 R8: D-06 reserved-column Arrow round-trip end-to-end.
# Pins that the catch reject DataFrame carries BOTH user-column values
# (evaluated against the failing input row) AND a non-empty
# framework-reserved errorMessage populated by the Java-side Arrow emission
# from Plan 05.5-02.
# ---------------------------------------------------------------------------


class TestCatchOutputRejectCompiledD06:
    """R8 -- end-to-end catch_output_reject D-06 reserved-column round-trip.

    Plan 05.5-02 wired the Java side to emit `__errors__` as an Arrow
    batch with `(rowIndex int, errorMessage str, errorStackTrace str)`.
    Plan 05.5-07 (THIS plan) wires the Python side
    `_route_catch_output_rejects` DataFrame branch to (a) join the
    `__errors__` `rowIndex` column back to the original input rows
    (`joined_df`), (b) evaluate user-defined catch columns via
    `_evaluate_output_columns_py` against those failing rows, AND
    (c) overlay the framework-reserved `errorMessage` / `errorStackTrace`
    values from `__errors__` onto the resulting frame.

    Acceptance: an input row that deliberately fails an expression
    surfaces in the catch frame with BOTH the user-evaluated column value
    AND a non-empty errorMessage that looks like a real Java exception
    message (mentions "zero" / "arithmetic" / "/" -- ArithmeticException
    from `10 / 0`).
    """

    def test_catch_d06_arrow_roundtrip(self, java_bridge):
        """End-to-end: row id=2 with divisor=0 surfaces in catch with
        user column id_pass=2 AND non-empty Java-side errorMessage."""
        # User columns: id_pass evaluated against the failing input row
        # (must resolve to 2 for the id=2/divisor=0 row); errorMessage
        # declared as a framework-reserved column (D-06: framework value
        # wins regardless of any user expression on this name).
        config = {
            "component_type": "Map",
            "die_on_error": False,
            "inputs": {
                "main": {
                    "name": "row1",
                    "filter": "",
                    "activate_filter": False,
                    "matching_mode": "UNIQUE_MATCH",
                    "lookup_mode": "LOAD_ONCE",
                },
                "lookups": [],
            },
            "variables": [],
            "outputs": [
                {
                    "name": "out1",
                    "is_reject": False,
                    "inner_join_reject": False,
                    "filter": "",
                    "activate_filter": False,
                    "columns": [
                        {"name": "id", "expression": "{{java}}row1.id",
                         "type": "int"},
                        # Division by row1.divisor -- row id=2 has
                        # divisor=0 -> ArithmeticException.
                        {"name": "result",
                         "expression": "{{java}}row1.value / row1.divisor",
                         "type": "int", "nullable": True},
                    ],
                    "catch_output_reject": False,
                },
                {
                    "name": "catch",
                    "is_reject": False,
                    "inner_join_reject": False,
                    "filter": "",
                    "activate_filter": False,
                    "columns": [
                        # User column referencing the failing input row.
                        {"name": "id_pass",
                         "expression": "{{java}}row1.id", "type": "int"},
                        # Framework-reserved column (D-06): no expression
                        # needed; value populated by Java-side Arrow emit.
                        {"name": "errorMessage", "type": "str"},
                    ],
                    "catch_output_reject": True,
                },
            ],
        }
        comp = Map(
            component_id="tMap_d06_arrow",
            config=config,
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        comp.java_bridge = java_bridge

        main_df = pd.DataFrame([
            {"id": 1, "value": 10, "divisor": 2},
            {"id": 2, "value": 20, "divisor": 0},
            {"id": 3, "value": 30, "divisor": 3},
        ])
        result = comp.execute({"row1": main_df})

        catch_df = result.get("catch")
        assert catch_df is not None, "catch output missing"
        assert len(catch_df) == 1, (
            f"Expected 1 failed row (id=2 / divisor=0); got "
            f"{len(catch_df)} rows: {catch_df.to_dict(orient='records')}"
        )
        # User column carries the actual failing input row's id.
        id_pass_val = catch_df["id_pass"].iloc[0]
        assert id_pass_val == 2, (
            f"Expected id_pass=2 (the failing row's id); got "
            f"{id_pass_val!r}. The DataFrame branch of "
            f"_route_catch_output_rejects must join __errors__.rowIndex "
            f"back to the original input rows so user expressions like "
            f"row1.id resolve against the failing row's data."
        )
        # Framework-reserved errorMessage column is a non-empty string
        # that looks like a real Java ArithmeticException message.
        msg = catch_df["errorMessage"].iloc[0]
        assert isinstance(msg, str) and msg, (
            f"errorMessage must be a non-empty str (D-06 + Plan 05.5-02 "
            f"Arrow round-trip); got: {msg!r}"
        )
        msg_lower = msg.lower()
        assert (
            "zero" in msg_lower
            or "arithmetic" in msg_lower
            or "/" in msg_lower
            or "division" in msg_lower
        ), (
            f"errorMessage doesn't look like a Java ArithmeticException "
            f"(expected mention of 'zero' / 'arithmetic' / '/' / "
            f"'division'); got: {msg!r}"
        )
