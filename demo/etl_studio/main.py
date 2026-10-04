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
from core.demo_fixtures import build_scripts
from core.knowledge import render_at_startup
from core.models import ModelConfig
from core.rpc import stdio_connection
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
    parser.add_argument(
        "--config",
        default=str(BASE_DIR / "studio_config.json"),
        help="Studio config (per-stage model selectors); absent = adapter defaults",
    )
    return parser.parse_args(argv)


async def amain(args: argparse.Namespace) -> None:
    conn = await stdio_connection()
    pace = PACES[args.pace]

    # Ticket 11: the knowledge render happens at EVERY core startup from the
    # vendored sources (the enum-ref drift check rides it -- fail loud).
    render_dir = render_at_startup()
    logger.info("knowledge rendered to %s", render_dir)

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
        model_config=ModelConfig.load(Path(args.config)),
    )
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    # The read loop must serve BEFORE restore: a crash-restored run resolves
    # its live provider over lm/* (ticket 17), which needs responses flowing.
    # Restore still journals run.crash_restored before resume; an attach that
    # races in replays the journal and picks the rest up live (the reducer is
    # seq-idempotent either way).
    run_task = asyncio.create_task(conn.run())
    await app.restore_at_boot()
    # Ticket 17's live-probe rig: a pending autorun.json self-starts a run
    # and answers its questions by the kind policy (dev affordance only).
    await app.maybe_autorun()

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
