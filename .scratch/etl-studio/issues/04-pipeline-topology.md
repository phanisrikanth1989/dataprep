# 04 - Pipeline topology: what survives the re-host?

Status: resolved
Type: grilling
Blocked by: 02

## Question

Which stages, loops, tiers and gates of the current pipeline survive into the
owned runtime, and which change?

To settle:

- Stage list given the front door(s) decided in ticket 02.
- Artifact bus: keep file-based artifacts under a work dir, or in-memory with
  persisted snapshots?
- Bounded repair loops and the 3-iteration caps: keep the semantics?
- Verification tiers (verified/smoke/build): keep, simplify, or rethink now
  that a human is live in the loop?
- Diagnostician rebuild: charting judged its data-blind design useless -- the
  rebuilt diagnostician is value-visible. What does it read, and what does
  its feedback artifact look like?
- Data-blindness posture generally: which stages keep it (if any) and why.

## Answer

Resolved 2026-08-09 via grilling. Terms recorded in root `CONTEXT.md`.

**The spine.** One path per door, converging per ticket 02, then exactly one
pipeline:

```
BRD door (one path, every .docx):        Typed door:
  explode_doc (code)                       thin intake builder (code)
    -> doc-normalizer (LLM, eyes-on)
    -> normalize_validate (code, fail-closed;
         shape_error -> shape-repair loop <=3;
         needs_human -> question channel)
                   \                        /
                    ->    intake.json    <-
                             |
        interpreter (LLM; gap-driven elicitation, <=3 rounds)
                             |
        requirement_spec.json -> SPEC SIGN-OFF
                             |
        materializer (code; input files + golden/ from either door's data;
                      computes the tier, rung-aware)
                             |
        flow-designer -> configurator (validate_config loop) -> assembler
                             |
        PRE-EXECUTION CODE GATE (surface_code_cells; one batch approval
          before the first harness run; re-pause only on new/changed cells)
                             |
        test-runner (code: harness as subprocess)
          pass -> HUMAN GATE
          fail -> diagnostician (LLM) -> repair loop (owner + forward, <=3) -> GATE
```

- The purity branch is dead: `docx_purity` is no longer a stage and there is no
  opt-in pause -- every `.docx` takes the explode -> normalize chain. The
  template route was pre-normalizer scaffolding; `extract_doc.py` survives as
  library code only. Template-pure docs keep `verified` eligibility (table
  handles are exact rungs) at the cost of one normalizer call. Escape hatch
  noted, not built: a silent code-side router for clean docs can be added later
  with no topology change if rehearsal shows variance.
- doc-interpreter merges into the shared **interpreter**: its prompt is
  vendored as the interpreter's core and its `ambiguities` channel is subsumed
  by 02's gap objects -- same machinery, nothing lost.
- Materialization moves from step 0 to after spec sign-off -- forced by 02:
  elicitation can add data mid-run, so goldens cannot be written until the
  data set is final.
- LLM stages (six): doc-normalizer, interpreter, flow-designer, configurator,
  assembler, diagnostician. Code stages: explode, normalize_validate, intake
  builder, materializer, test-runner (the agent ceremony is dropped -- the core
  invokes the harness directly).
- All three safety nets survive unchanged (harness sole verdict, append-only
  audit log, human gate never auto-approves); the pre-execution code gate
  survives as a standing gate.

**Artifact bus.** File-based and produce-don't-mutate: each stage writes its
own artifact under a fixed canonical name; nothing in a pass is overwritten.
Flat per-run work dir at `demo/etl_studio/work/<job>/` (with `golden/`),
gitignored via a nested `demo/etl_studio/.gitignore` so the containment
invariant holds. On any write where the canonical file already exists, the
superseded version moves to `history/<artifact>.<k>.json` -- `k` monotonic per
artifact, one dumb rule covering every rewrite cadence (repair loop,
shape-repair loop, spec revisions); `audit.jsonl` maps each `k` to its context.
In-memory bus rejected: 03's crash-restart decision, auditability, and no
serialization win since stages already exchange JSON.

**Loops and budgets.** Both bounded loops keep today's semantics and caps:
shape-repair (validator feedback -> normalizer retry, <=3) and the main repair
loop (diagnostician names ONE owner; the owner re-runs reading `feedback.json`
first, then every forward stage; <=3; verified tier only -- smoke is exactly
one run, build never runs). Two live-human upgrades: (1) budget exhaustion in
either loop becomes a question-channel event -- grant another 3 / stop to the
gate / steer -- never a silent stop; (2) `owner: human` becomes a mid-run
structured question instead of a dead stop. Grants are unlimited but each is
an explicit human act, so spend cannot run away silently. Elicitation's
3-round budget and the configurator's inner validate loop remain separate
counters. A mid-loop spec revision (`owner: interpreter`) re-presents
`requirement_spec.json` for a quick re-sign-off -- sign-off means the spec is
the human's.

**Verification tiers.** `verified`/`smoke`/`build` survive with today's
semantics and gate labels; only `verified` loops. Tier computation relocates
from `extract_doc` to the materializer (one shared computation for both
doors), honoring rungs -- transcribed image/prose data never earns `verified`.
New: absent sample/expected data raises an advisory gap ("attach data to get
verification"), so a typed one-liner climbs tiers by attachment; the tier
freezes at sign-off/materialization.

**Diagnostician rebuild (value-visible).** Reads: `test_report.json`, now
enriched by the harness with bounded examples (up to N=5 offending keys per
diff bucket, expected-vs-actual per differing column), PLUS direct read access
to the work dir (actual outputs, goldens, inputs, upstream artifacts).
`feedback.json`: `owner`, `evidence` (structural signal + real values,
bounded), `why`, `fix`, `suspect` (optional component id / config key),
`question` (present iff owner is `human`, routed on the channel). Owner enum:
`interpreter | flow-designer | configurator | assembler | human`. Principle
locked: **auto-repair only below the oracle** -- anything upstream of golden
materialization (a misread BRD, wrong attachments, a wrong spec answer)
invalidates the oracle itself, so no `doc-normalizer` owner exists; it routes
to `human`. Note-vs-oracle survives verbatim: a failure fixable only by
silencing a `source: "note"` rule routes to `human`, never silently repaired.

**Data-blindness posture.** Dropped -- no stage is data-blind by posture.
Three deterministic lines survive instead: (1) models never author or edit
input/golden bytes (only the exploder's jailed extraction and the materializer
write data files); (2) the harness verdict is the sole correctness source;
(3) the rung machinery survives verbatim, reframed as provenance/exactness
grading. The interpreter (and flow-designer/configurator when useful) may read
sample values -- bounded rows in-prompt, full files via tool.

**Execution isolation.** The harness runs as a subprocess of the agent core
(vendored CLI, captured output): job code cells are RCE-capable and must never
be able to take the core down.

**Mode.** Autonomous loop only for v1. Single-step/testing mode is retired and
recorded as prior art in the pause/steer fog entry.

**For ticket 08 (policy fixed here, shapes there).** The question-channel
event families this topology produces: elicitation gap rounds, extraction
`needs_human`, code-gate batch approval, spec sign-off and re-sign-off,
budget-exhaustion grants, `owner: human` questions, and the human gate itself.

Boundaries held: ticket 05 still owns who drives this loop (LLM or code);
ticket 08 owns the message shapes; pause/steer and reject-with-feedback stay
in the fog.
