# 10 - Walking skeleton: three layers wired end to end

Status: resolved
Type: task
Blocked by: 03

## Question

Build the minimal three-layer skeleton proving the architecture decided in
ticket 03, before any agent logic exists:

- Extension shim (TS): activates, opens the ETL Studio webview panel, spawns
  the Python agent core under the repo venv, speaks stdio JSON-RPC
  (vscode-jsonrpc on the TS side, LSP-style framing), auto-restarts it with a
  visible banner on crash, SIGTERMs it on panel close / deactivate.
- Agent core (Python): starts, speaks the same framing, answers a ping.
- Webview (React+TS): renders, round-trips one message
  webview -> shim -> core -> shim -> webview.
- LM bridge: one echo request through the provider port -- live vscode.lm
  adapter where Copilot models exist, test-double adapter everywhere else --
  with streamed chunks and cancellation crossing the wire.

The port surface here is provisional (send + stream + cancel only); ticket 07
formalizes it.

Done when the webview round trip and a streamed, cancellable LM echo both
work in the F5 dev host. This de-risks the bridge -- the one new
infrastructure risk in the ticket 03 decision -- ahead of the design tickets
landing.

## Answer

Resolved 2026-08-09. Built, CLI-verified, and confirmed by the user in the
F5 dev host -- all seven checklist steps green: webview round trip, live
Copilot echo (consent modal paid, usage/AIU chip from the real DataPart),
mid-stream cancel crossing the wire into the vscode token, crash -> visible
banner -> auto-restart with journal seq continuity, clean SIGTERM on panel
close. Live-adapter proof is Mac-provisional (free-tier Copilot); the Citi
machine repeat lands with rehearsal.

What exists, all under `demo/etl_studio/` (commit 2f8e506a):

- `extension/` -- TS shim: panel host, core supervisor (spawn on panel
  open; interpreter = etlStudio.pythonPath setting -> repo `.venv` ->
  python3; auto-restart with 3-crashes/60s -> dead + Restart button;
  SIGTERM on close/deactivate), mechanical `lm/*` bridge vendored from
  lm-probe. `engines.vscode ^1.104`; LanguageModelDataPart/ThinkingPart
  resolved dynamically (absent from the floor's types, present at runtime).
- `core/` -- Python stdlib only: `rpc.py` (LSP framing, JSON-RPC 2.0,
  `$/cancelRequest` both directions), `envelope.py` (08 envelope),
  `journal.py` (seq-owning `ui_journal.jsonl`), `port.py` (ProviderPort
  ABC, 07 event kinds + full neutral exception family), `app.py`
  (attach/replay, ping, echo streams, visible provider fallback).
- `adapters/` -- `vscode_lm` (semantic half: `mime="usage"` ->
  total_nano_aiu, NoPermissions -> ConsentDenied) and `double` (scripted
  playlist). `main.py` is the sole core/adapters wiring point;
  `tests/test_seam.py` (AST tripwire) guards the seam.
- Webview: React feed/streams/lifecycle banners on VS Code theme tokens
  only -- ticket 12 owns the real design.

Facts later tickets depend on:

- F5 path: open `demo/etl_studio/extension`, F5, then "ETL Studio: Open".
- `npm run smoke` (`extension/scripts/smoke.mjs`) is the editor-free wire
  proof (20/20 this session) -- reusable as the slices grow the contract.
- Repo `.venv` exists (python 3.14.6, `[dev]` extras), created at the
  user's direction; `.venv/` + `dataprep.egg-info/` sit in
  `.git/info/exclude`, root `.gitignore` untouched.
- ETL Studio's one-time consent dialog is already burned on this Mac.
- Provisional contract extensions to reconcile in the implementation
  slices: `stream.close` finish_reason `"error"` (beyond 07's
  stop|canceled|unknown -- an errored stream never yields done but still
  needs its close edge); `shim.restart` webview->shim command (08 gave the
  shim only shim.lifecycle + editor.*); run_id fixed to `"skeleton"` until
  the conductor owns real runs.

## Comments

**2026-08-09 (build session):** Skeleton built and CLI-verified; the F5
dev-host run (this ticket's done-when) remains with the human.

- Layers landed under `demo/etl_studio/`: `extension/` (TS shim -- panel
  host, core supervisor with visible restart policy, mechanical LM bridge
  vendored from lm-probe), `core/` (Python -- hand-rolled LSP-framed stdio
  JSON-RPC, 08 envelope + ui_journal attach/replay, provisional provider
  port), `adapters/` (semantic vscode_lm adapter, double playlist),
  `main.py` entrypoint as the only core/adapters wiring point (07 seam law).
- Scope followed 08's sharpening: the skeleton proves attach/replay plus one
  stream family end-to-end (envelope, journal-owned seq, stream id port to
  pixel), not just a bare ping.
- Evidence: `extension/scripts/smoke.mjs` drives the core over the real wire
  with the same vscode-jsonrpc client the shim uses -- 20/20 checks green:
  attach on a fresh journal, ping round trip, auto provider falling back to
  the double VISIBLY (health.provider_fallback before stream.open), streamed
  echo with text deltas + usage + close(stop), mid-stream cancel ->
  close(canceled) with no trailing deltas, skeleton.crash -> exit 13 ->
  restarted core continues the journal (seq 17 -> 18), full-fidelity replay
  across the restart, SIGTERM -> clean exit 0. Seam tripwire
  (`tests/test_seam.py`) green standalone and under pytest.
- Provisional extensions recorded while building: stream.close carries
  finish_reason "error" beyond 07's stop|canceled|unknown (an errored stream
  never yields done but the webview still needs the close edge);
  "shim.restart" added as a webview->shim command for the dead-state Restart
  button (08 gave the shim only shim.lifecycle + editor.*); run_id fixed to
  "skeleton" until the conductor owns real runs.
- Environment: repo `.venv` created at the user's direction (python 3.14.6,
  `.[dev]` extras; `.venv/` and `dataprep.egg-info/` kept out of git status
  via `.git/info/exclude` -- root `.gitignore` is outside the allowed folder).
  Shim resolves the interpreter as etlStudio.pythonPath setting -> repo
  `.venv` -> python3.
- A green F5 on this Mac exercises free-tier Copilot -- live-adapter proof
  stays Mac-provisional until a Citi-machine run, per the provenance rule.
