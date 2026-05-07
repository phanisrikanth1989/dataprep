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

    Realistic mix mirroring Citi production tMaps:
      - bucket 0: trivial passthrough     ``main_row.mNNN``
      - bucket 1: null-check + cast       ``(main_row.mNNN != null) ? ... : 0``
      - bucket 2: lookup + nullable
                  string method chain     uses both main and lookup row

    Heavy enough that 250 columns spread across two outputs overflow the
    pre-fix monolithic ``run()`` method's 64KB bytecode budget, but each
    individual output's helper compiles cleanly under 64KB after the
    per-output split.
    """
    name = f"c{col_idx:03d}"
    main_col = f"m{col_idx:03d}"
    bucket = col_idx % 3
    if bucket == 0:
        # Trivial passthrough.
        expr = f"(main_row.{main_col})"
    elif bucket == 1:
        # Null-check + cast + arithmetic.
        expr = (
            f"(main_row.{main_col} != null) "
            f"? (((Number) main_row.{main_col}).intValue() + {col_idx}) "
            f": (-1)"
        )
    else:
        # Lookup + main combined string method chain (the heaviest
        # variant, matches Citi tMap patterns that join lookup labels).
        expr = (
            f"((main_row.{main_col} != null && lk1.label != null) "
            f"? (main_row.{main_col}.toString().trim() + \"|\" "
            f"+ lk1.label.toString().trim() + \"_{col_idx}\") "
            f": \"\")"
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
        bucket = i % 3
        if bucket == 1:
            col_type = "int"   # cast result + arithmetic
        else:
            col_type = "str"   # passthrough or trim-concat
        columns.append({
            "name": name,
            "expression": "{{java}}" + expr,
            "type": col_type,
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
        """250-column output compiles cleanly and produces correct rows.

        Single output with the max agreed-on column count (250) -- this
        is the production cap. Even pre-fix this single-output case
        sometimes compiled, but the post-fix per-output split makes the
        margin comfortable: the helper holds only column expressions
        and the row-build prologue, no variable block / try-catch
        overhead.
        """
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
        # Inputs: main_row.m000="v0_0" (bucket 0 - passthrough),
        #         main_row.m001=1 (bucket 1 - int),
        #         main_row.m002="v0_2" (bucket 2 - trim+concat).
        row0 = out.iloc[0]

        # Bucket 0: passthrough.
        assert row0["c000"] == "v0_0", f"c000 expected 'v0_0', got {row0['c000']!r}"
        assert row0["c003"] == "v0_3", f"c003 expected 'v0_3', got {row0['c003']!r}"

        # Bucket 1: ((Number) main_row.mNNN).intValue() + idx.
        # m001 = 0*10 + 1 = 1, expr = 1 + 1 = 2.
        assert int(row0["c001"]) == 2, f"c001 expected 2, got {row0['c001']!r}"
        # m004 = 0*10 + 4 = 4, expr = 4 + 4 = 8.
        assert int(row0["c004"]) == 8, f"c004 expected 8, got {row0['c004']!r}"

        # Bucket 2: main_row.mNNN.toString().trim() + "|"
        #           + lk1.label.toString().trim() + "_idx".
        # m002 = "v0_2", lookup label = "Label_0" (after .trim()).
        assert row0["c002"] == "v0_2|Label_0_2", (
            f"c002 expected 'v0_2|Label_0_2', got {row0['c002']!r}"
        )
        # m005 = "v0_5".
        assert row0["c005"] == "v0_5|Label_0_5", (
            f"c005 expected 'v0_5|Label_0_5', got {row0['c005']!r}"
        )

    def test_compiles_with_two_outputs_each_max_columns(self, java_bridge):
        """Two outputs of 250 columns each.

        Canonical reproducer for the bug: pre-fix, both outputs' column
        expressions live inside a single monolithic ``run()`` so the
        bytecode budget is 500 columns + variables + try/catch, which
        exceeds 64KB and triggers MethodTooLargeException at
        ``GroovyShell.parse()``. Post-fix: each output gets its own
        helper method (250 columns each), each well under the limit.
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
        # Row 1, bucket 0 passthrough: m000="v1_0".
        assert out.iloc[0]["c000"] == "v1_0"
