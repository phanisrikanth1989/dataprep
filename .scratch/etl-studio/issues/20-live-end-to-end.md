# 20 - Live end-to-end in the dev host

Status: claimed
Type: task
Blocked by: 15, 16, 17, 18, 19

## Question

Attach ticket 15's webview to the real runtime and run the full
trade_positions job live in the F5 Extension Development Host -- the
destination's demo path end to end, no scripted sources left in the path.

Implements: the destination line itself; ticket 08 (contract live end to
end), ticket 06 (real thoughts on screen from a real run); editor.* shim
handlers land here (grilled 2026-08-10).

Scope:

- Replace 15's scripted event sources with the live conductor feed -- same
  reducer, same contract; `fetch_artifact` zoom against the real bus.
- editor.* shim handlers built out from the skeleton's stubs in `panel.ts`:
  `editor.pick_file` (BRD door's native file pick -- webviews cannot open
  dialogs) and `editor.open_file` (whole data files open in the real
  editor, never the feed).
- Demo input vendored: copy `agents/examples/demo_brd/trade_position_demo.docx`
  into `demo/etl_studio/examples/` so the demo folder is self-contained
  (data copy, not a code import).
- Full BRD-door run on the live vscode.lm adapter: pick the vendored BRD,
  answer elicitation in the UI, sign off the spec, watch the canvas
  assemble from artifact_written events, approve the code gate, get a
  harness verdict, approve at the human gate. Plus one typed-door run that
  climbs the tier by attachment.
- Exercised live in the same sessions: one hold + steer, one gate
  Request-changes, one mid-run crash-restore reattach (kill the core;
  seq continuity on screen), credits accumulating from real usage parts.
- Reconcile any contract gaps the live wiring exposes (the journal is the
  record); `npm run smoke` and the seam tripwire green at close.

Out of scope: Citi-machine rehearsal and the replay story (separate fog
entry -- live-adapter proof here stays Mac-provisional per the map's
provenance rule); `.vsix` packaging (out of scope for the effort).

Invariants: all new code under `demo/etl_studio/`; engine read-only;
nothing outside the folder modified.

Done when the user confirms the full run in the F5 dev host on this Mac --
both doors demonstrated, the beats 15 scripted now emerging from real
events, no scripted sources anywhere in the path.

## Comments

2026-08-10 -- Deferred from ticket 16 (user decision: F5 verification waits
until real things are present; smoke's editor-free wire proof is green).
The conductor swap changed a few visible beats the live pass should
confirm alongside this ticket's own list:

- [ ] Injected G0 card: a dataless typed run shows a three-gap round
      (G0 "attach data" + G1 + G2); answering G0 with paths in the
      free-text row completes the round and the run reaches `verified`.
- [ ] Configure retry choreography: the rate-limit beat is now a real
      re-issue -- errored stream close, retry chip, fresh Configurator
      stream (attempt 2) -- confirm it reads calm, not broken.
- [ ] Draft-2 walks re-materialize: a second "Materializer · wrote
      golden/" feed line after any re-sign-off is expected (honest
      re-materialization), not a duplicate-event bug.
- [ ] Hold -> steer live: directed interpreter re-run, draft-2 card,
      forward spine segments un-filling.
- [ ] Crash-restore live (Ctrl+Alt+Shift+K mid-run): banner, silent
      re-walk, zero duplicated feed items, seq continuity on screen.
- [ ] Bus spot-check after a run: `work/<job>-rN/` holds the canonical
      artifacts, golden/, runs/, history/<artifact>.<k>, audit.jsonl.

2026-08-10 -- From ticket 17's live probe (contract gap to reconcile here):
the vscode.lm adapter surfaced NO usage DataParts on this Mac, so the
credit readout counts scripted turns only and shows nothing for live model
calls. Confirm whether the shim drops the part or the local provider never
emits it, and reconcile (06's rule stands: absent part -> no number, never
an estimate). Likeliest read: the nano-AIU usage part is a Citi-gateway
behavior (ticket 09 observed it only there); public Copilot on the Mac may
never emit it on any plan/model -- so verify the credits pipeline on the
Citi machine, and treat Mac silence as expected, not a shim bug. Also already done by 17, from this ticket's list: the demo
BRD + CSVs are vendored under demo/etl_studio/examples/.

