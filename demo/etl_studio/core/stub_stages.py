"""Stub stage rig: the trade_positions specialists ticket 17 replaces stage
by stage (ticket 16's test rig -- the conductor is real, the specialist
CONTENT is canned).

Every stub exercises the real machinery -- streams go through the provider
port (the double plays the fixtures below, including a genuine tool-use
loop and a genuine rate-limit + backoff retry), artifacts land on the real
bus, and the conductor sequences with real counters -- but the artifact
content is the fixed trade_positions job ported from the ticket 12/15
design record, whatever the request says.

Rig knobs ride ``start_run`` params as ``rig: {...}`` (smoke uses them; the
webview never sends them): verify_fails (first N harness runs fail;
default 1), shape_errors (first N normalize passes report a shape error),
needs_human (one extraction question on the BRD door), owner_human (the
first diagnosis names the human as owner).
"""

from __future__ import annotations

from typing import Any, Dict, List

from .port import ToolDecl
from .stages import StageAdapter, StageContext, StageResult

# ---------------------------------------------------------------------------
# Run content (real-shaped, ported from the ticket 12 design record)
# ---------------------------------------------------------------------------

JOB = "trade_positions"
BRD = "Trade_Positions_BRD.docx"

SOURCES = [
    {"file": "trades.csv", "cols": 7},
    {"file": "accounts.csv", "cols": 3},
    {"file": "prices.csv", "cols": 2},
]

RULES = [
    {"id": "R1", "kind": "filter", "label": "Keep settled trades", "detail": "status = SETTLED"},
    {"id": "R2", "kind": "join", "label": "Add account details", "detail": "left join · account_id", "gap": "G1"},
    {"id": "R3", "kind": "join", "label": "Add closing price", "detail": "left join · symbol"},
    {"id": "R4", "kind": "derive", "label": "Compute market value", "detail": "quantity × price", "code": True},
    {"id": "R5", "kind": "validate", "label": "Validate trade_date", "detail": "yyyy-MM-dd"},
    {"id": "R6", "kind": "sort", "label": "Sort by market value", "detail": "high to low", "gap": "G2"},
]

GAPS = [
    {
        "id": "G1",
        "severity": "blocking",
        "rule": "R2",
        "prompt": "Trades with no matching account — drop them, or keep them with blank account fields?",
        "options": [
            {"id": "keep_blanks", "label": "Keep them with blanks", "kind": "choice",
             "recommended": True, "why": "the BRD reads as a full extract"},
            {"id": "drop", "label": "Drop unmatched trades", "kind": "choice"},
        ],
        "free_prompt": "Something else…",
    },
    {
        "id": "G2",
        "severity": "advisory",
        "rule": "R6",
        "prompt": "Equal market values: the BRD gives no tie-breaker. Default to trade_id ascending within ties?",
        "options": [
            {"id": "trade_id_asc", "label": "trade_id ascending", "kind": "choice",
             "recommended": True, "why": "stable and auditable"},
            {"id": "waive", "label": "Waive — proceed with the default", "kind": "waive"},
        ],
        "free_prompt": "A different tie-breaker…",
    },
]

NODES = [
    {"id": "in_trades", "kind": "source", "label": "Read trades", "sub": "trades.csv · 7 cols"},
    {"id": "in_accounts", "kind": "source", "label": "Read accounts", "sub": "accounts.csv · 3 cols"},
    {"id": "in_prices", "kind": "source", "label": "Read prices", "sub": "prices.csv · 2 cols"},
    {"id": "filter_settled", "kind": "filter", "label": "Keep status = SETTLED", "sub": "FilterRows"},
    {"id": "join_accounts", "kind": "join", "label": "Match accounts", "sub": "left join · account_id"},
    {"id": "join_prices", "kind": "join", "label": "Match prices", "sub": "left join · symbol"},
    {"id": "validate_date", "kind": "validate", "label": "Validate trade_date", "sub": "yyyy-MM-dd"},
    {"id": "derive_mv", "kind": "derive", "label": "Compute market_value", "sub": "generated cell", "code": True},
    {"id": "sort_mv", "kind": "sort", "label": "Sort by market_value", "sub": "numeric · desc"},
    {"id": "out_positions", "kind": "output", "label": "Write trade_positions", "sub": "trade_positions.csv"},
]

