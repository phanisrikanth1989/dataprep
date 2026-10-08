"""Render the plan-2 curated knowledge into the workspace-global dataprep-etl Agent Skill.

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
     "config": {"filepath": "source.csv", "fieldseparator": ";", "header_rows": 1, "csv_option": true, "text_enclosure": "\\""},
     "inputs": [], "outputs": ["source_flow"]},
    {"id": "in_lookup", "type": "FileInputDelimited", "subjob_id": "sj1",
     "schema": {"input": [], "output": [{"name": "cc", "type": "str"}, {"name": "country_name", "type": "str"}]},
     "config": {"filepath": "countries.csv", "fieldseparator": ";", "header_rows": 1, "csv_option": true, "text_enclosure": "\\""},
     "inputs": [], "outputs": ["lookup_flow"]},
    {"id": "join1", "type": "Map", "subjob_id": "sj1",
     "schema": {"input": [{"name": "cc", "type": "str"}], "output": [{"name": "cc", "type": "str"}, {"name": "country_name", "type": "str"}]},
     "config": {
       "inputs": {
         "main": {"name": "source_flow"},
         "lookups": [{"name": "lookup_flow", "join_mode": "LEFT_OUTER_JOIN",
                      "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE",
                      "join_keys": [{"lookup_column": "cc", "expression": "{{java}}source_flow.cc", "operator": "="}]}]
       },
       "outputs": [{"name": "enriched_flow", "is_reject": false, "columns": [
         {"name": "cc", "expression": "{{java}}source_flow.cc", "type": "str"},
         {"name": "country_name", "expression": "{{java}}lookup_flow.country_name", "type": "str"}]}]
     },
     "inputs": ["source_flow", "lookup_flow"], "outputs": ["enriched_flow"]},
    {"id": "enriched", "type": "FileOutputDelimited", "subjob_id": "sj1",
     "schema": {"input": [{"name": "cc", "type": "str"}, {"name": "country_name", "type": "str"}], "output": []},
     "config": {"filepath": "enriched.csv", "fieldseparator": ";", "include_header": true, "file_exist_exception": false, "csv_option": true, "text_enclosure": "\\""},
     "inputs": ["enriched_flow"], "outputs": []}
  ],
  "flows": [
    {"name": "source_flow", "type": "flow", "from": "in_source", "to": "join1"},
    {"name": "lookup_flow", "type": "flow", "from": "in_lookup", "to": "join1"},
    {"name": "enriched_flow", "type": "flow", "from": "join1", "to": "enriched"}
  ],
  "java_config": {"enabled": true, "routines": [
    "routines.TalendDate", "routines.TalendString", "routines.StringHandling",
    "routines.Mathematical", "routines.Relational", "routines.Numeric",
    "routines.DataOperation"], "libraries": []}
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
        "on a flow routes NOTHING; use `\"flow\"`. A common lookup-enrich join is a "
        "`LEFT_OUTER_JOIN` that KEEPS ALL source rows -- an unmatched source row still flows "
        "out, with null lookup columns. `inner_join_reject: true` on an output is AVAILABLE if a "
        "job must route unmatched source rows to a reject output (`is_reject` stays empty for a "
        "join miss), but that is NOT the left-join default.\n\n"
        "A terminal FileOutputDelimited's `id` MUST equal the output name it writes (the harness maps on "
        "this), and every delimited FileInput/FileOutput that reads/writes a materialized CSV MUST set "
        "`csv_option: true` (with `text_enclosure: \"\\\"\"`) so a value containing the `;` separator "
        "round-trips instead of shifting columns.\n\n"
        "Any job containing a `Map`/`tMap` component REQUIRES a top-level "
        "`\"java_config\": {\"enabled\": true, ...}` block: the tMap engine always compiles a Java "
        "script and crashes without the bridge. tMap expressions carry a `{{java}}` marker (as below).\n"
    )
    example = (
        "\nMinimal connected lookup-enrich example (source + lookup -> LEFT-join tMap -> output; "
        "every flow `from`/`to` is a real component id, and every component's `inputs`/`outputs` "
        "names a real flow):\n\n"
        "```json\n"
        + _JOB_ENVELOPE_EXAMPLE_JSON
        + "```\n"
    )
    return prose + example


def render_patterns() -> str:
    """The canonical flow-design patterns the flow-designer picks from (the skill's frontmatter
    promises these). Kept in the skill so a stage never has to RAG-search the engine source for a
    known shape -- e.g. the SchemaComplianceCheck validate->reject flow."""
    return (
        "# Flow patterns (pick the shape, then configure)\n\n"
        "Common data-preparation shapes. The flow-designer picks the shape; the configurator fills\n"
        "the config. These cover the curated node set -- you do NOT need to read engine source for them.\n\n"
        "## Lookup-enrich (add columns from a reference file)\n"
        "`source + lookup -> [tJoin | PyMap | tMap] -> ... -> FileOutputDelimited`.\n"
        "- `tJoin`: one equality-key lookup, keeps the first lookup row per key -- the default choice.\n"
        "- `PyMap` / `tMap`: several lookups, a join variable, or an expression-derived output column.\n"
        "- `LEFT_OUTER_JOIN` keeps every source row (an unmatched row flows out with null lookup\n"
        "  columns); `INNER_JOIN` drops misses. Keep the lookup key unique (`UNIQUE_MATCH` /\n"
        "  `FIRST_MATCH`, or pre-dedup with `UniqueRow` / `AggregateRow`) so one source row maps to one.\n\n"
        "## Validate a type/format, route failures to a reject (SchemaComplianceCheck)\n"
        "`SchemaComplianceCheck` validates each row against the declared column types/formats --\n"
        "INCLUDING a date format via a per-column `date_pattern` (e.g. `yyyy-MM-dd`) -- and routes rows\n"
        "that FAIL to a separate REJECT output flow while passing rows continue on the main flow:\n\n"
        "```\n"
        "... -> SchemaComplianceCheck --main----> (rest of the pipeline)\n"
        "                             --reject--> FileOutputDelimited (the rejected rows), if kept\n"
        "```\n\n"
        "Use it for a `schema_validate` rule that must ACT on bad rows (drop or route them). For a\n"
        "plain type conformance with no reject action, a `ConvertType` cast -- or BaseComponent's own\n"
        "output-schema coercion -- is enough; no extra node.\n\n"
        "## Derive / cast in one vectorized pass (python_dataframe)\n"
        "Place ONE `tPythonDataFrame` AFTER the join to collapse casts + derivations into a single\n"
        "pass. It is single-input (cannot join) and unsandboxed (human-reviewed); pin\n"
        "`execution_mode: \"batch\"` on it.\n\n"
        "## Aggregate before sort\n"
        "`AggregateRow` (pandas groupby) discards row order, so put `SortRow` LAST to fix the\n"
        "downstream-facing output order (the oracle diff is order-insensitive, so a wrong final order\n"
        "would otherwise ship undetected).\n"
    )


_SKILL_FRONTMATTER = (
    "---\n"
    "name: dataprep-etl\n"
    "description: >-\n"
    "  Code-verified knowledge for building DataPrep ETL jobs on the Python engine: per-component\n"
    "  config keys and allowed values, config landmines, the job.json envelope contract, and the\n"
    "  join/lookup and transform patterns. Use when interpreting an ETL requirement, designing the\n"
    "  flow, configuring components, or assembling/repairing a job.json.\n"
    "---\n"
)


def write_skill(root: str = ".github/skills/dataprep-etl") -> None:
    """Write SKILL.md + the four resource files for the dataprep-etl skill."""
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    (root_path / "config-reference.md").write_text(render_config_reference(), encoding="utf-8")
    (root_path / "landmines.md").write_text(render_landmines(), encoding="utf-8")
    (root_path / "job-envelope.md").write_text(render_job_envelope(), encoding="utf-8")
    (root_path / "patterns.md").write_text(render_patterns(), encoding="utf-8")
    body = (
        _SKILL_FRONTMATTER
        + "# DataPrep ETL knowledge\n\n"
        "Code-verified knowledge for building DataPrep ETL jobs (sources -> transformations -> outputs) "
        "on the Python engine that replaces Talend.\n\n"
        "Load the resource that fits the task:\n\n"
        "- `config-reference.md` - every allowed component config key + its resolved allowed values.\n"
        "- `landmines.md` - config traps that silently produce wrong output; respect each.\n"
        "- `job-envelope.md` - the exact job.json wiring shape the engine requires.\n"
        "- `patterns.md` - canonical flow shapes (lookup-enrich, validate->reject, derive, aggregate/sort).\n\n"
        "Validate any component config with `python -m agents.tools.validate_config --type T --config c.json` "
        "and test a whole job with `python -m agents.tools.run_and_validate --job job.json --golden-dir DIR` "
        "before claiming it is correct.\n"
    )
    (root_path / "SKILL.md").write_text(body, encoding="utf-8")
    logger.info("[render_skills] wrote dataprep-etl skill to %s", root)


if __name__ == "__main__":
    write_skill()
