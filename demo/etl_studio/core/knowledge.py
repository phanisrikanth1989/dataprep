"""Engine knowledge for the owned runtime (ticket 11, built by ticket 17).

Inline-primary hybrid: every LLM stage's knowledge slice is assembled
in-prompt by this module's slice renderers -- deterministic, provably carried
on every call. The vendored sources (knowledge/schemas/*.json + _index.json,
core/vendored/landmines.py, the authored prose below, knowledge/
config-surfaces.md) are rendered at EVERY core startup into a gitignored
render dir (``work/_knowledge/``) -- inspectable per run, never tracked,
never hand-edited: a wrong rendered artifact indicts its source.

Slice legality (ticket 11): a slice is the WHOLE artifact, a FIELD PROJECTION,
or a COMPONENT-FILTERED subset keyed on source metadata -- never an editorial
hand-pick. The SKILL index is retired; its routing job is the slice map here.

Freshness dissolves by construction: nothing rendered is tracked, so there is
no stale artifact. The enum-ref drift check rides along -- rendering the
config reference resolves every enum_ref against the live (read-only) engine,
so a drifted ref fails the render loudly at startup.

Fit-pass items landed here (ticket 11): code anchors restored in the landmine
rendering; component-filter and field-projection render functions; the
orchestrator's and diagnostician's matrix rows rendered for tickets 18/19.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .vendored.component_schema import _SCHEMA_DIR, _index, resolve_enum_ref
from .vendored.landmines import LANDMINES

logger = logging.getLogger(__name__)

STUDIO_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_SRC = STUDIO_ROOT / "knowledge"
RENDER_DIR = STUDIO_ROOT / "work" / "_knowledge"

_MAP_ALIASES = {"Map", "tMap"}


# ---------------------------------------------------------------------------
# Component-filter helpers (mechanical filters, never editorial picks)
# ---------------------------------------------------------------------------


def _canonical_files(types: Optional[Iterable[str]] = None) -> List[str]:
    """Schema files for the given component types/aliases (None = the whole
    curated catalog). Unknown (uncurated) types filter to nothing -- the
    engine + oracle gate those."""
    index = _index()
    if types is None:
        return sorted(set(index.values()))
    files = {index[t] for t in types if t in index}
    return sorted(files)


def canonical_type(name: str) -> str:
    """Canonical component type for any catalog name or Talend alias
    (ticket 20: one vocabulary on the canvas and in job.json -- the
    schema's own ``type`` field). Uncurated/unknown names pass through
    unchanged; the engine + oracle gate those."""
    index = _index()
    filename = index.get(str(name))
    if not filename:
        return str(name)
    schema = json.loads((_SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    return str(schema.get("type") or name)


def _canonical_types(types: Iterable[str]) -> set:
    """Expand component types/aliases to every name that shares their curated
    schema (tJoin -> {tJoin, Join}, ...) so landmine keying by canonical name
    matches whatever alias the flow used. Mechanical: keyed on _index.json."""
    index = _index()
    by_file: Dict[str, set] = {}
    for name, filename in index.items():
        by_file.setdefault(filename, set()).add(name)
    out = set(types)
    for t in list(out):
        filename = index.get(t)
        if filename:
            out |= by_file[filename]
    return out


def _landmines_filtered(types: Optional[Iterable[str]] = None) -> List[dict]:
    """Landmines for the given component types (global entries always kept);
    None = the full registry. Mirrors the source's ``landmines_for`` keying,
    alias-expanded through the schema index."""
    if types is None:
        return list(LANDMINES)
    wanted = _canonical_types(types)
    out = []
    for lm in LANDMINES:
        comp = lm.get("component")
        if comp is None:
            out.append(lm)
        elif comp in wanted or (comp in _MAP_ALIASES and wanted & _MAP_ALIASES):
            out.append(lm)
    return out


# ---------------------------------------------------------------------------
# Renderers (vendored from agents/tools/render_skills.py, ticket 17; the
# authored prose ports word-for-word, the landmine renderer regains anchors)
# ---------------------------------------------------------------------------


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


def render_config_reference(types: Optional[Iterable[str]] = None) -> str:
    """Markdown reference of curated components' config keys (enum_refs
    resolved live). ``types`` component-filters; None renders the catalog."""
    out = ["# Component config reference (code-verified)", ""]
    for filename in _canonical_files(types):
        schema = json.loads((_SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        out.append(f"## {schema['type']}")
        aliases = schema.get("aliases", [])
        if aliases:
            out.append(f"Aliases (accepted on input, never author these): {', '.join(aliases)}")
        out.extend(_render_keys(schema.get("keys", {})))
        out.append("")
    return "\n".join(out)


def render_landmines(types: Optional[Iterable[str]] = None, anchors: bool = False) -> str:
    """Markdown list of the code-verified config landmines. ``types``
    component-filters; ``anchors`` includes the code anchors (the ticket-11
    fit-pass restore -- the diagnostician's slice carries them as live
    pointers into the read-only engine source)."""
    out = ["# Config landmines (respect these)", ""]
    for lm in _landmines_filtered(types):
        comp = lm.get("component") or "GLOBAL"
        out.append(f"- **{lm['id']}** ({comp}): {lm['summary']}")
        if anchors and lm.get("code_anchor"):
            out.append(f"  - code anchor: {lm['code_anchor']}")
        out.append(f"  - guidance: {lm['guidance']}")
    return "\n".join(out) + "\n"


def render_landmine_summaries() -> str:
    """Field projection (id + component + summary, no guidance) -- the
    orchestrator's matrix row (ticket 18 consumes)."""
    out = ["# Landmine summaries (id + component + summary)", ""]
    for lm in LANDMINES:
        comp = lm.get("component") or "GLOBAL"
        out.append(f"- {lm['id']} ({comp}): {lm['summary']}")
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


