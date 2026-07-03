from agents.tools.audit_log import AuditLog


def test_record_and_read_roundtrip(tmp_path):
    log = AuditLog(str(tmp_path))
    log.record(1, "configurator", "artifact_written", {"file": "job_draft.json"})
    log.record(1, "test-runner", "oracle_verdict", {"passed": False, "reasons": ["output matched differs"]})
    rows = log.read()
    assert len(rows) == 2
    assert rows[0] == {"iteration": 1, "role": "configurator", "event": "artifact_written",
                       "detail": {"file": "job_draft.json"}}
    assert rows[1]["detail"]["passed"] is False


def test_read_missing_is_empty(tmp_path):
    assert AuditLog(str(tmp_path / "nope")).read() == []


def test_read_skips_malformed_partial_line(tmp_path):
    log = AuditLog(str(tmp_path))
    log.record(1, "configurator", "artifact_written", {"file": "x"})
    # simulate an interrupted process leaving a partial trailing line
    with (tmp_path / "audit.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"iteration": 2, "role": "test-ru')
    rows = log.read()          # must NOT raise
    assert len(rows) == 1 and rows[0]["role"] == "configurator"


def test_cli_appends_entry(tmp_path):
    from agents.tools.audit_log import main, AuditLog
    rc = main(["--job-dir", str(tmp_path), "--iteration", "1", "--role", "configurator",
               "--event", "artifact_written", "--detail", '{"file": "job.json"}'])
    assert rc == 0
    rows = AuditLog(str(tmp_path)).read()
    assert len(rows) == 1 and rows[0]["role"] == "configurator" and rows[0]["detail"]["file"] == "job.json"
