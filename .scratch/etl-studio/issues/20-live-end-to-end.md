# 20 - Live end-to-end in the dev host

Status: open
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
