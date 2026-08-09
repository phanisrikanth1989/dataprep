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
The single path by which questions reach the human. Specialists never address
the human directly: they surface gaps in their artifacts, the conductor raises
the event and records the resolution untouched, and the orchestrator gives the
outgoing prose its one voice. Questions are structured objects (prompt,
options, free-text fallback), batched in rounds.

**Spec sign-off**:
The explicit human approval of `requirement_spec.json` in the UI before flow
design begins. Provisional decision — kept for now, may be removed if it feels
like too much ceremony.

**Webview**:
The React UI surface of ETL Studio, running inside the VS Code webview panel.
Where the human sees the run's real state and answers questions. One of the
three layers; holds no agent logic.
_Avoid_: frontend (unqualified), UI layer

**Feed**:
The conversational surface of the webview — where the run talks to the human.
Only the orchestrator speaks here (narration, questions, gate summaries,
answers); specialist activity appears inline as observed work — thinking
blocks and tool chips — never as messages. Only the orchestrator gets chat
bubbles.
_Avoid_: chat, assistant panel

**Canvas**:
The state surface of the webview — the pipeline assembling live as the run
progresses; the hero of the demo. Everything on it is artifact content
rendered verbatim and attributed to the stage that wrote it — provenance
bylines, never bubbles.
_Avoid_: diagram, graph view

**Thoughts stream**:
Everything the human watches the run think: the specialists' live activity
(thinking deltas, tool calls, output) plus the orchestrator's narration and
answers. No separate narrator model exists — every word shown was authored by
an agent already doing the work.

**Live line**:
The one-line, present-tense pulse of the active stage, fed only by real
fragments — in priority order: the model's thinking deltas, else the
specialist's own opening line, else its tool-call verbs. The successor to the
retired canned thinking pill.
_Avoid_: thinking pill, status spinner

**Real content (vs canned)**:
The rule every webview string answers to: content shown as reasoning or state
must be traceable to this run — a stream part, an artifact field, an event —
while presentation (motion, shimmer, collapse grammar, fixed templates
framing real values) is free. Canned means invented content wearing the run's
clothes; polish is not fakery.

**Extension shim**:
The thin TypeScript layer in the VS Code extension host — it exists only
because vscode.lm and webview hosting live in that process. Three jobs: host
the webview, spawn and supervise the agent core, carry the LM bridge.
Deliberately dumb; zero agent logic.
_Avoid_: extension backend, host logic

**Agent core**:
The Python process beside the engine that owns all agent logic — conductor,
orchestrator, specialists, elicitation, artifacts, question channel, tools,
harness.
Model-agnostic: it reaches models only through the provider port.
_Avoid_: backend (unqualified), runtime (unqualified)

**LM bridge**:
The local channel by which the extension shim exposes vscode.lm to the agent
core — the wire the vscode.lm adapter talks through, not the adapter itself.
In production the bridge is dropped, not swapped: the core calls the model
gateway directly.

**Provider port**:
The plain-data interface through which the agent core requests model calls.
vscode.lm (via the LM bridge) is one adapter; R2D2 would be another; the
test-double is a third. The core never reaches around it.

**Adapter**:
An implementation of the provider port for one model source — the vscode.lm
adapter and the test double today. Owns every provider quirk: degrading the
port's ideal language to what the provider offers, normalizing provider
errors into the port's taxonomy. Classifies and raises, never retries —
retry policy belongs to the core, visibly.
_Avoid_: driver, provider (for the implementation)

**Test double**:
The adapter that plays back scripted responses instead of calling a real
model — deterministic streams, scripted tool calls, injected failures. The
offline development rig, and the standing proof that the core runs against a
second adapter unchanged.
_Avoid_: mock (unqualified), stub

**Conductor**:
The deterministic control layer of the agent core — the hub that runs the
pipeline. It computes every transition (the fixed itinerary, loop counters,
the owner-plus-forward repair rule, tier routing), enforces caps and gates,
invokes specialists and the harness, moves artifacts on the bus, writes the
audit trail, raises question-channel events, and records the human's
resolutions untouched. It cannot improvise: a run takes the same path in
rehearsal and live, and after a crash it restores from the bus and the audit
trail.
_Avoid_: driver, spine

**Orchestrator**:
The LLM agent that fronts a run — the sole agent addressing the human. It
narrates the conductor's transitions in its own words (non-blocking: the next
stage never waits on prose), answers the human's free-form questions grounded
in the run's real artifacts, gives all outgoing prose one voice, and catches
runs that leave the map by propose-confirm — free to stop and raise a
question, never free to act silently. Holds a persistent per-run context,
event-fed by the conductor and rebuilt from the audit trail on restart. It
never sequences.
_Avoid_: driver, free agent

**Specialist**:
An LLM-driven pipeline stage — doc-normalizer, interpreter, flow-designer,
configurator, assembler, diagnostician. Everything else is a code stage.
Specialists never address the human directly — their work is visible (streams
and artifact fields render observed and attributed) but never carries a
response affordance; the question channel relays, in the orchestrator's
voice.

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
at the gate, or steer: their free text becomes a directed spec revision, an
interpreter-owned iteration re-signed-off if the spec changes. Verified tier
only.

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
