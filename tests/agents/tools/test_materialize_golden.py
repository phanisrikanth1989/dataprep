import csv
from pathlib import Path

from agents.tools.materialize_golden import materialize_inputs


def _read(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh, delimiter=";"))


def test_materialize_inputs_writes_named_csv_at_root(tmp_path):
    extract = {
        "sample_input": {"transactions": [{"id": "T1", "amt": "10"}, {"id": "T2", "amt": "20"}]},
        "sources_schema": {"transactions": [{"name": "id"}, {"name": "amt"}]},
    }
    written = materialize_inputs(extract, tmp_path)
    assert written == ["transactions.csv"]
    rows = _read(tmp_path / "transactions.csv")
    assert rows[0] == ["id", "amt"]
    assert rows[1] == ["T1", "10"] and rows[2] == ["T2", "20"]


def test_materialize_inputs_quotes_embedded_separator(tmp_path):
    extract = {"sample_input": {"src": [{"id": "T1", "note": "a;b"}]},
               "sources_schema": {"src": [{"name": "id"}, {"name": "note"}]}}
    materialize_inputs(extract, tmp_path)
    # RFC-4180: the ';' inside the value must be quoted, not column-shifted.
    raw = (tmp_path / "src.csv").read_text(encoding="utf-8")
    assert '"a;b"' in raw
    assert _read(tmp_path / "src.csv")[1] == ["T1", "a;b"]


import json

from agents.tools.materialize_golden import materialize_expected


def test_materialize_expected_writes_manifest_and_graded_csv(tmp_path):
    extract = {
        "expected_output": {"enriched": [{"id": "T1", "name": "A"}]},
        "output_keys": {"enriched": ["id"]},
    }
    manifest = materialize_expected(extract, tmp_path)
    assert manifest == {"outputs": {"enriched": {"keys": ["id"], "sep": ";", "graded": True}}}
    assert "component" not in json.dumps(manifest)
    gdir = tmp_path / "golden"
    assert json.loads((gdir / "manifest.json").read_text()) == manifest
    assert (gdir / "enriched_expected.csv").exists()


def test_materialize_expected_declared_empty_is_graded_false_no_csv(tmp_path):
    extract = {"expected_output": {"rejects": []}, "output_keys": {"rejects": []}}
    manifest = materialize_expected(extract, tmp_path)
    assert manifest["outputs"]["rejects"]["graded"] is False
    # Declared-empty output: no expected CSV written (nothing to diff).
    assert not (tmp_path / "golden" / "rejects_expected.csv").exists()


def test_materialize_expected_embedded_sep_round_trips(tmp_path):
    extract = {"expected_output": {"o": [{"id": "T1", "note": "x;y"}]}, "output_keys": {"o": ["id"]}}
    materialize_expected(extract, tmp_path)
    import csv
    with open(tmp_path / "golden" / "o_expected.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh, delimiter=";"))
    assert rows[1] == ["T1", "x;y"]


from agents.tools.materialize_golden import main, materialize_golden


def test_materialize_golden_end_to_end(tmp_path):
    extract = {
        "tier": "verified",
        "sample_input": {"src": [{"id": "T1"}]},
        "sources_schema": {"src": [{"name": "id"}]},
        "expected_output": {"out": [{"id": "T1"}]},
        "output_keys": {"out": ["id"]},
    }
    result = materialize_golden(extract, tmp_path)
    assert result["tier"] == "verified"
    assert result["inputs"] == ["src.csv"]
    assert result["outputs"]["out"]["graded"] is True
    assert (tmp_path / "src.csv").exists()
    assert (tmp_path / "golden" / "out_expected.csv").exists()


def test_cli_emits_tier_and_returns_zero(tmp_path):
    ed = tmp_path / "extract_doc.json"
    ed.write_text(json.dumps({
        "tier": "smoke",
        "sample_input": {"src": [{"id": "T1"}]},
        "sources_schema": {"src": [{"name": "id"}]},
        "expected_output": {}, "output_keys": {},
    }))
    out = tmp_path / "mat.json"
    rc = main(["--extract-doc", str(ed), "--work-dir", str(tmp_path), "--out", str(out)])
    assert rc == 0
    assert json.loads(out.read_text())["tier"] == "smoke"


def test_cli_bad_extract_doc_returns_two(tmp_path):
    rc = main(["--extract-doc", str(tmp_path / "nope.json"), "--work-dir", str(tmp_path)])
    assert rc == 2
