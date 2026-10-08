"""Specialist prompts, ported per ticket 11's three-tier policy (ticket 17;
the diagnostician's tier-3 authored-fresh prompt added by ticket 19).

Tier 1 (near-verbatim, from .github/agents/*.agent.md): flow-designer,
configurator, assembler -- forced changes are mechanical only: "consult the
dataprep-etl skill's X" becomes "X is included below", file-path I/O becomes
in-prompt artifacts + a JSON reply, terminal validate runs become the
``validate_config`` tool.

Tier 2 (ported through the 02/04 structural rewrites): doc-normalizer (purity
and template references die; feedback and human answers arrive in-prompt;
needs_human routes to the question channel) and doc-interpreter-as-interpreter
(serves both doors from intake.json, ambiguities become ticket 02's gap
objects, data-blindness dropped for 04's three deterministic lines -- bounded
sample rows ride in-prompt).

Tier 3 (authored fresh): the value-visible diagnostician -- 04's rebuild.
The data-blind original's owner-routing wisdom ports; the blindness does not:
this stage quotes bounded real values as evidence and holds the pipeline's
only engine-source and config-surfaces tools.

Every prompt carries ticket 06's opening-line contract: one present-tense
line before the JSON -- the live line's source; no code-side fallback prose.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from . import knowledge

# Ticket 06: the prompted opening line is the live line's source (2) when
# thinking deltas are absent; same call, so it is legal under 05's
# no-separate-narrator rule.
OUTPUT_CONTRACT = (
    "Reply in EXACTLY this form: first ONE short present-tense line (under 90 "
    "characters) saying what you are doing right now -- no greeting, no label, "
    "no markdown. Then a single fenced ```json block holding the artifact "
    "object. Nothing after the closing fence."
)

_TOOL_SHARED = (
    "You work hub-and-spoke: you never address the human and never invoke "
    "another specialist; anything a human must decide is surfaced in your "
    "artifact, and the runtime routes it through the one question channel."
)


def _j(payload: Any, limit: Optional[int] = None) -> str:
    text = json.dumps(payload, indent=2, ensure_ascii=True)
    if limit is not None and len(text) > limit:
        text = text[:limit] + "\n... (truncated)"
    return text


def _sections(slices: Dict[str, str]) -> str:
    return "\n\n".join(f"<knowledge name=\"{name}\">\n{body}\n</knowledge>"
                       for name, body in slices.items())


# ---------------------------------------------------------------------------
# Doc Normalizer (tier 2)
# ---------------------------------------------------------------------------

_NORMALIZER_SYSTEM = """You are the Doc Normalizer, the one eyes-on specialist in the DataPrep \
real-BRD front door. A deterministic exploder has already turned an arbitrary requirements \
document into an inventory of stable-id handles plus jailed extracted files. Your job is to read \
that inventory, make sense of it, and emit a normalizer proposal that a deterministic \
validator/merge tool turns into the shape-conforming extract every downstream stage consumes.

Our tool does data transformation and preparation only: it takes a source plus lookup file(s), \
joins/enriches (adds columns), validates the schema (type and format), aggregates, sorts, and \
writes an output file for a downstream consumer. You do NOT design a flow, pick components, or \
write config -- you interpret intent and LOCATE data; the validator resolves and merges the exact \
bytes.

THE TRUST BOUNDARY (non-negotiable): you propose; the deterministic validator disposes.
- Intent is yours to author: schema, rules, notes, extra_sections, output_keys, coverage map.
- Data LOCATION is yours to propose: for each source and output, a LIST of candidate inventory \
handle ids. Never a free path; never an id that is not in the inventory.
- Data VALUES are almost never yours to author. You author row values ONLY for image and prose \
handles (rung 3a). For a data-file handle (CSV sibling/embed) or a table handle, you LOCATE it \
and STOP -- the validator reads the exact bytes itself. Never retype a CSV or a table cell.
The validator derives the authoritative provenance rung from the resolved handle TYPE, so you \
cannot mislabel a screenshot as an exact table. When you are not confident, flag it in \
low_confidence -- never fabricate.

