# 12 - Webview UI design

Status: claimed
Type: prototype

## Question

What does the webview actually look like? Ticket 06 fixed the content policy
(content real / presentation free; canvas hero with the feed docked beside);
this ticket fixes the look by prototyping it -- concrete mockups to react to,
not descriptions.

To settle:

- Layout: the canvas-hero + feed composition; where questions, gates, stage
  progression and the credit readout sit; what the screen does at each beat
  of a run (idle, streaming, question round, gate, verdict).
- The component vocabulary from 06, designed: thinking block (live preview
  line, collapse to "thought for Ns", reopenable), tool chips, the live
  line, provenance bylines on canvas nodes, failure/retry chips ("attempt 2
  of 3"), question cards, spec sign-off and code-gate views, the human gate.
- Aesthetic direction: AI-product polish (Claude/ChatGPT-class thinking UX --
  motion, shimmer, streaming feel) that lands in a Citi demo room.
- What ports from budget_ui's React canvas (nodes/edges/animation thinking)
  and what is rebuilt.

Not blocked by 08: mockups consume no real events, so look-and-feel can run
in parallel with the contract; 08's shapes constrain the working
implementation, not the design. Use the /prototype and frontend-design
skills; iterate live with the user.

## Comments

2026-08-09 — prototype session, iteration 1 (Claude). Two artifacts on this
branch, both double-clickable HTML, both five beats (idle / questions /
streaming / gate / verdict), keys 1-5 + r to replay:

- `demo/etl_studio/prototype-webview-ui.html` — v1: three structural variants
  (A Mission Control · B Instrument Bench · C Full-bleed Studio), switchable
  with arrow keys. User verdict: reads as budget_ui heritage with light
  improvements — not modern-AI-product enough. Kept as the arrangement
  comparison artifact.
- `demo/etl_studio/prototype-webview-ui-v2.html` — v2 showpiece, after the
  user chose "one killer version": full-bleed canvas + floating glass feed,
  warm-graphite elevation system (no border-boxes), product-scale type,
  camera choreography (leans into the active node), flowing lit edges,
  gate staged as a hold (desaturate + wash + one bright approve), verdict
  as the jade wide-shot. Content real-shaped throughout; conductor renders
  as state, never speech.

Iteration continues with the user's reaction to v2. Ticket stays claimed.
