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
