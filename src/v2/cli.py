"""Command line of the v2 engine.

    python -m src.v2 job.json [--context_param KEY=VALUE ...] [--check] [--row-counts] [--summary FILE]

Exit code 0 when the job finished, 1 when it ran and failed, 2 when it was
not run at all: the job config was refused, or the command line was wrong.

Log lines at INFO and DEBUG go to standard output; warnings and errors go
to standard error, and so do the refusal report and what is wrong with the
command line. An empty standard error means a clean run: a job that finished
but dropped rows for a fault has a warning there. A summary of the
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

from .engine import Runner, load_job, settled
from .engine.picking import only_from_text
from .errors import JobRefusedError, V2Error
from .job.loader import caller_settings
from .job.refusal import RefusalReport


def main(argv: Optional[List[str]] = None) -> int:
    """Run the command line. Returns the process exit code."""
    parser = argparse.ArgumentParser(prog="python -m src.v2", description="Run a job config on the v2 engine.")
    parser.add_argument("job_config", help="Path of the job config JSON file.")
    parser.add_argument("--context_param", action="append", default=[], metavar="KEY=VALUE",
                        help="Set a context variable. May be given several times.")
    parser.add_argument("--check", action="store_true", help="Load and check the job config; run nothing.")
    parser.add_argument("--engine", choices=("streaming", "in-memory", "auto"),
                        help="The Polars engine to run with (default: streaming).")
    parser.add_argument("--log-level", default=None, type=str.upper,
                        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
                        help="Logging level (default: the job config's run.log_level, or INFO).")
    parser.add_argument("--summary", metavar="FILE",
                        help="Also write the summary of the run to this file, as JSON.")
    parser.add_argument("--row-counts", action=argparse.BooleanOptionalAction, default=None,
                        help="Count the rows of every component and log them. For looking into a job: "
                             "the run takes about three times as long.")
    parser.add_argument("--only", metavar="ROWS",
                        help="Run the job for a few rows of one reader and no others: READER:COLUMN=VALUE[,VALUE] "
                             "by what a column holds, READER:line=NUMBER[,NUMBER] by the place a failure names "
                             "(record= or row= for readers that have those), or a `run.only` block in JSON.")
    parser.add_argument("--trace", action=argparse.BooleanOptionalAction, default=None,
                        help="With --only: put what every component did with the picked rows in the summary.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        return 0 if stop.code == 0 else 2
    # What the command line says wins over the job config's `run` block; the block is known once the job is loaded.
    with _log_streams(args.log_level or "INFO"):
        return _run(args)


def _writable(text: str, stream: object) -> str:
    """A text as a stream can write it: what its encoding cannot hold becomes an escape.

    Standard error does that by itself. Standard output does not: there
    such a character raises.
    """
    encoding = getattr(stream, "encoding", None) or "utf-8"
    return text.encode(encoding, "backslashreplace").decode(encoding)


class _Lenient(logging.StreamHandler):
    """A handler that loses no line to its stream's encoding.

    Without it a line standard output cannot write is dropped, and logging
    reports that on standard error.
    """

    def format(self, record: logging.LogRecord) -> str:
        return _writable(super().format(record), self.stream)


@contextmanager
def _log_streams(level: str) -> Iterator[None]:
    """Send log lines to the two standard streams for as long as the command runs.

    INFO and DEBUG lines go to standard output, warnings and errors to
    standard error. Logging is left as it was found.
    """
    layout = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
    quiet = _Lenient(sys.stdout)
    quiet.addFilter(lambda record: record.levelno < logging.WARNING)
    loud = _Lenient(sys.stderr)
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
    said: Dict[str, object] = {"log_level": args.log_level, "row_counts": args.row_counts,
                               "summary_file": args.summary, "trace": args.trace}
    if args.only is not None:
        try:
            said["only"] = only_from_text(args.only, job)
        except ValueError as exc:
            print(f"--only {args.only!r}: {exc}", file=sys.stderr)
            return 2
    asked, refusals = caller_settings({name: value for name, value in said.items() if value is not None})
    if refusals:
        report = RefusalReport(job_name=job.name)
        report.extend(refusals)
        print(report.format(), file=sys.stderr)
        return 2
    try:
        settings, asked_for = settled(job, asked)
    except JobRefusedError as refused:
        print(refused.report.format(), file=sys.stderr)
        return 2
    if args.check:
        print(_writable(f"Job '{job.name}': nothing refused.", sys.stdout))
        return 0
    if settings.log_level:
        logging.getLogger().setLevel(settings.log_level)

    # Opened before the job runs: a job is not run only to find that its summary has nowhere to go.
    # The file is empty while the job runs, so an earlier run's summary is never taken for this one's.
    summary_file, named_by = None, "--summary" if args.summary else "run.summary_file"
    if settings.summary_file:
        try:
            summary_file = open(settings.summary_file, "w", encoding="utf-8")
        except OSError as exc:
            print(f"{named_by} {settings.summary_file}: {exc}", file=sys.stderr)
            return 2

    result = Runner(job, engine=args.engine, settings=settings, asked_for=asked_for, asked_by="command line").run()
    summary = json.dumps(result.summary(), indent=2)
    print(summary)
    if summary_file is not None:
        try:
            with summary_file:
                summary_file.write(summary + "\n")
        except OSError as exc:
            # The job has run, and how it ended stands: this is said, and is not made a failure of the job.
            print(f"{named_by} {settings.summary_file}: {exc}", file=sys.stderr)
    return 0 if result.status == "success" else 1
