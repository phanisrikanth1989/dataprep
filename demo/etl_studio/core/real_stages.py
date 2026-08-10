"""The real pipeline stages on ticket 16's chassis: the two doors and the
design-side specialists (ticket 17) plus the verification spine (ticket 19)
-- materializer, harness-as-subprocess test runner, and the value-visible
diagnostician. Every slot is real; the stub rig is gone.

Structural rules carried here:
- Stages never raise questions; machine facts ride StageResult and the
  conductor owns the channel (needs_human answers come back through
  ``run.nh_resolutions``, shape feedback through ``ctx.repair``).
- The data-write ban is structural: no specialist holds a data-write tool;
  only the exploder's jailed extraction and the materializer write data
  files (04's first deterministic line).
- The engine-source mount is diagnostician-only: no other stage's tool
  registry carries ``read_engine_source`` -- registry absence IS the
  enforcement (ticket 11).
- Every artifact a stage parses from a stream is also read back from the bus
  when the journal skipped the stream (crash-restore re-walk).
- Rig knobs (smoke's and the autorun rig's, never the webview's) select
  scripted-fixture LABELS for demo beats; the vendored validators and the
  real harness judge whatever content plays, live or scripted:
  shape_errors / needs_human (doc-normalizer beats), diag_misses (the first
  N configurator-owned diagnoses play the misdiagnosis fixture),
  owner_human (the first diagnosis names the human), malformed_design
  (bounded-retry escalation), scripted_slots (force named slots onto the
  scripted port in a live run -- the live-probe affordance).
"""

from __future__ import annotations

import asyncio
import copy
import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import knowledge
from .llm import LlmCallError
from .port import ToolDecl
from .prompts import (
    assembler_messages,
    configurator_messages,
    designer_messages,
    diagnostician_messages,
    interpreter_messages,
    normalizer_messages,
)
from .specialist import run_specialist
from .stages import StageAdapter, StageContext, StageResult
from .vendored.explode_doc import explode
from .vendored.materialize_golden import materialize_golden
from .vendored.normalize_validate import validate_proposal
from .vendored.validate_config import validate_config

logger = logging.getLogger(__name__)

# The demo job identity: run dirs and run ids derive from it (<job>-r<k>).
JOB = "trade_positions"

# Slots whose streams route to the live provider when one resolved (17's
# specialists + 18's orchestrator + 19's diagnostician).
LIVE_SLOTS = frozenset({"doc_normalize", "interpret", "design", "configure", "assemble",
                        "orchestrator", "diagnose"})

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BRD = os.path.join(STUDIO_ROOT, "examples", "trade_position_demo.docx")

# Repo root (real_stages.py -> core/ -> etl_studio/ -> demo/ -> repo): the
# harness subprocess cwd and the diagnostician's read-only src/v1 jail root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_HARNESS_CLI = Path(__file__).resolve().parent / "vendored" / "run_and_validate.py"
_ENGINE_SRC_ROOT = _REPO_ROOT / "src" / "v1"

HARNESS_TIMEOUT_S = 180  # a hung job code cell must never hang the core
_SOURCE_LINE_CAP = 120
_WORK_READ_CAP = 8192

_READ_CAP_BYTES = 4096
_SAMPLE_ROW_CAP = 50

# Component type -> canvas node kind (derived state, ticket 06's sanctioned
# classify()-style projection; label/purpose stay model-authored).
_KIND_BY_TYPE = {
    "FileInputDelimited": "source", "tFileInputDelimited": "source",
    "FileOutputDelimited": "output", "tFileOutputDelimited": "output",
    "FilterRows": "filter", "tFilterRow": "filter", "tFilterRows": "filter",
    "Join": "join", "tJoin": "join", "Map": "join", "tMap": "join", "PyMap": "join",
    "SortRow": "sort", "tSortRow": "sort",
    "AggregateRow": "aggregate", "tAggregateRow": "aggregate",
    "UniqueRow": "dedupe", "tUniqRow": "dedupe", "tUniqueRow": "dedupe",
    "ConvertType": "derive", "tConvertType": "derive",
    "SchemaComplianceCheck": "validate", "tSchemaComplianceCheck": "validate",
    "PythonDataFrameComponent": "derive", "tPythonDataFrame": "derive",
}
_CODE_TYPES = {"PythonDataFrameComponent", "tPythonDataFrame", "PyMap"}


def _node_kind(comp_type: str) -> str:
    return _KIND_BY_TYPE.get(comp_type, "step")


def _find_code_field(config: Dict[str, Any]) -> Optional[str]:
    for key in ("python_code", "code", "script"):
        if isinstance(config.get(key), str) and config[key].strip():
            return key
    return None


# ---------------------------------------------------------------------------
# BRD door: explode (code)
# ---------------------------------------------------------------------------


class RealExplode(StageAdapter):
    key = "explode"

    async def run(self, ctx: StageContext) -> StageResult:
        brd_path = str(ctx.run.request.get("brd_path") or "").strip() or DEFAULT_BRD
        if not os.path.isfile(brd_path):
            # A named-but-missing path resolves against the vendored examples
            # (the demo affordance: the webview sends a display name).
            candidate = os.path.join(STUDIO_ROOT, "examples", os.path.basename(brd_path))
            if os.path.isfile(candidate):
                brd_path = candidate
            else:
                from .llm import LlmCallError
                raise LlmCallError("BrdNotFound", f"no BRD at {brd_path!r}")
        # Attachment contract (first live session, user decision): the
        # inventory carries the data files the human ATTACHED -- never
        # whatever shares a directory with the document.
        data_files = [str(a) for a in (ctx.run.request.get("attachments") or [])]
        inventory = explode(brd_path, ctx.bus.path("_explode"), data_files=data_files)
        inventory["brd"] = os.path.basename(brd_path)
        counts: Dict[str, int] = {}
        for h in inventory["handles"]:
            counts[h["type"]] = counts.get(h["type"], 0) + 1
        await ctx.write_artifact("exploder_inventory.json", inventory, kind="inventory")
        await ctx.write_artifact(
            "exploded.json",
            {"brd": inventory["brd"], "handles": len(inventory["handles"]),
             "tables": counts.get("table", 0),
             "prose_blocks": counts.get("prose", 0),
             "data_files": counts.get("sibling", 0) + counts.get("embed", 0),
             "images": counts.get("image", 0)},
            kind="exploded",
            note=(f"Explode · {inventory['brd']} → {len(inventory['handles'])} handles "
                  f"({counts.get('table', 0)} tables, {counts.get('sibling', 0)} data files)"),
        )
        return StageResult()


