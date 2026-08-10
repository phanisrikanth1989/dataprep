# ETL Studio -- Wayfinder Map

Label: wayfinder:map

## Destination

A VS Code extension running the full ETL job-authoring pipeline on an agent
runtime we own -- a BRD or a typed request in, the agents eliciting missing
requirements through questions to the human, then agents design, configure and
assemble the job, and a deterministic harness verifies it -- with the human in
the loop through the UI: agent questions, ambiguities and sign-offs surface
there and the answers flow back to steer the run, and what the UI shows is the
run's real reasoning and state, never canned placeholders. The agent core is
model-agnostic -- vscode.lm is one adapter behind a provider port the core
never reaches around -- so the later R2D2 swap is one new adapter with no
change to agent code.

## Notes

- This map carries execution: the destination is a working extension, not a
  hand-off spec.
- Tickets default to /grilling + /domain-modeling; domain terms land in
  CONTEXT.md lazily as they resolve.
- Testing is explicitly deprioritized for this effort (user decision; overrides
  the repo TDD default): get it working first, tests later.
- Hard invariants:
  - All new code lives strictly under `demo/etl_studio/`. Nothing outside that
    folder is modified -- `.github/agents`, `demo/budget_ui`, `agents/`,
    `src/` stay as-is and operational.
  - The ETL engine (`src/v1/`) is invoked read-only, never modified.
  - No imports from the `agents/` package. Copying (vendoring) existing
    agent/tool logic into `demo/etl_studio/` is allowed and expected -- most
    of it works clean for the BRD flow.
  - Diagnostician is the exception: its data-blind design is useless in
    practice; the rebuild makes it value-visible (detail in ticket 04).
  - Typed-English->ETL and BRD->ETL are one modular pipeline -- two front
    doors, no duplicated downstream code copies (owned by ticket 02).
  - UI is a webview inside the extension; demo run path is the F5 Extension
    Development Host (verified working by the user).
  - Provider port: a test-double adapter is in scope; a live second adapter
    proving the swap end-to-end is not.
- Model budget: ~20k credits available; 100-200 credits per demo run is a
  plus, up to ~500 acceptable. Cost is context, not a constraint. (Ticket 09
  decoded per-request nano-AIU billing from usage parts; whether AIU ==
  "credit" is unconfirmed.)
- Citi model roster (verified on-machine 2026-08-09, ticket 09): vendor
  `copilot` with claude-opus-4.8 / claude-opus-4.6 / claude-sonnet-4.6
  (~936k tokens), gpt-5.5, gpt-5.3-codex, plus minis and utility aliases;
  a `claude-code` vendor republishes the Claude models. Roster is
  org-mutable (the previously reported "GPT-5.Sol" has already vanished;
  "Claude Sonnet 5" never appeared) -- enumerate at runtime and select by
  vendor+id, never by display name.
- Demo framing: no "gateway today, product tomorrow" claim; the architecture
  makes the swap feasible, the demo does not perform it.

## Decisions so far

<!-- one line per closed ticket -->

- [01 - vscode.lm facts](issues/01-vscode-lm-facts.md) -- everything needed is
  stable API (tools 1.95, BYO provider 1.104, cross-extension visible); no
  System role in stable; one consent modal ever, then silent background loops;
  128-tool cap and three-tier error taxonomy mapped; F5 shares profile and
  extensions but NOT proposed APIs (launch-arg escape hatch); Citi selector
  strings need the on-machine probe (ticket 09).
- [02 - Input modes and requirement elicitation](issues/02-input-modes-elicitation.md)
  -- doors converge at requirement_spec.json via one shared interpreter; BRD
  door = existing docx chain vendored verbatim, typed door = thin intake that
  can carry data (so typed can reach verified); one `intake.json` envelope;
  elicitation is gap-driven and uniform (LLM finds gaps, deterministic
  bookkeeping stops the loop; 3-round soft budget, dependency-first rounds);
  gaps are structured objects with severity + recorded resolution; one
  orchestrator-owned question channel (structured AskUserQuestion-style,
  batched; purity trips and needs_human route through it too); explicit spec
  sign-off before flow design (provisional). Terms in root CONTEXT.md.
- [03 - Agent core: TypeScript or Python?](issues/03-agent-core-language.md)
  -- Python core beside the engine; React+TS webview; thin TS extension shim
  (vscode.lm and webview hosting live only there -- zero agent logic); LM
  bridge = stdio JSON-RPC, LSP framing, vscode-jsonrpc on the TS side; core
  spawned on panel open, visible auto-restart on crash; deciding axis: no
  Node.js on Citi servers (and a possible ADK future is Python-first); R2D2 =
  adapter swap, ADK = same-language re-host -- never blurred, no ADK-shaped
  abstractions on a "might"; walking skeleton graduated to ticket 10. Layer
  terms in root CONTEXT.md.
