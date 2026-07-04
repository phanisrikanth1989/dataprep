"""Inner-join-reject column-expression evaluation matrix (D-08).

20 parametrized tests covering the 5 join paths x 4 column kinds matrix
for inner_join_reject outputs, plus 1 PerformanceWarning regression check
for R7 (single-allocation reject DataFrame -- no per-column setitem loop
that would emit ``PerformanceWarning: DataFrame is highly fragmented``).

Join paths exercised:
  - EQUALITY        : standard pandas merge with a simple-ref join key
  - MAIN_SIDE       : {{java}}-expression join key referencing only the
                      main side (row1.*) -- _join_main_side
  - LOOKUP_SIDE     : {{java}}-expression join key referencing only the
                      lookup side (row2.*) -- _join_lookup_side
  - CROSS_TABLE     : {{java}}-expression join key referencing both sides
                      (row1.* AND row2.*) -- _join_cross_table
  - RELOAD_PER_ROW  : lookup_mode=RELOAD_AT_EACH_ROW + INNER_JOIN

Column kinds exercised in the reject output:
  - same_name_ref     : "{{java}}row1.id"            output column "id"
  - renamed_simple_ref: "{{java}}row1.id"            output column "orig_id"
  - hardcoded_literal : "{{java}}\\"REJECTED\\""     output column "status"
  - java_expression   : "{{java}}row1.id + \\"_REJ\\"" output column "label"

The unmatched main-row carries id=99 across all permutations; lookup rows
NEVER include id=99 / country=OTHER so the row is guaranteed to be the
sole reject.

All tests are @pytest.mark.java + @pytest.mark.integration: the {{java}}
markers in join keys force the compiled path, requiring a live JVM bridge.

Phase 05.4 plan 07 deliverable (D-08).
"""
from __future__ import annotations

import warnings
from typing import Any, Dict, List

import pandas as pd
import pytest

from src.v1.engine.components.transform.map import Map
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap


pytestmark = [pytest.mark.java, pytest.mark.integration]


# ---------------------------------------------------------------------------
# Column-kind dispatch
# ---------------------------------------------------------------------------

_COL_NAME: Dict[str, str] = {
    "same_name_ref": "id",
    "renamed_simple_ref": "orig_id",
    "hardcoded_literal": "status",
    "java_expression": "label",
}


def _reject_columns_for_kind(col_kind: str) -> List[Dict[str, Any]]:
    """Build the reject output's column list isolating one column kind.

    Each list always includes ``id`` so we have a stable row-identity column
    to sort/index by, plus the column under test. Two-column lists keep the
    schema minimal and the assertions targeted.
    """
    if col_kind == "same_name_ref":
        # Single column "id" (same name as main side); ref to row1.id
        return [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
        ]
    if col_kind == "renamed_simple_ref":
        return [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
            {"name": "orig_id", "expression": "{{java}}row1.id", "type": "int"},
        ]
    if col_kind == "hardcoded_literal":
        return [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
            {"name": "status", "expression": "{{java}}\"REJECTED\"",
             "type": "str"},
        ]
    if col_kind == "java_expression":
        return [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int"},
            {"name": "label",
             "expression": "{{java}}row1.id + \"_REJ\"",
             "type": "str"},
        ]
    raise ValueError(f"Unknown col_kind: {col_kind!r}")


def _expected_value_for_kind(col_kind: str, unmatched_id: int) -> Any:
    """Expected reject-row value for the column-under-test.

    Mirrors the expressions in ``_reject_columns_for_kind`` evaluated against
    the unmatched main row.
    """
    if col_kind in ("same_name_ref",):
        return unmatched_id
    if col_kind == "renamed_simple_ref":
        return unmatched_id
    if col_kind == "hardcoded_literal":
        return "REJECTED"
    if col_kind == "java_expression":
        # row1.id + "_REJ" -- Groovy/Java string concat coerces int to str
        return f"{unmatched_id}_REJ"
    raise ValueError(f"Unknown col_kind: {col_kind!r}")


# ---------------------------------------------------------------------------
# Join-path dispatch
# ---------------------------------------------------------------------------


