from pathlib import Path


def test_etl_template_exists_and_recon_template_gone():
    assert Path("agents/templates/etl_requirements_template.md").exists()
    assert not Path("agents/templates/recon_requirements_template.md").exists()


def test_etl_template_documents_required_optional_blocks_and_tiers():
    text = Path("agents/templates/etl_requirements_template.md").read_text(encoding="utf-8")
    low = text.lower()
    assert "inputs and schema" in low and "transformation rules" in low
    assert "notes / special handling" in low  # the new optional block
    assert "required" in low and "optional" in low
    assert "verified" in low and "smoke" in low and "build" in low
