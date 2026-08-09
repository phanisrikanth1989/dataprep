# ETL Studio

Domain language for the ETL Studio effort: a VS Code extension where agents turn
a typed request or an uploaded BRD into a harness-verified DataPrep job, with the
human in the loop through the UI. (Map: `.scratch/etl-studio/map.md`.)

## Language

**Front door**:
One of the two entry points into the pipeline — the BRD door (uploaded `.docx`
through the explode/normalize chain) or the typed door (typed English request,
optionally with attached data files). Each door is one path — no internal
routing branches. Doors differ; everything after the convergence point is
shared.
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

**Webview**:
The React UI surface of ETL Studio, running inside the VS Code webview panel.
Where the human sees the run's real state and answers questions. One of the
three layers; holds no agent logic.
_Avoid_: frontend (unqualified), UI layer

**Extension shim**:
The thin TypeScript layer in the VS Code extension host — it exists only
because vscode.lm and webview hosting live in that process. Three jobs: host
the webview, spawn and supervise the agent core, carry the LM bridge.
Deliberately dumb; zero agent logic.
_Avoid_: extension backend, host logic

**Agent core**:
The Python process beside the engine that owns all agent logic — orchestrator,
specialists, elicitation, artifacts, question channel, tools, harness.
Model-agnostic: it reaches models only through the provider port.
_Avoid_: backend (unqualified), runtime (unqualified)

**LM bridge**:
The local channel by which the extension shim exposes vscode.lm to the agent
core — the demo-day adapter behind the provider port. In production the bridge
is dropped, not swapped: the core calls the model gateway directly.

**Provider port**:
The plain-data interface through which the agent core requests model calls.
vscode.lm (via the LM bridge) is one adapter; R2D2 would be another; the
test-double is a third. The core never reaches around it.

**Specialist**:
An LLM-driven pipeline stage — doc-normalizer, interpreter, flow-designer,
configurator, assembler, diagnostician. Everything else is a code stage.
Specialists never address the human directly; the question channel relays.

**Artifact bus**:
The growing set of JSON artifacts a run produces under its work dir. Each
stage reads its predecessor's artifact and writes its own under a fixed
canonical name — produce, don't mutate; when a canonical file is superseded
(a repair re-run, a spec revision), the prior version moves to history rather
than being lost. Data never travels through an agent's prose.
_Avoid_: scratch files, pipeline state

**Materializer**:
The code stage that turns the signed-off requirement's data into the run's
ground truth — the input files and the golden answer key — and computes the
tier. Runs after spec sign-off, because elicitation can add data until then.
No model authors what it writes.

**Harness**:
The deterministic pass/fail oracle: runs the assembled job through the real
engine and diffs the outputs against the golden. Its verdict is the only
source of correctness — no model may override it, and a run it hasn't judged
is never done. Runs isolated from the agent core, so a misbehaving job cannot
take the core down.
_Avoid_: validator (that's the config/shape checker), test framework

**Tier**:
How much verification a run earns: verified (diffed against a golden — the
only tier whose failures drive the repair loop), smoke (runs once, ungraded),
build (assembled, never executed). Computed by the materializer from what data
exists and how exact its provenance is; a missing-data gap can raise the tier
mid-elicitation, and the tier freezes at spec sign-off.

**Rung**:
The exactness grade of a located piece of BRD data, derived from its
provenance: file and table handles are exact; image and prose transcriptions
are not, and can never ground a verified tier. Oracle-integrity machinery —
about who wrote the bytes, not who may look at them.

**Repair loop**:
The bounded fail-diagnose-re-run cycle on a built job: the diagnostician names
one owner, that stage re-runs reading the feedback first, and every stage
after it re-runs. Three iterations, then the human chooses — grant more, stop
at the gate, or steer. Verified tier only.

**Shape-repair loop**:
The bounded retry inside the BRD door: the validator rejects a structurally
malformed normalizer proposal with concrete fixes and the normalizer retries
with them. Three iterations, then the human.

**Owner**:
The single stage the diagnostician blames for a harness failure — the re-run
point of a repair iteration. Auto-repair applies only below the oracle:
anything upstream of golden materialization (a misread BRD, wrong attachments,
a wrong spec answer) breaks the oracle itself and is owned by the human.

**Pre-execution code gate**:
The standing human approval of every code-bearing cell in an assembled job,
in one batch, before the harness first executes the job. Re-checked each
iteration; re-pauses only when a cell is new or changed.

**Human gate**:
The final stop where only the human makes a job done: the runnable job, the
harness verdict, the surfaced code cells and every open question, presented
together and never auto-approved. A green harness is necessary, not
sufficient.
