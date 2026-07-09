# tests/demo_budget_ui/test_fetcher.py
import urllib.request, pathlib
from demo.budget_ui.server.app import app  # noqa
from demo.budget_ui.daemon.fetcher import fetch_once
# reuse the _server helper pattern from test_sender (import it)
from tests.demo_budget_ui.test_sender import _server, store

def test_fetch_once_downloads_the_uploaded_doc(tmp_path):
    with _server() as base:
        import io
        urllib.request.urlopen  # ensure import
        # upload via urllib multipart is awkward; use the store directly to enqueue
        job = store.create_job("brd.docx", b"HELLO")
        got = fetch_once(base, str(tmp_path))
    assert got == job
    assert (tmp_path / "brd.docx").read_bytes() == b"HELLO"
