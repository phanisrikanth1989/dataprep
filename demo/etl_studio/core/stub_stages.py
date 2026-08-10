"""Stub stage rig: the verification-spine stand-ins ticket 19 replaces
(ticket 16's test rig, pruned by ticket 17 -- the doors and design-side
specialists are real now; see core/real_stages.py).

Three slots stay canned: the materializer (writes the demo golden and
computes the tier), the test runner (grades from the rig plan -- the real
harness subprocess is ticket 19's), and the diagnostician (fixed diagnosis
content; its ``diag.run`` stream fixture lives in core/demo_fixtures.py).

Rig knobs ride ``start_run`` params as ``rig: {...}`` (smoke uses them; the
webview never sends them): verify_fails (first N harness runs fail; default
1), owner_human (the first diagnosis names the human as owner), plus
shape_errors / needs_human, consumed by the REAL doc-normalizer as scripted
fixture-label selectors (real_stages.RealDocNormalizer).
"""

from __future__ import annotations

from .stages import StageAdapter, StageContext, StageResult

JOB = "trade_positions"

VERDICT_TABLE = {
    "headers": ["trade_id", "account_name", "region", "symbol", "market_value", "closing_price"],
    "rows": [
        ["T004", "Gamma Funds", "APAC", "AAPL", "30200.00", "150.80"],
        ["T002", "Beta Partners", "EMEA", "MSFT", "20525.00", "411.00"],
        ["T001", "Alpha Capital", "NA", "AAPL", "15025.00", "150.80"],
        ["T005", "—", "—", "TSLA", "6901.00", "689.00"],
    ],
}


def _golden_csv() -> str:
    lines = [",".join(VERDICT_TABLE["headers"])]
    lines += [",".join(row) for row in VERDICT_TABLE["rows"]]
    return "\n".join(lines) + "\n"


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
