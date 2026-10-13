# 08 - Runtime<->webview message contract

Status: resolved
Type: grilling
Blocked by: 02, 03, 04, 05

## Question

What is the bidirectional message contract between the agent runtime and the
webview?

To settle:

- Event vocabulary replacing the old 10-event one-way stream (stage, nodes,
  edges, callout, gate, result, end...) -- what survives, what is new.
- The question/answer flow: how an agent question reaches the UI, how the
  answer returns and unblocks the run, timeouts/defaults.
- Sign-off flows (code gate, final approval) as real round-trips.
- Streaming thoughts (per ticket 06) as a channel.
- Resume semantics: reload the webview mid-run and reconstruct state.

## Answer

Resolved 2026-08-09 via grilling (two rounds; ticket 07 landed mid-session and
sharpened the stream shapes). Terms in root `CONTEXT.md`.

**Contract layering.** One message vocabulary, authored by the core; the
contract is core<->webview and the shim is a blind relay routing by method
family (the same stdio wire also carries 07's `lm/*` family, which is
shim<->core only and never reaches the webview). The shim owns exactly two
families of its own: `shim.lifecycle` (core spawned / crashed / restarting /
dead -- it is the only survivor when the core dies, so no webview-side
heartbeat inference) and `editor.*` (webview->shim VS Code actions: open a
file in the editor, native file pick). Everything else it relays untouched.

**Envelope.** Every core-originated event: `{seq, ts, run_id, source, type,
payload}`; `source` is `conductor | orchestrator | specialist:<stage> | shim`.
`seq` is monotonic per run and owned by the journal, not the process (see
resume). Shim events seq in their own namespace, since they can fire while the
core is dead. Protocol version rides the attach handshake once (`v: 1`), never
per message. Forward-compat law adopted from 07: the webview silently skips
unrecognized event types, so vocabulary can grow without lockstep releases.

**Event families (replacing the old presenter's ten).**

- `run.*` -- started / ended / crash_restored (door, tier, job name).
- `stage.*` -- started / completed / artifact_written / loop_attempt k-of-n.
  Conductor machine truth; feeds stage lights, step chips, provenance bylines.
  The old `sources`/`rules`/`nodes`/`edges`/`node_config` events collapse into
  `artifact_written` payloads carrying the renderable fields -- canvas is
  verbatim artifact fields, so the artifact event IS the canvas event.
- `question.*` -- raised / resolved. 04's seven policy families plus 05's
  propose-confirm escalation are a `kind` field on one shared lifecycle
  (raised -> pending -> resolved); the webview's question UI is single-pathed.
- `stream.*` -- open / delta / close per model call. Part kinds are 07's port
  vocabulary verbatim (`text_delta`, `thinking_delta`, `tool_call`, `usage`);
  the stream id is the SAME id the core generated for `lm/chat` -- one id
  follows a model call from port to pixel; close carries `done`'s
  finish_reason.
- `health.*` -- core-state only: retry/backoff chips (core owns retries per
  07), classified provider errors, ConsentDenied surfacing.
- Webview->core: `attach`, `answer`, `command.start_run`, `command.ask`,
  `fetch_artifact` (plus `editor.*`, terminating at the shim).

**Streaming.** Parts forward per-part as they arrive -- no core-side batching
or throttling (symmetric with 07's `lm/chatEvent` leg); the webview owns
coalescing to animation frames. The live credit readout accumulates
webview-side in the reducer from raw `usage` parts -- no core-side running
total (no parallel truth to keep honest).

**Artifact content travel.** Inline for everything the UI shows unprompted:
`artifact_written` and `question.raised` payloads carry the renderable fields
(canvas fields, code cells, diagnostician evidence, spec + gap resolutions) --
already small, bounded JSON by 04's design, and replay stays self-contained.
One `fetch_artifact` request exists for zoom-in affordances (full artifact
JSON on demand). Whole data files never cross postMessage -- they open in the
real editor via `editor.*`.

**Question/answer mechanics.** Notification pairs correlated by question id --
never a blocking RPC. A pending question is state: it replays on attach and
survives reloads. **No timeout exists anywhere in the contract**; a "default"
is only ever a recommended option the human still has to choose. The
resolution is one generic shape across all eight kinds: `{question_id,
choice, free_text?}` -- options are structured `{id, label, kind:
approve|reject|waive|grant|stop|steer|...}` and declare whether they accept
free text (steer text, reject feedback, gap fallback). The conductor records
resolutions untouched. Sign-offs ride the same lifecycle: the code gate raises
`kind: code_gate` with cells inline (id, code, provenance, new/changed flag);
spec sign-off carries the spec and its gap resolutions; the human gate carries
verdict, tier, cells and open questions. The SEMANTICS of reject-with-feedback
and pause/steer stay fog (graduated to ticket 13) -- 08 guarantees whatever
they decide fits this shape.

Batching (02's "rounds"): a round is N individual `question.raised` events
sharing a `round_id`; the webview groups them into one card set, and each
resolves independently through the normal `{question_id, choice, free_text?}`
answer. No round-level resolution message exists -- the conductor's
deterministic bookkeeping already knows when a round's gaps are all
answered-or-waived.

**Resume = journal replay.** The core appends every webview-bound event
verbatim -- stream deltas included -- to `ui_journal.jsonl` beside
`audit.jsonl` (append-only, one envelope per line). Full fidelity: thinking
blocks reopen with content after reload, rehearsal replay is exact, and the
size argument against it does not survive arithmetic at demo scale. The
webview attaches with `{v, since_seq}` (0 on fresh load); the core replays
from there; the reducer is pure, so state reconstructs exactly -- no snapshot
path, no second state derivation. Crash-restart: the restarted core reads the
journal tail and CONTINUES the same seq sequence, appending
`run.crash_restored`; a webview that never died just receives the
continuation. The journal, not the process, owns the sequence -- the same
move as 04 making the bus, not memory, own the artifacts.

**Attach, idle state, and starting a run.** `attach {v, since_seq}` ->
`attached {v, run?}`. If a run exists (active or finished), replay follows; if
not, the webview renders the idle state: the two front doors (typed request
input; BRD file pick via `editor.pick_file` -- webviews cannot open native
dialogs). A run starts via `command.start_run {door, payload}`. One run per
panel in v1; a finished run stays on screen until a new one starts, which
begins a fresh journal. No past-run browser.

**Free-form human->orchestrator Q&A (per 05).** `command.ask {ask_id, text}`;
the orchestrator's answer streams as normal orchestrator stream events
carrying `in_reply_to: ask_id`, so the feed can thread it. Conversation, not
a gate -- nothing blocks, nothing times out.

**Types.** Python dataclasses are canonical (the core authors the contract,
matching 07's port precedent); the webview imports a hand-mirrored `types.ts`.
The skip-unknown rule is exactly the tolerance that makes hand-mirroring safe
at this effort's testing posture. No JSON Schema toolchain.

**Flows onward.** Ticket 13 (graduated from fog): pause/steer and
reject-with-feedback semantics. Ticket 12 renders these families; ticket 10's
skeleton proves attach/replay plus one stream family end-to-end.
