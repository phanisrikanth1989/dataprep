"""Regression tests: tMap with 250-column outputs must not exceed JVM 64KB
method limit when compiled by Groovy.

The bug: _build_compiled_script previously emitted a single monolithic Groovy
script whose run() method body was the sum of all output column expressions
across all outputs (plus variables, filters, try/catch wrapper). With high
column counts this run() bytecode crossed the JVM hard limit of 65,535 bytes
per method, triggering groovyjarjarasm.asm.MethodTooLargeException at
GroovyShell.parse() time inside JavaBridge.compileTMapScript.

The fix: split output evaluation into per-output helper methods
(def evalOutput_<name>(int i, RowWrapper main_row, RowWrapper lk1, ..., Map Var))
called from a thin run() loop. Each helper is its own method with its own
64KB budget. Per-output cap of 250 columns (locked by user) is comfortably
below the per-method limit.

Tests in this module exercise the real Java bridge (mock-only tests would
not catch a Groovy compile failure -- see memory: feedback_test_real_bridge).
"""
from __future__ import annotations

import copy

import pandas as pd
import pytest

from src.v1.engine.components.transform.map import Map
from src.v1.engine.global_map import GlobalMap


# The ``java_bridge`` fixture (session-scoped, real JVM subprocess) is
# provided by ``tests/v1/engine/conftest.py``. Per project memory
# ``feedback_test_real_bridge``, this regression suite must exercise the
# real bridge -- a mock-only test would not catch a Groovy compile failure
# at GroovyShell.parse() time.


# ------------------------------------------------------------------
# Synthetic 250-column tMap config
# ------------------------------------------------------------------


def _wide_column_expression(col_idx: int) -> tuple[str, str]:
    """Generate (name, expression) for column col_idx.

    Mix of expression shapes used across real Citi Talend jobs. Every
    bucket produces a non-trivial expression so 250 columns reliably
    overflow the JVM 64KB method limit on the pre-fix monolithic run().
      - bucket 0: nested-null-guard + cast + arithmetic + concat
      - bucket 1: chained method calls + lookup ref + concat
      - bucket 2: combined main+lookup nullable string concat
    """
    name = f"c{col_idx:03d}"
    main_col = f"m{col_idx:03d}"
    bucket = col_idx % 3
    if bucket == 0:
        # Heavy null-check + cast + arithmetic + string concat. Every
        # operator + cast + concat call adds a dispatch site to bytecode.
        expr = (
            f"((main_row.{main_col} != null && lk1.label != null) "
            f"? (main_row.{main_col}.toString().trim() "
            f"+ \"|\" + lk1.label.toString().trim() "
            f"+ \"|{col_idx}\") "
            f": ((main_row.{main_col} != null) "
            f"? main_row.{main_col}.toString() : \"NA_{col_idx}\"))"
        )
    elif bucket == 1:
        # Multi-method chain on string with default.
        expr = (
            f"((main_row.key != null) "
            f"? (main_row.key.toString().trim() + \"-\" "
            f"+ ((main_row.{main_col} != null) "
            f"? main_row.{main_col}.toString() : \"\") "
            f"+ \"-{col_idx}\") "
            f": (\"X-{col_idx}\"))"
        )
    else:
        # Combined main + lookup nullable concat with constant.
        expr = (
            f"((lk1.label != null && main_row.{main_col} != null) "
            f"? (main_row.{main_col}.toString() + \"+\" "
            f"+ lk1.label.toString().trim() + \"={col_idx}\") "
            f": ((main_row.{main_col} != null) "
            f"? main_row.{main_col}.toString().trim() "
            f": \"none_{col_idx}\"))"
        )
    return name, expr


