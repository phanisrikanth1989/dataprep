# Demo UI Phase 3 -- React Frontend (the presenter's render half)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A React + Vite app that consumes the daemon's data-free SSE event stream and renders the "self-building pipeline" hero -- the exact experience validated in the committed prototype -- then builds to a static bundle the FastAPI server hosts.

**Architecture:** A pure `reduce(state, event)` turns the event stream into view state (sources, nodes, edges, node_config, callouts, stage, gate, result). A pure `layout(nodes, edges)` (ported from the prototype) assigns node positions; Framer Motion animates position changes (the "nodes glide into place" refinement). Components render state: a narrating Rail (+ thinking-state), a Canvas (SVG edges + animated nodes + callouts + code-gate + finale), a Stepper. An `useEventStream` hook drives it in LIVE mode (`EventSource` on `/stream/<id>`) or REPLAY mode (a recorded event array -- for dev/verification only, feeding the SAME generic renderer). `vite build` -> `dist/`, which the server serves.

**Tech Stack:** React 18 + Vite 5 + framer-motion. Logic tested with vitest (pure reducer/layout). Render verified with Playwright screenshot in replay mode. The generic renderer is design-agnostic: it draws whatever nodes/edges/labels the events carry.

**Depends on:** the event contract in `docs/superpowers/specs/2026-07-09-demo-ui-design.md` section 8 (hardened), the committed prototype `demo/budget_ui/frontend/prototype-thinking-state.html` (the CSS + layout + choreography source of truth), and the Phase-2 server.

## Global Constraints
- ASCII-only in all authored source (RHEL). Node is BUILD-TIME only; the shipped `dist/` is static (no runtime CDN -- Vite inlines deps).
- **Generic / no-hardcoding:** the renderer draws whatever the events contain. No pipeline-specific node ids, labels, or counts in the render logic. Replay mode feeds RECORDED REAL events to the same generic renderer -- it is a test harness, not a golden-replay demo path.
- **Contract rules (section 8):** `node_config` is AUTHORITATIVE (final ids + `kind`; supersedes the provisional `nodes` skeleton -- drop any skeleton node whose id is absent from node_config); `source` crosswalk links a `sources` node to its FileInput node; `gate:signed` clears the awaiting beat; `stage` drives the stepper; the terminal `end` event CLOSES the EventSource (else the browser auto-reconnects and replays); `result.sample` (present only in synthetic mode) renders the finale table, else counts only; branch the finale on `result.passed` (never a false green).

## File Structure
```
demo/budget_ui/frontend/
  package.json, vite.config.js, index.html, .gitignore (node_modules, dist)
  src/main.jsx, src/App.jsx, src/styles.css
  src/state/reducer.js        # pure (state,event)->state + initialState
  src/state/layout.js         # pure layered DAG layout (ported from the prototype)
  src/hooks/useEventStream.js  # EventSource (live) | array replay
  src/components/{Rail,Canvas,GraphNode,Edges,Callout,CodeGate,Finale,Stepper,Upload}.jsx
  src/replay/sample-events.json  # recorded full-run event stream (from the daemon over the fixtures)
  tests/reducer.test.js, tests/layout.test.js
```
Modify `demo/budget_ui/server/app.py` -- serve the built `dist/` (Task 5).

---

### Task 1: Scaffold Vite + React + deps; record the sample event stream

**Files:** create the frontend scaffold; generate `src/replay/sample-events.json` by running the Phase-1/2 daemon over the fixtures.

- [ ] **Step 1: Scaffold**
```bash
# Scaffold in a TEMP dir and copy in -- `npm create vite` in the non-empty frontend/ dir can offer
# "Remove existing files", which would DELETE the committed prototype that Tasks 2-3 port from.
TMP=$(mktemp -d); ( cd "$TMP" && npm create vite@latest app -- --template react )
mkdir -p demo/budget_ui/frontend/src
cp "$TMP"/app/package.json "$TMP"/app/vite.config.js "$TMP"/app/index.html demo/budget_ui/frontend/
cp -R "$TMP"/app/src/. demo/budget_ui/frontend/src/
cd demo/budget_ui/frontend
npm install
npm install framer-motion
npm install -D vitest @testing-library/react jsdom
printf 'node_modules\ndist\n' > .gitignore
```
Set `package.json` scripts to include `"test": "vitest run"` and keep `"build": "vite build"`, `"dev": "vite"`, `"preview": "vite preview"`.