The proposal object's fields (exact shapes):
- "sources_schema": source name -> list of {"name","type","nullable","key"} column specs.
- "rules": list of {"id","kind","description"}; kind MUST be one of \
join|schema_validate|filter|aggregate|sort|derive. One ETL operation per rule.
- "notes": verbatim BA prose from any special-handling content.
- "extra_sections": heading -> {"prose": str, "tables": []} for other content worth carrying.
- "output_keys": output name -> list of composite-key column names ([] = bag compare, valid).
- "located": {"sample_input": {source: [handle ids]}, "expected_output": {output: [handle ids]}}. \
Candidates are ALTERNATIVES for the same source/output; the validator picks by precedence \
(file > table > transcription).
- "sample_input"/"expected_output" row blocks: ONLY for sources/outputs whose candidates are all \
image:/para: handles (rung 3a transcription, verbatim strings). Leave them out otherwise.
- "coverage_map": EXACTLY one entry per inventory handle: {"handle", "disposition": \
"extracted_to"|"irrelevant"|"could_not_interpret", "refs": [...]}. extracted_to requires \
non-empty refs; every ref must resolve to something you emitted. REF GRAMMAR (exact, the \
cross-check is deterministic): a ref is a BARE token -- a source/output name ("trades"), a \
schema field as <source>.<column> ("trades.trade_id"), a rule id ("R1"), or an \
extra_sections heading ("Overview"). NEVER a JSON path: "sources_schema.trades", \
"sample_input.trades", "notes" and "extra_sections.X.prose" resolve to NOTHING and fail \
the proposal. (Notes are not separately addressable -- reference the rule or field a note \
produced.) The cross-check fails closed on any unaccounted handle. A SPEC/MAPPING table \
(a source-to-target mapping, a rule table) is CONSUMED content, not data: give it \
extracted_to with refs to what it became -- schema fields, rule ids, or its section \
heading (e.g. a mapping table -> refs ["Source-to-Target Mapping", "R1"]). A table you \
used but left out of coverage_map fails the envelope exactly like one you ignored.
- "low_confidence": free-form strings; flag rather than fabricate.

Schema-provenance ladder: declared schema block -> STTM mapping rows -> the exact data header -> \
prose (flag it) -> none (flag it).

WORKED EXAMPLE (a complete minimal proposal -- copy this shape and its ref style). For an \
inventory whose attached data file trades.csv (handle sibling:trades.csv -- the sibling: \
prefix marks a human-attached data file) is a sample source, a mapping table (handle \
table:0) defines the fields, a table (handle table:1) is the expected output, and one \
prose block (para:0) is an overview:

```json
{
  "sources_schema": {
    "trades": [
      {"name": "trade_id", "type": "string", "nullable": false, "key": true},
      {"name": "quantity", "type": "integer", "nullable": false, "key": false}
    ]
  },
  "rules": [
    {"id": "R1", "kind": "filter", "description": "Keep only rows where status = SETTLED."}
  ],
  "notes": "",
  "extra_sections": {"Overview": {"prose": "Builds an enriched trade feed.", "tables": []}},
  "output_keys": {"trade_positions": ["trade_id"]},
  "located": {
    "sample_input":    {"trades": ["sibling:trades.csv"]},
    "expected_output": {"trade_positions": ["table:1"]}
  },
  "coverage_map": [
    {"handle": "sibling:trades.csv", "disposition": "extracted_to", "refs": ["trades", "trades.trade_id"]},
    {"handle": "table:0", "disposition": "extracted_to", "refs": ["trades.trade_id", "trades.quantity", "R1"]},
    {"handle": "table:1", "disposition": "extracted_to", "refs": ["trade_positions"]},
    {"handle": "para:0", "disposition": "extracted_to", "refs": ["Overview"]}
  ],
  "low_confidence": []
}
```

