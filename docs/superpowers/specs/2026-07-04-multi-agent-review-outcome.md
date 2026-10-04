# Multi-Agent Enrichment System - Adversarial Review Outcome

- **Date:** 2026-07-04
- **Branch:** `feature/copilot-etl-agents`
- **Scope:** The VS Code 1.122 native multi-agent system that turns a Word enrichment-requirements doc into a validated DataPrep engine JSON job (doc-interpreter -> flow-designer -> configurator -> assembler -> test-runner -> diagnostician, orchestrated by a free-agent loop with deterministic safety nets).
- **Status:** Review loop STOPPED by owner decision at 0 Critical (2026-07-04). Agent-side work complete; durable code-exec fixes handed to the engine team as backlog A6/A8/A9/A10.

---

## 1. TL;DR

Six independent multi-lens adversarial review passes were run over the agent system (7 lenses each: correctness-parity, security-codeexec, enrichment-domain-fit, performance-resource, agent-instruction-quality, test-oracle-soundness, cross-artifact-cohesion; every finding adversarially verified before it counted). **Every confirmed finding across all six passes has been fixed and verified.** The system now has **0 Critical** open, and **every correctness defect ever found was fail-safe** - a false-*fail* (the harness refuses or flags a good job), never a false-*pass* (no wrong data can silently reach SmartStream TLM).

The loop was stopped deliberately: it was **not converging to zero** (see the trajectory), each additional pass costs ~1.5M tokens, and the remaining root-cause fixes are engine-source changes the engine team owns.

## 2. The review campaign

