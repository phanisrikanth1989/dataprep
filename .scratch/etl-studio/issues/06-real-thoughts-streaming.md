# 06 - Real thoughts: what streams to the UI?

Status: open
Type: grilling
Blocked by: 01

## Question

What does "real reasoning and state, never canned" concretely mean on the
webview -- raw token streams per agent, curated-but-real agent output, or
layered (curated default, expandable raw)?

To settle, informed by ticket 01's facts on what vscode.lm exposes:

- What is actually streamable per model call (text deltas; whether any
  reasoning/thinking content exists beyond output tokens).
- Per-agent framing: how the UI attributes a stream to a pipeline stage.
- What replaces the old presenter's canned _LABEL / _CALLOUT / THOUGHTS
  layers.
- Data posture: the old presenter was deliberately data-free; the new UI
  shows real content to the human who owns the input. State the new rule.
