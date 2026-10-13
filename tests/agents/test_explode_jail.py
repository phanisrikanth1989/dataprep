"""Guardrail tests for the exploder's jailed extraction (zip-slip/zip-bomb + sibling read-jail)."""
import pytest

from agents.tools.explode_doc import _safe_basename, _resolve_sibling


def test_zip_slip_and_absolute_reduced_to_basename():
    assert _safe_basename("word/media/../../evil.png") == "evil.png"
    assert _safe_basename("/abs/evil.png") == "evil.png"       # absolute -> basename, does NOT raise


def test_unsafe_basename_raises():
    with pytest.raises(ValueError):
        _safe_basename("..")                                    # reduces to ".." -> _safe_name raises


def test_sibling_read_rejects_escape(tmp_path):
    with pytest.raises(ValueError):
        _resolve_sibling(str(tmp_path), "../secret.csv")        # read-jail: escape rejected
