"""Time the payments job on v1 and on v2, and check that they write the same files.

    python -m scenarios.payments.run --rows 1000000
    python -m scenarios.payments.run --rows 1000000,2000000,5000000 --work /data/payments

For each row count this makes the input files, runs every variant of the
job as a process of its own, compares the files the variants wrote, and
prints a table. The variants:

``v2``        the Python job file on the v2 engine;
``v1-pymap``  the same Python job file on v1;
``v1-java``   the Java job file on v1, through the Java bridge.

What is timed is the whole process, from its start to its exit: starting
Python (and Java), loading the job, reading, transforming and writing. A v1
run that passes the cap is stopped and reported as stopped.

Run it from the repository's root. ``java`` has to be on the PATH for the
``v1-java`` variant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import data, jobs

REPO = Path(__file__).resolve().parents[2]
# Variant -> (engine, spelling of the job file).
VARIANTS: Dict[str, Tuple[str, str]] = {"v2": ("v2", "python"), "v1-pymap": ("v1", "python"), "v1-java": ("v1", "java")}
FINISHED, FAILED, STOPPED = "finished", "failed", "stopped at the cap"
_POLL_S = 0.01


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the scenario. Returns 0 when every run finished and every file matched, else 1."""
    parser = argparse.ArgumentParser(prog="python -m scenarios.payments.run", description=__doc__.split("\n\n")[0])
    parser.add_argument("--rows", default="1000000", help="Payments to run with; several sizes separated by commas.")
    parser.add_argument("--work", default="payments_work", help="The folder for the data, the outputs and the results.")
    parser.add_argument("--variants", default=",".join(VARIANTS), help=f"Which to run, of: {', '.join(VARIANTS)}.")
    parser.add_argument("--v2-runs", type=int, default=3, help="Runs of v2 at each size; the middle one is reported.")
    parser.add_argument("--v1-runs", type=int, default=1, help="Runs of each v1 variant at each size.")
    parser.add_argument("--v1-cap", type=float, default=1200.0, help="Seconds after which a v1 run is stopped.")
    args = parser.parse_args(argv)

    variants = [name.strip() for name in args.variants.split(",") if name.strip()]
    unknown = [name for name in variants if name not in VARIANTS]
    if unknown:
        parser.error(f"unknown variant(s) {', '.join(unknown)}; use {', '.join(VARIANTS)}")
    work = Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)

    runs: List[Dict[str, Any]] = []
    for rows in [int(size) for size in args.rows.split(",")]:
        runs += _one_size(rows, work, variants, args.v2_runs, args.v1_runs, args.v1_cap)
        # Written after every size, so a long session that is cut short keeps what it has.
        report = {"machine": _machine(), "runs": runs}
        (work / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (work / "results.md").write_text(_table(runs, markdown=True), encoding="utf-8")
    print(_table(runs))
    good = all(run["status"] == FINISHED and run["same_files_as_v2"] is not False for run in runs)
    return 0 if good else 1


# ------------------------------------------------------------------
# One size
# ------------------------------------------------------------------

def _one_size(rows: int, work: Path, variants: List[str], v2_runs: int, v1_runs: int, cap: float) -> List[Dict[str, Any]]:
    data_dir = work / f"data_{rows}"
    marker = data_dir / "rows.txt"
    if not marker.exists():
        print(f"[{rows:,} rows] making the input files in {data_dir}", flush=True)
        data.generate(data_dir, rows)
        marker.write_text(str(rows), encoding="ascii")

    found: List[Dict[str, Any]] = []
    hashes: Dict[str, Dict[str, str]] = {}
    for variant in variants:
        engine, spelling = VARIANTS[variant]
        out_dir = work / f"out_{rows}_{variant}"
        out_dir.mkdir(exist_ok=True)
        job_path = jobs.write(spelling, data_dir, out_dir, out_dir / f"job_{spelling}.json")
        count = v2_runs if engine == "v2" else v1_runs
        timings: List[Dict[str, Any]] = []
        for number in range(1, count + 1):
            print(f"[{rows:,} rows] {variant}: run {number} of {count}", flush=True)
            for name in jobs.OUTPUTS:
                (out_dir / name).unlink(missing_ok=True)
            timing = _run_once(engine, job_path, out_dir / "note.json", out_dir / f"run_{number}.log",
                               cap if engine == "v1" else None)
            timings.append(timing)
            print(f"[{rows:,} rows] {variant}: {timing['status']} after {timing['seconds']:.1f} s", flush=True)
            if timing["status"] != FINISHED:
                break
        entry = _entry(rows, variant, engine, timings)
        if entry["status"] == FINISHED:
            hashes[variant] = {name: _digest(out_dir / name) for name in jobs.OUTPUTS}
        found.append(entry)

    for entry in found:
        ours, theirs = hashes.get(entry["variant"]), hashes.get("v2")
        if entry["variant"] != "v2" and ours is not None and theirs is not None:
            entry["different_files"] = sorted(name for name in jobs.OUTPUTS if ours[name] != theirs[name])
            entry["same_files_as_v2"] = not entry["different_files"]
    return found


def _entry(rows: int, variant: str, engine: str, timings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """What is reported for a variant at a size: its middle run when all finished, else its last run."""
    last = timings[-1]
    finished = [timing for timing in timings if timing["status"] == FINISHED]
    if last["status"] == FINISHED:
        middle = statistics.median(timing["seconds"] for timing in finished)
        shown = min(finished, key=lambda timing: abs(timing["seconds"] - middle))
    else:
        shown = last
    return {
        "rows": rows, "variant": variant, "engine": engine, "status": last["status"], "error": last["error"],
        "seconds": [round(timing["seconds"], 2) for timing in timings],
        "reported_seconds": round(shown["seconds"], 2),
        "peak_memory_gb": round(max(timing["peak_memory_gb"] for timing in timings), 2),
        "stages": shown["stages"], "components": shown["components"],
        "same_files_as_v2": None, "different_files": [],
    }


# ------------------------------------------------------------------
# One run
# ------------------------------------------------------------------

def _run_once(engine: str, job_path: Path, note_path: Path, log_path: Path, cap: Optional[float]) -> Dict[str, Any]:
    """Run the job once in a process of its own; time it and take the most memory it held."""
    note_path.unlink(missing_ok=True)
    command = [sys.executable, "-m", "scenarios.payments.engine_run", engine, str(job_path), str(note_path)]
    stopped = False
    with open(log_path, "wb") as log:
        started = time.perf_counter()
        # A session of its own, so that stopping it also stops the Java process it started.
        process = subprocess.Popen(command, cwd=REPO, stdout=log, stderr=log, start_new_session=True)
        while True:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                break
            if cap is not None and time.perf_counter() - started > cap:
                os.killpg(process.pid, signal.SIGKILL)
                _, status, usage = os.wait4(process.pid, 0)
                stopped = True
                break
            time.sleep(_POLL_S)
        seconds = time.perf_counter() - started
    process.returncode = os.waitstatus_to_exitcode(status)

    note: Dict[str, Any] = {}
    if note_path.exists():
        note = json.loads(note_path.read_text(encoding="utf-8"))
    if stopped:
        outcome, error = STOPPED, f"stopped after {cap:.0f} s"
    elif process.returncode == 0 and note.get("status") == "success":
        outcome, error = FINISHED, ""
    else:
        outcome = FAILED
        error = note.get("error") or f"exit code {process.returncode}; see {log_path}"
    # macOS reports the most memory held in bytes, Linux in kilobytes.
    held = usage.ru_maxrss if sys.platform == "darwin" else usage.ru_maxrss * 1024
    return {
        "status": outcome, "error": error, "seconds": seconds, "peak_memory_gb": held / 1e9,
        "stages": note.get("stages", []), "components": note.get("components", {}),
    }


def _digest(path: Path) -> str:
    found = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 24):
            found.update(chunk)
    return found.hexdigest()


# ------------------------------------------------------------------
# Reporting
# ------------------------------------------------------------------

def _machine() -> Dict[str, Any]:
    import pandas
    import polars

    try:
        memory_gb = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 1)
    except (ValueError, OSError):
        memory_gb = None
    return {
        "system": f"{platform.system()} {platform.release()}", "processor": platform.processor() or platform.machine(),
        "cores": os.cpu_count(), "memory_gb": memory_gb, "python": platform.python_version(),
        "polars": polars.__version__, "pandas": pandas.__version__,
    }


