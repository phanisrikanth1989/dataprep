from agents.tools.validate_agents import validate_agent, validate_skill, parse_frontmatter

_GOOD_AGENT = """---
name: configurator
description: Fills component config for a recon job.
tools: ['edit/files', 'search/codebase']
user-invocable: false
---
You configure components.
"""

_MODEL_PINNED = """---
name: bad
description: has a model pin
model: Claude Opus 4.7
---
body
"""


def test_parse_frontmatter_ok():
    assert parse_frontmatter(_GOOD_AGENT)["name"] == "configurator"


def test_good_agent_has_no_errors():
    assert validate_agent(_GOOD_AGENT, "configurator.agent.md") == []


def test_model_key_is_flagged():
    errs = validate_agent(_MODEL_PINNED, "bad.agent.md")
    assert any("model" in e for e in errs)


def test_missing_description_flagged():
    text = "---\nname: x\n---\nbody\n"
    assert any("description" in e for e in validate_agent(text, "x.agent.md"))


def test_skill_name_must_match_dir():
    text = "---\nname: other-name\ndescription: d\n---\nbody\n"
    assert any("match" in e for e in validate_skill(text, "dataprep-etl"))


def test_malformed_yaml_is_reported_not_crashed():
    text = "---\ntools: [edit/files, search\nname: x\n---\nbody\n"   # unclosed bracket
    errs = validate_agent(text, "x.agent.md")                        # must NOT raise
    assert errs and any("x.agent.md" in e for e in errs)


def _write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8")


def test_validate_tree_clean_and_flags_unknown_ref(tmp_path):
    from agents.tools.validate_agents import validate_tree
    ad = tmp_path / "agents"; sd = tmp_path / "skills"
    _write(ad / "configurator.agent.md", "---\nname: configurator\ndescription: d\nuser-invocable: false\n---\nb\n")
    _write(ad / "orch.agent.md", "---\nname: orch\ndescription: d\nagents: ['configurator']\n---\nb\n")
    _write(sd / "dataprep-etl" / "SKILL.md", "---\nname: dataprep-etl\ndescription: d\n---\nb\n")
    assert validate_tree(ad, sd) == []
    # now point the orchestrator at a ghost
    _write(ad / "orch.agent.md", "---\nname: orch\ndescription: d\nagents: ['ghost']\n---\nb\n")
    assert any("ghost" in e for e in validate_tree(ad, sd))


def test_validate_tree_missing_dir_flagged(tmp_path):
    from agents.tools.validate_agents import validate_tree
    assert any("not found" in e for e in validate_tree(tmp_path / "nope", tmp_path / "s"))


def test_validate_tree_tolerates_malformed_file(tmp_path):
    from agents.tools.validate_agents import validate_tree
    ad = tmp_path / "agents"; sd = tmp_path / "skills"; sd.mkdir(parents=True)
    _write(ad / "bad.agent.md", "---\ntools: [oops\n---\nb\n")     # malformed yaml
    errs = validate_tree(ad, sd)                                   # must NOT raise
    assert any("bad.agent.md" in e for e in errs)
