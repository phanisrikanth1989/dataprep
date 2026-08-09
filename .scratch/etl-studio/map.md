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
- Orchestrator leaning recorded from charting: LLM-driven (stress-tested in
  ticket 05).

## Decisions so far

<!-- one line per closed ticket -->

- [01 - vscode.lm facts](issues/01-vscode-lm-facts.md) -- everything needed is
  stable API (tools 1.95, BYO provider 1.104, cross-extension visible); no
  System role in stable; one consent modal ever, then silent background loops;
  128-tool cap and three-tier error taxonomy mapped; F5 shares profile and
  extensions but NOT proposed APIs (launch-arg escape hatch); Citi selector
  strings need the on-machine probe (ticket 09).

## Not yet specified

- Pause/steer and reject-with-feedback interactions -- sharpen after tickets
  02, 04 and 08 land.
- Implementation slices -- extension+runtime skeleton, vendored/rebuilt
  agents, elicitation UI, verification wiring, what of budget_ui's React
  canvas thinking ports into the webview. Specifiable once the design tickets
  resolve.
- How rebuilt agents receive the engine knowledge (landmines /
  config-reference / job-envelope equivalents) in the new runtime.
- Demo rehearsal / replay story -- deterministic run-through for the day;
  revisit once the runtime exists.

## Out of scope

- Proving the R2D2 swap live (headless run through a second real adapter) --
  architected for, not demonstrated, per charting decision.
- R2D2 internals and wire format.
- `.vsix` packaging and distribution -- F5 dev host is the demo path.
