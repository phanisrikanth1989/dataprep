# 03 - Agent core: TypeScript or Python?

Status: resolved
Type: grilling
Blocked by: 01

## Question

Does the agent core live in TypeScript in the extension host (deterministic
Python tools invoked as subprocesses) or in Python beside the engine
(vscode.lm tunneled to Python over local RPC)?

Decide with a real trade-off table:

- Streaming and cancellation across the extension<->core boundary.
- Vendoring cost: most agent/tool logic being copied in is Python today.
- The production-runtime story: which choice keeps "same core, new adapter"
  honest when the core later runs outside the editor against R2D2.
- Complexity of the vscode.lm adapter in each world (native calls vs RPC
  bridge), informed by ticket 01's facts.

## Answer

Resolved 2026-08-09 via grilling. Decision: **Python core beside the engine**,
with a React+TS webview and a thin TS extension shim. Layer terms (webview /
extension shim / agent core / LM bridge / provider port) recorded in root
`CONTEXT.md`.

**The three layers.**

- Webview: React + TypeScript (TSX), bundled static assets. budget_ui's
  React/canvas thinking ports here (JSX -> TSX).
- Extension shim: TypeScript, thin and dumb -- unavoidable because vscode.lm
  and webview hosting exist only in the extension host process. Three jobs:
  host the webview, spawn/supervise the agent core, carry the LM bridge.
  Zero agent logic; a few hundred lines of relay code.
- Agent core: Python, beside the engine. Orchestrator, specialists,
  elicitation, artifact bus, question channel, vendored tools, engine
  harness. All agent logic lives here.

**Trade-off table (the ticket's four axes, as they landed).**

| Axis | TS core in host | Python core beside engine | Verdict |
| --- | --- | --- | --- |
| Streaming/cancellation across the boundary | in-process, native | two extra local hops of tiny JSON over stdio RPC; sub-ms per hop; token batching to animation frames happens UI-side anyway; cancel = request-id message, <100ms perceived | TS cleaner; Python fully workable -- not decisive |
| Vendoring cost | tools are already argparse CLIs -> subprocess them | same tools import in-process; NO agent loop exists to vendor in either world (today's loop is Copilot's runtime + 8 language-neutral .agent.md prompts) | wash -- much weaker axis than the ticket assumed |
| Production honesty ("same core, new adapter") | needs Node on Citi servers -- Node does not exist there | core redeploys as a Python service; R2D2 = one HTTP adapter | **Python, decisively -- the deciding axis** |
| vscode.lm adapter complexity (ticket 01 facts) | native wrapping of parts/consent/errors | same wrapping + a serialization shim; bounded -- no Arrow marshalling, no JVM warmup analogue | TS simpler; accepted cost |

Decisive user facts from the grilling: production servers have no Node.js; a
possible (not certain) post-budget future is Google ADK, which is
Python-first; the user's backend fluency and explicit preference is Python
("React with TS for frontend, backend side of things in Python"); a second
bridge is acceptable given the Java bridge's track record, with one guardrail
-- the UI/UX must not take a hit (met: only small JSON crosses the wire,
never data; DataFrames stay inside Python tools and the engine).

**Sub-decisions.**

- Transport: stdio JSON-RPC with LSP-style framing. TS side uses the
  battle-tested `vscode-jsonrpc` library (request ids, cancellation,
  notifications built in); Python side speaks the same framing (~150 lines,
  hand-rolled or pygls-style). No sockets, no port allocation, nothing for
  endpoint security to notice; lifetime tied to the spawned child. Localhost
  socket is the known fallback if stdio ever hits a corp quirk (not expected
  -- Py4J already listens locally on these machines).
- Lifecycle: one core per VS Code window, spawned when the ETL Studio panel
  opens (not on activation); auto-restart on crash with a visible UI banner,
  never silent; SIGTERM on panel close / extension deactivate. Run state
  lives in file artifacts under a work dir, so a restart lands on the last
  artifact; full mid-run resume semantics belong to ticket 08.
- Narrative lock: the demo claim is "our Python runtime; the model provider
  is one adapter -- vscode.lm today, R2D2 tomorrow". R2D2 = adapter swap
  (core unchanged). ADK = re-host, not adapter swap -- cheap because
  same-language (prompts, tools, artifacts all port), and said in exactly
  those words when asked. The core's internals are NOT shaped around ADK
  concepts on a "might".

**Flows onward.**

- Ticket 07 (unblocked by this): the provider port is a Python interface;
  the vscode.lm adapter is split across the wire (TS shim serializes, Python
  side presents the port). 07 decides the port surface and where error
  normalization lives (shim vs Python adapter).
- Ticket 08: the runtime<->webview contract rides JSON-RPC notifications
  over the same stdio channel, relayed by the shim to webview postMessage.
- Ticket 10 (new, graduated from the implementation-slices fog): walking
  skeleton wiring the three layers end to end -- the bridge is the one new
  infrastructure risk, so it gets built and proven first.
