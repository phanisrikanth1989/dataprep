# 07 - Provider port and adapter seam

Status: resolved
Type: grilling
Blocked by: 03

## Question

What exactly is the provider-port interface, and how is the seam enforced?

To settle:

- The port surface: chat (messages in, streamed parts out), tool declaration
  and invocation, token counting, cancellation, errors.
- What the vscode.lm adapter implements (in the language decided by ticket
  03), and what the test-double adapter implements (in scope per map Notes;
  a live second adapter is out of scope).
- Enforcement: how we guarantee the agent core never imports editor or
  provider specifics (lint rule, package boundary, CI check -- pick the
  mechanism).
- What R2D2 will plausibly need from the port (HTTP gateway, wire format
  unknown -- design for the unknown without inventing details).

## Answer

Resolved 2026-08-09 via grilling (one 12-question round + one clarification
round). Standing assumption locked with no objection: the port supports
concurrent in-flight requests (orchestrator narrates while specialists run,
per ticket 05); the wire multiplexes by stream id.

**Port speaks an ideal, provider-neutral chat language (Q1).** First-class
`system` role; `tool_call` / `tool_result` are first-class content items on
messages. Adapters own degradation: the vscode.lm adapter maps system -> the
leading-User-message emulation and tool items -> the Assistant-then-User
two-message convention (ticket 01 facts). Core prompts never encode provider
quirks.

**Content items include images in v1 (Q2).** text | image (base64 + mime),
guarded by an `image_input` capability flag -- the BRD door extracts images
and the doc-normalizer plausibly sends them to the model; whether the
vendored chain really does gets checked at vendoring time, and the port
supports it either way.

**Call shape (Q3).** One method: `chat(request) -> async iterator of typed
stream events`. Cancellation = cancelling/closing the iterator
(asyncio-native); adapter cleanup propagates the JSON-RPC cancel so the shim
cancels the vscode token. Timeouts are core-owned (asyncio.timeout around
consumption); adapters never time out on their own.

**Stream event vocabulary (Q4).** `text_delta`; `thinking_delta` (optional
per ticket 06 -- absent changes nothing); `tool_call` (complete call: id,
name, parsed args); `usage` (raw provider payload dict + adapter-normalized
fields only where the adapter is confident; UI shows what is present, never
estimates, per 06); `done` (finish_reason: stop | canceled | unknown --
vscode stable exposes no finish reason and output truncation is silent
success, so `unknown` is the honest value today). Forward-compat rule:
consumers must skip unrecognized event kinds; adapters may emit kinds the
core does not know.

**Errors (Q5).** One neutral exception family raised from the call/iterator
(not error events): `ConsentDenied`, `ModelNotFound`,
`RateLimited(retry_after?)`, `QuotaExhausted`, `InputTooLarge`,
`ProviderUnavailable` (bridge down/crashed), `RequestCanceled`, and a
`ProviderError(cause)` fallback. No vscode-flavored names anywhere in core.
**Adapters never retry**: they classify and raise; the core owns backoff and
re-issue, so 06's "Rate-limited -- retrying (2)" chips reflect real core
state, never an adapter's hidden loop.

**Normalization location (Q6) -- the question ticket 03 left open.**
Mechanical TS shim, semantic Python adapter. The shim converts
instanceof-discriminated parts to tagged JSON and forwards errors verbatim
({code, name, message}); all semantics -- error-string matching, taxonomy
mapping, system-role emulation, tool-convention mapping, part->event mapping
-- live in the Python vscode adapter. The wire speaks "serialized vscode".
Payoff: policy sits in one language; Citi-build error-string drift is a
Python-only fix (no shim rebuild); the shim stays 03's dumb relay; the
double and the vscode adapter are symmetric Python implementations of the
same port.

**Model discovery (Q7).** `list_models() -> [ModelInfo(id, vendor, family,
name, max_input_tokens, capabilities)]`. Core picks by config-supplied
selectors (real Citi strings land when ticket 09 runs); each chat request
carries the chosen model id. Per-stage selector config with a single
default. No roster change-event subscription in v1 -- re-list on demand.

**Token counting and options (Q8).** `count_tokens` is an optional
capability (`counts_tokens` flag on ModelInfo; core must degrade -- its only
core use is prompt-budget checks against max_input_tokens; the credit
readout never uses it, per 06). Request options are typed only:
`temperature?`, `max_output_tokens?` (vscode adapter maps to the
undocumented-but-working modelOptions.max_tokens), `stop?`. No open
provider-options dict crosses the port; provider-specific knobs are adapter
config.

**Consent (Q9 -- user chose b).** No warm-up call. The one-time vscode
consent modal fires whenever the first real model call happens (in practice
burned during skeleton development long before any demo); a decline
surfaces as `ConsentDenied` through the normal visible error path. The
vscode `justification` string is adapter config, not port surface.

**Test double (Q10).** Scripted playlist, deliberately simple: a JSON/YAML
fixture of responses consumed in order (each chat call takes the next),
streamed with fake cadence; scripted tool calls, thinking deltas and usage
events; error injection ("raise RateLimited on call N") to exercise 06's
failure rendering offline. No request-matching DSL. Adapter selection is an
entrypoint config field (provider: vscode_lm | double) read only at wiring
-- nowhere else in core.

**Seam enforcement (Q11).** Layout law + tripwire. Layout: `core/` (all
agent logic plus the port definition itself) never imports from `adapters/`
(vscode_lm/, double/ -- they import core's port types); only the entrypoint
wires an adapter into the core. Tripwire: one ~30-line pytest that AST-walks
core/ and fails on any import of `adapters` or vscode-anything -- zero new
tooling. Kept despite the effort's testing deprioritization: it is an alarm,
not ceremony. The TS shim's zero-agent-logic rule stays review-enforced.

**R2D2 (Q12 -- user: get it working first, assume the safest).** Nothing
speculative. The port carries no R2D2-only surface: neutral vocabulary
(already required by Q1/Q5), capability flags only where the demo's own
adapters actually differ (`image_input`, `thinking`, `counts_tokens`), no
opaque metadata pass-through field, and auth is entirely an adapter concern
if a real second adapter ever exists. If R2D2 needs more someday, the port
is revised then, from facts.

**Mechanical defaults (recorded, not grilled).**

- Wire methods on the existing stdio JSON-RPC channel (LM family only;
  ticket 08 owns the webview families): `lm/listModels`, `lm/countTokens`,
  `lm/chat`. `lm/chat` params carry a core-generated stream id; the shim
  emits `lm/chatEvent` {streamId, part} notifications per part and resolves
  the request at stream end; cancellation rides JSON-RPC's built-in
  $/cancelRequest, wired by the shim to the vscode CancellationTokenSource.
- Unknown stream parts are forwarded by the shim as {kind: 'unknown', ctor,
  mime?} -- never dropped silently. The Python adapter maps known ctor names
  even where the shim cannot instanceof them; notably, proposed-API thinking
  parts reach stable consumers as unnameable parts (ticket 01), so thinking
  deltas may be recoverable this way even without the proposed-API flag --
  ticket 09's probe records what actually arrives on the Citi build.
- The port is a Python ABC (ProviderPort) with plain dataclasses for
  requests, messages, content items, events and model info; exact module
  paths land in the implementation slices under the Q11 layout.

**Boundaries held.** 08 owns runtime<->webview message shapes; 09 fills the
real selector strings and probes thinking-part arrival; 10 builds its
skeleton to this surface (its provisional send+stream+cancel is this chat
call minus tools). Terms recorded in root CONTEXT.md: Adapter, Test double
added; LM bridge sharpened (channel, not adapter).