def _build_wide_tmap_config(num_cols: int) -> dict:
    """Build a tMap config with 1 main + 1 lookup, single output of num_cols.

    Includes:
      - 4 variables (forces variable evaluation block in script)
      - inner-join lookup with single key
      - heavy mix of column expressions sized to overflow the monolithic
        run() bytecode budget pre-fix.
    """
    columns = []
    for i in range(num_cols):
        name, expr = _wide_column_expression(i)
        columns.append({
            "name": name,
            "expression": "{{java}}" + expr,
            # All buckets now produce String -- nested null-guarded concats.
            "type": "str",
            "nullable": True,
        })

    return {
        "component_type": "Map",
        "inputs": {
            "main": {
                "name": "main_row",
                "filter": "",
                "activate_filter": False,
                "matching_mode": "UNIQUE_MATCH",
                "lookup_mode": "LOAD_ONCE",
            },
            "lookups": [{
                "name": "lk1",
                "matching_mode": "UNIQUE_MATCH",
                "lookup_mode": "LOAD_ONCE",
                "filter": "",
                "activate_filter": False,
                "join_keys": [{
                    "lookup_column": "key",
                    "expression": "{{java}}main_row.key",
                    "type": "str",
                    "nullable": False,
                    "operator": "=",
                }],
                "join_mode": "LEFT_OUTER_JOIN",
            }],
        },
        "variables": [
            {"name": "v1", "expression": "{{java}}((main_row.key != null) ? main_row.key.toString() : \"\")"},
            {"name": "v2", "expression": "{{java}}((main_row.m000 != null) ? main_row.m000.toString().trim() : \"\")"},
            {"name": "v3", "expression": "{{java}}((lk1.label != null) ? lk1.label.toString().trim() : \"NA\")"},
            {"name": "v4", "expression": "{{java}}(Var.get(\"v1\") + \"|\" + Var.get(\"v3\"))"},
        ],
        "outputs": [{
            "name": "out1",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": columns,
            "catch_output_reject": False,
        }],
        "die_on_error": True,
    }


def _build_wide_input_dataframes(num_cols: int, num_rows: int = 3):
    """Build matching main + lookup DataFrames for the wide config."""
    main_rows = []
    for r in range(num_rows):
        row = {"key": f"K{r}"}
        for i in range(num_cols):
            cname = f"m{i:03d}"
            # Mix of int-ish and string-ish values (mirrors expression buckets).
            if i % 3 == 1:
                row[cname] = r * 10 + i
            else:
                row[cname] = f"v{r}_{i}"
        main_rows.append(row)

    lookup_rows = [
        {"key": f"K{r}", "label": f"  Label_{r}  "} for r in range(num_rows)
    ]
    return pd.DataFrame(main_rows), pd.DataFrame(lookup_rows)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


