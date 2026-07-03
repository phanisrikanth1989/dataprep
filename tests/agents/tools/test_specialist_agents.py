from pathlib import Path

from agents.tools.validate_agents import validate_agent, parse_frontmatter

_AGENTS = Path(".github/agents")
_SPECIALISTS = ["doc-interpreter", "flow-designer", "configurator", "assembler",
                "test-runner", "diagnostician"]


def test_all_specialists_exist_and_valid():
    for name in _SPECIALISTS:
        f = _AGENTS / f"{name}.agent.md"
        assert f.exists(), f"missing {f}"
        text = f.read_text(encoding="utf-8")
        assert validate_agent(text, f.name) == []
        fm = parse_frontmatter(text)
        assert fm["name"] == name
        assert fm.get("user-invocable") is False          # subagent-only
        assert "model" not in fm                            # model-agnostic
