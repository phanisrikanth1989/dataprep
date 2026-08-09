# 12 - Webview UI design

Status: open
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
