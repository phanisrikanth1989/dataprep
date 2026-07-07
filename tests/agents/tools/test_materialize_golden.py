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
