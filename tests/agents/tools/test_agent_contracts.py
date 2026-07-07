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


def test_configurator_states_csv_option_and_filepath_contract():
    b = _body("configurator")
    assert "csv_option" in b and "text_enclosure" in b
    assert "<source-name>.csv" in b or "source-name>.csv" in b
    assert "quote_none" in b or "shift" in b or "round-trip" in b  # the WHY of csv_option


def test_assembler_states_id_equals_output_name():
    b = _body("assembler")
    assert "id" in b and "output name" in b
    assert "harness" in b or "run_and_validate" in b or "maps on" in b
    # F1: the assembler must READ the outputs list (names) from requirement_spec.json to bind ids.
    assert "requirement_spec.json" in b and "outputs" in b


def test_orchestrator_has_step0_tier_branching_and_note_guard():
    b = _body("etl-orchestrator")
    assert "materialize_golden" in b
    assert "verified" in b and "smoke" in b and "build" in b
    assert "--smoke" in b
    assert "extract_doc" in b
    assert "notes" in b and "extra_sections" in b
    assert "note" in b and ("repair" in b or "silently" in b)  # note-vs-oracle guard
