# 01 - vscode.lm facts

Status: open
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
