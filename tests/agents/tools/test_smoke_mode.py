import json

from agents.tools.run_and_validate import RunResult, _smoke_verdict


def test_smoke_verdict_has_no_passed_field():
    import pandas as pd
    rr = RunResult(status="success", outputs={"out1": pd.DataFrame({"cc": ["US"]})})
    v = _smoke_verdict(rr)
    assert "passed" not in v
    assert v["tier"] == "smoke"
    assert v["ran_clean"] is True
    assert v["produced_outputs"] == {"out1": 1}
    assert v["dropped_or_errored_components"] == []


def test_smoke_verdict_not_clean_on_dropped():
    rr = RunResult(status="success", dropped_components=["ghost"])
    v = _smoke_verdict(rr)
    assert v["ran_clean"] is False and "ghost" in v["dropped_or_errored_components"]


def test_smoke_verdict_not_clean_on_errored_component():
    rr = RunResult(status="success", component_stats={"c": {"status": "error"}})
    v = _smoke_verdict(rr)
    assert v["ran_clean"] is False and "c" in v["dropped_or_errored_components"]


def test_smoke_verdict_not_clean_on_engine_error_status():
    # Engine status != success -> not clean even with no dropped/errored component.
    rr = RunResult(status="error")
    v = _smoke_verdict(rr)
    assert v["ran_clean"] is False
    assert v["status"] == "error" and "passed" not in v


def test_cli_smoke_runs_job_and_emits_verdict(tmp_path):
    from agents.tools.run_and_validate import main
    src = tmp_path / "source.csv"; src.write_text("cc;amt\nUS;10\n")
    out = tmp_path / "out.csv"
    job = {
        "job_name": "smoke", "flows": [{"name": "f1", "from": "in1", "to": "out1", "type": "flow"}],
        "components": [
            {"id": "in1", "type": "FileInputDelimited",
             "config": {"filepath": str(src), "fieldseparator": ";", "header_rows": 1, "die_on_error": False},
             "inputs": [], "outputs": ["f1"],
             "schema": {"input": [], "output": [{"name": "cc"}, {"name": "amt"}]},
             "subjob_id": "s1", "is_subjob_start": True},
            {"id": "out1", "type": "FileOutputDelimited",
             "config": {"filepath": str(out), "fieldseparator": ";", "include_header": True,
                        "file_exist_exception": False, "create_directory": True},
             "inputs": ["f1"], "outputs": [],
             "schema": {"input": [{"name": "cc"}, {"name": "amt"}], "output": []},
             "subjob_id": "s1", "is_subjob_start": False},
        ],
    }
    job_path = tmp_path / "job.json"; job_path.write_text(json.dumps(job))
    report = tmp_path / "smoke.json"
    rc = main(["--job", str(job_path), "--smoke", "--out", str(report)])
    assert rc == 0
    v = json.loads(report.read_text())
    assert v["tier"] == "smoke" and "passed" not in v and v["ran_clean"] is True
