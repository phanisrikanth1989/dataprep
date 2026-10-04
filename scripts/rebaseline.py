#!/usr/bin/env python3
"""Re-baseline a component's benchmark by running the benchmark pair and writing JSON.

Usage:
    python scripts/rebaseline.py <component_name>
    python scripts/rebaseline.py filter_columns
    python scripts/rebaseline.py --all

Runs the benchmark test pair (test_benchmark_v2 + test_benchmark_raw_polars)
for the named component, captures timing, and writes the baseline JSON to
tests/v2/benchmark/baselines/<component>.json.

Baseline JSON schema:
{
    "component": "<name>",
    "polars_version": "1.38.x",
    "python_version": "3.12.x",
    "raw_polars_median_ns": <int>,
    "raw_polars_iqr_ns": <int>,
    "v2_median_ns": <int>,
    "v2_iqr_ns": <int>,
    "n_runs": <int>,
    "ratio": <float>,
    "timestamp": "ISO-8601",
    "machine_hash": "<hash>"
}
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import statistics
import sys
import time
from pathlib import Path

BASELINES_DIR = Path(__file__).resolve().parent.parent / "tests" / "v2" / "benchmark" / "baselines"

# Benchmark parameters per D-17
WARMUP = 1000
N_RUNS = 5
DISABLE_GC = True


def _machine_hash() -> str:
    """Deterministic hash of machine identity for baseline provenance."""
    raw = f"{platform.node()}:{platform.machine()}:{platform.processor()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _time_callable(fn, warmup: int = WARMUP, n: int = N_RUNS) -> tuple[float, float]:
    """Run fn warmup times, then n times, return (median_ns, iqr_ns)."""
    # Warmup
    for _ in range(warmup):
        fn()

    if DISABLE_GC:
        gc.disable()

    try:
        timings = []
        for _ in range(n):
            start = time.perf_counter_ns()
            fn()
            end = time.perf_counter_ns()
            timings.append(end - start)
    finally:
        if DISABLE_GC:
            gc.enable()

    timings.sort()
    median = statistics.median(timings)
    q1 = timings[len(timings) // 4]
    q3 = timings[3 * len(timings) // 4]
    iqr = q3 - q1
    return median, iqr


def write_baseline(
    component: str,
    raw_polars_fn,
    v2_fn,
    n_runs: int = N_RUNS,
) -> Path:
    """Run benchmark pair and write baseline JSON."""
    import polars as pl

    raw_median, raw_iqr = _time_callable(raw_polars_fn, n=n_runs)
    v2_median, v2_iqr = _time_callable(v2_fn, n=n_runs)

    baseline = {
        "component": component,
        "polars_version": pl.__version__,
        "python_version": platform.python_version(),
        "raw_polars_median_ns": int(raw_median),
        "raw_polars_iqr_ns": int(raw_iqr),
        "v2_median_ns": int(v2_median),
        "v2_iqr_ns": int(v2_iqr),
        "n_runs": n_runs,
        "ratio": round(v2_median / raw_median, 4) if raw_median > 0 else 0.0,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "machine_hash": _machine_hash(),
    }

    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BASELINES_DIR / f"{component}.json"
    out_path.write_text(json.dumps(baseline, indent=2) + "\n")
    return out_path


def load_baseline(component: str) -> dict | None:
    """Load an existing baseline JSON, or None if not found."""
    path = BASELINES_DIR / f"{component}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description="Re-baseline component benchmarks")
    parser.add_argument("component", help="Component name (e.g., filter_columns) or --all")
    parser.add_argument("--n-runs", type=int, default=N_RUNS, help=f"Number of timed runs (default: {N_RUNS})")
    args = parser.parse_args()

    print(f"Rebaseline is a library; component benchmarks call write_baseline() directly.")
    print(f"To re-baseline {args.component}, run its benchmark test with REBASELINE=1:")
    print(f"  REBASELINE=1 pytest tests/v2 -m benchmark -k {args.component} -x -q")


if __name__ == "__main__":
    main()
