# Demo UI for the ETL Agent System -- Design Spec ("budget-unlock" demo)

- **Date:** 2026-07-09
- **Branch:** feature/demo-ui
- **Status:** design approved in brainstorming; ready for writing-plans
- **Predecessor:** docs/superpowers/handoffs/2026-07-08-demo-ui-handoff.md (context + locked decisions)

ASCII-only throughout (RHEL-clean), matching the engine's existing logging rule.

---

## 1. Goal and audience

The multi-agent ETL system runs today inside the real Citi VS Code Copilot and WORKS. Next audience:
the **super-manager + business people**, to unlock an agentic-AI budget. We wrap the working agent
system in a polished, chatbot-style web UI and demo it as a finished product. This is **real
capability, staged delivery** -- the agents genuinely run; we add a presentation veneer + a run
driver, not fake tech.

**North star:** the audience walks out (a) believing this is a real, working product, and (b)
appreciating the craftsmanship of the reasoning -- enough to fund it.

---

## 2. Scope

- A UI for the **AGENT SYSTEM** (orchestrator + specialists + the doc-normalizer front door), NOT a
  UI for the ETL engine. A business user uploads a BRD, watches a friendly visual "the system is
  building your pipeline" experience, and sees the final built + tested pipeline.
- **v1 (this spec):** the happy path -- a clean end-to-end run of a chosen synthetic BRD, rendered
  live. The code-approval gate is a mirrored beat (operator signs off in VS Code).
- **Out of scope / v2 roadmap:** in-UI interactive human gate (audience approves in the browser),
  voice/TTS, multi-doc / side-by-side.

---

## 3. Hard principles (non-negotiable)

1. **NO hardcoding / NO golden-replay.** Everything runs LIVE. The presenter is GENERIC: it renders
   whatever the ACTUAL artifacts contain. A tweaked or fresh BRD produces a different graph, for real
   (tweak-and-re-run must work on stage).
2. **Agents + artifact bus stay UNCHANGED for correctness.** The Copilot agents do not do HTTP and do
   not touch the hardened `extract_doc.json` contract. (A tiny, additive audit-logging hardening on
   the orchestrator is allowed -- see 10 -- because it only adds an audit line and changes no
   artifact and no correctness path.)
3. **Data-free relay.** The server and frontend only ever see clean, business-readable summaries +
   graph structure -- never raw sample/expected cell values. The daemon strips values on the laptop.
4. **No LLM at demo time.** Narration = canned per-stage templates + the REAL reasoning the run
   already wrote into the artifacts (flow-designer purposes, ambiguity flags). The presentation layer
   only SURFACES what the run produced.
5. **Operator-in-the-loop.** VS Code is not auto-started. A human operator triggers the Copilot run
   and answers any live gate at the laptop. The frontend mirrors state; it never controls Copilot.
6. **Citi-internal only; laptop-outbound REST.** The laptop does all outbound calls; the server never
   reaches into the laptop.
7. **ASCII-only** in all code and authored docs (RHEL).

---

## 4. Architecture

```
[Business user browser]                    CITI SERVER  (FastAPI, unique port)        CITI LAPTOP (operator + VS Code)
   |  open app (served by FastAPI)         +--------------------------------+
   |  upload BRD --POST /upload-->         |  serves dist/ (built React)     |
   |                                       |  POST /job/<id>/event  <--------|--- daemon.py POSTs (data-free)
   |<-- SSE narrative -- GET /stream/<id>--|  GET  /job/next  --------------->|--- fetcher.py pulls doc -> input dir
                                           +--------------------------------+          |
                                                                                [operator triggers Copilot]
                                                                                etl-orchestrator -> ... -> test-runner
                                                                                writes agents/work/<job>/*.json + audit.jsonl
                                                                                       |
                                                                                [daemon.py] polls mtimes ->
                                                                                  generic artifact->data-free-delta -> POST up
```

**Deployment model.** Node is a BUILD-TIME tool only. On a dev box with Node, `vite build` produces a
static `dist/` (inlined HTML/JS/CSS, no runtime CDN). The Citi server runs ONE FastAPI process that
serves `dist/` AND the API/SSE, on a chosen unique port. The server never runs Node. The daemon +
fetcher are plain Python on the laptop. FastAPI and the ETL engine are already present on the server;
our app is additive on its own port and never touches the engine.

