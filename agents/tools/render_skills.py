"""Render the plan-2 curated knowledge into the workspace-global dataprep-recon Agent Skill.

enum_ref pointers are resolved to concrete value lists so an agent reading the
skill sees the real allowed values, not a Python import path.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from agents.knowledge.landmines import LANDMINES
from agents.tools.component_schema import _SCHEMA_DIR, _index, resolve_enum_ref

logger = logging.getLogger(__name__)


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
            bits.append("one of " + ", ".join(json.dumps(v) for v in vals))
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
    return "\n".join(out) + "\n"


_JOB_ENVELOPE_EXAMPLE_JSON = """{
  "components": [
    {"id": "in_source", "type": "FileInputDelimited", "subjob_id": "sj1",
     "schema": {"input": [], "output": [{"name": "cc", "type": "str"}]},
     "config": {"filepath": "source.csv", "fieldseparator": ";", "header_rows": 1},
     "inputs": [], "outputs": ["source_flow"]},
    {"id": "in_lookup", "type": "FileInputDelimited", "subjob_id": "sj1",
     "schema": {"input": [], "output": [{"name": "cc", "type": "str"}, {"name": "country_name", "type": "str"}]},
     "config": {"filepath": "countries.csv", "fieldseparator": ";", "header_rows": 1},
     "inputs": [], "outputs": ["lookup_flow"]},
    {"id": "join1", "type": "Map", "subjob_id": "sj1",
     "schema": {"input": [{"name": "cc", "type": "str"}], "output": [{"name": "cc", "type": "str"}, {"name": "country_name", "type": "str"}]},
     "config": {
       "inputs": {
         "main": {"name": "source_flow", "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
         "lookups": [{"name": "lookup_flow", "join_mode": "LEFT_OUTER_JOIN",
                      "join_keys": [{"lookup_column": "cc", "expression": "source_flow.cc", "operator": "="}]}]
       },
       "outputs": [{"name": "enriched_flow", "is_reject": false, "columns": [
         {"name": "cc", "expression": "source_flow.cc", "type": "str"},
         {"name": "country_name", "expression": "lookup_flow.country_name", "type": "str"}]}]
     },
     "inputs": ["source_flow", "lookup_flow"], "outputs": ["enriched_flow"]},
    {"id": "out_enriched", "type": "FileOutputDelimited", "subjob_id": "sj1",
     "schema": {"input": [{"name": "cc", "type": "str"}, {"name": "country_name", "type": "str"}], "output": []},
     "config": {"filepath": "enriched.csv", "fieldseparator": ";", "include_header": true, "file_exist_exception": false},
     "inputs": ["enriched_flow"], "outputs": []}
  ],
  "flows": [
    {"name": "source_flow", "type": "flow", "from": "in_source", "to": "join1"},
    {"name": "lookup_flow", "type": "flow", "from": "in_lookup", "to": "join1"},
    {"name": "enriched_flow", "type": "flow", "from": "join1", "to": "out_enriched"}
  ]
}
"""


def render_job_envelope() -> str:
    """The engine-verified job.json envelope contract (from plan-3 Task 4)."""
    prose = (
        "# Job envelope contract (engine-verified)\n\n"
        "Every component needs a `subjob_id`. Component `schema` is "
        "`{\"input\": [...], \"output\": [...]}` (NOT a flat list). Flows are "
        "`{\"name\": <flow>, \"type\": \"flow\", \"from\": <id>, \"to\": <id>}` and each "
        "component carries `inputs`/`outputs` lists referencing flow names. `type:\"main\"` "
        "on a flow routes NOTHING; use `\"flow\"`. The default enrichment join is a "
        "`LEFT_OUTER_JOIN` that KEEPS ALL source rows -- an unmatched source row still flows "
        "out, with null lookup columns. `inner_join_reject: true` on an output is AVAILABLE if a "
        "job must route unmatched source rows to a reject output (`is_reject` stays empty for a "
        "join miss), but that is NOT the enrichment default.\n"
    )
    example = (
        "\nMinimal connected enrichment example (source + lookup -> LEFT-join tMap -> output; "
        "every flow `from`/`to` is a real component id, and every component's `inputs`/`outputs` "
        "names a real flow):\n\n"
        "```json\n"
        + _JOB_ENVELOPE_EXAMPLE_JSON
        + "```\n"
    )
    return prose + example


_SKILL_FRONTMATTER = (
    "---\n"
    "name: dataprep-recon\n"
    "description: >-\n"
    "  Code-verified knowledge for building the recon team's DataPrep ENRICHMENT ETL jobs: per-component\n"
    "  config keys and allowed values, config landmines, the job.json envelope contract, and the tMap\n"
    "  lookup-join enrichment pattern. Use when interpreting an enrichment requirement, designing the\n"
    "  flow, configuring components, or assembling/repairing a job.json.\n"
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
        "recon = the recon TEAM; this tool does data ENRICHMENT/prep, not the reconciliation "
        "(SmartStream TLM reconciles).\n\n"
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
