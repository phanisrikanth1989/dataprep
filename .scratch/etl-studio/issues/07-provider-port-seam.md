# 07 - Provider port and adapter seam

Status: open
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
