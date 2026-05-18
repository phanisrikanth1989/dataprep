#!/usr/bin/env python3
"""Diff harness: run every tMap fixture through both new Map and legacy
Map, assert outputs are equal.

Usage:
    python scripts/diff_map_outputs.py [fixture_glob]

Default glob: tests/fixtures/jobs/transform/**/*.json
Exit code 0 if all fixtures produce equal outputs, 1 on any divergence.

Requires a running JVM (the new Map needs java_bridge for {{java}} marked
expressions). The script sets up a JavaBridgeManager inline.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import traceback
from pathlib import Path

import pandas as pd


def _import_map_classes():
    """Return (NewMap, LegacyMap)."""
    from src.v1.engine.components.transform.map.map_component import Map as NewMap
    from src.v1.engine.components.transform.map_legacy import Map as LegacyMap
    return NewMap, LegacyMap


def _start_bridge():
    """Start a JavaBridge for the duration of the run."""
    from src.v1.engine.java_bridge_manager import JavaBridgeManager
    mgr = JavaBridgeManager(enable=True, routines=[
        "routines.StringHandling",
        "routines.TalendString",
        "routines.TalendDate",
        "routines.Mathematical",
    ])
    mgr.start()
    return mgr


def _build_synthetic_inputs(map_comp_cfg, n_main=3, n_lookup=3) -> dict[str, pd.DataFrame]:
    """Build synthetic input DataFrames for each declared input flow.

    Uses the per-flow schema from `comp["schema"]["inputs"]` if present.
    Generates 3 rows per main, 3 rows per lookup with simple values.
    """
    schema_inputs = map_comp_cfg.get("schema", {}).get("inputs", {})
    main_name = map_comp_cfg["config"]["inputs"]["main"]["name"]

    inputs: dict[str, pd.DataFrame] = {}
    for flow_name, cols in schema_inputs.items():
        if not cols:
            continue
        n = n_main if flow_name == main_name else n_lookup
        data = {}
        for c in cols:
            col_type = c.get("type", "str")
            if col_type == "int":
                data[c["name"]] = list(range(1, n + 1))
            elif col_type == "float":
                data[c["name"]] = [1.0 * (i + 1) for i in range(n)]
            elif col_type == "bool":
                data[c["name"]] = [i % 2 == 0 for i in range(n)]
            else:  # str / datetime / Decimal -- use strings
                data[c["name"]] = [f"v{i}" for i in range(n)]
        inputs[flow_name] = pd.DataFrame(data)
    return inputs


def _run_one(MapClass, comp, inputs, bridge_mgr):
    """Instantiate MapClass, attach bridge + schemas, execute, return result."""
    m = MapClass(comp["id"], comp["config"])
    m.schema_inputs_map = comp.get("schema", {}).get("inputs", {})
    m.output_schema = comp.get("schema", {}).get("output", [])
    m.java_bridge = bridge_mgr.get_bridge()
    return m.execute(inputs)


_SKIP = "SKIP"  # sentinel status for schema-less fixtures


def diff_one_fixture(fixture_path: str, bridge_mgr) -> tuple[str, str]:
    """Return (status, message) where status is 'OK', 'FAIL', 'SKIP', or 'NONE'."""
    NewMap, LegacyMap = _import_map_classes()
    try:
        job = json.loads(Path(fixture_path).read_text())
    except Exception as e:
        return "FAIL", f"json load failed: {e}"

    diffs = []
    map_comps_found = 0
    skipped_comps = 0
    for comp in job.get("components", []):
        if comp.get("type") not in ("Map", "tMap"):
            continue
        map_comps_found += 1
        inputs = _build_synthetic_inputs(comp)
        if not inputs:
            skipped_comps += 1
            continue

        try:
            new_result = _run_one(NewMap, comp, inputs, bridge_mgr)
        except Exception as e:
            return "FAIL", f"  {comp['id']} NEW raised {type(e).__name__}: {e}\n{traceback.format_exc()}"
        try:
            legacy_result = _run_one(LegacyMap, comp, inputs, bridge_mgr)
        except Exception as e:
            return "FAIL", f"  {comp['id']} LEGACY raised {type(e).__name__}: {e}\n{traceback.format_exc()}"

        for out_name, new_df in new_result.items():
            if out_name in ("stats",) or not isinstance(new_df, pd.DataFrame):
                continue
            if out_name not in legacy_result or not isinstance(legacy_result[out_name], pd.DataFrame):
                continue
            legacy_df = legacy_result[out_name]
            try:
                pd.testing.assert_frame_equal(
                    new_df.reset_index(drop=True),
                    legacy_df.reset_index(drop=True),
                    check_dtype=False,
                )
            except AssertionError as e:
                diffs.append(
                    f"  {comp['id']}/{out_name} diverges:\n    {str(e).splitlines()[0]}"
                )

    if map_comps_found == 0:
        return "NONE", "no Map components"
    if skipped_comps == map_comps_found:
        return "SKIP", f"all {skipped_comps} Map component(s) lack schema.inputs"
    if diffs:
        return "FAIL", "\n".join(diffs)
    return "OK", "OK"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("glob", nargs="?", default="tests/fixtures/jobs/transform/**/*.json")
    args = parser.parse_args()

    fixtures = sorted(glob.glob(args.glob, recursive=True))
    if not fixtures:
        print(f"No fixtures matched {args.glob}")
        return 1

    bridge_mgr = _start_bridge()
    try:
        failures = []
        skipped = []
        passed = []
        for f in fixtures:
            status, msg = diff_one_fixture(f, bridge_mgr)
            if status == "NONE":
                continue  # not a Map fixture at all
            if status == "SKIP":
                print(f"SKIP {f}  [{msg}]")
                skipped.append(f)
            elif status == "FAIL":
                print(f"FAIL {f}")
                print(msg)
                failures.append(f)
            else:  # OK
                print(f"OK   {f}")
                passed.append(f)

        total_map_fixtures = len(passed) + len(failures) + len(skipped)
        print(f"\n{len(passed)}/{total_map_fixtures} Map fixtures passed diff")
        if skipped:
            print(f"{len(skipped)} skipped (no schema.inputs -- cannot diff without schema)")
        return 0 if not failures else 1
    finally:
        bridge_mgr.stop()


if __name__ == "__main__":
    sys.exit(main())
