"""Command line of the v2 engine.

    python -m src.v2 job.json [--context_param KEY=VALUE ...] [--check]

Exit code 0 when the job finished, 1 when it ran and failed, 2 when it was
not run at all: the job config was refused, or the command line was wrong.
A summary of the run is printed on standard output as JSON; log lines and
the refusal report go to standard error.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Dict, List, Optional

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
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        return 0 if stop.code == 0 else 2
    logging.basicConfig(level=args.log_level.upper(), stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s - %(message)s")

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

    result = run_job(job, engine=args.engine)
    print(json.dumps({
        "job_name": result.job_name,
        "status": result.status,
        "error": result.error,
        "failed_component": result.failed_component,
        "failures": result.failures,
        "rows": result.rows,
        "duration_s": round(result.duration_s, 3),
    }, indent=2))
    return 0 if result.status == "success" else 1
