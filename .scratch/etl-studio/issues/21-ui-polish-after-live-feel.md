# 21 - UI polish pass after live feel

Status: open
Type: task
Blocked by: 20

## Question

A dedicated finishing pass over the webview once the live end-to-end
(ticket 20) exists — the remaining nitty-gritties are wording-level and
small spacing/behavior adjustments that only read correctly against a real
run's pacing, not the scripted double.

Scope:

- Collect the nits during live dev-host runs (the user drives; each item
  lands here as a checklist line as it's spotted). Known categories from
  the 2026-08-10 F5 sessions: microcopy wording across cards, chips and
  voice lines; small gap/padding adjustments; affordance placement.
- Wording stays inside the settled language (CONTEXT.md: Build, run =
  execution only, RecTran) and the content-real rule; the v2 token system
  and surfaces are settled — this is finish work, not redesign.
- Both themes re-checked after each change; smoke and the seam tripwire
  stay green.

Done when the user signs off on the polished surface in the dev host
during a live build.

## Comments

2026-08-10 — Created at the user's direction after a day of F5 polish on
ticket 15 (leaders, gate footers, overflow menu, hero composer, Build
language, RecTran): "there are more nitty gritties present throughout...
wording level and few adjustments... i want to see how it looks and feels
during live run and then make those changes."

2026-08-10 — From ticket 16 (renderer gaps, beyond wording — small new
surfaces the wire already carries but the webview cannot show):

- [x] ~~`needs_human`~~ pulled forward at the user's direction
      (2026-08-10, commit 5a590f1b): a feed card in the propose-confirm
      pattern (validator reason as card text, recommended option primary,
      free-required options reveal an input), both themes checked via the
      journal-replay harness. Still open here:
- [ ] Question kinds `exhaustion` and `owner_human` have no card — they
      raise as real pending questions (journaled, replayed, answerable over
      the wire; smoke exercises them) but render nothing, so a live run
      that hits one waits invisibly. They start firing with ticket 19's
      real repair loops. Payload shapes are in `core/envelope.py`; the
      needs_human/propose-confirm feed cards are the pattern to follow.
- [ ] VerdictCard keys Approve on `verdict === "verified"` — an approvable
      `smoke_clean` (or build-tier `unverified`) verdict hides its Approve
      button. Ticket 13's "smoke-clean approvable" is wire-true (the
      conductor sends the Approve option), pixel-false. A tier chip on the
      verdict card would price it, per 13.

None fire in the default demo walk; they matter the moment ticket 17's
real specialists surface extraction questions or a dataless run reaches
the gate.