- [ ] **Step 2: Record a real event stream for replay/verification** (run the daemon over the fixtures, capture the enveloped events):
```bash
cd /Users/aarun/Workspace/Projects/citi/dataprep
python - <<'PY'
import json, shutil, tempfile, pathlib, time
from demo.budget_ui.daemon.daemon import Daemon
fix = pathlib.Path("tests/demo_budget_ui/fixtures/trade_position_demo")
work = pathlib.Path(tempfile.mkdtemp())
cap = []
d = Daemon("demo", str(work), send=cap.append, since=time.time()-1, synthetic=True)
for name in ["extract_doc.json","requirement_spec.json","flow_plan.json","job_draft.json","job.json"]:
    shutil.copy(fix/name, work/name); d.poll()
shutil.copy(fix/"test_report_passed.json", work/"test_report.json"); d.poll()
out = pathlib.Path("demo/budget_ui/frontend/src/replay/sample-events.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(cap, indent=1))
print("wrote", len(cap), "events ->", out)
PY
```

- [ ] **Step 3: Commit** `git add demo/budget_ui/frontend/package.json demo/budget_ui/frontend/vite.config.js demo/budget_ui/frontend/index.html demo/budget_ui/frontend/.gitignore demo/budget_ui/frontend/src && git commit -m "chore(demo-ui): scaffold React/Vite frontend + record sample event stream"` (do NOT add node_modules or dist).

---

### Task 2: The pure reducer + the pure layout (unit-tested with vitest)

**Files:** `src/state/reducer.js`, `src/state/layout.js`, `tests/reducer.test.js`, `tests/layout.test.js`.

