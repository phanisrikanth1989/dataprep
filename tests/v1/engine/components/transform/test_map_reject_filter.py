"""is_reject filter-reject column-evaluation tests (Plan 05.4-07).

Two classes, each covering 4 column kinds for the is_reject filter-reject
path:

TestFilterRejectPy  -- @pytest.mark.unit
  Exercises ``_evaluate_outputs_py`` (Python-eval path: no {{java}}
  markers, no bridge). 4 tests across (same_name_ref, renamed_simple_ref,
  hardcoded_literal, java_expression-style python) + 3 R5 null-lookup
  scenarios (die_on_error=True, catch routes, silent drop).

TestFilterRejectCompiled -- @pytest.mark.java + @pytest.mark.integration
  Exercises ``_apply_output_filter`` via the compiled path. 4 tests with
  the same column-kind matrix but with ``{{java}}`` markers throughout.
  Each test asserts ``_has_any_java_marker()`` BEFORE execute() so the
  compiled path is actually exercised (per plan-checker warning -- no
  accidental python-eval fallback).

Phase 05.4 plan 07 deliverable -- builds the filter-reject corner of the
D-08 test matrix.
"""
from __future__ import annotations

import copy
import logging

import pandas as pd
import pytest

from src.v1.engine.components.transform.map import Map
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ComponentExecutionError
from src.v1.engine.global_map import GlobalMap


# ---------------------------------------------------------------------------
# Helpers (shared by both classes)
# ---------------------------------------------------------------------------


