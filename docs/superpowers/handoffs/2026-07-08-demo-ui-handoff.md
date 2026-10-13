# Handoff: Demo UI for the ETL Agent System ("budget-unlock" demo)

- **Date:** 2026-07-08
- **Branch:** (new work; decide at start -- likely a fresh `feature/demo-ui` cut from `feature/real-brd-ingestion`)
- **First action for the new session:** `superpowers:brainstorming` to finalize the UI/presenter design
  (the requirement + all architecture decisions below are ALREADY agreed -- brainstorm the remaining
  UI-design opens, then `writing-plans`, then build). Pull in `frontend-design` + `dataviz` skills for
  the visual layer. Do NOT write code before the design is user-approved.

---

## 1. Why (the business context)

The multi-agent ETL system runs today inside the real Citi VS Code Copilot and WORKS (demoed to the
immediate manager; live-tested this session end-to-end on a complex BRD -- built a runnable job + ran
clean). Next audience: the **super-manager + business people**. You can't show them VS Code and call it
a demo. Citi has a real budget path for agentic AI, but it's a proposal + 3-4 months of bureaucracy.
The play: **wrap the working agent system in a polished chatbot-style web UI** and demo it as if it's a
finished product, to unlock budget NOW. This is **real capability, staged delivery** -- the agents
genuinely run; we're adding a presentation veneer + a run-driver, NOT faking the tech.

## 2. Scope (sharp)

A UI for the **AGENT SYSTEM** (the orchestrator + specialists + the doc-normalizer front door), **NOT**
a UI for the ETL engine. Business user uploads a BRD -> watches a friendly, visual "the system is
building your pipeline" experience -> sees the final built + tested pipeline.

## 3. Locked architecture decisions (agreed with the user)

- **Operator-in-the-loop.** VS Code is NOT auto-started. After the frontend upload, a human operator
  (you) manually triggers the Copilot orchestrator run (real-BRD mode). This honestly sidesteps the
  fact that Copilot's agent chat is a human-in-the-IDE flow, not headlessly triggerable.
- **Server = a dumb Citi-internal relay/queue.** Laptop -> Citi server REST calls are ALLOWED
  (confirmed by the user) and stay on Citi infra (not public cloud). The laptop does ALL the outbound
  (GET the uploaded doc, POST the narrative up); the server never needs to reach into the laptop (corp
  firewalls block inbound anyway). Frontend <- server via **SSE**.
- **Plumbing is deterministic local scripts, NOT LLM agents.** Two small plain-Python pieces on the
  laptop: (a) a **fetcher** (pull the uploaded doc from the server into the input dir; for MVP the
  operator could even click-download it), and (b) a **relay/watcher daemon** that WATCHES
  `agents/work/<job>/` + `audit.jsonl` (the files the agents already write) and POSTs changes up as
  they appear. **The Copilot agents stay 100% UNCHANGED** -- do not make them do HTTP or touch the
  hardened `extract_doc.json` artifact-bus contract.
- **Relay a business-readable, DATA-FREE narrative -- not raw artifacts.** The server/frontend only
  ever see clean summaries + graph structure, never the raw `extract_doc.json` (ugly + carries real
  sample values). This is also the whole egress story.
