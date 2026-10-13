# demo/budget_ui/daemon/sender.py
"""Laptop-outbound HTTP sender: POST one data-free event to the relay. stdlib only."""
from __future__ import annotations

import json
import urllib.request


class HttpSender:
    def __init__(self, base_url, job_id):
        self._url = base_url.rstrip("/") + "/job/" + job_id + "/event"

    def __call__(self, event):
        body = json.dumps(event).encode("utf-8")
        req = urllib.request.Request(self._url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:  # raises on non-2xx
            resp.read()