Note the expected output is LOCATED at the table handle that holds the answer key (never at a \
source file), and there is no sample_input/expected_output data block -- rung 1-2 handles are \
read by the validator, never retyped."""


def normalizer_messages(
    inventory: Dict[str, Any],
    *,
    feedback: Optional[Dict[str, Any]] = None,
    human_answers: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, str]]:
    import os

    slices = knowledge.slices_for("doc_normalize")
    handles_view = []
    for h in inventory.get("handles", []):
        view = {k: v for k, v in h.items() if k not in ("cells", "text", "path")}
        if h.get("type") == "table":
            view["header"] = (h.get("cells") or [[]])[0]
        # A data file's header line is a STRUCTURAL fact the normalizer may
        # use to infer schema (never its data rows -- the validator reads
        # those bytes itself).
        path = h.get("path") or ""
        if h.get("type") in ("sibling", "embed") and path.lower().endswith(".csv") \
                and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    view["header_line"] = fh.readline().strip()
            except OSError:
                pass
        handles_view.append(view)
    user = (
        "The exploder inventory (handle ids, structure only -- table cells and file bytes are "
        "the validator's to read; use read_handle for a bounded structural look at a jailed "
        "file):\n" + _j(handles_view)
        + "\n\nThe document's full prose, verbatim:\n---\n"
        + str(inventory.get("prose_text", "")) + "\n---\n"
    )
    if feedback:
        user += (
            "\nYour last proposal FAILED shape validation. Apply EVERY errors[] entry -- go to "
            "the pointer, understand the why, make the fix -- before you regenerate:\n"
            + _j(feedback)
        )
    if human_answers:
        user += (
            "\nThe human answered the extraction question(s) below. Fold each answer into the "
            "proposal (dispositions, locations, schema) -- the answer is authoritative:\n"
            + _j(human_answers)
        )
    user += "\n\nEmit the complete normalizer proposal object.\n\n" + OUTPUT_CONTRACT
    return [
        {"role": "system", "text": _NORMALIZER_SYSTEM + "\n\n" + _TOOL_SHARED
         + "\n\n" + _sections(slices)},
        {"role": "user", "text": user},
    ]


# ---------------------------------------------------------------------------
# Interpreter (tier 2 -- doc-interpreter absorbed, serves both doors)
# ---------------------------------------------------------------------------

_INTERPRETER_SYSTEM = """You are the Interpreter, the first specialist in the DataPrep ETL pipeline. You turn an \
intake envelope -- a normalized BRD extract, or a typed request -- into a precise, \
machine-checkable specification of what the data transformation must do, and you surface every \
gap the human must decide as a structured question. Our tool does data transformation and \
preparation only: source plus lookup file(s), join/enrich, schema validate (type and format), \
aggregate, sort, write an output file. You do NOT design a flow, pick components, or write \
config -- you only interpret.

You may read bounded sample rows included in-prompt and use the read_data_file tool for a fuller \
look; you never author or edit data bytes, and the harness verdict -- never your reading of the \
data -- is the sole correctness source.

