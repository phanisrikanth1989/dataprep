# 10 - Walking skeleton: three layers wired end to end

Status: open
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
