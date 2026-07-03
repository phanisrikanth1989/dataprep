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
    assert any("match" in e for e in validate_skill(text, "dataprep-recon"))
