# 09 - Run the vscode.lm probe on the Citi machine

Status: claimed
Type: task

## Question

Turn the "verify on-machine" gaps from ticket 01's research into recorded
facts by running the probe on the Citi VS Code F5 dev host. Only the user can
do this (Citi machine access). ~30 minutes.

Checklist and copy-paste probe extension:
`../research/2026-08-09-vscode-lm-facts.md`, section
"On-machine checklist (Citi F5 dev host)" (steps 0-7).

Record into this ticket's Answer:

- VS Code and Copilot extension versions on the Citi machine (provider API
  needs >= 1.104).
- Whether the F5 dev host shares the main install's Copilot auth and model
  roster.
- The real vendor/family/id/version/maxInputTokens for GPT-5.Sol,
  Claude Opus 4.8, Claude Sonnet 5 -- these become the provider port's
  selector strings.
- Consent dialog behavior: first-call modal with justification text,
  persisted grant, NoPermissions on decline, and multi-turn loop viability
  with no further prompts.
- Tool round-trip works end to end; any unknown stream parts observed
  (thinking / usage data parts).
- Whether modelOptions.max_tokens truncates output; exact input-overflow
  error text.
- Whether --enable-proposed-api works on the Citi stable build (gates the
  thinking-part display option in ticket 06).
- Copilot Business/Enterprise BYO-model policy state (gates the future
  R2D2-as-provider path discussed in ticket 07).

Results inform tickets 03, 06 and 07 (informs, does not block them).

## Comments

2026-08-09 -- Handoff package prepared at
[`../research/lm-probe/`](../research/lm-probe/): the probe extension as
ready-to-copy files (`package.json`, `extension.js`, `.vscode/launch.json`),
a run guide (`README.md`), and a results form (`WORKSHEET.md`) mirroring the
record-list above. Code follows the research-doc listing with
logging/robustness deltas documented in the README (notably: unknown stream
parts now dump their payload so a `usage` part yields its JSON, and the
engine pin is lowered so the probe still runs on a pre-1.104 build). Probe is
syntax-checked but not yet executed anywhere; the README describes an
optional dry run on any Copilot-enabled machine before spending the Citi
slot. Awaiting the on-machine run -- paste the filled worksheet (or a raw LM
Probe output dump) into a wayfinder session to resolve this ticket.
