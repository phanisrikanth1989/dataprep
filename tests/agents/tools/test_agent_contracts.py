from pathlib import Path

_AGENTS = Path(".github/agents")


def _body(name):
    text = (_AGENTS / f"{name}.agent.md").read_text(encoding="utf-8")
    return text.split("---", 2)[2].lower()  # body only (skip frontmatter)


def test_doc_interpreter_consumes_notes_extra_sections_tier_and_tags():
    b = _body("doc-interpreter")
    assert "notes" in b and "extra_sections" in b and "tier" in b
    assert "outputs" in b               # carries the output NAMES + keys (name/keys only, NOT graded)
    assert 'source: "note"' in b or "derived_from_note" in b
