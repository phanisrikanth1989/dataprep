"""Command line of the v2 engine.

    python -m src.v2 job.json [--context_param KEY=VALUE ...] [--check] [--row-counts]

Exit code 0 when the job finished, 1 when it ran and failed, 2 when it was
not run at all: the job config was refused, or the command line was wrong.

Log lines at INFO and DEBUG go to standard output; warnings and errors go
to standard error, and so do the refusal report and what is wrong with the
command line. An empty standard error means a clean run. A summary of the
run is the last thing written to standard output, as JSON; ``--summary``
writes it to a file as well.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from contextlib import contextmanager
from typing import Dict, Iterator, List, Optional

from .engine import load_job, run_job
from .errors import JobRefusedError, V2Error


def main(argv: Optional[List[str]] = None) -> int:
    """Run the command line. Returns the process exit code."""
    parser = argparse.ArgumentParser(prog="python -m src.v2", description="Run a job config on the v2 engine.")
    parser.add_argument("job_config", help="Path of the job config JSON file.")
    parser.add_argument("--context_param", action="append", default=[], metavar="KEY=VALUE",
                        help="Set a context variable. May be given several times.")
    parser.add_argument("--check", action="store_true", help="Load and check the job config; run nothing.")
    parser.add_argument("--engine", choices=("streaming", "in-memory", "auto"),
                        help="The Polars engine to run with (default: streaming).")
    parser.add_argument("--log-level", default="INFO", type=str.upper,
                        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
                        help="Logging level (default: INFO).")
    parser.add_argument("--summary", metavar="FILE",
                        help="Also write the summary of the run to this file, as JSON.")
    parser.add_argument("--row-counts", action="store_true",
                        help="Count the rows of every component and log them. For looking into a job: "
                             "the run takes about three times as long.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        return 0 if stop.code == 0 else 2
    with _log_streams(args.log_level):
        return _run(args)


@contextmanager
def _log_streams(level: str) -> Iterator[None]:
    """Send log lines to the two standard streams for as long as the command runs.

    INFO and DEBUG lines go to standard output, warnings and errors to
    standard error. Logging is left as it was found.
    """
    layout = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
    quiet = logging.StreamHandler(sys.stdout)
    quiet.addFilter(lambda record: record.levelno < logging.WARNING)
    loud = logging.StreamHandler(sys.stderr)
    loud.setLevel(logging.WARNING)
    root = logging.getLogger()
    before = root.level
    for handler in (quiet, loud):
        handler.setFormatter(layout)
        root.addHandler(handler)
    root.setLevel(level)
    try:
        yield
    finally:
        root.setLevel(before)
        for handler in (quiet, loud):
            root.removeHandler(handler)


def _run(args: argparse.Namespace) -> int:
    """Load the job the command line names and run it. Returns the process exit code."""
    context: Dict[str, str] = {}
    for item in args.context_param:
        key, separator, value = item.partition("=")
        if not separator or not key.strip():
            print(f"--context_param {item!r}: expected KEY=VALUE", file=sys.stderr)
            return 2
        context[key.strip()] = value.strip()

    try:
        job = load_job(args.job_config, context=context)
    except JobRefusedError as refused:
        print(refused.report.format(), file=sys.stderr)
        return 2
    except (OSError, ValueError, V2Error) as exc:
        print(f"{args.job_config}: {exc}", file=sys.stderr)
        return 2
    if args.check:
        print(f"Job '{job.name}': nothing refused.")
        return 0

    # Opened before the job runs: a job is not run only to find that its summary has nowhere to go.
    summary_file = None
    if args.summary:
        try:
            summary_file = open(args.summary, "w", encoding="utf-8")
        except OSError as exc:
            print(f"--summary {args.summary}: {exc}", file=sys.stderr)
            return 2

    result = run_job(job, engine=args.engine, row_counts=args.row_counts)
    summary = json.dumps({
        "job_name": result.job_name,
        "status": result.status,
        "error": result.error,
        "failed_component": result.failed_component,
        "failures": result.failures,
        "rows": result.rows,
        "counts": result.counts,
        "duration_s": round(result.duration_s, 3),
    }, indent=2)
    if summary_file is not None:
        with summary_file:
            summary_file.write(summary + "\n")
    print(summary)
    return 0 if result.status == "success" else 1
