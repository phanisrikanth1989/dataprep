"""End-to-end regression tests for Phase 05.4 inner_join_reject fix.

This module runs the promoted Job_05_4_inner_reject fixture through the
ETLEngine via a live JVM bridge and asserts on the per-column values in
the inner_join_reject output (D-08 / D-10: reject assertions must check
per-column values, not just row counts).

The fixture has:
  - 7 employees in employees.csv with country_codes US, UK, FR, DE, ES, JP, CN
  - 2 lookup rows in country_partial_05_4.csv with country_codes US and UK
  - INNER_JOIN on country_code; reject output ``rej`` declares 6 columns
    covering all 4 column kinds (simple ref, renamed ref, literal,
    java expression)

Expected: rows for FR, DE, ES, JP, CN (5 rows) flow to ``rej`` with the
per-column values produced by the reject output's own column expressions.

Project memory: feedback_test_real_bridge -- mock-only tests gave false
confidence for tMap historically (Phase 5.1). This module exercises the
full XML -> JSON -> engine -> live bridge -> reject pipeline.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from src.v1.engine.engine import ETLEngine

pytestmark = [pytest.mark.java, pytest.mark.integration]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "fixtures" / "jobs" / "transform" / "05_4"
DATA_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "data"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_config(name: str) -> Dict[str, Any]:
    """Load a fixture job config by name and return a deep copy."""
    path = FIXTURES_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


class _BridgeShim:
    """Minimal JavaBridgeManager shim that wraps a live bridge.

    Mirrors the pattern in test_map_05_3_e2e.py. Wires the session-scoped
    bridge into ETLEngine without invoking JavaBridgeManager.start() (which
    would compete for ports under -n auto).
    """

    def __init__(self, bridge):
        self._bridge = bridge

    def get_bridge(self):
        return self._bridge

    def is_available(self) -> bool:
        return True


def _run_job(config: Dict[str, Any], java_bridge=None) -> ETLEngine:
    """Run the ETL engine with a config dict and return the engine instance.

    When ``java_bridge`` is provided the function disables the job's
    java_config so ETLEngine does NOT start its own JavaBridgeManager,
    then wires the session bridge into every component and the
    ContextManager via a lightweight shim. This matches the production
    path exactly.
    """
    cfg = copy.deepcopy(config)
    if java_bridge is not None:
        cfg.setdefault("java_config", {})["enabled"] = False

    engine = ETLEngine(cfg)

    if java_bridge is not None:
        shim = _BridgeShim(java_bridge)
        engine.context_manager.java_bridge_manager = shim
        for comp in engine.components.values():
            comp.java_bridge = java_bridge

    stats = engine.execute()
    if stats.get("status") == "error":
        raise RuntimeError(
            f"ETLEngine reported error: {stats.get('error', 'unknown')}"
        )
    return engine


def _set_component_filepath(config: Dict[str, Any], comp_id: str, path: str) -> None:
    """Set filepath config key on a named component (in-place)."""
    for comp in config["components"]:
        if comp["id"] == comp_id:
            comp.setdefault("config", {})["filepath"] = path
            return
    raise KeyError(f"Component '{comp_id}' not found in config")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInnerRejectE2E:
    """End-to-end regression: inner_join_reject column-expression evaluation.

    The fixture's reject output ``rej`` declares 6 columns:
      - id           : row1.id              (simple ref, same name as main col)
      - original_id  : row1.id              (renamed simple ref)
      - renamed_name : row1.first_name      (renamed simple ref)
      - country_code : row1.country_code    (simple ref, same name)
      - error_code   : "INNER_JOIN_FAIL"    (hard-coded literal)
      - error_num    : 999                  (hard-coded literal numeric)
      - error_msg    : "No match for code: " + row1.country_code (java expr)

    Before Phase 05.4-02, the legacy ``_route_inner_join_rejects`` name-based
    copy would leave ``error_code``, ``error_num``, and ``original_id`` as
    None (those names are not in the rejects DataFrame). After the fix,
    every column carries its declared expression's value.
    """

    def test_inner_reject_columns_evaluated(self, java_bridge):
        """Reject output columns must be populated per declared expressions."""
        config = _load_config("inner_reject")

        # Wire input files. The fixture defaults already point to test paths
        # but we explicitly set them for clarity (matches Phase 05.3 pattern).
        _set_component_filepath(
            config,
            "tFileInputDelimited_1",
            str(DATA_DIR / "employees.csv"),
        )
        _set_component_filepath(
            config,
            "tFileInputDelimited_2",
            str(DATA_DIR / "country_partial_05_4.csv"),
        )

        engine = _run_job(config, java_bridge=java_bridge)

        # Reject flow is named "rej" on tMap_2; no downstream consumer means
        # it lives in OutputRouter._data_flows. Access via get_flow_data.
        rej = engine.output_router.get_flow_data("rej")
        assert rej is not None, (
            "inner_join_reject output 'rej' missing from engine data flows"
        )

        # Expected: 5 rejects (FR, DE, ES, JP, CN -- 7 employees minus 2 matches).
        assert len(rej) == 5, (
            f"Expected 5 reject rows (7 employees - 2 lookup matches); "
            f"got {len(rej)} rows: {rej.to_dict(orient='records')}"
        )

        # Per-column expected values (not just counts).
        # Sort by id for deterministic ordering across pandas versions.
        rej_sorted = rej.sort_values("id").reset_index(drop=True)

        # id column: simple ref row1.id -- should match the 5 unmatched
        # employee ids. From employees.csv: 1=US, 2=UK match; 3=FR, 4=DE,
        # 5=ES, 6=JP, 7=CN reject.
        assert rej_sorted["id"].tolist() == [3, 4, 5, 6, 7], (
            f"Expected id=[3,4,5,6,7]; got {rej_sorted['id'].tolist()!r}"
        )

        # original_id column: renamed simple ref row1.id -- must equal id.
        assert rej_sorted["original_id"].tolist() == [3, 4, 5, 6, 7], (
            f"Expected original_id=[3,4,5,6,7]; got "
            f"{rej_sorted['original_id'].tolist()!r} "
            f"(D-08 / D-10: renamed simple-ref column dropped under legacy code)"
        )

        # renamed_name column: row1.first_name for the 5 rejected employees.
        assert rej_sorted["renamed_name"].tolist() == [
            "Pierre", "Hans", "Maria", "Yuki", "Li",
        ], (
            f"Expected renamed_name=['Pierre','Hans','Maria','Yuki','Li']; got "
            f"{rej_sorted['renamed_name'].tolist()!r}"
        )

        # country_code column: simple ref row1.country_code.
        assert rej_sorted["country_code"].tolist() == [
            "FR", "DE", "ES", "JP", "CN",
        ], (
            f"Expected country_code=['FR','DE','ES','JP','CN']; got "
            f"{rej_sorted['country_code'].tolist()!r}"
        )

        # error_code column: hard-coded literal "INNER_JOIN_FAIL".
        # This is the column that returns None under the legacy name-based
        # copy because "error_code" is not a column name in the rejects
        # DataFrame.
        assert rej_sorted["error_code"].tolist() == [
            "INNER_JOIN_FAIL", "INNER_JOIN_FAIL", "INNER_JOIN_FAIL",
            "INNER_JOIN_FAIL", "INNER_JOIN_FAIL",
        ], (
            f"Expected all error_code='INNER_JOIN_FAIL'; got "
            f"{rej_sorted['error_code'].tolist()!r} "
            f"(D-08 / D-10: hard-coded literal dropped under legacy code)"
        )

        # error_num column: hard-coded literal 999.
        assert rej_sorted["error_num"].tolist() == [999, 999, 999, 999, 999], (
            f"Expected error_num=[999]*5; got "
            f"{rej_sorted['error_num'].tolist()!r}"
        )

        # error_msg column: java expression "No match for code: " + row1.country_code.
        assert rej_sorted["error_msg"].tolist() == [
            "No match for code: FR",
            "No match for code: DE",
            "No match for code: ES",
            "No match for code: JP",
            "No match for code: CN",
        ], (
            f"Expected error_msg with country_code suffix; got "
            f"{rej_sorted['error_msg'].tolist()!r}"
        )

    def test_job_runs_without_error(self, java_bridge):
        """Sanity check: full inner-reject job completes successfully end-to-end.

        Distinct from ``test_inner_reject_columns_evaluated`` -- that test
        asserts on the reject DataFrame's content. This one pins that the
        full pipeline (tFileInput x2 -> tMap with INNER_JOIN -> tLogRow x2)
        executes without raising, exercising the compiled-path dual-invocation
        (Plan 05.4-06) over the live JVM bridge.
        """
        config = _load_config("inner_reject")
        _set_component_filepath(
            config,
            "tFileInputDelimited_1",
            str(DATA_DIR / "employees.csv"),
        )
        _set_component_filepath(
            config,
            "tFileInputDelimited_2",
            str(DATA_DIR / "country_partial_05_4.csv"),
        )

        engine = _run_job(config, java_bridge=java_bridge)
        # ETLEngine.execute() returned status != "error" (enforced by _run_job).
        # The reject flow ``rej`` still has data because it has no downstream
        # consumer in the fixture (sanity-check the reject pipeline routed
        # data even though main flows were consumed).
        rej = engine.output_router.get_flow_data("rej")
        assert rej is not None and len(rej) == 5, (
            "End-to-end run produced unexpected reject flow state"
        )
