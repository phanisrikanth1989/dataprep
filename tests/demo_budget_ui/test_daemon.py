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

def test_daemon_multi_artifact_poll_emits_in_pipeline_order(tmp_path):
    # job_draft is written BEFORE job, but 'job.json' sorts alphabetically BEFORE
    # 'job_draft.json' -- the daemon must emit in mtime (pipeline) order, not filename order.
    work = tmp_path / "job4"; work.mkdir()
    d = Daemon("job4", str(work), send=(cap := []).append, since=time.time() - 1)
    shutil.copy(FIX / "job_draft.json", work / "job_draft.json")
    time.sleep(0.02)
    shutil.copy(FIX / "job.json", work / "job.json")
    d.poll()   # ONE poll sees both new files
    types = [e["type"] for e in cap]
    assert types.index("node_config") < types.index("edges")   # configuring before wiring
    stages = [e["stage"] for e in cap if e["type"] == "stage"]
    assert stages.index("configuring") < stages.index("wiring")

def test_full_run_replay_is_ordered_and_data_free(tmp_path):
    work = tmp_path / "job"; (work / "golden").mkdir(parents=True)
    cap = []
    d = Daemon("job", str(work), send=cap.append, since=time.time() - 1)
    order = ["extract_doc.json", "requirement_spec.json", "flow_plan.json",
             "job_draft.json", "job.json", "test_report_passed.json"]
    for name in order:
        target = "test_report.json" if name == "test_report_passed.json" else name
        shutil.copy(FIX / name, work / target)
        time.sleep(0.01)
        d.poll()
    types = [e["type"] for e in cap]
    # every expected type appeared, sources before edges before result
    for t in ("sources", "rules", "nodes", "node_config", "edges", "gate", "callout", "result"):
        assert t in types, t
    assert types.index("sources") < types.index("edges") < types.index("result")
    assert cap[-1] == {"job": "job", "seq": cap[-1]["seq"], "t": cap[-1]["t"], "type": "end", "passed": True}
    # gate signed, signoff+testing stages, and node/result contract fields are present
    assert any(e["type"] == "gate" and e.get("status") == "signed" for e in cap)
    stage_names = {e["stage"] for e in cap if e["type"] == "stage"}
    assert {"signoff", "testing"} <= stage_names
    ncfg = next(e for e in cap if e["type"] == "node_config")
    assert all("kind" in n for n in ncfg["nodes"])                 # node_config carries kind
    assert any(n.get("source") == "trades" for n in ncfg["nodes"]) # source crosswalk present
    res = next(e for e in cap if e["type"] == "result")
    assert res["outputs"] == ["trade_positions"]                   # finale glow target named
    # callouts appear exactly once per node (no duplicate emit)
    callout_nodes = [e["node"] for e in cap if e["type"] == "callout"]
    assert len(callout_nodes) == len(set(callout_nodes))
    # node_config resolves the lookup name from job.json flows -> "Match accounts", not "Match lookup"
    ncfg = next(e for e in cap if e["type"] == "node_config")
    ncfg_ids = {n["id"] for n in ncfg["nodes"]}
    assert "Match accounts" in {n["label"] for n in ncfg["nodes"]}
    # the authoritative graph is id-consistent: every edge endpoint has a node_config entry
    edge_ids = {x for e in cap if e["type"] == "edges" for f in e["edges"] for x in (f["from"], f["to"])}
    assert edge_ids <= ncfg_ids                 # no edge to a phantom node
    assert "trade_positions" in ncfg_ids        # assembler's FINAL output id (not flow_plan's out_trade_positions)
    from tests.demo_budget_ui.test_presenter import _forbidden_values, P
    for e in cap:
        P.assert_data_free(e, _forbidden_values())
    # seq is strictly monotonic
    seqs = [e["seq"] for e in cap]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)

def test_daemon_lights_reading_early_and_stages_anticipate(tmp_path):
    # purity.json is the FIRST artifact (written in seconds) -> "reading" lights immediately,
    # so the screen is not blank for the ~90s doc read before extract_doc lands.
    work = tmp_path / "jobp"; work.mkdir()
    d = Daemon("jobp", str(work), send=(cap := []).append, since=time.time() - 1)
    (work / "purity.json").write_text("{}")
    d.poll()
    assert any(e["type"] == "stage" and e["stage"] == "reading" and e["status"] == "active" for e in cap)
    # ANTICIPATORY: flow_plan (the designer's OUTPUT) lights CONFIGURING active -- the
    # configurator is already running by the time its input artifact appears, so the UI is not
    # one step behind (showing "designing" while Copilot configures).
    cap.clear()
    shutil.copy(FIX / "flow_plan.json", work / "flow_plan.json")
    time.sleep(0.02)
    d.poll()
    assert any(e["type"] == "stage" and e["stage"] == "configuring" and e["status"] == "active" for e in cap)

def test_daemon_recovers_from_torn_read(tmp_path):
    work = tmp_path / "jobt"; work.mkdir()
    d = Daemon("jobt", str(work), send=(cap := []).append, since=time.time() - 1)
    p = work / "extract_doc.json"
    p.write_text("{ not valid json")            # torn / half-written
    d.poll()
    assert cap == []                            # skipped, no crash, nothing emitted, not marked seen
    shutil.copy(FIX / "extract_doc.json", p)    # write completes -> mtime bumps
    time.sleep(0.02)
    d.poll()
    assert any(e["type"] == "sources" for e in cap)  # re-read on the next pass
