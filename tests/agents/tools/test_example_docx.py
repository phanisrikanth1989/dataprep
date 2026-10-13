from pathlib import Path

from agents.tools.extract_doc import extract_doc

_DOCX = Path("agents/examples/sample_etl_requirements.docx")


def test_example_docx_present_and_old_gone():
    assert _DOCX.exists()
    assert not Path("agents/examples/sample_enrichment_requirements.docx").exists()


def test_example_docx_is_verified_tier_with_notes():
    result = extract_doc(str(_DOCX))
    assert result.conformance.ok is True
    assert result.tier == "verified"
    assert result.notes != ""  # exercises the Notes / Special Handling capture
