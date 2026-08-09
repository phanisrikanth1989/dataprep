# 08 - Runtime<->webview message contract

Status: open
Type: grilling
Blocked by: 02, 03, 04

## Question

What is the bidirectional message contract between the agent runtime and the
webview?

To settle:

- Event vocabulary replacing the old 10-event one-way stream (stage, nodes,
  edges, callout, gate, result, end...) -- what survives, what is new.
- The question/answer flow: how an agent question reaches the UI, how the
  answer returns and unblocks the run, timeouts/defaults.
- Sign-off flows (code gate, final approval) as real round-trips.
- Streaming thoughts (per ticket 06) as a channel.
- Resume semantics: reload the webview mid-run and reconstruct state.
