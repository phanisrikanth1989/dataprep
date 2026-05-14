"""End-to-end regression tests for Phase 05.3 tMap fixes.

Each test runs a JSON job config through the engine and asserts on output
file contents. All tests are @pytest.mark.java + @pytest.mark.integration.

Project memory: feedback_test_real_bridge -- mock-only tests gave false
confidence for tMap historically (Phase 5.1). Live-bridge tests mandatory
for tMap path coverage.

Issues covered by this module:
  Issue 1  (clean baseline)        : test_issue_1_clean_baseline
  Issue 2a (main-side .trim() key) : test_issue_2a_main_side_trim
  Issue 2b (routine as join key)   : test_issue_2b_routine_join_key
  Issue 2c (empty join_keys+filter): test_issue_2c_filter_join_no_crash
  Issue 3  (lookup-to-lookup trim) : test_issue_3_lookup_to_lookup_trim
  Issue 5  (chained vars)          : test_issue_5_chained_vars_simple_outputs

  Extra:   test_marker_present_no_bridge_hard_fails (D-01 sentinel)

Issue 4 is blocked on D-07 decision (plan 08). Issue 6 is in
test_file_output_delimited_05_3_e2e.py.
"""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from src.v1.engine.components.transform.map import Map
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.engine import ETLEngine
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap

