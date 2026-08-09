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
  plus, up to ~500 acceptable. Cost is context, not a constraint.
- Models reported in Citi Copilot chat (user-reported, lightly normalized):
  GPT-5.Sol, Claude Opus 4.8, Claude Sonnet 5. Availability inside the F5 dev
  host is assumed, not verified -- ticket 09 carries the on-machine probe.
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

## Not yet specified

- Pause/steer and reject-with-feedback interactions -- sharpen after ticket 08
  lands (02, 04 and 05 are in; 05 pinned exhaustion-steer and the
  propose-confirm escalation). Prior art: the retired single-step/testing mode
  (one stage per turn, no auto-repair); ticket 04 ships v1 autonomous-only.
- Implementation slices -- vendored/rebuilt agents, the conductor state
  machine and orchestrator agent (ticket 05), verification wiring, wiring
  the webview to the live runtime. Specifiable once the design tickets
  resolve. (Webview look-and-feel graduated to ticket 12.)
- Demo rehearsal / replay story -- deterministic run-through for the day;
  revisit once the runtime exists.

## Out of scope

- Proving the R2D2 swap live (headless run through a second real adapter) --
  architected for, not demonstrated, per charting decision.
- R2D2 internals and wire format.
- `.vsix` packaging and distribution -- F5 dev host is the demo path.
