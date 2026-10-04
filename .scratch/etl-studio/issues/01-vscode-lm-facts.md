# 01 - vscode.lm facts

Status: resolved
Type: research

## Question

What are the hard facts of the vscode.lm surface the ETL Studio design must
build on -- with primary-source citations, no assumptions?

Specifically:

1. Stable vs proposed API: exactly what of `vscode.lm` is stable in current
   VS Code (`selectChatModels`, `LanguageModelChat.sendRequest`, message
   types, `LanguageModelChatTool` / tool-calling parts, `lm.registerTool` /
   `lm.invokeTool`, `registerLanguageModelChatProvider`), and what requires
   proposed-API flags (unusable in a normal install).
2. Streaming: the exact response stream shape (text parts, tool-call parts),
   cancellation semantics, and error types (`LanguageModelError` cases).
3. Multi-turn agent loops: constraints on running a long agentic loop from an
   extension -- consent prompts, user-initiation requirements, background
   use, rate limiting behavior.
4. Tool calling: schema declaration, the invocation round-trip, limits on
   tool counts / payload sizes.
5. Model availability: how models surface through `selectChatModels`
   (vendor/family/version selectors); whether the F5 Extension Development
   Host shares the main window's Copilot auth and model roster; what can
   only be verified on the Citi machine (end with an explicit on-machine
   checklist for the user). User-reported models in Citi Copilot chat:
   GPT-5.Sol, Claude Opus 4.8, Claude Sonnet 5 -- map to expected selector
   strings if documented.
6. Token/context limits per model (`maxInputTokens`, `countTokens`) and how
   quota/billing surfaces (user reports ~20k credits available; cost is
   context, not constraint).
7. Anything that would prevent the agent core from living behind a provider
   port -- API shapes that leak `vscode` types into agent logic.

Answer informs ticket 03 (agent-core language) and ticket 06 (real thoughts).

## Answer

Resolved 2026-08-09. Full findings with per-claim citations:
`../research/2026-08-09-vscode-lm-facts.md` (all facts stamped against
VS Code stable 1.132.0; Copilot-implementation details flagged separately).

Digest:

1. Everything the design needs is STABLE API: selectChatModels + sendRequest
   + streaming (since 1.90), tool calling (1.95),
   registerLanguageModelChatProvider + languageModelChatProviders
   contribution (1.104). No proposed flags needed for the demo path.
2. Streaming: response.stream yields TextPart | ToolCallPart | DataPart |
   unknown -- consumers MUST skip unrecognized parts (Copilot really emits
   proposed thinking parts and 'usage' data parts on stable). Cancellation
   via CancellationToken or breaking the loop. Errors surface in two places:
   the sendRequest promise and the stream iteration.
3. Consent: ONE modal dialog per consumer extension, ever (on first
   sendRequest; justification string rendered; declining = NoPermissions).
   After the grant: unlimited background requests, no user-gesture
   enforcement in code -- a long agent loop is fine. canSendRequest()
   pre-checks silently. Docs still require the first call from a user
   action.
4. Tool calling: private tools (no contribution point) suffice for a
   self-contained loop. Round-trip: Assistant msg with ToolCallPart ->
   User msg with ToolResultPart (callId-matched; sequencing enforced by
   Copilot). Copilot caps: 128 tools/request; toolMode Required = exactly
   one tool; tool schemas consume prompt budget.
5. No System role in stable (User=1/Assistant=2; languageModelSystem is
   proposed and runtime-enforced) -- emulate via a leading User message.
   Thinking parts are proposed-only (bears on ticket 06).
6. Limits: maxInputTokens + countTokens are the consumer surface; no stable
   output cap -- undocumented modelOptions.max_tokens works on the 1.132
   Copilot build. Input overflow = plain Error('Message exceeds token
   limit.') (not LanguageModelError); output overflow silently truncates as
   success. Quota: LanguageModelError named 'ChatQuotaExceeded'; rate
   limit: plain Error named 'ChatRateLimited' + temporary per-extension
   blocklist (Blocked). Per-request usage arrives as a trailing 'usage'
   DataPart -- usable for credit accounting in the demo.
7. Provider port: fully feasible -- every input is constructible from plain
   data and every output reducible to it. The adapter must wrap:
   instanceof-based part classes (sharpest edge), CancellationToken,
   Event/Disposable, the consent side effect, and normalize the three-tier
   error mess. Nothing forces vscode types into the core.
8. R2D2-as-provider path is open: provider-contributed models are visible
   to OTHER extensions via selectChatModels (stable, 1.104). Risk: Copilot
   Business/Enterprise "BYO model" admin policy can disable third-party
   providers -- on-machine check (ticket 09).
9. F5 dev host: loads all installed extensions and the same profile by
   default (Copilot roster present; auth sharing strongly inferred, not
   explicitly documented). Proposed APIs do NOT work under plain F5 on
   stable builds; --enable-proposed-api=<id> in launch args is the
   code-verified escape hatch.
10. Citi selector strings (GPT-5.Sol / Claude Opus 4.8 / Claude Sonnet 5)
    are undocumented anywhere; the research file ends with a copy-runnable
    probe extension to capture them -- now ticket 09 (task).

Design recommendation recorded in the research: build the demo against
stable API only (System-role emulation, skip unknown parts); keep
--enable-proposed-api as a verified fallback if thinking-part streaming is
wanted for the UI.
