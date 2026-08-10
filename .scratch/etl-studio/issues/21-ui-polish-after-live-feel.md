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
- [ ] The attach picker is single-select — a BRD plus three data files means
      four separate picker round-trips (user, first live session
      2026-08-10). Allow multi-select (`canSelectMany` in the shim's
      editor.pick_file) and/or real drag-and-drop onto the composer.
- [ ] At the spec sign-off, the card's leader lines anchor only to the
      gap-answered rules — which reads as "you are signing R1 and R2" when
      the signature covers the whole spec (user asked exactly this, live
      session 2). Consider dropping/deemphasizing leaders at sign-off, or
      an all-rules highlight sweep instead.
- [ ] "Doc Normalizer · proposal validated clean — 3 sources, tier verified"
      renders twice in the feed (the intake stage-completed note and the
      intake.json artifact note carry the same string) — de-duplicate or
      differentiate the wording (live session 2, 2026-08-10).
- [ ] The idle screen is fully clickable before the wire is actually ready:
      while attach is pending (or the core is frozen/holding a run) the
      composer renders as a normal "READY" idle surface, and health chips
      only render inside the run view — so every wire-level failure reads
      as dead clicks (first live session, third dead-click variant; the
      core-side freeze itself is fixed by the 8s resolve timeout,
      commit 40051689). Needs a connecting/health state on the idle
      surface and Start build disabled until attach resolves.
- [ ] `health.provider_fallback` (live -> double) renders only as a feed
      chip — a run playing SCRIPTED content instead of live Copilot should
      be unmistakable (e.g. a persistent header marker near the credits),
      or a cold-start fallback will be mistaken for a live run.
- [ ] `health.error RunActive` ("a build is already active — one build per
      panel") renders nothing: clicking a door while a restored run still
      holds a gate is silently refused (first live session, 2026-08-10,
      hit it 12 times across two restarts — reads as dead clicks). Needs a
      visible banner, and ideally the door surface disabled while a run is
      active.
- [ ] After a crash-restore lands mid-gate, the webview needs an obvious
      "this build continues — answer the pending gate" cue (and/or a
      deliberate start-over affordance): the user reopened the panel and
      reached for the doors instead of the restored gate card.
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