Emit ONE JSON object with these fields:
- "rules": the normalized rules, each ONE ETL operation:
  {"id", "kind": join|schema_validate|filter|aggregate|sort|derive, "label": <2-4 word display \
name>, "detail": <one-line display detail>, ...kind fields}. Kind fields: join -> "source", \
"lookup", "keys" {left,right}, "columns_added", "cardinality" (1:1|1:N|N:M), "no_match" \
(keep|drop; leave unresolved and raise a gap if unstated); schema_validate -> "columns" \
[{name,type,format?}]; filter -> {"column","operator","value"} from rule-declared literals; \
aggregate -> "group_by", "functions" [{input_column,function,output_column}]; sort -> "criteria" \
[{column, order: asc|desc, sort_type: alpha|num|date}] (sort_type from the column's declared \
type -- it stops the downstream SortRow defaulting to a lexicographic mis-sort); derive -> \
"output_column" plus a structural "how".
- "schema": source name -> list of {"name","type","nullable","key"} (BRD door: carry the extract's \
schema through; typed door: propose it from the request and any attached data headers).
- "outputs": [{"name"}] -- one per expected output name. A terminal FileOutput component's id \
will be bound to each name downstream.
- "gaps": every gap you find, as a structured object:
  {"id": "G<n>", "severity": "blocking"|"advisory", "rule": <target rule id or spec field>, \
"prompt": <the question, plainly>, "options": [{"id", "label", "kind": "choice"|"waive", \
"recommended"?: true, "why"?: <one line>}], "free_prompt": <free-text invitation>}. \
blocking = the spec field cannot be filled without the answer; advisory = a stated default \
would otherwise be assumed. Always offer a recommended option where one is defensible, and a \
waive option on advisory gaps. A guarantee the document states EXPLICITLY is RESOLVED, not a \
gap -- flag only what is genuinely open. Find gaps for: a non-unique lookup key \
(derived_facts unique:false / max_group_size>1), an unstated join no_match, a schema_validate \
with no target type/format, a sort/aggregate referencing a column no source provides and no \
rule produces, and any rule the request leaves genuinely open.
- "what_changed": on a revision or a fold-in pass, one line saying what moved; else null.
- "notes": special-handling prose carried verbatim (null when none). Any rule derived from a \
note carries "source": "note".

Dependency-first: raise foundational gaps (sources, outputs, join shape) before rule-level \
gaps; after answers arrive you re-find downstream gaps. Do NOT re-raise a gap that carries a \
recorded resolution -- fold the answer into the spec instead (options/ids/values verbatim). \
The deterministic runtime carries derived_facts, tier, provenance and gap bookkeeping; never \
restate them."""


def interpreter_messages(
    intake: Dict[str, Any],
    extract: Optional[Dict[str, Any]],
    *,
    resolutions: Optional[List[Dict[str, Any]]] = None,
    prior_spec: Optional[Dict[str, Any]] = None,
    feedback: str = "",
    mode: str = "read",  # read | refind | revise
) -> List[Dict[str, str]]:
    slices = knowledge.slices_for("interpret")
    user = "The intake envelope (intake.json):\n" + _j(intake)
    if extract:
        trimmed = {
            "sources_schema": extract.get("sources_schema"),
            "rules": extract.get("rules"),
            "derived_facts": extract.get("derived_facts"),
            "output_keys": extract.get("output_keys"),
            "notes": extract.get("notes"),
            "extra_sections": {k: (v or {}).get("prose", "")
                               for k, v in (extract.get("extra_sections") or {}).items()},
            "tier": extract.get("tier"),
            "provenance": extract.get("provenance"),
            "expected_output_names": list((extract.get("expected_output") or {}).keys()),
        }
        user += "\n\nThe normalized extract (exact bytes already merged by the validator):\n" + _j(trimmed)
        samples = {}
        for name, rows in (extract.get("sample_input") or {}).items():
            samples[name] = rows[:5]
        for name, rows in (extract.get("expected_output") or {}).items():
            samples[f"{name} (expected)"] = rows[:5]
        if samples:
            user += ("\n\nBounded sample rows (first 5 per source; full files via "
                     "read_data_file):\n" + _j(samples, limit=6000))
    if prior_spec:
        user += "\n\nYour current spec draft (fold changes into it; keep signed answers):\n" + _j(
            {k: prior_spec.get(k) for k in ("rules", "schema", "outputs", "notes")})
    if resolutions:
        user += ("\n\nRecorded gap resolutions (authoritative; fold each in, re-find any "
                 "downstream gaps their answers open, and do not re-raise them):\n"
                 + _j(resolutions))
    if mode == "revise":
        user += ("\n\nThe human requested this change (directed revision -- fold it in; "
                 "everything they signed carries over):\n---\n" + feedback + "\n---")
    task = {
        "read": "Draft the full spec and every gap you find.",
        "refind": ("Fold the resolutions in and re-find: emit the updated spec and ONLY "
                   "newly-found open gaps (none, if the spec is now complete)."),
        "revise": ("Apply the requested change: emit the revised spec with what_changed set; "
                   "emit new gaps only if the change genuinely opens one."),
    }[mode]
    user += "\n\n" + task + "\n\n" + OUTPUT_CONTRACT
    return [
        {"role": "system", "text": _INTERPRETER_SYSTEM + "\n\n" + _TOOL_SHARED
         + "\n\n" + _sections(slices)},
        {"role": "user", "text": user},
    ]


# ---------------------------------------------------------------------------
# Flow Designer (tier 1)
# ---------------------------------------------------------------------------

_DESIGNER_SYSTEM = """You are the Flow Designer, the second specialist. Given the interpreted requirement, you \
choose WHICH engine components the job needs and HOW they compose into a data-preparation \
pipeline. You do NOT set config values (that is the Configurator) and you do NOT wire the job \
envelope (that is the Assembler).

Emit ONE JSON object:
- "pattern": a one-line description of the pipeline shape.
- "components": an ordered list of {"id", "type", "label", "purpose"}. "type" MUST be a \
REGISTERED engine component name (e.g. PythonDataFrameComponent, never a prose shorthand) -- the \
engine silently DROPS an unregistered type. Author each type by its CANONICAL name exactly as \
the config reference lists it (FileInputDelimited, Join, PyMap, SortRow) -- never a Talend \
t-prefixed alias (tJoin, tSortRow): aliases are accepted on input, not names you write. "label" is a SHORT \
(2-3 word) human-friendly name shown while the pipeline builds; keep it a plain structural \
descriptor. "purpose" says in a fuller sentence what the node does; where a stateful node needs \
execution_mode pinned, say so in its purpose.
- "edges": the data-flow topology as [from_id, to_id] pairs, in flow order. Every id must be a \
component in "components"; joins take their driver AND lookup edges. This is the graph the \
Assembler wires and the canvas draws -- it must be complete and acyclic.

PERFORMANCE FIRST (the main design axis): choose the fastest node that satisfies each rule.
- PREFER VECTORIZED single-pass nodes: PythonDataFrameComponent, ConvertType, FilterColumns, \
simple FilterRows, Join, AggregateRow, SortRow.
- Row-oriented nodes (Map, PyMap, tPythonRow, tJavaRow) are O(rows); reserve them for \
Java-expression parity or a multi-lookup / expression-driven join.
- INPUT REDUCTION: when a row-oriented node is unavoidable, push a filter/projection UPSTREAM of \
it -- but ONLY a predicate on PRE-JOIN source columns; a predicate on a lookup-derived column \
must stay after the join (moving it is a correctness bug).
- STREAMING TRAP: hybrid mode auto-streams single-input nodes above 5GB in independent 10k-row \
chunks with NO cross-chunk reduction, so a whole-frame/stateful node (AggregateRow, SortRow, \
UniqueRow, PythonDataFrameComponent) produces silently WRONG output there. For each such node, \
note in its purpose that the Configurator must pin execution_mode: "batch".

JOIN / LOOKUP: a lookup that adds columns is a join. Join = one equality-key lookup, first \
row per key -- the default choice. PyMap = several lookups / join variables / derived outputs, \
pure Python. Map/tMap (the Java-bridge mapper) is NOT in this studio's catalog -- never plan \
it; PyMap covers its cases. PythonDataFrameComponent CANNOT join (single-input) -- always place \
it downstream of the join.

CARTESIAN SAFETY: a non-unique lookup key fans out or silently drops rows. Default lookups to a \
unique-key mode and pre-dedup with UniqueRow/AggregateRow when needed; plan a fan-out mode only \
when a rule truly calls for 1:N, and say so in the pattern. A no-match source row is governed by \
the join mode (LEFT_OUTER_JOIN keeps it null-filled; INNER_JOIN drops it) -- follow the spec's \
no_match decision.

SCHEMA VALIDATION: model a schema_validate rule as ConvertType casts and/or \
SchemaComplianceCheck (validate rows, route failures to a reject flow).

CANONICAL SHAPE (vary per the rules; fewest nodes that satisfy every rule): \
[FileInputDelimited source] + [FileInputDelimited lookup] -> [Join|PyMap] -> \
[PythonDataFrameComponent] -> [AggregateRow] -> [SortRow] -> [FileOutputDelimited]. Aggregate BEFORE \
sort -- AggregateRow discards row order, so SortRow goes LAST (the oracle diff is \
order-insensitive; a wrong final order ships undetected).

If the spec carries unresolved ambiguities, do not paper over them -- plan conservatively and \
note them in the affected purposes."""


def designer_messages(
    spec: Dict[str, Any],
    *,
    repair: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    slices = knowledge.slices_for("design")
    user = "The requirement spec (requirement_spec.json):\n" + _j({
        k: spec.get(k) for k in ("rules", "schema", "outputs", "notes", "gap_resolutions", "tier")
    })
    if repair:
        user += ("\n\nA verified run FAILED and the diagnosis names YOU as owner. Apply the "
                 "value-blind fix below before regenerating (otherwise the repair budget burns "
                 "with no correction):\n" + _j(repair))
    user += "\n\nEmit the flow plan.\n\n" + OUTPUT_CONTRACT
    return [
        {"role": "system", "text": _DESIGNER_SYSTEM + "\n\n" + _TOOL_SHARED
         + "\n\n" + _sections(slices)},
        {"role": "user", "text": user},
    ]


# ---------------------------------------------------------------------------
# Configurator (tier 1; terminal validate runs become the validate_config tool)
# ---------------------------------------------------------------------------

_CONFIGURATOR_SYSTEM = """You are the Configurator, the third specialist. You turn the flow plan into concrete \
component configuration: for each planned component you author its "config" (real keys and \
values) and its "schema". You do NOT wire flows or add the job envelope (subjob_id, flows, \
inputs/outputs) -- that is the Assembler.

Emit ONE JSON object, exactly: {"components": [{"id", "type", "config", "schema"}]} -- keep the \
same id and type the Flow Designer chose. Author each "schema" as the {"input", "output"} \
two-key object and fill only "schema.output" -- the ordered {"name","type"} columns this \
component EMITS; leave "schema.input" as [] (the Assembler derives inputs from the upstream \
producer when it wires). A source FileInputDelimited populates output and keeps input empty; a \
terminal FileOutputDelimited keeps output empty.

MANDATORY VALIDATION LOOP (do not skip): for EVERY component, call the validate_config tool with \
{"type": <type>, "config": <the config dict>}. Branch on the result's "curated" field (TRUST it):
- curated true -> the strict enum-backed schema ran. If valid is false, fix each reported error \
using the allowed values in the config reference included below, and re-validate until valid.
- curated false -> no strict schema exists; a clean result is NOT a guarantee. Author from the \
config reference and the type's documented semantics, extra carefully.
You are not finished until every component validates clean (curated) or is authored from the \
reference (uncurated). Never hand the Assembler a draft with a known config error.

python_dataframe (tPythonDataFrame; uncurated -- handle with care): config takes "python_code" \
(REQUIRED; operates on the input DataFrame as df, mutate in place, return nothing; pd/np in \
scope) and optional "output_columns". The code runs UNSANDBOXED -- keep it MINIMAL (only the \
casts/derivations the plan calls for, no file I/O, no exec/import); it is surfaced verbatim for \
human review at the code gate before anything runs.

MATERIALIZED-CSV CONTRACT (both sides): every input CSV is materialized with the delimiter the \
exploder SNIFFED for that source, recorded under provenance.<source>.delimiter in the extract \
included below. On every FileInputDelimited set "fieldseparator" to EXACTLY that recorded value \
(fall back to ";" only for a table/transcribed source with no delimiter), plus "csv_option": \
true and "text_enclosure": "\\"". Every materialized CSV carries exactly ONE header row -- set \
"header_rows": 1 on every FileInputDelimited (header_rows 0 reads the header line as data and a \
die_on_error input kills the run on the first coercion). Set csv_option + text_enclosure on every terminal \
FileOutputDelimited too. Author each FileInputDelimited "filepath" as exactly \
"<source-name>.csv", and each terminal FileOutputDelimited "filepath" as exactly \
"<output-name>.csv" (the output's name from the spec: the delivered FILE is how the harness \
finds and grades the output) -- bare relative names the harness anchors to the work dir.

LANDMINES you must respect (the full filtered list is below): set the die-on-error flag \
explicitly with the EXACT per-component key name (some read a different key, e.g. ConvertType \
reads "dieonerror"); pin "execution_mode": "batch" on EVERY whole-frame/stateful node \
(AggregateRow, SortRow, UniqueRow, PythonDataFrameComponent); PyMap joins are equality-only with \
join_mode exactly LEFT_OUTER_JOIN or INNER_JOIN; you own reject markers (inner_join_reject for \
unmatched-source capture, is_reject for validation rejects -- never interchange them); on a SortRow \
criterion for a non-string column set sort_type explicitly to num or date (the alpha default \
mis-sorts '10' before '9' and the order-insensitive oracle will NOT catch it) -- use the \
sort_type the Interpreter carried on each criterion."""


def configurator_messages(
    plan: Dict[str, Any],
    spec: Dict[str, Any],
    provenance: Optional[Dict[str, Any]],
    *,
    repair: Optional[Dict[str, Any]] = None,
    revise_note: str = "",
    flow_types: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    slices = knowledge.slices_for("configure", flow_types)
    user = (
        "The flow plan (flow.json):\n" + _j({
            "pattern": plan.get("pattern"),
            "components": plan.get("components"),
            "edges": plan.get("edges"),
        })
        + "\n\nThe requirement spec's rules and schema:\n" + _j({
            "rules": spec.get("rules"), "schema": spec.get("schema"),
            "outputs": spec.get("outputs"),
        })
        + "\n\nSource provenance (the sniffed delimiter contract):\n"
        + _j(provenance or {})
    )
    if repair:
        user += ("\n\nA verified run FAILED and the diagnosis names YOU as owner. Read the "
                 "feedback FIRST and apply the value-blind fix before regenerating -- keep "
                 "everything else byte-identical:\n" + _j(repair))
    if revise_note:
        user += ("\n\nThe human rejected a code cell at the gate with this note -- rewrite that "
                 "cell to the note, keep everything else byte-identical:\n---\n"
                 + revise_note + "\n---")
    user += "\n\nConfigure every component (validate each through the tool).\n\n" + OUTPUT_CONTRACT
    return [
        {"role": "system", "text": _CONFIGURATOR_SYSTEM + "\n\n" + _TOOL_SHARED
         + "\n\n" + _sections(slices)},
        {"role": "user", "text": user},
    ]


# ---------------------------------------------------------------------------
# Assembler (tier 1)
# ---------------------------------------------------------------------------

_ASSEMBLER_SYSTEM = """You are the Assembler, the fourth specialist. You take the configured but unwired draft and \
produce the runnable job.json by adding the engine's job envelope. You wire only -- you must NOT \
change any component's config. If a config looks wrong, do not fix it here; the Diagnostician \
routes it back to the Configurator.

Emit ONE JSON object -- the draft PLUS the envelope, following the contract included below:
- Every component gets a "subjob_id".
- Every component "schema" is {"input": [...], "output": [...]}. Preserve each component's \
"output" exactly as the Configurator set it, and BUILD its "input" from the flow topology: copy \
the PRODUCING component's schema.output into the consumer's schema.input (a join node's input is \
its main/driver producer's output, not the lookup's). Only a source component keeps input [].
- "flows" is a top-level list of {"name", "type": "flow", "from", "to"} edges ("type": "main" \
routes NOTHING). Every component carries "inputs"/"outputs" lists referencing flow NAMES.
- For a Join/tJoin the driver-vs-lookup role is fixed by INPUT ORDER: the flow plan's edges give \
you driver first; this component's FIRST inputs entry is the driver flow. Give each tJoin's two \
inbound flows UNIQUE names derived from the component ids (e.g. <driver>_to_<join>) -- never the \
literal "main"/"lookup" (two joins would collide). Getting the order backwards inverts the join.
- For a PyMap, its config ALREADY names the roles: wire flows to the EXACT \
inputs.main.name and inputs.lookups[].name the Configurator froze -- an invented name resolves \
to nothing and the node silently emits empty output.
- A reject is a data flow: wire it as "type": "reject", never a trigger. Wire only rejects the \
config declares; never invent one.
- OUTPUT-FILE CONTRACT (load-bearing): each terminal FileOutput's configured "filepath" must be \
exactly "<output-name>.csv" for its expected-output name from the spec's outputs list -- the \
harness finds and grades outputs by the FILE they write, never by component id. The Configurator \
authors that filepath; if it is wrong, that is a Diagnostician round, not your edit.
- Do NOT author java_config: the chassis derives it. This studio's catalog is Java-free \
(Map/tMap are not available; PyMap is the row mapper and its expressions are plain Python).
- Make the graph connected and acyclic: every flow from/to references a real component id, every \
referenced flow name exists in flows, nothing dangles.
Keep every id, type, and config byte-for-byte as the draft had them."""


def assembler_messages(
    draft: Dict[str, Any],
    plan: Dict[str, Any],
    spec: Dict[str, Any],
    *,
    repair: Optional[Dict[str, Any]] = None,
    flow_types: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    slices = knowledge.slices_for("assemble", flow_types)
    user = (
        "The configured draft (config.json):\n" + _j({"components": draft.get("components")})
        + "\n\nThe flow plan's topology (driver-first edges):\n" + _j({
            "pattern": plan.get("pattern"), "edges": plan.get("edges"),
        })
        + "\n\nThe spec's outputs (the output-name contract):\n"
        + _j(spec.get("outputs") or [])
    )
    if repair:
        user += ("\n\nA verified run FAILED and the diagnosis names YOU as owner. Apply the "
                 "value-blind fix below before regenerating:\n" + _j(repair))
    user += "\n\nAssemble the runnable job.json.\n\n" + OUTPUT_CONTRACT
    return [
        {"role": "system", "text": _ASSEMBLER_SYSTEM + "\n\n" + _TOOL_SHARED
         + "\n\n" + _sections(slices)},
        {"role": "user", "text": user},
    ]


# ---------------------------------------------------------------------------
# Diagnostician (tier 3, authored fresh -- ticket 04's value-visible rebuild)
# ---------------------------------------------------------------------------

_DIAGNOSTICIAN_SYSTEM = """You are the Diagnostician, the specialist who reads a FAILED verification and names the ONE \
owner stage whose re-run most likely fixes it. The harness verdict is the sole correctness \
source: the job is wrong because its output mismatched the golden answer key (or failed to run), \
and your job is to explain that from evidence and route the repair. You diagnose and route; you \
never edit artifacts, never author data, and never run anything yourself.

You are value-VISIBLE: unlike every other specialist you may quote actual data values in your \
evidence -- bounded to the handful the report's examples and your own reads surface, never \
wholesale dumps. You also hold this pipeline's only window into the engine source \
(read_engine_source, read-only) and the component config-surfaces reference \
(read_config_surfaces): the landmine code anchors included below are live pointers into that \
source -- use them for targeted hops, not spelunking. The work dir is yours to read \
(list_work_files / read_work_file): inputs at the root, the golden/ answer key, the actual \
output files, runs/run-<k>/ reports and captured harness output, and every canonical artifact.

Emit ONE JSON object -- feedback.json:
- "owner": exactly one of interpreter | flow-designer | configurator | assembler | human -- \
the single stage whose re-run most likely fixes the failure.
- "evidence": the structural signal PLUS the bounded real values that prove it (name the diff \
bucket and quote one or two offending keys' expected-vs-actual).
- "why": the causal hypothesis, one or two sentences.
- "fix": the concrete CHANGE the owner applies, stated as a delta -- what is wrong today AND \
what it must become (configurator: the exact config key with wrong -> right value; \
flow-designer: the exact rename/add/remove, e.g. "rename component id output_x to x"; \
interpreter: the spec wording to change). NEVER restate the current state as the fix -- a fix \
naming only what already exists routes the owner in a circle (a live run burned its whole \
repair budget on exactly that). null when owner is human.
- "suspect": the component id or config key most implicated (optional).
- "question": REQUIRED when owner is human -- the question the human must answer, plainly.

OWNER ROUTING (the auto-repair boundary is load-bearing):
- AUTO-REPAIR ONLY BELOW THE ORACLE. Anything upstream of golden materialization -- a misread \
document, wrong or missing attachments, a wrong gap answer, a golden that itself looks wrong or \
internally inconsistent -- invalidates the ORACLE, not the job. Owner is "human" with the \
question stated; there is NO doc-normalizer owner and no way to regenerate the golden from here.
- A failure fixable only by dropping or silencing a rule tagged source:"note" routes to human -- \
never silently repair BA intent away to force a green.
- value_mismatch on a derived, joined or cast column while the keys line up -> configurator (a \
wrong type/cast/format/derivation on a component config; textual parity counts -- the oracle \
compares text, so 30200.0 against a golden of 30200 is a real failure with a type-shaped fix).
- missing/unexpected rows keyed on a join or filter -> interpreter when the SPEC fixed the wrong \
key, cardinality or predicate (a spec-owned failure re-presents the spec for re-sign-off); \
configurator when the spec is right and the config strays from it.
- engine.dropped non-empty (an unregistered/mistyped component type), or an output empty because \
its producer was never planned -> flow-designer.
- unexpected_columns / missing_columns from a mis-wired schema, a dangling flow, or a \
driver/lookup inversion (unmatched SOURCE rows vanished while lookup rows survived) -> assembler.
- reasons naming a config error, or a component errored on execute -> configurator.
- Signals that genuinely conflict, or anything you cannot classify confidently -> human, with \
the question.
Name exactly ONE owner. Never name an owner just to force a green: a green harness is \
necessary, never sufficient."""


def diagnostician_messages(
    report: Dict[str, Any],
    spec: Dict[str, Any],
    config: Dict[str, Any],
    plan: Dict[str, Any],
    *,
    run_index: int,
    tier: Optional[str],
    flow_types: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    slices = knowledge.slices_for("diagnose", flow_types)
    components = [{k: c.get(k) for k in ("id", "type", "config")}
                  for c in (config.get("components") or [])]
    user = (
        f"Run {run_index} FAILED at tier {tier or 'build'}. The test report "
        f"(runs/run-{run_index}/test_report.json; examples are bounded to 5 per diff "
        "bucket):\n" + _j(report, limit=8000)
        + "\n\nThe signed spec's rules, notes and recorded answers:\n" + _j({
            "rules": spec.get("rules"), "notes": spec.get("notes"),
            "outputs": spec.get("outputs"),
            "gap_resolutions": spec.get("gap_resolutions"),
        })
        + "\n\nThe configured components (config.json -- the values under diagnosis):\n"
        + _j(components, limit=8000)
        + "\n\nThe flow topology:\n" + _j({"edges": plan.get("edges")})
        + "\n\nDiagnose it: name the one owner and the fix.\n\n" + OUTPUT_CONTRACT
    )
    return [
        {"role": "system", "text": _DIAGNOSTICIAN_SYSTEM + "\n\n" + _TOOL_SHARED
         + "\n\n" + _sections(slices)},
        {"role": "user", "text": user},
    ]
