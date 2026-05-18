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


# TestFilterRejectPy -- DELETED in Phase 8 triage. The whole class
# exercised the legacy Python-eval no-marker path (Map._evaluate_outputs_py
# + _eval_expr soft-error semantics). Per spec section 3, that path is
# OUT OF SCOPE: "Python-eval path (no-marker dispatch) -- All production
# tMaps come from the converter with {{java}} markers. Single execution
# path = simpler." The same column-kind matrix is exercised end-to-end
# through the live bridge in TestFilterRejectCompiled below.


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


# ---------------------------------------------------------------------------
# Plan 05.5-04 R7: filter-reject column expression with context.X and
# globalMap.X. Python-eval path only -- the 4 compiled-path filter-reject
# xfails are RETAINED per R9 decision in 05.5-XFAIL-REVIEW.md (orthogonal
# root cause in _build_compiled_script's active-mode reject emission).
# ---------------------------------------------------------------------------


# TestFilterRejectContextSync -- DELETED in Phase 8 triage. Exercised
# the legacy Python-eval no-marker path (R7 Python-path coverage). The
# Python-eval path is OUT OF SCOPE per spec section 3. Equivalent
# coverage via the compiled path (the only execution path the new code
# supports) lives in test_map_bridge.py::TestPhase055ContextSync and
# in TestFilterRejectCompiled in this file.