**Where the generic transform lives.** The daemon (Python, laptop) does the artifact -> data-free
delta transform (semantic extraction + value stripping). The React frontend is a pure renderer +
animator: it lays out the graph and drives the animation/thinking-state from the delta stream.

---

## 5. Code layout

```
demo/budget_ui/
  daemon/
    daemon.py        # laptop: poll work-dir mtimes -> emit data-free events -> POST /job/<id>/event
    presenter.py     # the GENERIC artifact -> data-free-delta transforms (Python)
    fetcher.py       # laptop: poll GET /job/next -> download the uploaded doc into the input dir
  server/
    app.py           # Citi server: FastAPI relay + static host (serves ./dist)
    dist/            # built React bundle (copied from frontend build output at deploy time)
  frontend/          # React source, built with Vite on the laptop
    src/...
    package.json
    vite.config.*
  README.md          # build + deploy + rehearse steps
```

The demo lives entirely under `demo/budget_ui/`, separate from `agents/` (which stays unchanged).

---

## 6. The demo BRD

- Source: `agents/examples/demo_brd/gen_demo_brd.py` (already built + verified) -- a no-ambiguity,
  verified-tier fork of the complex real-BRD generator. It produces `trade_position_demo.docx` +
  sibling `trades.csv` / `accounts.csv` / `prices.csv`.
- **One fix required (deferred until build time):** align the golden EXPECTED numeric values to the
  engine's float repr so the graded diff passes clean. Change the doc's Expected-Result table:
  `market_value` -> `30200.0 / 20525.0 / 15025.0 / 6901.0` and `closing_price` -> `150.8 / 411.0 /
  150.8 / 689.0`. (The 2-decimal currency the doc currently shows false-fails the string-exact oracle;
  see the diagnostician-data-blind-diff-gap and demo-doc-golden-float-alignment memories.) The
  standard verified-tier method is to author the expected table FROM an actual clean run.
- The pipeline this BRD produces (the reference graph, from the real `trade_position_demo` run): 3
  sources -> FilterRows (keep SETTLED) -> tJoin (accounts) -> tJoin (prices) -> SchemaComplianceCheck
  (validate trade_date) -> tPythonDataFrame (derive market_value) -> SortRow (market_value desc) ->
  FileOutputDelimited. 10 components, 9 flows.

---

## 7. The daemon (laptop)

**Watch loop.** Poll `agents/work/<job>/` every ~500 ms. Track each artifact by (name, mtime). On a
new/changed artifact, run the matching transform in `presenter.py`, emit one or more data-free events,
and POST each to `/job/<id>/event`. `audit.jsonl` carries NO timestamps, so mtime-watching is the
pacing source; the daemon stamps each event with its own observation time.

**Artifact -> event mapping** (the generic presenter, extract half):

| Artifact observed | Events emitted |
|---|---|
| `purity.json` / `exploder_inventory.json` | `stage:reading:active` |
| `extract_doc.json` | `sources` (from `sources_schema`), stage transition |
| `requirement_spec.json` | `rules` (kinds + business labels), `callout` per ambiguity (flag), stage |
| `flow_plan.json` | `nodes` (skeleton, business labels from type+purpose), `callout` per purpose (rationale), `stage:designing` |
| `job_draft.json` | `node_config` (config sublabels fill in), `stage:configuring` |
| `job.json` | `edges` (from `flows[]`), `gate` if a code-bearing cell exists, `stage:wiring` |
| `test_report.json` | `result` (passed/tier/rows/graded, + sample in synthetic mode), `stage:testing`/`done` |
| `audit.jsonl` lines | `stage` transitions; `gate:signed` on `preexec_code_approved` |

**Value stripping.** `presenter.py` derives labels only from config STRUCTURE and rule-declared
literals (a filter value such as "SETTLED" is part of the rule, not sample data). It never reads or
emits `sample_input` / `expected_output` cell values. `result.sample` is included ONLY when the daemon
runs in synthetic-demo mode (a launch flag); for a real audience-uploaded doc it emits counts only.

---

## 8. The event schema (data-free -- the linchpin)

Envelope on every event: `{ "job": "<slug>", "seq": <int>, "t": <epoch_s>, "type": "<type>", ... }`.
`seq` is monotonic per job (ordering + replay + dedup); `t` is the daemon's observation time (pacing).

