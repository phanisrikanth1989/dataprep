# 09 - Run the vscode.lm probe on the Citi machine

Status: open
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