# ---------------------------------------------------------------------------
# BRD door: doc-normalizer (LLM, tier-2 port)
# ---------------------------------------------------------------------------


class RealDocNormalizer(StageAdapter):
    key = "doc_normalize"

    def __init__(self) -> None:
        self._passes = 0

    def _label(self, ctx: StageContext) -> str:
        """Scripted-beat label plan (rig-driven; live runs and the default
        demo walk always use the plain label)."""
        self._passes += 1
        shape_n = int(ctx.run.rig.get("shape_errors", 0) or 0)
        wants_nh = bool(ctx.run.rig.get("needs_human"))
        if self._passes <= shape_n:
            return "brd.normalize.shape"
        if wants_nh and self._passes == shape_n + 1:
            return "brd.normalize.gap"
        return "brd.normalize"

    def _tools(self, ctx: StageContext, inventory: Dict[str, Any]):
        async def read_handle(args: Dict[str, Any]) -> Dict[str, Any]:
            hid = str(args.get("id", ""))
            for h in inventory.get("handles", []):
                if h.get("id") != hid:
                    continue
                if h.get("type") == "prose":
                    return {"ok": True, "text": str(h.get("text", ""))[:_READ_CAP_BYTES]}
                if h.get("type") == "table":
                    cells = h.get("cells") or []
                    return {"ok": True, "columns": h.get("columns"),
                            "n_rows": h.get("n_rows"), "header": cells[0] if cells else []}
                path = h.get("path")
                if path and os.path.isfile(path):
                    with open(path, "r", encoding="utf-8", errors="replace") as fh:
                        return {"ok": True, "head": fh.read(_READ_CAP_BYTES)}
                return {"ok": False, "note": "handle has no readable file"}
            return {"ok": False, "note": f"no handle {hid!r} in the inventory"}

        decls = [ToolDecl(
            "read_handle",
            "Read one inventory handle for structure: prose text, a table's "
            "header, or the head of a jailed file (read-only, bounded)",
            {"type": "object", "properties": {"id": {"type": "string"}},
             "required": ["id"]},
        )]
        return {"read_handle": read_handle}, decls

    async def run(self, ctx: StageContext) -> StageResult:
        inventory = ctx.bus.read_json("exploder_inventory.json") or {}
        messages = normalizer_messages(
            inventory,
            feedback=ctx.repair,
            human_answers=ctx.run.nh_resolutions or None,
        )
        tools, decls = self._tools(ctx, inventory)
        parsed = await run_specialist(
            ctx, who="Doc Normalizer", label=self._label(ctx),
            stage_label="Intake", messages=messages, tools=tools, tool_decls=decls,
        )
        if parsed is None:  # journal-held stream: the bus owns the proposal
            parsed = ctx.bus.read_json("normalizer_proposal.json") or {}
        await ctx.write_artifact("normalizer_proposal.json", parsed, kind="proposal")
        return StageResult()


# ---------------------------------------------------------------------------
# BRD door: normalize_validate (code, fail-closed)
# ---------------------------------------------------------------------------


