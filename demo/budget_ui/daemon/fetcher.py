# demo/budget_ui/daemon/fetcher.py
"""Laptop-outbound fetcher: pull the next queued BRD from the relay to the input dir. stdlib only."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path


def fetch_once(base_url, out_dir):
    base = base_url.rstrip("/")
    with urllib.request.urlopen(base + "/job/next", timeout=5) as resp:
        info = json.loads(resp.read())
    job = info.get("job")
    if not job:
        return None
    with urllib.request.urlopen(base + "/job/" + job + "/doc", timeout=30) as resp:
        data = resp.read()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / Path(info["filename"]).name).write_bytes(data)   # basename only -- no path traversal
    return job
