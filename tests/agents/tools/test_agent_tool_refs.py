import importlib
import re
from pathlib import Path


def test_every_python_m_reference_in_agents_has_a_main():
    refs = set()
    for f in Path(".github/agents").glob("*.agent.md"):
        refs |= set(re.findall(r"python -m (agents\.tools\.\w+)", f.read_text(encoding="utf-8")))
    assert refs, "expected at least one 'python -m agents.tools.X' reference in the agents"
    missing = [m for m in sorted(refs)
               if not callable(getattr(importlib.import_module(m), "main", None))]
    assert missing == [], f"agents reference these via 'python -m' but they have no main(): {missing}"