- [04 - Pipeline topology](issues/04-pipeline-topology.md) -- one path per door
  (purity branch dead, template parser demoted to library code); interpreter
  absorbs doc-interpreter; materializer runs post-sign-off and owns the
  rung-aware tier; test-runner becomes code, six LLM specialists remain; bus =
  fixed canonical names under `demo/etl_studio/work/<job>/` with
  `history/<artifact>.<k>` snapshots; both 3-cap loops keep semantics, with
  exhaustion and `owner: human` becoming question-channel events; mid-loop spec
  revision re-signs off; data-blindness dropped for three deterministic lines;
  diagnostician value-visible (harness embeds examples + work-dir reads),
  auto-repair only below the oracle; harness runs as a core subprocess.
- [05 - Orchestrator: LLM-driven or deterministic?](issues/05-orchestrator-llm-or-code.md)
  -- two layers: a code conductor sequences (fixed itinerary, caps, gates,
  events, resolutions; crash-restores from bus+audit) under an LLM orchestrator
  that fronts the run (non-blocking narration, answers the human from real
  artifacts, one voice, propose-confirm on the unplanned -- may always stop,
  never silently act); no standing between-stage judge; prose restyled but
  options/ids/code/values verbatim; exhaustion-steer = directed spec revision
  via the interpreter; rationale: keep the recognizable multi-agent pattern
  with deterministic control. ADR 0001.
- [06 - Real thoughts: what streams to the UI?](issues/06-real-thoughts-streaming.md)
  -- content real / presentation free (every shown string traceable to this
  run; polish unrestricted -- AI-product thinking UX, not a compliance
  display); thoughts stream per 05 = specialist streams + orchestrator
  narration; live line fed by thinking deltas (proposed-API flag, 09 probes)
  -> prompted specialist opening line -> tool verbs; canvas is hero, feed
  beside; voice split: feed bubbles = orchestrator only, specialist work =
  observed window (no response affordances), canvas = verbatim artifact
  fields with provenance bylines; title-cased domain names, code stages as
  step chips; data-free dead (real values, no masking mode); live credit
  readout from usage parts; failures rendered real and calm.
- [07 - Provider port and adapter seam](issues/07-provider-port-seam.md) --
  port speaks a neutral ideal chat language (system role, first-class
  tool_call/tool_result items, image content behind a capability flag;
  adapters degrade); chat = one async-iterator call, cancel = close the
  iterator, concurrent requests multiplexed by stream id; events
  text/thinking/tool_call/usage/done + skip-unknown rule; neutral exception
  family, adapters never retry (core owns visible backoff); mechanical TS
  shim / semantic Python adapter (wire = serialized vscode); list_models +
  per-stage config selectors; count_tokens optional capability; typed
  options only; no consent warm-up (modal on first real call); double =
  scripted playlist + error injection; seam = core/-never-imports-adapters/
  + AST tripwire test; nothing R2D2-specific.
- [08 - Runtime<->webview message contract](issues/08-runtime-webview-contract.md)
  -- one core-authored vocabulary end-to-end (shim = blind relay plus only
  `shim.lifecycle` and `editor.*`); envelope `{seq, ts, run_id, source, type,
  payload}` with skip-unknown; families run/stage/question/stream/health plus
  webview commands; canvas rides `artifact_written` payloads (old presenter
  events collapse); all question kinds share one raised->resolved lifecycle
  with generic resolution `{choice, free_text?}` and NO timeouts anywhere;
  streams forward 07's parts per-part (same stream id port to pixel), credits
  accumulate in the reducer; resume = full-fidelity `ui_journal.jsonl` replay
  via `attach {v, since_seq}`, seq continuous across crash-restart; idle
  state = the two front doors, `start_run`/`ask` commands; Python dataclasses
  canonical, hand-mirrored TS types. Pause/steer semantics graduated to
  ticket 13.