2026-08-10 (ticket 18's live probe) -- usage-parts update, supersedes the
"NO usage DataParts on this Mac" read above: the live adapter NOW surfaces
usage parts on every stream (20/20 on the probe run), but in OpenAI token
shape (prompt_tokens / completion_tokens / copilot_usage.token_details) with
no nano-AIU field -- so total_nano_aiu stays unnormalized and the readout
still shows nothing for live turns. The reconcile here is a normalization
decision (map raw token shapes? still gateway-only nano-AIU?), to be settled
against the Citi gateway per the note above. Probe cost for one full BRD
run with the ticket-18 orchestrator: ~89k tokens (80k prompt / 9.4k
completion).

2026-08-10 -- User sequencing for the live pass (recorded ahead of start;
this ticket starts only on the user's explicit go, not as a default
frontier pick): run live end to end with a small document first, then a
bigger, more complicated document; only once both work, fix whatever
those runs expose -- the fixes belong to this ticket. .vsix packaging
reconfirmed not needed.

2026-08-10 -- Claimed; pre-run build landed (commit b3ff9683). Survey
found the scope list mostly already real: the webview has ridden the live
conductor feed since 16 (no scripted event sources left to replace;
LIVE_SLOTS covers all seven model moments -- five specialists,
orchestrator, diagnostician), editor.pick_file landed earlier, examples/
vendored by 17. What this commit adds: editor.open_file end to end --
human-gate payload gains ``files`` (actual output beside its golden, real
bus paths), the verdict card renders them as "Open in editor" chips, the
shim opens them beside the panel (06's whole-files-never-the-feed).
fetch_artifact stays a wire capability; no webview zoom surface exists
yet (that's 21's renderer-gap territory). Verified: typecheck/esbuild
clean, smoke 93 green, seam green, ``files`` wire-verified in fresh smoke
journals. Pixel proof of the chips rides run 1. Stale-state check:
work/_skeleton holds two ENDED dev runs (r1/r2) -- panel will boot-restore
the finished r2 view; the overflow menu's New build reaches the composer.
autorun marker: only the inert .consumed file present; no hijack risk.
Next: run 1 (small document = vendored trade_position_demo.docx, BRD
door, live adapter), user-driven in the F5 dev host.

2026-08-10 -- Run 1 findings (live, F5 dev host):
- Drag-and-drop of the BRD onto the composer lands nothing (user, first
  attempt). Scripted-era handler; live-dead for structural reasons --
  detail recorded on ticket 21's existing picker/drag item. Unblock:
  attach via the picker (editor.pick_file), which is live-capable.
  Fix-phase decision rides this ticket's close-out or 21.
- Live normalizer (r3, BRD + 3 attached CSVs) located everything right
  (CSVs -> sample inputs, table:1 -> expected output, prose consumed) but
  omitted table:0 (the section-2 source-to-target mapping table) from the
  coverage_map while filing it in extra_sections -- normalize_validate
  fail-closed and raised needs_human, card rendered and answerable (the
  17-era pull-forward earning its keep). Recovery path = free-text steer,
  re-find round. Fix-phase candidate: prompt nudge so spec tables consumed
  into schema/rules get coverage_map entries like prose does, else the
  demo BRD trips this card every run.
- r3 repair-loop burn, root-caused from the journal + reports: the
  vendored harness maps golden outputs to job components BY COMPONENT ID
  (wants id == "trade_positions"); the live designer named it
  output_trade_positions. Diagnostician got owner+evidence right every
  pass but its fix field restated the wrong id (19's "fix field
  off-target" item, reproduced live 3/3) -- three passes reproduced the
  same job, budget exhausted, and the exhaustion question raised
  INVISIBLY (21's predicted gap). Landed in response (same commit):
  exhaustion/owner_human ride the needs_human feed card; designer prompt
  now carries the OUTPUT ID CONTRACT line. Unblock plan: reload window ->
  crash-restore re-raises the card -> Steer routes the id fix through the
  interpreter (an uncapped human act; the forward re-walk is a spec-door
  full reconfigure, which also re-lights the orphaned join nodes).
- Component vocabulary canonicalized (user direction, this session): the
  designer prompt itself taught the t-alias ("e.g. tPythonDataFrame") --
  now canonical-only prompts, "never author" alias phrasing in the config
  reference, and knowledge.canonical_type() normalization at all three
  parse seams (design/configure/assemble), so canvas and job.json speak
  one vocabulary whatever the model writes. Proven: smoke fixtures author
  tJoin/tPythonDataFrame, fresh smoke bus holds Join/
  PythonDataFrameComponent, 93 checks + engine walk green.
- Thought-for accordions render only streamed parts: tool chips when the
  turn made tool calls; thinking deltas never arrive on this Mac (09's
  probe, reasoning_tokens 0), so no-tool turns show an empty body --
  expected here, re-check on the Citi gateway (ticket 22).
