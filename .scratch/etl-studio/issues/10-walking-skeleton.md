# 10 - Walking skeleton: three layers wired end to end

Status: claimed
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
