"""Benchmark the engine on a converted Talend job with synthetic data.

Converts a Talend ``.item`` file, points every tFileInputDelimited at a
generated CSV of ``--rows`` rows (tMap lookup inputs get a fixed 200-row
country table so joins match), replaces tLogRow sinks with
tFileOutputDelimited so the run measures real I/O without console spam, runs
the job in-process and prints per-component timings.

Usage (from the repo root)::

    python scripts/benchmark_job.py tests/talend_xml_samples/Job_tMap_0.1.item --rows 1000000
    python scripts/benchmark_job.py <job.item> --rows 200000 --profile

Generated inputs are cached under ``--work-dir`` (one file per job, component
and row count) so repeated runs compare like with like. Output files land in
``--out-dir`` so two code versions can be diffed byte-for-byte. Both default
to ``<system temp>/dataprep_bench`` so nothing is written inside the repo.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import logging
import pstats
import random
import string
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.converters.talend_to_v1.converter import TalendToV1Converter  # noqa: E402
from src.v1.engine.engine import ETLEngine  # noqa: E402

_OUTPUT_CONFIG: Dict[str, Any] = {
    "advanced_separator": False,
    "append": False,
    "compress": False,
    "create_directory": True,
    "csv_option": False,
    "encoding": "UTF-8",
    "fieldseparator": ";",
    "file_exist_exception": False,
    "include_header": True,
    "os_line_separator": False,
    "row_separator": "\\n",
    "split": False,
}
_WORDS = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
          "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa"]
_COUNTRIES = [f"C{i:03d}" for i in range(200)]


def _is_country_code(name: str) -> bool:
    lowered = name.lower()
    return "country" in lowered and "code" in lowered


def _cell(col: Dict[str, Any], row: int, rng: random.Random) -> str:
    """Return one synthetic CSV cell matching the schema column type."""
    name, ctype = col["name"].lower(), col["type"]
    if _is_country_code(name):
        return _COUNTRIES[rng.randrange(len(_COUNTRIES))]
    if ctype == "int":
        if name == "id":
            return str(row)
        if "salary" in name or "amount" in name:
            return str(rng.randrange(30000, 150000))
        return str(rng.randrange(0, 1000))
    if ctype in ("float", "Decimal"):
        return f"{rng.uniform(0, 10000):.2f}"
    if ctype == "datetime":
        return f"2024-{rng.randrange(1, 13):02d}-{rng.randrange(1, 29):02d}"
    if ctype == "bool":
        return rng.choice(["true", "false"])
    return rng.choice(_WORDS) + "".join(rng.choices(string.ascii_lowercase, k=4))


def _write_input(path: Path, schema: List[Dict[str, Any]], rows: int, sep: str,
                 header: bool, is_lookup: bool) -> None:
    """Write a deterministic synthetic CSV for one input component."""
    rng = random.Random(42)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        if header:
            handle.write(sep.join(c["name"] for c in schema) + "\n")
        if is_lookup:
            for code in _COUNTRIES:
                handle.write(sep.join(
                    code if _is_country_code(c["name"]) else _cell(c, 0, rng) for c in schema
                ) + "\n")
            return
        for row in range(rows):
            handle.write(sep.join(_cell(c, row, rng) for c in schema) + "\n")


def build_job(item: Path, rows: int, work_dir: Path, out_dir: Path) -> Dict[str, Any]:
    """Convert ``item`` and rewire its file inputs and log sinks for benchmarking.

    Args:
        item: Talend ``.item`` job file.
        rows: Row count for main (non-lookup) inputs.
        work_dir: Directory for generated input CSVs.
        out_dir: Directory for output CSVs.

    Returns:
        The runnable job config dict.
    """
    cfg = TalendToV1Converter().convert_file(str(item))
    work_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    lookup_flows = {
        lk["name"]
        for c in cfg["components"] if c["type"] == "Map"
        for lk in c["config"]["inputs"].get("lookups", [])
    }
    for comp in cfg["components"]:
        if comp["type"] == "FileInputDelimited":
            is_lookup = any(flow in lookup_flows for flow in comp["outputs"])
            path = work_dir / f"{item.stem}_{comp['id']}_{rows}.csv"
            if not path.exists():
                _write_input(
                    path, comp["schema"]["output"], rows,
                    comp["config"].get("fieldseparator", ";"),
                    int(comp["config"].get("header_rows", 0) or 0) > 0, is_lookup,
                )
            comp["config"].update(filepath=str(path), encoding="UTF-8", csv_option=False)
        elif comp["type"] == "LogRow":
            comp["type"] = "FileOutputDelimited"
            comp["config"] = dict(
                _OUTPUT_CONFIG, filepath=str(out_dir / f"{item.stem}_{rows}_{comp['id']}.csv"),
            )
            comp["schema"]["output"] = []
    return cfg


def main(argv: List[str] | None = None) -> int:
    """CLI entry point. Returns 0 when the job succeeds, 1 otherwise."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("item", type=Path, help="Talend .item job file")
    parser.add_argument("--rows", type=int, default=100_000, help="rows per main input")
    bench_root = Path(tempfile.gettempdir()) / "dataprep_bench"
    parser.add_argument("--work-dir", type=Path, default=bench_root / "inputs")
    parser.add_argument("--out-dir", type=Path, default=bench_root / "outputs")
    parser.add_argument("--profile", action="store_true", help="print the top cProfile entries")
    args = parser.parse_args(argv)

    logging.disable(logging.CRITICAL)
    cfg = build_job(args.item, args.rows, args.work_dir, args.out_dir)

    profiler = cProfile.Profile() if args.profile else None
    start = time.perf_counter()
    if profiler:
        profiler.enable()
    with ETLEngine(cfg) as engine:
        init_seconds = time.perf_counter() - start
        stats = engine.execute()
    if profiler:
        profiler.disable()
    total_seconds = time.perf_counter() - start

    print(f"job={args.item.stem} rows={args.rows} status={stats.get('status')} "
          f"init={init_seconds:.2f}s total={total_seconds:.2f}s")
    for comp_id, comp_stats in stats.get("component_stats", {}).items():
        print(f"  {comp_id:28s} {comp_stats.get('execution_time', 0):8.2f}s  "
              f"NB_LINE={comp_stats.get('NB_LINE')} OK={comp_stats.get('NB_LINE_OK')} "
              f"REJECT={comp_stats.get('NB_LINE_REJECT')} {str(comp_stats.get('error', ''))[:80]}")
    if profiler:
        buffer = io.StringIO()
        pstats.Stats(profiler, stream=buffer).sort_stats("tottime").print_stats(25)
        report = buffer.getvalue()
        print(report[report.find("ncalls"):])
    return 0 if stats.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
