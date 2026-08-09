# ETL Studio

Domain language for the ETL Studio effort: a VS Code extension where agents turn
a typed request or an uploaded BRD into a harness-verified DataPrep job, with the
human in the loop through the UI. (Map: `.scratch/etl-studio/map.md`.)

## Language

**Front door**:
One of the two entry points into the pipeline — the BRD door (uploaded `.docx`
through the deterministic docx chain) or the typed door (typed English request,
optionally with attached data files). Doors differ; everything after the
convergence point is shared.
_Avoid_: input mode, entry path

**Convergence point**:
The place where both front doors become one artifact: `requirement_spec.json`,
produced by the one shared interpreter/elicitation stage. Upstream of it, doors
may be asymmetric; downstream, there is exactly one pipeline.

**Intake**:
The artifact a front door produces, upstream of convergence: one common
envelope carrying which door it came through plus the door-specific payload
(the BRD extract, or the typed request with any attached data). The
interpreter's single input.

**Gap**:
A missing or ambiguous piece of the requirement spec, surfaced by the
interpreter as a structured object carrying its severity — blocking (the spec
can't be completed without an answer) or advisory (a default would be assumed)
— and, once addressed, its recorded resolution (the answer given, or a waive).
Elicitation asks the human only about gaps — a complete BRD yields zero
questions; a one-line typed request yields many.
_Avoid_: ambiguity (as the artifact term), issue

**Waive**:
The human's explicit "proceed with your default" on a gap. Recorded on the gap
itself, so the requirement spec carries its own audit trail of what the human
decided.

**Elicitation**:
The gap-driven Q&A loop between the pipeline and the human that refines either
door's intake into a complete-enough requirement spec. One uniform mechanism
for both doors. The LLM owns finding gaps; a deterministic stop rule owns
ending the loop — it ends when no gap is left unanswered and unwaived, with a
soft budget of three rounds. Rounds are dependency-first: foundational gaps
before rule-level ones.
_Avoid_: interview, questionnaire

**Question channel**:
The single orchestrator-owned path by which questions reach the human.
Specialists never address the human directly; they surface gaps in their
artifacts and the orchestrator relays them. Questions are structured objects
(prompt, options, free-text fallback), batched in rounds.

**Spec sign-off**:
The explicit human approval of `requirement_spec.json` in the UI before flow
design begins. Provisional decision — kept for now, may be removed if it feels
like too much ceremony.