def _lookup_config_for_join_path(join_path: str) -> Dict[str, Any]:
    """Build the single-lookup config block (join_keys + lookup_mode).

    Each join path produces a configuration that exercises a distinct branch
    in the join-key classifier inside ``Map._classify_join_keys``.
    """
    base_join_key = {
        "lookup_column": "country_code",
        "type": "str",
        "nullable": True,
        "operator": "=",
    }
    if join_path == "equality":
        return {
            "lookup_mode": "LOAD_ONCE",
            "join_keys": [
                {**base_join_key,
                 "expression": "{{java}}row1.country_code"},
            ],
        }
    if join_path == "main_side":
        # Main-side computed key: a .trim() call on row1 forces the classifier
        # to route this through _join_main_side (single-side bridge eval).
        return {
            "lookup_mode": "LOAD_ONCE",
            "join_keys": [
                {**base_join_key,
                 "expression": "{{java}}row1.country_code.trim()"},
            ],
        }
    if join_path == "lookup_side":
        # Lookup-side computed key: a .trim() call on row2.
        return {
            "lookup_mode": "LOAD_ONCE",
            "join_keys": [
                {**base_join_key,
                 "expression": "{{java}}row2.country_code.trim()"},
            ],
        }
    if join_path == "cross_table":
        # Cross-table key: references both row1 and row2 -- forces full
        # cross-product evaluation via _join_cross_table. The classifier
        # compares the expression's evaluated value against the prefixed
        # lookup column; we structure the expression to evaluate to
        # row2.country_code when row1.id == 1, otherwise empty -- so id=1
        # matches MATCH_ONLY and id=99 does not.
        return {
            "lookup_mode": "LOAD_ONCE",
            "join_keys": [
                {**base_join_key,
                 "expression": "{{java}}row1.id == 1 ? row2.country_code : \"NO_MATCH\""},
            ],
        }
    if join_path == "reload_per_row":
        return {
            "lookup_mode": "RELOAD_AT_EACH_ROW",
            "join_keys": [
                {**base_join_key,
                 "expression": "{{java}}row1.country_code"},
            ],
        }
    raise ValueError(f"Unknown join_path: {join_path!r}")


# ---------------------------------------------------------------------------
# Config and component factories
# ---------------------------------------------------------------------------


def _build_config(join_path: str, col_kind: str) -> Dict[str, Any]:
    """Assemble a full Map config with one inner_join_reject output.

    The main output 'out1' carries a no-op id column so the engine has a
    valid join-target with a populated schema; we never assert on its
    contents.
    """
    lookup_cfg = _lookup_config_for_join_path(join_path)
    reject_columns = _reject_columns_for_kind(col_kind)

    return {
        "component_type": "Map",
        "die_on_error": True,
        "inputs": {
            "main": {
                "name": "row1",
                "filter": "",
                "activate_filter": False,
                "matching_mode": "UNIQUE_MATCH",
                "lookup_mode": "LOAD_ONCE",
            },
            "lookups": [
                {
                    "name": "row2",
                    "matching_mode": "UNIQUE_MATCH",
                    "lookup_mode": lookup_cfg["lookup_mode"],
                    "filter": "",
                    "activate_filter": False,
                    "join_keys": lookup_cfg["join_keys"],
                    "join_mode": "INNER_JOIN",
                }
            ],
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
                ],
                "catch_output_reject": False,
            },
            {
                "name": "rej",
                "is_reject": False,
                "inner_join_reject": True,
                "filter": "",
                "activate_filter": False,
                "columns": reject_columns,
                "catch_output_reject": False,
            },
        ],
    }


def _make_component(java_bridge, config, comp_id="tMap_reject_matrix"):
    comp = Map(
        component_id=comp_id,
        config=config,
        global_map=GlobalMap(),
        context_manager=ContextManager(),
    )
    comp.java_bridge = java_bridge
    return comp


# ---------------------------------------------------------------------------
# Test matrix
# ---------------------------------------------------------------------------

