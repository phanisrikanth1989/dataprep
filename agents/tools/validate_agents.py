"""Validate authored .agent.md / SKILL.md frontmatter against the v1.122 schema.

Structural + model-agnostic gate; it does NOT verify that a tool id resolves in
a live VS Code install (that is a Citi-side check, see PLATFORM.md).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")


def parse_frontmatter(text: str) -> dict:
    """Return the leading ----delimited YAML frontmatter as a dict."""
    if not text.startswith("---"):
        raise ValueError("no frontmatter block")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("unterminated frontmatter block")
    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data


def _common(fm: dict, errors: list) -> None:
    if not fm.get("name"):
        errors.append("missing 'name'")
    if not fm.get("description"):
        errors.append("missing 'description'")


def validate_agent(text: str, filename: str) -> list:
    """Return frontmatter errors for a .agent.md (empty = valid)."""
    errors: list = []
    try:
        fm = parse_frontmatter(text)
    except ValueError as exc:
        return [f"{filename}: {exc}"]
    _common(fm, errors)
    if "model" in fm:
        errors.append("'model' key is forbidden (model-agnostic: omit it)")
    for key in ("tools", "agents"):
        if key in fm and not isinstance(fm[key], list):
            errors.append(f"'{key}' must be a list")
    for key in ("user-invocable", "disable-model-invocation"):
        if key in fm and not isinstance(fm[key], bool):
            errors.append(f"'{key}' must be a boolean")
    return [f"{filename}: {e}" for e in errors]


def validate_skill(text: str, dirname: str) -> list:
    """Return frontmatter errors for a SKILL.md (empty = valid)."""
    errors: list = []
    try:
        fm = parse_frontmatter(text)
    except ValueError as exc:
        return [f"{dirname}/SKILL.md: {exc}"]
    _common(fm, errors)
    name = fm.get("name", "")
    if name and name != dirname:
        errors.append(f"name {name!r} must match dir {dirname!r}")
    if name and not _NAME_RE.match(name):
        errors.append(f"name {name!r} must be lowercase-alphanumeric-hyphen, <=64 chars")
    if len(str(fm.get("description", ""))) > 1024:
        errors.append("description exceeds 1024 chars")
    return [f"{dirname}/SKILL.md: {e}" for e in errors]


def validate_tree(agents_dir, skills_dir) -> list:
    """Validate all agents + skills and cross-check orchestrator `agents:` references."""
    errors: list = []
    agents_dir, skills_dir = Path(agents_dir), Path(skills_dir)
    names = set()
    allowlists = []
    for af in sorted(agents_dir.glob("*.agent.md")):
        text = af.read_text(encoding="utf-8")
        errors.extend(validate_agent(text, af.name))
        try:
            fm = parse_frontmatter(text)
            if fm.get("name"):
                names.add(fm["name"])
            if isinstance(fm.get("agents"), list):
                allowlists.append((af.name, fm["agents"]))
        except ValueError:
            pass
    for sd in sorted(p for p in skills_dir.glob("*") if p.is_dir()):
        sf = sd / "SKILL.md"
        if sf.exists():
            errors.extend(validate_skill(sf.read_text(encoding="utf-8"), sd.name))
    for fname, allow in allowlists:
        for ref in allow:
            if ref != "*" and ref not in names:
                errors.append(f"{fname}: agents: references unknown agent {ref!r}")
    return errors