EDGES = [
    ["in_trades", "filter_settled"],
    ["filter_settled", "join_accounts"],
    ["in_accounts", "join_accounts"],
    ["join_accounts", "join_prices"],
    ["in_prices", "join_prices"],
    ["join_prices", "validate_date"],
    ["validate_date", "derive_mv"],
    ["derive_mv", "sort_mv"],
    ["sort_mv", "out_positions"],
]

CODE_CELL = {
    "id": "derive_market_value",
    "node_id": "derive_mv",
    "component": "tPythonDataFrame",
    "author": "Configurator",
    "code": "df['market_value'] = df['quantity'].astype(float) * df['price'].astype(float)",
    "validator": "validator clean · output schema 6 columns",
}
CODE_CELL_REVISED = dict(
    CODE_CELL,
    code=(
        "df['market_value'] = (df['quantity'].astype('float64')\n"
        "                      * df['price'].astype('float64')).round(2)"
    ),
    validator="validator clean · output schema 6 columns · rounding pinned",
)

VERDICT_TABLE = {
    "headers": ["trade_id", "account_name", "region", "symbol", "market_value", "closing_price"],
    "rows": [
        ["T004", "Gamma Funds", "APAC", "AAPL", "30200.00", "150.80"],
        ["T002", "Beta Partners", "EMEA", "MSFT", "20525.00", "411.00"],
        ["T001", "Alpha Capital", "NA", "AAPL", "15025.00", "150.80"],
        ["T005", "—", "—", "TSLA", "6901.00", "689.00"],
    ],
}

ORCH = {
    "questions": "I’ve read the requirement — three sources, six rules. Answers below and the spec is complete. They’re pinned to the rules they block, out on the canvas.",
    "signed": "Spec signed off. Your goldens are in place — this build grades against them.",
    "flow": "The flow is designed: a filter, two lookups, one computed column, a date check, a sort. Configuring each step now.",
    "gate": "One step writes code — computing market_value. Nothing runs until you approve the exact cell. The cell is on the canvas, spotlit.",
    "verdict": "Verified. The output matches your golden — all 4 rows, order included. Run 1 mis-sorted; the fix was one setting.",
    "reverdict": "Re-verified after your revision — the output still matches your golden, all 4 rows.",
}

THINK_INTERPRETER = (
    "R4 reads “settled trades only” — that’s a filter on status = SETTLED. "
    "Section 3 never says what happens to trades with no account match — raising it rather than assuming. "
    "Sort is given (value, high to low) but no tie-breaker — advisory, default trade_id."
)
THINK_FLOW = (
    "Filter first — it shrinks both lookups. "
    "Two joins stay separate: different keys, and rejects must be traceable per lookup. "
    "Sort placed last so the output order is the contract."
)
THINK_CONFIG_1 = (
    "join_accounts carries account_name and region; left join per the G1 answer — unmatched trades keep blanks. "
    "prices joins on symbol; single lookup column closing_price, key unique in the sample rows."
)
THINK_CONFIG_2 = (
    "market_value = quantity × price lands as the one generated cell — flagging it for the code gate. "
    "sort_mv compares numerically, descending; ties per the G2 default."
)

TOOL_RESULTS: Dict[str, Dict[str, Any]] = {
    "read_knowledge": {"ok": True,
                       "note": "loaded: join modes, key rules, 2 landmines (lookup dupe fan-out; type-mismatched keys)"},
    "validate_config": {"ok": True, "warn": "attempt 2 of 3",
                        "note": "run 1: sort_type missing → fixed. run 2: clean."},
    "write_artifact": {"ok": True, "note": "config.json · 10 components · 9 flows"},
}

TOOL_DECLS = [
    ToolDecl("read_knowledge", "Load the rendered knowledge slice for a component",
             {"type": "object", "properties": {"component": {"type": "string"}}}),
    ToolDecl("validate_config", "Validate one configured step against the component schema",
             {"type": "object", "properties": {"step": {"type": "string"}}}),
    ToolDecl("write_artifact", "Write a canonical artifact to the bus",
             {"type": "object", "properties": {"path": {"type": "string"}}}),
]


async def _tool_read_knowledge(args: Dict[str, Any]) -> Dict[str, Any]:
    return dict(TOOL_RESULTS["read_knowledge"])


async def _tool_validate_config(args: Dict[str, Any]) -> Dict[str, Any]:
    return dict(TOOL_RESULTS["validate_config"])


async def _tool_write_artifact(args: Dict[str, Any]) -> Dict[str, Any]:
    return dict(TOOL_RESULTS["write_artifact"])


