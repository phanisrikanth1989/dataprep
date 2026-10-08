from pathlib import Path


def test_platform_doc_has_citi_checklist_and_run_commands():
    text = Path("agents/PLATFORM.md").read_text(encoding="utf-8")
    low = text.lower()
    assert "citi" in low and "checklist" in low
    assert "runsubagent" in low
    assert "run_and_validate" in text          # names the deterministic harness command
    assert "terminal" in low and "autoapprove" in low.replace(" ", "")


def test_platform_doc_names_materialize_and_tiers():
    text = Path("agents/PLATFORM.md").read_text(encoding="utf-8")
    assert "materialize_golden" in text
    low = text.lower()
    assert "verified" in low and "smoke" in low and "build" in low
    assert "extract_doc" in text