def render_job_envelope(worked_example: bool = True) -> str:
    """The engine-verified job.json envelope contract; ``worked_example``
    appends the minimal connected example (the assembler's slice keeps it,
    the configurator's schema-section slice drops it)."""
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
        "A terminal FileOutputDelimited's configured `filepath` MUST be `<output-name>.csv` for the "
        "spec output it delivers (the harness finds and grades outputs by the FILE they write, never by "
        "component id), and every delimited FileInput/FileOutput that reads/writes a materialized CSV "
        "MUST set `csv_option: true` (with `text_enclosure: \"\\\"\"`) so a value containing the `;` "
        "separator round-trips instead of shifting columns.\n\n"
        "Any job containing a `Map`/`tMap` component REQUIRES a top-level "
        "`\"java_config\": {\"enabled\": true, ...}` block: the tMap engine always compiles a Java "
        "script and crashes without the bridge. tMap expressions carry a `{{java}}` marker (as below). "
        "A job with NO Map/tMap and no `{{java}}` expression must carry "
        "`\"java_config\": {\"enabled\": false}` instead -- enabling the JVM a job never uses "
        "hard-fails on hosts without the bridge JAR. (The example below enables it because it IS a "
        "tMap job.)\n"
    )
    if not worked_example:
        return prose
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
    """The canonical flow-design patterns the flow-designer picks from. Kept
    inline so a stage never has to search the engine source for a known shape."""
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


# ---------------------------------------------------------------------------
# Startup render (ticket 11: at EVERY core startup, into a gitignored dir)
# ---------------------------------------------------------------------------


def render_at_startup(render_dir: Optional[Path] = None) -> Path:
    """Render every knowledge artifact from the vendored sources. Raises on a
    drifted enum_ref (the drift check rides the render -- fail loud, fix the
    source). Returns the render dir."""
    out = Path(render_dir) if render_dir else RENDER_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / "config-reference.md").write_text(render_config_reference(), encoding="utf-8")
    (out / "landmines.md").write_text(render_landmines(anchors=True), encoding="utf-8")
    (out / "landmine-summaries.md").write_text(render_landmine_summaries(), encoding="utf-8")
    (out / "job-envelope.md").write_text(render_job_envelope(), encoding="utf-8")
    (out / "patterns.md").write_text(render_patterns(), encoding="utf-8")
    surfaces = KNOWLEDGE_SRC / "config-surfaces.md"
    if surfaces.is_file():  # diagnostician's tool surface (ticket 19 consumes)
        shutil.copy(surfaces, out / "config-surfaces.md")
    logger.info("[knowledge] rendered %d artifacts to %s",
                len(list(out.glob("*.md"))), out)
    return out


# ---------------------------------------------------------------------------
# The slice map (SKILL.md's routing job, retired into code -- ticket 11)
# ---------------------------------------------------------------------------


def slices_for(stage: str, flow_types: Optional[List[str]] = None) -> Dict[str, str]:
    """Named inline knowledge blocks for a stage, per ticket 11's matrix.
    ``flow_types`` is the component-type list from flow.json -- the mechanical
    flow-scoping filter for post-flow stages (configure/assemble/diagnose).
    """
    if stage == "doc_normalize":
        return {"landmines": render_landmines()}
    if stage == "interpret":
        return {"landmines": render_landmines()}
    if stage == "design":
        return {
            "patterns": render_patterns(),
            "config_reference": render_config_reference(),
            "landmines": render_landmines(),
            "envelope_wiring": render_job_envelope(worked_example=False),
        }
    if stage == "configure":
        return {
            "config_reference": render_config_reference(flow_types),
            "landmines": render_landmines(flow_types),
            "envelope_schema": render_job_envelope(worked_example=False),
        }
    if stage == "assemble":
        return {
            "envelope": render_job_envelope(worked_example=True),
            "landmines": render_landmines(flow_types),
        }
    if stage == "diagnose":  # ticket 19 consumes
        return {
            "landmines": render_landmines(flow_types, anchors=True),
            "envelope": render_job_envelope(worked_example=True),
            "config_reference": render_config_reference(flow_types),
        }
    if stage == "orchestrator":  # ticket 18 consumes
        return {
            "patterns": render_patterns(),
            "envelope_wiring": render_job_envelope(worked_example=False),
            "landmine_summaries": render_landmine_summaries(),
        }
    return {}
