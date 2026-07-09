# tests/demo_budget_ui/test_daemon_synthetic.py
import shutil, time, pathlib
from demo.budget_ui.daemon.daemon import Daemon
FIX = pathlib.Path(__file__).parent / "fixtures" / "trade_position_demo"

def test_synthetic_mode_emits_finale_sample(tmp_path):
    work = tmp_path / "j"; work.mkdir()
    cap = []
    d = Daemon("j", str(work), send=cap.append, since=time.time() - 1, synthetic=True)
    shutil.copy(FIX / "extract_doc.json", work / "extract_doc.json"); d.poll()
    shutil.copy(FIX / "test_report.json", work / "test_report.json"); d.poll()
    res = next(e for e in cap if e["type"] == "result")
    assert "sample" in res and len(res["sample"]) >= 1     # finale table has rows in synthetic mode

def test_default_mode_has_no_sample(tmp_path):
    work = tmp_path / "j2"; work.mkdir()
    cap = []
    d = Daemon("j2", str(work), send=cap.append, since=time.time() - 1)   # synthetic defaults False
    shutil.copy(FIX / "extract_doc.json", work / "extract_doc.json"); d.poll()
    shutil.copy(FIX / "test_report.json", work / "test_report.json"); d.poll()
    res = next(e for e in cap if e["type"] == "result")
    assert "sample" not in res                              # fail-closed

def test_mark_seen_after_send_retries_on_failure(tmp_path):
    work = tmp_path / "j3"; work.mkdir()
    calls = {"n": 0}
    def flaky(ev):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("server down")
    d = Daemon("j3", str(work), send=flaky, since=time.time() - 1)
    shutil.copy(FIX / "extract_doc.json", work / "extract_doc.json")
    d.poll()                     # first send raises -> artifact NOT marked seen
    ok = []
    d.send = ok.append
    d.poll()                     # retried on the next poll
    assert any(e["type"] == "sources" for e in ok)

def test_test_report_marked_seen_no_double_emit(tmp_path):
    # regression: test_report.json must be marked seen too, or run() re-emits result/end every poll
    work = tmp_path / "j4"; work.mkdir()
    cap = []
    d = Daemon("j4", str(work), send=cap.append, since=time.time() - 1)
    shutil.copy(FIX / "test_report.json", work / "test_report.json")
    d.poll()
    d.poll()                     # unchanged file -> must NOT re-emit
    assert sum(1 for e in cap if e["type"] == "result") == 1
