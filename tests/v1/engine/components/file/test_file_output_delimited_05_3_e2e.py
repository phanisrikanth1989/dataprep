"""End-to-end regression test for Phase 05.3 Issue 6: filepath as Java expression.

Issue 6: When the converter's FILENAME parameter contains operators (e.g.
`context.OUT_DIR + context.OUT_NAME + context.OUT_EXT`), the converter now
marks it with `{{java}}`. The engine's FileOutputDelimited._resolve_java_expr_param
evaluates the marked expression via the bridge and uses the result as the
actual file path.

Before the fix (plan 06), the engine wrote the file to a path that literally
contained the `+` operators (e.g. `"/tmp/repro + output_via_expr + .csv"`),
because context resolution leaves operator strings untouched and the engine
never sent them to the bridge.

Test: filepath_expr.json has `{{java}}context.OUT_DIR + context.OUT_NAME + context.OUT_EXT`.
Override context vars via ETLEngine.set_context_variable so the resolved path
ends up at `tmp_path / "output_via_expr.csv"`. Assert the file exists there
and NOT at a path containing literal `+` operators.

All tests are @pytest.mark.java + @pytest.mark.integration (live bridge needed
for bridge evaluation of filepath expression).

Project memory: feedback_test_real_bridge -- mock-only tests are insufficient
for bridge-path coverage. D-06 specifically added the bridge call site in
file_output_delimited._resolve_java_expr_param.
"""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from src.v1.engine.engine import ETLEngine

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
    """Load a fixture job config and return a deep copy."""
    path = FIXTURES_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _set_component_filepath(config: Dict[str, Any], comp_id: str, path: str) -> None:
    """Set filepath on a component's config (in-place)."""
    for comp in config["components"]:
        if comp["id"] == comp_id:
            comp.setdefault("config", {})["filepath"] = path
            return
    raise KeyError(f"Component '{comp_id}' not found in config")


def _set_context_var(config: Dict[str, Any], var_name: str, value: str) -> None:
    """Set a context variable in the job config's Default context (in-place)."""
    ctx = config.setdefault("context", {}).setdefault("Default", {})
    ctx[var_name] = {"value": value, "type": "str"}


def _run_job(config: Dict[str, Any]) -> ETLEngine:
    """Run the ETL engine and return the engine instance."""
    engine = ETLEngine(copy.deepcopy(config))
    stats = engine.execute()
    if stats.get("status") == "error":
        raise RuntimeError(
            f"ETLEngine reported error: {stats.get('error', 'unknown')}"
        )
    return engine


class TestIssue6FilepathExpr:
    """Issue 6: filepath as Java expression evaluated correctly by engine.

    The converter marks `context.OUT_DIR + context.OUT_NAME + context.OUT_EXT`
    with `{{java}}`. The engine must evaluate it via the bridge and write to
    the resolved path, NOT to a path with literal `+` operators.
    """

    def test_issue_6_filepath_expr(self, java_bridge, tmp_path, assert_ascii_logs):
        """Run filepath_expr.json; output must be at resolved path, not at + path."""
        config = _load_config("filepath_expr")

        # Set input file (employees with email schema)
        input_csv = str(DATA_DIR / "employees_with_email.csv")
        _set_component_filepath(config, "tFileInputDelimited_1", input_csv)

        # Override context vars so output goes to tmp_path
        out_dir = str(tmp_path) + "/"
        out_name = "output_via_expr"
        out_ext = ".csv"
        _set_context_var(config, "OUT_DIR", out_dir)
        _set_context_var(config, "OUT_NAME", out_name)
        _set_context_var(config, "OUT_EXT", out_ext)

        expected_path = tmp_path / "output_via_expr.csv"

        _run_job(config)

        # The file must exist at the RESOLVED path
        assert expected_path.exists(), (
            f"Issue 6: expected output at {expected_path}, but file not found. "
            f"Check whether {{{{java}}}} marker was evaluated or left as literal string."
        )

        # Verify the file contains data (not empty)
        with expected_path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f, delimiter=";"))
        assert len(rows) > 0, f"Output file is empty: {expected_path}"

        # Sanity: no + operator in the file path on disk
        for bad_path in tmp_path.parent.glob("* + *"):
            pytest.fail(
                f"Issue 6: file with literal '+' in path found: {bad_path}. "
                "The filepath expression was not evaluated via the bridge."
            )

        assert_ascii_logs
