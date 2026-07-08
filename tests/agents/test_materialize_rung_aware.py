"""Guardrail tests for the deterministic tier cap in materialize_expected.

The invariant: a rung-3 (LLM-authored) or provenance-missing output can NEVER be
graded -- no ``<name>_expected.csv`` answer key lands on disk as gradable. This is
enforced as a fail-closed ALLOW-LIST at the grading boundary, independent of the
orchestrator LLM. Rung-1/2 outputs materialize exactly as today; the template path
(no ``provenance`` key) is unchanged.
"""
from agents.tools.materialize_golden import materialize_expected


def test_rung3_output_not_graded_and_no_csv(tmp_path):
    extract = {"expected_output": {"result": [{"id": "1"}]},
               "output_keys": {"result": ["id"]},
               "provenance": {"result": {"rung": "3a", "handle": "image:0"}}}
    manifest = materialize_expected(extract, tmp_path)
    assert manifest["outputs"]["result"]["graded"] is False
    assert not (tmp_path / "golden" / "result_expected.csv").exists()


def test_missing_provenance_entry_on_normalizer_path_not_graded(tmp_path):
    # normalizer path (provenance key present) but NO entry for 'result' -> fail-closed, never graded
    extract = {"expected_output": {"result": [{"id": "1"}]},
               "output_keys": {"result": ["id"]},
               "provenance": {"trades": {"rung": "1", "handle": "sibling:t.csv"}}}
    manifest = materialize_expected(extract, tmp_path)
    assert manifest["outputs"]["result"]["graded"] is False
    assert not (tmp_path / "golden" / "result_expected.csv").exists()


def test_rung1_output_graded_as_today(tmp_path):
    extract = {"expected_output": {"result": [{"id": "1"}]},
               "output_keys": {"result": ["id"]},
               "provenance": {"result": {"rung": "2", "handle": "table:2"}}}
    manifest = materialize_expected(extract, tmp_path)
    assert manifest["outputs"]["result"]["graded"] is True
    assert (tmp_path / "golden" / "result_expected.csv").exists()