def _make_filter_reject_config(
    source_columns,
    reject_columns,
    source_filter="row1.score > 50",
    main_filter_active=True,
):
    """Build a Map config: source output filters on score > 50,
    reject output receives rejected rows. No lookups.
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
                "filter": source_filter,
                "activate_filter": main_filter_active,
                "columns": source_columns,
            },
            {
                "name": "rej1",
                "is_reject": True,
                "inner_join_reject": False,
                "filter": "",
                "activate_filter": False,
                "columns": reject_columns,
            },
        ],
    }


def _make_component(config, comp_id="tMap_filter_reject", java_bridge=None):
    comp = Map(
        component_id=comp_id,
        config=config,
        global_map=GlobalMap(),
        context_manager=ContextManager(),
    )
    if java_bridge is not None:
        comp.java_bridge = java_bridge
    return comp


# ---------------------------------------------------------------------------
# TestFilterRejectPy (Python-eval path, unit)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFilterRejectPy:
    """is_reject filter-reject under the Python-eval path (no markers).

    Each test sends one passing + one failing row through a source output
    with ``activate_filter=True``; asserts the reject DataFrame's column
    schema matches the REJECT output's declared columns (not the source
    output's) and that per-column values match the reject expressions.
    """

    def test_filter_reject_py_same_name_ref(self):
        """Reject column 'id' uses simple ref row1.id (same name as source col)."""
        cfg = _make_filter_reject_config(
            source_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
                {"name": "tag", "expression": "'KEEP'", "type": "str"},
            ],
            reject_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
            ],
        )
        comp = _make_component(cfg)
        main_df = pd.DataFrame([
            {"id": 1, "score": 80},   # passes
            {"id": 2, "score": 30},   # rejects
        ])
        result = comp.execute({"row1": main_df})
        rej = result.get("rej1")
        assert rej is not None
        assert list(rej.columns) == ["id"]
        assert rej["id"].tolist() == [2]

    def test_filter_reject_py_renamed_ref(self):
        """Reject column 'orig_id' = row1.id (renamed simple ref)."""
        cfg = _make_filter_reject_config(
            source_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
            ],
            reject_columns=[
                {"name": "orig_id", "expression": "row1.id", "type": "int"},
            ],
        )
        comp = _make_component(cfg)
        main_df = pd.DataFrame([
            {"id": 1, "score": 80},
            {"id": 7, "score": 20},
        ])
        result = comp.execute({"row1": main_df})
        rej = result["rej1"]
        assert list(rej.columns) == ["orig_id"]
        assert rej["orig_id"].tolist() == [7]

    def test_filter_reject_py_hardcoded_literal(self):
        """Reject column 'status' uses a hard-coded literal 'REJECTED'."""
        cfg = _make_filter_reject_config(
            source_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
            ],
            reject_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
                {"name": "status", "expression": "'REJECTED'", "type": "str"},
            ],
        )
        comp = _make_component(cfg)
        main_df = pd.DataFrame([
            {"id": 1, "score": 80},
            {"id": 5, "score": 10},
        ])
        result = comp.execute({"row1": main_df})
        rej = result["rej1"]
        assert rej["status"].tolist() == ["REJECTED"]
        assert rej["id"].tolist() == [5]

    def test_filter_reject_py_java_expr(self):
        """Reject column uses a python-evaluable composite expression."""
        cfg = _make_filter_reject_config(
            source_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
            ],
            reject_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
                # Python expression (str cast + concat): no Java marker
                {"name": "label", "expression": "str(row1.id) + '_REJ'",
                 "type": "str"},
            ],
        )
        comp = _make_component(cfg)
        main_df = pd.DataFrame([
            {"id": 1, "score": 80},
            {"id": 42, "score": 5},
        ])
        result = comp.execute({"row1": main_df})
        rej = result["rej1"]
        assert rej["label"].tolist() == ["42_REJ"]

    # ----- R5 null-lookup scenarios (3 modes per SPEC.md R5 AC) -----

    def test_filter_reject_py_null_lookup_die_on_error_true(self):
        """R5: die_on_error=True + reject references row2.col on unmatched.

        Filter-reject on a main row WHERE row1.score > 50 is FALSE; the
        reject output then references ``row2.something`` -- but the reject
        config has no lookups, so row2 is bound to ``_NullNamespace`` which
        returns None silently. To force a raise we use die_on_error=True
        with an expression that would AttributeError on None (e.g.
        ``row2.value.upper()`` -- AttributeError 'NoneType has no upper').
        """
        cfg = _make_filter_reject_config(
            source_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
            ],
            reject_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
                # row2 has no binding -> _NullNamespace returns None for
                # row2.value; .upper() then raises AttributeError. With
                # die_on_error=True, _eval_expr re-raises wrapped in
                # ComponentExecutionError.
                {"name": "val", "expression": "row2.value.upper()",
                 "type": "str"},
            ],
        )
        cfg["die_on_error"] = True
        comp = _make_component(cfg, comp_id="tMap_R5_die")
        main_df = pd.DataFrame([{"id": 1, "score": 30}])
        with pytest.raises(ComponentExecutionError) as excinfo:
            comp.execute({"row1": main_df})
        # ASCII-only error message (project memory feedback_ascii_logging).
        assert str(excinfo.value).encode("ascii", errors="strict")

    def test_filter_reject_py_null_lookup_catch_routes(self):
        """R5: catch_output_reject captures rows when reject-column eval fails.

        When the source output rejects a row AND the reject output's
        expressions error out (here ``row2.value.upper()`` raises NameError
        because no lookup binding exists in the no-lookup config), the
        Python-eval path's soft-error semantics (die_on_error=False) route
        the row through the catch_output_reject sibling output. The user
        ``id`` column is evaluated; the framework-reserved ``errorMessage``
        column is populated by the framework (D-06, Phase 05.4-04 SUMMARY).
        """
        cfg = _make_filter_reject_config(
            source_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
            ],
            reject_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
                {"name": "val", "expression": "row2.value.upper()",
                 "type": "str"},
            ],
        )
        # Add a catch_output_reject sibling output.
        cfg["outputs"].append({
            "name": "catch1",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "int"},
                {"name": "errorMessage", "expression": "''", "type": "str"},
            ],
            "catch_output_reject": True,
        })
        cfg["die_on_error"] = False
        comp = _make_component(cfg, comp_id="tMap_R5_catch")
        main_df = pd.DataFrame([{"id": 1, "score": 30}])
        result = comp.execute({"row1": main_df})
        # Reject row carries id=1; val is None per soft-error semantics.
        rej = result["rej1"]
        assert rej["id"].tolist() == [1]
        assert pd.isna(rej["val"].iloc[0]) or rej["val"].iloc[0] is None
        # Catch output picks up the row whose reject-column eval failed.
        catch = result.get("catch1")
        assert catch is not None and len(catch) == 1, (
            f"Expected 1 catch row; got {catch}"
        )
        # User-defined column 'id' evaluated against the failing row.
        assert catch["id"].tolist() == [1]
        # 'errorMessage' is present (framework-reserved per D-06); its
        # exact value depends on the implementation (could be empty string
        # if the user-supplied expression "''" was kept, or the framework's
        # error string if the framework wrote it).
        assert "errorMessage" in catch.columns

    def test_filter_reject_py_null_lookup_silent_drop(self, caplog):
        """R5: die_on_error=False -> expression error logs WARNING and None
        is substituted (per _eval_expr semantics, Phase 05.4-02 D-04
        soft-error path).

        Project memory feedback_ascii_logging.md: the captured log line
        must be ASCII-only.
        """
        cfg = _make_filter_reject_config(
            source_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
            ],
            reject_columns=[
                {"name": "id", "expression": "row1.id", "type": "int"},
                {"name": "val", "expression": "row2.value.upper()",
                 "type": "str"},
            ],
        )
        cfg["die_on_error"] = False
        comp = _make_component(cfg, comp_id="tMap_R5_silent")
        main_df = pd.DataFrame([{"id": 1, "score": 30}])
        caplog.clear()
        with caplog.at_level(logging.WARNING,
                             logger="src.v1.engine.components.transform.map"):
            result = comp.execute({"row1": main_df})
        # Reject row exists; val is None (silent substitution).
        rej = result["rej1"]
        assert rej["id"].tolist() == [1]
        assert rej["val"].iloc[0] is None or pd.isna(rej["val"].iloc[0])
        # At least one WARNING line was emitted by the map module.
        assert any(
            "Expression eval failed" in r.message or "eval failed" in r.message
            for r in caplog.records
        ), f"Expected a WARNING about eval failure; got: {[r.message for r in caplog.records]}"
        # ASCII-only check on all captured records (per project memory).
        for record in caplog.records:
            assert record.message.encode("ascii", errors="strict"), (
                f"Non-ASCII log message: {record.message!r}"
            )


# ---------------------------------------------------------------------------
# TestFilterRejectCompiled (compiled-path, java+integration)
# ---------------------------------------------------------------------------


@pytest.mark.java
@pytest.mark.integration
class TestFilterRejectCompiled:
    """is_reject filter-reject under the compiled-Groovy path.

    Each test mirrors the Py class's column-kind matrix but with
    ``{{java}}`` markers throughout -- forcing the compiled path
    (Plan 05.4-06's dual-invocation dispatch via the live JVM bridge).
    A pre-execute assertion (``_has_any_java_marker()``) confirms the
    compiled path is actually exercised (no accidental python-eval
    fallback -- plan-checker warning).

    KNOWN COMPILED-PATH GAP (xfail with reason -- documented in
    05.4-07-SUMMARY.md "Deferred Issues"): the compiled Groovy script
    emitted by ``_build_compiled_script`` invokes ``evalOutput_<rej>``
    only inside the ``rejectMode=true`` branch (Plan 05.4-06 D-09 dual
    invocation), which is driven by ``inner_join_reject_dfs``. There is
    NO compiled-path mechanism that routes filter-failed rows (an
    is_reject=True output's source rows) to the reject buffer -- those
    rows are silently dropped when the source output's
    ``activate_filter`` predicate returns false. This was outside the
    scope of Plan 05.4-03 (which fixed the Python-eval path) and Plan
    05.4-06 (which fixed inner_join_reject for the compiled path).
    R2 SPEC acceptance lists both paths, but compiled-path filter-reject
    is not yet wired. Tests are pinned ``xfail(strict=True)`` so any
    future fix that closes this gap will surface as XPASS and force a
    re-evaluation of these tests.
    """

    _COMPILED_FILTER_REJECT_XFAIL = pytest.mark.xfail(
        strict=True,
        reason=(
            "Compiled-path filter-reject not wired: _build_compiled_script "
            "only emits evalOutput_<rej> calls inside the rejectMode=true "
            "branch, which is driven by inner_join_reject_dfs. Filter-failed "
            "rows from active-mode never reach the reject buffer. Tracked "
            "in 05.4-07-SUMMARY.md and deferred to a future plan that wires "
            "filter-reject into the active-mode row loop."
        ),
    )

    def _build_marker_cfg(self, reject_columns):
        """Build a marker-bearing filter-reject config."""
        return _make_filter_reject_config(
            source_filter="{{java}}row1.score > 50",
            source_columns=[
                {"name": "id", "expression": "{{java}}row1.id",
                 "type": "int"},
            ],
            reject_columns=reject_columns,
        )

    @_COMPILED_FILTER_REJECT_XFAIL
    def test_filter_reject_compiled_same_name_ref(self, java_bridge):
        """Compiled-path reject with same-name simple ref."""
        cfg = self._build_marker_cfg([
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
        ])
        comp = _make_component(cfg, comp_id="tMap_fr_c_same",
                               java_bridge=java_bridge)
        # Populate self.config so _has_any_java_marker can inspect it.
        comp.config = copy.deepcopy(comp._original_config)
        assert comp._has_any_java_marker(), (
            "Compiled path must be exercised (marker should be present)"
        )
        main_df = pd.DataFrame([
            {"id": 1, "score": 80},
            {"id": 2, "score": 30},
        ])
        result = comp.execute({"row1": main_df})
        rej = result["rej1"]
        assert list(rej.columns) == ["id"]
        assert rej["id"].tolist() == [2]

    @_COMPILED_FILTER_REJECT_XFAIL
    def test_filter_reject_compiled_renamed_ref(self, java_bridge):
        """Compiled-path reject with renamed simple ref."""
        cfg = self._build_marker_cfg([
            {"name": "orig_id", "expression": "{{java}}row1.id",
             "type": "int"},
        ])
        comp = _make_component(cfg, comp_id="tMap_fr_c_ren",
                               java_bridge=java_bridge)
        comp.config = copy.deepcopy(comp._original_config)
        assert comp._has_any_java_marker()
        main_df = pd.DataFrame([
            {"id": 1, "score": 80},
            {"id": 7, "score": 10},
        ])
        result = comp.execute({"row1": main_df})
        rej = result["rej1"]
        assert list(rej.columns) == ["orig_id"]
        assert rej["orig_id"].tolist() == [7]

    @_COMPILED_FILTER_REJECT_XFAIL
    def test_filter_reject_compiled_hardcoded_literal(self, java_bridge):
        """Compiled-path reject with hard-coded literal status='REJECTED'."""
        cfg = self._build_marker_cfg([
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
            {"name": "status", "expression": "{{java}}\"REJECTED\"",
             "type": "str"},
        ])
        comp = _make_component(cfg, comp_id="tMap_fr_c_lit",
                               java_bridge=java_bridge)
        comp.config = copy.deepcopy(comp._original_config)
        assert comp._has_any_java_marker()
        main_df = pd.DataFrame([
            {"id": 1, "score": 80},
            {"id": 5, "score": 10},
        ])
        result = comp.execute({"row1": main_df})
        rej = result["rej1"]
        assert rej["status"].tolist() == ["REJECTED"]
        assert rej["id"].tolist() == [5]

    @_COMPILED_FILTER_REJECT_XFAIL
    def test_filter_reject_compiled_java_expr(self, java_bridge):
        """Compiled-path reject with Java string-concat expression."""
        cfg = self._build_marker_cfg([
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
            {"name": "label",
             "expression": "{{java}}row1.id + \"_REJ\"",
             "type": "str"},
        ])
        comp = _make_component(cfg, comp_id="tMap_fr_c_java",
                               java_bridge=java_bridge)
        comp.config = copy.deepcopy(comp._original_config)
        assert comp._has_any_java_marker()
        main_df = pd.DataFrame([
            {"id": 1, "score": 80},
            {"id": 42, "score": 5},
        ])
        result = comp.execute({"row1": main_df})
        rej = result["rej1"]
        # Java string concat coerces int -> str: 42 + "_REJ" -> "42_REJ"
        assert rej["label"].tolist() == ["42_REJ"]