STUB_TOOLS = {
    "read_knowledge": _tool_read_knowledge,
    "validate_config": _tool_validate_config,
    "write_artifact": _tool_write_artifact,
}


def build_scripts() -> Dict[str, List[List[Dict[str, Any]]]]:
    """Fixture scripts handed to the DoubleAdapter at the main.py wiring
    point, keyed by call label. Multi-call labels script the REAL loops:
    ``config.main`` round 2 is the tool-results follow-up; ``config.write``
    call 1 rate-limits so the runner's backoff genuinely re-issues."""
    u = lambda n: {"usage": int(n * 1e9)}  # noqa: E731 -- AIU to nano-AIU
    return {
        "orch.opening.brd": [[
            {"text": "Reading Trade_Positions_BRD.docx — three tables and six rule paragraphs found. I’ll interpret them into a spec; anything unclear becomes a question, never an assumption."},
            u(2.1),
        ]],
        "orch.opening.typed": [[
            {"text": "Reading your request. I’ll interpret it into a spec; anything unclear becomes a question, never an assumption."},
            u(1.7),
        ]],
        "brd.normalize": [[
            {"think": "Three tables explode clean — headers exact, handles pinned. Six rule paragraphs normalize to one requirement block each; nothing ambiguous enough to stop for."},
            u(2.8),
        ]],
        "interp.read": [[{"think": THINK_INTERPRETER}, u(3.4)]],
        "interp.revise": [[
            {"think": "Reading your note — folding it into the spec as a revision. Every signed answer carries over; only what you flagged moves."},
            u(2.6),
        ]],
        "orch.questions": [[{"text": ORCH["questions"]}, u(1.8)]],
        "orch.signed": [[{"text": ORCH["signed"]}, u(1.2)]],
        "flow.design": [[{"think": THINK_FLOW}, u(3.1)]],
        "orch.flow": [[{"text": ORCH["flow"]}, u(1.6)]],
        "config.main": [
            [
                {"think": THINK_CONFIG_1},
                {"tool": {"call_id": "t1", "name": "read_knowledge", "args": {"component": "tJoin"}}},
                {"pause": 0.5},
                {"tool": {"call_id": "t2", "name": "validate_config", "args": {"step": "keep_settled"}}},
                u(12.4),
            ],
            [u(0.6)],  # tool-results round: nothing more to say
        ],
        "config.write": [
            [
                {"think": "writing config.json for the configured steps…"},
                {"error": {"kind": "RateLimited", "message": "provider returned 429 on the last call", "retry_after": 1.8}},
            ],
            [
                {"think": THINK_CONFIG_2},
                {"tool": {"call_id": "t3", "name": "write_artifact", "args": {"path": "config.json"}}},
                u(9.7),
            ],
            [u(0.4)],  # tool-results round
        ],
        "config.revise": [[
            {"think": "Rewriting the market_value cell per your note — explicit float64 cast and a pinned 2-decimal round, no drift."},
            u(3.9),
        ]],
        "orch.gate": [[{"text": ORCH["gate"]}, u(1.9)]],
        "diag.run": [[
            {"think": "run 1 output: rows 2 and 3 swapped against the golden. sort_mv compares as text — '15025.00' sorts above '6901.00' only numerically. Owner: Configurator; fix is one setting, sort_type = num."},
            u(5.3),
        ]],
        "orch.verdict": [[{"text": ORCH["verdict"]}, u(2.4)]],
        "orch.reverdict": [[{"text": ORCH["reverdict"]}, u(1.8)]],
        "orch.hold": [[
            {"text": "You’d like me to pause. Confirm and I’ll hold at the next stage boundary — the stage in flight finishes and its artifact lands whole, then the build waits for you."},
            u(1.4),
        ]],
        "orch.stop": [[
            {"text": "You’d like to stop this build. Confirm and I’ll end it plainly at the next boundary — nothing else executes, everything so far stays on the canvas."},
            u(1.3),
        ]],
        "orch.resume": [[{"text": "Resuming — picking the build up exactly where the hold left it."}, u(0.9)]],
        "orch.steer": [[
            {"text": "That’s spec-shaped feedback, so it routes to the Interpreter: the spec revises, you re-sign it, and the stages after it re-run."},
            u(1.2),
        ]],
        "orch.ask": [[{"echo_prompt": True}, u(1.5)]],
    }


