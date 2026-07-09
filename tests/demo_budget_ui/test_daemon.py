# tests/demo_budget_ui/test_daemon.py
import json, shutil, pathlib, time
from demo.budget_ui.daemon.daemon import Daemon
FIX = pathlib.Path(__file__).parent / "fixtures" / "trade_position_demo"

def test_daemon_emits_ordered_data_free_events(tmp_path):
    work = tmp_path / "job1"; (work / "golden").mkdir(parents=True)
    captured = []
    d = Daemon("job1", str(work), send=captured.append, since=time.time())
    # 1) drop extract_doc -> expect a 'sources' event, envelope-wrapped
    shutil.copy(FIX / "extract_doc.json", work / "extract_doc.json")
    d.poll()
    types = [e["type"] for e in captured]
    assert "sources" in types
    src = next(e for e in captured if e["type"] == "sources")
    assert src["job"] == "job1" and isinstance(src["seq"], int) and "t" in src
    # 2) drop job.json -> expect edges + gate, and 'wiring' stage
    shutil.copy(FIX / "job.json", work / "job.json")
    d.poll()
    types = [e["type"] for e in captured]
    assert "edges" in types and "gate" in types
    assert any(e["type"] == "stage" and e["stage"] == "wiring" for e in captured)
    # data-free across the whole stream
    from tests.demo_budget_ui.test_presenter import _forbidden_values, P
    for e in captured:
        P.assert_data_free(e, _forbidden_values())

def test_daemon_ignores_preexisting_artifacts_before_since(tmp_path):
    work = tmp_path / "job2"; work.mkdir()
    shutil.copy(FIX / "extract_doc.json", work / "extract_doc.json")
    time.sleep(0.01)
    d = Daemon("job2", str(work), send=(cap := []).append, since=time.time())  # since AFTER the file
    d.poll()
    assert cap == []   # pre-existing artifact older than `since` is not replayed

def test_daemon_dedups_unchanged_files(tmp_path):
    work = tmp_path / "job3"; work.mkdir()
    d = Daemon("job3", str(work), send=(cap := []).append, since=time.time() - 1)
    shutil.copy(FIX / "extract_doc.json", work / "extract_doc.json")
    d.poll(); n = len(cap); d.poll()   # second poll, no change
    assert len(cap) == n               # no re-emit
