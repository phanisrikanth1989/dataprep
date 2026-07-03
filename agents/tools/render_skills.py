"""Render the plan-2 curated knowledge into the workspace-global dataprep-recon Agent Skill.

enum_ref pointers are resolved to concrete value lists so an agent reading the
skill sees the real allowed values, not a Python import path.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from agents.knowledge.landmines import LANDMINES
from agents.tools.component_schema import _SCHEMA_DIR, load_schema, resolve_enum_ref

logger = logging.getLogger(__name__)


def _index() -> dict:
    with (_SCHEMA_DIR / "_index.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def _resolved_values(spec: dict):
    if "enum" in spec:
        return [v for v in spec["enum"]]
    if "enum_ref" in spec:
        return sorted(resolve_enum_ref(spec["enum_ref"]), key=str)
    return None


def _render_keys(keys: dict, indent: str = "") -> list:
    lines = []
    for name, spec in keys.items():
        bits = [f"type={spec.get('type', 'any')}"]
        if "default" in spec:
            bits.append(f"default={spec['default']!r}")
        if spec.get("required"):
            bits.append("REQUIRED")
        vals = _resolved_values(spec)
        if vals is not None:
            bits.append("one of " + ", ".join(str(v) for v in vals))
        lines.append(f"{indent}- `{name}`: {'; '.join(bits)}")
        if spec.get("type") == "list" and isinstance(spec.get("item_keys"), dict):
            lines.append(f"{indent}  items:")
            lines.extend(_render_keys(spec["item_keys"], indent + "    "))
    return lines


def render_config_reference() -> str:
    """Markdown reference of every curated component's config keys (enum_refs resolved)."""
    files = sorted(set(_index().values()))
    out = ["# Component config reference (code-verified)", ""]
    for filename in files:
        schema = json.loads((_SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        out.append(f"## {schema['type']}")
        aliases = schema.get("aliases", [])
        if aliases:
            out.append(f"Aliases: {', '.join(aliases)}")
        out.extend(_render_keys(schema.get("keys", {})))
        out.append("")
    return "\n".join(out)


def render_landmines() -> str:
    """Markdown list of the code-verified config landmines."""
    out = ["# Config landmines (respect these)", ""]
    for lm in LANDMINES:
        comp = lm.get("component") or "GLOBAL"
        out.append(f"- **{lm['id']}** ({comp}): {lm['summary']}")
        out.append(f"  - guidance: {lm['guidance']}")
    return "\n".join(out)


def render_job_envelope() -> str:
    """The engine-verified job.json envelope contract (from plan-3 Task 4)."""
    return (
        "# Job envelope contract (engine-verified)\n\n"
        "Every component needs a `subjob_id`. Component `schema` is "
        "`{\"input\": [...], \"output\": [...]}` (NOT a flat list). Flows are "
        "`{\"name\": <flow>, \"type\": \"flow\", \"from\": <id>, \"to\": <id>}` and each "
        "component carries `inputs`/`outputs` lists referencing flow names. `type:\"main\"` "
        "on a flow routes NOTHING; use `\"flow\"`. tMap one-sided breaks use an output with "
        "`inner_join_reject: true` (NOT `is_reject`, which stays empty for a join miss).\n"
    )


_SKILL_FRONTMATTER = (
    "---\n"
    "name: dataprep-recon\n"
    "description: >-\n"
    "  Code-verified knowledge for building DataPrep recon ETL jobs: per-component config keys and\n"
    "  allowed values, config landmines, the job.json envelope contract, and the tMap match/break\n"
    "  patterns. Use when interpreting a recon requirement, designing the flow, configuring components,\n"
    "  or assembling/repairing a recon job.json.\n"
    "---\n"
)


def write_skill(root: str = ".github/skills/dataprep-recon") -> None:
    """Write SKILL.md + the three resource files for the dataprep-recon skill."""
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    (root_path / "config-reference.md").write_text(render_config_reference(), encoding="utf-8")
    (root_path / "landmines.md").write_text(render_landmines(), encoding="utf-8")
    (root_path / "job-envelope.md").write_text(render_job_envelope(), encoding="utf-8")
    body = (
        _SKILL_FRONTMATTER
        + "# DataPrep recon knowledge\n\n"
        "Load the resource that fits the task:\n\n"
        "- `config-reference.md` - every allowed component config key + its resolved allowed values.\n"
        "- `landmines.md` - config traps that silently produce wrong output; respect each.\n"
        "- `job-envelope.md` - the exact job.json wiring shape the engine requires.\n\n"
        "Validate any component config with `python -m agents.tools.validate_config --type T --config c.json` "
        "and test a whole job with `python -m agents.tools.run_and_validate --job job.json --golden-dir DIR` "
        "before claiming it is correct.\n"
    )
    (root_path / "SKILL.md").write_text(body, encoding="utf-8")
    logger.info("[render_skills] wrote dataprep-recon skill to %s", root)


if __name__ == "__main__":
    write_skill()