def _golden_csv() -> str:
    lines = [",".join(VERDICT_TABLE["headers"])]
    lines += [",".join(row) for row in VERDICT_TABLE["rows"]]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Code-slot stubs (explode, normalize_validate, intake_build, materialize,
# test_run) -- ticket 19 makes test_run real; the rest go real with 17.
# ---------------------------------------------------------------------------


class StubExplode(StageAdapter):
    key = "explode"

    async def run(self, ctx: StageContext) -> StageResult:
        await ctx.sleep(0.5)
        await ctx.write_artifact(
            "exploded.json",
            {"brd": ctx.run.request.get("brd_name") or BRD, "tables": 3, "rule_paragraphs": 6},
            kind="exploded",
        )
        return StageResult()


class StubNormalizeValidate(StageAdapter):
    """Fail-closed normalize: shape errors loop back to the normalizer
    (conductor-counted, <=3); needs_human raises on the question channel."""

    key = "normalize_validate"

    def __init__(self) -> None:
        self._passes = 0

    async def run(self, ctx: StageContext) -> StageResult:
        self._passes += 1
        await ctx.sleep(0.4)
        if self._passes <= int(ctx.run.rig.get("shape_errors", 0) or 0):
            return StageResult(
                "shape_error",
                {"note": f"pass {self._passes}: table 2 handle drifted — re-normalizing"},
            )
        if ctx.run.rig.get("needs_human") and not ctx.run.rig.get("_needs_human_done"):
            ctx.run.rig["_needs_human_done"] = True
            return StageResult(
                "needs_human",
                {"question": {
                    "source": "normalize_validate",
                    "prompt": "Table 2's second column header reads “Acct Name” in one row and “Account Name” in another — same column?",
                    "options": [
                        {"id": "same", "label": "Same column — merge the headers", "kind": "choice",
                         "recommended": True, "why": "the rows align and types match"},
                        {"id": "distinct", "label": "Treat as two columns", "kind": "choice"},
                    ],
                    "free_prompt": "Something else…",
                }},
            )
        await ctx.write_artifact(
            "intake.json",
            {"door": "brd", "brd": ctx.run.request.get("brd_name") or BRD,
             "sources": SOURCES, "tables": 3,
             "attachments": ctx.run.request.get("attachments") or []},
            kind="intake",
            fields={"sources": SOURCES, "door": "brd"},
            note=f"Explode · {ctx.run.request.get('brd_name') or BRD} → 3 tables, 6 rule paragraphs",
        )
        return StageResult(data={"data_present": True})  # BRD tables are exact rungs


class StubIntakeBuilder(StageAdapter):
    key = "intake_build"

    async def run(self, ctx: StageContext) -> StageResult:
        await ctx.sleep(0.9)
        attachments = list(ctx.run.request.get("attachments") or [])
        await ctx.write_artifact(
            "intake.json",
            {"door": "typed", "request_text": ctx.run.request.get("text"),
             "sources": SOURCES, "attachments": attachments},
            kind="intake",
            fields={"sources": SOURCES, "door": "typed"},
            note="Intake · request" + (" + attached sample and expected data" if attachments
                                       else " — no data attached"),
        )
        return StageResult(data={"data_present": bool(attachments)})


class StubMaterializer(StageAdapter):
    """Post-sign-off: writes input files + golden/ and computes the tier,
    rung-aware (ticket 04 -- one shared computation for both doors)."""

    key = "materialize"

    async def run(self, ctx: StageContext) -> StageResult:
        await ctx.sleep(0.6)
        tier = "verified" if ctx.run.data_present else "build"
        if ctx.run.data_present:
            await ctx.write_artifact(
                "golden/trade_positions.csv", None, text=_golden_csv(),
                kind="golden",
                fields={"outputs": 1, "tier": tier},
                note=f"Materializer · wrote golden/ — tier {tier}",
            )
        else:
            await ctx.write_artifact(
                "golden/.tier", None, text=tier + "\n", kind="golden",
                fields={"outputs": 0, "tier": tier},
                note=f"Materializer · no data to grade against — tier {tier}",
            )
        return StageResult(data={"tier": tier})


class StubTestRunner(StageAdapter):
    """Harness-as-subprocess arrives with ticket 19; the stub grades from
    the rig plan (first ``verify_fails`` runs fail on the sort bug)."""

    key = "test_run"

    async def run(self, ctx: StageContext) -> StageResult:
        k = int(ctx.run.rig.get("_run_index", 0)) + 1
        ctx.run.rig["_run_index"] = k
        await ctx.sleep(1.0)
        clean = k > int(ctx.run.rig.get("verify_fails", 1) or 0)
        report = {
            "run": k, "clean": clean, "graded": ctx.run.tier == "verified",
            "mismatches": [] if clean else [
                {"kind": "row_order", "rows": ["T001", "T005"],
                 "expected_before": "15025.00 above 6901.00",
                 "actual": "text compare put '6901.00' above '15025.00'"}],
        }
        await ctx.write_artifact(
            f"runs/run-{k}/test_report.json", report, kind="test_run",
        )
        note = (f"Test Runner · run {k} — clean" if clean
                else f"Test Runner · run {k} — 2 rows out of order")
        # Event-only marker: runs/run-<k> is a directory on the bus (the
        # report above lives inside it), so no payload rides this name.
        await ctx.write_artifact(f"runs/run-{k}", None, kind="test_run", note=note)
        return StageResult(data={"clean": clean, "run_index": k})


# ---------------------------------------------------------------------------
# LLM-slot stubs (doc_normalize, interpret, design, configure, assemble,
# diagnose) -- ticket 17 replaces these with the real specialists.
# ---------------------------------------------------------------------------


class StubDocNormalizer(StageAdapter):
    key = "doc_normalize"

    async def run(self, ctx: StageContext) -> StageResult:
        await ctx.stream("Doc Normalizer", "brd.normalize", stage_label="Intake")
        await ctx.write_artifact(
            "normalized.json", {"blocks": 6, "handles": 3}, kind="normalized",
        )
        return StageResult()


class StubInterpreter(StageAdapter):
    key = "interpret"

    async def run(self, ctx: StageContext) -> StageResult:
        revision = ctx.run.draft > 1
        await ctx.stream(
            "Interpreter",
            "interp.revise" if revision else "interp.read",
            stage_label="Interpret",
        )
        what_changed = (
            f"Draft {ctx.run.draft}: folded in your note — {ctx.run.feedback[:120]}"
            if revision else None
        )
        gaps = [] if revision else list(GAPS)
        await ctx.write_artifact(
            "requirement_spec.json",
            {"draft": ctx.run.draft, "sources": SOURCES, "rules": RULES,
             "gaps": gaps, "gap_resolutions": ctx.run.gap_resolutions,
             "what_changed": what_changed},
            kind="spec",
            fields={"draft": ctx.run.draft, "sources": SOURCES, "rules": RULES,
                    "gaps": gaps,
                    "gap_resolutions": ctx.run.gap_resolutions,
                    "what_changed": what_changed},
            note=f"Interpreter · requirement_spec draft {ctx.run.draft}",
        )
        return StageResult(data={"gaps": gaps, "what_changed": what_changed})


class StubFlowDesigner(StageAdapter):
    key = "design"

    async def run(self, ctx: StageContext) -> StageResult:
        if ctx.iteration == 1:
            await ctx.stream("Flow Designer", "flow.design", stage_label="Design")
        await ctx.write_artifact(
            "flow.json", {"nodes": NODES, "edges": EDGES}, kind="flow",
            fields={"nodes": NODES, "edges": EDGES},
            note="Flow Designer · 10 components, 9 flows",
        )
        return StageResult()


def _config_components(code: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for n in NODES:
        comp: Dict[str, Any] = {"id": n["id"], "type": "tPythonDataFrame" if n["id"] == "derive_mv"
                                else f"t{n['kind'].capitalize()}", "config": {}}
        if n["id"] == "derive_mv":
            comp["config"]["python_code"] = code
        out.append(comp)
    return out


class StubConfigurator(StageAdapter):
    key = "configure"

    async def run(self, ctx: StageContext) -> StageResult:
        code = CODE_CELL_REVISED if ctx.run.rig.get("_cell_revised") else CODE_CELL
        if ctx.repair:
            # Repair-loop re-run (04: owner reads feedback.json first): the
            # fix is a setting, not the cell -- rewrite config.json quietly,
            # no streams or progress walk.
            await ctx.sleep(0.5)
            await ctx.write_artifact(
                "config.json",
                {"components": _config_components(code["code"]),
                 "applied_fix": ctx.repair.get("fix"),
                 "cell_meta": {"derive_mv": {
                     "id": code["id"], "node_id": code["node_id"],
                     "component": code["component"], "author": code["author"],
                     "validator": code["validator"]}}},
                kind="config",
            )
            return StageResult(data={"repaired": True})
        condensed = ctx.iteration > 1
        if condensed:
            await ctx.stream("Configurator", "config.revise", stage_label="Configure")
            for n in NODES:
                await ctx.progress(n["id"], "configured")
        else:
            for n in NODES[:4]:
                await ctx.progress(n["id"], "active")
                await ctx.sleep(0.55)
                await ctx.progress(n["id"], "configured")
            await ctx.progress("join_accounts", "active")
            await ctx.stream("Configurator", "config.main", stage_label="Configure",
                             tools=STUB_TOOLS, tool_decls=TOOL_DECLS)
            await ctx.progress("join_accounts", "configured")
            await ctx.progress("join_prices", "active")
            await ctx.stream("Configurator", "config.write", stage_label="Configure",
                             tools=STUB_TOOLS, tool_decls=TOOL_DECLS)
            await ctx.progress("join_prices", "configured")
            for nid in ("validate_date", "derive_mv", "sort_mv", "out_positions"):
                await ctx.progress(nid, "active")
                await ctx.sleep(0.5)
                await ctx.progress(nid, "configured")
            await ctx.loop_attempt(
                2, 3, "validate loop · run 1: sort_type missing → fixed · run 2: clean")
        await ctx.write_artifact(
            "config.json",
            {"components": _config_components(code["code"]),
             "cell_meta": {"derive_mv": {
                 "id": code["id"], "node_id": code["node_id"],
                 "component": code["component"], "author": code["author"],
                 "validator": code["validator"]}}},
            kind="config",
        )
        return StageResult(data={"validate_attempts": 1 if condensed else 2})


class StubAssembler(StageAdapter):
    key = "assemble"

    async def run(self, ctx: StageContext) -> StageResult:
        config = ctx.bus.read_json("config.json") or {}
        job = {"components": config.get("components", []),
               "flows": [{"from": a, "to": b} for a, b in EDGES],
               "triggers": []}
        if ctx.repair:
            # Quiet re-assembly inside the repair loop: bus truth moves,
            # the feed narrates through the loop_attempt chip instead.
            await ctx.sleep(0.3)
            await ctx.write_artifact("job.json", job, kind="job")
            return StageResult(data={"repaired": True})
        await ctx.sleep(0.8)
        await ctx.write_artifact(
            "job.json", job, kind="job",
            fields={"components": len(config.get("components", [])), "flows": len(EDGES)},
            note="Assembler · job assembled — 10 components, 9 flows",
        )
        return StageResult()


class StubDiagnostician(StageAdapter):
    key = "diagnose"

    async def run(self, ctx: StageContext) -> StageResult:
        await ctx.stream("Diagnostician", "diag.run", stage_label="Verify")
        if ctx.run.rig.get("owner_human") and not ctx.run.rig.get("_owner_human_done"):
            ctx.run.rig["_owner_human_done"] = True
            feedback = {
                "owner": "human",
                "evidence": "expected output row T009 has no counterpart in any input row",
                "why": "the golden itself looks inconsistent with the attached sample",
                "fix": None,
                "question": "Row T009 exists only in the expected output — is the golden right?",
            }
        else:
            feedback = {
                "owner": "configurator",
                "evidence": "rows 2 and 3 swapped against the golden; '15025.00' sorts above '6901.00' only numerically",
                "why": "sort_mv compares as text",
                "fix": "sort_type = num",
                "suspect": "sort_mv",
            }
        await ctx.write_artifact(
            "feedback.json", feedback, kind="diagnosis",
            fields={"owner": feedback["owner"].capitalize(), "fix": feedback.get("fix")},
            note=("Diagnostician · owner: Configurator — sort compares as text"
                  if feedback["owner"] == "configurator"
                  else "Diagnostician · owner: you — the golden itself is in question"),
        )
        return StageResult(data={"feedback": feedback})


def build_stub_stages() -> Dict[str, StageAdapter]:
    """The rig's slot map; ticket 17 swaps entries one by one."""
    return {
        s.key: s
        for s in (
            StubExplode(), StubDocNormalizer(), StubNormalizeValidate(),
            StubIntakeBuilder(), StubInterpreter(), StubMaterializer(),
            StubFlowDesigner(), StubConfigurator(), StubAssembler(),
            StubTestRunner(), StubDiagnostician(),
        )
    }