| type | payload | drives |
|---|---|---|
| `stage` | `stage` (reading/interpreting/designing/configuring/wiring/signoff/testing/done), `status` (active/done) | stepper, rail stage line, thinking-state |
| `sources` | `nodes: [{id, label, kind:"source", sub}]` | source nodes fade in |
| `rules` | `count, items: [{id, kind, label}]` | rail rule enumeration |
| `nodes` | `nodes: [{id, ntype, kind, label, sub}]` | transform/output nodes appear (skeleton) |
| `node_config` | `nodes: [{id, sub}]` | config sublabels fill in |
| `edges` | `edges: [{from, to}]` | edges draw (the connect) |
| `callout` | `node, text, kind:"rationale"\|"flag"` | reasoning bubble pops on a node |
| `gate` | `kind:"code_signoff", node, code, status:"awaiting"\|"signed"` | code-approval mirror beat |
| `result` | `passed, tier, rows, graded:"N/M", sample?: [{col:val}]` | green finale + output table |
| `note` | `text` | optional live reasoning surfaced during a gap |

`kind` on a node is one of: source, filter, join, validate, derive, sort, aggregate, output, op.
`code` in `gate` is transform logic (e.g. the tPythonDataFrame `python_code`), not data -- safe.

---

## 9. The server (Citi, FastAPI)

One FastAPI app, one unique port, serving static + API + SSE.

| Endpoint | Method | Purpose |
|---|---|---|
| `/` and static | GET | serve `dist/` (the built React app) |
| `/upload` | POST | multipart BRD upload; create a job id; enqueue; return `{job}` |
| `/job/next` | GET | the fetcher (laptop) polls; return the next queued job's id + doc download |
| `/job/<id>/event` | POST | the daemon posts one event; append to the job's in-memory log; fan out to SSE clients |
| `/stream/<id>` | GET | SSE (`text/event-stream`); replay the job's event log (late-join catch-up) then stream new events |

- Job state is in-memory per job (an ordered event list + a set of SSE subscriber queues); ephemeral,
  which is right for a demo. Restart clears state.
- Auth: an opaque job id acts as a capability token in the URL; Citi-internal only. Keep it simple.
- SSE via `sse-starlette` (or `StreamingResponse`); async fan-out to subscribers.

---

## 10. The React frontend (the presenter, render half)

Built from the validated prototype (`scratchpad/thinking-state.html`), ported to React + Vite. Uses
Framer Motion for node layout/movement animation.

**Flow.** Upload view -> `POST /upload` -> job id -> watch view -> open SSE `/stream/<id>` -> render
events. State: nodes, edges, node configs, callouts, stage, gate, result.

**Rendering.**
- **Rail** (left): narration derived from `stage` + `rules` + `callout` events; the thinking-state
  pill at the bottom (spinner + rotating thoughts) driven by the current active `stage`.
- **Canvas** (right): the DAG. A generic layered layout (ported from the prototype: longest-path
  layers, sourceless nodes pulled toward their consumer, main-line at row 0) assigns positions;
  Framer Motion `layout` animates nodes into place as the graph grows -- this is the "node movement"
  refinement (nodes enter neutral, then glide to their computed spots rather than popping in placed).
  SVG edges draw on the `edges` event. Call-outs pop on their nodes.
- **Stepper** (bottom): the seven stages; active + past styling.
- **Code-gate**: on `gate:awaiting`, show the exact `code` + "awaiting human sign-off" (the mirror);
  on `gate:signed`, flip to signed and continue. The operator signs in VS Code; a "Sign off
  (operator)" control exists for rehearsal but the real gate is the operator's VS Code action.
- **Finale**: on `result`, green glow on the output node + the output table (synthetic sample) +
  "N rows, N/M graded, tier: verified".

**Pacing.** Reveals are event-gated (each event triggers its reveal); Framer/CSS smoothing makes each
beat land as craft; the thinking-state fills the gaps between events (which are long -- minutes -- in
the real run). Exact dwell/smoothing is CALIBRATED AFTER a live run against the real stage timings; we
do not guess it now.

**How the frontend knows about the code gate** (no Copilot API needed): the `gate` event is emitted by
the daemon the moment `job.json` lands with a code-bearing cell (deterministic, agent-independent);
`gate:signed` follows from the `preexec_code_approved` audit line or the appearance of `test_report`.

