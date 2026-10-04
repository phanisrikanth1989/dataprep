# 02 - Input modes and requirement elicitation

Status: resolved
Type: grilling

## Question

How do a typed English request and an uploaded BRD both become one requirement
spec through agent<->human Q&A -- one modular pipeline, two front doors, no
duplicated downstream code copies?

To settle:

- What the elicitation loop asks, in what order, and when it stops -- what
  makes a requirement spec "complete enough" to hand to flow design.
- Whether BRD upload and typed request converge on the same artifact (the
  requirement-spec equivalent) and where the convergence point is.
- How the existing BRD-flow stages (docx purity, explode, normalize,
  interpret) map onto or merge with the typed-request path.
- What ambiguity handling looks like mid-run now that questions can reach the
  human live (today ambiguities surface only at the end).

Constraint from charting (map Notes): one modular pipeline, two front doors,
no duplicated code copies.

## Answer

Resolved 2026-08-09 via grilling. Terms recorded in root `CONTEXT.md`.

**Convergence point.** The two front doors converge at `requirement_spec.json`,
produced by one shared interpreter/elicitation stage. Upstream of it the doors
are asymmetric and that is fine; downstream there is exactly one pipeline.

**The doors.**
- BRD door: the existing deterministic chain (docx_purity -> extract_doc /
  explode -> normalize_validate) vendored into `demo/etl_studio/` essentially
  verbatim.
- Typed door: a thin intake -- request text, optional attached/referenced data
  files (sample input, optionally expected output), job name. Because the typed
  door can carry data, typed jobs can reach `smoke`/`verified`; the tier is one
  shared computation for both doors.
- One intake envelope wraps both: `intake.json` with `door: brd|typed` plus the
  door-specific payload, so the interpreter has a single documented input
  contract ("two front doors, one pipeline" made structurally true).

**Elicitation loop.** Gap-driven and uniform across doors: the interpreter
(LLM) emits every gap it finds as a structured object; a complete BRD yields
zero questions, a one-line typed request yields many. The split of judgment vs
bookkeeping: the LLM owns "what's unclear" (finding gaps); the stop rule is
deterministic bookkeeping over the structured gap list -- the loop ends when
the open-gap list is empty (every gap answered or explicitly waived). Soft
budget of 3 elicitation rounds, after which remaining open gaps are presented
as one batch for answer-or-waive. Rounds are dependency-first: foundational
gaps (sources, outputs) before rule-level gaps; the interpreter re-finds
downstream gaps after each round.

**Gap object.** Target spec field/rule, question text, proposed options with a
recommended default, severity (`blocking` -- field can't be filled without it;
`advisory` -- a default would be assumed), and the recorded resolution (answer
or waive). The spec thus carries its own audit trail of what the human decided.

**Question channel.** Single, orchestrator-owned. Specialists never address the
human directly -- they surface gaps in their artifacts and the orchestrator
relays. Questions are structured (AskUserQuestion-style: choose an option, with
a free-text fallback), batched in rounds, and carry a `source` field naming the
stage/tool that raised them. The BRD door's deterministic "ask a human"
moments -- docx_purity trips and normalize_validate `needs_human` exits --
become questions on this same channel, not dead stops.

**Spec sign-off (provisional).** The human explicitly approves
`requirement_spec.json` in the UI before flow design begins. Kept for now; may
be removed later if it feels like too much ceremony. Approve = proceed;
reject-with-feedback re-enters elicitation (interaction detail stays in the fog
for tickets 04/08).

Message *shape* of the channel belongs to ticket 08; this ticket fixes the
policy (orchestrator-only, structured, batched, pausing).