@pytest.mark.java
@pytest.mark.integration
class TestTMapMethodSize:
    """End-to-end tMap compilation + execution with 250-column output.

    Pre-fix: compileTMapScript throws groovyjarjarasm.asm.MethodTooLargeException
    (often wrapped as groovy.lang.GroovyRuntimeException) because run() bytecode
    exceeds 65,535 bytes.

    Post-fix: per-output method split keeps each method below the limit,
    compilation + execution succeed, output rows match expected values.
    """

    NUM_COLS = 250
    NUM_ROWS = 3

    def test_compiles_and_executes_with_250_columns(self, java_bridge):
        """250-column output compiles cleanly and produces correct rows."""
        config = _build_wide_tmap_config(self.NUM_COLS)
        main_df, lookup_df = _build_wide_input_dataframes(
            self.NUM_COLS, self.NUM_ROWS
        )

        gm = GlobalMap()
        comp = Map(component_id="tMap_wide", config=config, global_map=gm)
        comp.java_bridge = java_bridge

        result = comp.execute({"main_row": main_df, "lk1": lookup_df})

        assert "out1" in result, "Expected 'out1' in result dict"
        out = result["out1"]
        assert len(out) == self.NUM_ROWS, (
            f"Expected {self.NUM_ROWS} rows, got {len(out)}"
        )
        assert len(out.columns) == self.NUM_COLS, (
            f"Expected {self.NUM_COLS} output columns, got {len(out.columns)}"
        )

        # Spot-check column values for row 0.
        # Inputs: main_row.key="K0", main_row.m000="v0_0", main_row.m003="v0_3",
        #         lk1.label="Label_0" (joined value, lookup .trim() applied
        #         in expression).
        row0 = out.iloc[0]

        # Bucket 0 (col_idx % 3 == 0): both non-null -> trimmed-main + "|"
        # + trimmed-lookup + "|<idx>".
        # m000="v0_0", lookup label trimmed="Label_0", idx=0
        assert row0["c000"] == "v0_0|Label_0|0", (
            f"c000 expected 'v0_0|Label_0|0', got {row0['c000']!r}"
        )
        # m003="v0_3", idx=3
        assert row0["c003"] == "v0_3|Label_0|3", (
            f"c003 expected 'v0_3|Label_0|3', got {row0['c003']!r}"
        )

        # Bucket 1 (col_idx % 3 == 1): trimmed-key + "-" + main + "-" + idx.
        # key="K0", m001=1 (int -> toString -> "1"), idx=1
        assert row0["c001"] == "K0-1-1", (
            f"c001 expected 'K0-1-1', got {row0['c001']!r}"
        )

        # Bucket 2 (col_idx % 3 == 2): main + "+" + trimmed-lookup + "=<idx>".
        # m002="v0_2", lookup label trimmed="Label_0", idx=2
        assert row0["c002"] == "v0_2+Label_0=2", (
            f"c002 expected 'v0_2+Label_0=2', got {row0['c002']!r}"
        )

    def test_compiles_with_two_outputs_each_max_columns(self, java_bridge):
        """Two outputs of 250 columns each -- doubles total expression count.

        Pre-fix this would also overflow because all outputs lived in the
        same monolithic run(). Post-fix: each output is its own method
        with its own 64KB budget, so this comfortably succeeds.
        """
        base = _build_wide_tmap_config(self.NUM_COLS)
        out2_cols = copy.deepcopy(base["outputs"][0]["columns"])
        base["outputs"].append({
            "name": "out2",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": out2_cols,
            "catch_output_reject": False,
        })

        main_df, lookup_df = _build_wide_input_dataframes(
            self.NUM_COLS, self.NUM_ROWS
        )

        gm = GlobalMap()
        comp = Map(component_id="tMap_wide_2out", config=base, global_map=gm)
        comp.java_bridge = java_bridge

        result = comp.execute({"main_row": main_df, "lk1": lookup_df})
        assert "out1" in result and "out2" in result
        assert len(result["out1"]) == self.NUM_ROWS
        assert len(result["out2"]) == self.NUM_ROWS
        assert len(result["out1"].columns) == self.NUM_COLS
        assert len(result["out2"].columns) == self.NUM_COLS

    def test_filter_folded_into_helper(self, java_bridge):
        """Output filter is evaluated inside the helper; rejected rows omitted.

        Validates the helper-returns-null contract: when activate_filter=True
        and filter rejects the row, helper returns null and the run() loop
        skips that row's slot.
        """
        config = _build_wide_tmap_config(self.NUM_COLS)
        # Filter: only keep rows where main_row.key equals "K1".
        config["outputs"][0]["activate_filter"] = True
        config["outputs"][0]["filter"] = (
            "{{java}}main_row.key.equals(\"K1\")"
        )

        main_df, lookup_df = _build_wide_input_dataframes(
            self.NUM_COLS, self.NUM_ROWS
        )

        gm = GlobalMap()
        comp = Map(component_id="tMap_wide_filter", config=config, global_map=gm)
        comp.java_bridge = java_bridge

        result = comp.execute({"main_row": main_df, "lk1": lookup_df})
        out = result["out1"]
        # 3 input rows, only "K1" passes -> 1 output row.
        assert len(out) == 1, f"Expected 1 row after filter, got {len(out)}"
        # Row 1: m000="v1_0", lk1.label trimmed="Label_1", idx=0.
        assert out.iloc[0]["c000"] == "v1_0|Label_1|0"
