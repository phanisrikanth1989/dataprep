#!/usr/bin/env python3
"""Per-module line-coverage floor enforcement (Phase 14).

Reads a coverage.json file produced by ``pytest-cov --cov-report=json`` (or
equivalently ``coverage json``) and exits non-zero if ANY in-scope module's
line coverage falls below the floor (default 95.0%).

Usage:
    python scripts/check_per_module_coverage.py coverage.json
    python scripts/check_per_module_coverage.py coverage.json --floor 95

Output:
    PASS case (stdout, exit 0):
        PASS: all <N> in-scope modules at >= 95.0% line coverage

    FAIL case (stderr, exit 1):
        FAIL: <K> module(s) below 95.0% line coverage:
          69.0%  src/v1/engine/components/transform/join.py  (missing 45 lines)
          77.0%  src/v1/engine/components/transform/map.py  (missing 198 lines)
          ...

The script is intentionally stdlib-only and ASCII-only (project rule).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple


def _load_coverage_json(path: Path) -> dict:
    """Load and minimally validate a coverage.json file.

    Args:
        path: Path to the JSON file produced by pytest-cov / coverage.

    Returns:
        Parsed JSON object.

    Raises:
        SystemExit: If the file does not exist, is not valid JSON, or lacks
            the required ``files`` top-level key.
    """
    if not path.is_file():
        print(f"ERROR: coverage report not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"ERROR: coverage report is not valid JSON: {exc}", file=sys.stderr)
        raise SystemExit(2)
    if "files" not in data or not isinstance(data["files"], dict):
        print(
            "ERROR: coverage report missing 'files' object "
            "(expected pytest-cov / coverage JSON shape)",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return data


def _collect_failures(
    files: dict, floor: float
) -> Tuple[List[Tuple[float, str, int]], int]:
    """Collect modules whose line coverage is below the floor.

    Args:
        files: ``coverage.json["files"]`` mapping path -> file-record.
        floor: Coverage percentage threshold (e.g. 95.0).

    Returns:
        Tuple of (failures, total_modules) where failures is a list of
        ``(percent_covered, path, missing_lines)`` sorted ascending by
        percent_covered.
    """
    failures: List[Tuple[float, str, int]] = []
    total = 0
    for path, record in files.items():
        summary = record.get("summary") or {}
        if "percent_covered" not in summary:
            # Unexpected shape -- treat as a fatal data error rather than
            # silently passing.
            print(
                f"ERROR: file record missing summary.percent_covered: {path}",
                file=sys.stderr,
            )
            raise SystemExit(2)
        total += 1
        pct = float(summary["percent_covered"])
        if pct < floor:
            missing = int(summary.get("missing_lines", 0))
            failures.append((pct, path, missing))
    failures.sort(key=lambda row: (row[0], row[1]))
    return failures, total


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Enforce per-module line-coverage floor against a coverage.json "
            "report (Phase 14)."
        )
    )
    parser.add_argument(
        "report",
        type=Path,
        help="Path to coverage.json (produced by pytest-cov --cov-report=json).",
    )
    parser.add_argument(
        "--floor",
        type=float,
        default=95.0,
        help="Per-module line-coverage floor in percent (default: 95.0).",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    data = _load_coverage_json(args.report)
    failures, total = _collect_failures(data["files"], args.floor)

    if failures:
        print(
            f"FAIL: {len(failures)} module(s) below {args.floor:.1f}% line coverage:",
            file=sys.stderr,
        )
        for pct, path, missing in failures:
            print(
                f"  {pct:5.1f}%  {path}  (missing {missing} lines)",
                file=sys.stderr,
            )
        return 1

    print(
        f"PASS: all {total} in-scope modules at >= {args.floor:.1f}% line coverage"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
