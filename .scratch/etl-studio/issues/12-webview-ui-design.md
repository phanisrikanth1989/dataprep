# 12 - Webview UI design

Status: resolved
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

## Answer

Resolved 2026-08-09 across two live iterations with the user (/prototype UI
branch + frontend-design). The settled direction is the **v2 showpiece** —
user verdict "neat and elegant … perfect" after choosing "one killer version"
over three modernized variants.

**Artifacts** (committed on `feature/demo-vs-plugin`; double-clickable; five
beats each — idle / questions / streaming / gate / verdict; keys 1–5, r
replays, t toggles theme):

- `demo/etl_studio/prototype-webview-ui-v2.html` — **the design of record.**
- `demo/etl_studio/prototype-webview-ui.html` — v1, three structural variants
  (Mission Control / Instrument Bench / Full-bleed Studio). User verdict:
  budget_ui-heritage dashboard, not modern enough. Kept as the
  arrangement-comparison record; its A-structure feed column + C-structure
  full-bleed canvas merged into v2.

**Layout.** The canvas IS the app (hero per 06), full-bleed with a drifting
dot grid; the feed floats over it as a first-class glass column left (392px)
with composer (08's `ask`); run spine bottom-center (stage segments + gate
diamonds + the current stage word — the single uppercase element); brand chip
top-left; run + credits chips top-right. No steppers, rails, or status bars.

**Aesthetic system.** Warm graphite ground (#131110), ember/copper as the one
live accent, jade = verified, violet = code, sky = sources; elevation instead
of borders (tonal fills, layered shadows, inset highlight; strokes only for
focus/active); product-scale type — system sans 14–15px body, Archivo for
wordmark / stage words / "Verified", Plex Mono only for code, paths, values.

**Motion language.** Spring entries; assembly choreography (nodes scatter →
glide into the DAG, edges draw, then flow); **camera choreography** — the
canvas leans into the node being configured (~0.9), pulls to the gate cell
(0.74), goes wide for the verdict; lit edges carry flowing dashes; the gate
is staged as a hold (canvas desaturates under a breathing wash, one bright
approve button); verdict = jade sweep + output bloom. Reduced-motion
collapses all of it.

**Component vocabulary** (06's policy, designed): orchestrator-only messages
(soft blocks, glowing identity dot); thinking blocks that spring shut into
reopenable "Thought for Ns" pills; tool pills with expandable real output;
the live line as a shimmering one-liner inside the observed activity window;
provenance bylines as soft chips (Flow Designer / Configurator /
"Configurator · now"); question rounds as cards — blocking/advisory severity
dots, recommended-preselected options with radio + why-line, free text,
waive, "nothing times out"; code-gate card (meta chips, verbatim cell,
validator line, approve + ask); verdict card (display-scale VERIFIED, stats,
borderless zebra diff table, human-gate strip); calm-real failure pills
("attempt 2 of 3", "rate-limited — retrying (2)"); resolution chips recording
answers in-feed; the feed is cumulative (earlier beats ride above, recessed —
08's replay made visible). The conductor renders as state only (spine,
gates), never speech.

**Interrupt placement.** Questions, the gate and the verdict anchor to their
subject on the canvas — cards live in viewport space (never scaled) with
dashed leaders; the canvas spotlights the implicated nodes and blurs the
rest.

**Themes.** Dark is default and the demo lead; a full token-level light mode
(warm paper, white glass, copper/jade/violet re-cut for contrast) toggles
live (☀/☾, key t, `&theme=light`). Production posture: the webview follows
VS Code's theme — the pair proves the token layer supports it. Fonts come
from a CDN in the prototype; the real webview bundles them.

**budget_ui port verdict** (ticket question): ports — the layout() layered-
DAG algorithm (math verbatim), edge bezier construction, the assemble-then-
wire choreography concept, fit-to-viewport scaling (generalized into the
camera). Retired — the entire instrument skin (navy tokens, bordered boxes,
mono-caps chrome), node anatomy, rail/stepper/gate/result components, and
callouts (replaced by bylines + anchored cards).

**Content discipline held:** every string is real-shaped from the
trade_positions run (04's stages, 08's idle-two-doors and question grammar,
09's credits readout); no canned reasoning; specialist content carries no
response affordances.

Deviation from /prototype's capture default, on record: prototypes stay
committed on the working branch instead of a throwaway branch — repo
precedent (budget_ui's committed prototype HTML) treats demo/ prototypes as
first-class primary sources.

Graduated: ticket 15 (build the webview to this design). Pause/steer
surfaces are deliberately absent — ticket 13 owns them; they land on this
system as an increment.

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

2026-08-09 — iteration 2 (Claude). User verdict on v2: "neat and elegant";
asked for a light mode. Added to v2 as a full token-level light theme (warm
paper ground, white glass, copper/jade/violet accents re-tuned for contrast)
with a live toggle: ☀/☾ button in the prototype bar, key `t`, shareable via
`&theme=light` in the URL. Dark stays the default. Product note recorded: the
real webview should follow VS Code's theme (light/dark pair mapped at the
token layer), so proving both modes here de-risks that.