pytestmark = [pytest.mark.java, pytest.mark.integration]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "fixtures" / "jobs" / "transform" / "05_3"
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

    Used to wire the session-scoped bridge fixture into an ETLEngine that
    was initialized with java_config.enabled=False. The engine's
    ContextManager and BaseComponent both call get_bridge() / is_available()
    on the manager -- this shim satisfies that interface.
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
    java_config so ETLEngine does NOT start its own JavaBridgeManager
    (which would cause port contention in parallel test runs under -n auto),
    then wires the session bridge into every component and into the
    ContextManager via a lightweight shim. This matches the production path
    exactly -- ETLEngine wires ``manager.bridge`` to components after init.

    Raises on error stats so tests see the failure immediately.
    """
    cfg = copy.deepcopy(config)
    if java_bridge is not None:
        # Disable auto-start: prevent ETLEngine.__init__ from calling
        # JavaBridgeManager.start() which would compete for JVM ports.
        cfg.setdefault("java_config", {})["enabled"] = False

    engine = ETLEngine(cfg)

    if java_bridge is not None:
        # Wire the session bridge into context manager and all components.
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


def _read_csv(path: Path) -> list[dict]:
    """Read a CSV and return list of row dicts."""
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _wire_clean_job(config: Dict[str, Any], tmp_path: Path) -> tuple[Path, Path]:
    """Set input + output paths for the clean fixture and return output paths."""
    employees_csv = str(DATA_DIR / "employees.csv")
    lookup_csv = str(DATA_DIR / "country_lookup.csv")
    out_main = tmp_path / "out.csv"
    out2 = tmp_path / "out2.csv"

    _set_component_filepath(config, "tFileInputDelimited_1", employees_csv)
    _set_component_filepath(config, "tFileInputDelimited_2", lookup_csv)
    _set_component_filepath(config, "tLogRow_1", str(out_main))
    _set_component_filepath(config, "tLogRow_2", str(out2))

    return out_main, out2


def _wire_two_input_job(config: Dict[str, Any], tmp_path: Path) -> tuple[Path, Path]:
    """Wire two-input (employees + country_lookup) jobs. Returns (out_main, out2)."""
    return _wire_clean_job(config, tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIssue1CleanBaseline:
    """Issue 1: baseline tMap with literal output column and join.

    The clean fixture has salary > 60000 output filter. With 8 employees
    (salaries: 85000, 65000, 90000, 55000, 78000, 72000, 95000, + one more)
    and all having countries in the lookup, 6 rows should appear in 'out'.
    """

    def test_issue_1_clean_baseline(self, java_bridge, tmp_path, assert_ascii_logs):
        """Runs clean.json end-to-end; asserts on output row count and side column."""
        config = _load_config("clean")
        out_main, out2 = _wire_clean_job(config, tmp_path)

        _run_job(config, java_bridge=java_bridge)

        assert out_main.exists(), "out.csv should exist"
        rows = _read_csv(out_main)
        # salary > 60000: employees 1(85k), 2(65k), 3(90k), 5(78k), 6(72k), 7(95k) = 6
        assert len(rows) == 6, f"Expected 6 rows with salary>60000, got {len(rows)}"
        # All rows should have the literal "L" value from the side column
        for row in rows:
            assert row.get("side") == "L", f"Expected side='L', got {row.get('side')!r}"

        assert_ascii_logs


class TestIssue2aMainSideTrim:
    """Issue 2a: main-side .trim() join key expression.

    join_trim.json uses '{{java}}row1.country_code.trim()' as join key.
    Before the fix, the classifier routed this to cross-table (wrong), causing
    O(n*m) behavior. With main_side classification, it batch-evals the trimmed
    key on joined_df and does a standard pd.merge.
    """

    def test_issue_2a_main_side_trim(self, java_bridge, tmp_path, assert_ascii_logs):
        """Runs join_trim.json; all employees should match (trim doesn't change values)."""
        config = _load_config("join_trim")
        out_main, _ = _wire_two_input_job(config, tmp_path)

        _run_job(config, java_bridge=java_bridge)

        assert out_main.exists(), "out.csv should exist"
        rows = _read_csv(out_main)
        # salary > 60000 and all countries match
        assert len(rows) == 6, f"Expected 6 rows, got {len(rows)}"

        assert_ascii_logs


class TestIssue2bRoutineJoinKey:
    """Issue 2b: routine call as join key expression.

    join_routine.json uses 'routines.StringHandling.UPCASE(row1.country_code)'
    as join key. The country codes in employees.csv are already uppercase (US, UK, etc.)
    so UPCASE preserves them and all employees should match.
    """

    def test_issue_2b_routine_join_key(self, java_bridge, tmp_path, assert_ascii_logs):
        """Runs join_routine.json; routine-based join key should resolve correctly."""
        config = _load_config("join_routine")
        out_main, _ = _wire_two_input_job(config, tmp_path)

        _run_job(config, java_bridge=java_bridge)

        assert out_main.exists(), "out.csv should exist"
        rows = _read_csv(out_main)
        # salary > 60000 with all countries matching
        assert len(rows) == 6, f"Expected 6 rows, got {len(rows)}"

        assert_ascii_logs


class TestIssue2cFilterJoinNoCrash:
    """Issue 2c: empty join_keys + activate_filter as match condition.

    filter_join.json has join_keys=[] and a filter expression
    'row1.country_code.trim().equals(row2.country_code)' as the match.
    Before the fix this crashed with 'list index out of range'.
    """

    def test_issue_2c_filter_join_no_crash(self, java_bridge, tmp_path, assert_ascii_logs):
        """Runs filter_join.json; should NOT raise 'list index out of range'."""
        config = _load_config("filter_join")
        out_main, _ = _wire_two_input_job(config, tmp_path)

        # Must NOT raise
        _run_job(config, java_bridge=java_bridge)

        assert out_main.exists(), "out.csv should exist after filter-only join"
        rows = _read_csv(out_main)
        # All 7 employees have countries in the lookup
        assert len(rows) >= 1, "Expected at least 1 matched row, got 0"

        assert_ascii_logs


class TestIssue3LookupToLookupTrim:
    """Issue 3: lookup-to-lookup join key using row2.region.trim().

    l2l_trim.json has three inputs: employees -> tMap with two lookups:
      row2 join: row1.country_code (simple)
      row3 join: row2.region.trim() (prior-joined lookup ref)

    Before the fix, _evaluate_with_bridge was called with only [current_lookup]
    so row2.region was not visible. D-04 fix passes joined_lookup_names.
    """

    def test_issue_3_lookup_to_lookup_trim(self, java_bridge, tmp_path, assert_ascii_logs):
        """Runs l2l_trim.json; row3 join on row2.region.trim() must produce matches."""
        config = _load_config("l2l_trim")
        employees_csv = str(DATA_DIR / "employees.csv")
        lookup_csv = str(DATA_DIR / "country_lookup.csv")
        regions_csv = str(DATA_DIR / "regions_meta.csv")
        out_main = tmp_path / "out.csv"
        out2 = tmp_path / "out2.csv"

        _set_component_filepath(config, "tFileInputDelimited_1", employees_csv)
        _set_component_filepath(config, "tFileInputDelimited_2", lookup_csv)
        _set_component_filepath(config, "tFileInputDelimited_3", regions_csv)
        _set_component_filepath(config, "tLogRow_1", str(out_main))
        _set_component_filepath(config, "tLogRow_2", str(out2))

        _run_job(config, java_bridge=java_bridge)

        assert out_main.exists(), "out.csv should exist"
        rows = _read_csv(out_main)
        # All 7 employees have countries in lookup and regions in regions_meta
        assert len(rows) > 0, (
            "Issue 3: expected matched rows for row2.region.trim() join, got 0. "
            "This indicates joined_lookup_names was not passed correctly (D-04 bug)."
        )
        # Check that continent column (from row3) is populated
        non_empty_continent = [r for r in rows if r.get("continent")]
        assert len(non_empty_continent) > 0, (
            "continent column (from row3) is empty -- row3 lookup not resolved correctly"
        )

        assert_ascii_logs


class TestIssue5ChainedVarsSimpleOutputs:
    """Issue 5: chained variable expressions where outputs are simple column refs.

    vars_simple.json has 3 variables:
      var1 = row1.salary.toString()           -> e.g. "85000"
      var2 = Var.var1 + "_USD"               -> e.g. "85000_USD"
      var3 = Var.var2.length() > 4 ? "LONG" : "SHORT"  -> "LONG"

    The output columns 'v2' and 'v3' reference Var.var2 and Var.var3 respectively.
    Before the fix, variables were evaluated without the Var namespace, so v2/v3
    were empty.
    """

    def test_issue_5_chained_vars_simple_outputs(
        self, java_bridge, tmp_path, assert_ascii_logs
    ):
        """Runs vars_simple.json; v2=='85000_USD' and v3=='LONG' for first row."""
        config = _load_config("vars_simple")
        out_main, _ = _wire_two_input_job(config, tmp_path)

        _run_job(config, java_bridge=java_bridge)

        assert out_main.exists(), "out.csv should exist"
        rows = _read_csv(out_main)
        assert len(rows) > 0, "Expected at least one output row"

        # Find the row for John Smith (salary=85000, country=US)
        john_rows = [r for r in rows if r.get("department") == "Engineering" and r.get("salary") == "85000"]
        assert john_rows, f"No row for John Smith found; got rows: {rows[:2]}"
        john = john_rows[0]

        assert john["v2"] == "85000_USD", (
            f"Issue 5: v2 should be '85000_USD', got {john['v2']!r}. "
            "Chained variable Var.var1 + '_USD' not evaluated correctly."
        )
        assert john["v3"] == "LONG", (
            f"Issue 5: v3 should be 'LONG', got {john['v3']!r}. "
            "Ternary on Var.var2.length() not evaluated correctly."
        )

        assert_ascii_logs


class TestMarkerPresentNoBridgeHardFail:
    """D-01: hard-fail when {{java}} expressions present but bridge unavailable.

    Per D-01 and PATTERNS.md: if ANY field has a {{java}} marker and the bridge
    is None, _validate_config raises ConfigurationError. This is NOT a regression
    test for a fix -- it's a sentinel that confirms the universal marker rule
    is enforced independently of the java_bridge fixture.
    """

    def test_marker_present_no_bridge_hard_fails(self):
        """Map with {{java}} expression and java_bridge=None must raise ConfigurationError."""
        config = {
            "component_type": "Map",
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
                        "lookup_mode": "LOAD_ONCE",
                        "filter": "",
                        "activate_filter": False,
                        "join_keys": [
                            {
                                "lookup_column": "country_code",
                                "expression": "{{java}}row1.country_code",
                                "type": "str",
                                "nullable": True,
                                "operator": "=",
                            }
                        ],
                        "join_mode": "LEFT_OUTER_JOIN",
                    }
                ],
            },
            "variables": [],
            "outputs": [
                {
                    "name": "out",
                    "is_reject": False,
                    "inner_join_reject": False,
                    "filter": "",
                    "activate_filter": False,
                    "columns": [
                        {
                            "name": "id",
                            "expression": "{{java}}row1.id",
                            "type": "int",
                            "nullable": True,
                        }
                    ],
                    "catch_output_reject": False,
                }
            ],
            "die_on_error": True,
        }

        import copy

        comp = Map(
            component_id="tMap_no_bridge",
            config=config,
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        comp.java_bridge = None  # Explicitly no bridge
        # Populate self.config (normally done by execute() before _validate_config)
        comp.config = copy.deepcopy(comp._original_config)

        with pytest.raises(ConfigurationError, match="Java bridge"):
            comp._validate_config()
