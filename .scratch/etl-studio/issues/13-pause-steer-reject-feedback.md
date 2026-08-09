# 13 - Pause/steer and reject-with-feedback semantics

Status: open
Type: grilling
Blocked by: 02, 04, 05, 08

## Question

What do pause/steer and reject-with-feedback actually DO -- the interaction
semantics ticket 08 deliberately left open after fixing their message shape
(`{question_id, choice, free_text?}`)?

To settle:

- Can the human pause or redirect a run outside the enumerated pause points at
  all in v1? (04 shipped autonomous-only; 05's propose-confirm and
  exhaustion-steer are the only steering that exists today.)
- Reject-with-feedback per gate kind: spec sign-off reject re-enters
  elicitation (02, provisional) -- flesh out that loop; what does reject mean
  at the code gate and at the human gate (a directed spec revision, a
  repair-loop entry, or a stop)?
- Does `steer` generalize beyond budget exhaustion, or stay scoped as 05
  deliberately left it?
- Prior art: the retired single-step/testing mode (one stage per turn, no
  auto-repair) -- does anything of it return?