def _table(runs: List[Dict[str, Any]], markdown: bool = False) -> str:
    """The results as a table: one line per variant and size."""
    names = ["start-up", *[stage for stage in ("settings", "validate and enrich", "reject report")]]
    head = ["rows", "variant", "result", "time", "memory", *names, "same files as v2"]
    lines: List[List[str]] = []
    for run in runs:
        stages = {stage["name"]: stage["seconds"] for stage in run["stages"]}
        same = {None: "-", True: "yes", False: "NO: " + ", ".join(run["different_files"])}[run["same_files_as_v2"]]
        lines.append([
            f"{run['rows']:,}", run["variant"], run["status"], f"{run['reported_seconds']:.1f} s",
            f"{run['peak_memory_gb']:.1f} GB",
            *[f"{stages[name]:.1f} s" if name in stages else "-" for name in names],
            "-" if run["variant"] == "v2" else same,
        ])
    if markdown:
        rule = ["---"] * len(head)
        return "\n".join("| " + " | ".join(line) + " |" for line in [head, rule, *lines]) + "\n"
    widths = [max(len(line[place]) for line in [head, *lines]) for place in range(len(head))]
    return "\n".join("  ".join(cell.ljust(width) for cell, width in zip(line, widths)).rstrip() for line in [head, *lines])


if __name__ == "__main__":
    sys.exit(main())