---

## 11. Parallel agent-perf work (separable; needed for a fast, clean live demo)

Not part of the UI build, but required before demo day so the run is fast and passes clean. Tracked
separately; the UI can be built and tested against the existing artifacts regardless.

1. **Align the demo golden** (Section 6) so the run reaches a clean `verified` pass with no repair
   loop.
2. **Curate `tJoin` + `tPythonDataFrame`** (add `agents/schemas/*.json`) so the configurator uses
   curated schemas instead of reading engine source -- the ~11 min configurator drops to ~2 min. (Part
   of the component-schema-coverage-gap backlog; for this demo only these two are needed.)
3. **Tiny orchestrator audit hardening:** guarantee a `preexec_code_review_pause` audit line is
   written BEFORE the code-approval stop (additive; no correctness change) so the daemon's gate signal
   is rock-solid. (Optional -- the daemon can already infer the gate from `job.json`.)
4. **Backlog (not demo-blocking):** enrich `run_and_validate`'s `test_report` diff with a value-free
   column+format characterization so the data-blind diagnostician can pinpoint format/precision fixes
   (the diagnostician-data-blind-diff-gap TODO).

Projected run time with 1+2 done: ~32 min -> ~8 min of agent time (the human ambiguity pause is
already gone with the fixed doc). The thinking-state fills it; the presenter talks over it.

---

## 12. Reliability and demo-day operations

- **A well-chosen demo doc** (Section 6) that reliably flows end-to-end.
- **Operator answers any live gate at the laptop** (code sign-off; a fresh audience-tweaked doc that
  hits a human gate). Honest; the frontend mirrors it.
- **Recovery is real, not canned:** if the LLM hiccups, the operator re-runs a stage live (the
  orchestrator's diagnose -> re-run-owner loop). The recovery visual is DESIGNED (a `feedback`-style
  beat) but kept out of the happy-path flow; it exists for the worst case and the "change a rule and
  re-run" flex.
- **Cold rehearsal** end-to-end on the Citi laptop before the demo; calibrate pacing then.

---

## 13. Testing and verification

- **`presenter.py` (daemon transform):** unit-tested with the REAL `trade_position_demo` artifacts as
  fixtures (they are on disk from the live run) -- assert each artifact yields the expected data-free
  events, and assert NO sample/expected cell value ever appears in any emitted event (the data-free
  guarantee, testable).
- **Server:** endpoint tests (upload -> job id; event ingest -> SSE fan-out; late-join replay).
- **Frontend:** render the presenter against a recorded event stream (a fixture captured from the real
  run); visual check of each stage; reduced-motion + responsive checks.
- **End-to-end:** cold rehearsal on the laptop (upload -> operator triggers Copilot -> daemon relays
  -> browser renders the full choreography).

---

## 14. Open risks

- **Doc-normalizer classification:** the real-BRD front door must classify the demo doc's
  Expected-Result table as the answer key (not a 4th source) to reach `verified`. Confirm on the next
  live run; adjust the doc's headings/prose if needed.
- **LLM variance:** a live run can vary (component choice, a stray ambiguity). Mitigated by the
  chosen doc + operator live-recovery + cold rehearsal.
- **Run time:** even at ~8 min, it is a live wait; mitigated by the thinking-state + the presenter
  narrating to the audience while it runs (the frontend is a live backdrop, not a silent stare).

---

## 15. Summary of locked decisions

- Hero = faithful DAG + translating rail (altitude A); the thinking-state is the star.
- Pacing = event-gated reveals + smoothing + live thinking filler; exact dwell calibrated post-build.
- Stack = React + Vite -> static `dist/`; FastAPI server (already present) on a unique port; Python
  daemon + fetcher on the laptop; Framer Motion for node movement.
- Generic transform in the daemon (Python, strips values); React is a pure renderer.
- Data-free event schema (Section 8); labels from config structure + rule literals; output sample
  only in synthetic-demo mode.
- Demo doc = `gen_demo_brd.py` (+ golden float-align).
- Code-approval = mirrored governance beat (operator signs in VS Code; frontend detects via job.json +
  audit).
- Parallel agent-perf = curate tJoin + tPythonDataFrame, align golden, optional audit hardening.
- ASCII-only everywhere (RHEL).
