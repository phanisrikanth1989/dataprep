"""is_reject filter-reject column-evaluation tests (Plan 05.4-07).

Two classes, each covering 4 column kinds for the is_reject filter-reject
path:

TestFilterRejectPy  -- @pytest.mark.unit
  Exercises ``_evaluate_outputs_py`` (Python-eval path: no {{java}}
  markers, no bridge). 4 tests across (same_name_ref, renamed_simple_ref,
  hardcoded_literal, java_expression-style python) + 3 R5 null-lookup
  scenarios (die_on_error=True, catch routes, silent drop).

TestFilterRejectCompiled -- @pytest.mark.java + @pytest.mark.integration
  Exercises filter-reject via the compiled path. 4 tests with the same
  column-kind matrix but with ``{{java}}`` markers throughout. Each test
  asserts ``has_any_java_marker()`` BEFORE execute() so the compiled path
  is actually exercised (per plan-checker warning -- no accidental
  python-eval fallback).

Phase 05.4 plan 07 deliverable -- builds the filter-reject corner of the
D-08 test matrix.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.v1.engine.components.transform.map import Map
from src.v1.engine.components.transform.map.map_config import (
    has_any_java_marker,
    parse_config,
)
from src.v1.engine.context_manager import ContextManager
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
    A pre-execute assertion (``has_any_java_marker()``) confirms the
    compiled path is actually exercised (no accidental python-eval
    fallback -- plan-checker warning).

    Filter-reject rows (is_reject=True output) are populated inline by the
    active Groovy script via the matchedAny boolean. The tMap rewrite (Task
    3.3) wired this path in _build_active_script -- filter-failed rows are
    written to the reject output buffer in the same active-mode row loop as
    the passing rows.
    """

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

    def test_filter_reject_compiled_same_name_ref(self, java_bridge):
        """Compiled-path reject with same-name simple ref."""
        cfg = self._build_marker_cfg([
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
        ])
        comp = _make_component(cfg, comp_id="tMap_fr_c_same",
                               java_bridge=java_bridge)
        assert has_any_java_marker(parse_config(cfg)), (
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

    def test_filter_reject_compiled_renamed_ref(self, java_bridge):
        """Compiled-path reject with renamed simple ref."""
        cfg = self._build_marker_cfg([
            {"name": "orig_id", "expression": "{{java}}row1.id",
             "type": "int"},
        ])
        comp = _make_component(cfg, comp_id="tMap_fr_c_ren",
                               java_bridge=java_bridge)
        assert has_any_java_marker(parse_config(cfg))
        main_df = pd.DataFrame([
            {"id": 1, "score": 80},
            {"id": 7, "score": 10},
        ])
        result = comp.execute({"row1": main_df})
        rej = result["rej1"]
        assert list(rej.columns) == ["orig_id"]
        assert rej["orig_id"].tolist() == [7]

    def test_filter_reject_compiled_hardcoded_literal(self, java_bridge):
        """Compiled-path reject with hard-coded literal status='REJECTED'."""
        cfg = self._build_marker_cfg([
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
            {"name": "status", "expression": "{{java}}\"REJECTED\"",
             "type": "str"},
        ])
        comp = _make_component(cfg, comp_id="tMap_fr_c_lit",
                               java_bridge=java_bridge)
        assert has_any_java_marker(parse_config(cfg))
        main_df = pd.DataFrame([
            {"id": 1, "score": 80},
            {"id": 5, "score": 10},
        ])
        result = comp.execute({"row1": main_df})
        rej = result["rej1"]
        assert rej["status"].tolist() == ["REJECTED"]
        assert rej["id"].tolist() == [5]

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
        assert has_any_java_marker(parse_config(cfg))
        main_df = pd.DataFrame([
            {"id": 1, "score": 80},
            {"id": 42, "score": 5},
        ])
        result = comp.execute({"row1": main_df})
        rej = result["rej1"]
        # Java string concat coerces int -> str: 42 + "_REJ" -> "42_REJ"
        assert rej["label"].tolist() == ["42_REJ"]


# ---------------------------------------------------------------------------
# The 4 compiled-path filter-reject tests above were promoted from xfail
# (strict) to active in Phase 9 (Task 9.3). Filter-reject is now wired in
# the active Groovy script via the matchedAny boolean (Task 3.3).
# ---------------------------------------------------------------------------


# TestFilterRejectContextSync -- DELETED in Phase 8 triage. Exercised
# the legacy Python-eval no-marker path (R7 Python-path coverage). The
# Python-eval path is OUT OF SCOPE per spec section 3. Equivalent
# coverage via the compiled path (the only execution path the new code
# supports) lives in test_map_bridge.py::TestPhase055ContextSync and
# in TestFilterRejectCompiled in this file.
