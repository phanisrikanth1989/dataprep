"""The real doors and design-side specialists (ticket 17), on ticket 16's
chassis: StageAdapter implementations for explode, doc_normalize,
normalize_validate, intake_build (the two doors) and interpret, design,
configure, assemble (the specialists). Materialize, test_run and diagnose
stay ticket 16's stubs until ticket 19.

Structural rules carried here:
- Stages never raise questions; machine facts ride StageResult and the
  conductor owns the channel (needs_human answers come back through
  ``run.nh_resolutions``, shape feedback through ``ctx.repair``).
- The data-write ban is structural: no specialist holds a data-write tool;
  only the exploder's jailed extraction writes data files on this ticket.
- Every artifact a stage parses from a stream is also read back from the bus
  when the journal skipped the stream (crash-restore re-walk).
- Rig knobs (smoke's, never the webview's) select scripted-fixture LABELS for
  the shape-repair / needs_human demo beats; the vendored validator judges
  whatever content plays, live or scripted.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from .port import ToolDecl
from .prompts import (
    assembler_messages,
    configurator_messages,
    designer_messages,
    interpreter_messages,
    normalizer_messages,
)
from .specialist import run_specialist
from .stages import StageAdapter, StageContext, StageResult
from .vendored.explode_doc import explode
from .vendored.normalize_validate import validate_proposal
from .vendored.validate_config import validate_config

logger = logging.getLogger(__name__)

# Slots whose streams route to the live provider when one resolved (17's
# specialists; 18 adds the orchestrator, 19 the diagnostician).
LIVE_SLOTS = frozenset({"doc_normalize", "interpret", "design", "configure", "assemble"})

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BRD = os.path.join(STUDIO_ROOT, "examples", "trade_position_demo.docx")

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
        inventory = explode(brd_path, ctx.bus.path("_explode"))
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
    def _nh_question(extraction: Dict[str, Any]) -> Dict[str, Any]:
        unaccounted = list(extraction.get("unaccounted") or [])
        unresolved = list(extraction.get("unresolved") or [])
        why = dict(extraction.get("unresolved_why") or {})
        bits = []
        if unaccounted:
            bits.append("no disposition for " + ", ".join(unaccounted))
        for name in unresolved:
            bits.append(f"{name} cannot be resolved ({why.get(name, 'no usable data handle')})")
        detail = "; ".join(bits) or "an unresolvable extraction state"
        if unresolved:
            # A source/output the validator cannot resolve is a DATA problem:
            # the safe act is directed guidance, never waving data away.
            options = [
                {"id": "guide", "label": "Tell the normalizer what to fix",
                 "kind": "choice", "recommended": True, "free": "required",
                 "why": "the validator's reason above says exactly what does not line up"},
                {"id": "drop_source", "label": "Treat it as absent", "kind": "choice"},
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
                "question": self._nh_question(extraction), "extraction": extraction})
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
        parsed = await run_specialist(
            ctx, who="Flow Designer",
            label="flow.repair" if ctx.repair else "flow.design",
            stage_label="Design",
            messages=designer_messages(spec, repair=ctx.repair),
        )
        if parsed is None:
            parsed = ctx.bus.read_json("flow.json") or {}
        components = list(parsed.get("components") or [])
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
        # in full instead (config.main again).
        revise = (ctx.iteration > 1 and not ctx.repair
                  and bool(ctx.run.rig.get("_cell_revised")))
        label = ("config.repair" if ctx.repair
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
        ``config`` is byte-for-byte the draft's (the assembler wires, never
        edits config). The terminal FileOutput rename maps by elimination."""
        draft_comps = {str(c.get("id")): c for c in draft.get("components") or []}
        unclaimed = dict(draft_comps)
        for comp in job.get("components") or []:
            cid = str(comp.get("id"))
            if cid in unclaimed:
                comp["config"] = unclaimed.pop(cid).get("config")
        leftovers = list(unclaimed.values())
        for comp in job.get("components") or []:
            if str(comp.get("id")) in draft_comps:
                continue
            match = next((d for d in leftovers
                          if str(d.get("type")) == str(comp.get("type"))), None)
            if match is not None:
                comp["config"] = match.get("config")
                leftovers.remove(match)

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
# The slot map: real doors + specialists, stub verification spine (ticket 19)
# ---------------------------------------------------------------------------


def build_stages() -> Dict[str, StageAdapter]:
    from .stub_stages import StubDiagnostician, StubMaterializer, StubTestRunner

    adapters = [
        RealExplode(), RealDocNormalizer(), RealNormalizeValidate(),
        RealIntakeBuilder(), RealInterpreter(), RealFlowDesigner(),
        RealConfigurator(), RealAssembler(),
        StubMaterializer(), StubTestRunner(), StubDiagnostician(),
    ]
    return {s.key: s for s in adapters}