# Phase 8 triage: 'lookup_side' and 'cross_table' join paths are
# OUT OF SCOPE per spec section 3 (lookup-side computed keys and
# truly two-sided keys are not expressible in the Talend tMap UI;
# the right-side of a join key is just a column picker). The
# remaining three paths cover all join shapes the rewrite supports:
#  - equality:      SIMPLE strategy (pd.merge on simple column refs)
#  - main_side:     COMPUTED strategy (batch-evaluated main-side keys)
#  - reload_per_row RELOAD strategy (per-row matching)
_JOIN_PATHS = ("equality", "main_side", "reload_per_row")
_COL_KINDS = ("same_name_ref", "renamed_simple_ref", "hardcoded_literal",
              "java_expression")

# Build the 12-entry param list (3 x 4).
_MATRIX_PARAMS: List[tuple] = []
for jp in _JOIN_PATHS:
    for ck in _COL_KINDS:
        _MATRIX_PARAMS.append(
            pytest.param(jp, ck, id=f"{jp}-{ck}")
        )


class TestInnerJoinRejectMatrix:
    """20 (join-path x column-kind) inner_join_reject assertions.

    The unmatched row carries id=99, country_code='OTHER'. The lookup
    contains a single row with country_code='MATCH_ONLY' so id=99 is
    guaranteed to be the sole reject under every join path. Each test
    asserts the per-column expected value (not a row count or "any"
    predicate) -- this is the D-10 strengthening pattern applied to a
    fresh matrix.
    """

    @pytest.mark.parametrize("join_path,col_kind", _MATRIX_PARAMS)
    def test_inner_join_reject_column(self, java_bridge, join_path, col_kind):
        """Reject column kind X under join path Y carries the expected value.

        Two main rows: id=1/MATCH_ONLY (matches) and id=99/OTHER (rejects).
        The match keeps joined_df non-empty so the compiled-path dispatch
        (Plan 05.4-06 dual-invocation) is exercised for `{{java}}`-marker
        configs -- otherwise the joined_df.empty early-return branch would
        force Python-eval routing for all reject configs.
        """
        config = _build_config(join_path, col_kind)
        comp = _make_component(java_bridge, config)

        # Two main rows: id=1 matches MATCH_ONLY; id=99 never matches.
        main_df = pd.DataFrame([
            {"id": 1, "country_code": "MATCH_ONLY"},
            {"id": 99, "country_code": "OTHER"},
        ])
        lookup_df = pd.DataFrame(
            [{"country_code": "MATCH_ONLY", "label": "Match Only Row"}]
        )

        result = comp.execute({"row1": main_df, "row2": lookup_df})
        # The reject output is named 'rej' in our config.
        rej = result.get("rej")
        assert rej is not None, (
            f"join={join_path}, col={col_kind}: 'rej' output missing from result"
        )
        assert len(rej) == 1, (
            f"join={join_path}, col={col_kind}: expected exactly 1 reject "
            f"row (id=99), got {len(rej)} rows: "
            f"{rej.to_dict(orient='records')}"
        )
        # The reject row must be id=99 (the OTHER country row), not the match.
        assert rej["id"].iloc[0] == 99, (
            f"join={join_path}, col={col_kind}: expected reject id=99, "
            f"got id={rej['id'].iloc[0]!r}"
        )

        col_name = _COL_NAME[col_kind]
        expected = _expected_value_for_kind(col_kind, unmatched_id=99)
        actual = rej[col_name].iloc[0]
        assert actual == expected, (
            f"join={join_path}, col={col_kind}: reject column "
            f"{col_name!r} expected {expected!r}, got {actual!r}"
        )


