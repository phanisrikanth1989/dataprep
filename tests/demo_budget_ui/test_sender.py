# tests/demo_budget_ui/test_sender.py
import threading, time, urllib.request, json, socket, contextlib
import uvicorn
from demo.budget_ui.server.app import app, store
from demo.budget_ui.daemon.sender import HttpSender

def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

@contextlib.contextmanager
def _server():
    store.__init__()
    port = _free_port()
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    srv = uvicorn.Server(cfg)
    t = threading.Thread(target=srv.run, daemon=True); t.start()
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/job/next", timeout=0.2); break
        except Exception:
            time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.should_exit = True; t.join(timeout=2)

def test_http_sender_posts_events():
    with _server() as base:
        send = HttpSender(base, "job-x")
        send({"type": "sources", "seq": 1, "nodes": []})
        send({"type": "end", "passed": True, "seq": 2})
        # verify via the stream replay
        req = urllib.request.urlopen(f"{base}/stream/job-x", timeout=2)
        data = req.read().decode()
    assert '"type": "sources"' in data and '"type": "end"' in data