- **No LLM at demo time.** Narration text = canned per-stage templates + the REAL reasoning the run
  already wrote into the artifacts (low_confidence flags, the flow-designer's rationale). The
  presentation layer only SURFACES what the real run produced; it generates nothing new.
- **Frontend = plain HTML/CSS/JS** (SVG/canvas for the diagram, CSS for animation). **TEXT + VISUALS
  ONLY -- no voice/audio/TTS.**
- **Demo doc = synthetic + no-intervention** (authored so it flows end-to-end without hitting a
  blocking human gate). Synthetic => the external-relay egress worry evaporates.

## 4. THE hard principle: NO HARDCODING / NO GOLDEN-REPLAY

Everything runs **LIVE**. There is **no canned/golden-replay fallback** and **no doc-specific
scripting** -- because the audience may upload their own neat BRD, or (the most impressive moment) ask
to "change a rule and re-run," and a hardcoded demo dies exactly there.

> **The presenter is GENERIC: it renders whatever the ACTUAL artifacts contain.** The flow-graph draws
> whatever components/edges are in the real `flow_plan.json`/`job.json`; the narration derives from the
> real `requirement_spec` rules + flags + `test_report`. A tweaked or fresh BRD reflects
> authentically (different pipeline -> different graph, for real).

**Reliability without faking** comes from: (1) a well-chosen demo doc that reliably flows; (2) the
operator re-running a stage LIVE if the LLM hiccups (the orchestrator already supports the
diagnose->re-run-owner repair loop -- recovery is real, not canned); (3) cold rehearsal. If an
audience-tweaked doc hits a human gate, the operator answers it live at the laptop (honest); the
polished in-UI gate is a v2 flourish.

## 5. Architecture diagram

```
[Business user]                         CITI SERVER (dumb relay)              CITI LAPTOP
   |  upload BRD  --REST-->        [/upload  /job/next  /job/<id>/event]        |
   |                                     ^                    ^                 |
   |<-- SSE narrative --------  [/stream/<id>]               | POST events     |
                                                       GET doc |               |
                                                               |        [fetcher.py] --> input dir
                                                               |        [relay_daemon.py] --watches-->
                                                               |          agents/work/<job>/ + audit.jsonl
                                                               |               |
                                                               |        [OPERATOR triggers Copilot]
                                                               |        etl-orchestrator (real-BRD mode)
                                                               |          -> doc-normalizer -> ... -> test-runner
                                                               |          (agents UNCHANGED; write artifact bus)
[Frontend: HTML/SVG]  self-assembling ETL flow-graph + text assistant rail + reasoning call-outs
```

## 6. The UI hero (agreed vision)

- A **narrating TEXT assistant rail** (chatbot voice, written): "Reading your document... found 3
  sources and 6 rules... building the pipeline... testing... ran clean, 4 rows."
- A **central canvas where the ETL pipeline BUILDS ITSELF**: source nodes fade in -> transform nodes
  (filter/join/sort) appear -> edges draw -> each node fills a **business-readable config** ("Filter:
  keep SETTLED", "Join accounts - first match", "Sort by value down").
- **Reasoning call-outs** pop on the relevant node at key decisions ("account list has duplicates ->
  taking the first match", "moved the filter earlier to run faster") -- this is what makes them
  appreciate the thought process.
- **Lean into pacing**: the real run takes minutes; fill the wait with the live "thinking" state so the
  minutes read as craftsmanship, not lag.
- **Finale**: pipeline glows -> "Tested: ran clean, N rows" -> a peek at the output table.

## 7. Artifact -> visual mapping (the "presenter" -- build generic)

| Artifact (already written by the run) | Business-readable presentation |
|---|---|
| `purity.json` / route | "Reading your document..." |
| `exploder_inventory.json` / `extract_doc.json` | source nodes appear; "found N sources, tier=..." |
| `requirement_spec.json` (typed rules + ambiguities) | "understood N rules"; reasoning call-outs; flags |
| `flow_plan.json` | the flow-graph STRUCTURE draws (nodes + edges, business labels) |
| `job_draft.json` | node configs fill in (animated) |
| `job.json` | pipeline locks/connects fully |
| `test_report.json` | "ran clean, N rows" + output peek |
| `audit.jsonl` | drives the stage-by-stage timing/progress |

## 8. Open questions for the build session (design these)

- **Frontend stack**: vanilla HTML/SVG vs a tiny graph lib for the self-assembling diagram (keep it
  self-contained + easy to host on the Citi server; no heavy build system).
- **Presenter mapping schema**: the exact artifact->{graph-delta, narration-card, reasoning-callout}
  transform (Section 7 is the skeleton). Must be GENERIC (Section 4).
- **Relay event schema**: what the daemon POSTs per change (stage, status, graph delta, text) -- keep
  it data-free.
- **Server API contract**: upload / job-queue / event-ingest / SSE-stream endpoints (thin).
- **Pacing model**: tie animation to the real artifact timestamps vs a smoothing/typewriter layer.
- **The no-intervention demo doc**: author a synthetic BRD that flows clean end-to-end (build it as a
  generator like `agents/examples/gen_complex_real_brd.py`, but tuned so no blocking gate fires).

## 9. First moves for the new session

1. Read this handoff. Confirm branch (cut `feature/demo-ui` from `feature/real-brd-ingestion`).
2. `superpowers:brainstorming` -> finalize the UI opens (Section 8), leaning on `frontend-design` +
   `dataviz`. Biggest design task = the GENERIC presenter (artifact -> visual), and the hero animation.
3. `writing-plans` -> then build: the thin server relay, the two laptop scripts (fetcher +
   watcher-daemon), the HTML/SVG frontend + presenter, and the synthetic demo-doc generator.
4. Rehearse cold end-to-end on the Citi laptop; iterate the demo doc for reliability.

## 10. Constraints carried forward (locked)

- **Agents + artifact bus stay UNCHANGED** (no HTTP in agents; don't touch the `extract_doc.json`
  contract we hardened this session).
- **ASCII-only** in code/logs/authored markdown (RHEL-clean).
- **Model-agnostic + no new LLM calls at demo time** (the presenter is deterministic templating over
  real artifacts).
- Citi-internal server only; laptop-outbound REST (allowed).
- **v2/roadmap** (explicitly deferred): in-UI interactive ask-answer human gate; possibly voice;
  multi-doc / side-by-side.

## 11. Key file pointers (the working system this UI wraps)

- Artifact bus + logs the presenter reads: `agents/work/<job>/*.json`, `agents/work/<job>/audit.jsonl`.
- The graph source: `flow_plan.json` / `job.json` (components + `flows` edges).
- Orchestrator (operator triggers this): `.github/agents/etl-orchestrator.agent.md` (real-BRD step-0 +
  the free-agent loop + human gates).
- Doc-normalizer front door (this session): `agents/tools/{docx_purity,explode_doc,normalize_validate}.py`,
  `.github/agents/doc-normalizer.agent.md`, rung-aware `materialize_golden.py`.
- Real-BRD design + plan: `docs/superpowers/specs/2026-07-08-real-brd-doc-normalizer-design.md`,
  `docs/superpowers/plans/2026-07-08-real-brd-doc-normalizer.md`.
- A worked live example (artifacts to model the presenter on): the `complex_brd` run produced a full
  set (extract_doc -> requirement_spec -> flow_plan -> job_draft -> job -> test_report). Regenerate via
  `agents/examples/gen_complex_real_brd.py` (or author a cleaner no-intervention variant).
