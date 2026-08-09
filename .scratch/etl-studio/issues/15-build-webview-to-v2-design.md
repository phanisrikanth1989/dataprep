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
- Ticket 13 increment (semantics resolved there, 2026-08-09): the spec-gate
  card — question-card family anchored to the rules scatter, spec summary
  header, per-gap resolution chips, [Approve and sign] + [Request changes]
  with required free text, draft-N re-sign-off variant; ghost
  [Request changes] on the code-gate and verdict cards (red verdict drops
  [Approve job]); the hold flow (propose-confirm card, armed feed chip, hold
  question card with Resume/Stop/steer, HOLDING spine word); reject/hold
  resolution chips and spine un-fill while forward stages re-run. The
  scripted double run also exercises one hold and one gate reject.

Out of scope: live vscode.lm runs (rehearsal concern), `.vsix` packaging
(out of scope for the effort).

Unblocked: 03, 07, 08, 10 and 12 are all resolved.
