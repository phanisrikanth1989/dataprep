"""ETL Studio agent core entrypoint.

The one place adapters and core meet (ticket 07 seam law): this module wires
provider adapters into the StudioApp and runs the stdio JSON-RPC loop.
Spawned by the extension shim with the panel; exits 0 on SIGTERM/EOF
(deliberate shutdown) and nonzero on crashes, which is what the shim's
restart policy keys on.

Run standalone for smoke testing:
    python main.py --provider double --work-dir work/_smoke --pace fast
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

from core.app import StudioApp
from core.rpc import stdio_connection
from core.scripted_run import build_scripts
from adapters.double.adapter import DoubleAdapter
from adapters.vscode_lm.adapter import VscodeLmAdapter

logger = logging.getLogger("main")

# Demo pace types at a watchable cadence; fast keeps the smoke suite quick.
PACES = {
    "demo": {"chunk_delay": 0.032, "scale": 1.0},
    "fast": {"chunk_delay": 0.003, "scale": 0.08},
}


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ETL Studio agent core")
    parser.add_argument(
        "--provider",
        choices=["auto", "vscode_lm", "double"],
        default="auto",
        help="Provider adapter for live calls: auto = vscode.lm with announced fallback",
    )
    parser.add_argument(
        "--work-dir",
        default=str(BASE_DIR / "work" / "_skeleton"),
        help="Work dir holding per-run journals (ui_journal.jsonl)",
    )
    parser.add_argument(
        "--pace",
        choices=sorted(PACES),
        default="demo",
        help="Stream cadence: demo = watchable, fast = smoke-suite speed",
    )
    return parser.parse_args(argv)


async def amain(args: argparse.Namespace) -> None:
    conn = await stdio_connection()
    pace = PACES[args.pace]

    # One double instance serves both roles: scripted demo runs (keyed
    # fixtures) and the skeleton echo fallback (legacy synthesized echo).
    double = DoubleAdapter(scripts=build_scripts(), chunk_delay=pace["chunk_delay"])
    if args.provider == "double":
        primary, primary_name, fallback = double, "double", None
    else:
        primary, primary_name = VscodeLmAdapter(conn), "vscode_lm"
        fallback = double if args.provider == "auto" else None

    app = StudioApp(
        conn,
        Path(args.work_dir),
        primary,
        primary_name,
        fallback,
        scripted_port=double,
        pace=pace["scale"],
    )
    # Crash-restore before serving: an un-ended run continues from its
    # journal (run.crash_restored lands ahead of any attach replay).
    await app.restore_at_boot()

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    run_task = asyncio.create_task(conn.run())
    stop_task = asyncio.create_task(stop.wait())
    logger.info(
        "core up: provider=%s work_dir=%s pace=%s python=%s",
        args.provider,
        args.work_dir,
        args.pace,
        sys.version.split()[0],
    )
    await asyncio.wait({run_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
    run_task.cancel()
    stop_task.cancel()
    app.close()
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