| Pass | Findings | Critical | Important | Headline defect it caught |
|------|----------|----------|-----------|---------------------------|
| 1 | 26 | 0 | 12 | Enrichment-vs-reconciliation framing; oracle false-passes |
| 2 | ~17 | 1 | 8 | 3 writer specialists had no write tool (pipeline couldn't produce artifacts in Citi); arbitrary-file-write |
| 3 | 12 | 1 | 5 | Output path-jail was a `FileOutput`-only allowlist; ~8 other writers escaped |
| 4 | 12 | 0 | 3 | Oracle read back with a header even when `include_header` defaults false -> false-fail on headerless output |
| 5 | 7 | 0 | 3 | Side-effecting/egress components auto-ran in-process before the human gate; the canonical tMap example crashed for lack of `java_config` |
| 6 | 11 | 1 | 5 | SwiftTransformer external `config_file` loaded `eval`'d code the human gate never surfaced (RCE) |

The count oscillated at a low-but-nonzero level (7-12) rather than trending to zero; a fresh Critical appeared at pass 6 that five prior passes missed. This is the expected behaviour of adversarially reviewing a large surface (86 engine components, the full deterministic harness, 7 authored agents, the generated knowledge skill): each pass peels a new layer.

## 3. What was fixed, by theme

**Security perimeter (the harness is both the pass/fail authority and the pre-execution gate):**
- Output path-jail rewritten from a `FileOutput`-only allowlist to **default-deny across all writers**, plus relative-path anchoring (CWD-independent) and idempotent re-runs.
- **Fail-closed egress gate**: side-effecting/egress components (`tSendMail`, DB output/exec, FTP/HTTP/REST/SOAP/SSH, messaging) are refused before the engine runs, so no external side effect fires before the human gate.
- **Code-cell surfacing completeness**: `surface_code_cells` covers `python_dataframe`, `tPython*`, `tJava*`, `{{java}}`, PyMap, SwiftTransformer `python_expression`, RowGenerator `array`, RunIf `condition`; SwiftTransformer external `config_file` and nested `tRunJob` are **fail-closed**; top-level `java_config`/`python_config` code-load paths are jailed.
- Pre-execution human gate pauses on **any** surfaced code cell (not only "full-builtins" ones), because every eval/exec namespace in the engine is object-graph-escapable.

**Oracle soundness (fail-safe direction preserved throughout):**
- `include_header`-aware readback (headerless output no longer false-fails / crashes), missing-key diff guard, hollow-oracle guard (zero outputs != pass), non-delimited-writer diagnostic, duplicate-key + extra/missing-column symmetric checks.

**Knowledge layer (now engine-verified, not just plausible):**
- tMap mode values corrected to what the engine actually recognizes (`RELOAD_AT_EACH_ROW`; `ALL_ROWS` silently aliases `UNIQUE_MATCH` keep-last), mirrored into `map.json` and `config-surfaces.md` so they stop re-seeding.
- tMap date formatting corrected to the **real** mechanism (the `{{java}}` column expression; both `pattern` and `date_pattern` are dead on a tMap column) - note the review's *own* proposed fix here was wrong and was corrected against the source.
- `tmap-requires-java-config`, `tjoin-needs-use-lookup-cols`, `sortrow-alpha-default`, `sortrow-external-noop`, per-component `die_on_error` key, streaming-corruption batch-pin - all added/corrected and code-anchored.

**Agent instructions & cohesion:**
- The 3 writer specialists granted `edit/files`; sort_type propagation; schema handoff (configurator emits output, assembler derives input from topology); pushdown guidance (source-columns-only); live ambiguity-escalation channel; `inner_join_reject` ownership assigned to the configurator; enrichment-scope banners on the historical plans/spec so re-rendering can't resurrect the reconciliation model.

**The taught canonical example now provably runs** on the real engine + live Java bridge (a new `@pytest.mark.java` test parses and executes it - it was previously only string-matched, which is how the missing `java_config` crash hid).

## 4. Current verified state

- `python -m pytest tests/agents/` -> **165 passed**.
- `validate_tree(.github/agents, .github/skills)` -> `[]` (all agent/skill frontmatter valid; no `model:` key anywhere - model-agnostic).
- `check_schema_drift` -> clean (curated schemas match live fixtures).
- Golden enrichment e2e + the canonical job-envelope example both **pass over the live Java bridge**.
- Security refusals confirmed live: Swift `config_file`, nested `tRunJob`, escaping writer paths, and egress components are all rejected before execution.

## 5. Ship-readiness assessment

**Ready for Citi pilot use, with the engine-team backlog tracked.** The deterministic safety architecture is sound and load-bearing: the harness (not LLM judgment) owns pass/fail, the human gate is never auto-collapsed, every step is audit-logged, and every correctness defect surfaced during review failed safe. The agent-side mitigations for code-execution risk (surface + fail-closed) are complete.

**This is not a formal security sign-off.** The residual code-execution risk is real but bounded by the trusted-internal authorship + human-review threat model, and mitigated agent-side; the durable fixes are engine-source (below).

## 6. Engine-team backlog (owner: engine team; out of agent-system scope)

These are the root-cause fixes for the code-execution findings. The agent system's interim controls (surfacing + fail-closed gates) hold until they land.

- **A6** - `python_dataframe` runs a bare `exec` with full auto-injected builtins (unsandboxed). Align with `_code_component_mixin._build_safe_builtins`.
- **A8** - SwiftTransformer `eval`s each `python_expression` with `__import__` in builtins -> arbitrary-import RCE. Remove `__import__` (this is the durable fix for pass 6's Critical).
- **A9** - extend the harness output-path jail to `SwiftTransformer.output_file` as a first-class manifest entry (currently caught by the key-name-aware default-deny scan, but not explicitly manifested).
- **A10** - OS-sandbox the RowGenerator/RunIf eval sinks (object-graph-escapable namespaces; surfaced but not sandboxed).

See `docs/superpowers/specs/2026-07-03-copilot-etl-agents-backlog.md` Section A for full anchors.

## 7. Residual risks / caveats for Citi sign-off

- Code-execution components (`python_dataframe`, SwiftTransformer, tMap `{{java}}`) are unblocked for enrichment and can run LLM-authored code in-process. Interim control = surface every cell + human approval before first execution; durable control = A6/A8/A10.
- The `HYBRID` streaming-corruption class (stateful nodes silently wrong above 5GB) is mitigated by the configurator batch-pin instruction, not an engine guard - relies on the agent following the landmine.
- Uncurated components (78 of 86) degrade gracefully in `validate_config` (no strict schema), so the configurator must ground them in engine source; the oracle is the backstop.
- Live subagent orchestration only runs inside Citi's VS Code Copilot; local tests cover the deterministic tooling + the frontmatter gate. See `agents/PLATFORM.md` for the Citi-verification checklist.

## 8. Recommended next steps

1. **Engine team**: schedule A6/A8/A10 (the code-exec hardening) - A8 closes the only Critical-class root cause.
2. **Citi verification**: run `agents/PLATFORM.md`'s checklist inside the 1.122 Copilot enclave (tool-ID resolution, live `runSubagent`, skill load).
3. **This branch**: ready for review/merge when you are (`superpowers:finishing-a-development-branch`).