class RealNormalizeValidate(StageAdapter):
    key = "normalize_validate"

    @staticmethod
    def _nh_question(extraction: Dict[str, Any],
                     inventory: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        unaccounted = list(extraction.get("unaccounted") or [])
        unresolved = list(extraction.get("unresolved") or [])
        why = dict(extraction.get("unresolved_why") or {})
        type_of = {h.get("id"): h.get("type")
                   for h in (inventory or {}).get("handles", [])}
        # Unaccounted DATA handles (files/tables) are never boilerplate:
        # recommending "irrelevant" for them told a live run its own sample
        # CSVs were noise (first live session) -- data-looking handles get
        # the directed-guidance recommendation instead.
        unaccounted_data = [h for h in unaccounted
                            if type_of.get(h) in ("sibling", "embed", "table")]
        unaccounted_prose = [h for h in unaccounted if h not in unaccounted_data]
        bits = []
        if unaccounted_prose:
            bits.append("no disposition for " + ", ".join(unaccounted_prose))
        if unaccounted_data:
            bits.append(", ".join(unaccounted_data)
                        + " look like data files with no disposition — say where "
                          "each belongs (a sample source? the expected output?)")
        for name in unresolved:
            bits.append(f"{name} cannot be resolved ({why.get(name, 'no usable data handle')})")
        detail = "; ".join(bits) or "an unresolvable extraction state"
        if unresolved or unaccounted_data:
            # A data problem: the safe act is directed guidance, never
            # waving data away.
            options = [
                {"id": "guide", "label": "Tell the normalizer what to fix",
                 "kind": "choice", "recommended": True, "free": "required",
                 "why": "the reason above says exactly what does not line up"},
                {"id": "irrelevant", "label": "Treat them as irrelevant anyway",
                 "kind": "choice"},
            ]
        else:
            options = [
                {"id": "irrelevant", "label": "Mark them irrelevant boilerplate",
                 "kind": "choice", "recommended": True,
                 "why": "unaccounted parts are usually headers and prose framing"},
                {"id": "guide", "label": "Explain what they are", "kind": "choice",
                 "free": "required"},
            ]
        return {
            "source": "normalize_validate",
            "prompt": (f"Extraction cannot close the envelope: {detail}. "
                       "Tell the Doc Normalizer how to treat this."),
            "options": options,
            "free_prompt": "What these parts are / where the data lives…",
        }

    async def run(self, ctx: StageContext) -> StageResult:
        proposal = ctx.bus.read_json("normalizer_proposal.json") or {}
        inventory = ctx.bus.read_json("exploder_inventory.json") or {}
        status, payload = validate_proposal(proposal, inventory)
        if status == "shape_error":
            errors = payload.get("errors") or []
            await ctx.write_artifact("normalizer_feedback.json", payload, kind="feedback")
            first = errors[0] if errors else {}
            note = (f"{len(errors)} shape error(s) · "
                    f"{first.get('pointer', '$')}: {first.get('why', 'malformed proposal')}")
            return StageResult("shape_error", {"note": note, "errors": errors})
        if status == "needs_human":
            extraction = payload.get("extraction") or {}
            return StageResult("needs_human", {
                "question": self._nh_question(extraction, inventory),
                "extraction": extraction})
        # ok: the envelope closes -- extract + intake land on the bus.
        await ctx.write_artifact("extract_doc.json", payload, kind="extract")
        brd = str(inventory.get("brd")
                  or ctx.run.request.get("brd_name") or "requirements.docx")
        sources = [{"file": name if name.endswith(".csv") else f"{name}.csv",
                    "cols": len(cols)}
                   for name, cols in (payload.get("sources_schema") or {}).items()]
        data_present = any(rows for rows in (payload.get("sample_input") or {}).values())
        tier_hint = payload.get("tier")
        intake = {
            "door": "brd", "brd": brd, "sources": sources,
            "tables": sum(1 for h in inventory.get("handles", []) if h.get("type") == "table"),
            "attachments": list(ctx.run.request.get("attachments") or []),
            "data_present": data_present, "tier_hint": tier_hint,
        }
        note = (f"Doc Normalizer · proposal validated clean — {len(sources)} sources, "
                f"tier {tier_hint}")
        await ctx.write_artifact(
            "intake.json", intake, kind="intake",
            fields={"sources": sources, "door": "brd"}, note=note)
        return StageResult(data={"data_present": data_present, "note": note})


# ---------------------------------------------------------------------------
# Typed door: intake builder (code)
# ---------------------------------------------------------------------------


class RealIntakeBuilder(StageAdapter):
    key = "intake_build"

    async def run(self, ctx: StageContext) -> StageResult:
        await ctx.sleep(0.4)
        attachments = [str(a) for a in (ctx.run.request.get("attachments") or [])]
        sources: List[Dict[str, Any]] = []
        for path in attachments:
            entry: Dict[str, Any] = {"file": os.path.basename(path)}
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    header = fh.readline().strip()
                if header:
                    entry["cols"] = header.count(",") + 1
            except OSError:
                pass  # a path promised but not present yet: named, not shaped
            sources.append(entry)
        intake = {
            "door": "typed",
            "request_text": str(ctx.run.request.get("text") or ""),
            "job": ctx.run.job,
            "sources": sources,
            "attachments": attachments,
            "data_present": bool(attachments),
        }
        note = ("Intake · request + " + str(len(attachments)) + " data file(s)"
                if attachments else "Intake · request — no data attached")
        await ctx.write_artifact(
            "intake.json", intake, kind="intake",
            fields={"sources": sources, "door": "typed"}, note=note)
        return StageResult(data={"data_present": bool(attachments), "note": note})


# ---------------------------------------------------------------------------
# Interpreter (LLM, tier-2 port -- both doors, elicitation, revisions)
# ---------------------------------------------------------------------------


class RealInterpreter(StageAdapter):
    key = "interpret"

    @staticmethod
    def _label(mode: str, door: str) -> str:
        if mode == "refind":
            # Door-split label: the two doors' fold-in stories diverge (the
            # scripted typed round 2 re-finds a gap; the BRD round drains).
            return "brd.refind" if door == "brd" else "interp.refind"
        return {"read": "interp.read", "revise": "interp.revise"}[mode]

    def _tools(self, ctx: StageContext, extract: Optional[Dict[str, Any]]):
        async def read_data_file(args: Dict[str, Any]) -> Dict[str, Any]:
            name = str(args.get("source", ""))
            rows = ((extract or {}).get("sample_input") or {}).get(name)
            if rows is None:
                rows = ((extract or {}).get("expected_output") or {}).get(name)
            if rows is not None:
                return {"ok": True, "rows": rows[:_SAMPLE_ROW_CAP], "n_total": len(rows)}
            for path in ctx.run.request.get("attachments") or []:
                if os.path.basename(str(path)) in (name, f"{name}.csv"):
                    try:
                        with open(path, "r", encoding="utf-8", errors="replace") as fh:
                            return {"ok": True, "head": fh.read(_READ_CAP_BYTES)}
                    except OSError as e:
                        return {"ok": False, "note": f"unreadable: {e}"}
            return {"ok": False, "note": f"no data for source {name!r}"}

        decls = [ToolDecl(
            "read_data_file",
            "Read a source's merged sample rows (or an attachment's head) "
            "beyond the bounded in-prompt rows (read-only)",
            {"type": "object", "properties": {"source": {"type": "string"}},
             "required": ["source"]},
        )]
        return {"read_data_file": read_data_file}, decls

    @staticmethod
    def _display_sources(schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{"file": name if name.endswith(".csv") else f"{name}.csv",
                 "cols": len(cols or [])}
                for name, cols in (schema or {}).items()]

    @staticmethod
    def _display_rules(rules: List[Dict[str, Any]], gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        gap_by_rule = {g.get("rule"): g.get("id") for g in gaps or []}
        out = []
        for r in rules or []:
            row = dict(r)
            gap = gap_by_rule.get(r.get("id"))
            if gap:
                row["gap"] = gap
            if r.get("kind") == "derive":
                row["code"] = True
            out.append(row)
        return out

    async def run(self, ctx: StageContext) -> StageResult:
        mode = ctx.run.interpret_mode or "read"
        intake = ctx.bus.read_json("intake.json") or {}
        extract = ctx.bus.read_json("extract_doc.json")
        prior = ctx.bus.read_json("requirement_spec.json")
        messages = interpreter_messages(
            {k: v for k, v in intake.items()},
            extract,
            resolutions=ctx.run.gap_resolutions or None,
            prior_spec=prior,
            feedback=ctx.run.feedback,
            mode=mode,
        )
        tools, decls = self._tools(ctx, extract)
        parsed = await run_specialist(
            ctx, who="Interpreter", label=self._label(mode, ctx.run.door),
            stage_label="Interpret", messages=messages, tools=tools, tool_decls=decls,
        )
        if parsed is None:  # journal-held stream: the bus owns the spec
            spec = ctx.bus.read_json("requirement_spec.json") or {}
            return StageResult(data={"gaps": list(spec.get("gaps") or []),
                                     "what_changed": spec.get("what_changed")})
        gaps = list(parsed.get("gaps") or [])
        # BRD door: the source schema is the validator's exact-merged truth --
        # a deterministic carry-through the model cannot rewrite (the live
        # probe showed a model collapsing three sources into one output-shaped
        # schema; same principle as derived_facts/tier below). The typed door
        # has no extract, so there the model's proposed schema stands.
        if extract and extract.get("sources_schema"):
            schema = extract.get("sources_schema") or {}
        else:
            schema = parsed.get("schema") or {}
        rules = list(parsed.get("rules") or [])
        spec = {
            "draft": ctx.run.draft,
            "schema": schema,
            "rules": self._display_rules(rules, gaps),
            "outputs": parsed.get("outputs") or [],
            "gaps": gaps,
            "gap_resolutions": ctx.run.gap_resolutions,
            "what_changed": parsed.get("what_changed"),
            "notes": parsed.get("notes"),
            "sources": self._display_sources(schema),
            # Deterministic carry-through (never model-retyped):
            "derived_facts": (extract or {}).get("derived_facts"),
            "tier": (extract or {}).get("tier"),
            "provenance": (extract or {}).get("provenance"),
        }
        await ctx.write_artifact(
            "requirement_spec.json", spec, kind="spec",
            fields={"draft": ctx.run.draft, "sources": spec["sources"],
                    "rules": spec["rules"], "gaps": gaps,
                    "gap_resolutions": ctx.run.gap_resolutions,
                    "what_changed": spec.get("what_changed")},
            note=f"Interpreter · requirement_spec draft {ctx.run.draft}",
        )
        return StageResult(data={"gaps": gaps, "what_changed": spec.get("what_changed")})


# ---------------------------------------------------------------------------
# Flow Designer (LLM, tier-1 port)
# ---------------------------------------------------------------------------


class RealFlowDesigner(StageAdapter):
    key = "design"

    async def run(self, ctx: StageContext) -> StageResult:
        spec = ctx.bus.read_json("requirement_spec.json") or {}
        # Rig knob (smoke's, fixture-label selector only): a permanently
        # malformed designer forces the bounded-retry exhaustion ticket 18's
        # escalation path demonstrates. Live runs play the plain label.
        malformed = bool(ctx.run.rig.get("malformed_design"))
        parsed = await run_specialist(
            ctx, who="Flow Designer",
            label=("flow.design.bad" if malformed
                   else "flow.repair" if ctx.repair else "flow.design"),
            stage_label="Design",
            messages=designer_messages(spec, repair=ctx.repair),
        )
        if parsed is None:
            parsed = ctx.bus.read_json("flow.json") or {}
        components = list(parsed.get("components") or [])
        # One vocabulary on the canvas and in job.json (ticket 20): any
        # Talend alias the model authored lands as the schema's canonical
        # type. The engine registers both names; the studio shows one.
        for c in components:
            if c.get("type"):
                c["type"] = knowledge.canonical_type(str(c["type"]))
        edges = [list(e) for e in (parsed.get("edges") or [])]
        nodes = [{
            "id": c.get("id"),
            "kind": _node_kind(str(c.get("type", ""))),
            "label": c.get("label") or c.get("id"),
            "sub": c.get("type"),
            **({"code": True} if str(c.get("type")) in _CODE_TYPES else {}),
        } for c in components]
        flow = {"pattern": parsed.get("pattern"), "components": components,
                "edges": edges, "nodes": nodes}
        await ctx.write_artifact(
            "flow.json", flow, kind="flow",
            fields={"nodes": nodes, "edges": edges, "pattern": parsed.get("pattern")},
            note=f"Flow Designer · {len(components)} components, {len(edges)} flows",
        )
        return StageResult(data={"components": len(components)})


# ---------------------------------------------------------------------------
# Configurator (LLM, tier-1 port; vendored validate_config as the inner loop)
# ---------------------------------------------------------------------------


class RealConfigurator(StageAdapter):
    key = "configure"

    def _tools(self, ctx: StageContext, stats: Dict[str, Any]):
        async def tool_validate(args: Dict[str, Any]) -> Dict[str, Any]:
            comp_type = str(args.get("type", ""))
            config = args.get("config")
            comp_id = args.get("id")
            if not isinstance(config, dict):
                return {"ok": False, "valid": False,
                        "errors": ["config must be a JSON object"], "curated": False}
            errors = validate_config(comp_type, config)
            from .vendored.component_schema import is_curated
            curated = is_curated(comp_type)
            stats["calls"] += 1
            if errors:
                stats["error_rounds"] += 1
            if comp_id:
                await ctx.progress(str(comp_id), "configured" if not errors else "active")
            return {"ok": True, "valid": not errors, "errors": errors, "curated": curated}

        decls = [ToolDecl(
            "validate_config",
            "Validate one component's config dict against its curated schema "
            "(strict + enum-backed for curated types; advisory for the rest)",
            {"type": "object", "properties": {
                "type": {"type": "string"},
                "config": {"type": "object"},
                "id": {"type": "string"},
            }, "required": ["type", "config"]},
        )]
        return {"validate_config": tool_validate}, decls

    @staticmethod
    def _cell_meta(components: List[Dict[str, Any]],
                   nodes_by_id: Dict[str, Dict[str, Any]],
                   validated_clean: bool) -> Dict[str, Any]:
        meta: Dict[str, Any] = {}
        for comp in components:
            config = comp.get("config") or {}
            field = _find_code_field(config)
            if not field:
                continue
            cid = str(comp.get("id"))
            out_cols = len(((comp.get("schema") or {}).get("output")) or [])
            meta[cid] = {
                "id": f"{cid}_cell",
                "node_id": cid,
                "component": comp.get("type"),
                "author": "Configurator",
                "validator": (f"validator clean · output schema {out_cols} columns"
                              if validated_clean else "validator pending"),
            }
        return meta

    @staticmethod
    def _preserve_gated_cells(components: List[Dict[str, Any]],
                              prior: Dict[str, Any]) -> None:
        """Chassis invariant on a repair pass: an approved code cell only
        changes through the code gate (hash-based re-raise), so a repair
        keeps every prior python-code field byte-for-byte."""
        prior_by_id = {str(c.get("id")): c for c in prior.get("components") or []}
        for comp in components:
            before = prior_by_id.get(str(comp.get("id")))
            if not before:
                continue
            field = _find_code_field(before.get("config") or {})
            if field and isinstance(comp.get("config"), dict):
                comp["config"][field] = (before.get("config") or {}).get(field)

    async def run(self, ctx: StageContext) -> StageResult:
        plan = ctx.bus.read_json("flow.json") or {}
        spec = ctx.bus.read_json("requirement_spec.json") or {}
        extract = ctx.bus.read_json("extract_doc.json") or {}
        flow_types = [str(c.get("type")) for c in plan.get("components") or []]
        nodes_by_id = {str(n.get("id")): n for n in plan.get("nodes") or []}
        # A code-gate reject (ticket 13's code door) is the only iteration>1
        # path that rewrites the cell; a spec-door forward re-run reconfigures
        # in full instead (config.main again). On a repair pass the scripted
        # label follows the diagnosis that produced it (a misdiagnosis plays
        # the faithful-but-wrong fixture; live runs apply the real feedback).
        revise = (ctx.iteration > 1 and not ctx.repair
                  and bool(ctx.run.rig.get("_cell_revised")))
        label = ("config.repair.miss"
                 if ctx.repair and ctx.run.rig.get("_last_diag") == "miss"
                 else "config.repair" if ctx.repair
                 else "config.revise" if revise else "config.main")
        stats = {"calls": 0, "error_rounds": 0}
        tools, decls = self._tools(ctx, stats)
        parsed = await run_specialist(
            ctx, who="Configurator", label=label, stage_label="Configure",
            messages=configurator_messages(
                plan, spec, extract.get("provenance"),
                repair=ctx.repair,
                revise_note=ctx.run.feedback if revise else "",
                flow_types=flow_types,
            ),
            tools=tools, tool_decls=decls,
        )
        if parsed is None:
            parsed = {"components": (ctx.bus.read_json("config.json") or {}).get("components", [])}
        components = list(parsed.get("components") or [])
        for c in components:
            if c.get("type"):
                c["type"] = knowledge.canonical_type(str(c["type"]))
        if ctx.repair:
            self._preserve_gated_cells(components, ctx.bus.read_json("config.json") or {})
        if not ctx.repair:
            # Completion sweep: every configured node lights up (real state --
            # the draft holds them all), whatever the fixture's tool-call count.
            for comp in components:
                await ctx.progress(str(comp.get("id")), "configured")
                await ctx.sleep(0.12)
            attempts = 1 + (1 if stats["error_rounds"] else 0)
            note = ("validate loop · " +
                    (f"{stats['error_rounds']} error round(s) fixed · final: clean"
                     if stats["error_rounds"] else
                     f"{stats['calls']} check(s) · clean on run 1")
                    if stats["calls"] else "validate loop · draft revalidated clean")
            await ctx.loop_attempt(attempts, 3, note)
        config = {
            "components": components,
            "cell_meta": self._cell_meta(components, nodes_by_id, validated_clean=True),
        }
        if ctx.repair:
            config["applied_fix"] = ctx.repair.get("fix")
        await ctx.write_artifact("config.json", config, kind="config")
        n_planned = len(plan.get("components") or []) or len(components)
        note = (f"Configurator · revision applied — validate loop clean" if revise
                else f"Configurator · {len(components)}/{n_planned} configured — "
                     + ("validate loop clean on attempt 2" if stats["error_rounds"]
                        else "validate loop clean"))
        return StageResult(data={"repaired": bool(ctx.repair), "note": note,
                                 "validate_calls": stats["calls"]})


# ---------------------------------------------------------------------------
# Assembler (LLM, tier-1 port)
# ---------------------------------------------------------------------------


class RealAssembler(StageAdapter):
    key = "assemble"

    @staticmethod
    def _enforce_draft_configs(job: Dict[str, Any], draft: Dict[str, Any]) -> None:
        """Structural enforcement of the assembler contract: every component's
        ``config`` AND ``schema.output`` are byte-for-byte the draft's -- the
        assembler wires, it never edits what the Configurator authored. The
        prompt always said schema.output is the Configurator's; ticket 19
        extended the enforcement to it after the repair loop showed a
        schema-typed fix could be silently dropped in re-wiring. Each
        consumer's ``schema.input`` then rebuilds from its DRIVER producer's
        enforced output (the first ``inputs`` entry is the driver flow). The
        terminal FileOutput rename maps by elimination."""
        draft_comps = {str(c.get("id")): c for c in draft.get("components") or []}
        unclaimed = dict(draft_comps)
        matched: Dict[str, Dict[str, Any]] = {}
        for comp in job.get("components") or []:
            cid = str(comp.get("id"))
            if cid in unclaimed:
                matched[cid] = unclaimed.pop(cid)
        leftovers = list(unclaimed.values())
        for comp in job.get("components") or []:
            cid = str(comp.get("id"))
            if cid in matched:
                continue
            match = next((d for d in leftovers
                          if str(d.get("type")) == str(comp.get("type"))), None)
            if match is not None:
                matched[cid] = match
                leftovers.remove(match)
        for comp in job.get("components") or []:
            d = matched.get(str(comp.get("id")))
            if d is None:
                continue
            comp["config"] = d.get("config")
            schema = comp.get("schema")
            if isinstance(schema, dict):
                schema["output"] = copy.deepcopy(
                    (d.get("schema") or {}).get("output") or [])
        by_id = {str(c.get("id")): c for c in job.get("components") or []}
        producer_of = {str(f.get("name")): str(f.get("from"))
                       for f in job.get("flows") or []}
        for comp in job.get("components") or []:
            schema = comp.get("schema")
            inputs = [str(n) for n in comp.get("inputs") or []]
            if not isinstance(schema, dict) or not inputs:
                continue
            producer = by_id.get(producer_of.get(inputs[0], ""))
            if producer is not None:
                schema["input"] = copy.deepcopy(
                    (producer.get("schema") or {}).get("output") or [])

    async def run(self, ctx: StageContext) -> StageResult:
        draft = ctx.bus.read_json("config.json") or {}
        plan = ctx.bus.read_json("flow.json") or {}
        spec = ctx.bus.read_json("requirement_spec.json") or {}
        flow_types = [str(c.get("type")) for c in plan.get("components") or []]
        parsed = await run_specialist(
            ctx, who="Assembler",
            label="assemble.repair" if ctx.repair else "assemble.run",
            stage_label="Assemble",
            messages=assembler_messages(draft, plan, spec, repair=ctx.repair,
                                        flow_types=flow_types),
        )
        if parsed is None:
            parsed = ctx.bus.read_json("job.json") or {}
        job = {k: parsed[k] for k in ("components", "flows", "triggers", "java_config")
               if k in parsed}
        job.setdefault("components", [])
        job.setdefault("flows", [])
        job.setdefault("triggers", [])
        for comp in job["components"]:
            if comp.get("type"):
                comp["type"] = knowledge.canonical_type(str(comp["type"]))
        self._enforce_draft_configs(job, draft)
        if ctx.repair:
            await ctx.write_artifact("job.json", job, kind="job")
            return StageResult(data={"repaired": True})
        await ctx.write_artifact(
            "job.json", job, kind="job",
            fields={"components": len(job["components"]), "flows": len(job["flows"])},
            note=(f"Assembler · job assembled — {len(job['components'])} components, "
                  f"{len(job['flows'])} flows"),
        )
        return StageResult()


# ---------------------------------------------------------------------------
# Materializer (code, ticket 19 -- runs post-sign-off, freezes the tier)
# ---------------------------------------------------------------------------


class RealMaterializer(StageAdapter):
    """Writes input files + golden/ from either door's data via the vendored
    materialize_golden, and computes the rung-aware tier the conductor
    freezes (ticket 04: one shared computation for both doors; transcribed
    image/prose data never earns verified -- the BRD door's tier arrives
    rung-graded from the validator's extract, and the typed door's
    attachments are all rung 1 by construction, so its tier reduces to
    verified/smoke/build by what the human actually attached)."""

    key = "materialize"

    @staticmethod
    def _read_attachment(path: str):
        """(rows, delimiter) for one attached CSV; (None, None) when
        unreadable or empty -- a promised-but-absent path degrades the tier
        honestly instead of crashing the run."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
                sample = fh.readline()
                if not sample.strip():
                    return None, None
                try:
                    sep = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
                except csv.Error:
                    sep = ","
                fh.seek(0)
                rows = [dict(r) for r in csv.DictReader(fh, delimiter=sep)]
            return rows, sep
        except OSError:
            return None, None

    def _typed_extract(self, ctx: StageContext) -> Dict[str, Any]:
        """Synthesize the extract shape from the typed door's attachments:
        an attachment whose stem is ``<output>`` or ``<output>_expected``
        (per the spec's outputs) becomes that output's answer key; every
        other readable CSV is a sample source named by its stem. Mechanical
        mapping, never an editorial pick."""
        spec = ctx.bus.read_json("requirement_spec.json") or {}
        output_names = [str(o.get("name")) for o in (spec.get("outputs") or [])
                        if o.get("name")]
        extract: Dict[str, Any] = {
            "sources_schema": spec.get("schema") or {},
            "sample_input": {}, "expected_output": {},
            "output_keys": {}, "provenance": {}, "tier": "build",
        }
        skipped: List[str] = []
        for path in [str(a) for a in ctx.run.request.get("attachments") or []]:
            base = os.path.basename(path)
            stem = base[:-4] if base.lower().endswith(".csv") else base
            rows, sep = self._read_attachment(path)
            if rows is None:
                skipped.append(base)
                continue
            prov = {"rung": "1", "handle": f"attach:{base}", "delimiter": sep}
            target = next((o for o in output_names
                           if stem in (o, f"{o}_expected")), None)
            if target is not None:
                extract["expected_output"][target] = rows
                extract["provenance"][target] = prov
                header = list(rows[0].keys()) if rows else []
                unique_first = bool(header) and len(
                    {r.get(header[0]) for r in rows}) == len(rows)
                extract["output_keys"][target] = [header[0]] if unique_first else []
            else:
                extract["sample_input"][stem] = rows
                extract["provenance"][stem] = prov
        graded = [n for n, r in extract["expected_output"].items() if r]
        if extract["sample_input"]:
            extract["tier"] = "verified" if graded else "smoke"
        if skipped:
            extract["skipped_attachments"] = skipped
        return extract

    async def run(self, ctx: StageContext) -> StageResult:
        await ctx.sleep(0.4)
        if ctx.run.door == "brd":
            extract = ctx.bus.read_json("extract_doc.json") or {}
        else:
            extract = self._typed_extract(ctx)
            # One downstream contract for both doors: the typed door's
            # synthesized extract lands under the same canonical name, so
            # the configurator's delimiter reads and the diagnostician's
            # provenance reads never fork on the door.
            await ctx.write_artifact("extract_doc.json", extract, kind="extract")
        try:
            result = materialize_golden(extract, ctx.bus.run_dir)
        except (OSError, ValueError) as e:
            raise LlmCallError("MaterializeFailed", str(e))
        outputs = dict(result.get("outputs") or {})
        graded = [n for n, s in outputs.items() if s.get("graded")]
        tier = str(result.get("tier") or "build")
        n_inputs = len(result.get("inputs") or [])
        if graded:
            note = (f"Materializer · {n_inputs} input file(s), {len(graded)} golden "
                    f"output(s) — tier {tier}")
        elif n_inputs:
            note = (f"Materializer · {n_inputs} input file(s), no gradable golden "
                    f"— tier {tier}")
        else:
            note = f"Materializer · no data to grade against — tier {tier}"
        # Event-only: the vendored code already wrote the files (data files
        # are the sanctioned direct writes -- 04's first deterministic line).
        await ctx.write_artifact(
            "golden/manifest.json", None, kind="golden",
            fields={"inputs": result.get("inputs") or [], "outputs": outputs,
                    "tier": tier},
            note=note)
        return StageResult(data={"tier": tier, "inputs": result.get("inputs"),
                                 "outputs": outputs})


# ---------------------------------------------------------------------------
# Test runner (code, ticket 19 -- the harness as a core subprocess)
# ---------------------------------------------------------------------------


class RealTestRunner(StageAdapter):
    """Runs the vendored run_and_validate CLI as a SUBPROCESS of the core
    against the read-only engine (ticket 04's execution isolation: job code
    cells are RCE-capable and must never be able to take the core down).
    Output captured beside the report; verdict facts are the report's,
    verbatim."""

    key = "test_run"

    @staticmethod
    def _fail_summary(report: Dict[str, Any]) -> str:
        if report.get("error"):
            return str(report["error"])[:140]
        bits: List[str] = []
        for name, d in (report.get("outputs") or {}).items():
            if d.get("equal"):
                continue
            if d.get("reason"):
                bits.append(f"{name}: {d['reason']}")
                continue
            counts = [(d.get("value_mismatch"), "value mismatch(es)"),
                      (d.get("missing"), "missing row(s)"),
                      (d.get("unexpected"), "unexpected row(s)"),
                      (len(d.get("unexpected_columns") or []), "extra column(s)"),
                      (len(d.get("missing_columns") or []), "missing column(s)")]
            inner = ", ".join(f"{n} {label}" for n, label in counts if n)
            cols = sorted({c for ex in ((d.get("examples") or {}).get("value_mismatch") or [])
                           for c in (ex.get("columns") or {})})
            if cols:
                inner += " on " + "/".join(cols)
            bits.append(f"{name}: {inner or 'differs'}")
        if not bits:
            reasons = report.get("reasons") or []
            if reasons:
                bits.append(str(reasons[0])[:140])
        return "; ".join(bits[:2]) or "output mismatched the golden"

    async def run(self, ctx: StageContext) -> StageResult:
        k = int(ctx.run.rig.get("_run_index", 0)) + 1
        ctx.run.rig["_run_index"] = k
        tier = ctx.run.tier or "build"
        rel = f"runs/run-{k}/test_report.json"
        report_path = ctx.bus.path(rel)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        argv = [sys.executable, str(_HARNESS_CLI),
                "--job", str(ctx.bus.path("job.json")), "--out", str(report_path)]
        argv += (["--smoke"] if tier == "smoke"
                 else ["--golden-dir", str(ctx.bus.path("golden"))])
        proc = await asyncio.create_subprocess_exec(
            *argv, cwd=str(_REPO_ROOT),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout = stderr = b""
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=HARNESS_TIMEOUT_S)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            report: Optional[Dict[str, Any]] = {
                "passed": False,
                "error": f"harness timed out after {HARNESS_TIMEOUT_S}s"}
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        else:
            report = None
            if report_path.is_file():
                try:
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                except ValueError:
                    report = None
            if report is None:
                tail = (stderr or stdout or b"").decode("utf-8", "replace")[-2000:]
                report = {"passed": False,
                          "error": f"harness exited {proc.returncode} with no report",
                          "output_tail": tail}
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        # The captured child output lands beside the report (04: captured,
        # and the diagnostician can read it through the work dir).
        (report_path.parent / "harness_output.txt").write_text(
            "--- stdout (tail) ---\n"
            + (stdout or b"").decode("utf-8", "replace")[-10000:]
            + "\n--- stderr (tail) ---\n"
            + (stderr or b"").decode("utf-8", "replace")[-10000:]
            + "\n",
            encoding="utf-8")
        clean = (bool(report.get("ran_clean")) if tier == "smoke"
                 else report.get("passed") is True)
        graded = report.get("graded")
        if clean:
            note = (f"Test Runner · run {k} — ran clean (smoke tier, nothing graded)"
                    if tier == "smoke" else
                    f"Test Runner · run {k} — output matches your golden "
                    f"({graded}/{report.get('total', graded)} outputs graded)")
        else:
            note = f"Test Runner · run {k} — {self._fail_summary(report)}"
        await ctx.write_artifact(
            rel, None, kind="test_run",
            fields={"run": k, "passed": report.get("passed"), "clean": clean,
                    "graded": graded, "tier": tier})
        # Event-only marker: runs/run-<k> is a directory on the bus (the
        # report above lives inside it), so no payload rides this name.
        await ctx.write_artifact(f"runs/run-{k}", None, kind="test_run", note=note)
        return StageResult(data={"clean": clean, "run_index": k, "report": report})


# ---------------------------------------------------------------------------
# Diagnostician (LLM, tier 3 -- ticket 04's value-visible rebuild)
# ---------------------------------------------------------------------------


class RealDiagnostician(StageAdapter):
    """Reads the enriched report plus the work dir and writes feedback.json
    naming the one owner. Holds the pipeline's ONLY engine-source mount and
    config-surfaces tool (ticket 11: tool-registry absence enforces the ban
    for every other stage). The conductor enforces the owner enum
    fail-closed; the artifact records what the model actually said."""

    key = "diagnose"

    def _label(self, ctx: StageContext) -> str:
        """Scripted-beat label plan (rig-driven; live runs and the default
        demo walk always play the plain label)."""
        rig = ctx.run.rig
        if rig.get("owner_human") and not rig.get("_owner_human_done"):
            rig["_owner_human_done"] = True
            rig["_last_diag"] = "human"
            return "diag.run.human"
        misses = int(rig.get("diag_misses", 0) or 0)
        done = int(rig.get("_diag_misses_done", 0) or 0)
        if done < misses:
            rig["_diag_misses_done"] = done + 1
            rig["_last_diag"] = "miss"
            return "diag.run.miss"
        rig["_last_diag"] = "fix"
        return "diag.run.after" if misses else "diag.run"

    def _tools(self, ctx: StageContext):
        run_root = Path(os.path.realpath(ctx.bus.run_dir))

        async def list_work_files(_args: Dict[str, Any]) -> Dict[str, Any]:
            out = []
            for p in sorted(run_root.rglob("*")):
                if not p.is_file():
                    continue
                rel = p.relative_to(run_root).as_posix()
                if rel == "ui_journal.jsonl":
                    continue
                out.append({"path": rel, "bytes": p.stat().st_size})
                if len(out) >= 200:
                    break
            return {"ok": True, "files": out}

        async def read_work_file(args: Dict[str, Any]) -> Dict[str, Any]:
            rel = str(args.get("path", ""))
            target = Path(os.path.realpath(run_root / rel))
            if not target.is_relative_to(run_root):
                return {"ok": False, "note": "path escapes the work dir"}
            if not target.is_file():
                return {"ok": False, "note": f"no file at {rel!r}"}
            data = target.read_text(encoding="utf-8", errors="replace")
            return {"ok": True, "text": data[:_WORK_READ_CAP],
                    "truncated": len(data) > _WORK_READ_CAP}

        async def read_engine_source(args: Dict[str, Any]) -> Dict[str, Any]:
            rel = str(args.get("path", "")).removeprefix("src/v1/")
            root = Path(os.path.realpath(_ENGINE_SRC_ROOT))
            target = Path(os.path.realpath(root / rel))
            if not target.is_relative_to(root):
                return {"ok": False, "note": "path escapes src/v1 (read-only jail)"}
            if not target.is_file():
                return {"ok": False, "note": f"no engine source at src/v1/{rel}"}
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
            start = max(1, int(args.get("start", 1) or 1))
            end = int(args.get("end", 0) or 0) or (start + _SOURCE_LINE_CAP - 1)
            end = min(len(lines), end, start + _SOURCE_LINE_CAP - 1)
            body = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))
            return {"ok": True, "path": f"src/v1/{rel}", "start": start, "end": end,
                    "total_lines": len(lines), "text": body}

        async def read_config_surfaces(args: Dict[str, Any]) -> Dict[str, Any]:
            surfaces = knowledge.RENDER_DIR / "config-surfaces.md"
            if not surfaces.is_file():
                return {"ok": False, "note": "config-surfaces.md is not rendered"}
            text = surfaces.read_text(encoding="utf-8")
            component = str(args.get("component", "") or "").strip()
            if component:
                sections = text.split("\n## ")
                hits = [s for s in sections[1:]
                        if component.lower() in s.splitlines()[0].lower()]
                if not hits:
                    return {"ok": False,
                            "note": f"no config-surfaces section matches {component!r}"}
                return {"ok": True, "text": ("## " + hits[0])[:_WORK_READ_CAP]}
            return {"ok": True, "text": text[:2 * _WORK_READ_CAP],
                    "truncated": len(text) > 2 * _WORK_READ_CAP}

        decls = [
            ToolDecl(
                "list_work_files",
                "List this run's work-dir files (relative path + size; read-only)",
                {"type": "object", "properties": {}},
            ),
            ToolDecl(
                "read_work_file",
                "Read one work-dir file's head (8KB cap; read-only, jailed to "
                "the run dir): inputs, goldens, actual outputs, reports, artifacts",
                {"type": "object", "properties": {"path": {"type": "string"}},
                 "required": ["path"]},
            ),
            ToolDecl(
                "read_engine_source",
                "Read engine source under src/v1 (read-only; ~120-line window). "
                "Use the landmine code anchors below as entry points",
                {"type": "object", "properties": {
                    "path": {"type": "string"},
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                }, "required": ["path"]},
            ),
            ToolDecl(
                "read_config_surfaces",
                "The code-verified component config-surfaces reference with "
                "file:line anchors (whole file, or one component's section)",
                {"type": "object",
                 "properties": {"component": {"type": "string"}}},
            ),
        ]
        return {"list_work_files": list_work_files,
                "read_work_file": read_work_file,
                "read_engine_source": read_engine_source,
                "read_config_surfaces": read_config_surfaces}, decls

    async def run(self, ctx: StageContext) -> StageResult:
        k = int(ctx.run.rig.get("_run_index", 0))
        report = ctx.bus.read_json(f"runs/run-{k}/test_report.json") or {}
        spec = ctx.bus.read_json("requirement_spec.json") or {}
        config = ctx.bus.read_json("config.json") or {}
        plan = ctx.bus.read_json("flow.json") or {}
        flow_types = [str(c.get("type")) for c in plan.get("components") or []]
        messages = diagnostician_messages(
            report, spec, config, plan,
            run_index=k, tier=ctx.run.tier, flow_types=flow_types)
        tools, decls = self._tools(ctx)
        parsed = await run_specialist(
            ctx, who="Diagnostician", label=self._label(ctx), stage_label="Verify",
            messages=messages, tools=tools, tool_decls=decls)
        if parsed is None:  # journal-held stream: the bus owns the diagnosis
            parsed = ctx.bus.read_json("feedback.json") or {}
        owner = str(parsed.get("owner") or "")
        note = f"Diagnostician · owner: {owner.capitalize() or '?'}"
        if owner == "human":
            note += " — the call is yours"
        elif parsed.get("fix"):
            note += f" — fix: {str(parsed['fix'])[:70]}"
        await ctx.write_artifact(
            "feedback.json", parsed, kind="diagnosis",
            fields={"owner": owner.capitalize(), "fix": parsed.get("fix"),
                    "suspect": parsed.get("suspect"),
                    "evidence": parsed.get("evidence")},
            note=note)
        return StageResult(data={"feedback": parsed})


# ---------------------------------------------------------------------------
# The slot map: every slot real (tickets 17 + 19)
# ---------------------------------------------------------------------------


def build_stages() -> Dict[str, StageAdapter]:
    adapters = [
        RealExplode(), RealDocNormalizer(), RealNormalizeValidate(),
        RealIntakeBuilder(), RealInterpreter(), RealFlowDesigner(),
        RealConfigurator(), RealAssembler(),
        RealMaterializer(), RealTestRunner(), RealDiagnostician(),
    ]
    return {s.key: s for s in adapters}
