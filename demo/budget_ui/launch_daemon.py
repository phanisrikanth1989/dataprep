"""Laptop launcher: watch agents/work/<job>/ and POST its data-free events to the relay.

Run this on the laptop with the SAME <job> name you give the Copilot etl-orchestrator.
It wires the Phase-1 daemon to the Phase-2 relay (HttpSender), starting from now so it
ignores any pre-existing artifacts (guardrail 16.2) and only relays this run.

Usage:
    python -m demo.budget_ui.launch_daemon --server http://HOST:PORT --job <job> [--synthetic]

Then, in Copilot, trigger the etl-orchestrator on your BRD with job name <job>. Open the
browser at the server root and enter <job> (or navigate to /?job=<job>) to watch it build.
ASCII-only.
"""
from __future__ import annotations

import argparse
import os
import time

from demo.budget_ui.daemon.daemon import Daemon
from demo.budget_ui.daemon.sender import HttpSender


def main(argv=None):
    p = argparse.ArgumentParser(description="Relay a Copilot ETL run to the demo UI server.")
    p.add_argument("--server", required=True, help="relay base URL, e.g. http://host:8088")
    p.add_argument("--job", required=True, help="job/work-dir slug (== the Copilot job name)")
    p.add_argument("--work-root", default="agents/work", help="parent of the <job> work dir")
    p.add_argument("--synthetic", action="store_true",
                   help="synthetic-demo mode: include the finale output-table sample (answer-key rows)")
    p.add_argument("--interval", type=float, default=0.5, help="poll interval seconds")
    a = p.parse_args(argv)

    work = os.path.join(a.work_root, a.job)
    os.makedirs(work, exist_ok=True)
    daemon = Daemon(a.job, work, send=HttpSender(a.server, a.job),
                    since=time.time(), synthetic=a.synthetic)
    print("[launch] watching %s -> %s  (job=%s, synthetic=%s)" % (work, a.server, a.job, a.synthetic))
    print("[launch] now trigger the Copilot etl-orchestrator with job name: %s" % a.job)
    print("[launch] open the browser at %s/?job=%s" % (a.server.rstrip("/"), a.job))
    try:
        daemon.run(interval=a.interval)
    except KeyboardInterrupt:
        print("\n[launch] stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