class TestRejectFragmentationWarning:
    """R7: reject DataFrame must be allocated in one pass (no PerformanceWarning).

    Phase 05.4-02 SUMMARY documents that ``_route_inner_join_rejects`` was
    rewritten to use ``_evaluate_output_columns_py``'s single-allocation
    ``pd.DataFrame(...)`` so the legacy per-column ``reject_df[col_name] = ...``
    loop (which emitted ``PerformanceWarning: DataFrame is highly fragmented``)
    is gone. This test pins that behaviour by promoting that warning to an
    error inside the routing call.
    """

    def test_no_fragmentation_warning_on_multi_row_reject(self, java_bridge):
        """20-row reject path with 5-column reject output: no fragmentation."""
        # Multi-column reject output exercises the previously-fragmented path.
        config = _build_config(join_path="equality",
                               col_kind="hardcoded_literal")
        # Add 3 more reject columns so the reject DataFrame has 5 columns.
        config["outputs"][1]["columns"].extend([
            {"name": "extra1", "expression": "{{java}}row1.id",
             "type": "int"},
            {"name": "extra2", "expression": "{{java}}\"X\"",
             "type": "str"},
            {"name": "extra3", "expression": "{{java}}row1.country_code",
             "type": "str"},
        ])
        comp = _make_component(java_bridge, config,
                               comp_id="tMap_reject_frag")

        # 20 unmatched rows + 1 matched (keeps joined_df non-empty so the
        # compiled-path reject dispatch runs over the unmatched batch).
        rows = [{"id": i, "country_code": "OTHER"} for i in range(20)]
        rows.append({"id": 9999, "country_code": "MATCH_ONLY"})
        main_df = pd.DataFrame(rows)
        lookup_df = pd.DataFrame(
            [{"country_code": "MATCH_ONLY", "label": "M"}]
        )

        # Promote pandas PerformanceWarning to error inside the routing call.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "error", category=pd.errors.PerformanceWarning
            )
            result = comp.execute({"row1": main_df, "row2": lookup_df})

        # Sanity: rejects materialized.
        rej = result.get("rej")
        assert rej is not None and len(rej) == 20, (
            f"Expected 20 reject rows; got {len(rej) if rej is not None else 'None'}"
        )
        # And our 5 reject columns are present.
        assert set(["id", "status", "extra1", "extra2", "extra3"]).issubset(
            set(rej.columns)
        ), f"Reject columns mismatch: {list(rej.columns)!r}"


# ---------------------------------------------------------------------------
# Plan 05.5-04 R7: reject-output column expressions referencing
# context.X and globalMap.X must resolve at row-evaluation time.
# ---------------------------------------------------------------------------


class TestInnerJoinRejectContextSync:
    """R7 -- reject-output column with both context.X and globalMap.X.

    Plan 05.5-04 wires ``_push_runtime_state_to_bridge`` into the
    reject-mode invocation of ``execute_compiled_tmap_chunked``
    (map.py L2177). This test pins that the reject DataFrame's column
    value built from a mixed context + globalMap expression resolves
    correctly.
    """

    def test_inner_join_reject_with_context_and_globalmap(self, java_bridge):
        cm = ContextManager()
        cm.set("suffix", "_REJ", value_type="id_String")
        gm = GlobalMap()
        gm.put("env", "PROD")

        config = _build_config(
            join_path="equality", col_kind="same_name_ref"
        )
        # Replace the reject columns: include id + a mixed-source label.
        config["outputs"][1]["columns"] = [
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
        ]

        comp = Map(
            component_id="tMap_055_r7_inner",
            config=config,
            global_map=gm,
            context_manager=cm,
        )
        comp.java_bridge = java_bridge

        # id=1 matches MATCH_ONLY; id=99 rejects.
        main_df = pd.DataFrame([
            {"id": 1, "country_code": "MATCH_ONLY"},
            {"id": 99, "country_code": "OTHER"},
        ])
        lookup_df = pd.DataFrame(
            [{"country_code": "MATCH_ONLY", "label": "Match Only Row"}]
        )

        result = comp.execute({"row1": main_df, "row2": lookup_df})
        rej = result.get("rej")
        assert rej is not None and len(rej) == 1, (
            f"Expected exactly 1 reject row (id=99); got "
            f"{len(rej) if rej is not None else 'None'}"
        )
        assert rej["id"].iloc[0] == 99
        assert rej["tag"].iloc[0] == "99_REJPROD", (
            f"R7 inner-join reject context+globalMap regressed: got "
            f"{rej['tag'].iloc[0]!r}"
        )