- [09 - Run the vscode.lm probe on the Citi machine](issues/09-citi-machine-probe.md)
  -- VS Code 1.122.1 (all needed APIs stable); dev host shares auth and
  roster; 13-model roster recorded with selector strings (family == id ==
  version for frontier models; no "Sonnet 5"/"GPT-5.Sol" -- roster
  org-mutable, select by vendor+id via enumeration, names non-unique);
  consent = one modal then silent loops (canSendRequest unreliable --
  request-time NoPermissions is the gate; ETL Studio pays its own dialog
  once, warm up at rehearsal); tool round trip verified on Opus 4.6; usage
  DataPart decoded (total_nano_aiu + per-type AIU rates; readout =
  sum/1e9; AIU=="credit" unconfirmed); max_tokens raises "Response too
  long." instead of truncating, and 3.74M-token input raised NO overflow
  error -- budget proactively via countTokens; --enable-proposed-api
  honored on stable (thinking parts unobserved, reasoning_tokens was 0 --
  dev-time prompts will discriminate; 06's fallback chain covers it);
  claude-code vendor proves third-party providers work on-machine (BYO
  policy page descoped).
- [11 - Engine knowledge in the owned runtime](issues/11-engine-knowledge.md)
  -- inline-primary hybrid: the core assembles per-stage knowledge slices
  in-prompt (whole artifact / field projection / component-filtered -- never
  editorial picks; inline is O(job), tool-read is O(catalog)); knowledge
  sources vendored, rendered at every core startup to a gitignored dir, never
  hand-edited; SKILL index retires into the core's slice map; engine-source
  mount is diagnostician-only (tool-registry absence enforces the ban);
  prompt ports in three tiers (near-verbatim / 02-04 structural rewrite /
  authored fresh); substantive enrichment deferred to ticket 14 (post-v1).
- [10 - Walking skeleton: three layers wired end to end](issues/10-walking-skeleton.md)
  -- built and F5-verified (user-confirmed, all steps): shim/core/webview +
  LM bridge live under `demo/etl_studio/`; stdio JSON-RPC proven end to end
  (attach/replay, stream family with port-to-pixel ids, cross-wire cancel,
  crash-restart seq continuity, live Copilot echo -- Mac-provisional);
  `npm run smoke` = standing editor-free wire proof, seam tripwire green;
  repo `.venv` now exists (interpreter resolution: setting -> `.venv` ->
  python3); provisional extensions recorded in the ticket (finish_reason
  "error", shim.restart, fixed run_id).
- [12 - Webview UI design](issues/12-webview-ui-design.md) -- v2 showpiece
  settled ("one killer version", user-approved): full-bleed canvas + floating
  glass feed, warm-graphite/ember elevation system (no border-boxes,
  product-scale type), camera choreography, flowing lit edges, gate staged as
  a hold, jade verdict wide-shot; interrupts anchor to their canvas subject;
  dark default + token-level light mode (VS Code theme-following posture);
  budget_ui layout() math ports, its skin retires; v1 three-variant file kept
  as the arrangement record; build graduated to ticket 15.
- [13 - Pause/steer and reject-with-feedback](issues/13-pause-steer-reject-feedback.md)
  -- one primitive: directed iteration (owner stage re-runs on human feedback,
  forward stages follow; interpreter = spec door with re-sign-off,
  configurator = code door); interruption is composer-only via
  propose-confirm — hold = a ninth question kind raised at the stage boundary
  (Resume/Stop/steer; artifacts land whole, no mid-stream cancel); steer
  always routes to the interpreter; gate rejects = Request changes
  (spec/human gate -> spec door, code gate -> configurator; red verdict loses
  Approve, smoke-clean approvable); stop ends the run plainly; human acts
  uncapped (caps bound autonomous iteration only); single-step stays retired;
  zero new wire families; UI = new spec-gate card + Request-changes ghosts +
  hold flow, landing via ticket 15 (scope amended).

- [15 - Build the webview to the v2 design](issues/15-build-webview-to-v2-design.md)
  -- built and editor-free-verified (F5 pass stays with the human): v2 system
  ported whole (tokens + light mode on VS Code theme classes, layout()/camera,
  assembly choreography, full component vocabulary, 13's gate/hold surfaces);
  pure reducer per 08 with rAF coalescing and reducer-side credits; scripted
  trade_positions run drives every beat over the real wire through the double
  (rejects, hold, errored stream, crash-restore mid-gate); fonts bundled
  locally via @fontsource; smoke 20 -> 51 checks green, seam green; provisional
  extensions recorded (stage.progress, tool_result part, stream labels,
  runless attach, editor.pick_file); scripted driver is the placeholder
  ticket 16's conductor replaces behind the same wire.
- [16 - Conductor and artifact bus](issues/16-conductor-and-artifact-bus.md)
  -- the deterministic chassis is real behind the unchanged wire (webview
  zero changes): code conductor with both doors' itinerary, caps/grants,
  owner+forward directed iteration, tier routing, hold/steer/stop verbs and
  propose-confirm escalation; file bus with canonical names,
  history/<artifact>.<k> and audit.jsonl; all nine question kinds on one
  validated lifecycle (resolutions recorded untouched); port completed
  (tool loop runner, count_tokens, typed options, per-stage selectors,
  core-owned backoff) with the shim's lm/countTokens + tools; crash-restore
  re-walks from bus+audit with count-based journal ledgers; stub
  trade_positions rig is 17's replacement target; smoke 51 -> 74 green;
  renderer gaps (3 kind cards, smoke-clean Approve) flagged to 21.

## Not yet specified

- Demo rehearsal / replay story -- deterministic run-through for the day;
  revisit once the runtime exists.

## Out of scope

- Proving the R2D2 swap live (headless run through a second real adapter) --
  architected for, not demonstrated, per charting decision.
- R2D2 internals and wire format.
- `.vsix` packaging and distribution -- F5 dev host is the demo path.