**Interfaces:**
- `initialState` and `reduce(state, event) -> state`. State: `{ stage, sources[], rules{count,items}, nodesById{}, order[], edges[], callouts[], gate, result, ended }`. Handle EVERY event type (a `default` that drops `sources`/`rules`/`callout` leaves the rail + reasoning empty -- that is the demo's north star, so it must not be dropped):
  - `sources` -> `state.sources = event.nodes`
  - `rules` -> `state.rules = {count: event.count, items: event.items}`
  - `nodes` (skeleton) -> add provisional `{id,kind,label}` to `nodesById`, append ids to `order`
  - `node_config` (AUTHORITATIVE) -> REPLACE the node set: `nodesById` = the node_config nodes keyed by id (final ids + kind + label + sub + source), and REBUILD `order` from the node_config ids (so a dropped skeleton id like `out_trade_positions` is gone from BOTH `nodesById` and `order` -- else a component iterating `order` derefs `undefined.kind` and crashes)
  - `edges` -> `state.edges = event.edges`
  - `callout` -> push `{node, text, kind}` to `state.callouts`
  - `gate` -> MERGE into `state.gate` (`{...state.gate, ...event}`) -- a `signed` event omits `code`; preserve the earlier `code`
  - `result` -> `state.result = event`
  - `stage` -> `state.stage = {name: event.stage, status: event.status}`
  - `end` -> `state.ended = true`
- `layout(nodesById, edges) -> { pos:{id:{x,y}}, W, H }` -- ported verbatim from the prototype's `layout()` (longest-path layers + sourceless-pull + main-line rows).

- [ ] **Step 1: Failing tests**
```javascript
// tests/reducer.test.js
import { describe, it, expect } from "vitest";
import { reduce, initialState } from "../src/state/reducer.js";
import sample from "../src/replay/sample-events.json";

describe("reducer", () => {
  it("builds the authoritative graph from the recorded stream", () => {
    const state = sample.reduce(reduce, initialState);
    // node_config authoritative -> final ids, no dangling skeleton output id
    const ids = Object.keys(state.nodesById);
    expect(ids).toContain("trade_positions");
    expect(ids).not.toContain("out_trade_positions");
    // every node has a kind (coloring) and the join resolved its lookup name
    expect(ids.every(id => state.nodesById[id].kind)).toBe(true);
    expect(Object.values(state.nodesById).some(n => n.label === "Match accounts")).toBe(true);
    // edges reference only real nodes
    const edgeIds = new Set(state.edges.flatMap(e => [e.from, e.to]));
    expect([...edgeIds].every(id => state.nodesById[id])).toBe(true);
    // finale + terminal
    expect(state.result.passed).toBe(true);
    expect(state.result.rows).toBe(4);
    expect(state.result.outputs).toEqual(["trade_positions"]);
    expect(state.ended).toBe(true);
    expect(state.gate && state.gate.status).toBe("signed");
    // rail + reasoning populated (north star), order has no dropped skeleton id, finale table + preserved code
    expect(state.sources.length).toBe(3);
    expect(state.rules.count).toBe(6);
    expect(state.callouts.length).toBe(5);
    expect(state.order).not.toContain("out_trade_positions");
    expect(state.result.sample.length).toBe(4);
    expect(state.gate.code).toContain("market_value");   // code preserved through the signed merge
  });
});
```
```javascript
// tests/layout.test.js
import { describe, it, expect } from "vitest";
import { reduce, initialState } from "../src/state/reducer.js";
import { layout } from "../src/state/layout.js";
import sample from "../src/replay/sample-events.json";
describe("layout", () => {
  it("positions every node with finite coords and a sane canvas", () => {
    const s = sample.reduce(reduce, initialState);
    const { pos, W, H } = layout(s.nodesById, s.edges);
    for (const id of Object.keys(s.nodesById)) {
      expect(Number.isFinite(pos[id].x)).toBe(true);
      expect(Number.isFinite(pos[id].y)).toBe(true);
    }
    expect(W).toBeGreaterThan(0); expect(H).toBeGreaterThan(0);
  });
  it("guards the empty graph (early beats) with finite dimensions", () => {
    const { W, H } = layout({}, []);
    expect(Number.isFinite(W)).toBe(true); expect(Number.isFinite(H)).toBe(true);
    expect(W).toBeGreaterThan(0); expect(H).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run -> FAIL** (`cd demo/budget_ui/frontend && npx vitest run`).
- [ ] **Step 3: Implement** `reducer.js` (the state machine above) and `layout.js`. Port the prototype's `layout()` to an ES module `layout(nodesById, edges)`: adapt ONLY the first line to `const ids = Object.keys(nodesById);` (every later use is `ids`/`flows`; `edges` as `[{from,to,reject}]` works unchanged); keep the same NW/NH/COLW constants; return `{pos, W, H}`. GUARD the empty graph FIRST: `if (ids.length === 0) return { pos: {}, W: 640, H: 360 };` -- the Canvas renders during the reading/sources beats before any node exists, and an unguarded `Math.max(...[])` returns `-Infinity` (spec section 16.4: never a blank/invalid canvas). Read `demo/budget_ui/frontend/prototype-thinking-state.html`'s `layout()` and port the rest (topo Kahn, longest-path layer, sourceless pull, main line at row 0).
- [ ] **Step 4: Run -> PASS.**
- [ ] **Step 5: Commit** `git add src/state tests && git commit -m "feat(demo-ui): pure event reducer (authoritative graph) + ported layout, vitest-covered"`

---

### Task 3: Components + the event-stream hook (render the prototype's UI from state)

**Files:** `src/hooks/useEventStream.js`, `src/components/*.jsx`, `src/App.jsx`, `src/main.jsx`, `src/styles.css`.

**Interfaces:**
- `useEventStream({ job, replay }) -> state` -- if `replay` (an events array) is given, dispatch them on a timer (a few hundred ms apart) through `reduce`; else open `new EventSource("/stream/"+job)`, `reduce` each `onmessage` JSON, and `close()` on the `end` event.
- Components are presentational, driven by `state` + `layout(...)`: `Rail` (narration lines derived from `stage`/`rules`/`callouts` + a thinking-state pill for the active stage), `Canvas` (an `Edges` SVG layer + Framer-Motion `GraphNode`s positioned by `layout`, using `motion.div` with the `layout` prop so a node animates when its position changes; `Callout`s; a `CodeGate` overlay driven by `state.gate`; a `Finale` driven by `state.result`), `Stepper` (7 steps lit by `state.stage`).

- [ ] **Step 1: Port the styles.** Translate the prototype's `<style>` block into `src/styles.css` (same tokens, node/edge/rail/stepper/gate/finale classes). Keep the instrument/blueprint skin verbatim; it is provisional but validated.
- [ ] **Step 2: Implement the hook + components.** Build each component to render `state` (no pipeline-specific literals). CRITICAL -- key the stepper + rail + thinking-state by the DAEMON's `stage` NAMES (`reading, interpreting, designing, configuring, wiring, signoff, testing`), NOT the prototype's role keys (`interpreter/flow/configurator/assembler/approval/test`): only `reading` matches, so a naive port lights 1 of 7 steps and shows an empty thinking-pill for every later stage (the thinking-state is "the star"). Define ONE canonical ordered STAGES list keyed by the daemon names and re-key the prototype's `THOUGHTS`/rail narration to them. `GraphNode` colors by `node.kind` (`k-<kind>`), shows `label` + `sub`; code badge on `kind==="derive"`. `Edges` draws a bezier per `state.edges` between `layout` anchors (reject edges styled distinctly). `Rail` narrates from `state` (stage line + rule list from `state.rules` + a thinking pill for `state.stage.name`). `CodeGate` shows `state.gate.code` when `status==="awaiting"`, and KEEPS the code visible under a "signed" stamp when `"signed"` (matching the prototype). `Finale` branches on `state.result.passed`: pass -> green glow on the `result.outputs` node(s) + the `result.sample` table (counts if no sample); non-pass -> a neutral "refining" state (never green). Link a `sources` node to its FileInput node via the shared `source` crosswalk.
- [ ] **Step 3: App.** `App.jsx` reads `?job=` (live) or `?replay=1` (import `sample-events.json`) from the URL, calls `useEventStream`, and renders `<Rail/>` + `<Canvas/>` + `<Stepper/>`. An `Upload` view (POST `/upload` a chosen file -> `{job}` -> set `?job=`) is the default when neither param is present.
- [ ] **Step 4: Sanity build** `npx vite build` -> confirm `dist/` is produced with no errors. Commit `git add -A && git commit -m "feat(demo-ui): React components + event-stream hook rendering the pipeline"` (dist is gitignored).

---

### Task 4: Render verification (Playwright screenshot in replay mode)

**Files:** none committed beyond a note; this task PROVES the UI renders.

- [ ] **Step 1: Build + preview + screenshot.**
```bash
cd demo/budget_ui/frontend
npx vite build
# serve the built app and open it in replay mode; screenshot the final frame
npx vite preview --port 5232 &   # or: python -m http.server -d dist 5232
```
Then load `http://localhost:5232/?replay=1` in a browser (Playwright MCP or the local browser), let the replay run to the finale, and take a screenshot. VERIFY visually: 10 nodes with business labels ("Keep status = SETTLED", "Match accounts", "Compute market_value"), edges connecting `in_trades..trade_positions` (no dangling `out_trade_positions`), colored nodes (kind), the code-gate beat, and the green finale with the 4-row table. If anything is wrong (dangling node, missing color, no table), fix the reducer/component and rebuild.
- [ ] **Step 2:** Record the verification outcome in the report; commit any fixes. Kill the preview server.

---

### Task 5: The server serves the built frontend

**Files:** modify `demo/budget_ui/server/app.py`; test `tests/demo_budget_ui/test_server.py`.

- [ ] **Step 1: Failing test** (actually create a `dist/`, assert `/` serves it AND `/job/next` still wins):
```python
def test_root_serves_index_and_api_still_wins():
    import pathlib
    from fastapi.testclient import TestClient
    import demo.budget_ui.server.app as A
    dist = pathlib.Path(A.__file__).parent / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text("<html>DEMO_UI_ROOT</html>")
    try:
        A.mount_static()                                   # (re)mount now that dist exists
        c = TestClient(A.app)
        assert "DEMO_UI_ROOT" in c.get("/").text           # dist index served at /
        A.store.__init__()
        assert c.get("/job/next").json()["job"] is None    # API route wins over the catch-all mount
    finally:
        (dist / "index.html").unlink(); dist.rmdir()
```

- [ ] **Step 2: Implement.** Add a `mount_static()` at the END of `app.py` (after all routes): if `Path(__file__).parent / "dist"` exists, `app.mount("/", StaticFiles(directory=<dist>, html=True), name="static")` (import `from fastapi.staticfiles import StaticFiles`, `from pathlib import Path`). Call `mount_static()` once at import. Because the API routes are registered (by their decorators) BEFORE the mount, Starlette matches them first, so `/upload`,`/job/*`,`/stream/*` win over the `/` catch-all; exposing `mount_static()` lets the test (re)mount after creating a `dist/`.
- [ ] **Step 3: Run -> PASS** (`python -m pytest tests/demo_budget_ui/test_server.py -v`).
- [ ] **Step 4: Commit** `git add demo/budget_ui/server/app.py tests/demo_budget_ui/test_server.py && git commit -m "feat(demo-ui): server hosts the built React dist/ (API routes take precedence)"`

---

## Self-Review
- **Spec coverage:** section 10 render half -> Tasks 2-4; the hardened contract rules (node_config authoritative, source crosswalk, kind, gate:signed, stage stepper, end-closes-stream, finale sample + passed-branch) -> the reducer (Task 2) + components (Task 3); section 9 static hosting -> Task 5; the node-movement refinement -> Framer `layout` prop (Task 3).
- **Placeholder scan:** none. The visual port references the committed prototype (the CSS/layout source of truth) rather than re-inventing.
- **Type consistency:** `reduce`/`initialState` and `layout` signatures match the tests; `useEventStream` returns the same `state` shape the components read.

## Execution Handoff
Subagent-Driven. Units: **A = scaffold + reducer + layout (Tasks 1-2, vitest-verified)**; **B = components + hook + App (Task 3)**; **C = render verification + server static (Tasks 4-5)**. Final whole-branch review of the Phase-3 diff. Because UI correctness is visual, Task 4's Playwright screenshot is a required gate, not optional.
