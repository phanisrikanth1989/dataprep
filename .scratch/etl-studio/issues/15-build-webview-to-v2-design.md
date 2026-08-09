# 15 - Build the webview to the v2 design

Status: open
Type: task

## Question

Implement the real React webview on the walking skeleton to ticket 12's
settled design — `demo/etl_studio/prototype-webview-ui-v2.html` is the design
of record — consuming ticket 08's envelope end to end.

Scope:

- Port the v2 token system, component vocabulary, canvas (layout() math,
  camera choreography, assembly/flow animation) and both themes into
  `demo/etl_studio/extension/webview/` (React + TS, per ticket 03 layers).
- Real events replace the beat scrubber: reducer per 08 (attach/replay from
  `ui_journal.jsonl`, per-part stream forwarding with port-to-pixel ids, the
  one question lifecycle, credits accumulated from usage parts). The five
  beats become emergent states of the run, not modes.
- Drive it against the test double first (07): a scripted run that reaches
  every beat — idle, elicitation round, streaming activity, code gate,
  verdict — plus failure states (retry pills, finish_reason "error",
  crash-restart reattach with seq continuity).
- VS Code theme-following: map the token layer onto the webview's
  light/dark theme class; bundle fonts locally — no CDN inside the webview.
- `npm run smoke` stays green; the seam tripwire stays green; the prototype
  files stay untouched as the design record.

Out of scope: pause/steer surfaces (ticket 13 — they land on this system as
an increment), live vscode.lm runs (rehearsal concern), `.vsix` packaging
(out of scope for the effort).

Unblocked: 03, 07, 08, 10 and 12 are all resolved.
