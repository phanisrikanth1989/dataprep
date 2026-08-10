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
      Confirmed live in ticket 20 run 1 (2026-08-10): drag-and-drop lands
      NOTHING in the dev host — Finder drags carry no `File.path` (removed
      in modern Electron; the scripted-era handler falls back to a bare
      name), Explorer drags arrive as `uri-list` payloads with no `File`
      objects, so the current `dataTransfer.files` handler is dead code
      live. Fix = consume `text/uri-list` / VS Code's uri-list mime in the
      drop handler, or retire the drop affordance so the composer doesn't
      invite a gesture that can't work.
- [ ] At the spec sign-off, a scatter rule card can sit partially under the
      gate card (R6 in the replay-harness check after the blur lift) — the
      scatter camera or card placement should keep every rule fully visible
      at sign-off.
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
- [x] ~~Question kinds `exhaustion` and `owner_human` have no card~~ pulled
      forward (2026-08-10, ticket 20 live pass): r3's repair budget spent
      and the run waited invisibly on the exhaustion question, exactly as
      predicted — both kinds now ride the needs_human feed card (title by
      kind, prompt falls back to payload.voice, free-text placeholder from
      the option). First live render pending the r3 crash-restore.
- [ ] Orchestrator narration reads near-verbatim across runs (user, after
      4 runs of the small BRD): journal-compared, no beat is string-equal
      run to run — it IS generated — but the fixed beats (opening,
      spec-signed, gate) get near-identical prompts and land on the same
      sentence shape every time, which reads memorized. Candidates:
      richer per-beat state in the narration prompt (name the actual
      rules/components/values), an anti-repetition style instruction, or
      sampling options if the port exposes them. Presentation-free zone —
      content-real is not in question.
- [ ] Canvas configured-state (type caption + Configurator byline) is
      keyed by node id and never re-associates: when a re-design renames a
      node (r3: join_accounts -> join_trades_accounts) the new id renders
      designer-fresh though its config cell exists — and repair-pass
      configure skips the completion sweep entirely (`if not ctx.repair`),
      so repaired nodes never re-light. A spec-door forward re-run heals
      both (full sweep); consider a repair-pass sweep or id-migration by
      label for the polish pass.
- [ ] VerdictCard keys Approve on `verdict === "verified"` — an approvable
      `smoke_clean` (or build-tier `unverified`) verdict hides its Approve
      button. Ticket 13's "smoke-clean approvable" is wire-true (the
      conductor sends the Approve option), pixel-false. A tier chip on the
      verdict card would price it, per 13.

None fire in the default demo walk; they matter the moment ticket 17's
real specialists surface extraction questions or a dataless run reaches
the gate.

## Comments

2026-08-10 (found during ticket 18's F5 verification; fixed immediately --
a stuck-run defect, not polish): the gap-round card stranded a live run.
Root cause chain, confirmed against the run journal (trade_positions-r3:
G1 resolved, G2 raised with a recommended option yet never auto-answered,
never resolved): question.raised events ride separate postMessages and the
envelope pump flushes per animation frame, so a round's cards can mount
before all members arrive; GapRoundCard initialized selections only at
mount, a click on a late member created a partial record without `free`,
send() threw on `s.free.trim()` mid-loop AFTER earlier answers went out,
and the one-shot `sent` latch left "Send answers" permanently disabled.
Fixed in Cards.tsx (fix commit on this branch): selections derive lazily
from complete per-question defaults (recommended preselect works for late
arrivals), Send re-arms when the pending set changes (core ignores
duplicate answers), and waive now sends the waive option's REAL id instead
of the literal "waive" (live-authored options need not use it -- same
stranding pattern otherwise). Latent since 15; first conductor-era F5 pass
surfaced it.

2026-08-10 (live-feel finding from the ticket-18 HITL F5 pass, user):
stage transitions need a breathing beat. Today a stage completes and the
next specialist's stream opens immediately while the orchestrator's
narration for the finished stage is still queued or streaming -- the room
wants: stage completes -> orchestrator speaks -> next agent starts.
Design tension to respect when fixing: 05/18 deliberately made narration
non-blocking (the walk never waits on prose; smoke depends on overlap),
so the fix is a paced choreography dwell at stage boundaries -- e.g. a
conductor-side boundary beat at demo pace (zero at fast/smoke pace), or
wait-for-narration-close with a hard cap -- NOT a return to blocking
narration. Decide the shape in this ticket's pass.

Same pass also confirmed on real pixels: the gap-round card fix (comment
above) -- multi-gap live round answered clean, preselects shown, Send
live; and ticket 18's beats (narration alongside stages, threaded
tool-grounded composer answer, hold propose-confirm -> boundary hold ->
resume) all read correctly at human pace.

2026-08-10 -- Pre-Citi build sweep (user lost the Mac Copilot
subscription; everything buildable landed so the Citi laptop session is
pure testing; commits cefda779 / 6f4e9eb1 / efac5e68). BUILT, live
pixel-check pending -- the checklist boxes stay for the live pass:
- Multi-select picker (canSelectMany + list contract) AND working drop
  (uri-list payloads from Explorer drags, windows drive form handled).
- Scatter reserves the gate card's band at sign-off (no rule under it).
- Sign-off leaders dropped (whole-spec signature reading).
- Intake stage-completed line reworded (dup feed line).
- Idle connecting state: Start disabled + hint until attach resolves.
- Persistent SCRIPTED chrome chip on provider fallback (+ feed warning).
- RunActive renders a banner (cleared on run start/end).
- Crash-restored run with a pending question announces itself.
- VerdictCard: Approve keyed on the conductor's approve option
  (smoke-clean approvable), tier chip in the eyebrow, honest smoke
  wording.
- Repair-pass configure sweep (stale Flow-Designer bylines heal).
- Stage-boundary breathing beat: conductor waits for the orchestrator
  queue to drain, 8s cap, demo pace only (shape decided per the
  2026-08-10 comment above).
- Narration variety: style rule (never reuse a sentence shape this run;
  anchor in the moment's particulars).
- Credits chip: renders credits (nano-AIU) or tokens, whichever the
  provider sent; nothing when neither.
Still open here: microcopy collection during live runs (the ticket's
original core), both-themes re-check of the new surfaces, and the
checklist ticks themselves.
