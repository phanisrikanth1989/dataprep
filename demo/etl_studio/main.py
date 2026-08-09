"""ETL Studio agent core entrypoint.

The one place adapters and core meet (ticket 07 seam law): this module wires
a provider adapter into the SkeletonApp and runs the stdio JSON-RPC loop.
Spawned by the extension shim with the panel; exits 0 on SIGTERM/EOF
(deliberate shutdown) and nonzero on crashes, which is what the shim's
restart policy keys on.

Run standalone for smoke testing:
    python main.py --provider double --work-dir work/_smoke
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

from core.app import SkeletonApp
from core.journal import UiJournal
from core.rpc import stdio_connection
from adapters.double.adapter import DoubleAdapter
from adapters.vscode_lm.adapter import VscodeLmAdapter

logger = logging.getLogger("main")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ETL Studio agent core (skeleton)")
    parser.add_argument(
        "--provider",
        choices=["auto", "vscode_lm", "double"],
        default="auto",
        help="Provider adapter: auto = vscode.lm with announced fallback to the double",
    )
    parser.add_argument(
        "--work-dir",
        default=str(BASE_DIR / "work" / "_skeleton"),
        help="Run work dir holding ui_journal.jsonl",
    )
    return parser.parse_args(argv)


async def amain(args: argparse.Namespace) -> None:
    conn = await stdio_connection()
    journal = UiJournal(Path(args.work_dir) / "ui_journal.jsonl")

    double = DoubleAdapter()
    if args.provider == "double":
        primary, primary_name, fallback = double, "double", None
    else:
        primary, primary_name = VscodeLmAdapter(conn), "vscode_lm"
        fallback = double if args.provider == "auto" else None

    SkeletonApp(conn, journal, primary, primary_name, fallback)

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    run_task = asyncio.create_task(conn.run())
    stop_task = asyncio.create_task(stop.wait())
    logger.info(
        "core up: provider=%s work_dir=%s python=%s",
        args.provider,
        args.work_dir,
        sys.version.split()[0],
    )
    await asyncio.wait({run_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
    run_task.cancel()
    stop_task.cancel()
    journal.close()
    logger.info("core exiting")


def main() -> None:
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="[core] %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(amain(parse_args()))


if __name__ == "__main__":
    main()
