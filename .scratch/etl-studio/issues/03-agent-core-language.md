# 03 - Agent core: TypeScript or Python?

Status: open
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
