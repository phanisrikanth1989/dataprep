from pathlib import Path

from agents.tools.validate_agents import parse_frontmatter, validate_tree

_AGENTS = Path(".github/agents")
_SKILLS = Path(".github/skills")


def test_orchestrator_valid_and_references_all_specialists():
    text = (_AGENTS / "etl-orchestrator.agent.md").read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    assert fm["name"] == "etl-orchestrator"
    assert fm.get("user-invocable") is True
    assert "model" not in fm
    allow = fm["agents"]
    for name in ["doc-interpreter", "flow-designer", "configurator", "assembler",
                 "test-runner", "diagnostician"]:
        assert name in allow
    # human gate + harness-decides must be stated in the body
    low = text.lower()
    assert "human" in low and "approv" in low
    assert "run_and_validate" in text or "test-runner" in low


def test_orchestrator_has_single_step_testing_mode():
    """A first-class single-step / testing mode (for AGENT_STEPWISE_TESTING_GUIDE.md):
    the orchestrator halts after one stage and waits for 'proceed', keeping the safety nets."""
    low = (_AGENTS / "etl-orchestrator.agent.md").read_text(encoding="utf-8").lower()
    assert "single-step" in low and "testing mode" in low
    # halts after one stage and waits for the human's go-ahead
    assert "one stage" in low and "proceed" in low
    # does not auto-repair in testing mode, and keeps the safety nets in force
    assert "auto-repair" in low and "safety net" in low


def test_whole_tree_validates():
    assert validate_tree(_AGENTS, _SKILLS) == []
