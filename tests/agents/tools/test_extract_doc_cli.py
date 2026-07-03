# tests/agents/tools/test_extract_doc_cli.py
import json
from dataclasses import dataclass, field

import agents.tools.extract_doc as ed


def _fake_result(ok=True):
    return ed.ExtractResult(
        sources_schema={"ledger": [ed.ColumnSpec("txn_id", "string", False, True)]},
        rules=[{"id": "R1", "kind": "match", "description": "join on txn_id"}],
        sample_input={"ledger": [{"txn_id": "1"}]},
        expected_output={"matched": [{"txn_id": "1"}]},
        output_keys={"matched": ["txn_id"]},
        derived_facts={"ledger": {"txn_id": {"unique": True}}},
        conformance=ed.ConformanceReport(ok=ok),
    )


def test_to_dict_roundtrips_all_fields():
    d = ed.to_dict(_fake_result())
    assert d["sources_schema"]["ledger"][0]["name"] == "txn_id"
    assert d["rules"][0]["id"] == "R1"
    assert d["output_keys"]["matched"] == ["txn_id"]
    assert d["conformance"]["ok"] is True
    json.dumps(d)  # must be JSON-serializable


def test_cli_writes_json_and_exit_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(ed, "extract_doc", lambda path, raise_on_error=True: _fake_result(ok=True))
    out = tmp_path / "r.json"
    rc = ed.main(["ignored.docx", "--out", str(out)])
    assert rc == 0
    payload = json.loads(out.read_text())
    assert payload["rules"][0]["kind"] == "match"


def test_cli_conformance_error_exit_two(tmp_path, monkeypatch):
    def _raise(path, raise_on_error=True):
        raise ed.ConformanceError(ed.ConformanceReport(ok=False, missing_blocks=["Sample Input"]))
    monkeypatch.setattr(ed, "extract_doc", _raise)
    out = tmp_path / "r.json"
    rc = ed.main(["bad.docx", "--out", str(out)])
    assert rc == 2
    assert json.loads(out.read_text())["conformance"]["missing_blocks"] == ["Sample Input"]
